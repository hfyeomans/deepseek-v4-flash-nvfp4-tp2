# Experimental runtime patches

These patches fix the failures recorded for jasl/vllm
`0f59188db1504b042ce621842bdde6c0fe862df6`, tag
[`sm120-pr-41834-stable-preview-20260804`](https://github.com/jasl/vllm/releases/tag/sm120-pr-41834-stable-preview-20260804).
Before patching, all 2,175 shared Python files matched the installed image.
Generated metadata, bundled modules and compiled binaries weren't compared.

- `0001`: honor main-only NVFP4 metadata for the embedded MXFP4 draft.
- `0002`: match the exact 0731 model's low/high/max reasoning prefixes.
- `0003`: opt-in source-tensor coverage checks for the embedded TP-only MXFP4 draft.

These modify Apache-2.0 vLLM source, whose SPDX notices remain intact.
The reasoning strings come from the [pinned DeepSeek model encoder](https://huggingface.co/nvidia/DeepSeek-V4-Flash-0731-NVFP4/blob/f1caa71142bd0be02f728c79f75042ac1e461579/encoding/encoding_dsv4.py).
See [the model license](https://huggingface.co/nvidia/DeepSeek-V4-Flash-0731-NVFP4/blob/f1caa71142bd0be02f728c79f75042ac1e461579/LICENSE)
and [vLLM license](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/LICENSE).

All 13 CPU methods pass. At 64K, both TP ranks verified 4,608 expert tensors,
99 non-expert sources and 99 bindings. DSpark API checks passed at 32K; retrieval
passed with 61,287 prompt tokens at 64K. Build/restart validation is complete;
see [source acceptance](../docs/source-image-validation.md) and
[primary restoration](../results/feasibility-primary-restoration.json). Adaptive
candidate qualification remains pending. Recheck source ownership, prefixes,
metadata and encoder behavior before applying these patches elsewhere.
