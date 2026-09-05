# Release findings

Two independent reviews inspected the complete clean snapshot `c678eeb`, then
cross-reviewed the fixes. The scope covered executable build/serve/client paths,
state ownership, accidental repeated work, first-user instructions, SDLC checks
and unsupported claims. No architectural expansion was justified.

The demonstrated defects were incomplete benchmark stream acceptance, omitted
streaming diagnostics, colliding profiler report destinations, reverse patch
application and a rollback image mismatch. Cross-review also caught an explicit
server-error envelope being ignored and an onboarding command that launched a
second container with the wrong image. See [resolution and evidence](review.md).

The first-run prerequisite instructions were checked against the official
[HF CLI guide](https://huggingface.co/docs/huggingface_hub/guides/cli) and
[NVIDIA Container Toolkit installation guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
on September 5, 2026. CLI setup, GPU visibility, checkpoint reuse and the source
build passed rehearsal on the original Linux host. Existing drivers and
Docker layers make this a same-host rehearsal, not an independent clean-machine
installation. Raw host evidence stays outside the published repository.

## Ownership decision

The API client owns stream transport, snapshots, closure and one observation
record. Feature checks retain their own semantic assertions. The benchmark
keeps its separate timing path because general feature observations would change
the measured workload. This fixes four missing observation paths without adding
a forwarding layer or a second request/state owner. Revert the shared boundary
if it causes duplicate dispatch, changes cancellation or loses partial evidence;
regressions exercise those conditions.

Profiler analysis validates report destinations before writing. Existing result
formats and filenames remain unchanged for valid input. Frozen baseline copies
and historical measurement records are intentional provenance, not dead code.
