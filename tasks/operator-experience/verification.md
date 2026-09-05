# Verification, 2026-09-05

`bash scripts/check-local.sh` passed: Bash syntax, ShellCheck and **42 CPU test
methods**, including 14 operator tests. The health test needed permission to
bind a temporary localhost socket in this sandbox. It made no GPU requests.

The entrypoint tests execute real Bash scripts with fake Docker/Git boundaries.
They cover required config, paths with spaces, image agreement, the selected
profile, model/client identity, logging switches, diagnostic controls, missing
or invalid settings and failed container creation. A real local HTTP stub
confirmed the generated health command accepts 200 and rejects 503 and 204.
The logging test confirms normal DEBUG records are suppressed and INFO records
aren't duplicated.

The missing-config tests failed against the original scripts, then passed.
Adversarial review found two more defects, each reproduced before its fix:

| Finding | Fix | Result |
|---|---|---|
| Missing IMAGE inherited an old shell export | Clear recipe-owned names before sourcing config | Build and serve now reject the incomplete file before effects |
| Extra CLI flags overrode the port/alias used by health and client output | Require all launcher settings through `.env`; reject CLI arguments | Separate and equals-form overrides fail before Docker |

The independent reviewer reran all 14 operator tests and confirmed both fixes.
No further actionable defects were found in the bounded review.

Local Markdown paths/anchors passed the documentation scan; `git diff --check`
passed. Historical `results/`, runtime patches and benchmark fixtures are
unchanged from `1ed5bfa`. Current instructions use `.env`; recovery commands for
the frozen `recipe-1m-k5` tag keep that version's older syntax. Updated prose
received humanizer and then Hank's technical-voice passes.

Pinned source inspection confirmed request/output flags, the negative
`--no-enable-log-deltas` flag, custom logger config support and the DEBUG-only
prompt detail behavior. A full image build, actual vLLM logs, GPU health and
performance under the new logging defaults remain for the owner's retest.
The existing host/container was not changed. No public release was made.
