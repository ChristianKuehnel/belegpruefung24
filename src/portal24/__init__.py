"""portal24 — unofficial, strictly read-only Python client for Immoware24 Portal24.

This library is not affiliated with or endorsed by Immoware24 GmbH.
It only performs read operations (plus login/logout) and never
modifies server-side business data.
"""

from __future__ import annotations

from .client import Portal24Client
from .config import Portal24Config, load_config
from .credentials import Credentials, load_credentials
from .errors import (
    AuthenticationError,
    ConfigurationError,
    CredentialsError,
    NetworkError,
    ParseError,
    Portal24Error,
    ReadOnlyViolationError,
    SessionExpiredError,
    SyncError,
)
from .http import Portal24HTTP
from .models import (
    DmsCategory,
    Document,
    PaginationInfo,
    PaymentLine,
    Property,
    RentUnit,
    SyncResult,
    Ticket,
    Transaction,
)

__version__ = "0.1.0"

__all__ = [
    "AuthenticationError",
    "ConfigurationError",
    "Credentials",
    "CredentialsError",
    "DmsCategory",
    "Document",
    "NetworkError",
    "ParseError",
    "PaginationInfo",
    "PaymentLine",
    "Portal24Client",
    "Portal24Config",
    "Portal24Error",
    "Portal24HTTP",
    "Property",
    "ReadOnlyViolationError",
    "RentUnit",
    "SessionExpiredError",
    "SyncError",
    "SyncResult",
    "Ticket",
    "Transaction",
    "__version__",
    "load_config",
    "load_credentials",
]
