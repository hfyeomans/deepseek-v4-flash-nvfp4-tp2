"""Coordinate image/container lifecycle; build.sh and serve.sh own their specs."""

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import uuid


OWNER = "deepseek-v4-flash-nvfp4-tp2"
BUILD_LABEL = "recipe.build-inputs"
OWNER_LABEL = "recipe.owner"
SPEC_LABEL = "recipe.serving-spec"
TARGET_LABEL = "recipe.container-name"


def run(args, *, env=None, capture=True):
    result = subprocess.run(args, env=env, text=True, capture_output=capture)
    if result.returncode:
        raise RuntimeError((result.stderr or "Command failed: " + shlex.join(args)).strip())
    return result.stdout or ""


def inspect(kind, name):
    result = subprocess.run(["docker", kind, "inspect", name], text=True, capture_output=True)
    if result.returncode:
        missing = f"No such {kind}:"
        if missing in result.stderr:
            return None
        raise RuntimeError(result.stderr.strip() or f"Cannot inspect {kind} {name}")
    records = json.loads(result.stdout)
    if len(records) != 1:
        raise RuntimeError(f"Expected one {kind} for {name}")
    return records[0]


def labels(item):
    return (item or {}).get("Config", {}).get("Labels") or {}


def phase(message):
    print(message, flush=True)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_digest(root, spec):
    root = root.resolve()
    dockerfiles = sorted(root.glob("Dockerfile*"))
    paths = {root / "build.sh", root / ".dockerignore", *dockerfiles}
    for dockerfile in dockerfiles:
        for line in dockerfile.read_text().splitlines():
            if not re.match(r"^\s*(COPY|ADD)\s", line, re.IGNORECASE):
                continue
            parts = shlex.split(line)
            if len(parts) != 3 or parts[0].upper() != "COPY" or parts[1].startswith("--"):
                raise RuntimeError(f"Unsupported build input in {dockerfile.name}: {line}. Update build-input tracking before applying.")
            source = (root / parts[1]).resolve()
            if not source.is_relative_to(root.resolve()) or not source.is_file():
                raise RuntimeError(f"COPY input must be a file inside the recipe: {parts[1]}")
            paths.add(source)
    return digest([spec, [(str(p.relative_to(root)), hashlib.sha256(p.read_bytes()).hexdigest())
                          for p in sorted(paths)]])


def recipe_container(item):
    if labels(item).get(OWNER_LABEL) == OWNER:
        return True
    config = item.get("Config", {})
    return ("DSPARK_VERIFY_WEIGHT_COVERAGE=1" in (config.get("Env") or [])
            and "--tool-call-parser" in (config.get("Cmd") or [])
            and "deepseek_v4" in (config.get("Cmd") or []))


def check_container(item, name):
    if item and (item.get("Name") != "/" + name or not recipe_container(item)):
        raise RuntimeError(f"{name} belongs to an unrecognized container. Choose another CONTAINER_NAME; no container was changed.")


@contextmanager
def operation(root, config):
    work = root / "work" / "lifecycle"
    work.mkdir(parents=True, exist_ok=True)
    with (work / "lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another recipe operation is running in this checkout.") from None
        with tempfile.TemporaryDirectory(prefix="config-", dir=work) as directory:
            frozen = Path(directory) / "profile.env"
            frozen.write_text("".join(f"{key}={shlex.quote(value)}\n" for key, value in config.items()))
            frozen.chmod(0o600)
            yield dict(os.environ, RECIPE_ENV_FILE=str(frozen))


def spec_from(root, script, env):
    return json.loads(run(["bash", str(root / script), "--print-spec"], env=env))


def describe(item):
    state = item["State"]
    health = state.get("Health", {}).get("Status", "no health check")
    return f"{state['Status']} / {health}"


