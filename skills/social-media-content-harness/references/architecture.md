# Architecture boundaries

## Account Skill

Store reusable invocation, recovery, stage order, authority rules, and tool routing. Do not store API keys, Campaign-specific paths, fixed shot orders, product-specific facts, or production code.

## Local engine

Workspace: user-configured through `SMH_WORKSPACE` or the current directory.  
Active engine: Engine 2.6  
Entrypoint: `engine_v2_6.py`  
Immediate predecessor: Engine 2.5  
Frozen predecessor: Engine 2.3  
Freeze manifest: `releases/social-media-harness-v1/engine-freeze-manifest.json`

Keep executable validation, state transitions, privacy gates, evidence manifests, review orchestration, revision guards, media routing, final-package construction, and checksum verification here.

## Project directory

Store durable business rules, platform scope, brand direction, language defaults, fact boundaries, review policy, tool-instance decisions, and templates under `projects/<project>/`.

## Campaign directory

Store the one-off brief, source manifest, evidence, fact snapshot, story candidates, selected and final contracts, reviews, renders, publication package, and status under `campaigns/<campaign>/`.

## Persistent memory

Use versioned `memory/HEAD*.json` records and their referenced state chain. Every stage saves artifacts, active authorized panel reviews, bounded inactive-reviewer reasons, optional adversarial review and Codex dispositions when invoked, decision updates, current state, and next action.

## Archive

Use immutable `SMmmddyyyyNN` packages with archive manifest schema v3 containing master and platform media, covers, copy, subtitles, provenance, contracts, reviews, adjudication, owner approval, hashes, and publication status.
