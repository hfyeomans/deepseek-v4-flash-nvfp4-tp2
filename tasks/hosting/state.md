# Hosting state

Updated September 5, 2026.

## Latest measurement and repository follow-up

The [primary controls](../../docs/primary-control-screen.md) and
[component profiles](../../docs/component-profiling.md) are complete. The restored
1M/96% primary passed 19 API checks. Adaptive work moved to the
[private research repo](../../docs/repository-boundaries.md); this repo keeps
fixed-K5 deployment code and findings. The split changed no serving settings.

## Verified

- Recorded branch: `recipe/validated-tp2`.
- Two RTX PRO 6000 Blackwell Max-Q GPUs, 97,887 MiB each, TP=2.
- Driver 610.57.04, Linux 7.0.0-30-generic, 246 GiB RAM; NODE topology within one
  NUMA node, no NVLink.
- Snapshot `f1caa71142bd0be02f728c79f75042ac1e461579`: all 48 shard sizes match
  Hub metadata, totaling 175,550,788,904 bytes.
- Original `vllm-sm120-dsv4:preview-20260804`, source and MXFP4 launcher preserved.
  Image `sha256:a8434606207901f4596c6de6bac6bc246afef620dac3c8cde6f9555ab0075d26`.
- Buildx pins source, target, arguments and base digests in
  `results/original-build-provenance.json`. All 2,175 shared Python files matched;
  generated/bundled files and binaries were excluded.
- Rebuilding FlashInfer with installed TVM FFI/NVRTC resolved startup.
- Patch 0001 passed five dispatch methods; patch 0002 passed four encoder methods.
- The baseline passed reasoning, tools, streaming, schemas, two-request
  concurrency, prefix reuse, cancellation recovery and 24,417-token retrieval.
- JSON-object mode used wrong keys once; the explicit-key retest passed. Both
  remain recorded because this mode guarantees syntax, not schema.
- Eager rates were about 16.3 tok/s C1 and 32.3 aggregate, from small synthetic
  workloads with two repeats per single workload.

## DSpark results

- Target NVFP4 uses FlashInfer CUTLASS; draft MXFP4 uses Marlin via `moe_backend`.
- Synchronous diagnostics located the inherited CUTLASS draft failure in SM120
  GEMM1 profiling. Marlin resolved startup without changing target backend.
- All 20 checks passed at 32K, including reasoning/tools and 24,417-token retrieval:
  `results/dspark-marlin-features.json`.
- One snapshot recorded 37 rounds, 181 proposals and 133 accepted tokens. It proves
  activity, not a representative acceptance rate.
- Patch 0003 passed four CPU methods, including missing weight/scale cases. Both
  ranks verified 4,608 expert sources, 99 non-expert sources and 99 bindings.

## Large-context learning goals

The goal was to reach 801K/1M and understand the limits. Keep successful
retrievals and failures with their memory/speed evidence; 64K was an
intermediate step.

- 64K/graphs passed 20 checks and 61,287-token retrieval.
- Matched short-input graphs control measured 95.5 tok/s versus 174–209 with
  DSpark (1.82–2.19x); C2 aggregate rose 168.6→292.9.
- 801K started at 95% with 5.22 GiB KV and 928,987 calculated capacity. All facts
  were correct at 799,847 input tokens; short recovery passed. Probe/HTTP times
  were 343.6/342.2 seconds, with JIT/build contention.
- 1M failed at 95%: 5.73 GiB needed, 4.98 available, estimated ceiling 813,056. At 96%,
  retrieval passed at 998,847 input tokens, then 19 API checks. Probe/HTTP/prefill
  times were 509.7/507.9/505.4 seconds; decode took 0.425 seconds for 35 tokens.
  JIT/build limits apply. See `results/dspark-1m-95-startup-failure.json`.
- Public rebuild passed using HTTPS/IPv4 and host networking. Image:
  `sha256:1f0776d3ac4a990186899d122ebee81e5ad0bcdf1dbb95ebccb30d5f94c6908e`.
  It passed 13 CPU methods, fresh-cache startup in 519.5 seconds, 19 LAN checks,
  998,868-token retrieval and chat/tool recovery. Details: docs/source-image-validation.md.

- 97%/1M passed startup, 19 checks and 998,847-token retrieval in 508.1 seconds.
  KV was 6.88 GiB, calculated capacity 1.32x and startup minima 347/312 MiB.
  Build/JIT/mixed timing limits apply.
- A short request still timed out after 180 seconds despite a second slot and
  spare KV. Long prefill consumed the step budget; later cap tests fixed admission.

