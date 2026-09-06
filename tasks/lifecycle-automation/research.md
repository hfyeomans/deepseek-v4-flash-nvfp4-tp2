# Automated lifecycle research

The owner wants to edit `.env` and run one script that chooses build, resume
or replacement. They selected automatic apply and requested a complete docs
reconciliation. Performance tests, model validation and serving defaults keep
their existing behavior.

`build.sh` owns the three image stages. `serve.sh` owns serving validation and
Docker/vLLM arguments. `scripts/config.sh` loads trusted Bash assignments.
Docker retains stopped containers, which caused the reported name conflict.
The current manual replacement instructions require too much Docker knowledge.

A small coordinator can reuse those owners. Compose would add a dependency and
require adapting the Bash configuration or maintaining another launch definition.
Always rebuilding/replacing would avoid comparisons but needlessly interrupt
unchanged service. Choose a coordinator with explicit build and serving records.

The lifecycle review recommends preparing a stopped candidate before stopping
the old service, preserving its container/logs and image, and comparing actual
Docker image IDs. Failed inspection must not be treated as absence. Load one
effective configuration per operation and serialize changes within the checkout.
An old unlabeled image needs a conservative cached build to establish provenance;
an existing recipe container can be migrated while retaining it for recovery.

No Docker or SSH operations are part of this implementation session.
