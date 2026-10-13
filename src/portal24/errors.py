"""Exception hierarchy for the Portal24 client."""

from __future__ import annotations


class Portal24Error(Exception):
    """Base class for all Portal24 client errors."""


class ConfigurationError(Portal24Error):
    """Missing or invalid local configuration."""


class CredentialsError(Portal24Error):
    """Missing or unusable credentials."""


class AuthenticationError(Portal24Error):
    """The server rejected the credentials or the login flow failed."""


class SessionExpiredError(AuthenticationError):
    """A previously valid session is no longer accepted by the server."""


class ReadOnlyViolationError(Portal24Error):
    """A request was blocked because it could modify server-side state."""


class NetworkError(Portal24Error):
    """A transient or persistent network-level failure."""


class ParseError(Portal24Error):
    """A server response could not be parsed as expected."""


class SyncError(Portal24Error):
    """A mirror/synchronization operation failed."""
