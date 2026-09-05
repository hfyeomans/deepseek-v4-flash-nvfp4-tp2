"""Exercise the real shell entrypoints without Docker, Git access or GPUs."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


REPO = Path(__file__).resolve().parents[1]


class OperatorConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls_file = self.root / "calls.jsonl"
        recorder = '''#!/usr/bin/env python3
import json, os, pathlib, sys
tool = pathlib.Path(sys.argv[0]).name
with open(os.environ["TEST_CALLS"], "a") as output:
    output.write(json.dumps([tool, *sys.argv[1:]]) + "\\n")
if tool == "git" and "rev-parse" in sys.argv:
    print("0f59188db1504b042ce621842bdde6c0fe862df6")
if tool == "docker":
    if os.environ.get("TEST_DOCKER_FAIL"):
        sys.exit(17)
    print("test-container-id")
'''
        for name in ("docker", "git"):
            executable = self.bin / name
            executable.write_text(recorder)
            executable.chmod(0o755)
        self.config = self.root / "profile with spaces.env"
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                        TEST_CALLS=str(self.calls_file),
                        RECIPE_ENV_FILE=str(self.config))

    def run_script(self, name, *args):
        return subprocess.run(["bash", str(REPO / name), *args],
                              cwd=self.root, env=self.env, text=True,
                              capture_output=True, timeout=15)

    def calls(self):
        if not self.calls_file.exists():
            return []
        return [json.loads(line) for line in self.calls_file.read_text().splitlines()]

    def configure(self, **overrides):
        self.config.write_text((REPO / "example.env").read_text() + "\n" + "\n".join(
            f"{key}={shlex.quote(str(value))}" for key, value in overrides.items()) + "\n")

    def launch(self, **overrides):
        self.configure(**overrides)
        result = self.run_script("serve.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][:2], ["docker", "run"])
        return result, calls[0]

    @staticmethod
    def value(args, flag):
        return args[args.index(flag) + 1]

    def test_missing_config_blocks_launch_before_docker(self):
        result = self.run_script("serve.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("example.env", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_missing_config_blocks_build_before_git_or_docker(self):
        result = self.run_script("build.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("example.env", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_custom_config_wins_and_preserves_paths_from_another_directory(self):
        self.env["IMAGE"] = "old-image:do-not-use"
        self.env["TEST_PRIVATE_TOKEN"] = "do-not-forward"
        result, args = self.launch(IMAGE="local-model:tested", CONTAINER_NAME="my-model",
                                   HF_CACHE="/cache with spaces", SERVED_MODEL_NAME="my-coder",
                                   BIND_ADDRESS="10.0.150.247", PORT=8123)
        self.assertIn("local-model:tested", args)
        self.assertNotIn("old-image:do-not-use", args)
        self.assertIn("/cache with spaces:/root/.cache/huggingface", args)
        self.assertEqual(self.value(args, "--served-model-name"), "my-coder")
        self.assertIn("Client base URL: http://10.0.150.247:8123/v1", result.stdout)
        self.assertIn("Model: my-coder", result.stdout)
        self.assertIn("docker stop my-model", result.stdout)
        self.assertIn("Starting; wait for healthy", result.stdout)
        self.assertNotIn("do-not-forward", " ".join(args))
        self.assertNotIn("--env-file", args)

    def test_build_and_serve_share_one_image_setting(self):
        source = self.root / "source with spaces"
        source.mkdir()
        self.configure(IMAGE="local-model:shared", SOURCE_DIR=source)
        result = self.run_script("build.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        builds = [call for call in self.calls() if call[:2] == ["docker", "build"]]
        self.assertEqual(len(builds), 3)
        self.assertEqual(self.value(builds[-1], "-t"), "local-model:shared")
        self.calls_file.unlink()
        result = self.run_script("serve.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("local-model:shared", self.calls()[0])

    def test_missing_field_cannot_fall_back_to_a_stale_shell_export(self):
        self.configure()
        self.config.write_text("\n".join(line for line in self.config.read_text().splitlines()
                                         if not line.startswith("IMAGE=")) + "\n")
        self.env["IMAGE"] = "stale-image:previous-test"
        for script in ("build.sh", "serve.sh"):
            with self.subTest(script=script):
                result = self.run_script(script)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Missing IMAGE", result.stderr)
                self.assertEqual(self.calls(), [])

    def test_selected_profile_and_stable_names(self):
        _, args = self.launch()
        expected = {"--name": "dsv4-nvfp4", "--max-model-len": "1000000",
                    "--gpu-memory-utilization": "0.96", "--max-num-seqs": "2",
                    "--max-num-batched-tokens": "2048",
                    "--long-prefill-token-threshold": "1792"}
        for flag, value in expected.items():
            self.assertEqual(self.value(args, flag), value)
        self.assertIn("dsv4-nvfp4:recipe", args)
        self.assertIn("dsv4-nvfp4-kernels:/root/.cache/flashinfer", args)
        self.assertEqual(json.loads(self.value(args, "--speculative-config"))["num_speculative_tokens"], 5)

    def test_native_request_completion_health_and_retention_options(self):
        _, args = self.launch()
        for flag in ("--enable-log-requests", "--enable-log-outputs", "--no-enable-log-deltas"):
            self.assertIn(flag, args)
        self.assertEqual(self.value(args, "--max-log-len"), "256")
        self.assertEqual(self.value(args, "--health-start-period"), "15m")
        self.assertEqual(self.value(args, "--health-interval"), "30s")
        self.assertEqual(self.value(args, "--log-driver"), "json-file")
        self.assertIn("max-file=3", args)
        self.assertIn("VLLM_LOGGING_CONFIG_PATH=/etc/vllm/logging.json", args)
        self.assertIn("readonly", self.value(args, "--mount"))

    def test_request_logging_can_be_disabled_without_disabling_health(self):
        _, args = self.launch(LOG_REQUESTS=0)
        self.assertNotIn("--enable-log-requests", args)
        self.assertNotIn("--enable-log-outputs", args)
        self.assertIn("--health-cmd", args)
        self.assertNotIn("--disable-uvicorn-access-log", args)

    def test_diagnostic_controls_keep_the_selected_context(self):
        _, args = self.launch(DSPARK=0, EAGER=1, LONG_PREFILL_TOKEN_THRESHOLD=512)
        self.assertNotIn("--speculative-config", args)
        self.assertNotIn("--compilation-config", args)
        self.assertIn("--enforce-eager", args)
        self.assertEqual(self.value(args, "--max-model-len"), "1000000")
        self.assertEqual(self.value(args, "--long-prefill-token-threshold"), "512")

    def test_invalid_or_incomplete_config_has_no_docker_effects(self):
        for setting, value in (("IMAGE", ""), ("REVISION", "main"),
                               ("DSPARK", "yes"), ("MAX_LOG_LEN", "-1"),
                               ("HEALTH_TIMEOUT_SECONDS", "5);print('injected')")):
            with self.subTest(setting=setting):
                self.configure(**{setting: value})
                result = self.run_script("serve.sh")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(setting, result.stderr)
                self.assertEqual(self.calls(), [])

    def test_failed_docker_creation_does_not_claim_startup(self):
        self.configure()
        self.env["TEST_DOCKER_FAIL"] = "1"
        result = self.run_script("serve.sh")
        self.assertEqual(result.returncode, 17)
        self.assertNotIn("Created", result.stdout)
        self.assertNotIn("Client base URL", result.stdout)

    def test_command_line_overrides_cannot_break_client_or_health_settings(self):
        self.configure()
        for args in (("--port", "8124"), ("--port=8124",),
                     ("--served-model-name", "different-model"),
                     ("--config", "another-config.yaml")):
            with self.subTest(args=args):
                result = self.run_script("serve.sh", *args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(".env", result.stderr)
                self.assertEqual(self.calls(), [])

    def test_normal_logging_has_no_debug_and_emits_status_once(self):
        code = '''import json, logging, logging.config, sys
logging.config.dictConfig(json.load(open(sys.argv[1])))
logging.getLogger("vllm.v1.engine").debug("hidden-engine-debug")
logging.getLogger("vllm.v1.engine").info("engine-stats")
logging.getLogger("vllm.entrypoints.serve.utils.request_logger").debug("prompt-excerpt")
logging.getLogger("vllm.entrypoints.serve.utils.request_logger").info("request-status")
logging.getLogger("uvicorn.access").info("health-status-200")
'''
        result = subprocess.run([sys.executable, "-c", code, str(REPO / "config/logging.json")],
                                text=True, capture_output=True, check=True)
        self.assertNotIn("hidden-engine-debug", result.stdout)
        self.assertNotIn("prompt-excerpt", result.stdout)
        for message in ("engine-stats", "request-status", "health-status-200"):
            self.assertEqual(result.stdout.count(message), 1)

    def test_health_command_checks_the_configured_port_and_rejects_errors(self):
        class HealthHandler(BaseHTTPRequestHandler):
            status = 200

            def do_GET(self):
                self.send_response(self.status if self.path == "/health" else 404)
                self.end_headers()

            def log_message(self, *_args):
                pass

        with ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                _, args = self.launch(SERVER_PORT=server.server_port)
                command = self.value(args, "--health-cmd")
                for status in (200, 503, 204):
                    HealthHandler.status = status
                    result = subprocess.run(["bash", "-c", command], text=True,
                                            capture_output=True, timeout=10)
                    self.assertEqual(result.returncode == 0, status == 200)
            finally:
                server.shutdown()
                worker.join()


if __name__ == "__main__":
    unittest.main()
