# Interactive latency plan

1. Add `--short-check reply|tools_auto`, keeping the reply default and reusing
   the tool check. Require both tool calls to finish before the long request;
   retain failures and usage.
2. Run one warmup and three 262K mixed repeats per profile without a build. Match
   delay, use fresh long prefixes and save GPU/server counters. Fixed tool
   prompts may reuse cache; don't label the whole workload uncached.
3. Compare 1M/96%/batch 2048/cap 1792, then cap 512 with other settings fixed. Record
   actual lengths, latency and headroom; check startup/APIs and recover if needed.
4. Test promising profiles near 1M and on short/48K coding inputs. The smaller
   cap's coding penalty warrants testing both caps. Keep the original profile
   if gains don't repay costs; this small matrix can't prove an optimum.
5. Record gains, regressions and retained features in the scorecard.

This tests configuration only. Scheduler/DSpark changes and adaptive
compatibility remain separate work.
