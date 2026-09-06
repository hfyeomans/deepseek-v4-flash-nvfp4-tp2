# Is DSpark helping this deployment?

We wanted to know whether DSpark was doing useful work. First check loading
and accepted tokens. Then compare speed and outputs with DSpark disabled.
An acceptance counter going up only answers the first part.

## Evidence already obtained

The matched short-input test measured **95.5 output tok/s with graphs alone**
and **174–209 with DSpark**, a **1.8–2.2x** gain. Two-request aggregate rate rose
from 168.6 to 292.9 tok/s. Inputs were 30–41 tokens with 256-token outputs, and
the source build was stopped. See [settings and results](performance.md); these
measurements don't describe long-input speed.

Both ranks verified 4,608 expert sources, 99 non-expert sources and 99 parameter
bindings. Accepted-token counters increased during generation. Synthetic
reasoning, streaming, tools, structured output, cancellation and concurrency
checks passed. A separate near-1M retrieval passed too; broad long-context
coding/tool accuracy remains untested.

## What external results tell us

DSpark combines parallel drafting with a lightweight sequential head. Its paper
also proposes confidence-based verification using hardware costs and load.
Accepted tokens help when they repay draft and verification time; under load,
that work competes with other requests. The paper reports 60–85% faster per-user
generation at matched throughput against **MTP-1**, a different control from
ours. See the [DSpark paper](https://arxiv.org/html/2607.05147v1).

NVIDIA's older preview reports mean accepted lengths of 5.192 for MT-Bench
coding and 3.846 overall. Its 32K subset ranges from 4.939 on low-entropy data
to 2.641 on high-entropy data. These are **tokens returned per step**, not
speedup factors or percentages. The test used eight B300 GPUs, TP8 with expert
parallelism, seven draft positions and a different checkpoint. It shows workload
dependence, not a target for this TP2 recipe.
[NVIDIA preview results](https://huggingface.co/nvidia/DeepSeek-V4-Flash-nvfp4-DSpark#speculative-decoding-evaluation).

The 0731 NVFP4 checkpoint retains DSpark heads, but NVIDIA didn't test
speculative decoding for that release. We therefore needed checkpoint-specific
checks. See the [model card](https://huggingface.co/nvidia/DeepSeek-V4-Flash-0731-NVFP4#usage).

## Paper, current documentation, and our pinned engine

The August 4 V1 proposer uses fixed-block verification. It loads the confidence
head but doesn't call it to select variable prefixes. Our profile uses
**five draft tokens** with probabilistic sampling. See the
[pinned proposer](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/spec_decode/dspark.py#L213).

| Capability | Status in the tested recipe |
|---|---|
| Parallel draft backbone | Active |
| Sequential Markov correction | Active at every draft position |
| Target verification and accepted draft advancement | Active; live counters and matched timing confirm useful acceleration |
| Learned confidence head | Loaded, but not invoked by the active inference chain |
| Confidence/load/hardware-aware variable-prefix verification | Not implemented in this pinned proposer |
| Generic draft-length table by batch size | Disabled; not a validated substitute for confidence scheduling |
| Target decode CUDA graphs | Enabled and measured with `FULL_DECODE_ONLY` |
| Optional DSpark draft CUDA graph | Available in the pinned fork; disabled pending testing on this hardware |
| Fused Markov sampling optimization | Enabled by default, with request-dependent fallbacks; temperature-zero requests use the greedy path |

We didn't lose confidence scheduling through memory tuning; this source never
used it. Switching the draft to Marlin keeps Markov correction and target
verification. Draft experts stay MXFP4 and target routed experts stay NVFP4.

Fixed verification may spend work on weak suffixes; that cost is unmeasured
here. The generic batch-size table can't replace confidence scheduling: it
doesn't read confidence, changes full graphs to PIECEWISE and allows values
below the checkpoint's validated five-token layout. See
[Markov sampling](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/spec_decode/dspark_sampling.py#L182)
and [dynamic graph behavior](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/config/vllm.py#L902).

Measured graphs cover **target decode**. DSpark drafting is enabled. Its optional
draft CUDA graph records and replays the draft model's forward pass, the
computation used to propose tokens, to reduce GPU launch overhead. The prototype
uses `dspark_forward_cudagraph` and, for TP2, `dspark_forward_cudagraph_allow_tp`;
both default false. It captures one active draft request; two-request batches
fall back to ordinary execution while retaining two slots. Draft KV preparation,
input copies, vocabulary logits, Markov sampling and target verification stay
outside that graph. TP2/Marlin correctness, memory, recovery and speed remain
untested. See the [draft graph wrapper](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/spec_decode/dspark.py#L28).

Later vLLM documentation describes adaptive verification with confidence and
profiled graph costs, subject to attention-backend requirements. It doesn't
establish compatibility with this pinned SM120 build, mixed quantization or
Marlin. Qualify a separate candidate before adding the feature.
[Adaptive documentation](https://docs.vllm.ai/en/latest/features/speculative_decoding/adaptive_verification/).

## Matched evaluation to choose the default

Compare DSpark on/off with graphs enabled and the same checkpoint, context,
batch, slots, prompts, output lengths and sampling. Warm kernels separately,
stop competing builds, separate cache keys and repeat. Label any setting
changed to make a mode fit.

| Workload | Record together |
|---|---|
| Short coding, prose and reasoning | First-output delay, output tokens, generation time, total response time, accepted/proposed drafts |
| Fixed longer inputs | Actual input counts, prefill/TTFT, generation rate after prefill, end-to-end time |
| Tool call and tool-result round trip | Correct tool name/arguments/association, latency through usable final response, streaming behavior |
| One versus two active requests | Per-request latency, aggregate throughput, acceptance, queueing and preemptions |
| Short request during long prefill | Independent-client latency and correctness, server activity before/after, long-request cost |

Save raw and per-position counts so you can tell accepted/proposed fraction
from advancement per round. A weak suffix is worth investigating. It doesn't
tell you that turning DSpark off will be faster.

Random tokens test memory and scheduling. Their acceptance doesn't predict
natural coding workloads or code quality.

Count actual output tokens; one streamed event may contain several. Use the
independent mixed-load client because the pinned benchmark shares connections
with its probes. The [measurement audit](benchmark-measurement.md) explains why.

I'd choose on working APIs, interactive response and enough memory headroom.
Keep both short-decode and prefill-heavy results visible. That tells readers
where DSpark pays off and where input processing still dominates.

The [primary control report](primary-control-screen.md) applies this method.
[K5 metrics](dspark-k-and-verification.md) explain configuration and acceptance
denominators. Adaptive implementation and comparisons belong in the
[private research project](repository-boundaries.md).
