# Social Media Harness

[![CI](https://github.com/tsunpp/social-media-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/tsunpp/social-media-harness/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Social Media Harness is a narrative-first, privacy-aware production workflow for authentic social-media videos, covers, captions, review evidence, platform packages, and immutable archives.

The current public release is software version **0.2.0** and contains the **Engine 2.6** workflow model. It separates reusable software from private campaigns and keeps publication owner-controlled.

Version 0.2.0 adds Direction Grill: a research-first, owner-confirmed creative-direction contract that must be aligned before new Campaigns enter Narrative-First planning. Direction confirmation is hash-bound, recoverable, and never grants production or publication authority.

Direction-enabled Campaigns require complete fact, privacy, manifest, and asset-catalog evidence; reject ambiguous owner answers; and use Engine-generated, hash-bound drift reports at narrative-option, shot-mapping, final-master, and publication-package checkpoints.

## What it provides

- exactly three evidence-testable story options before shot ranking;
- platform profiles for WeChat Channels, Instagram Reels, TikTok, and YouTube Shorts;
- scoped reviewer authorization for Claude, MiniMax, Kimi, and optional DeepSeek;
- deterministic FFmpeg-oriented production and technical validation;
- final-contract consistency, audio-authority, privacy, provenance, and archive gates;
- no automatic publication.

External reviewers and generation backends are optional adapters. Missing or unauthorized reviewers are recorded as inactive, never fabricated as passing.

## Install

```bash
git clone https://github.com/tsunpp/social-media-harness.git
cd social-media-harness
python -m pip install -e ".[dev]"
smh --help
```

Create a private workspace outside the repository and inspect the available capabilities:

```bash
mkdir ../smh-workspace
smh --root ../smh-workspace capabilities
```

Install FFmpeg separately and ensure it is on `PATH`, or set `SMH_FFMPEG` to its executable. External reviewer and generation adapters require their respective service credentials and may incur charges. Core validation, planning preparation, and capability inspection do not require paid API calls.

## Privacy boundary

Do not place real campaigns, source media, review uploads, credentials, publication accounts, or persistent owner memory in this repository. The `.gitignore` blocks the standard private directories, but users remain responsible for reviewing staged changes.

See [Public readiness](docs/PUBLIC_READINESS.md), [Architecture](docs/ARCHITECTURE.md), and [Security](SECURITY.md).

## Status

Alpha software. Interfaces, schemas, and adapter behavior may change before 1.0. It is not a hosted publishing service and never bypasses the owner publication gate. Contributions and reproducible bug reports are welcome.

## License

Apache License 2.0. Third-party services, models, fonts, music, images, and media remain subject to their own terms and licenses.
