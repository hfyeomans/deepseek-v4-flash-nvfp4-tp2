# Validation requirements

A result is useful when someone can tell what ran. Save image/runtime and
model identity, hardware, context, concurrency, generation settings, DSpark
and prefix-cache state with each run.

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

Match prompts, generation, warmups and prefix-cache state with DSpark on/off.
Use actual output counts and elapsed time; streamed chunks may contain several
tokens. Report first output, decode and total time separately. Test several
prompt types, single-request latency and two-request aggregate throughput.

Check the answers against the non-speculative baseline as well as timing them.
Sampling variation isn't the same as corrupted output, and different kernels
needn't produce identical tokens. Test that separately if you need the guarantee.

## Historical request-recording limitation

The old recorder retained mutable requests, so later tool turns could appear
in earlier saved payloads. Affected records are marked; responses, usage and
timings remain valid, but those payloads can't be replayed exactly. The fix
snapshots data before sending. An HTTP regression failed before the fix and
passes after it, including nested tool changes. See
[evidence](../results/request-recording-regression.json).

## Mixed tool responsiveness

The independent probe reuses the automatic tool check. Five regressions cover
delayed preparation, early long completion, fresh prefixes, both tool payloads
and wrong tool-result answers. The two tool cases failed before implementation
and passed afterward. A separate delayed-second-response check passed functionally
but correctly failed overlap. Server admission/prefill still need server evidence.
