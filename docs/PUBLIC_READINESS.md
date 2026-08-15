# Public readiness and extraction record

## Decision

The private production workspace must not be published or converted in place. This repository is a clean extraction containing reusable code, generic configuration, schemas, policies, templates, tests, documentation, and the reusable Skill only.

## Excluded from the public repository

- campaigns, source media, rendered media, archives, review payloads, and persistent memory;
- family names, private project identifiers, local drive paths, and machine-specific tool paths;
- API keys, account registries, cookies, tokens, and authorization decisions tied to real people;
- third-party restaurant imagery, music, fonts, or other assets without redistribution rights;
- bytecode, caches, logs, and historical private Git data.

## Public release controls

- secrets scan over tracked files;
- absolute-path and private-identifier scan;
- Python test suite;
- package build and clean-install smoke test;
- GitHub Actions on pushes and pull requests;
- owner-controlled GitHub publication and releases.

## Case studies

Real family and client campaigns are intentionally absent. Examples must be synthetic, public-domain, or independently licensed and must not reproduce private review evidence.
