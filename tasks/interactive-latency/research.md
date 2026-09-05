# Interactive latency research

The source 1M/batch 2560/cap 2304 candidate passed retrieval/APIs but took 37.941
seconds for tools during near-1M prefill versus 2.095 for a tiny reply. Admission
was observed; serving free memory reached 507/472 MiB. See
[source evidence](../../docs/source-image-validation.md).

`mixed_probe.py` already measures call overlap, uses independent requests and
fresh prefixes, and checks retrieval. `verify.py` has an automatic tool check.
Reuse them through a probe option and keep the default reply.

Smaller chunks may help tools respond while slowing the long input. Lower
batch/utilization may add serving headroom. Test preparation pressure separately
and keep K5, Markov, precision and target graphs unchanged.
