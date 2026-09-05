# Validation requirements

Every result records runtime/image identity, model revision, hardware, context,
concurrency, generation settings, and whether DSpark and prefix caching are active.

| Feature | Observable pass condition |
|---|---|
| Model and TP=2 | Correct revision, complete weights, both GPUs used, recorded memory |
| DSpark | Expected draft weights load; proposed and accepted token metrics increase |
| Chat | Exact synthetic answer with no unintended reasoning or special-token leakage |
| Multi-turn | Retains a unique fact introduced in an earlier turn |
| Reasoning | Thinking produces separated reasoning and content; effort controls render correctly |
| Automatic tools | Selects the appropriate tool and valid schema-conforming arguments |
| Required/named tools | Honors the requested call mode and tool name |
| Tool round trip | Final answer incorporates a synthetic value available only in tool output |
| Multiple calls | Distinct call IDs and correctly associated returned values |
| JSON | Valid JSON and exact requested schema/fields |
| Streaming | Content/reasoning/tool deltas assemble correctly, with valid finish reasons |
| Concurrency | Two requests retain their own unique facts and both finish correctly |
| Prefix reuse | Reused prefix does not replace or contaminate a changed suffix |
| Cancellation | Aborted stream followed by a successful independent request |
| Long context | Retrieves unique facts at multiple positions within each measured length |
| Restart | Same short suite passes after relaunching the pinned recipe |

## DSpark performance

Compare identical prompts and generation settings with speculation on and off.
Use real completion-token counts and elapsed time; never count streamed chunks as
tokens. Report time to first token separately from decode and total request time.
Warmup and prefix-cache conditions must be matched. Compare multiple prompt types
because acceptance depends on the workload. Record concurrency-one latency and
concurrency-two aggregate throughput separately.

Speculative decoding does not establish correctness merely by increasing speed.
Check functional outputs against the non-speculative baseline and distinguish
sampling variation from malformed or corrupted responses. Do not promise exact
token equality across kernels unless that property was separately demonstrated.

## Historical request-recording limitation

The original verifier stored a mutable request object. Later tool-turn messages
could therefore appear inside an earlier saved request. Affected observations
are explicitly annotated: their response, server usage and timing remain valid,
but the saved request is not an exact replay payload. The fix snapshots request
data before transmission. An HTTP-boundary regression failed before the fix and
passes afterward, including later transcript and nested tool-definition changes.
See [regression evidence](../results/request-recording-regression.json).

## Mixed tool responsiveness

The independent mixed probe can reuse the automatic tool check. Five local
regressions cover delayed prompt preparation, completed-long rejection, fresh
prefixes, both actual tool payloads and an incorrect tool-result answer. The two
new tool tests failed before the option existed and pass afterward. A separate
review delayed the second tool response past the long request: functional checks
passed, but the overall overlap check correctly failed. Server admission and
prefill remain separately observed properties, not conclusions from client timing.
