# What the pinned benchmark actually measures

This audit applies to vLLM commit
`0f59188db1504b042ce621842bdde6c0fe862df6`, using `--backend vllm` and
`/v1/completions`. Check another version independently.

## Counts and streaming

The client requests streamed usage and usually replaces estimates with server
token counts. Without usage it falls back to tokenization, but saved JSON does
not identify which path supplied the counts. Server deltas independently
confirmed 262,144 prompt and 1,024 output tokens across the two 128K pilot
requests, with zero prefix hits.

TTFT ends at the first stream event with choices. TPOT divides the remaining
generation time by output tokens minus one. ITL measures gaps between stream
events, which can carry several DSpark tokens. In the C1 pilot, 512-token outputs
produced 298 and 212 ITL intervals. Those gaps are not per-token timings.

Source: [streaming client and usage handling](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/benchmarks/lib/endpoint_request_func.py#L175),
[metric calculation](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/benchmarks/serve.py#L587).

## Why the built-in mixed probe was rejected

The pilot sent two 131,072-input/512-output requests at concurrency one with
`--probe-request-rate 0.5`. Three tiny probes reported a median **23.809 seconds**,
which server timings did not support as short-request server latency.

Probes bypass the request semaphore but share a connection pool capped at
`max_concurrency`. At concurrency one, the long response holds the only
connection, so probe timing includes client-side waiting. Without connection
traces we cannot split that delay precisely. It is not evidence for changing
the scheduler. See the [pilot record](../results/builtin-probe-measurement-failure.json).

The probe loop waits for a response, then sleeps. Rate 0.5 means a two-second
pause after completion, not arrivals every two seconds. The main throughput
timer also waits for the final probe and its sleep. Main token totals exclude
probes; global speculative counters include them.

Use [the independent probe](../mixed_probe.py) with server running/waiting
observations. It measures completion-call overlap; admission and prefill still
need server evidence. Raising benchmark concurrency to avoid the connection
limit changes the workload.

Source: [shared connector](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/benchmarks/serve.py#L808),
[serial probe loop](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/benchmarks/serve.py#L978),
[duration boundary](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/benchmarks/serve.py#L1068).

## Matched prompts without cross-run prefix hits

A fresh `cache_salt` in `--extra-body` changes the first cache-block hash and
its descendants, separating identical seeded prompts across runs. Record it
with `--metadata`; extra body is not saved automatically. Salting neither
purges old entries nor prevents reuse within a run. Check server hit deltas.

The [context/batch example](context-batch.md#run-a-benchmark-case) includes
these controls. Record warm state, build activity, request counts, sampling
and actual input/output lengths.

Source: [completion request salt](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/entrypoints/openai/completion/protocol.py#L185),
[cache hash construction](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/core/kv_cache_utils.py#L543).

## The recipe's chat benchmark

`benchmark.py` uses chat completions. It warms each exact prose/code/reasoning
prompt, then runs repeats and one concurrent prose/code pair. It requires
server usage, the requested output count and final `[DONE]`; token counts have
no estimation fallback. First output means visible content or reasoning. Rates
include prefill and stream completion.

To compare the same longer coding prompt across DSpark configurations:

```bash
python3 benchmark.py --label dspark-long-code --tokens 512 --repeats 3 \
  --code-prompt-file code-prompt.txt --cache-mode uncached \
  --output long-code-dspark.json
```

Use the same UTF-8 file and arguments for the control. Results retain prompt
bytes, SHA-256, usage, warmups and a unique salt for every request. Verify
server hit deltas too: HTTP payload regressions check construction, not live
cache isolation.

The pair remains **prose plus code**, so a long-code override tests mixed
short/long inputs. Speculative counters include all warmups and workloads;
they cannot isolate long-code acceptance. Synthetic code also does not measure
broad coding accuracy.

Source: [chat request salt](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/entrypoints/openai/chat_completion/protocol.py#L475),
[chat rendering forwards the salt](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/renderers/online_renderer.py#L440).
