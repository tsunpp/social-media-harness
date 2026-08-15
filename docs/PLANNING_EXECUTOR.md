# Planning review executor

## Active interface

Engine API 1.4, entrypoint `engine_v1_4.py`.

## Commands

Prepare the complete campaign context for Codex planning:

```powershell
python engine_v1_4.py plan-prepare --project synthetic-social-project --campaign sample-documentary
```

Prepare and validate a three-option plan without paid API calls:

```powershell
python engine_v1_4.py plan-review --project synthetic-social-project --campaign sample-documentary --plan campaigns/sample-documentary/plans/plan_options_process_liquid_v2.json
```

Run the paid Claude and MiniMax planning review only after authorization:

```powershell
python engine_v1_4.py plan-review --project synthetic-social-project --campaign sample-documentary --plan campaigns/sample-documentary/plans/plan_options_process_liquid_v2.json --run-apis
```

## Evidence contract

- Codex receives the complete brief, project configuration, project decisions, latest active decisions, every asset catalog entry, all thumbnails, systematic keyframes and proxy inventory.
- Claude receives all planning text, every asset thumbnail and every systematic keyframe.
- MiniMax receives the same text and image evidence plus every available video proxy for motion and pacing context.
- Both reviewers assess all three plan options. They may recommend A, B, C or a combination, but cannot bypass the owner direction gate.

## Fact preflight

Active owner-confirmed fact rules run before any external API call. Superseded wording returns `FACT_CONFLICT`, records zero API calls and tells Codex to correct facts without changing creative direction.

Historical plans remain immutable. The current synthetic review candidate is `plan_options_process_liquid_v2.json`, with six factual wording changes recorded separately.

