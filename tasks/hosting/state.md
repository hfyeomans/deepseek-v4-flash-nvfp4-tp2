# Hosting state

Updated September 5, 2026.

## Latest measurement and repository follow-up

The [exact-primary controls](../../docs/primary-control-screen.md) and
[diagnostic profiles](../../docs/component-profiling.md) are complete. The
original 1M / 96% primary image/command was restored and passed 19 API checks;
adaptive verification remains disabled. Research and candidate work now belong
in a [separate private repository](../../docs/repository-boundaries.md). The
recipe retains acceleration findings, clients and all fixed-mode results.
No serving profile changed during the split.

## Verified

- Local Git repository: branch `recipe/validated-tp2`.
- Two RTX PRO 6000 Blackwell Max-Q GPUs, 97,887 MiB each; TP=2.
- Driver 610.57.04, Linux 7.0.0-30-generic, 246 GiB host RAM. GPU topology is
  NODE within one NUMA node, without NVLink.
- NVIDIA snapshot `f1caa71142bd0be02f728c79f75042ac1e461579`; all 48 shard
  sizes match Hub metadata, totaling 175,550,788,904 bytes.
- Original image `vllm-sm120-dsv4:preview-20260804` and original MXFP4 launcher
  are unchanged. Original image ID:
  `sha256:a8434606207901f4596c6de6bac6bc246afef620dac3c8cde6f9555ab0075d26`.
- Retained Docker Buildx history establishes public source revision, build target,
  arguments, and CUDA base digests: see `results/original-build-provenance.json`.
  All 2,175 installed Python files also present in the source checkout matched.
  Generated/bundled files and compiled binaries were not compared.
- Rebuilt the incompatible FlashInfer cached kernel against installed TVM FFI.
  Removing the precompiled cache, supplying the existing NVRTC include directory,
  and adding the missing development library link resolved baseline startup.
- Patch 0001 passes five CPU methods for mixed main-NVFP4/draft-MXFP4 dispatch;
  patch 0002 passes four methods against the checkpoint's official reasoning encoder.
- Patched baseline without DSpark passed chat, multi-turn recall, low/high/max
  reasoning, streamed reasoning/content/tools, automatic/required/named tools
  with round trips, two-tool association, strict JSON schema, concurrency two,
  prefix reuse, cancellation recovery, and 24,417-token prompt retrieval.
- One JSON-object probe used incorrect keys; the explicit-key retest passed.
  Both attempts are preserved. JSON-object mode guarantees syntax, not a schema.
- Fixed-length baseline benchmark: approximately 16.3 output tokens/second for
  one request and 32.3 aggregate for two. These are end-to-end rates from small
  synthetic workloads, with two measured repeats per workload.

## DSpark results

- Main NVFP4 experts use FlashInfer CUTLASS; the MXFP4 draft uses Marlin through
  the existing speculative `moe_backend` option.
- The inherited CUTLASS MXFP4/MXFP8 draft backend failed in its SM120 grouped
  GEMM1 profiler. Synchronous CUDA diagnostics localized the fault; Marlin
  resolved startup without changing the main model's backend.
- All 20 API checks passed with DSpark at 32K, including reasoning-through-tools
  and retrieval from a 24,417-token prompt. See `results/dspark-marlin-features.json`.
- A live metrics snapshot showed 37 draft rounds, 181 proposed draft tokens,
  and 133 accepted tokens. This establishes active speculation, not a general
  acceptance rate or performance guarantee.
- Patch 0003 checks individual expert tensors, fused companion source tensors,
  and all parameter bindings. Four CPU test methods pass, including deliberate
  missing weight/scale cases. GPU loading verified all 4,608 expert source tensors,
  99 non-expert sources, and 99 parameter bindings on both ranks.

## Large-context learning goals

The user explicitly wants attempted **801K and 1M context windows**, with
successful retrieval or exact failures and resource/performance tradeoffs.
The 64K result is an intermediate milestone.

- 64K with graphs passed all 20 feature checks and 61,287-token retrieval.
- Matched short-prompt graphs control measured ~95.5 tok/s, versus 174–209 tok/s
  with DSpark (1.82–2.19x); concurrency-two aggregate improved 168.6 to 292.9.
  These rates are not large-context throughput measurements.
- The 801,000-token DSpark configuration started successfully at 95% GPU memory
  utilization, with 5.22 GiB available KV space and reported 928,987-token
  capacity. Retrieval passed with 799,847 prompt tokens, all three facts correct,
  followed by successful short-chat recovery. Total probe 343.6 s, completion
  request 342.2 s; first-use compilation and a concurrent build affect timing.
