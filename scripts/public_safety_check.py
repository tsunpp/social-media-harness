from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PREFIXES = (
    "campaigns/",
    "archive/",
    "asset_library/",
    "memory/",
    "audits/",
    "logs/",
    ".runtime/",
)
TEXT_SUFFIXES = {
    ".bat", ".cfg", ".csv", ".env", ".example", ".ini", ".json", ".md",
    ".ps1", ".py", ".sh", ".toml", ".txt", ".xml", ".yaml", ".yml",
}
TEXT_FILENAMES = {"Dockerfile", "Makefile"}
PRIVATE_IDENTIFIERS = (
    "beijing" + " party",
    "cannabis" + "-social-media",
    "dad" + "ong",
    "diamond" + "-documentary",
    "mother" + " liquor",
    "mother" + "_liquor",
    "ocean" + "deeplab",
    "vape" + "-liquid",
)
PATTERNS = {
    "personal_path": re.compile(
        r"(?:[A-Za-z]:" + r"\\Users\\|/" + r"Users/|/" + r"home/[^/\s]+/|G:"
        + r"\\My Drive|[A-Za-z]:" + r"\\[^\r\n]*\\(?:Google Drive|OneDrive)\\)",
        re.I,
    ),
    "service_token": re.compile(
        r"(?:sk" + r"-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}"
        + r"|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})",
        re.I,
    ),
    "bearer_token": re.compile(r"Bearer" + r"\s+[A-Za-z0-9._-]{12,}", re.I),
    "private_key": re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?" + r"PRIVATE KEY", re.I),
    "credential_assignment": re.compile(
        r"(?:api[_-]?key|access[_-]?token|secret[_-]?key|password)"
        + r"\s*[:=]\s*['\"][^'\"\r\n]{8,}['\"]",
        re.I,
    ),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return [ROOT / line for line in result.stdout.splitlines() if line.strip()]


def scan_text(relative: str, text: str) -> list[str]:
    problems: list[str] = []
    lowered = text.lower()
    for identifier in PRIVATE_IDENTIFIERS:
        if identifier.lower() in lowered:
            problems.append(f"private_identifier: {relative}")
            break
    for name, pattern in PATTERNS.items():
        if pattern.search(text):
            problems.append(f"{name}: {relative}")
    return problems


def scan_path(path: Path) -> list[str]:
    relative = path.relative_to(ROOT).as_posix()
    problems: list[str] = []
    if relative.startswith(FORBIDDEN_PREFIXES):
        problems.append(f"forbidden tracked path: {relative}")
    if not path.is_file():
        return problems
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TEXT_FILENAMES:
        return problems
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    problems.extend(scan_text(relative, text))
    return problems


def main() -> int:
    problems = [problem for path in tracked_files() for problem in scan_path(path)]
    if problems:
        print("Public safety check failed:")
        for problem in sorted(set(problems)):
            print(f"- {problem}")
        return 1
    print("Public safety check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())