def show_service(root, config, item):
    phase(f"Container: {config['CONTAINER_NAME']} ({describe(item)})")
    phase("Starting or running does not mean healthy; use the existing health/API checks.")
    phase(f"Profile: TP={config['TENSOR_PARALLEL_SIZE']}, context={config['MAX_MODEL_LEN']}, "
          f"GPU memory utilization={config['GPU_MEMORY_UTILIZATION']}, slots={config['MAX_NUM_SEQS']}")
    host = config["BIND_ADDRESS"]
    if host == "0.0.0.0":
        host = "127.0.0.1"
    phase(f"Client: http://{host}:{config['PORT']}/v1\nModel: {config['SERVED_MODEL_NAME']}")
    phase("Logs: " + shlex.join(["docker", "logs", "--timestamps", "-f", config["CONTAINER_NAME"]]))
    selected = Path(os.environ["RECIPE_ENV_FILE"]).resolve()
    command = ["bash", str(root / "recipe.sh")]
    if selected != (root / ".env").resolve():
        command = ["env", f"RECIPE_ENV_FILE={selected}", *command]
    for label, action in (("Status", "status"), ("Stop", "stop")):
        phase(label + ": " + shlex.join([*command, action]))
    if config["BIND_ADDRESS"] == "0.0.0.0":
        phase("LAN clients use the GPU host address in place of 127.0.0.1.")


def recovery(old, candidate, name):
    if not old:
        return
    failed = name + "-failed-" + uuid.uuid4().hex[:8]
    print("Recovery: the previous container and its logs are preserved.", file=sys.stderr)
    for command in (["docker", "stop", candidate["Id"]],
                    ["docker", "rename", candidate["Id"], failed],
                    ["docker", "rename", old["Id"], name],
                    ["docker", "start", old["Id"]]):
        print(shlex.join(command), file=sys.stderr)


