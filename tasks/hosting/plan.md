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
- [ ] Select an interactive default after testing the observed long-prefill tool-latency/headroom tradeoff.
- [ ] Review shareable configuration, evidence, attribution, and documentation.
- [x] Produce the requested [before/after numerical scorecard](../performance-scorecard/plan.md),
  including the progression to 292.9 tok/s aggregate and its comparison limits.
- [ ] Publish only after the completed repository is reviewed for sharing.

Keep raw host logs under private scratch storage. Preserve failed tests alongside
retests; distinguish observed performance from advertised model capabilities.

## Learning goal clarified by the user

801K and 1M are explicit attempted context targets. Success is not presumed.
The community recipe should teach why a configuration succeeds or fails and
show the practical speed/memory tradeoffs. A well-evidenced failed attempt counts
as an informative result; stopping at a smaller working context does not address
this learning objective. Use 801,000 and 1,000,000 total-token windows, with
output headroom in retrieval prompts, and identify any additional test at the
model's 1,048,576-token ceiling separately.

## Performance optimization criterion

The user wants the fastest practical recipe with critical evaluation of 97% GPU
memory utilization. Keep DSpark, CUDA graphs, and API features enabled while
comparing feasible profiles. Assess long-input prefill latency, output generation
rate, and concurrency separately; no single metric establishes a universal optimum.

The user selected **interactive coding and tools, with occasional very long
inputs**, as the default workload. Prioritize short-request TTFT and tail latency,
generation and tool round trips during a concurrent long prefill. Preserve the
large-window option where feasible; a larger-batch throughput profile is optional
and must earn its context/headroom cost with measured gains.

- Establish the 1M/96% capacity result and sampled inference headroom.
- Evaluate 97% unchanged first as a capacity/headroom experiment; it is not an
  automatic speed optimization and must survive startup and actual requests.
- Use pinned cache-sizing code to select a small feasible batching comparison.
  Preserve two sequence slots in the main profile; a one-slot profile must be
  explicitly labeled as a concurrency tradeoff.
- Run controlled timing after the source build finishes, using the final image.
  Separate first-use compilation, cached-prefix reuse, and cold-input prefill.
  Warm kernels, then invalidate prefixes or reset the cache before timed long
  inputs. Record actual prompt/output tokens and speculative acceptance deltas.
- Select a default from measured results. If short-input serving and near-1M
  prefill prefer different settings, publish both profiles and their tradeoffs.

## Mixed-length responsiveness gate

The uncapped 97% profile admitted only the long prefill into execution; a short
request queued and timed out after 180 seconds. Preserve that failure evidence.
Test batch2560 with long-prefill threshold2304, yielding 248 scheduled tokens
for other work after DSpark's eight reserved slots. Require the short request to
finish while the long prefill remains active, and require the long retrieval to
complete correctly. No runtime source patch is planned for this configuration
issue.

For a later matched interactive comparison, batch2048/threshold1792 at 96% also
leaves 248 scheduling tokens. Compare it with batch2560/threshold2304 at 97%,
keeping speculation, graphs, sequence slots, prompts, cache state, and competing
load controlled. This compares a real responsiveness-preserving speed tradeoff.

After the current mixed trial, test 96.5% with the same batch2560/threshold2304
settings. Its projected KV budget is about 6.30 GiB versus 6.158 GiB admission
required, but the profile must confirm the fit. This should reclaim approximately
0.475 GiB per GPU if other allocations remain comparable; preserve all features.

## Context versus batch experiment

Keep the attempted 801K/1M goals alongside smaller-window alternatives. Compare
262,144, 524,288, and 1,000,000 total-token limits with feasible batches selected
from 2,048, 2,560, 4,096, and 6,144. First hold actual input at 131,072 tokens,
output at 512, and concurrency at one; then test two requests. Keep DSpark,
graphs, precision, memory utilization, and proportional prefill reservations
explicit. Record warm uncached TTFT, prefill throughput, decode latency,
aggregate throughput, short-probe latency, memory, preemptions, and correctness.
Near-limit retrieval is a separate capacity experiment. Use final-image results
without a concurrent build before selecting a performance default.

The standalone mixed probe previously started its overlap timer during prompt
preparation, allowing a false pass before the long HTTP request started. That
narrow measurement bug is fixed with request-bound timestamps, a fresh recorded
prompt prefix, and regressions for delayed preparation and early completion.
Keep the existing live observations, whose separate running-request metrics
support overlap. Do not expand the probe into another benchmark framework.

The pinned built-in probe has a separate shared-connection bottleneck at bounded
client concurrency. Use the independent client for responsiveness. Keep identical
random seeds across C1/C2 and profiles with fresh per-run cache salts, explicitly
recorded, and verify zero cache-hit deltas for uncached comparisons.

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
- [ ] Compare tool round trips during long prefill across feasible scheduling
  profiles. Preserve DSpark and API behavior; measure the latency, prefill-speed
  and memory costs before selecting a default.
- [x] Separate adaptive research and candidate qualification into the
  [private adaptive project](../../docs/repository-boundaries.md). Candidate
  implementation remains unfinished there; the recipe retains usable fixed-K5
  profiles and their acceleration evidence.