- The 1,000,000-token startup failed at 95%: needed 5.73 GiB KV, available
  4.98 GiB; estimated maximum 813,056. The 96% retry passed startup and
  retrieval from 998,847 actual prompt tokens, then all 19 short API checks.
  The long probe took 509.7 s, completion HTTP 507.9 s, server prefill 505.4 s
  and decode 0.425 s for 35 output tokens. Build/JIT confounds apply.
  See `results/dspark-1m-95-startup-failure.json`.
- The public-source build completed using optional HTTPS/IPv4 package setup and
  host networking. Final image manifest is
  `sha256:1f0776d3ac4a990186899d122ebee81e5ad0bcdf1dbb95ebccb30d5f94c6908e`.
  Its dependencies were inspected and all 13 CPU regression methods passed.
  GPU startup with a fresh FlashInfer cache passed after 519.5 seconds of
  observation. All 19 LAN API checks and 998,868-token retrieval passed, followed
  by chat/tool recovery. See docs/source-image-validation.md for the evidence.

- The 97%/1M profile passed startup and all 19 short API checks. Its KV pool
  is 6.88 GiB, reported concurrency 1.32x. Minimum sampled startup free memory
  was 347/312 MiB per GPU. Near-1M retrieval also passed (998,847 tokens;
  508.1 s total probe), with build/JIT/mixed-request timing limitations.
- A short request submitted during that long prefill queued despite the
  second sequence slot and spare KV capacity; it hit the 180-second client
  timeout. The running long request consumes
  the step token budget before waiting requests are considered. The subsequent
  explicit long-prefill threshold tests below resolve admission and measure
  the throughput/responsiveness tradeoff.

- The 97%/batch2560/threshold2304 profile started with 6.77–6.78 GiB KV.
  Its first short request finished in 4.720 s while the long retrieval continued;
  a warmed short request finished in 3.242 s with one running request still
  present before/after. The near-1M retrieval passed at 998,847 input tokens
  and 35 output tokens: 525.519 s probe, 523.662 s completion HTTP. All 19
  follow-up API checks passed. Startup minimum free memory was 111/76 MiB;
  inference minima were 453/418 MiB. The 96.5% retry also passed mixed retrieval
  with 998,871 input/35 output tokens (525.619 s probe, 523.813 s HTTP), short
  replies in 4.199/2.252 s, and all 19 follow-up API checks. Its sampled inference
  minima were 1,011/976 MiB. Neither timing run is a controlled speed comparison.
- Startup log review found early allocation warnings during draft preparation
  in both batch2560 launches, with allocator-reported free memory as low as
  1–2 MiB. Both reached readiness. Lower utilization shrank the later KV pool
  but did not eliminate that preparation pressure; see results/startup-allocation-review.json.
- The standalone mixed probe now measures completion-call boundaries and uses
  a unique prompt prefix. Three regression cases failed before the correction
  and pass afterward. Server admission/prefill evidence remains separate.
- Added docs/context-batch.md with source-derived admission estimates and a
  bounded matched-input experiment. Smaller windows remain alternatives, while
  801K/1M capacity and the learning objective are preserved.
- User selected interactive coding/tools with occasional very long inputs as
  the default workload. Interactive latency and feature preservation take
  precedence over maximum bulk throughput when choosing a default.

## DSpark capability and measurement follow-up

- Source audit confirms the active fixed K=5 proposer uses sequential Markov
  correction but never calls the loaded confidence head. Confidence-scheduled
  adaptive verification is explicitly out of scope in this preview. Memory and
  context tuning did not remove it. Current upstream documentation describes a
  later implementation; compatibility with this recipe is untested.
- Built-in mixed benchmark probes share the main client's connection pool.
  At concurrency one, client-side waiting contaminates probe latency. Reject
  the pilot's 23.809-second probe median as server responsiveness evidence.
  Use the independent probe and server activity observations.
- Live repeated seed101 runs with different cache salts confirmed zero cache
  hits and actual totals of 262,144 input / 1,024 output tokens for each C1/C2
  pilot. On 1M/96.5%/batch2560/cap2304, aggregate output rates were 20.531 and
  21.312 tok/s; median per-request TPOT was 8.436 and 29.752 ms. Each has only
  two requests and a concurrent source build, so these are pilot observations.
  Minimum sampled free memory was 587/552 MiB during both pilots, lower than
  the earlier retrieval-only workload. Memory headroom is workload-dependent.
