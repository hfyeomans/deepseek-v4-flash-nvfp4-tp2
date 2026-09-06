# Operator feedback, 2026-09-05

The owner is walking through the recipe. Build and launch use different image
variables (`FINAL_IMAGE` and `IMAGE`), names describe a first run, the kernel
volume carries an assistant name, and launch output gives no readiness or
client guidance. The primary profile also requires overrides to 64K defaults.

The pinned upstream [Dockerfile](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/docker/Dockerfile#L575)
invokes `setup.py bdist_wheel` in three places. That can reach the deprecated
install command during wheel assembly. The reported warning lacks its build
step heading, so the exact emitting package isn't established.
[PyPA](https://packaging.python.org/en/latest/discussions/setup-py-deprecated/)
deprecates direct invocation, not setuptools or the setup.py configuration file.
Migration needs a separate full build and runtime qualification.

Pinned vLLM source has `--enable-log-requests`, `--max-log-len`, output logging
and access logs. Its [request logger](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/entrypoints/serve/utils/request_logger.py)
prints prompt text only at DEBUG; INFO prints request IDs and parameters.
The user clarified that normal runs must have no DEBUG output. Keep all loggers
at INFO; document opt-in DEBUG for the request logger alone. Native Docker probes
will call `/health`; vLLM access logs will report HTTP status. A streaming HTTP
200 isn't evidence that generation finished; final output logs and the client
stream establish that boundary.

The duplication review confirmed one launch owner and the split image setting.
It recommends one config loader, no polling daemon or new HTTP middleware.
Historical measurements and frozen-tag rollback commands must stay intact.

## Stopped container name conflict

The owner stopped `dsv4-nvfp4` and reran `bash serve.sh`. Docker rejected the
name because stopping retains the container. The launcher unconditionally
calls `docker run`; its printed `docker start` command is easy to miss.
The running guide explains replacement, but the launch path gives no recovery
hint when a saved container exists.

The changed setting was `BIND_ADDRESS=0.0.0.0`. Docker's published address is
chosen at container creation. Rebuilding the image cannot update that address
in an existing container. The owner emphasized that this distinction must be
visible to anyone following the recipe, before they rebuild unnecessarily.

## Kernel provenance clarification

`build.sh` targets architecture 12.0 using the pinned SM120 fork and CUDA 13.0.3.
The original build provenance records the same target. The ABI Dockerfile
removes the incompatible FlashInfer JIT cache and fixes header/linker lookup;
it contains no CUDA kernel source edits. All three recipe patches modify Python
files. Source-image records retain packaged FlashInfer cubins, so this isn't a
claim that every GPU binary was compiled locally. Existing component profiles
provide a starting point for future kernel work, not proof of kernel optimality.
