# Is DSpark helping this deployment?

The answer has two parts: verify that drafting works, then measure whether it
improves the workload that matters. Positive acceptance counters establish
activity. They do not establish a speedup or broad correctness.

## Evidence already obtained

The matched short-prompt control measured about **95.5 output tokens/second
with graphs alone**, versus **174–209 with DSpark**, or **1.8–2.2x**. Two-request
aggregate throughput rose from 168.6 to 292.9 tok/s. These tests used 30–41 input
tokens and 256 output tokens, with the source build stopped. They do not
establish speed after a long input. See [settings and raw results](performance.md).

Draft loading was checked on both GPU ranks: 4,608 expert source tensors, 99
non-expert sources, and 99 parameter bindings. Accepted draft counters increased
during generation. Synthetic reasoning, streaming, tools, structured output,
cancellation and concurrency checks passed, alongside near-1M retrieval.
The short API suite and near-limit retrieval are separate tests, not broad
long-context coding or tool accuracy evidence.

## What external results tell us

DSpark combines parallel drafting with a lightweight sequential head. Its paper
also introduces confidence-based verification that accounts for hardware cost
and load. More accepted tokens help only if they repay drafting and verification
time. Extra speculative work can compete with other requests under load.
The paper reports 60–85% faster per-user generation at matched throughput against
the production **MTP-1** baseline; that is a different comparison from our
DSpark-off control. [DSpark paper](https://arxiv.org/html/2607.05147v1).

NVIDIA's older preview DSpark checkpoint reports average accepted lengths of
5.192 for MT-Bench coding and 3.846 overall. Its 32K throughput subset varies
from 4.939 on low-entropy data to 2.641 on high-entropy data. These are tokens
returned per decoding step, **not speedup factors or percentages**. That run
used eight B300 GPUs, TP8 plus expert parallelism, draft length seven, and a
different checkpoint. It is evidence of workload dependence, not a target this
two-GPU recipe must match.
[NVIDIA preview evaluation](https://huggingface.co/nvidia/DeepSeek-V4-Flash-nvfp4-DSpark#speculative-decoding-evaluation).

The exact 0731 NVFP4 model preserves the DSpark heads, but NVIDIA did not exercise
speculative decoding during its release validation. Our checkpoint-specific
checks are therefore necessary.
[0731 model card](https://huggingface.co/nvidia/DeepSeek-V4-Flash-0731-NVFP4#usage).

## Paper, current documentation, and our pinned engine

This recipe uses the August 4 preview source. Its V1 DSpark proposer explicitly
implements fixed-block verification and excludes confidence-scheduled variable
prefixes. The checkpoint confidence head is constructed and loaded; that alone
does not mean it is invoked. Our enabled profile uses **five draft tokens** and
probabilistic draft sampling. Loading every weight and using every research
feature are different claims.
[Pinned proposer scope](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/spec_decode/dspark.py#L213).

| Capability | Status in the tested recipe |
|---|---|
| Parallel draft backbone | Active |
| Sequential Markov correction | Active at every draft position |
| Target verification and accepted draft advancement | Active; live counters and matched timing confirm useful acceleration |
| Learned confidence head | Loaded, but not invoked by the active inference chain |
| Confidence/load/hardware-aware variable-prefix verification | Not implemented in this pinned proposer |
| Generic draft-length table by batch size | Disabled; not a validated substitute for confidence scheduling |
| Target decode CUDA graphs | Enabled and measured with `FULL_DECODE_ONLY` |
| Experimental DSpark draft-forward graph | Available in the pinned fork, disabled and not GPU-validated here |
| Fused Markov sampling optimization | Enabled by default, with request-dependent fallbacks; temperature-zero requests use the greedy path |

The memory/context experiments did not remove confidence scheduling: it was
already absent from this source. Switching draft experts to Marlin did not
remove the Markov head or target verification. The draft retains the checkpoint's
native MXFP4 format; the main routed experts remain NVFP4.

The practical cost of fixed verification is potentially spending compute on
weak draft suffixes. Its magnitude on these GPUs is unmeasured. The generic
batch-size table does not read learned confidence, and on this runner would
change full graphs to PIECEWISE. Values below the checkpoint's five-token block
also reach an unvalidated layout. Do not present it as a safe replacement for
adaptive verification.
[Markov sampling](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/spec_decode/dspark_sampling.py#L182),
[dynamic-schedule graph behavior](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/config/vllm.py#L902).

The measured graphs cover **target decode**, not the entire drafting pipeline.
The separate prototype uses speculative-config fields `dspark_forward_cudagraph`
and, for TP2, `dspark_forward_cudagraph_allow_tp`; both default false. It captures
only draft-model forward work for one active draft request. Two-request draft
batches fall back to ordinary execution without reducing the configured two
slots. Draft KV preparation, input copies, vocabulary logits, Markov sampling and
target verification remain outside that draft graph. Capture and replay have
constraints; source eligibility does not prove TP2/Marlin correctness, memory
fit, recovery or speed. This is an untested execution optimization, not evidence
that a model capability has been removed.
[Pinned draft graph wrapper](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/spec_decode/dspark.py#L28).

Newer vLLM documentation describes opt-in adaptive verification using DSpark
confidence estimates and profiled graph costs. It also imposes attention-backend
requirements. Those instructions describe a later implementation, and do not
establish compatibility with our pinned SM120 engine, mixed quantization, or
Marlin draft. Treat migration as a separately tested candidate, rather than
adding an unsupported flag to this recipe.
[Current adaptive-verification documentation](https://docs.vllm.ai/en/latest/features/speculative_decoding/adaptive_verification/).

## Matched evaluation to choose the default

For the selected interactive coding/tools workload, compare DSpark on and off
with graphs enabled in both cases, the same checkpoint, context limit, batch
budget, request slots, prompts, output budget and sampling settings. Warm kernels
separately, stop competing builds, isolate prefix-cache keys, and repeat each
case. If a setting differs to make one configuration fit, label it explicitly.

| Workload | Record together |
|---|---|
| Short coding, prose and reasoning | First-output delay, output tokens, generation time, total response time, accepted/proposed drafts |
| Fixed longer inputs | Actual input counts, prefill/TTFT, generation rate after prefill, end-to-end time |
| Tool call and tool-result round trip | Correct tool name/arguments/association, latency through usable final response, streaming behavior |
| One versus two active requests | Per-request latency, aggregate throughput, acceptance, queueing and preemptions |
| Short request during long prefill | Independent-client latency and correctness, server activity before/after, long-request cost |

Keep acceptance fraction (accepted/proposed drafts) separate from mean advancement
per draft round. Record raw counters so differences in metric definitions remain
auditable. Inspect acceptance by position when available: a weak suffix may
consume work without useful advancement. It is a tuning clue, not evidence that
turning DSpark off will be faster.

Random-token workloads are useful for matched memory and scheduling tests. They
do not represent code quality or reliably predict acceptance on natural coding
requests. Never extrapolate their acceptance to the whole deployment.

Use actual output-token counts; streamed events may contain multiple tokens.
Avoid the pinned benchmark's shared-connection mixed probe; use the independent
client. The [measurement audit](benchmark-measurement.md) records this failure
and the corrected procedure.

The default must preserve the tested API behavior and improve interactive
latency with adequate memory headroom. A larger acceptance number, batch size,
or advertised context window alone does not decide the winner. If DSpark helps
short decode but has little effect on a prefill-dominated long request, publish
both results; the useful conclusion is workload-specific.

The [exact-primary control report](primary-control-screen.md) applies this
method to the selected 1M profile and preserves the measured benefits and costs.
Read [K5 and accepted-prefix metrics](dspark-k-and-verification.md) for the
configuration constraints and correct acceptance denominators. Adaptive
implementation and its future comparisons now belong in the
[separate private research project](repository-boundaries.md).
