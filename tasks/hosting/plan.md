# Implementation and validation plan

- [x] Identify the exact host image, GPUs, cached model revision, and source provenance.
- [x] Preserve the user's existing image, source, and launcher.
- [x] Reproduce startup and mixed-quantization failures before applying narrow fixes.
- [x] Rebuild the incompatible kernel and validate the native NVFP4 baseline.
- [x] Compare reasoning prompts against the pinned checkpoint's official encoder.
- [x] Enable DSpark with the correct draft format and a working SM120 backend.
- [x] Verify positive speculative counters and the full 32K feature suite.
- [x] Add and regress the complete draft-loading diagnostic.
- [x] Verify that diagnostic against real weights on both GPUs.
- [x] Validate 64K with CUDA graphs and a 61,287-token retrieval probe.
- [x] Attempt 801K context with DSpark; record memory fit and retrieval or failure.
- [x] Attempt 1M context with DSpark; record memory fit and retrieval or failure.
- [ ] Explain limiting resources using DSpark-off controls and bounded tuning/offload experiments when warranted.
- [x] Complete a fresh public-source build and inspect its runtime dependencies.
- [x] Run matched baseline/DSpark benchmarks without competing build activity.
- [x] Restart the source-built candidate and repeat feature acceptance.
- [x] Select an interactive default after testing the observed long-prefill tool-latency/headroom tradeoff.
  See [completed selection](../interactive-latency/state.md).
- [ ] Review shareable configuration, evidence, attribution, and documentation.
- [x] Produce the requested [before/after numerical scorecard](../performance-scorecard/plan.md),
  including the progression to 292.9 tok/s aggregate and its comparison limits.
- [ ] Publish only after the completed repository is reviewed for sharing.

Keep raw host logs private. Retain failures beside retests and distinguish
measured behavior from advertised capabilities.

## Learning goal clarified by the user

Attempt 801K and 1M and explain successes or failures through measured speed
and memory. A failed attempt is useful evidence; stopping at 64K would leave
the goal unfinished. Use 801,000 and 1,000,000 total-token windows with output
headroom. Label tests at the model's1,048,576 ceiling separately.

## Performance optimization criterion

Find the fastest practical profile and critically test 97% memory. Keep DSpark,
graphs and APIs enabled. Compare prefill, generation and concurrency separately.

The selected workload is **interactive coding and tools, with occasional long
inputs**. Prioritize first output, tail latency and tools during long prefill.
Keep a large window where feasible; a larger-batch profile needs measured
benefits to justify less context or headroom.

- Establish 1M/96% capacity and sampled serving headroom.
- Test 97% unchanged for capacity and headroom before treating it as faster.
- Use pinned sizing code to choose a small batch comparison. Keep two slots;
  label any one-slot test as a concurrency tradeoff.
- Time the final image without a competing build. Separate cold compilation,
  cached prefixes and warm uncached prefill. Record tokens and draft acceptance.
- Choose profiles from measurements; publish separate short/long choices if
  their tradeoffs warrant it.

## Mixed-length responsiveness gate

The uncapped 97% profile queued a short request until its 180-second timeout.
Retain the failure. Test batch 2560/cap 2304, leaving 248 scheduled tokens after
DSpark reserves eight. Require correct retrieval and a short reply before
long prefill finishes. This is a configuration test; no scheduler patch is planned.

Then compare 96% / batch 2048 / cap 1792 with 97% / batch 2560 / cap 2304. Both leave
248 scheduling tokens. Match speculation, graphs, slots, prompts, cache and load.

Test 96.5% with batch 2560/cap 2304. Projected KV is 6.30 GiB versus 6.158 GiB
required; startup must confirm fit. The expected saving is 0.475 GiB per GPU
if other allocations match, with all features retained.

## Context versus batch experiment

Compare 262,144,524,288 and 1,000,000 windows with feasible batches from 2,048,
2,560,4,096 and 6,144, alongside 801K/1M capacity goals. Fix input at 131,072,
output at 512 and compare C1/C2 separately. Match memory or label differences.
Record warm uncached TTFT, prefill, decode, aggregate throughput, probes, memory,
preemptions and correctness. Use controlled final-image results to choose defaults.

The mixed probe previously counted prompt preparation as overlap. Request-bound
timestamps, unique prefixes and delayed-preparation/early-completion regressions
fix that false-pass path. Keep earlier live results supported by server metrics.
Reuse this client rather than adding a benchmark framework.

The built-in probe has a shared-connection bottleneck. Use the independent
client for responsiveness. Match random seeds across C1/C2 and profiles, assign
fresh recorded salts and verify zero hits for uncached comparisons.

## DSpark effectiveness and capability audit

- [x] Compare primary-source expectations against the exact pinned implementation.
- [x] Establish active parallel drafting and Markov correction, fixed K=5, and
  loaded-but-unused confidence head. Document adaptive verification as absent
  from the preview rather than removed by memory tuning.
- [x] Clarify that measured graphs cover target decode. Record the disabled,
  experimental draft-forward graph and its one-active-draft/TP-opt-in limits.
- [ ] If evaluating that prototype after the baseline, use an isolated candidate
  and measure capture/replay correctness, C1 benefit, C2 fallback, memory and
  mixed-request behavior; do not infer a gain from the flag alone.
- [x] Repeat matched DSpark on/off controls on the final image for coding,
  longer inputs and two-request load. Separate prefill,
  generation, total latency, and acceptance; preserve existing short results.
  Reuse benchmark.py with optional --code-prompt-file and --cache-mode inputs:
  preserve warm-prefix defaults, freeze and hash exact code-prompt bytes, and
  assign a fresh recorded cache salt to every request in uncached mode. Regress
  the actual outgoing payloads and default behavior. The existing concurrent
  pair remains prose + code, so a long-code override makes it a mixed-length
  pair. Global speculative counters still cover the entire run, not code alone.
- [x] Compare tool round trips during long prefill across feasible scheduling
  profiles. Preserve DSpark and API behavior; measure the latency, prefill-speed
  and memory costs before selecting a default.
- [x] Separate adaptive research and candidate qualification into the
  [private adaptive project](../../docs/repository-boundaries.md). Candidate
  implementation remains unfinished there; the recipe retains usable fixed-K5
  profiles and their acceleration evidence.
