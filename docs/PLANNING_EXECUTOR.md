# Planning review executor

## Active interface

Engine API 1.4, entrypoint `engine_v1_4.py`.

## Commands

Prepare the complete campaign context for Codex planning:

```powershell
python engine_v1_4.py plan-prepare --project cannabis-social-media --campaign diamond-documentary
```

Prepare and validate a three-option plan without paid API calls:

```powershell
python engine_v1_4.py plan-review --project cannabis-social-media --campaign diamond-documentary --plan campaigns/diamond-documentary/plans/plan_options_mother_liquor_v2.json
```

Run the paid Claude and MiniMax planning review only after authorization:

```powershell
python engine_v1_4.py plan-review --project cannabis-social-media --campaign diamond-documentary --plan campaigns/diamond-documentary/plans/plan_options_mother_liquor_v2.json --run-apis
```

## Evidence contract

- Codex receives the complete brief, project configuration, project decisions, latest active decisions, every asset catalog entry, all thumbnails, systematic keyframes and proxy inventory.
- Claude receives all planning text, every asset thumbnail and every systematic keyframe.
- MiniMax receives the same text and image evidence plus every available video proxy for motion and pacing context.
- Both reviewers assess all three plan options. They may recommend A, B, C or a combination, but cannot bypass the owner direction gate.

## Fact preflight

Active owner-confirmed fact rules run before any external API call. Superseded wording returns `FACT_CONFLICT`, records zero API calls and tells Codex to correct facts without changing creative direction.

The historical Diamond plan remains unchanged. The current review candidate is `plan_options_mother_liquor_v2.json`, with six factual wording changes recorded separately.

