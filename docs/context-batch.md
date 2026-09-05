# Choosing context and batch size from measurements

We wanted to find out whether giving up context would buy enough speed or
concurrency to be worthwhile. This plan compares smaller windows alongside
the original 801,000- and 1,000,000-token goals. Failed attempts stay in the
results because they help explain the limits.

For everyday coding and tools, I care about the wait before output and whether
a tool can respond while a large input is processing. Aggregate throughput
alone won't choose that profile. A 1M window with smaller prefill chunks may
be the better tradeoff.

## Three different settings

| Setting | Meaning | What raising it can cost |
|---|---|---|
| `max_model_len` | Maximum prompt plus generated tokens in one conversation | More history must fit, and some buffers grow with the limit |
| `max_num_batched_tokens` | Token budget per scheduling step, shared by active requests | Larger temporary and cache working buffers; longer steps can delay other requests |
| `max_num_seqs` | Maximum active request slots | More simultaneous histories and decode work |

A 4,096-token batch is a per-step token budget, not 4,096 users. Keep two
request slots and measure one versus two active requests separately.

A shorter window need not lower idle GPU memory: vLLM still fills the KV pool
from its budget. It reduces maximum-request admission needs and may shrink
other buffers, potentially allowing a larger batch. Reprofile and serve a real
request for each setting.

## What the pinned source predicts

These are **conservative KV admission requirements per GPU** for the pinned
model/source, K5 DSpark, asynchronous scheduling, FP8 KV, block 256 and two slots.
Weights and other allocations are additional. The table doesn't predict free
memory or speed.

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

Context charges for history; batch charges cover compression and sliding-window
workspaces for two in-flight asynchronous batches. The stride is padded for
admission; actual packed allocation uses another stride. This model-specific
formula can't be used as generic KV bytes/token, and TP=2 pools aren't
additive. See [memory details](context-memory.md) and
[admission code](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/core/kv_cache_utils.py).

Dropping from 1M to 801K saves **0.797 GiB** in admission. Doubling batch 2,048
to 4,096 costs **1.704 GiB**. The savings don't cover the increase. At 524,288,
batch 4,096 is more plausible, but we still have to measure its speed.

## Bounded test matrix

This initial candidate matrix requires startup profiling. The later pilot
results appear below; inclusion here isn't a recommendation.

| Context | Batch | Long-prefill cap | Purpose |
|---|---:|---:|---|
| 1,000,000 | 2,048 | 1,792 | Large-window control |
| 1,000,000 | 2,560 | 2,304 | Larger chunk while preserving 1M |
| 524,288 | 2,560 | 2,304 | Isolate the effect of the context ceiling |
| 524,288 | 4,096 | 3,840 | Spend lower admission requirements on a larger chunk |
| 262,144 | 4,096 | 3,840 | Isolate a further context reduction |
| 262,144 | 6,144 | 5,888 | Explore a larger batch if its startup profile fits |

K5 with two slots reserves eight tokens from the nominal batch. These caps
leave 248 scheduled tokens for other work, even when the long request is
alone. Record the cap with timings. Two long requests can still fill both
slots, so this doesn't guarantee priority for short work.

Match memory utilization where possible. Label any changed budget or startup
failure so a comparison doesn't imply that only batch size changed.

## Workloads and metrics

Use **131,072 input tokens and 512 output tokens** across all rows so every
profile processes the same length. Warm with a different prompt, separate
prefixes and control seed, image, clocks, speculation and load. Save all
repeats alongside medians.

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

Keep individual probe times. Two samples can't tell you reliable p50/p95
latency. For prefill timing, isolate the request or measure its work separately;
global counters in a mixed test include everything.

TTFT is how long you wait for output, including queueing and input processing.
Decode time/token describes generation afterward. Aggregate output rate uses
the whole run, so a long prompt can pull that rate down even when generation
is fast. Report both to show where the time went.

DSpark can stream several tokens per event. Event gaps describe display cadence;
use actual completion-token counts and the relevant elapsed time for throughput.

Test near-limit retrieval separately, recording actual input tokens and reserving
reasoning/output space. A configured 1M window, successful 998K retrieval, fast
128K processing and broad long-context accuracy each need their own evidence.

## What we give up

A shorter window rejects longer conversations and leaves less output room.
Fitting requests keep the same model precision, DSpark, graphs, reasoning, tools
and structured output. Recheck those features on the chosen profile.

A larger batch may speed prefill but use more memory and delay other work
with longer steps. Measure both effects before picking everyday and bulk-input
profiles.

Current observations and their limitations are in [performance.md](performance.md).

## Run a benchmark case

Launch a candidate, check `/health` and use its bundled benchmark. The flags
below match the pinned CLI. Random completions exercise memory and scheduling;
include coding fixtures, tool roundtrips and API checks when choosing a default.

```bash
source scripts/config.sh
TOKENIZER_PATH="/root/.cache/huggingface/hub/models--nvidia--DeepSeek-V4-Flash-0731-NVFP4/snapshots/$REVISION"
LABEL=1m-b2560-c1-seed101
BENCH_SEED=101
CACHE_SALT=$(python3 -c 'import uuid; print(uuid.uuid4())')
CONCURRENCY=1
PROMPT_COUNT=2

docker exec "$CONTAINER_NAME" vllm bench serve \
  --model "$SERVED_MODEL_NAME" --tokenizer "$TOKENIZER_PATH" \
  --tokenizer-mode deepseek_v4 --backend vllm \
  --base-url "http://127.0.0.1:$SERVER_PORT" --endpoint /v1/completions \
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

Warm C1 and C2 separately with another seed and distinct labels. For measured
repeats, use the same seed list, such as 101 and 102, across configurations.
Assign a fresh `CACHE_SALT` each invocation: it separates keys without changing
prompt tokens, but doesn't purge old entries or stop reuse within a run.
Record it explicitly because `--extra-body` isn't saved. Check actual usage
against server counters and verify hit deltas. Set `CONCURRENCY` to 2 for the
paired case, with a new label/salt and matched seed.

Use [the independent mixed probe](../mixed_probe.py) with server activity
observations. The built-in probes share a pool capped at `max_concurrency`;
with one connection, they wait behind the long response in the client. Their
serial loop also pauses after each response. Those timings can't establish
server responsiveness. See [the audit](benchmark-measurement.md).

Save `/metrics` before/after each run, sample GPU memory and retain exact
server arguments. Benchmark JSON supplies request timings; it needs resource
and server evidence to establish memory use or prefill activity.