def execute(root, config, action, env):
    name = config.get("CONTAINER_NAME", "")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", name):
        raise RuntimeError("CONTAINER_NAME must be a valid Docker container name in .env.")
    if action in ("stop", "status"):
        current = inspect("container", name)
        check_container(current, name)
        if not current:
            phase(f"No container named {name}.")
        elif action == "status":
            phase(f"{name}: {describe(current)}")
        else:
            run(["docker", "stop", current["Id"]])
            phase(f"Stopped {name}; container, image, logs and caches retained.")
        return

    phase(f"Phase 1: validate configuration from {os.environ['RECIPE_ENV_FILE']}.")
    build_spec = spec_from(root, "build.sh", env)
    serving = None if action == "build" else spec_from(root, "serve.sh", env)
    wanted_build = build_digest(root, build_spec)
    image = inspect("image", config["IMAGE"])
    current = None if action == "build" else inspect("container", name)
    check_container(current, name)
    needs_build = action == "rebuild" or labels(image).get(BUILD_LABEL) != wanted_build
    if action == "plan":
        if needs_build:
            phase("Plan: build image (missing, changed or unrecorded build inputs), then "
                  + ("replace the current container." if current else "create a container."))
        else:
            desired = serving_digest(serving, image, config)
            matching = current and labels(current).get(SPEC_LABEL) == desired and current["Image"] == image["Id"]
            phase("Plan: " + ("reuse the unchanged container (resume if stopped)." if matching
                             else "reuse the image and replace/create the container."))
        return

    if needs_build:
        phase("Phase 2: build image using Docker's cache; any current service stays in place.")
        run(["bash", str(root / "build.sh")], env=dict(env, RECIPE_BUILD_INPUTS=wanted_build), capture=False)
        if build_digest(root, spec_from(root, "build.sh", env)) != wanted_build:
            raise RuntimeError("Build inputs changed during the build. Rerun recipe.sh; the current container was not changed.")
        image = inspect("image", config["IMAGE"])
        if not image or labels(image).get(BUILD_LABEL) != wanted_build:
            raise RuntimeError("Built image is missing its expected build record; current container was not changed.")
    else:
        phase("Phase 2: reuse the image; build inputs are unchanged.")
    if action == "build":
        phase(f"Image ready: {config['IMAGE']} ({image['Id']}). No container was started.")
        return

    refreshed = inspect("container", name)
    if (refreshed or {}).get("Id") != (current or {}).get("Id"):
        raise RuntimeError("The active container changed during the build; rerun recipe.sh. It was not stopped.")
    current = refreshed
    desired = serving_digest(serving, image, config)
    if current and labels(current).get(SPEC_LABEL) == desired and current["Image"] == image["Id"]:
        state = current["State"]["Status"]
        if state in ("created", "exited"):
            phase("Phase 3: resume the unchanged container.")
            run(["docker", "start", current["Id"]])
        elif state == "running":
            phase("Phase 3: settings match; leave the running container in place.")
        else:
            raise RuntimeError(f"Container is {state}; inspect it before applying changes.")
        show_service(root, config, inspect("container", name))
        return

    candidate_name = name + "-candidate"
    candidate = inspect("container", candidate_name)
    if candidate:
        if (labels(candidate).get(OWNER_LABEL) != OWNER or labels(candidate).get(TARGET_LABEL) != name
                or candidate["State"]["Status"] != "created"):
            raise RuntimeError(f"{candidate_name} already exists outside a pending recipe update; it was not changed.")
        if labels(candidate).get(SPEC_LABEL) != desired or candidate["Image"] != image["Id"]:
            run(["docker", "rm", candidate["Id"]])
            candidate = None
    if not candidate:
        phase("Phase 3: prepare a stopped candidate before interrupting the current service.")
        options = list(serving["docker_options"])
        options[options.index("--name") + 1] = candidate_name
        candidate_id = run(["docker", "create", *options,
                            "--label", f"{OWNER_LABEL}={OWNER}",
                            "--label", f"{SPEC_LABEL}={desired}",
                            "--label", f"{TARGET_LABEL}={name}",
                            image["Id"], *serving["model_args"]]).strip()
        candidate = inspect("container", candidate_id)
    else:
        phase("Phase 3: reuse the prepared candidate from an interrupted update.")

    latest = inspect("container", name)
    if (latest or {}).get("Id") != (current or {}).get("Id"):
        raise RuntimeError("The active container changed during preparation; rerun recipe.sh. It was not stopped.")
    current = latest
    archived = False
    try:
        if current:
            phase("Phase 4: stop and retain the previous container, including its logs.")
            if current["State"]["Status"] not in ("created", "exited"):
                run(["docker", "stop", current["Id"]])
            backup = name + "-previous-" + uuid.uuid4().hex[:8]
            run(["docker", "rename", current["Id"], backup])
            archived = True
            phase(f"Previous container: {backup}")
        phase("Phase 5: promote and start the prepared container.")
        run(["docker", "rename", candidate["Id"], name])
        run(["docker", "start", candidate["Id"]])
    except RuntimeError:
        if archived:
            recovery(current, candidate, name)
        else:
            print("The candidate is retained for retry; inspect the current container before rerunning recipe.sh.", file=sys.stderr)
        raise
    show_service(root, config, inspect("container", name))


def serving_digest(spec, image, config):
    normalized = dict(spec, image=image["Id"])
    logging_hash = hashlib.sha256(Path(config["LOGGING_CONFIG"]).read_bytes()).hexdigest()
    return digest([normalized, logging_hash])


def main():
    parser = argparse.ArgumentParser(description="Apply .env through the recipe's build and serving paths.")
    parser.add_argument("action", nargs="?", default="apply",
                        choices=("apply", "plan", "build", "rebuild", "stop", "status"))
    action = parser.parse_args().action
    root = Path(os.environ["RECIPE_DIR"])
    keys = re.findall(r"^([A-Z][A-Z_0-9]*)=", (root / "example.env").read_text(), re.MULTILINE)
    config = {key: os.environ[key] for key in keys if key in os.environ}
    try:
        with operation(root, config) as env:
            execute(root, config, action, env)
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print(f"Recipe stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
