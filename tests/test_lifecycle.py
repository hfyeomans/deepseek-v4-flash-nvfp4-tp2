"""Run real recipe scripts against a stateful Docker boundary; no GPU needed."""

import json
import fcntl
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]

DOCKER = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
path = pathlib.Path(os.environ["FAKE_STATE"])
state = json.loads(path.read_text())
args = sys.argv[1:]
state["calls"].append(args)
def finish(code=0, output="", error=""):
    path.write_text(json.dumps(state))
    if output: print(output)
    if error: print(error, file=sys.stderr)
    sys.exit(code)
def value(flag):
    return args[args.index(flag) + 1]
def container(ref):
    return next((c for c in state["containers"].values()
                 if c["Id"] == ref or c["Name"] == "/" + ref), None)
if state.get("daemon_error"):
    finish(1, error="Cannot connect to the Docker daemon")
if args[:2] == ["image", "inspect"]:
    image = state["images"].get(args[2])
    if not image: finish(1, error="Error: No such image: " + args[2])
    finish(output=json.dumps([image]))
if args[:2] == ["container", "inspect"]:
    item = container(args[2])
    if not item: finish(1, error="Error: No such container: " + args[2])
    finish(output=json.dumps([item]))
if args[:1] == ["build"]:
    if state.get("fail_build"): finish(7, error="build failed")
    state["next_image"] = state.get("next_image", 0) + 1
    image = {"Id": "sha256:image-" + str(state["next_image"]), "Config": {"Labels": {}}}
    for i, arg in enumerate(args):
        if arg == "--label":
            key, val = args[i + 1].split("=", 1)
            image["Config"]["Labels"][key] = val
    state["images"][value("-t")] = image
    if state.pop("edit_env_on_build", False):
        with open(os.environ["ORIGINAL_CONFIG"], "a") as config:
            config.write("\\nBIND_ADDRESS=0.0.0.0\\n".replace("\\n", "\n"))
    finish(output="built")
if args[:1] == ["create"]:
    if state.get("fail_create"): finish(8, error="invalid mount")
    if container(value("--name")): finish(125, error="Conflict")
    if state.pop("restart_during_create", False):
        container("dsv4-nvfp4")["State"]["Status"] = "running"
    state["next_container"] = state.get("next_container", 0) + 1
    ident = "container-" + str(state["next_container"])
    labels = {}
    for i, arg in enumerate(args):
        if arg == "--label":
            key, val = args[i + 1].split("=", 1)
            labels[key] = val
    image_id = next(arg for arg in args if arg.startswith("sha256:"))
    model_args = args[args.index(image_id) + 1:]
    state["containers"][ident] = {"Id": ident, "Name": "/" + value("--name"),
        "Image": image_id, "Config": {"Labels": labels, "Cmd": model_args, "Env": []},
        "State": {"Status": "created", "Health": {"Status": "starting"}}}
    finish(output=ident)
if args[0] in ("start", "stop", "rename", "rm"):
    item = container(args[1])
    if not item: finish(1, error="No such container")
    if args[0] == "start":
        if state.get("fail_start"): finish(9, error="start failed")
        item["State"]["Status"] = "running"
    elif args[0] == "stop":
        if state.get("fail_stop"): finish(10, error="stop failed")
        item["State"]["Status"] = "exited"
    elif args[0] == "rename":
        if container(args[2]): finish(1, error="name conflict")
        item["Name"] = "/" + args[2]
    elif args[0] == "rm": del state["containers"][item["Id"]]
    finish(output=item["Id"])
