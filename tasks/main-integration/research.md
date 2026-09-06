# Branch integration findings

The owner requested direct integration into `main`, without a PR or loss of
work. Before integration, no local or remote `main` existed. GitHub's default
was `recipe/validated-tp2`. Both local worktrees were clean, with no stashes.

All local and remote branch tips belong to one continuous history:

| Branch | Tip before integration |
|---|---|
| `recipe/validated-tp2` | `0b67089` |
| `release/community-readiness` | `0b67089` |
| `docs/concise-voice` | `1ed5bfa` |
| `recipe/operator-config` | `f4f53e8` |

Ancestry checks confirmed that `f4f53e8` contains every tip above. Creating
`main` at that commit preserves the complete history without conflict resolution
or rewritten commits. CI passed for `f4f53e8` before integration.

The clone fetched only the original default branch by default. It needs to
track `main` as well so ordinary fetch/pull commands keep the new branch current.
The separate adaptive-verification repository is outside this change.
