# Portal24 Python Client — Agent Instructions

## Mission
Build an unofficial, publishable, strictly read-only Python client for Immoware24 Portal24. Follow `docs/PROJECT_SPEC.md` as the authoritative requirements document.

## Working Practices
- Read `docs/PROJECT_SPEC.md` and `docs/IMPLEMENTATION_PLAN.md` before implementing.
- Maintain `docs/IMPLEMENTATION_PLAN.md` after each milestone and `docs/REVERSE_ENGINEERING.md` with verified findings only.
- Start with documented interfaces and authorized observation of ordinary browser requests. Never assume endpoints exist.
- Prefer Python 3.12+, type hints, httpx, pytest, and Playwright only when necessary.
- Make working changes and run tests; do not stop at a plan.
- Distinguish confirmed, inferred, and untested behaviors; never invent validation results.

## Read-Only Requirement
- Never approve or reject accounting transactions, send review comments, mutate documents, or modify server-side business data.
- Do not invoke potentially state-changing business endpoints, even for testing. Authentication, session refresh, and logout are permitted.
- Respect account permissions, rate limits, MFA, and service restrictions. Do not bypass controls.

## Privacy and Local Data
- Keep the Git repository separate from all sensitive runtime data.
- Preferred source directory: `~/projects/portal24-python/`.
- Preferred mirror directory: `~/data/portal24-mirror/`.
- Preferred configuration directory: `~/.config/portal24/`.
- Secrets in OS keyring or protected credential storage only. Do not ask users to paste passwords into chat or commit them.
- Never write authentic documents, accounting records, auth tokens, cookies, authenticated HAR files, or logs with private data inside the repository.
- Check Git history and staging for secrets and private data before publication.
- Require explicit confirmation before publishing a GitHub repository publicly.

## Scope
Implement a reusable Python library, CLI, incremental mirror, transaction exports where supported, and validation reports. No automated accounting approval or external publication without approval.
