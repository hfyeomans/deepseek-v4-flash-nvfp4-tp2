# Removed paths

Removed the launcher's assistant-named kernel cache default and the walkthrough's
temporary first-run image/container/cache names. New runs use stable NVFP4 names.
Historical records retain their original identifiers.

Removed the separate `FINAL_IMAGE` setting from current build code. `IMAGE` now
owns build and launch selection. Frozen-tag rollback examples still use the old
setting because that code requires it.

Removed direct CLI argument passthrough from `serve.sh`; it could override the
port/model without updating Docker health probes or client instructions. Use
the corresponding `.env` settings. No runtime model feature was removed.
