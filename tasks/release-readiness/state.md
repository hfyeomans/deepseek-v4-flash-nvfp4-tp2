# Release readiness state

Earlier release checkpoint, September 5, 2026: review fixes, 28 local methods and shell checks passed.
Onboarding, tagged recovery, development docs and CPU CI are included.
Historical results and runtime patches remain unchanged.

Current deployment uses the [automated lifecycle](../lifecycle-automation/state.md).
Its local checks and pending GPU walkthrough are separate from this record.

The separate source rebuild passed on the existing GPU host, including Docker
GPU visibility, isolated HF CLI setup, pinned cache reuse and 13 image methods.
The candidate passed 19 API checks, 61K retrieval, a short benchmark and 19 API checks after
restart. The restored original passed 19 API checks too. CPU CI passed. See
[verification](verification.md).

The recipe remains private during prose review. It was replaced under the
same GitHub name after local research backups; its repository ID changed.
Three old research commits are missing, with Git-object endpoints returning 404.
Clean refs/settings are restored. After prose review, publication still needs
visibility approval and anonymous clone verification. Adaptive research stays
private.

Adaptive implementation gets a separate session; its private repo has the
handoff. The owner's walkthrough is in progress; a fresh-machine install and
the new lifecycle's GPU qualification remain open.
