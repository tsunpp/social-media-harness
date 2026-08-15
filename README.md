# Social Media Harness

Social Media Harness is a narrative-first, privacy-aware production workflow for authentic social-media videos, covers, captions, review evidence, platform packages, and immutable archives.

This first public release is software version **0.1.0** and contains the **Engine 2.6** workflow model. It separates reusable software from private campaigns and keeps publication owner-controlled.

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

Install FFmpeg separately and ensure it is on `PATH`, or set `SMH_FFMPEG` to its executable. Set `SMH_WORKSPACE` to a private working directory outside this repository.

## Privacy boundary

Do not place real campaigns, source media, review uploads, credentials, publication accounts, or persistent owner memory in this repository. The `.gitignore` blocks the standard private directories, but users remain responsible for reviewing staged changes.

See [Public readiness](docs/PUBLIC_READINESS.md), [Architecture](docs/ARCHITECTURE.md), and [Security](SECURITY.md).

## Status

Alpha software. Interfaces and schemas may change before 1.0. Contributions and reproducible bug reports are welcome.

## License

Apache License 2.0. Third-party services, models, fonts, music, images, and media remain subject to their own terms and licenses.