- 97% / batch 2560 / cap 2304 passed mixed retrieval with 6.77–6.78 GiB KV. Short
  replies took 4.720/3.242 seconds; retrieval used 998,847 input/35 output tokens
  in 525.519 seconds (523.662 HTTP). 19 checks passed. Startup/inference minima:
  111/76 and 453/418 MiB.
- 96.5% passed the same protocol: 998,871/35 tokens, 525.619 seconds (523.813 HTTP),
  short replies 4.199/2.252 seconds, 19 checks, serving minima 1,011/976 MiB. Neither
  run is a controlled timing comparison.
- Both batch 2560 launches recovered from preparation warnings reporting 1–2 MiB
  free. Lower utilization shrank later KV without fixing earlier pressure:
  results/startup-allocation-review.json.
- The mixed probe now uses call boundaries and fresh prefixes; three regressions
  failed before the fix and passed after it. Server-phase evidence stays separate.
- docs/context-batch.md records sizing and matched-input plans. The default
  prioritizes coding/tools and preserves 801K/1M as learning goals.

## DSpark capability and measurement follow-up

- Source audit confirms K5/Markov and an unused confidence head. Adaptive
  verification was absent before memory tuning; later upstream compatibility
  remains untested.
- The built-in probe's 23.809-second median includes shared-connection waiting.
  Use the independent client with server observations.
- Seed 101 salted C1/C2 pilots matched 262,144 input/1,024 output tokens with zero
  hits. At 1M/96.5%/batch 2560/cap 2304, rates were 20.531/21.312 tok/s and median
  TPOT 8.436/29.752 ms, with 587/552 MiB free.
- At 524,288/batch 2560/cap 2304, rates were 20.054/21.169 tok/s, TPOT 8.256/29.349 ms,
  KV 6.88 GiB and 739/704 MiB free. Batch 4096/cap 3840 had 6.60 GiB KV and 407/372 MiB
  free; C1 was 18.920, its saved repeat 21.084 and C2 21.966 tok/s.
- At 1M/batch 2048/cap 1792, C1/C2 measured 18.804/19.996 tok/s with 795/760 MiB free.
  All pilots used 96.5%, matching counts and zero hits/preemptions. Small samples
  during a build can't rank these profiles. See results/context-batch-pilot.json.
- The source candidate passed 1M/96.5%/batch 2560/cap 2304 and its DSpark-off control.
  After restoration, 19 LAN checks passed. It was saved before interactive trials.

## Selected profile and remaining phases

Source acceptance, controls and profile selection are complete. Selected settings:
1M/96%/batch 2,048/cap 1,792, K5/Markov, target graphs and FP8 KV. Generic defaults
remain 64K/95%; use explicit overrides. Clean checkpoint `recipe-1m-k5` is
private; see [publication status](../publication/state.md).

The [interactive report](../../docs/interactive-latency.md) records three 262K
trials per profile and warmups. Both 96% caps passed 19 API checks and near-1M retrieval.
Cap 512 favors tools; cap 1792 favors coding. All outputs, hit differences,
serving minima and single-trial near-1M limits are retained there. Cap 1792 also
passed a 65.268-second restart and 19 post-long LAN checks.

The 48K fixture took 8.906 seconds at cap 1792 versus 12.205 at cap 512, a 37% cost
that favors cap 1792 for coding. Its 7% cost versus batch 2560/cap 2304 buys more
headroom. Short paired medians were 269.88/260.03 tok/s. Exact fixture bytes
and instructions are in benchmarks/prompts/.

The initial source candidate's tiny reply took 2.095 seconds while tools took
37.941 during near-1M prefill, despite observed admission. The four-call mixed
run took 513.165 seconds and sampled 507/472 MiB free. That motivated lower-memory
profiles. Short pairs measured 203.4/302.9/263.3 tok/s; the median 263.31 versus
163.96 control is 1.61x. Across nine short requests per workload, rates roughly
doubled. The 48,345-token fixture measured 61.50 versus 43.49 tok/s with zero hits;
KV fell 11.84→6.30 GiB per GPU. Full evidence: docs/source-image-validation.md.

Adaptive implementation and ROI remain in the
[private project](../../docs/repository-boundaries.md). Fixed-K5 gains stay here.

The [scorecard task](../performance-scorecard/plan.md) documents progression
through 292.9 tok/s aggregate, selected-profile gains and costs in
docs/performance-scorecard.md.

## User-reported MXFP4 comparison

The owner reported 801K and possibly 1M with MXFP4. We haven't reproduced that
run here, so compare allocations and settings before explaining a gap.
