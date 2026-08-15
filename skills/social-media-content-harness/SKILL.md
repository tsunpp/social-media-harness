---
name: social-media-content-harness
description: Run or resume the local narrative-first, four-agent social-media production workflow for authentic image, video, cover, caption, platform-package, and archive tasks. Use when Codex needs to turn raw business or production media into Instagram Reels, YouTube Shorts, TikTok-style vertical content, image posts, covers, or reusable post packages; when the user asks for the Social Media Harness, Narrative-First planning, Claude, MiniMax, Kimi, or optional DeepSeek review, ComfyUI or MiniMax generation routing, campaign recovery, or an SM-numbered archive; or when continuing a campaign created by this workflow.
---

# Social Media Content Harness

Use the local engine as the execution authority and this Skill as the workflow entrypoint.

## Locate and recover

1. Resolve the workspace from the user's input, `SMH_WORKSPACE`, or the current directory. Never assume a personal drive path.
2. Verify `engine_v2_6.py`, `config/engine_interface_2_6.json`, `engine_v2_5.py`, `engine_v2_3.py`, and `releases/social-media-harness-v1/engine-freeze-manifest.json` exist. Treat Engine 2.5 as the immediate predecessor and Engine 2.3 as frozen; neither is the default for new work.
3. Read the newest valid `memory/HEAD*.json`, following its referenced state and decision chain. Do not reconstruct state from chat history when persisted state exists.
4. Read the selected project's `project.yaml`, `PROJECT_DECISIONS.md`, applicable files under `decisions/`, and `NARRATIVE_FIRST_POLICY.md`.
5. Read the current Campaign brief, source manifest, active fact contract, privacy state, final effective story contract, review state, and render manifest. Treat superseded contracts as history only.

Read [architecture.md](references/architecture.md) when selecting project, Campaign, memory, engine, or archive boundaries. Read [workflow.md](references/workflow.md) before creating or resuming production.

## Use Engine 2.6

- Use `engine_v2_6.py` or `app.engine_api_v2_6.EngineV26` for new work. Engine 2.6 extends Engine 2.5 and the frozen Engine 2.3 integrity rules.
- Preserve older engine interfaces for historical Campaign recovery; never rewrite an archived Campaign merely to upgrade it.
- Resolve external review transfers through the project's Engine 2.6 authorization matrix. Do not repeat confirmation inside an active recorded scope, and never extend authorization to a new recipient, material class, identifiable-person scope, or publication.
- Resolve platform requirements from `config/platform_profiles_v2_6.json`; do not impose Instagram or YouTube dimensions on WeChat or TikTok packages.
- Resolve audio authority independently from media-input capability. Retain the owner listening gate unless the requested listening domain is explicitly validated.
- Require stable file hashes, explicit status, reviewer evidence, Codex adjudication, and a next action at every stage.
- Save every material stage result before proceeding. Do not depend on the conversation context as project memory.

## Enforce Narrative-First planning

Before ranking shots, create exactly three evidence-testable micro-story skeletons. Require each to define the audience question, middle change or discovery, visual climax, ending insight, story-advancing text progression, authentic source feasibility, five narrative beats, and verified asset IDs for every beat.

Reject an attractive montage without progression. Reject label-only copy. If a required documentary beat is missing, revise the story or request new capture; never silently generate the missing factual event.

## Review with complete evidence

- Give Claude the complete systematic visual timeline. Use Claude primarily for visual hierarchy, composition, typography, color, pixel-visible facts, privacy, and narrative clarity.
- Give MiniMax every complete source proxy needed by the story and the complete cumulative or final video. Use MiniMax primarily for action start/change/result, motion, pacing, temporal continuity, and stable-rest judgments. Do not infer complete-audio or BGM authority from video-input access; require a separately validated capability record.
- Give Kimi a sanitized Campaign dossier, the complete multi-image timeline, brief, facts, current effective contract, copy, all review records, and provenance manifests. Use Kimi for narrative logic, fact integrity, copy consistency, chronology, provenance, and workflow audit—not visual aesthetics, motion, pacing, audio, BGM, or cover selection.
- Give every active reviewer the complete evidence required by its Engine 2.6 evidence contract. Record privacy-inactive reviewers with a bounded reason and never represent them as PASS.
- Treat a review without the required complete evidence as invalid. Save normalized and raw responses separately.

When reviewers disagree, apply Engine 2.6 modality arbitration rather than majority vote. Let MiniMax complete-video evidence govern validated motion-only disputes unless pixels contradict it; let Claude systematic visual evidence govern typography, composition, color, privacy, and pixel facts; let an active Kimi govern its validated narrative, fact, copy, chronology, provenance, and workflow-audit domains; let Codex govern orchestration, contracts, evidence adjudication, repair, and persistence. Record the reason.

Use DeepSeek only as an optional text-only adversarial critic at narrative selection, final master, or publication-package stages. It challenges Codex conclusions using cited textual evidence, is not a panel vote, and has no visual, motion, audio, BGM, mix, or publication authority. Codex must disposition every challenge; escalate unresolved factual uncertainty or owner-only issues.

## Produce and revise

1. Map every selected shot to one narrative function.
2. Create a segment contract before rendering.
3. Render one segment at a time, then review the complete cumulative timeline through that segment.
4. Route ordinary defects back to Codex automatically, respecting the quality-first revision limit and no-improvement guard.
5. Synchronize the final story contract whenever asset, timing, text, or beat assignments change.
6. Require authoritative Engine 2.6 privacy-adaptive panel clearance against the synchronized final contract before approving a master. A reviewer may clear only its validated modality; an unavailable or unauthorized reviewer must be recorded as inactive, not PASS.

Default every video title, subtitle, source credit, and cover title to a transparent background. Never use black boxes, black pills, or large dark backing panels unless the owner explicitly requests them. Preserve legibility with restrained shadow, fine stroke, placement, or local contrast instead.

Use FFmpeg for deterministic editing, subtitles, color, HDR/HLG-to-SDR conversion, audio, assembly, and platform encoding. Use `comfyui_aki` only when deterministic methods cannot meet the approved goal. Never fall back to `comfyui_standard`; it remains disabled until separately audited. Do not use generation merely to ensure ComfyUI participates. Record instance, workflow, model, prompt, source hashes, and output hashes for every generated artifact.

## Preserve authority boundaries

Automatically perform ordinary API review calls, evidence-safe uploads, normal creative repair, rerendering, technical QC, hashing, and persistence.

Escalate only factual or privacy uncertainty, incompatible core creative requirements, a reached safety or no-improvement limit, required new capture, a material change to product truth, or final publication authorization. Never publish automatically.

## Finalize and archive

After synchronized Engine 2.6 panel clearance and a passing hash-bound final-contract consistency gate:

- mark the master `APPROVED_NOT_PUBLISHED`;
- prepare platform outputs, covers, captions, subtitles, specifications, and hashes at the publication-package stage;
- retain the owner publication gate;
- archive with `SMmmddyyyyNN` naming and archive manifest schema v3 without overwriting an existing package;
- update persistent memory and the next action.

## Validate integrity

Before handing off a completed stage, run relevant tests; verify media decode and technical properties; verify contract/render synchronization; verify no quarantined pixels were sent externally; verify cross-version text attribution; and report the exact status and publication authority.
