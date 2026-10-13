"""Command-line interface.

Exit codes:
    0  success
    1  runtime failure (network, server, sync)
    2  usage / configuration error
    3  authentication failure
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from .client import Portal24Client
from .errors import (
    AuthenticationError,
    ConfigurationError,
    CredentialsError,
    NetworkError,
    Portal24Error,
    ReadOnlyViolationError,
)

EXIT_OK = 0
EXIT_RUNTIME = 1
EXIT_USAGE = 2
EXIT_AUTH = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="portal24",
        description="Unofficial, strictly read-only client for Immoware24 Portal24.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", metavar="PATH", help="Path to config.local.yaml")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="Authenticate and store the session locally")
    sub.add_parser("logout", help="End the session and remove stored cookies")
    sub.add_parser("status", help="Show configuration and session state")

    p_props = sub.add_parser(
        "properties", help="List accessible properties/objects"
    )
    p_props.add_argument("--json", action="store_true", help="Machine-readable output")

    p_docs = sub.add_parser(
        "documents", help="List all accessible documents"
    )
    p_docs.add_argument("--json", action="store_true", help="Machine-readable output")

    p_txn = sub.add_parser(
        "transactions", help="List Belegprüfung (voucher review) documents"
    )
    p_txn.add_argument("--json", action="store_true", help="Machine-readable output")

    p_sync = sub.add_parser(
        "sync", help="Mirror all accessible documents and metadata"
    )
    p_sync.add_argument("--output", metavar="DIR", help="Mirror destination (default from config)")
    p_sync.add_argument("--dry-run", action="store_true", help="Report what would be downloaded")

    p_export = sub.add_parser(
        "export-transactions", help="Export Belegprüfung document records (CSV/JSON)"
    )
    p_export.add_argument("--format", choices=("csv", "json"), default="csv")
    p_export.add_argument("--output", metavar="FILE", required=True)

    return parser


def _make_client(args: argparse.Namespace) -> Portal24Client:
    return Portal24Client.from_local_credentials(args.config)


def _cmd_login(args: argparse.Namespace) -> int:
    client = _make_client(args)
    try:
        with client:
            final_path = client.login()
    except AuthenticationError as exc:
        print(f"login failed: {exc}", file=sys.stderr)
        return EXIT_AUTH
    print(f"Logged in successfully (landed on {final_path}).")
    print(f"Session stored at {client.config.session_file}")
    return EXIT_OK


def _cmd_logout(args: argparse.Namespace) -> int:
    client = _make_client(args)
    try:
        with client:
            client.logout()
    except Portal24Error as exc:
        print(f"logout failed: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    print("Logged out; local session cleared.")
    return EXIT_OK


def _cmd_status(args: argparse.Namespace) -> int:
    client = _make_client(args)
    try:
        with client:
            info = client.status()
    except Portal24Error as exc:
        print(f"status failed: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    print(json.dumps(info, indent=2, ensure_ascii=False))
    return EXIT_OK


def _cmd_properties(args: argparse.Namespace) -> int:
    client = _make_client(args)
    try:
        with client:
            properties = client.list_properties()
    except Portal24Error as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    if args.json:
        print(json.dumps([p.__dict__ for p in properties], indent=2, ensure_ascii=False))
    else:
        for prop in properties:
            address = f"  ({prop.address})" if prop.address else ""
            print(f"{prop.id}\t{prop.name}{address}")
    return EXIT_OK


def _cmd_documents(args: argparse.Namespace) -> int:
    client = _make_client(args)
    try:
        with client:
            documents = client.list_documents()
    except Portal24Error as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    if args.json:
        print(json.dumps([d.__dict__ for d in documents], indent=2, ensure_ascii=False))
    else:
        for doc in documents:
            size = f"{doc.size_label}" if doc.size_label else "?"
            cat = doc.category or "-"
            print(f"{doc.id}\t{size:>9}\t{doc.released or '':22}\t{cat:28}\t{doc.name}")
    return EXIT_OK


def _cmd_transactions(args: argparse.Namespace) -> int:
    client = _make_client(args)
    try:
        with client:
            categories = {c.name: c for c in client.list_categories()}
            review = categories.get("Belegprüfung")
            if review is None:
                print(
                    "No 'Belegprüfung' category found for this account; "
                    "no reviewable vouchers are available.",
                    file=sys.stderr,
                )
                return EXIT_OK
            documents = client.list_documents(review.id)
    except Portal24Error as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME

    if args.json:
        print(json.dumps([d.__dict__ for d in documents], indent=2, ensure_ascii=False))
    else:
        print(
            f"Note: this tenant portal provides no structured transaction feed. "
            f"Accounting data is available as PDF documents in category "
            f"'Belegprüfung' ({len(documents)} documents, server count "
            f"{review.count})."
        )
        for doc in documents:
            size = doc.size_label or "?"
            print(f"{doc.id}\t{size:>9}\t{doc.released or '':22}\t{doc.name}")
    return EXIT_OK


def _cmd_sync(args: argparse.Namespace) -> int:
    client = _make_client(args)
    try:
        with client:
            result = client.sync(destination=args.output, dry_run=args.dry_run)
    except Portal24Error as exc:
        print(f"sync failed: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    mode = "dry-run: would download" if args.dry_run else "downloaded"
    print(
        f"Sync {'complete' if result.complete else 'INCOMPLETE'}: "
        f"enumerated={result.enumerated} {mode}={result.downloaded} "
        f"skipped_unchanged={result.skipped_unchanged} failed={result.failed}"
    )
    for error in result.errors:
        print(f"  error: {error}", file=sys.stderr)
    if not args.dry_run:
        print(f"Mirror at: {result.destination}")
    return EXIT_OK if result.complete else EXIT_RUNTIME


def _cmd_export_transactions(args: argparse.Namespace) -> int:
    client = _make_client(args)
    try:
        with client:
            categories = {c.name: c for c in client.list_categories()}
            review = categories.get("Belegprüfung")
            if review is None:
                print("No 'Belegprüfung' category found; nothing to export.", file=sys.stderr)
                return EXIT_RUNTIME
            documents = client.list_documents(review.id)
    except Portal24Error as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME

    output = Path(args.output).expanduser()
    if args.format == "json":
        payload = {
            "provenance": "client-generated from the DMS document list "
            "(server-rendered HTML); not a native server export",
            "base_url": client.http.base_url,
            "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "documents": [d.__dict__ for d in documents],
        }
        output.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    else:
        import csv

        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                ["id", "name", "category", "size_bytes", "size_label", "released",
                 "downloaded", "status", "download_url", "provenance"]
            )
            for doc in documents:
                writer.writerow(
                    [
                        doc.id, doc.name, doc.category, doc.size, doc.size_label,
                        doc.released, doc.downloaded, doc.status,
                        f"{client.http.base_url}{doc.download_url}",
                        "client-generated from server-rendered HTML",
                    ]
                )
    print(f"Exported {len(documents)} document records to {output}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        if args.command == "login":
            return _cmd_login(args)
        if args.command == "logout":
            return _cmd_logout(args)
        if args.command == "status":
            return _cmd_status(args)
        if args.command == "properties":
            return _cmd_properties(args)
        if args.command == "documents":
            return _cmd_documents(args)
        if args.command == "transactions":
            return _cmd_transactions(args)
        if args.command == "sync":
            return _cmd_sync(args)
        if args.command == "export-transactions":
            return _cmd_export_transactions(args)
        return EXIT_USAGE
    except (ConfigurationError, CredentialsError) as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except ReadOnlyViolationError as exc:
        print(f"blocked by read-only policy: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except NetworkError as exc:
        print(f"network error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    except Portal24Error as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
