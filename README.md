# portal24-python

An **unofficial**, strictly **read-only** Python client and CLI for
[Portal24](https://www.portal24.com/) by Immoware24.

> **Disclaimer:** This project is not affiliated with, endorsed by, or
> connected to Immoware24 GmbH. It only performs read operations
> (plus login/logout) using your own authorized account, and never
> approves, rejects, comments on, or otherwise modifies business data.

## Status
- **Implemented and verified against a live account (read-only, 2026-10-13):**
  configuration, credential handling, session persistence, read-only-enforced
  HTTP layer with retries and log redaction, the login/logout flow, typed
  discovery (objects, rent units, category tree, documents, tickets), full
  document mirroring with manifests, SHA-256 verification, incremental and
  idempotent re-sync, dry-run, and CSV/JSON exports.
- **Documented limitation:** this tenant portal provides no structured
  transaction feed; accounting data exists as PDF documents in the
  "Belegprüfung" category, which are mirrored and exported as clearly
  labeled client-generated metadata. See
  [docs/REVERSE_ENGINEERING.md](docs/REVERSE_ENGINEERING.md).
- See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for the
  live validation results (43/43 documents mirrored, hashes verified,
  second run idempotent).

## Why
Portal24 has no public API. This client reproduces the ordinary,
authorized browser requests of a logged-in user so that all accessible
documents and structured accounting data can be mirrored locally for
offline use and auditing.

## Installation
Requires Python 3.12+.

```sh
pip install -e .
```

## Configuration
Create `config.local.yaml` in the repository root (it is gitignored;
see [config.example.yaml](config.example.yaml)):

```yaml
base_url: https://portal.example-verwalter.de/
credentials:
  email: you@example.com
  password: secret
mirror:
  destination: ~/data/portal24-mirror
```

Credentials may also come from `PORTAL24_EMAIL` / `PORTAL24_PASSWORD`
environment variables or the OS keyring (service `portal24`). Session
cookies are stored in `~/.config/portal24/session.json` (mode `0600`),
never inside the repository.

## Usage

### CLI
```sh
portal24 login
portal24 status
portal24 properties
portal24 documents
portal24 transactions            # Belegprüfung voucher documents
portal24 sync --dry-run
portal24 sync --output ~/data/portal24-mirror
portal24 export-transactions --format csv --output ~/data/portal24-mirror/belegpruefung.csv
portal24 logout
```

### Python
```python
from portal24 import Portal24Client

with Portal24Client.from_local_credentials() as client:
    client.login()
    for prop in client.list_properties():
        print(prop.id, prop.name)
    result = client.sync()          # mirrors all accessible documents
    print(result.downloaded, result.failed)
```

## Privacy
- No credentials, cookies, documents, or account data ever belong in this
  repository.
- Mirrored content lives outside the source tree
  (default `~/data/portal24-mirror/`).
- The HTTP layer refuses any request that is not GET/HEAD or part of the
  authentication lifecycle.

## Development
```sh
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check src tests
```

## License
[MIT](LICENSE)
