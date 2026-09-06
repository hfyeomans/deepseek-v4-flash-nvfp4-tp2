# Branch integration state

`main` contains all four recipe branches through `f4f53e8`, including the
automated lifecycle, documentation edits, code, patches and recorded findings.
The original branches, `recipe-1m-k5` tag and release worktree are retained.

Before creating `main`, a local Git bundle was saved under the workspace's
`work/main-integration/` directory. `git bundle verify` confirmed that it contains
complete history. No branch was deleted and no history was rewritten.

Verification on `main` passed: Bash syntax, ShellCheck, all 74 CPU test methods,
282 local documentation links and 32 anchors across 58 documents, plus whitespace
checks. Historical results, runtime patches and benchmark fixtures are unchanged.

The current branch references now point to `main`; historical measurement
branches remain labeled as historical. Existing local files and the separate
adaptive repository are unchanged. GPU qualification remains pending for the
new lifecycle; branch integration does not add a GPU performance result.