- The 524,288/96.5%/batch2560/cap2304 context-only comparison completed C1/C2
  with identical seed101 and fresh salts. Actual counts matched and cache hits
  and preemptions stayed zero. Output rates were 20.054/21.169 tok/s and median
  TPOT 8.256/29.349 ms, similar to 1M. Its reported KV pool was 6.88 GiB;
  sampled inference free memory was 739/704 MiB. Batch4096/cap3840 also started
  (6.60 GiB KV), passed C1/C2 counts/cache/preemption checks, and sampled only
  407/372 MiB free. Initial C1 was 18.920 tok/s; an uneven first-token pair led
  to a preserved repeat at 21.084 tok/s. C2 was 21.966 tok/s. No final ranking
  follows from these small, build-contended differences. The 1M/96.5%/batch2048/
  cap1792 profile then passed both warmed cases: 18.804/19.996 tok/s C1/C2,
  zero prefix hits/preemptions and 795/760 MiB minimum sampled free memory.
  Original image/source/launcher remain preserved. The source-built candidate
  passed at 1M/96.5%/batch2560/cap2304. Its matched DSpark-off control completed;
  the DSpark candidate was restored and all 19 LAN API checks passed again.
  It is now saved and stopped while the source-built interactive variants run.
  See results/context-batch-pilot.json.

## Selected profile and remaining phases

Source-image GPU acceptance, matched controls, the bounded interactive comparison
and default selection are complete. The selected coding service is running at
1M / 96% / batch2,048 / cap1,792, retaining DSpark K5/Markov, target decode graphs,
FP8 KV and the tested API features. Generic launcher defaults remain 64K/95%;
the selected profile uses explicit documented overrides. The repository has
a clean private recipe snapshot with checkpoint tag `recipe-1m-k5`; see
[publication state](../publication/state.md). No public release has been made.

The [interactive latency comparison](../../docs/interactive-latency.md) completed
three measured 262K trials per profile, plus retained warmups. The 96%/batch2048/
cap512 profile measured a 2.186-second tool median and 61.564-second long HTTP
median, versus 6.808/54.491 seconds at cap1792. Output/cache differences are
explicit. Both lower-memory variants passed all 19 API checks and near-1M
retrieval. Cap512 retrieved 998,866 tokens in 539.998 seconds over HTTP; cap1792
retrieved 998,869 in 513.759 seconds. Their tool checks at delay240 passed in
18.113 and 32.035 seconds. Sampled near-1M free memory was 1,787/1,752 and
1,099/1,064 MiB, respectively. Both had zero prefix hits/preemptions. These
single trials do not establish latency guarantees. Cap1792 passed a 65.268-second
warmed restart and all 19 LAN API checks after its long test.

The frozen 48K code fixture completed in 8.906 seconds median at cap1792 versus
12.205 seconds at cap512. This 37% cost supports selecting cap1792 for coding
while retaining cap512 as a concurrent-tools alternative. The selected profile
is roughly 7% slower on this fixture than the initial batch2560/cap2304 profile,
with more sampled serving headroom. Short paired medians were similar at
269.88 and 260.03 tok/s; all trials remain, not just their peaks. Exact fixture
bytes and reproduction instructions are included in benchmarks/prompts/.

Source-image testing found a 2.095-second tiny reply but a 37.941-second automatic
tool round trip during near-1M prefill. Both passed; server snapshots show prompt
admission, so functional overlap is not sufficient evidence of interactive
tool responsiveness. The full mixed run took 513.165 seconds, included four API
calls, and sampled only 507/472 MiB free. That original profile is saved as a
control; the lower-memory comparison above supplied the selected coding profile.
Short paired throughput was 203.4, then 302.9 and
263.3 tok/s; all trials are retained. The frozen 48,345-token coding fixture
measured 61.50 tok/s end to end versus 43.49 without DSpark, with zero prefix hits
in both configurations. Across nine short requests per workload, DSpark delivered
about 2x throughput; across all three paired trials its median aggregate was
263.31 versus 163.96 tok/s (1.61x). Reported KV availability fell from 11.84 to
6.30 GiB per GPU. See docs/source-image-validation.md and the unrounded results.

The follow-on adaptive-verification research and implementation plan moved to
the [separate private project](../../docs/repository-boundaries.md). Its ROI
remains unmeasured; the recipe continues to report fixed-K5 acceleration.

The user also requested a [before/after performance scorecard](../performance-scorecard/plan.md)
showing the numerical optimization progression, including the 292.9 tok/s
two-request aggregate. Historical and source-image comparisons are documented in
docs/performance-scorecard.md, including the selected profile and its costs.

## User-reported MXFP4 comparison

The user reports that the earlier MXFP4 build reached 801K and possibly 1M
context on this machine. Treat this as a user-observed reference point;
that run has not been reproduced in this investigation. Compare actual NVFP4
weight/draft/KV allocations and launch settings before explaining any gap.
