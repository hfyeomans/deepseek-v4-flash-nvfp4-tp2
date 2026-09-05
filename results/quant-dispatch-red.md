# Quantization dispatch regression: unchanged image

The CPU regression reproduced the expected failure on 2026-09-05 at approximately
00:44 UTC. It ran against the original installed source, with no production patch,
GPU devices, network access inside the container, or writes to the model cache.

| Input | Pinned value |
|---|---|
| Image tag | `vllm-sm120-dsv4:preview-20260804` |
| Image ID actually executed | `sha256:a8434606207901f4596c6de6bac6bc246afef620dac3c8cde6f9555ab0075d26` |
| Model | `nvidia/DeepSeek-V4-Flash-0731-NVFP4` |
| Model revision | `f1caa71142bd0be02f728c79f75042ac1e461579` |
| Original config.json SHA-256 | `bb0d2286d6761439e41d3cef31d16489411b816ed8688922f59730bbd5567cdb` |
| Test source SHA-256 | `c685241bee71f458bedead12af4bdce2a1ce13a517d4577f68650bba16156564` |
| Raw output SHA-256 | `2c2cd01a9ee6eaed6142a5eebec3f1c535a189876cd2448b2813a80b1abbc5bc` |

Result: **5 test methods, 16 assertion failures, 0 errors; exit status 1.**

- All three draft runtime layers, with and without the `model.` prefix, selected
  NVFP4 and returned `is_mxfp4_quant=False`: six failed subtests.
- Five malformed explicit scopes failed to raise `ValueError` through either
  dispatch API: ten failed subtests. These are guard requirements for the repair.
- Target boundary dispatch, pinned metadata checks, and the native MXFP4 control
  passed. The MXFP4 control removes conversion metadata from a copy of the pinned
  config; it does not claim testing a second downloaded checkpoint.

See [the runnable test](../tests/test_quant_dispatch.py) and
[the complete failure output](quant-dispatch-red.txt). Missing CUDA/Triton driver
warnings are expected in this deliberately GPU-free container; no test errored.

The test imports the installed quantization config and executes its real config
parsing and dispatch methods. Only MXFP4/NVFP4 GPU method constructors are mocked.
It uses a real `RoutedExperts` instance shell without allocating its weights.
This demonstrates dispatch behavior; it does not demonstrate successful tensor
loading, GPU arithmetic, inference, or DSpark speedup.

## Reproduce on a host with the image and checkpoint cached

Run from the repository root. Set `HF_CACHE` to the Hugging Face **hub** directory,
so the snapshot's relative symlinks can resolve into `blobs`.

```bash
export HF_CACHE=/path/to/huggingface/hub
export IMAGE_ID=sha256:a8434606207901f4596c6de6bac6bc246afef620dac3c8cde6f9555ab0075d26
export MODEL_REVISION=f1caa71142bd0be02f728c79f75042ac1e461579
export DSPARK_TEST_MODEL_CONFIG="/hf-cache/models--nvidia--DeepSeek-V4-Flash-0731-NVFP4/snapshots/$MODEL_REVISION/config.json"

docker run --rm -i --network none \
  --mount "type=bind,source=$HF_CACHE,target=/hf-cache,readonly" \
  --env DSPARK_TEST_MODEL_CONFIG \
  --entrypoint python3 "$IMAGE_ID" - \
  < tests/test_quant_dispatch.py
```

The test is supplied on standard input; it is not copied onto the remote host.
After applying a candidate patch, rerun the same test against the new image and
retain both results. The unchanged-image failures are intentional and are not
marked as expected failures that would hide regressions.
