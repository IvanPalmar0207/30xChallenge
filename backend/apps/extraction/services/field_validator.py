"""
Deterministic validation for extracted invoice fields.

Sits between raw AI output and data accepted by the invoice system.
AI responses cannot be trusted for type correctness or consistency;
this module is the gatekeeper before any value reaches the invoice domain.

Confidence labels (descriptive only — NOT a financial guarantee):
  'medium' — field has a value AND supporting evidence text
  'low'    — field has a value but NO evidence (potentially hallucinated)
  'absent' — field is null (not found in the document)
  'high' is intentionally absent: AI extraction cannot guarantee accuracy.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from datetime import date
from decimal import Decimal, InvalidOperation

from .ai_extractor import EXTRACTABLE_FIELDS, RawExtractionResult, RawFieldResult


@dataclass
class ValidatedField:
    value:             str | None
    evidence:          str | None
    confidence:        str                    # 'medium' | 'low' | 'absent'
    validation_errors: list[str] = dc_field(default_factory=list)


@dataclass
class ValidationResult:
    fields:             dict[str, ValidatedField]
    cross_field_errors: list[str] = dc_field(default_factory=list)


def validate_fields(raw: RawExtractionResult) -> ValidationResult:
    """Apply deterministic rules to every extracted field."""
    fields: dict[str, ValidatedField] = {}
    for name in EXTRACTABLE_FIELDS:
        raw_f = raw.fields.get(name, RawFieldResult(None, None))
        fields[name] = _validate_field(name, raw_f)
    return ValidationResult(
        fields=fields,
        cross_field_errors=_cross_validate(fields),
    )


# ── Per-field rules ───────────────────────────────────────────────────────────

def _validate_field(name: str, raw: RawFieldResult) -> ValidatedField:
    if raw.value is None:
        return ValidatedField(value=None, evidence=None, confidence="absent")

    value  = raw.value
    errors: list[str] = []

    if name in ("issue_date", "due_date"):
        value, errors = _validate_date(value, name)
    elif name == "amount":
        value, errors = _validate_amount(value)
    elif name == "currency":
        value, errors = _validate_currency(value)
    elif name == "invoice_number":
        value, errors = _validate_invoice_number(value)
    elif name == "vendor_name":
        value = (value.strip() or None)
        if value:
            value = value[:200]
        else:
            errors = ["vendor_name cannot be blank."]
    elif name == "vendor_tax_id":
        value = (value.strip().upper() or None)
        if value:
            value = value[:50]
        else:
            errors = ["vendor_tax_id cannot be blank when provided."]
    elif name == "description":
        value = value.strip()[:500]   # blank is acceptable

    confidence = _confidence(value, raw.evidence)
    return ValidatedField(
        value=value,
        evidence=raw.evidence,
        confidence=confidence,
        validation_errors=errors,
    )


# ── Cross-field rules ─────────────────────────────────────────────────────────

def _cross_validate(fields: dict[str, ValidatedField]) -> list[str]:
    errors: list[str] = []
    issue = fields.get("issue_date")
    due   = fields.get("due_date")
    if (
        issue and due
        and issue.value and due.value
        and not issue.validation_errors
        and not due.validation_errors
    ):
        try:
            if date.fromisoformat(issue.value) > date.fromisoformat(due.value):
                errors.append(
                    f"issue_date ({issue.value}) is after due_date ({due.value})."
                )
        except ValueError:
            pass   # already flagged per-field
    return errors


# ── Field-specific validators ─────────────────────────────────────────────────

def _validate_date(value: str, field_name: str) -> tuple[str | None, list[str]]:
    v = value.strip()
    try:
        return date.fromisoformat(v).isoformat(), []
    except ValueError:
        return None, [
            f"{field_name}: '{v}' is not a valid date. Expected YYYY-MM-DD."
        ]


def _validate_amount(value: str) -> tuple[str | None, list[str]]:
    v = value.strip()
    cleaned = re.sub(r"[,$€£¥₹\s]", "", v)
    # Accept European decimal comma (e.g. "1.500,00" or "1500,00")
    if re.match(r"^\d[\d.]*,\d{1,2}$", cleaned):
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return None, [
            f"amount: '{v}' is not a valid decimal number. "
            "Expected a numeric value (e.g. '1500.00')."
        ]
    if amount <= 0:
        return None, [f"amount: must be greater than zero (got {amount})."]
    return str(amount.quantize(Decimal("0.01"))), []


def _validate_currency(value: str) -> tuple[str | None, list[str]]:
    v = value.strip().upper()
    if not re.match(r"^[A-Z]{3}$", v):
        return None, [
            f"currency: '{value}' is not a valid ISO 4217 code. "
            "Expected 3 uppercase letters (e.g. 'USD', 'EUR')."
        ]
    return v, []


def _validate_invoice_number(value: str) -> tuple[str | None, list[str]]:
    v = value.strip().upper()
    if not v:
        return None, ["invoice_number cannot be blank."]
    return v[:100], []


# ── Confidence ────────────────────────────────────────────────────────────────

def _confidence(value: str | None, evidence: str | None) -> str:
    if value is None:
        return "absent"
    return "medium" if evidence else "low"
