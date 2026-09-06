# Lifecycle automation state

Design agreed: automatic apply after editing `.env`, with an optional preview.
Implemented on `recipe/operator-config` and included in `main`; recovery is
`a2a699b`. The [plan](plan.md), [research](research.md) and [verification](verification.md)
record ownership, review findings and failure paths.

`recipe.sh` now chooses build, resume or replacement and offers plan/build/
rebuild/stop/status actions. It retains the previous container, logs and caches.
Current documentation uses this path; historical measurements and frozen rollback
syntax remain labeled with their original context.

Local verification passed: Bash syntax, ShellCheck and 74 CPU test methods,
including 21 operator and 25 lifecycle methods. The documentation scan checked
280 local links and 32 anchors across 55 documents. Whitespace checks passed;
historical results, runtime patches and benchmark fixtures are unchanged.

The GPU host is untouched. Existing image/API/performance validation stays
separate; the owner's GPU walkthrough of this automation is still required.
