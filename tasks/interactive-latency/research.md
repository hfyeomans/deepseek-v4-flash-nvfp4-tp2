# Interactive latency research

The source-built 1M/batch2560/cap2304 candidate passes retrieval and all API
checks, but one automatic tool round trip during near-1M prefill took 37.941 s.
A tiny reply took 2.095 s. Admission was observed, so testing only a tiny reply
misses the longer generation delay. Sampled serving free memory reached
507/472 MiB per GPU. See [source-image evidence](../../docs/source-image-validation.md).

The existing `mixed_probe.py` already excludes prompt preparation from its overlap
boundary, uses an independent client, records fresh long-input prefixes and checks
retrieval correctness. `verify.py` already implements a checked automatic tool
round trip. Reuse both by adding a probe choice, retaining the existing default.

Smaller prefill chunks may shorten each mixed generation step but reduce long-input
throughput. Lower batch and utilization may improve serving headroom; early draft
preparation pressure is a separate concern. The pinned fixed-K5 DSpark, Markov
correction, precision and target graphs remain enabled throughout this comparison.
