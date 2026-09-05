# Community recipe readiness

The release keeps the tested fixed-K5 runtime and measured acceleration findings.
A newcomer needs an ordered path from prerequisites and model download to build,
launch, API checks and rollback. Review scripts, tests and documentation as one
user workflow; fix reproducible defects without unnecessary shared frameworks.

Acceptance: independent adversarial and duplication reviews are triaged; focused
regressions cover fixes; local checks can be reproduced; setup steps identify
what is required and what is already installed; unsupported platforms and unrun
checks remain labeled. Existing synthetic feature checks and 1M capacity results
must not become broad accuracy or clean-machine reproducibility claims.

- [x] Inspect build/launch, benchmark/client and documentation ownership.
- [x] Correct release-impacting findings and remove stale status claims.
- [x] Provide a newcomer walkthrough and reproducible local check command.
- [x] Rehearse available deployment steps; distinguish simulation, existing-host
  execution and an independent fresh-machine install.
- [x] Verify links, shell/client checks, relevant regressions and review fixes.
- [ ] Publish reviewed recipe and record remaining limitations.
