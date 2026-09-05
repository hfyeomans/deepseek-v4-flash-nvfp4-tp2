# Release deployment qualification

Status: **passed September 5, 2026**, using reviewed runtime inputs and clients
at `9cedab8225c03fe2500636b8bb32a982008f4c38`. This is a fresh recipe/source
working directory and a distinct rebuilt image on the original Linux GPU host, with existing
drivers, model cache and reusable Docker layers. It is not an independent
clean-machine installation or the user's own walkthrough.

- Source build: passed from pinned public source `0f59188db1504b042ce621842bdde6c0fe862df6`
  with `APT_HTTPS_IPV4=1 BUILD_NETWORK=host` and separate image names.
- Prerequisites: Docker GPU visibility passed on both cards; a separate Python
  environment installed the HF CLI; the pinned checkpoint download reused the
  existing cache successfully.
- Runtime image: all 13 CPU methods passed against checkpoint metadata.
- Local code: 28 host-only test methods, Bash syntax and ShellCheck passed.
- GPU first launch: passed at the selected 1M/96% profile with a new kernel
  volume. Readiness took 537.743 seconds from rehearsal start, including saved
  service shutdown and candidate launch/load/compile. New request shapes still
  compiled afterward. This is not a pure kernel compilation timing.
- First launch and warmed restart: 19/19 short feature checks passed on each.
  Each suite retained all four streaming observations, including early
  cancellation, and closed their responses.
- Retrieval: all three synthetic facts were correct in a 61,287-token prompt;
  the check took 22.744 seconds. No new near-1M retrieval was run in this rehearsal.
- Short benchmark: completed with valid terminal reasons; code median
  201.36 tok/s and one C2 aggregate 265.95 tok/s. These warm-prefix diagnostics
  have no matched off control or independent C2 warmup.
- DSpark: 2,326 accepted of 5,148 proposed tokens across feature, retrieval and
  benchmark traffic, with zero preemptions. This pooled count proves activity,
  not per-workload speedup. Coverage verified 4,608 expert tensors, 99 non-expert
  source tensors and 99 parameter bindings on each TP rank at both startups.
- Recovery: saved original image/container restored; health and 19/19 feature
  checks passed. The candidate remains stopped and available for inspection.
- [CPU CI passed](https://github.com/hfyeomans/deepseek-v4-flash-nvfp4-tp2/actions/runs/33985710528).
  Publication status is tracked [separately](../publication/state.md).

The rebuilt image is
`sha256:ed67a87a0cb1f5e1d337613add7c4255c1c9a5158d6fb026e243344b4fb5f817`.
The four checked runtime files and vLLM/Torch/FlashInfer/TVM FFI versions match
the preserved image. Both candidate startups reported 5.93 GiB available KV,
1,135,251 cache tokens and 0.10 GiB decode graph allocation. This does not prove
two simultaneous 1M requests. No out-of-memory text appeared in the captured
candidate log; shutdown emitted Python resource-tracker warnings. One restart
and bounded synthetic traffic do not establish long-duration stability.

[Machine-readable summary](../../results/release-qualification/summary.json),
[first features](../../results/release-qualification/candidate-features.json),
[restart](../../results/release-qualification/candidate-restart-features.json),
[retrieval](../../results/release-qualification/retrieval-61k.json),
[all benchmark trials](../../results/release-qualification/benchmark.json) and
[restoration](../../results/release-qualification/restored-original-features.json)
retain exact values and client/build hashes. Raw host logs remain in local
private evidence storage; synthetic feature observations are included here.

No new acceleration comparison or near-1M quality claim is made by this release
check. The earlier measured scorecard and 801K/near-1M observations remain
historical evidence at their recorded image and client revisions.
