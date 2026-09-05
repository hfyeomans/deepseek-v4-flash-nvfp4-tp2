# Choosing context and batch size from measurements

The learning question is: **how much prompt-processing speed or concurrency do
we gain by accepting a shorter maximum conversation?** The 801,000- and
1,000,000-token windows remain attempted goals. Smaller windows are useful
alternatives to measure, and a failed configuration is worth recording.

The default workload is **interactive coding and tools, with occasional very
long inputs**. Prioritize first-output delay, generation and tool round trips,
including short requests arriving during a long prefill. Maximum aggregate
throughput alone does not decide the default. Retaining 1M with a modest prefill
chunk may be more useful than a smaller window with a larger batch; measure it.

## Three different settings

| Setting | Meaning | What raising it can cost |
|---|---|---|
| `max_model_len` | Maximum prompt plus generated tokens in one conversation | More history must fit, and some buffers grow with the limit |
| `max_num_batched_tokens` | Token budget per scheduling step, shared by active requests | Larger temporary and cache working buffers; longer steps can delay other requests |
| `max_num_seqs` | Maximum active request slots | More simultaneous histories and decode work |

Batch tokens and simultaneous requests are different knobs. A 4,096-token batch
does not mean 4,096 users. In these first comparisons, keep two request slots and
measure one versus two active requests separately.

Lowering the configured window does not necessarily lower idle GPU memory:
vLLM allocates its KV pool from the remaining utilization budget. It lowers the
memory needed to admit a maximum-length request, and may reduce non-KV buffers.
That can make a larger batch feasible. Each configuration still needs its own
startup profile and a real request.

## What the pinned source predicts

These are **per-GPU conservative KV admission requirements**, not total GPU
memory, observed free memory, or speed predictions. They apply to this pinned
model/source with DSpark five, asynchronous scheduling, FP8 KV, block size 256,
and two request slots. Model weights and other allocations are additional.

| Total context limit | Batch 2,048 | Batch 2,560 | Batch 4,096 | Batch 6,144 | Batch 8,192 |
|---|---:|---:|---:|---:|---:|
| 262,144 | 2.779 GiB | 3.205 GiB | 4.483 GiB | 6.187 GiB | 7.891 GiB |
| 524,288 | 3.828 GiB | 4.254 GiB | 5.532 GiB | 7.236 GiB | 8.940 GiB |
| 801,000 | 4.935 GiB | 5.361 GiB | 6.639 GiB | 8.343 GiB | 10.047 GiB |
| 1,000,000 | 5.732 GiB | 6.158 GiB | 7.436 GiB | 9.140 GiB | 10.844 GiB |

For these aligned batch sizes, the model-specific calculation simplifies to:

```text
required_bytes = (ceil(context_limit / 256) + 13 * batch_tokens / 16 + 26)
                 * 1,099,584
```

The context term represents history. The batch term includes compression and
sliding-window working space for two in-flight asynchronous batches. The stride
is the conservative padded group size used in startup admission; actual packed
pool allocation uses a different stride. This is not a generic transformer
KV-bytes-per-token formula, and TP=2 does not make two independent pools additive.
See [the full memory analysis](context-memory.md) and
[pinned admission implementation](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/core/kv_cache_utils.py).

For example, reducing 1M to 801K saves about **0.797 GiB** of admission space,
while increasing batch 2,048 to 4,096 costs **1.704 GiB**. That small context
reduction alone does not buy a doubled batch. Reducing to 524,288 makes batch
4,096 a more plausible candidate. Neither statement predicts throughput.

## Bounded test matrix

Start with the following candidates, subject to startup profiling. These rows
are a test plan, not recommended or benchmarked configurations.

| Context | Batch | Long-prefill cap | Purpose |
|---|---:|---:|---|
| 1,000,000 | 2,048 | 1,792 | Large-window control |
| 1,000,000 | 2,560 | 2,304 | Larger chunk while preserving 1M |
| 524,288 | 2,560 | 2,304 | Isolate the effect of the context ceiling |
| 524,288 | 4,096 | 3,840 | Spend lower admission requirements on a larger chunk |
| 262,144 | 4,096 | 3,840 | Isolate a further context reduction |
| 262,144 | 6,144 | 5,888 | Explore a larger batch if its startup profile fits |

With DSpark five and two slots, eight tokens are reserved from the nominal
batch. These caps leave 248 scheduled tokens for other work. The cap also
applies when the long request is alone, so record it as part of the performance
configuration. Two long requests can still occupy both slots; this is not a
general priority guarantee.

Use a common memory utilization for matched rows where feasible. If a row
requires another utilization or cannot start, label that change or failure;
do not silently compare it as if only the batch changed.

## Workloads and metrics

First use the same **131,072-token input and 512-token output** across all rows.
This fits each proposed window and avoids confusing a shorter input with a
faster configuration. Warm kernels with a different prompt, use fresh/reset
prefixes, and keep seeds, image, clocks, speculation, and load controlled.
Repeat measurements; save individual results as well as medians.

| Measurement | Decision it supports |
|---|---|
| Prefill time and input tokens/second | Does a larger chunk process the same input faster? |
| Time to first token (TTFT) | How long does a user wait before output starts? |
| Decode time per token and output tokens/second | Does prefill tuning hurt generation? |
| One-request and two-request aggregate throughput | Does serving more requests increase useful work? |
| Short-request latency during long prefill | Does throughput come at an unacceptable interactive delay? |
| Sampled minimum free memory, errors and preemptions | Is the apparent gain stable and repeatable? |
| Proposed/accepted draft tokens | Is DSpark still active, and how does acceptance change? |
| Retrieval, reasoning, tools and structured output checks | Do the tested features still work? |

