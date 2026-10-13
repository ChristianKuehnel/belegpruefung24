# Implementation Plan

> Agent-maintained execution plan. Update statuses and concrete next steps after each milestone. Do not record credentials or private data here.

## Status
- Current phase: Phase 6 (Validation) complete — live mirror verified, idempotent second run confirmed
- Live authentication: Done (2026-10-13)
- Live validation: **RUN** (2026-10-13) — see "Live validation results" below
- Known blockers: None. Remaining gaps are documented limitations (no structured transaction feed exists; POM meetings are client-rendered).

## Checklist
- [x] Research Portal24 integrations and existing public clients.
- [x] Document confirmed login flow and safe, read-only endpoints.
- [x] Implement credentials/session management outside Git. (config.local.yaml, gitignored; session.json in ~/.config/portal24, 0600)
- [x] Implement read-only HTTP layer (policy guard, retries, redaction) + login/logout/status CLI.
- [x] Implement typed resource discovery (objects, rent units, categories, documents, tickets).
- [x] Download and verify authorized documents (43/43 live, SHA-256 verified).
- [x] Discover structured transaction feeds: **none exist** — accounting data is PDF documents in the "Belegprüfung" category (documented, not invented).
- [x] Implement full recursive hierarchy traversal (category tree incl. nesting, pagination).
- [x] Implement manifests and incremental/resumable local mirroring (dedup, dry-run, git-tree rejection).
- [x] Synthetic test suite: 71 tests passing, ruff clean; GitHub Actions CI in place.
- [x] Execute opt-in read-only live full sync.
- [x] Validate counts, failures, file hashes, and second-run idempotency.
- [x] Review source and Git history for sensitive data (none found; config.local.yaml gitignored).
- [ ] Prepare documentation, license, and publication-ready Git commits (docs + LICENSE + SECURITY.md + CI done; commit on user request).
- [ ] Obtain explicit user approval before any public GitHub publication.

## Live validation results (2026-10-13, real account, read-only)
- Login: OK (landed on `/portal/object/show`); session persisted to `~/.config/portal24/session.json`.
- Enumeration: 1 object, 1 rent unit, 15 top-level categories (20 incl. children), 43 documents (server total = 43, enumerated = 43), 1 ticket, 3 forms.
- Full sync to `~/data/portal24-mirror`: **43/43 downloaded, 0 failed, 97 MB**, all 43 SHA-256 hashes verified against manifest.
- Duplicates: 4 documents appear in both a parent and child category list (server behavior); stored once, logical references recorded in manifest.
- Second sync: **0 downloaded, 43 skipped-unchanged** (idempotent, no re-download).
- Exports: `documents.json`, `account.json`, `belegpruefung.csv` (24 Belegprüfung records, client-generated, provenance labeled).
- `sync-report.json` written; `complete: true`.
- State-changing endpoints were identified and blocked; one early discovery crawl followed `switch-*` GET links (session context change only) — documented in REVERSE_ENGINEERING.md; shipped client never calls them.

## Next Action
1. User review of the mirror and this report.
2. Optional: mirror ticket attachments (`/communicator/ticket/download-attachment/{t}/{a}`) and notifications if desired.
3. On user request: create publication-ready Git commits (after final secret scan).
4. Public GitHub publication only with explicit user approval.

## Decisions / Blockers
- 2026-10-13: No public API exists; client reproduces authorized browser behavior (server-rendered PHP + jQuery). Endpoints are discovered per page.
- 2026-10-13: Per user instruction, local config (base URL + credentials) lives in repo-root `config.local.yaml` (gitignored). Session cookies persist to `~/.config/portal24/session.json` (0600), never in the repo.
- 2026-10-13: Minimal-dependency stack: `httpx`, `PyYAML`; stdlib `argparse` + `dataclasses`; `keyring` optional/lazy. Python 3.12+.
- 2026-10-13: Read-only enforced in the HTTP layer: only GET/HEAD plus an explicit auth allowlist (login/logout); all other methods/paths rejected client-side.
- 2026-10-13: No structured transaction feed exists in this tenant portal; the client exports Belegprüfung document records (clearly labeled client-generated) and mirrors the PDFs. No invented data.
- 2026-10-13: Mirror hierarchy follows the server: data-source → category tree → document (documents have no per-object id server-side). Objects/rent-units are mirrored as metadata.
- 2026-10-13: `/dms/document/show/{id}` marks documents read → the client downloads via `/dms/document/download/{id}` only and never opens show pages during sync.
