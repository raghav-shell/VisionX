"""Exception hierarchy.

Two families matter for reporting: :class:`UnsafeInputError` means an input was *rejected by a
security boundary* (traversal, bomb, oversize); :class:`LoaderError` means an input was malformed.
Neither is ever reported as a capability being "unavailable".
"""

from __future__ import annotations


class VisionSentinelError(Exception):
    """Base class. ``hint`` is shown to operators alongside the message."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


class ConfigurationError(VisionSentinelError):
    pass


class ProfileError(ConfigurationError):
    pass


class LoaderError(VisionSentinelError):
    pass


class UnsafeInputError(VisionSentinelError):
    """An input was rejected by a security boundary."""


class ResourceLimitError(UnsafeInputError):
    """An input exceeded a configured resource budget."""


class CapabilityError(VisionSentinelError):
    """A detector asked for an asset or capability that negotiation did not grant."""


class IntegrityError(VisionSentinelError):
    pass


class EvidenceIntegrityError(IntegrityError):
    pass


class GovernanceError(VisionSentinelError):
    pass


class AuthorizationError(GovernanceError):
    pass


class SandboxError(VisionSentinelError):
    """The sandboxed model worker failed, was killed, or returned a malformed response."""
