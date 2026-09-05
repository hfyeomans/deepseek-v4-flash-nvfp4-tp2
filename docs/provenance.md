# Recipe snapshot provenance and rollback

Use `recipe-1m-k5` when you need to get back to the clean tested snapshot.
Runtime/build files, patches, clients, fixtures, tests and results kept their
original bytes at that tag. Docs and repo administration were split from research.

The later [release review](../tasks/release-readiness/review.md) fixed benchmark
termination, stream records, report paths and patch direction, and added
onboarding/CPU CI. Historical results, fixtures and runtime patches stayed
unchanged. Old manifests identify tagged clients; later
[GPU checks](../tasks/release-readiness/verification.md) have separate records.

## Reproduce the runtime

The checkpoint remains `f1caa71142bd0be02f728c79f75042ac1e461579`; the vLLM
source remains `0f59188db1504b042ce621842bdde6c0fe862df6` plus the
[three recipe patches](../patches/README.md). See
[original build provenance](../results/original-build-provenance.json) and
[source-image provenance](../results/source-build-provenance.json).
Model weights aren't included. Apache-2.0 source attribution is preserved.

## Checkpoints and historical records

Use `recipe-1m-k5` for this recipe's recovery point. The original
`baseline-1m-k5` Git tag and combined history remain in the private adaptive
archive. Old IDs in results identify the measurement environment; they are
not available refs in this clean repo. Keep those records unchanged.

The local Docker tag `dsv4-nvfp4:baseline-1m-k5` names image
`sha256:1f0776d3ac4a990186899d122ebee81e5ad0bcdf1dbb95ebccb30d5f94c6908e`
on the test host, independently of Git tags. It wasn't uploaded to a registry.
See [recovery instructions](running.md#preserved-baseline-and-rollback).

## Working copies after the history change

Start with a clean clone. Merging an old combined branch would bring research
history back into this repo. Keep research private, and label new measurements
with their own image/settings instead of rewriting historical results.
