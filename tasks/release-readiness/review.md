# Adversarial release review

Two independent reviewers audited `c678eeb` and release changes for behavior,
onboarding, duplication, state ownership and SDLC. They cross-checked fixes;
the main task ran the shared suite.

| Finding | Resolution | Evidence |
|---|---|---|
| Fixed-output benchmarks accepted missing or invalid termination | Require `finish_reason=length` and reject SSE error envelopes | Negative missing/invalid reason and explicit server-error tests fail before the fixes and pass afterward |
| Four streaming feature paths omitted observations | One API stream boundary records request, received events/raw lines, partial errors, completion, closure and timing | Success, malformed/partial data, HTTP/SSE errors, missing DONE, early cancellation and CLI failure-output tests |
| Two profiler inputs could silently replace one detail report | Validate all destination identities before any output write | Same-rank collisions in one and nested case directories fail before creating output; distinct ranks remain valid |
| Reapplying a Docker patch could reverse it with exit zero | Add `--forward` to all three patch commands | Real command fixtures apply once, reject the second application and retain patched content |
| Fresh-host rollback selected an image the build never made | Explicit recovery `FINAL_IMAGE`, separate checkout/container and health recheck | Commands checked against actual build/launcher defaults |
| README suggested a second launch after the first-run guide | Remove redundant launch; walkthrough leaves the selected profile running | Independent command-path review |
| Completed acceptance/default selection still described as pending | Reconcile current prose/checklists; explain historical build-stage status | Links point to completed evidence; raw result JSON unchanged |
| No common local verification entry point or CPU CI | Add `scripts/check-local.sh` and a minimal read-only CI workflow | Local runner passes with `PYTHONPATH` unset; CI status is recorded separately |

## Verification and scope

All **28 methods** pass: five benchmark, five mixed-probe, eight observation,
nine trace-analysis and one patch-command method with three Docker subcases.
Bash/ShellCheck pass. Module discovery fixed an initial test-runner import
error. Historical results, manifests, prompts and three runtime patches are
byte-identical.

Review found no critical default-launch defect, duplicate generation/state
update or competing implementation. The small script structure remains;
adaptive code stays in its own repo.

CPU tests cannot establish GPU compatibility, model accuracy or acceleration.
See [deployment qualification](verification.md) for live evidence and
[release state](state.md) for publication status.
