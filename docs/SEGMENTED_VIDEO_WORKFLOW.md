# Segmented Video Production Workflow

This workflow is mandatory for every newly generated video.

1. Codex creates at least two candidate segmentation schemes. Each segment defines its purpose, duration, evidence, production route, prompt, continuity in/out and acceptance criteria.
2. Claude receives the complete brief, asset inventory, visual evidence and every candidate scheme. MiniMax receives the same context plus all representative motion evidence and generation-route details.
3. No generation starts until both reviewers pass the same selected scheme. Ordinary comments are adjudicated by Codex; factual, privacy or incompatible direction conflicts go to the owner.
4. Each approved segment runs through Engine 1.8 production: authentic edit, Aki ComfyUI H3, MiniMax H3 API and/or FFmpeg. The standard ComfyUI remains disabled until separately audited.
5. Each segment is technically checked and independently reviewed by Claude and MiniMax using the complete segment video, not isolated text or a few discretionary frames. Only a dual-model pass registers the segment as complete.
6. When every segment passes, the engine creates a continuity review covering narrative handoff, motion direction, subject identity, exposure/color, sound, typography and transition rhythm.
7. After continuity approval, segments may be assembled. The complete master then runs through the existing full-video review: Claude receives the systematic complete timeline and MiniMax receives the complete video with audio.
8. Failed final findings route back to the affected segment where possible. The master is rebuilt and reviewed again. The quality-first revision policy remains active: default eight cycles, with owner escalation after two cycles without measurable improvement, three repetitions of the same blocker, or the configured limit.
9. Only a final dual-model pass permits handoff to the publication-package executor. Publication itself always remains an owner gate.

The engine must never treat a segment pass as a final-master pass, and must never allow direct whole-video generation to bypass segmentation consensus.
