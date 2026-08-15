from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PREFIXES = ("campaigns/", "archive/", "asset_library/", "memory/", "audits/", "logs/")
TEXT_SUFFIXES = {".py", ".json", ".yaml", ".yml", ".md", ".toml", ".txt", ".example"}
PATTERNS = {
    "personal_path": re.compile(
        r"(?:[A-Za-z]:" + r"\\Users\\|/" + r"Users/|G:" + r"\\My Drive|C:" + r"\\AI\\" + r")",
        re.I,
    ),
    "private_identifier": re.compile(
        r"(?:beijing" + r" party|ocean" + r"deeplab|gmail" + r"\.com" + r")", re.I
    ),
    "token_shape": re.compile(
        r"(?:sk-" + r"[A-Za-z0-9_-]{12,}|Bearer" + r"\s+[A-Za-z0-9._-]{12,}" + r")", re.I
    ),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return [ROOT / line for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    problems: list[str] = []
    for path in tracked_files():
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith(FORBIDDEN_PREFIXES):
            problems.append(f"forbidden tracked path: {relative}")
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for name, pattern in PATTERNS.items():
            if pattern.search(text):
                problems.append(f"{name}: {relative}")
    if problems:
        print("Public safety check failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("Public safety check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
