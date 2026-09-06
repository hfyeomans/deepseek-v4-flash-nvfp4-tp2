# Verification, 2026-09-05

`bash scripts/check-local.sh` passed: Bash syntax, ShellCheck and **47 CPU test
methods**, including 19 operator tests. The health test needed permission to
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

The initial independent review reran all 14 operator tests then present and confirmed both fixes.
No further actionable defects were found in the bounded review.

Two later tests cover the exposed `TENSOR_PARALLEL_SIZE` setting. They failed
against the hardcoded launcher and passed after configuration wiring and
positive-integer validation were added. The default-profile assertion confirms
TP2. The override test checks command arguments only; it doesn't qualify TP4
or any other hardware configuration. Existing GPU measurements remain TP2.

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

## Saved-container follow-up

Two new regression methods reproduced the raw name conflict across seven
container states before the fix, then passed. The launcher now performs only
a read-only inspection when the name exists. It suggests resuming only for
`exited` or `created` states and never starts, stops or removes an existing container.
A third test covers a name claimed between inspection and creation; Docker's
failure remains visible and no startup success is printed. The daemon-failure
test also confirms the underlying connection error remains visible.

Independent lifecycle review found one documentation issue: saving Docker logs
with stdout redirection alone could lose stderr before removal. The replacement
command now saves both streams with `2>&1`. No other actionable lifecycle or
duplication findings were reported. This follow-up made no GPU-host changes
and doesn't establish startup, throughput or model-quality results.

## Kernel provenance documentation

Checked the explanation against `build.sh`, both patch Dockerfiles, the patch
inventory and saved build provenance. It distinguishes SM120 compilation and
integration fixes from CUDA arithmetic edits, and preserves upstream attribution.
The component table and future-task links received Humanizer and then Hank's
technical-voice passes. Markdown link/anchor and whitespace checks passed.
This was a documentation-only change; no runtime tests or GPU experiments ran.
