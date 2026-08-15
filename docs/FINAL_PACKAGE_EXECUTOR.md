# Final Publication Package Executor

Engine 2.0 accepts only a complete master that has passed the technical gate and independent Claude plus MiniMax final review.

The prepare operation validates the archive ID, input files, review evidence, 1080x1920 resolution, 15–30 second duration, SDR BT.709 color, publishing copy and reviewed cover set. It performs no copy and no publication.

The build operation creates a hidden staging directory, writes separate Instagram Reels and YouTube Shorts deliverables, copies the canonical master and review evidence, records SHA-256 checksums, verifies them, and atomically renames the staging directory to `archive/SMmmddyyyyNN`. Existing archives are never overwritten. A failed build removes its staging directory.

Every completed manifest has `publishing_authorized: false`, `status: READY_NOT_PUBLISHED`, and `publication_gate: OWNER_APPROVAL_REQUIRED`. The executor has no upload or publish operation.

Commands:

```powershell
python engine_v2_0.py --root . final-package --spec <spec.json>
python engine_v2_0.py --root . final-package --spec <spec.json> --build
python engine_v2_0.py --root . verify-package --archive-id SM0811202601
```
