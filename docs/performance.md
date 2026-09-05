# Performance observations

These results use the existing preview image plus all three recipe patches.
The public-source image has also passed CPU, LAN API and near-1M retrieval
acceptance; see its [separate measurements](source-image-validation.md).
The measurements below remain preview results.

## Matched short-prompt benchmark

Both runs use 64K configured context, TP=2, two sequence slots, FP8 KV,
95% memory utilization, and FULL_DECODE_ONLY **target decode** CUDA graphs. Main experts use
FlashInfer CUTLASS. DSpark uses a Marlin draft with five proposed tokens.
The source build was stopped during measurement.
The separate experimental DSpark draft-forward graph wrapper was disabled;
these results do not claim whole-pipeline graph capture.

Single-request figures are medians of two measured repeats after one warmup
per prompt, generating 256 tokens. The concurrency figures use one paired trial
per configuration.
The input lengths are only 30–41 tokens. Rates include end-to-end elapsed time;
they do not describe generation after a 64K, 801K, or 1M input.

| Workload | Graphs, DSpark off | Graphs + DSpark | Ratio |
|---|---:|---:|---:|
| prose | 95.5 tok/s | 209.4 tok/s | 2.19x |
| code | 95.6 tok/s | 190.2 tok/s | 1.99x |
| reasoning | 95.5 tok/s | 174.0 tok/s | 1.82x |
| Two requests, aggregate | 168.6 tok/s | 292.9 tok/s | 1.74x |

Warm first visible output was roughly 76–78 ms without DSpark and 82–94 ms with
DSpark in the measured single-request trials. This is a small synthetic
comparison, not a representative application benchmark or quality evaluation.

The early eager baseline measured approximately 16.3 tok/s. It is retained as
diagnostic evidence and is not the control used to estimate DSpark speedup.

See the raw [control](../results/control-graphs-benchmark.json),
[DSpark](../results/dspark-graphs-benchmark.json), and
[comparison](../results/graph-benchmark-comparison.json) files.

## Large-context learning targets

Attempt 801,000- and 1,000,000-token windows with DSpark. Record configured
window, actual prompt/completion tokens, retrieval correctness, prefill/first
output latency, generation rate, peak GPU/host memory, and any failure.
Preserve the distinction between an allocated window and successful retrieval.

The user reports reaching 801K and possibly 1M with the earlier MXFP4 build. The cached
MXFP4 revision is `7872f01b1d1fe23eabc4c98b48bffcef5a386062`, with
166,886,535,336 bytes of weights, versus 175,550,788,904 for NVIDIA NVFP4.
Both configurations have the same compression ratios. This disk-size difference
does not by itself quantify runtime or KV-cache capacity.

## Avoiding a cached-input benchmark artifact

In this pinned build, enabling the endpoint readiness check sends the first
workload prompt and then includes it in the measured run. Additional warmups
also reuse that prompt, so prefix caching can accelerate the first measured
request. The CLI defaults to no readiness check and zero warmups; the internal
Python benchmark function has a different readiness default. Keep those entry
points distinct when reproducing results.

For uncached-input comparisons, verify `/health` separately and use
`--ready-check-timeout-sec 0 --num-warmups 0`. Warm kernels in a separate
run using a different random-data seed, then measure identical seeds across
configurations. Use `--random-prefix-len 0 --random-range-ratio 0` and record the
actual input/output lengths. Use a fresh per-run `cache_salt` to repeat identical
seeded prompts on the same running server; record the salt and verify cache-hit
deltas. See [the measured-count and probe audit](benchmark-measurement.md).

