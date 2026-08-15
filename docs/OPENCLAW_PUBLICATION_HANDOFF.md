# OpenClaw Publication Handoff Executor

Engine 2.5 can validate an immutable `READY_NOT_PUBLISHED` archive and create a machine-readable OpenClaw handoff under `archive/<ID>/handoffs/openclaw/`.

The handoff includes absolute media/copy paths, file sizes, SHA-256 hashes, the archive-manifest hash, exact platform scope, and a receipt initialized as `PREPARED_NOT_DISPATCHED`. Rebuilding the same request is idempotent; a different request cannot overwrite an existing handoff.

This executor does not invoke OpenClaw, upload media, or publish. Both the task and receipt retain `publication_authorized: false`; OpenClaw must obtain and verify fresh owner authorization for the exact archive and platforms before any external action.

```powershell
python engine_v2_5.py --root . openclaw-handoff --archive-id SM0813202601
python engine_v2_5.py --root . openclaw-handoff --archive-id SM0813202601 --build
python engine_v2_5.py --root . verify-openclaw-handoff --archive-id SM0813202601
```
