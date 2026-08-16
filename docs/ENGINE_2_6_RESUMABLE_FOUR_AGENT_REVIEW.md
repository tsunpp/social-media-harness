# Engine 2.6 resumable four-agent review

Prepare without external calls:

```powershell
python engine_v2_6.py --root . four-agent-review --spec campaigns/<campaign>/review-spec.json
```

Run or resume the authorized panel:

```powershell
python engine_v2_6.py --root . four-agent-review --spec campaigns/<campaign>/review-spec.json --run-apis
```

The spec identifies the project, Campaign, master, render manifest, brief, fact and privacy contracts, effective story contract, copy, source manifest, ordered complete visual timeline, review directory, and FFmpeg path.

The command:

1. resolves the persistent authorization matrix for Claude, MiniMax, and Kimi;
2. creates a minimal external authorization attestation without exporting internal decision files;
3. hashes every required evidence item into a stable evidence fingerprint;
4. creates a complete-duration MiniMax proxy only when the master exceeds the provider limit;
5. persists raw and normalized responses independently after each reviewer;
6. resumes only missing, failed, stale-master, or stale-evidence reviewers;
7. creates a panel bound to the master hash, evidence fingerprint, normalized review files, and review hashes.

Scoped recovery:

```powershell
python engine_v2_6.py --root . recover --project <project> --campaign <campaign>
```

Recovery supports both historical reference chains and newer self-contained Campaign state snapshots.

