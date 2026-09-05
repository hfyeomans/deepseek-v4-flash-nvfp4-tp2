# Release findings

Two independent reviewers audited `c678eeb` and cross-checked fixes. They
covered build/serve/clients, state ownership, duplication, onboarding, SDLC
and unsupported claims. No architectural expansion was needed.

Findings: incomplete stream acceptance/diagnostics, colliding report paths,
reverse patching and a rollback-image mismatch. Cross-review caught ignored
server errors and an onboarding command using the wrong image for a second
container. See [resolutions](review.md).

Prerequisites were checked against the
[HF CLI guide](https://huggingface.co/docs/huggingface_hub/guides/cli) and
[NVIDIA Container Toolkit guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
on September 5, 2026. CLI setup, GPU visibility, cache reuse and source build
passed on the existing host. Installed drivers and cached layers prevent
calling it a fresh-machine test. Raw host logs remain private.

## Ownership decision

The API client owns transport, request snapshots, closure and one observation.
Feature checks own assertions. Benchmarks keep separate timing semantics.
This fixes four missing record paths without another request owner or forwarding
layer. Regressions cover duplicate dispatch, cancellation and partial evidence;
revert the boundary if those break.

Check profiler destinations before writing. Valid reports keep their formats.
Frozen baselines and old results stay because they explain what we measured.
