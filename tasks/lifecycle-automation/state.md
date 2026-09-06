# Lifecycle automation state

Design agreed: automatic apply after editing `.env`, with an optional preview.
Implementation in progress on `recipe/operator-config`; recovery is `a2a699b`.
The [plan](plan.md) and [research](research.md) define ownership and failure paths.
The GPU host is untouched. Existing API/performance validation stays separate.
