# Recipe snapshot provenance and rollback

The recipe starts from a clean Git snapshot of the tested serving files and
recorded acceleration findings. All runtime/build files, patches, benchmark
clients, fixtures, tests and measured result files retain their original bytes.
Documentation and repository administration were separated from private research.
This is a history/publication change, not a new model, runtime or benchmark run.

## Reproduce the runtime

The checkpoint remains `f1caa71142bd0be02f728c79f75042ac1e461579`; the vLLM
source remains `0f59188db1504b042ce621842bdde6c0fe862df6` plus the
[three recipe patches](../patches/README.md). See
[original build provenance](../results/original-build-provenance.json) and
[source-image provenance](../results/source-build-provenance.json).
Model weights are not included. Apache-2.0 source attribution is preserved.

## Checkpoints and historical records

Use this repository's `recipe-1m-k5` tag for the clean recipe checkpoint.
The original `baseline-1m-k5` Git tag and combined development history remain
unchanged in the private adaptive archive. Old commit IDs and rollback-tag names
inside measurement records identify the original measurement environment; they
are historical metadata, not refs advertised by this clean recipe repository.
Do not rewrite old result records to label them as newly measured experiments.

The recorded local Docker tag `dsv4-nvfp4:baseline-1m-k5` is independent of Git
tag naming. It identifies image
`sha256:1f0776d3ac4a990186899d122ebee81e5ad0bcdf1dbb95ebccb30d5f94c6908e`
on the tested host. No image was uploaded to a registry during repository work.
Follow [rollback instructions](running.md#preserved-baseline-and-rollback).

## Working copies after the history change

Use a fresh recipe clone. Do not merge an old combined-history branch back into
this repository; that would restore research ancestry. Keep research changes in
the private adaptive project. Shared metric updates must distinguish historical
observations from new measurements and identify the tested image and settings.