finish(2, error="Unsupported Docker call: " + repr(args))
'''


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "recipe with spaces"
        self.repo.mkdir()
        for name in ("build.sh", "serve.sh", "recipe.sh", "example.env", ".dockerignore"):
            if (REPO / name).exists():
                shutil.copy2(REPO / name, self.repo / name)
        for name in ("scripts", "config", "patches", "tests"):
            shutil.copytree(REPO / name, self.repo / name, ignore=shutil.ignore_patterns("__pycache__"))
        for path in REPO.glob("Dockerfile*"):
            shutil.copy2(path, self.repo / path.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.bin / "docker").write_text(DOCKER)
        (self.bin / "docker").chmod(0o755)
        (self.bin / "git").write_text("#!/bin/sh\ncase \"$*\" in *rev-parse*) echo 0f59188db1504b042ce621842bdde6c0fe862df6;; esac\n")
        (self.bin / "git").chmod(0o755)
        self.state_file = self.root / "docker.json"
        self.save({"calls": [], "images": {}, "containers": {}})
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                        FAKE_STATE=str(self.state_file), ORIGINAL_CONFIG=str(self.repo / ".env"))
        self.env.pop("RECIPE_ENV_FILE", None)
        self.configure()

    def state(self):
        return json.loads(self.state_file.read_text())

    def save(self, state):
        self.state_file.write_text(json.dumps(state))

    def configure(self, **overrides):
        (self.repo / ".env").write_text((self.repo / "example.env").read_text() + "\n" +
            "\n".join(f"{key}={shlex.quote(str(value))}" for key, value in overrides.items()) + "\n")

    def run_recipe(self, *args):
        return subprocess.run(["bash", str(self.repo / "recipe.sh"), *args],
                              env=self.env, cwd=self.root, text=True,
                              capture_output=True, timeout=20)

    def apply(self):
        result = self.run_recipe()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def clear_calls(self, **changes):
        state = self.state()
        state.update(changes, calls=[])
        self.save(state)

    def mutations(self):
        return [call for call in self.state()["calls"]
                if call[0] in ("build", "create", "start", "stop", "rename", "rm")]

    def current(self):
        return next(c for c in self.state()["containers"].values() if c["Name"] == "/dsv4-nvfp4")

    def test_fresh_apply_builds_then_creates_and_starts(self):
        result = self.apply()
        actions = [c[0] for c in self.mutations()]
        self.assertEqual(actions, ["build", "build", "build", "create", "rename", "start"])
        self.assertIn("Starting", result.stdout)
        self.assertEqual(self.current()["State"]["Status"], "running")

    def test_unchanged_running_and_comment_edits_do_nothing(self):
        self.apply()
        with (self.repo / ".env").open("a") as config:
            config.write("\n# A comment, not a setting change\nUNRELATED_SECRET=private-value\n")
        self.clear_calls()
        self.apply()
        self.assertEqual(self.mutations(), [])
        self.assertNotIn("private-value", self.state_file.read_text())

    def test_stop_then_apply_resumes_without_build_or_replacement(self):
        self.apply()
        self.assertEqual(self.run_recipe("stop").returncode, 0)
        self.clear_calls()
        self.apply()
        self.assertEqual([c[0] for c in self.mutations()], ["start"])

    def test_bind_change_replaces_preserving_previous_container_and_cache(self):
        self.apply()
        old_id = self.current()["Id"]
        self.configure(BIND_ADDRESS="0.0.0.0")
        self.clear_calls()
        self.apply()
        self.assertEqual([c[0] for c in self.mutations()], ["create", "stop", "rename", "rename", "start"])
        old = self.state()["containers"][old_id]
        self.assertEqual(old["State"]["Status"], "exited")
        self.assertIn("previous", old["Name"])
        create = self.mutations()[0]
        self.assertIn("0.0.0.0:8000:8000", create)
        self.assertIn("dsv4-nvfp4-kernels:/root/.cache/flashinfer", create)

    def test_plan_never_mutates_docker(self):
        result = self.run_recipe("plan")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("build", result.stdout.lower())
        self.assertEqual(self.mutations(), [])

    def test_build_failure_preserves_running_container(self):
        self.apply()
        old_id = self.current()["Id"]
        self.clear_calls(fail_build=True)
        result = self.run_recipe("rebuild")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.current()["Id"], old_id)
        self.assertEqual(self.current()["State"]["Status"], "running")
        self.assertFalse(any(c[0] in ("stop", "rename") for c in self.mutations()))

    def test_invalid_serving_config_fails_before_any_mutation(self):
        self.configure(TENSOR_PARALLEL_SIZE=0)
        result = self.run_recipe()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TENSOR_PARALLEL_SIZE", result.stderr)
        self.assertEqual(self.mutations(), [])

    def test_stop_and_status_work_with_invalid_serving_settings(self):
        self.apply()
        self.configure(TENSOR_PARALLEL_SIZE=0)
        self.clear_calls()
        self.assertEqual(self.run_recipe("status").returncode, 0)
        self.assertEqual(self.run_recipe("stop").returncode, 0)
        self.assertEqual([c[0] for c in self.mutations()], ["stop"])

    def test_daemon_error_is_not_absence(self):
        self.clear_calls(daemon_error=True)
        result = self.run_recipe()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot connect", result.stderr)
        self.assertEqual(self.mutations(), [])

    def test_failed_candidate_creation_keeps_current_running(self):
        self.apply()
        self.configure(BIND_ADDRESS="0.0.0.0")
        self.clear_calls(fail_create=True)
        result = self.run_recipe()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.current()["State"]["Status"], "running")
        self.assertEqual([c[0] for c in self.mutations()], ["create"])

    def test_failed_start_preserves_backup_and_reports_recovery(self):
        self.apply()
        old_id = self.current()["Id"]
        self.configure(MAX_MODEL_LEN=801000)
        self.clear_calls(fail_start=True)
        result = self.run_recipe()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Recovery", result.stderr)
        self.assertIn(old_id, result.stderr)
        self.assertIn(old_id, self.state()["containers"])
        self.assertFalse(any(c[0] == "rm" for c in self.mutations()))

    def test_logging_file_content_change_replaces_without_build(self):
        self.apply()
        with (self.repo / "config/logging.json").open("a") as output:
            output.write("\n")
        self.clear_calls()
        self.apply()
        self.assertNotIn("build", [c[0] for c in self.mutations()])
        self.assertIn("create", [c[0] for c in self.mutations()])

    def test_build_only_does_not_start_model(self):
        result = self.run_recipe("build")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([c[0] for c in self.mutations()], ["build"] * 3)

    def test_missing_env_has_setup_hint(self):
        (self.repo / ".env").unlink()
        result = self.run_recipe()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("example.env", result.stderr)
        self.assertEqual(self.state()["calls"], [])

    def test_unrelated_test_and_patch_docs_changes_do_not_rebuild(self):
        self.apply()
        for path in ("tests/test_operator_config.py", "patches/README.md"):
            with (self.repo / path).open("a") as output:
                output.write("\n# Documentation-only edit\n")
        self.clear_calls()
        self.apply()
        self.assertEqual(self.mutations(), [])

    def test_packaged_patch_change_rebuilds_and_replaces(self):
        self.apply()
        image_id = self.current()["Image"]
        with (self.repo / "patches/0001-scope-dspark-expert-format.patch").open("a") as output:
            output.write("\n")
        self.clear_calls()
        self.apply()
        self.assertNotEqual(self.current()["Image"], image_id)
        self.assertEqual([c[0] for c in self.mutations()][:4], ["build"] * 3 + ["create"])

    def test_bad_memory_fraction_cannot_interrupt_current_service(self):
        self.apply()
        for value in ("not-a-number", "nan", "0", "1.1"):
            with self.subTest(value=value):
                self.configure(GPU_MEMORY_UTILIZATION=value)
                self.clear_calls()
                result = self.run_recipe()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("GPU_MEMORY_UTILIZATION", result.stderr)
                self.assertEqual(self.mutations(), [])
                self.assertEqual(self.current()["State"]["Status"], "running")

    def test_unrelated_container_is_never_replaced(self):
        self.apply()
        state = self.state()
        state["containers"][self.current()["Id"]]["Config"] = {"Labels": {}, "Cmd": ["other-app"]}
        self.save(state)
        self.clear_calls()
        result = self.run_recipe()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unrecognized", result.stderr)
        self.assertEqual(self.mutations(), [])

    def test_pre_automation_recipe_is_migrated_with_backup(self):
        self.apply()
        old_id = self.current()["Id"]
        state = self.state()
        state["images"]["dsv4-nvfp4:recipe"]["Config"]["Labels"] = {}
        state["containers"][old_id]["Config"]["Labels"] = {}
        state["containers"][old_id]["Config"]["Env"] = ["DSPARK_VERIFY_WEIGHT_COVERAGE=1"]
        self.save(state)
        self.clear_calls()
        self.apply()
        self.assertIn("previous", self.state()["containers"][old_id]["Name"])
        self.assertNotEqual(self.current()["Id"], old_id)

    def test_prepared_candidate_is_reused_after_interruption(self):
        self.apply()
        self.configure(BIND_ADDRESS="0.0.0.0")
        self.clear_calls(fail_stop=True)
        self.assertNotEqual(self.run_recipe().returncode, 0)
        self.clear_calls(fail_stop=False)
        self.apply()
        self.assertNotIn("create", [c[0] for c in self.mutations()])
        self.assertEqual(len(self.state()["containers"]), 2)

    def test_promote_candidate_when_old_was_already_archived(self):
        self.apply()
        old_id = self.current()["Id"]
        self.configure(BIND_ADDRESS="0.0.0.0")
        self.clear_calls(fail_stop=True)
        self.assertNotEqual(self.run_recipe().returncode, 0)
        state = self.state()
        state["containers"][old_id]["Name"] = "/dsv4-nvfp4-previous-interrupted"
        state["containers"][old_id]["State"]["Status"] = "exited"
        self.save(state)
        self.clear_calls(fail_stop=False)
        self.apply()
        self.assertEqual([c[0] for c in self.mutations()], ["rename", "start"])
        self.assertIn(old_id, self.state()["containers"])

    def test_env_edited_during_build_applies_original_snapshot(self):
        self.clear_calls(edit_env_on_build=True)
        self.apply()
        create = next(c for c in self.mutations() if c[0] == "create")
        self.assertIn("127.0.0.1:8000:8000", create)
        self.assertIn("BIND_ADDRESS=0.0.0.0", (self.repo / ".env").read_text())
        self.clear_calls()
        self.apply()
        create = next(c for c in self.mutations() if c[0] == "create")
        self.assertIn("0.0.0.0:8000:8000", create)
        self.assertNotIn("build", [c[0] for c in self.mutations()])

    def test_concurrent_operation_is_rejected_before_docker(self):
        lock_path = self.repo / "work/lifecycle/lock"
        lock_path.parent.mkdir(parents=True)
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_recipe()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Another recipe operation", result.stderr)
        self.assertEqual(self.state()["calls"], [])

    def test_container_restarted_during_preparation_is_stopped_before_replacement(self):
        self.apply()
        old_id = self.current()["Id"]
        self.assertEqual(self.run_recipe("stop").returncode, 0)
        self.configure(BIND_ADDRESS="0.0.0.0")
        self.clear_calls(restart_during_create=True)
        self.apply()
        self.assertEqual(self.state()["containers"][old_id]["State"]["Status"], "exited")
        self.assertIn("stop", [c[0] for c in self.mutations()])

    def test_printed_actions_keep_an_alternate_configuration(self):
        self.configure(CONTAINER_NAME="custom-coder")
        alternate = self.root / "alternate profile.env"
        shutil.move(self.repo / ".env", alternate)
        self.env["RECIPE_ENV_FILE"] = str(alternate)
        result = self.apply()
        for label, action in (("Stop", "stop"), ("Status", "status")):
            commands = [line.split(": ", 1)[1] for line in result.stdout.splitlines()
                        if line.startswith(label + ": ")]
            self.assertEqual(len(commands), 1, f"Missing {label} command")
            self.assertEqual(shlex.split(commands[0]), ["env", f"RECIPE_ENV_FILE={alternate.resolve()}",
                                                    "bash", str(self.repo / "recipe.sh"), action])


if __name__ == "__main__":
    unittest.main()
