# Why the tested recipe uses K5

**K5 matches the checkpoint and pinned runtime; it is not a proved performance
optimum.** It is independent of whether adaptive verification is available.
The measured acceleration belongs to this fixed-K5 configuration.

## Four quantities that should not be conflated

| Quantity | Meaning in this checkpoint and runtime |
|---|---|
| Native block width W=5 | The checkpoint declares five draft positions; the NVIDIA model groups rows in blocks of five |
| Proposal length K | The number of draft tokens the proposer asks to generate |
| Verified prefix L | The number of those proposals sent for target verification, at most K |
| Accepted prefix A | The proposals the target accepts, followed by a recovered or bonus target token |

With K5 and full verification, a step can advance **six tokens**, absent EOS or
output-limit truncation. That is five accepted proposals plus one target token,
not six draft positions. Acceptance fraction, accepted tokens per draft event,
and total advancement per step therefore have different denominators.

The standard sampler uses target/proposal probabilities to accept proposals and
recover after rejection. Poor draft quality alone does not prove wrong final
output; actual probability and state bookkeeping must still be correct.
[Rejection sampler](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/sample/rejection_sampler.py#L743).

## What the pinned source supports

The checkpoint declares five draft positions, and the NVIDIA model groups rows
in blocks of five. The global configuration rejects K1–4. Values above five
can pass with a warning, but do not change that model grouping; they require
request/probability mapping validation before any performance result is useful.
This is not a supported free-form K sweep.
[Config guard](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/config/speculative.py#L1134),
[model grouping](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/models/deepseek_v4/nvidia/dspark.py#L852).

The generic batch-dependent K table is disabled. It does not read the learned
confidence head, and the pinned runner changes full-graph behavior when that
table is enabled. It has not been qualified as an alternative to this recipe.
See [capability details](dspark-evaluation.md).

## What the counters say about acceleration

Across the exact-primary on-short clients, 1,924 draft rounds proposed 9,620
tokens and accepted 4,233. Accepted positions 1–5 totaled
1,533 / 1,111 / 741 / 511 / 337. The fifth position survived in 17.5% of all
rounds, but in 65.95% of rounds where the first four survived. Those are different
denominators; neither establishes an optimal prefix by itself.

As a rough counterfactual holding those acceptance histories fixed, dropping
the fifth position reduces expected advancement from 3.200 to 3.025 tokens per
round. Whole-cycle cost would have to fall by more than 5.5% just to break even.
This arithmetic is not a measured shorter-prefix result: changed histories,
graph padding and extra policy work can alter the outcome. The
[control report](primary-control-screen.md) keeps counters, latency, throughput
and memory costs together.

The active recipe retains Markov correction and target verification. Its
confidence head is loaded but unused; no adaptive gain is claimed. Research
into fixed prefixes, compatibility and confidence-based selection belongs in
the [separate adaptive project](repository-boundaries.md). Future measured
improvements can return here as qualified recipe options.