For short probes, report individual latencies and enough repeated observations
before treating p50/p95 as stable. Two observations cannot establish a meaningful
tail-latency guarantee. Prefill metrics require isolated requests or explicit
per-request attribution; aggregate counters during mixed tests include all work.

TTFT includes queueing and input processing, so it describes the user's initial
wait. Decode time per output token describes generation after output begins.
The benchmark's aggregate output throughput divides all output tokens by the
whole run duration, including input processing. A long input can therefore have
low end-to-end output throughput while still decoding quickly after its first
token. Keep those rates separate.

With DSpark, one streamed event can carry several tokens. Inter-event gaps
describe display cadence; counting streamed chunks or taking the reciprocal of
their average gap does not establish token throughput. Use actual completion
token counts and the appropriate elapsed interval.

Then run near-limit retrieval separately. Record actual prompt tokens and leave
room for reasoning and output. A configured 1M window, a successful 998K-input
retrieval, a fast 128K workload, and broad long-context accuracy are four
different claims.

## What we give up

A shorter window rejects conversations that no longer fit and leaves less room
for long generated answers. It does not inherently disable DSpark, CUDA graphs,
reasoning, tools, structured output, or change model precision on fitting
requests. Those features still need acceptance checks on the chosen profile.

A larger batch may improve prefill throughput while increasing temporary memory
or the duration of each scheduling step. The outcome can favor an interactive
profile and a separate bulk/large-document profile. Choose them from measured
tradeoffs, rather than declaring the largest batch universally fastest.

Current observations and their limitations are in [performance.md](performance.md).

## Run a benchmark case

After launching one candidate and checking `/health`, use the benchmark bundled
in that same image. These flags were checked against the pinned CLI. The example
uses a raw-completion synthetic workload; the API feature suite separately
tests chat, reasoning, tools and structured output.
Random tokens exercise memory and scheduling but do not represent coding
accuracy or natural code generation. Include the fixed coding prompts and tool
round trips when choosing the interactive default.

```bash
CONTAINER_NAME=dsv4-nvfp4
MODEL_ALIAS=dsv4-nvfp4
REVISION=f1caa71142bd0be02f728c79f75042ac1e461579
TOKENIZER_PATH="/root/.cache/huggingface/hub/models--nvidia--DeepSeek-V4-Flash-0731-NVFP4/snapshots/$REVISION"
LABEL=1m-b2560-c1-seed101
BENCH_SEED=101
CACHE_SALT=$(python3 -c 'import uuid; print(uuid.uuid4())')
CONCURRENCY=1
PROMPT_COUNT=2

docker exec "$CONTAINER_NAME" vllm bench serve \
  --model "$MODEL_ALIAS" --tokenizer "$TOKENIZER_PATH" \
  --tokenizer-mode deepseek_v4 --backend vllm \
  --base-url http://127.0.0.1:8000 --endpoint /v1/completions \
  --dataset-name random --random-input-len 131072 --random-output-len 512 \
  --random-prefix-len 0 --random-range-ratio 0 \
  --num-prompts "$PROMPT_COUNT" --max-concurrency "$CONCURRENCY" \
  --temperature 0 --ignore-eos --seed "$BENCH_SEED" \
  --extra-body "{\"cache_salt\":\"$CACHE_SALT\"}" \
  --metadata "cache_salt=$CACHE_SALT" "dataset_seed=$BENCH_SEED" \
  --ready-check-timeout-sec 0 --num-warmups 0 \
  --percentile-metrics ttft,tpot,itl,e2el --metric-percentiles 50,95 \
  --save-result --save-detailed --label "$LABEL" \
  --result-dir /tmp --result-filename "$LABEL.json"

mkdir -p results/raw
docker cp "$CONTAINER_NAME:/tmp/$LABEL.json" "results/raw/$LABEL.json"
```

Before measurement, run separate C1 and C2 warmup cases with a different seed
and labels; warming only one concurrency does not establish warm kernels for
the other execution shapes.
For repeats, reuse the same seed list (for example 101, 102) across configurations
and concurrency levels, with a fresh `CACHE_SALT` for each invocation. The salt
separates prefix-cache keys without changing the prompt tokens. It does not
purge older entries or prevent shared-prefix reuse within one invocation, so
verify cache-hit deltas. Record the salt explicitly: the result does not save
`--extra-body` automatically. Read saved actual token counts and corroborate
them with server counters; requested dataset lengths alone are insufficient.
Increase `CONCURRENCY` to 2 with a new label and salt, keeping the seed matched.

For mixed-load responsiveness, use [the independent probe](../mixed_probe.py)
and confirm server activity around its short request. **Do not use this pinned
benchmark's built-in probes as server responsiveness evidence at bounded client
concurrency.** They bypass its semaphore but share a connection pool capped at
`max_concurrency`. At one connection, a probe waits in the client for the long
response to finish. Its reported latency includes that wait. The probe loop is
also serial, with a pause after each response; its rate flag does not establish
an independent arrival rate. See [the measurement audit](benchmark-measurement.md).

Save `/metrics` before and after each run for prefill and DSpark counters, and
sample GPU memory during the run. Preserve the exact server arguments next to
each result. The benchmark JSON supplies request timings; it does not by itself
establish peak memory, prefill-phase attribution, or application correctness.
