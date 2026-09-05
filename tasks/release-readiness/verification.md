# Release deployment qualification

Status: in progress on September 5, 2026. This is a fresh recipe/source checkout
and a distinct rebuilt image on the original Linux GPU host, with existing
drivers, model cache and reusable Docker layers. It is not an independent
clean-machine installation or the user's own walkthrough.

- Source build: passed from pinned public source `0f59188db1504b042ce621842bdde6c0fe862df6`
  with `APT_HTTPS_IPV4=1 BUILD_NETWORK=host` and separate image names.
- Prerequisites: Docker GPU visibility passed on both cards; a separate Python
  environment installed the HF CLI; the pinned checkpoint download reused the
  existing cache successfully.
- Runtime image: all 13 CPU methods passed against checkpoint metadata.
- Local code: 28 host-only test methods, Bash syntax and ShellCheck passed.
- GPU first launch, 19 API checks, bounded retrieval, short benchmark, warmed
  restart and restoration of the original service: pending completion.
- CI execution and GitHub publication: pending.

No new acceleration comparison or near-1M quality claim is made by this release
check. The earlier measured scorecard and 801K/near-1M observations remain
historical evidence at their recorded image and client revisions.
