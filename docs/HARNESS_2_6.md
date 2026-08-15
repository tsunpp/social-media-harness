# Social Media Harness 2.6

Harness 2.6 extends Engine 2.5 without rewriting the frozen Engine 2.3 predecessor or historical archives.

## Changes

1. Project-scoped authorization matrices persist recipient, material, identifiable-person and metadata rules. A standing authorization removes repeated confirmations only inside its recorded scope.
2. Platform profiles replace hard-coded Instagram/YouTube assumptions. The initial registry covers WeChat Channels, Instagram Reels, TikTok and YouTube Shorts.
3. New archives use immutable manifest schema v3 with a canonical master, complete hashed asset inventory, final story contract, review records, owner approval and an explicit publication gate.
4. The final contract consistency gate binds the final story contract, render manifest, master hash, sound strategy, publishing copy and platform before packaging.
5. Audio capabilities are modeled independently. Accepting video or audio bytes does not establish listening authority. The owner listening gate remains mandatory for BGM quality, mix balance and musical pacing unless a validated authority is registered.
6. Panel activation is privacy-adaptive. An unauthorized reviewer is recorded as inactive with a bounded reason and can never be represented as PASS.

## Entrypoint

```powershell
python engine_v2_6.py --root . capabilities
```

New commands:

- `authorization-resolve`
- `platform-validate`
- `contract-consistency`
- `audio-authority`
- `archive-manifest-validate`
- `final-package` and `verify-package` now use the 2.6 platform and archive contracts

Publication remains owner-only and is never performed by package construction.