These options affect benchmark measurement, not the server's prefix-cache
feature. Cached-prefix performance is useful too, but must have a separate label.
Source: [pinned benchmark readiness and warmup implementation](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/benchmarks/serve.py#L826).

## Observed mixed-request scheduling limit

With the default long-prefill threshold, a newly submitted short request queued
behind an active near-1M prefill at 97% utilization. Metrics reported one running
request, one waiting for capacity, and only about 61–68% KV-cache occupancy.
The short client subsequently timed out after its 180-second deadline. Two
sequence slots alone did not ensure responsive mixed-length serving.
[Failure evidence](../results/dspark-1m-97-concurrent-short-timeout.json).

The pinned scheduler first schedules running requests. With a zero long-prefill
threshold, the long request can consume the entire step token budget; the
waiting-request loop only runs when budget remains. A lower
`long_prefill_token_threshold` can cap the long chunk and leave token capacity
for a waiting short request. The batch2560/threshold2304 configuration subsequently passed the mixed
retrieval test with DSpark, graphs, and both request slots retained.
Source: [running-request budgeting](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/core/sched/scheduler.py#L488),
[waiting-request admission](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/core/sched/scheduler.py#L690).

For DSpark with five speculative tokens and two slots, parallel drafting reserves
eight batch slots. A 2,560-token budget therefore schedules at most 2,552 tokens.
A 2,304-token long-prefill cap leaves 248 tokens for a short request; a 2,048 cap
leaves 504. Setting a cap of 2,048 on the current 2,048 budget would not help,
because its effective scheduled budget is only 2,040. These candidate caps retain
DSpark, graphs, asynchronous scheduling, and both request slots.

The 97%/batch2560/threshold2304 candidate subsequently passed startup. Its first
short request returned correctly in 4.720 s while the long retrieval continued;
a second warmed request returned in 3.242 s, with one request still running before
and after. The long retrieval completed correctly with 998,847 input tokens
and 35 output tokens (525.519 s total probe; 523.662 s completion HTTP). All
19 follow-up API checks passed. Startup minimum sampled free memory was only
111/76 MiB; inference minima were 453/418 MiB. This is responsiveness evidence,
not a controlled speed comparison. See [mixed-trial evidence](../results/dspark-1m-97-b2560-t2304-mixed.json).

The original mixed probe included prompt preparation in its overlap timer. Its
standalone claim was too broad; separate running-request observations and fresh
container/prefix-hit logs support this live result. The corrected probe anchors
overlap at completion-call boundaries and records a unique prompt prefix.
Three regression cases first failed and then passed. It explicitly requires
separate server metrics for admission/prefill-phase claims.

For the next comparison, see [context versus batch measurements](context-batch.md).

The same batch2560/threshold2304 settings also passed at **96.5%** with
998,871 input tokens and 35 output tokens. The long probe took 525.619 s
(523.813 s completion HTTP). Short replies returned in 4.199 s and 2.252 s;
the latter had one running request before and after. All 19 follow-up API checks
passed. Sampled inference free memory was at least 1,011/976 MiB, compared with
453/418 MiB at 97%. These are not matched timing runs; first-use compilation,
concurrent build activity, and a fresh unique prompt prefix limit the comparison.
[96.5% mixed evidence](../results/dspark-1m-965-b2560-t2304-mixed.json).

## Matched-input pilot: concurrency at 1M

These **pilot observations** use the patched preview while a source build runs.
They validate the harness and help select candidates; final-image controlled
repeats are still required. Both cases use the same seed101, two 131,072-token
inputs and 512-token outputs, fresh per-run cache salts, a 1M ceiling, 96.5%
memory budget, batch2560, prefill cap2304, DSpark five and decode graphs.

| Client concurrency | Aggregate output rate, including prefill | Individual TTFTs | Median per-request TPOT | Draft acceptance fraction |
|---:|---:|---|---:|---:|
| 1 | 20.531 tok/s | 20.403 s, 20.851 s | 8.436 ms | 20.51% |
| 2 | 21.312 tok/s | 22.779 s, 42.571 s | 29.752 ms | 19.69% |

The C2 run produced about 3.8% more aggregate output per second, with substantially
worse average generation delay per token. Two requests per case do not establish
a stable speed difference or tail-latency guarantee. Server counters confirmed
262,144 actual input and 1,024 output tokens, zero cache hits and zero preemptions
for each run. C2 request-time sums overlap, so do not interpret their sum as GPU
compute time. Random inputs do not represent coding quality or representative
DSpark acceptance.

Both pilots sampled minimum free memory of 587/552 MiB, lower than the earlier
near-1M retrieval probe. Serving headroom depends on workload and warmed runtime
allocations. The 96.5% setting alone does not guarantee a gigabyte of free memory.
See [pilot evidence](../results/context-batch-pilot.json) and
[measurement semantics](benchmark-measurement.md).

The context-only retry at **524,288 tokens**, with the same 96.5%/batch2560/cap2304,
also completed both salted cases. C1 aggregate output was 20.054 tok/s with
TTFTs 21.171/21.453 s and median TPOT 8.256 ms. C2 was 21.169 tok/s with
TTFTs 23.158/43.146 s and median TPOT 29.349 ms. Actual counts again matched
262,144 input / 1,024 output, with no cache hits or preemptions. These small,
build-contended differences do not establish a benefit from the lower ceiling
alone. Its startup reported 6.88 GiB KV rather than the 1M profile's 6.30 GiB;
minimum sampled inference free memory was 739/704 MiB. A larger-batch trial
followed to check whether the reduced admission requirement bought useful speed.

The **524,288/batch4096/cap3840** profile started at 96.5%, reporting 6.60 GiB
KV and 1.31x maximum-length cache concurrency. Both benchmark cases completed
with matching actual counts, zero prefix hits and zero preemptions. Initial C1
output throughput was 18.920 tok/s, with uneven TTFTs of 25.394/20.528 s.
A separately saved C1 repeat reached 21.084 tok/s and 19.919/20.414 s TTFTs.
C2 reached 21.966 tok/s with TTFTs 21.795/41.139 s and median TPOT 28.857 ms.
Minimum sampled inference free memory was 407/372 MiB.

The first C1 pair was run after a C2 warmup; that does not prove every C1 shape
was warm. The server log did not identify compilation as the reason for the
uneven times. Preserve the first pair and repeat rather than selecting only the
faster result. In final testing, warm both C1 and C2 explicitly. These small
differences, concurrent build activity and within-profile variation do not yet
justify a smaller context ceiling or establish an optimal batch size.

The final preview pilot used **1M/batch2048/cap1792**, also at 96.5%, with
separate C1 and C2 warmups. C1 output throughput was 18.804 tok/s, TTFTs
21.904/22.154 s and median TPOT 10.173 ms; C2 was 19.996 tok/s, TTFTs
45.116/25.191 s and median TPOT 28.973 ms. Actual counts matched, prefix hits
and preemptions were zero, and minimum sampled free memory was 795/760 MiB.
Startup reported 6.41 GiB KV and 1,226,192 tokens of cache capacity. Its C1
draft acceptance was 13.71%, versus 19.57% at C2; variable acceptance is another
reason to avoid attributing these small-run differences solely to batch size.
The source build was still active, so controlled final-image measurements remain
the decision gate. All nine measured pilot cases are preserved in the evidence.
