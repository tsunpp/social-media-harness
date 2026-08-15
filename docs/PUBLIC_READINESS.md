# Public readiness and extraction record

## Decision

The private production workspace must not be published or converted in place. This repository is a clean extraction containing reusable code, generic configuration, schemas, policies, templates, tests, documentation, and the reusable Skill only.

## Excluded from the public repository

- campaigns, source media, rendered media, archives, review payloads, and persistent memory;
- family names, private project identifiers, local drive paths, and machine-specific tool paths;
- API keys, account registries, cookies, tokens, and authorization decisions tied to real people;
- third-party restaurant imagery, music, fonts, or other assets without redistribution rights;
- bytecode, caches, logs, and historical private Git data.

## Enforced public release controls

- project-specific tracked-file scan for forbidden directories, private identifiers, personal paths, credential shapes, and private keys;
- Gitleaks scan over Git history;
- Python 3.11, 3.12, and 3.13 test matrix;
- wheel and source-distribution build with package metadata validation;
- clean wheel installation and CLI smoke test in a fresh virtual environment;
- GitHub Actions on pushes and pull requests.

## Owner-controlled release controls

- review the complete staged diff and public-safety output;
- require successful CI before merging the release commit;
- create an annotated version tag from the verified default branch;
- publish GitHub releases without private campaign artifacts.

Automated scanning reduces risk but does not establish publication rights. A human must still review business context, identities, media provenance, and third-party licenses.

## Case studies

Real family and client campaigns are intentionally absent. Examples must be synthetic, public-domain, or independently licensed and must not reproduce private review evidence.

## Verification

Run `python -m pytest`, `python scripts/public_safety_check.py`, and `python -m build` before proposing a public release. CI independently repeats these checks and installs the resulting wheel in a clean environment.