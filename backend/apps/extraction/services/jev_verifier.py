"""
Jev verification layer abstraction.

INTEGRATION STATUS: NOT IMPLEMENTED — Jev identity unconfirmed
─────────────────────────────────────────────────────────────
"Jev" was requested as a field-level verification layer for extracted invoice
candidates.  After thorough investigation the identity of Jev could not be
confirmed:

  • Not present anywhere in the project codebase.
  • Not available as a Python package: `pip install jev` → not found.
  • Not found as an npm package: the hits in package-lock.json are SHA-512
    hash strings that happen to contain the substring "jev", not a package
    declaration.
  • No official documentation, API endpoint, authentication mechanism,
    response format, or SDK could be located.

Per spec §5: AbstractVerifier + NullVerifier implemented; full infrastructure
is in place.  When Jev's identity and API are confirmed:
  1. Create JevVerifier(AbstractVerifier) in this module.
  2. Populate settings.JEV_ENABLED / JEV_API_KEY / JEV_ENDPOINT.
  3. Update get_verifier() to return JevVerifier when enabled.

See docs/jev-integration.md for the full decision record and integration guide.

Security contract for all verifier implementations:
  - Receive only extracted field values and evidence text (data already in
    the document).
  - Never receive API keys, user tokens, org data beyond the minimum needed,
    or full document bytes.
  - Handle errors gracefully: return ERROR status, never raise.
  - Never log credentials, full document content, or sensitive user data.
  - Advisory only: never change invoice state, policy decisions, or approval.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field as dc_field
from enum import Enum

from .ai_extractor import RawExtractionResult


class VerificationStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    CONFIRMED      = "confirmed"
    CONFLICT       = "conflict"
    ABSENT         = "absent"
    INCONCLUSIVE   = "inconclusive"
    ERROR          = "error"


class OverallVerificationStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    PASSED         = "passed"
    WARNINGS       = "warnings"
    FAILED         = "failed"
    PARTIAL        = "partial"


@dataclass
class FieldVerificationResult:
    status:            VerificationStatus
    confirmed_value:   str | None = None
    conflict_evidence: str | None = None
    note:              str | None = None


@dataclass
class VerificationResult:
    overall: OverallVerificationStatus
    message: str
    fields:  dict[str, FieldVerificationResult] = dc_field(default_factory=dict)


class AbstractVerifier(ABC):
    """Contract for any field-level verifier.

    Advisory only: verifiers never change invoice state, policy decisions,
    or approval outcomes.  Must handle all errors internally (return ERROR,
    never raise).
    """
    @abstractmethod
    def verify(self, result: RawExtractionResult) -> VerificationResult:
        """Verify extracted fields.  Never raises; always returns a result."""


class NullVerifier(AbstractVerifier):
    """Active when no verifier is configured (including Jev unconfirmed).

    Returns NOT_CONFIGURED for all fields.  The UI must clearly show that
    verification was not performed — it must NEVER present this as 'verified'.
    """

    def verify(self, result: RawExtractionResult) -> VerificationResult:
        return VerificationResult(
            overall=OverallVerificationStatus.NOT_CONFIGURED,
            message=(
                "Verification provider not configured. "
                "Jev identity is unconfirmed — see docs/jev-integration.md. "
                "Manual review of all extracted fields is required."
            ),
        )


def get_verifier() -> AbstractVerifier:
    """Return the active verifier.

    Currently always returns NullVerifier because Jev's identity is
    unconfirmed.  Update this factory once a verifier is available:

        if getattr(settings, "JEV_ENABLED", False):
            return JevVerifier(
                api_key=settings.JEV_API_KEY,
                endpoint=settings.JEV_ENDPOINT,
            )
    """
    return NullVerifier()
