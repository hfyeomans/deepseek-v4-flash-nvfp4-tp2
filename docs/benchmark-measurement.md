# What the pinned benchmark actually measures

This audit applies to vLLM commit
`0f59188db1504b042ce621842bdde6c0fe862df6`, using `--backend vllm` and
`/v1/completions`. Check another version independently.

## Counts and streaming

The client requests streamed usage and normally replaces dataset estimates with
the server's actual prompt and completion counts. When usage is absent, it has
tokenizer-based fallbacks; saved JSON does not identify that provenance. For the
128K-input pilot, server metric deltas independently confirmed 262,144 prompt
tokens and 1,024 output tokens across two requests, with no prefix-cache hits.

TTFT ends at the first stream event containing choices. TPOT divides elapsed
generation time after that event by actual output tokens minus one. It is an
average, including the effects of multi-token bursts. ITL measures time between
stream events: with DSpark, an event may contain several tokens. In the C1 pilot,
512-token outputs produced 298 and 212 ITL intervals. Those intervals are not
individual-token observations.

Source: [streaming client and usage handling](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/benchmarks/lib/endpoint_request_func.py#L175),
[metric calculation](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/benchmarks/serve.py#L587).

## Why the built-in mixed probe was rejected

Our pilot sent two 131,072-input/512-output main requests at client concurrency
one, with `--probe-request-rate 0.5`. Three tiny probes completed. Their reported
median was **23.809 seconds**, but aggregate server timing did not support
interpreting that as short-request server latency.

The source explains the discrepancy: main requests and probes share an HTTP
connection pool capped at `max_concurrency`. Probes bypass the main semaphore,
but they still need that connection. At concurrency one, the long response holds
the sole connection; a probe's timer includes its client-side wait. We did not
capture connection tracing, so we cannot assign an exact fraction of each delay.
This measurement does not justify a server scheduling change.
[Preserved pilot observation](../results/builtin-probe-measurement-failure.json).

The probe loop also awaits each response before sleeping for the inverse of the
rate. A value of 0.5 gives a two-second pause after completion, not an independent
arrival every two seconds. The benchmark awaits the final probe and its sleep
before stopping the main throughput timer. Main token totals exclude probes,
while global speculative metric deltas include them.

Use [the independent request-bound probe](../mixed_probe.py), with server
running/waiting observations, for mixed-request responsiveness. Its own proof
boundary is completion-call overlap; server admission and prefill timing still
require separate evidence. Do not increase the main benchmark concurrency to
work around the connection limit and describe the result as the same workload.

Source: [shared connector](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/benchmarks/serve.py#L808),
[serial probe loop](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/benchmarks/serve.py#L978),
[duration boundary](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/benchmarks/serve.py#L1068).

## Matched prompts without cross-run prefix hits

A fresh `cache_salt` in `--extra-body` reaches the first cache-block hash and
therefore its descendants. This permits identical seeded prompts across runs
without reusing their prior cache keys. Save the salt explicitly with
`--metadata`, because the benchmark does not automatically record extra body.
It does not purge old entries or prevent reuse among requests within one run.
Check the server's cache-hit deltas every time.

The [runnable context/batch example](context-batch.md#run-a-benchmark-case)
includes these controls. Keep warmed runtime state, build activity, request
counts, sampling settings and actual input/output lengths with every comparison.

Source: [completion request salt](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/entrypoints/openai/completion/protocol.py#L185),
[cache hash construction](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/core/kv_cache_utils.py#L543).

## The recipe's chat benchmark

`benchmark.py` is a separate, small chat-completions client. Its default remains
one warmup per exact prose, code and reasoning prompt, followed by measured
repeats and one concurrent prose/code pair. It requires streamed server usage,
the requested completion count and a final `[DONE]` event; it has no estimated
token-count fallback. First output means visible content or reasoning, not an
empty stream event. End-to-end rates include prefill and stream completion.

To compare the same longer coding prompt across DSpark configurations:

```bash
python3 benchmark.py --label dspark-long-code --tokens 512 --repeats 3 \
  --code-prompt-file code-prompt.txt --cache-mode uncached \
  --output long-code-dspark.json
```

Use the identical UTF-8 file and arguments for the control. The output preserves
the prompt, its SHA-256, actual usage, warmup observations and each request's
fresh cache salt. Salts differ even between identical warmup/repeat/concurrent
requests. Check server cache-hit deltas as live evidence; the two HTTP-boundary
regression tests prove payload construction, not runtime cache isolation.

The concurrent pair remains **prose plus code**. A long-code override therefore
measures mixed short/long requests, not two long coding requests. Speculative
counters span the entire run, including warmups and all workloads. Do not label
their aggregate acceptance as long-code acceptance. Longer synthetic code is
also not a broad coding-quality evaluation.

Source: [chat request salt](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/entrypoints/openai/chat_completion/protocol.py#L475),
[chat rendering forwards the salt](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/renderers/online_renderer.py#L440).
