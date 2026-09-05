# Interactive latency plan

1. Add `--short-check reply|tools_auto` to the independent mixed probe, preserving
   its default reply and reusing the existing tool check. Verify that both tool
   calls complete before the long completion; record failures and actual usage.
2. On the existing source-image candidate, run repeated mixed 262K retrieval/tool
   probes at the same delay with fresh long prefixes. Keep all trials, with GPU,
   running/waiting, usage, prefix-hit and preemption measurements. No build runs.
   Use one warmup and three measured repeats per profile. Tool prompts remain
   identical and can reuse cached blocks; do not claim the whole workload is
   uncached. The long prompt gets a fresh prefix on every run.
3. Compare the planned 1M/96%/batch2048/cap1792 candidate, then cap512 with otherwise
   identical settings. Use the same tool payloads and requested long length.
   Record actual lengths, warmups, mixed latency and long duration. Check startup
   fit and API behavior; revert to the saved candidate if a new profile fails.
4. Carry promising interactive profiles to near-1M mixed tool tests and short
   benchmarks. Include the frozen 48K coding fixture: the smaller cap's observed
   coding penalty justified testing both cap512 and cap1792 at near-1M. Retain
   the existing profile if improvement is not worth the prefill/headroom cost.
   Do not claim a universal optimum from a small matrix.
5. Document the gains, regressions and retained features, and update the scorecard.

This is a bounded configuration experiment. It does not introduce a scheduler,
change the DSpark algorithm or bypass adaptive-verification compatibility gates.
