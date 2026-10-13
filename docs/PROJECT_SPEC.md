# Portal24 Python Client — Project Specification

## 1. Goal and Deliverable
Create a production-oriented, open-source Python 3.12+ library and command-line tool for **Portal24 by Immoware24** (https://www.portal24.com/). Investigate the actual service interfaces, and use the authenticated user's existing permissions to retrieve all accessible documents and, wherever present, structured accounting/transaction data. Produce a thoroughly tested, documented Git repository named provisionally `portal24-python`. This is an **unofficial** client, not endorsed by Immoware24.

Do not stop at a research report or proof of concept. Implement functioning features, run live read-only validation when authenticated access is available, document limitations honestly, and prepare the repository for publication. Public GitHub publication requires explicit user approval.

## 2. Reconnaissance and Reverse Engineering
1. Search for official documentation, APIs, OpenAPI/Swagger descriptions, public clients, and integration guidance.
2. Determine actual hostnames and login flow, application architecture, and session mechanism.
3. Observe *normal authorized* browser traffic, focusing on Fetch/XHR responses for property lists, document repositories, the **Online-Belegprüfung**, accounting views, and individual document downloads.
4. Investigate REST, GraphQL, JSON and export mechanisms, pagination, lazy loading, CSRF and session expiry. Read publicly delivered JavaScript code only as necessary to understand authorized interfaces.
5. Document verified HTTP methods, paths, parameters, response schemas, account-specific IDs, and caveats in `docs/REVERSE_ENGINEERING.md`. Redact identifiers, tokens, cookies, and personal data; use synthetic examples.
6. Prefer stable, server-provided structured APIs over HTML scraping. Prefer `httpx` direct requests; use Playwright only for login, discovery, or operations that cannot reliably use HTTP directly.

No bypass of MFA, CAPTCHAs, access controls, rate limits or other technical protections. Never probe other users' objects or unauthorized accounts. Respect applicable service terms. If an integration is blocked, stop that method and document the blocker.

## 3. Authentication and Secret Handling
- Provide local interactive setup, such as `portal24 login` or a supported browser-mediated login.
- Prefer an OS keyring for passwords and session secrets. A protected local credential store with restrictive file permissions may be supported as an explicit fallback; environment variables are also acceptable.
- Keep ordinary non-secret configuration under `~/.config/portal24/`; never inside the source tree.
- Session persistence and refresh should be reliable, and interactive MFA supported where applicable, without bypassing it.
- Implement clear authentication/session expiry errors and safe logging. Redact passwords, cookies, bearer tokens, authorization headers, user identifiers, and signed URLs.
- Never include real credentials in fixtures, example files, CI or Git history.

## 4. Accessible Resource Discovery
Enumerate all resources available to the authenticated user, where the portal provides them:
- Properties, buildings, and owners' associations (WEGs).
- Document categories, folders, nested folders, files, and associated metadata.
- Accounting periods and annual statements.
- Online-Belegprüfung: transaction/bookings lists grouped by account, individual bookings, linked receipts/invoices, and review metadata (read only).
- Other accessible documents and financial records relevant to local mirroring.

Handle multiple properties, all categories, server pagination, nested folders, lazy loading, and different document endpoints. Preserve stable server identifiers and original parent-child relationships where available.

## 5. Structured Accounting and Transaction Data
Actively check for machine-readable records and exports (server JSON, CSV, XLSX, or similar), including ledger entries, booking dates, descriptions, amounts, counterparties, invoice numbers, account identifiers, fiscal periods, and transaction-to-document relationships. Prefer unmodified server-provided records. Preserve raw JSON including unknown fields; additionally provide a normalized, typed Python model and client-generated JSON/CSV exports with clearly documented provenance. Do not pretend that HTML-derived exports were native server exports. Do not invent missing fields or relationships.

## 6. Python Package and CLI
Prefer minimal dependencies (`httpx`, `pydantic` or dataclasses, `typer`/`argparse`, optional `playwright`, `keyring`) and Python 3.12+. Separate authentication, API communication, models, documents, accounting, synchronization, and command-line logic. Use typed models and context-managed clients where appropriate.

Design a discoverable library API, e.g.:

```python
from portal24 import Portal24Client

with Portal24Client.from_local_credentials() as client:
    properties = client.list_properties()
    for prop in properties:
        print(prop.id, prop.name)
    client.sync(destination="~/data/portal24-mirror")
```

The precise API must reflect **confirmed** server functionality rather than assumed capabilities.

Offer CLI commands where supported, such as:

```sh
portal24 login
portal24 status
portal24 properties
portal24 documents
portal24 transactions
portal24 sync --output ~/data/portal24-mirror
portal24 sync --dry-run
portal24 export-transactions --format csv
```

Provide helpful exit codes, progress and failure reporting, filters (property/period/category where supported), and structured machine-readable output as an option.

## 7. Faithful Local Mirror
The primary deliverable is an organized **local mirror of every file that the authenticated account may access**. Discover the site's logical hierarchy first, and reproduce it as closely as server metadata allows: property/WEG → category → folder/subfolder → document. Do not impose invented folder hierarchies when the server exposes a different one.

Example *only*:

```text
~/data/portal24-mirror/
├── properties/
│   └── property-123_building-name/
│       ├── documents/
│       │   └── server-derived-subfolders/
│       ├── accounting/
│       │   └── 2025/
│       │       ├── transactions.json
│       │       ├── transactions.csv
│       │       └── supporting-documents/
│       └── metadata.json
├── manifests/
│   ├── files.json
│   └── synchronization.json
└── sync-report.json
```

Requirements:
- Traverse all accessible properties, folders, document categories, and accounting periods; handle pagination and lazy loading.
- Download the original binary bytes via streaming; preserve original names/extensions in metadata and safely sanitized filenames on disk.
- Prevent path traversal, case-folding conflicts, accidental overwrites, and duplicate filename collisions by using stable IDs.
- Preserve source URL/identifier and server-provided metadata safely without persisting short-lived signed URLs or secrets where unnecessary.
- Maintain manifest(s) mapping server resources to local paths; record size, local SHA-256, timestamps, download state, and all logical references.
- Retry transient network failures with bounded exponential backoff; honor rate limits; avoid aggressive concurrency.
- Allow safe incremental synchronization and resuming after interruptions; avoid re-downloading unchanged items when reliably detectable.
- Don't delete local files when remote entries disappear unless a distinct, explicitly enabled deletion policy is implemented. Default is nondestructive.
- If identical documents appear in multiple folders, preserve multiple logical references and deduplicate storage safely when possible.
- Provide `--dry-run`; never claim a complete mirror if enumeration or downloads fail.

## 8. Strictly Read-Only Operation (Non-Negotiable)
This library must never intentionally modify Portal24 business data, metadata, accounting state, permissions, or review state. In particular **do not approve, reject, comment on, create, edit, or delete transactions or documents**. Do not experiment with potentially state-changing endpoints. HTTP GET is not necessarily safe merely because its method is GET: understand side effects before invoking endpoints. Authentication, token renewal, and logout are permitted as required for read-only access. Do not expose write operations in the public Python API or CLI.

## 9. Strict Physical Separation of Code and Private Data (Non-Negotiable)
The repository must not contain genuine documents, ledger data, API payloads, browser profiles, auth traffic captures, credentials, session cookies, or runtime logs—not even temporarily.

Use separate directory trees:

```text
~/projects/portal24-python/   # publishable source only
~/data/portal24-mirror/       # actual private downloaded content and manifests
~/.config/portal24/          # local non-secret configuration
OS keyring/protected store   # secrets and session credentials
```

Reject destinations inside a Git working tree by default, especially this project's working tree. Use synthetic fixtures only for tests. `.gitignore` is an extra precaution, not the privacy boundary. Validate real data and logs reside outside the repository.

## 10. Live Read-Only Validation (Mandatory When Access Is Available)
With user-provided authorized access:
1. Log in successfully.
2. Enumerate all accessible properties, organizational structures, document repositories, accounting periods, and available transaction lists.
3. Download **all currently accessible documents** into the external mirror folder, preserving hierarchy and metadata.
4. Export structured transactions where available and preserve connections to supporting files.
5. Compare server-reported totals with enumerated items, downloads, failures, and duplicates where such counts exist.
6. Compute local file hashes, inspect downloads for truncation where possible, and produce machine-readable `sync-report.json`.
7. Run synchronization a second time, confirming idempotency, no unnecessary duplication, and correct manifests.
8. Explicitly report failed or unreachable categories and uncertainty in completeness.

Never fabricate successful live tests, document totals, endpoint discovery, or download results. If no browser/network access or login is available, implement what can be verified locally and clearly mark live validation **NOT RUN** with reproducible instructions. Obtain only essential user intervention for secure authentication/MFA and publication approval.

## 11. Test Strategy
Use `pytest` and synthetic fixtures for unit and CI tests. Cover configuration and credential handling, API parsing, pagination, errors, filename sanitization, path security, retry logic, duplicate handling, hierarchy mapping, resumption, incremental sync, and data export provenance. Keep real-account integration tests opt-in and outside ordinary CI. Execute tests after meaningful changes, and report actual results.

## 12. Documentation and Open Source Delivery
Prepare a clean repository with `pyproject.toml`, `src/portal24/`, `tests/`, `examples/`, `docs/`, `README.md`, `LICENSE` (MIT preferred), `SECURITY.md`, `.gitignore`, and GitHub Actions CI. Documentation in English. Describe authentication, commands, Python usage, discovered interfaces, reverse-engineering findings without leaking private information, security, limitations, and troubleshooting. Use an explicit unofficial/non-affiliated disclaimer.

Review the Git working tree, staging area, and entire commit history for secrets and private documents; run secret scanning when available. Check examples and traces for privacy. Never push or make the project public without explicit authorization. Leave a ready-to-publish Git repository if publication approval or tooling is unavailable.

## 13. Work Phases
1. **Research:** Find public technical information and any existing libraries.
2. **Discovery:** Inspect authorized browser interactions; document verified API and authentication behavior.
3. **Minimal client:** Log in, list resources, download one permitted file, and confirm real functionality.
4. **Full discovery:** Implement coverage of all folders and available transactions.
5. **Mirror:** Implement safe full and incremental synchronization with manifests.
6. **Validation:** Mirror all accessible documents, export accounting data, verify counts and repeat sync.
7. **Release:** Finish tests, documentation, security review, and ready-to-publish repository.

Keep `docs/IMPLEMENTATION_PLAN.md` current throughout. Log architectural decisions, evidence, verified behavior and blockers in `docs/REVERSE_ENGINEERING.md` with no sensitive data.

## 14. Completion Report
Report source repository location, authentication approach, **verified** endpoints/capabilities, available transaction formats, local mirror design, number of properties and documents enumerated, downloaded file count, size, errors, duplicate counts, test outcomes, idempotent-sync results, known restrictions, publication status, and exact rerun commands. Distinguish observed measurements from estimates. If some resources cannot be accessed, report the limitation rather than asserting full completeness.

## 15. Final Principle
**Discover first. Implement second. Verify third. Publish only with approval.**

The separate downstream AI accounting-audit application is **out of scope** for this project. Design stable, documented exports and transaction-to-document mappings so that a future audit tool can consume the mirrored files and records without reverse-engineering Portal24 again.
