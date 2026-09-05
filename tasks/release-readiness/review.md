# Adversarial release review

Reviewed the complete `c678eeb` snapshot and the subsequent release changes.
Two independent reviewers inspected executable behavior, newcomer commands,
duplication/state ownership, SDLC structure and unnecessary complexity. Each
reviewer cross-checked the other's changes; the main task ran the common suite.

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

The local suite passes **28 test methods**: five benchmark, five mixed-probe,
eight observation, nine trace-analysis and one real patch-command method with
three Docker-stage subcases. Bash syntax and ShellCheck pass. The new local
runner initially exposed a Python import-path mistake; using module discovery
fixed it before release. Historical results, input manifests, prompts and all
three runtime patch files retain their original bytes.

No critical runtime defect was established in the pinned default launch. No
confirmed duplicate generation dispatch, normal state update or competing
implementation was found. The review kept the small script-based structure;
it did not add an application framework or move adaptive code into this recipe.

CPU fixtures do not prove GPU compatibility, model quality, large-context
accuracy or acceleration. [Deployment qualification](verification.md) records
the actual rebuild, serving checks and their limits. Remaining publication
administration belongs in [current state](state.md); passing tests alone does not
mean the GitHub repository has been made public.
