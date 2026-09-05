# Critical evaluation of 97% GPU memory utilization

97% passed startup and all 19 short API checks with DSpark and CUDA graphs.
It also passed near-1M retrieval, but a concurrent short request timed out behind
the uncapped prefill. It is not established as faster or robust across workloads.
Near-1M retrieval passed at 96% (998,847 prompt tokens), followed by all 19
short API checks. The 97% request also recovered all three facts from 998,847
prompt tokens. Observed probe times were 509.7 s at 96% and 508.1 s at 97%; these
are not matched benchmarks and provide no useful evidence of a speed gain.

## What the percentage controls

In the pinned build, `request_memory` multiplies the CUDA-visible total by
`gpu_memory_utilization`. The worker profiles non-KV allocations and subtracts
them, plus the graph estimate, to determine the KV pool. This is a startup budget,
not a driver-enforced ceiling on every allocation during the process lifetime.

Sources: [requested-memory calculation](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/worker/utils.py#L433),
[KV-budget calculation](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/worker/gpu_worker.py#L464).

The runtime reports approximately 95.01 GiB CUDA-visible memory per GPU. Moving
from 96% to 97% therefore adds about **0.95 GiB / 973 MiB per GPU** to the
requested budget, assuming an unchanged profile. Do not add the two TP budgets
and treat that total as an independently usable cache on either rank.

## Evidence for and against 97%

| Observation | Implication |
|---|---|
| 1M/95% failed admission: 5.73 GiB needed, 4.98 GiB available | 95% is insufficient for this exact batch-2048 configuration |
| 1M/96% started: 5.93 GiB KV, reported 1.14x cache concurrency | 97% is unnecessary merely to start 1M |
| The 97% launch reported 6.88 GiB KV | More cache could help prefix retention or mixed request lengths |
| Reported cache concurrency at 97% is only about 1.32x | This does not establish two simultaneous full 1M requests |
| During 96% startup autotuning, the observed free memory was 657/622 MiB | An additional 973 MiB makes transient allocation failure plausible |
| During the early 96% long-input request, observed free memory was 1,535/1,500 MiB | Steady inference had more headroom than the sampled startup peak |

These free-memory values are snapshots, not complete peak measurements. Driver
reserved memory explains why reported used plus free differs from the displayed
total. Allocator-reserved memory can also be reclaimable, so these readings alone
cannot prove that 97% will fail. The subsequent startup test succeeded, with only **347/312 MiB minimum sampled
free memory** on the two GPUs. All 19 short API checks then passed. This updates
the earlier concern: 97% is possible at startup, but still has a tight sampled
margin. Near-1M inference subsequently passed, while the separate mixed-length
responsiveness probe hit a 180-second timeout. More cache did not fix scheduling.
[97% startup/API evidence](../results/dspark-1m-97-startup-api.json).

The post-warmup 96% log also recommends 5.68 GiB KV to meet its requested budget,
while reporting 5.93 GiB actually allocated. The source includes a 150 MiB buffer
in that recommendation because profiling can underestimate consumption. Do not
interpret “97%” as a promise that exactly 3% remains free at runtime.

## Feature and performance consequences

Changing only the percentage does **not** disable DSpark, reduce its five
speculative tokens, change model or KV precision, remove graphs, or turn off
reasoning, tools, structured output, streaming, or prefix caching. It exchanges
allocation headroom for additional KV capacity.

It also does not increase `max_model_len`, create more sequence slots, or promise
a faster single request. A full window includes the prompt, reasoning, tool
history, and generated output. More KV budget does not remove that token limit.

If fitting a different profile required reducing sequence slots, that would
reduce concurrent execution. Disabling DSpark would surrender its measured
short-prompt speed benefit. Removing CUDA graphs trades their memory for their
execution benefit; the current graph pool is only about 0.10 GiB, so that change
alone would not cover the 0.75 GiB admission shortfall seen at 95%.
[vLLM's memory guide](https://docs.vllm.ai/en/latest/configuration/conserving_memory/#reduce-cuda-graphs)
describes graphs as a separate speed/memory control.

None of those feature reductions is part of the proposed 97% experiment.

## How to choose the fastest practical profile

Measure time to first output/prefill, output generation rate, and concurrent
throughput separately. Prefer a lower percentage if it fits the same workload
with equal measured performance. A higher value earns a place in the recipe
when extra cache or a larger feasible prefill batch improves the target workload
without startup or inference failures.

Keep model revision, quantization, DSpark, graphs, and request workloads fixed.
Exclude competing build activity from final timing. Warm kernel compilation but
invalidate or reset cached prefixes before measuring uncached long-input prefill;
otherwise repeated prompts can produce misleading speedups. Check actual tokens,
retrieval output, speculative acceptance, and per-rank memory through startup,
prefill, decode, and concurrent requests. First-use and warm results stay separate.

The initial batch2560/threshold2304 profile
passed mixed near-1M retrieval at both 97% and 96.5%, followed by all 19 API
checks. The [source-image comparison](interactive-latency.md) now measures
batch2048 at 96% with caps1792 and512. The former preserves foreground coding
speed more closely; the latter lowers the measured 262K tool median while slowing
the coding fixture. Both offer more sampled serving headroom in those workloads.
The cap512 near-1M test also passed with 1,787/1,752 MiB minimum sampled free memory.
Cap1792 then passed with 1,099/1,064 MiB and was selected for its stronger coding
performance. Its warmed restart and all 19 post-long LAN API checks passed.
This establishes a working 1M profile at 96%; the evidence does not justify
raising its budget to 97% for the chosen workload. Startup warnings and narrow
startup headroom remain distinct from these serving observations.
There is no demonstrated capacity or speed benefit that justifies 97% for these
tested workloads. This does not rule out a different workload needing more cache.

## Startup and serving headroom are separate

A review of allocator warnings found startup pressure below the periodic
sampler's minima. These counts cover both ranks and are **allocation warning
occurrences, not failed user requests**. These four initial patched-preview
launches all reached readiness; source-image results are recorded separately.

| 1M launch | Draft post-load warnings | Later autotuning warnings |
|---|---:|---:|
| 96%, batch 2,048 | 0 | 2 |
| 97%, batch 2,048 | 0 | 4 |
| 97%, batch 2,560 | 198 | 4 |
| 96.5%, batch 2,560 | 191 | 2 |

Both batch2560 launches include allocator messages reporting only **1–2 MiB
free** during draft post-load preparation. This precedes KV profiling and pool
allocation. Their sampled minima, 111/76 MiB at 97% and 19/36 MiB at 96.5%,
caught different phases and must not be compared as true startup minima.

The 96.5% launch reduced its packed KV pool by **486.5 MiB per GPU** relative to
97%, with the same batch/cap. Post-ready sampled free memory rose from
1,395/1,360 MiB to 1,953/1,918 MiB. Other allocation and sampling variation
contributes to that difference. Lower utilization improved post-ready headroom;
it did not remove the earlier preparation pressure.
The 96.5% long retrieval subsequently passed with 998,871 input tokens. Sampled
inference free memory stayed at or above 1,011/976 MiB, versus 453/418 MiB in
the 97% mixed trial. Both use the same batch and prefill cap.

Later 128K-input/512-output C1/C2 pilots on that same 96.5% profile sampled only
587/552 MiB free. The earlier near-1M retrieval is not a worst-case memory test;
longer generated output, request mix and warmed allocations can change headroom.
[Pilot measurements](../results/context-batch-pilot.json).

The source loads and prepares weights before calculating available KV. The
utilization setting does not impose a hard allocator ceiling or shrink those
earlier conversions. Logs identify the phase but lack allocation stacks, so they
do not establish the exact failing operation, recovery mechanism, or which
autotuning tactics were skipped. Do not label these warnings a fatal startup
failure, or claim comfortable startup headroom merely because readiness passed.
Source: [model load and profiling order](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/worker/gpu_worker.py#L435).
See [recorded warning review](../results/startup-allocation-review.json).

## Batching candidates from the pinned sizing code

At 1M context with asynchronous scheduling, five speculative tokens, and two
sequence slots, the conservative admission calculation predicts:

| Maximum batched tokens | Padded KV required | Margin against a hypothetical 6.88 GiB at 97% |
|---:|---:|---:|
| 1,024 | 4.880 GiB | 2.000 GiB |
| 2,048 | 5.732 GiB | 1.148 GiB |
| 2,560 | 6.158 GiB | 0.722 GiB |
| 3,072 | 6.584 GiB | 0.296 GiB |
| 4,096 | 7.436 GiB | -0.556 GiB |

These are admission requirements, not predictions of available memory. Each
batch setting must be reprofiled because larger activation/workspace allocations
can reduce the KV budget. The in-flight bound uses two asynchronous batches;
reducing sequence slots from two to one does not change this admission term.
It would remove concurrent request execution and might only save separately
profiled buffers.

Use 2,048 as the control and 2,560 as the first larger-batch experiment. Both
have passed real near-1M requests. Consider 3,072 only after a useful measured gain and sufficient
headroom. The 1,024 setting is a potential headroom alternative, not presumed
faster. All these two-slot candidates retain DSpark, graphs, and API features.

A later, distinct candidate is a 4,096-token batch with synchronous scheduling.
The pinned configuration permits DSpark with asynchronous scheduling disabled.
With one in-flight batch instead of two, its admission charge returns to
5.732 GiB, matching the asynchronous 2,048-token control. It retains DSpark,
graphs, and two-request batching, but loses scheduling overlap; this may hurt
decode responsiveness even if larger prefill chunks help. Actual activation
memory and serving behavior remain untested. Consider it only after the initial
97%/2,560 comparison, and measure prefill and decode separately.

The [context-versus-batch guide](context-batch.md) adds smaller-window candidates
and a matched-input measurement procedure without surrendering the 801K/1M goals.
