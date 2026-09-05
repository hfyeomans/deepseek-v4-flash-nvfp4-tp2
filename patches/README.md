# Experimental runtime patches

The patches target jasl/vllm commit
`0f59188db1504b042ce621842bdde6c0fe862df6`, public tag
[`sm120-pr-41834-stable-preview-20260804`](https://github.com/jasl/vllm/releases/tag/sm120-pr-41834-stable-preview-20260804).
All 2,175 installed Python files also present in that checkout matched byte for
byte before patching. Generated version metadata and bundled third-party modules
were outside this comparison; it does not prove identical compiled binaries.

- `0001`: honor main-only NVFP4 metadata for the embedded MXFP4 draft.
- `0002`: match the exact 0731 model's low/high/max reasoning prefixes.
- `0003`: opt-in source-tensor coverage checks for the embedded TP-only MXFP4 draft.

These modify Apache-2.0 vLLM source, whose SPDX notices remain intact.
The reasoning strings come from the [pinned DeepSeek model encoder](https://huggingface.co/nvidia/DeepSeek-V4-Flash-0731-NVFP4/blob/f1caa71142bd0be02f728c79f75042ac1e461579/encoding/encoding_dsv4.py).
See [the model license](https://huggingface.co/nvidia/DeepSeek-V4-Flash-0731-NVFP4/blob/f1caa71142bd0be02f728c79f75042ac1e461579/LICENSE)
and [vLLM license](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/LICENSE).

All 13 CPU test methods pass in the diagnostic image. The 64K GPU launch
verified 4,608 expert tensors, 99 non-expert source tensors, and 99 bindings on
each TP rank. DSpark API feature checks passed at 32K, with retrieval repeated
at 61,287 prompt tokens on the 64K configuration. Final build/restart validation
is complete for this source image; see
[source-built acceptance](../docs/source-image-validation.md) and
[primary restoration](../results/feasibility-primary-restoration.json).
Adaptive candidate build/restart qualification remains pending. Do not apply
these patches blindly to another runtime or checkpoint:
upstream may have changed ownership, prefixes, metadata, or encoder behavior.
