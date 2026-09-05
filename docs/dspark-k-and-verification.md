# Why the tested recipe uses K5

**K5 matches the checkpoint and pinned runtime; it is not a measured optimum.**
The recipe's acceleration uses fixed K5, independently of adaptive verification.

## Four quantities that should not be conflated

| Quantity | Meaning in this checkpoint and runtime |
|---|---|
| Native block width W=5 | The checkpoint declares five draft positions; the NVIDIA model groups rows in blocks of five |
| Proposal length K | The number of draft tokens the proposer asks to generate |
| Verified prefix L | The number of those proposals sent for target verification, at most K |
| Accepted prefix A | The proposals the target accepts, followed by a recovered or bonus target token |

A fully accepted K5 step can advance **six tokens**: five proposals plus one
target token, unless EOS or the output limit truncates it. Acceptance fraction,
accepted drafts per event and total advancement therefore use different
denominators.

The rejection sampler uses target/proposal probabilities to accept drafts and
recover after rejection. Poor proposals alone do not imply wrong final output,
but probability and state bookkeeping must be correct.
[Sampler implementation](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/sample/rejection_sampler.py#L743).

## What the pinned source supports

The checkpoint declares five positions and groups rows in fives. Configuration
rejects K1–4. Values above five may pass with a warning but keep the same model
grouping. Validate request/probability mapping before benchmarking those values;
this is not a supported K sweep. See the
[guard](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/config/speculative.py#L1134)
and [grouping code](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/models/deepseek_v4/nvidia/dspark.py#L852).

The disabled batch-dependent K table does not read confidence and changes
full-graph behavior. It is unqualified for this recipe. See
[capabilities](dspark-evaluation.md).

## What the counters say about acceleration

Primary on-short clients recorded 1,924 rounds, 9,620 proposals and 4,233
accepted drafts. Positions 1–5 survived 1,533 / 1,111 / 741 / 511 / 337 times.
The fifth survived 17.5% of all rounds and 65.95% of rounds where the first four
survived. Neither fraction establishes the best prefix length.

Holding acceptance histories fixed, removing position five would reduce
advancement from 3.200 to 3.025 tokens per round. Cycle cost must fall more than
5.5% to break even. This is an estimate: changed histories, graph padding and
policy overhead can change the outcome. See the
[control report](primary-control-screen.md) for counters, timings and memory.

Markov correction and target verification are active; the confidence head is
loaded but unused. The [adaptive project](repository-boundaries.md) owns prefix
and confidence research. Measured improvements can return here as tested
recipe options.
