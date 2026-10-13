# Security Policy

## Scope
This project is an **unofficial** client for Immoware24 Portal24. Security
reports are accepted for the client code itself (authentication handling,
credential/session storage, read-only enforcement, mirror integrity).

## Reporting a Vulnerability
Please report vulnerabilities by opening a **private** security advisory on
this repository (GitHub: Security → Reporting a vulnerability) or by
contacting the maintainers directly. Do not open public issues for
security problems.

## What We Consider Security Issues
- Credential or session-cookie leakage (logs, error messages, files, mirrors).
- Bypass or weakening of the read-only request policy.
- Path traversal or overwrite issues in the local mirror.
- Insecure storage of secrets (wrong file permissions, secrets in repo).

## What Is Out of Scope
- Vulnerabilities of the Portal24 service itself (report to Immoware24
  support instead).
- Issues caused by user misconfiguration (e.g. committing
  `config.local.yaml` to a different repository).

## Supported Versions
The latest release only. This project is in alpha.

## Local Data Guarantees
- Credentials are read from `config.local.yaml` (gitignored), environment
  variables, or the OS keyring — never written to disk by the library.
- Session cookies are stored in `~/.config/portal24/session.json` with
  `0600` permissions, outside any Git working tree.
- Mirrored documents go to a directory outside the repository
  (default `~/data/portal24-mirror`).
