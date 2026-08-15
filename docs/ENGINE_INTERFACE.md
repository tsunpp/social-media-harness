# Stable local engine interface

The future account-level Skill must call this interface instead of importing campaign-specific scripts.

## Output contract

Every command returns one JSON object containing:

- `engine_api_version`
- `run_id`
- `command`
- `status`
- `ok`
- `data`
- `errors`
- `next_action`

## Commands

```powershell
python engine.py recover
python engine.py capabilities
python engine.py campaign list
python engine.py campaign start --slug second-campaign --title "Second Campaign"
python engine.py campaign status --slug second-campaign
python engine.py campaign history --slug second-campaign
python engine.py campaign advance --slug second-campaign --to INGESTED --actor codex --note "assets ready"
python engine.py review-video --campaign sample-documentary --version v1-en-sdr
```

`review-video --run-apis` performs paid Claude and MiniMax calls and must only be invoked when authorized by the active workflow.

## Honest capability boundary

The interface reserves `plan`, `review-image`, `finalize`, and `archive`, but currently returns `NOT_IMPLEMENTED` for them. A Skill must inspect `capabilities` and may not claim these stages are executable until their implementations and tests exist.

## Recovery

`recover` begins at `memory/HEAD.json`, validates every referenced file, loads the base state, applies state overlays in order, loads active decisions, and reports superseded records. Missing references produce a structured failure instead of silently continuing with stale context.

