"""Organization models.

Tenant model: organizations own every domain object in later slices. The
access gate for protected resources is an ACTIVE membership in an ACTIVE
organization (see organizations.permissions) — never a client-supplied ID.
"""

import uuid

from django.conf import settings
from django.db import models


class Organization(models.Model):
    """A tenant that owns domain data (invoices, vendors, policies, ...)."""

    class Status(models.TextChoices):
        ACTIVE = "active"
        INACTIVE = "inactive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class OrganizationRole(models.TextChoices):
    """Minimum organization-scoped roles for this slice.

    Baseline only: roles are stored data now. Per-role permissions are added
    in later slices. The financial approval authority must always be granted
    explicitly — never implicitly through superuser/staff status.
    """

    FINANCE_ADMIN = "FINANCE_ADMIN"
    OPERATOR = "OPERATOR"
    APPROVER = "APPROVER"
    AUDITOR = "AUDITOR"


class OrganizationMembership(models.Model):
    """A user's organization-scoped membership and role.

    Security invariant: access is granted only through an ACTIVE membership
    (is_active=True) of an ACTIVE organization. Uniqueness per (user,
    organization) is enforced at the database level below.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=32, choices=OrganizationRole.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization__name", "user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization"],
                name="unique_user_organization_membership",
            ),
        ]

    def __str__(self):
        return f"{self.user} @ {self.organization} ({self.role})"


class Vendor(models.Model):
    """A supplier owned by exactly one organization (tenant-scoped).

    Vendors are never deleted: deactivation (status=inactive) preserves the
    record and its historical identity. The tax identifier is normalized
    (strip + uppercase) before storage and uniqueness checks; the supported
    jurisdiction is unspecified, so no country-specific format validation is
    performed (documented limitation).
    """

    class Status(models.TextChoices):
        ACTIVE = "active"
        INACTIVE = "inactive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="vendors",
    )
    legal_name = models.CharField(max_length=200)
    tax_id = models.CharField(max_length=50)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["legal_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "tax_id"],
                name="unique_vendor_tax_id_per_organization",
            ),
        ]

    def __str__(self):
        return f"{self.legal_name} @ {self.organization}"


class Invoice(models.Model):
    """A supplier invoice owned by exactly one organization.

    Registered securely for later slices (extraction, policy evaluation,
    human review). The initial status is always `received`; lifecycle states
    arrive in later slices. Money is stored as Decimal, never float. The
    invoice number is normalized (strip + uppercase) before storage and
    duplicate checks; the database uniqueness constraint acts on the stored
    value, so normalization is an application-level guarantee (documented
    limitation, consistent with Vendor.tax_id).
    """

    class Status(models.TextChoices):
        RECEIVED = "received"
        APPROVED = "approved"
        BLOCKED = "blocked"
        ESCALATED = "escalated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invoices",
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    invoice_number = models.CharField(max_length=100)
    issue_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3)
    description = models.TextField(blank=True, max_length=500)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RECEIVED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "vendor", "invoice_number"],
                name="unique_invoice_number_per_vendor_in_organization",
            ),
        ]

    def __str__(self):
        return f"{self.invoice_number} @ {self.organization}"


class Policy(models.Model):
    """An explicit, versioned, immutable organization policy for invoice
    evaluation.

    Creating a new policy deactivates the previous active one (one active
    policy per organization); historical versions are never modified. Rule
    semantics (documented): `allowed_currencies=[]` means no currency
    restriction; `max_amount` is a hard cap (exceeding it blocks);
    `escalation_threshold` escalates amounts above it (if not blocked
    first); `require_due_date` / `require_description` escalate invoices with
    missing data. When both limits are set, `escalation_threshold` must not
    exceed `max_amount` (validated at creation).
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="policies",
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    allowed_currencies = models.JSONField(default=list, blank=True)
    max_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    escalation_threshold = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    require_due_date = models.BooleanField(default=False)
    require_description = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "version"],
                name="unique_policy_version_per_organization",
            ),
        ]

    def __str__(self):
        return f"Policy v{self.version} @ {self.organization}"


class PolicyDecision(models.Model):
    """The persisted, auditable result of evaluating one invoice against the
    active policy.

    One decision per invoice (database-level backstop against duplicate
    evaluations). The `rules_snapshot` makes the decision self-contained:
    later policy changes never alter recorded decisions. The requester never
    chooses the outcome — the deterministic engine does.
    """

    class Result(models.TextChoices):
        APPROVED = "approved"
        BLOCKED = "blocked"
        ESCALATED = "escalated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="policy_decisions",
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="decisions",
    )
    result = models.CharField(max_length=20, choices=Result.choices)
    reason_code = models.CharField(max_length=50)
    reason_detail = models.TextField(blank=True)
    policy_id = models.UUIDField(null=True, blank=True)
    policy_version = models.PositiveIntegerField(null=True, blank=True)
    rules_snapshot = models.JSONField(default=dict, blank=True)
    evaluated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["invoice"],
                name="unique_policy_decision_per_invoice",
            ),
        ]

    def __str__(self):
        return f"{self.result} ({self.reason_code}) for {self.invoice}"


class AuditEvent(models.Model):
    """Append-only audit record for security-relevant administrative changes.

    Records account and membership administration events with the actor,
    organization context, action, target reference, timestamp, and safe
    metadata. Never stores passwords, hashes, tokens, or raw headers.

    Append-only is enforced at the application level (save/delete are
    blocked); the database itself does not enforce it, so a direct SQL write
    could still mutate rows. That limitation is accepted for the MVP and
    documented in the slice report.
    """

    class Action(models.TextChoices):
        ACCOUNT_CREATED = "account_created", "Account created"
        ACCOUNT_ACTIVATED = "account_activated", "Account activated"
        ACCOUNT_DEACTIVATED = "account_deactivated", "Account deactivated"
        MEMBERSHIP_CREATED = "membership_created", "Membership created"
        MEMBERSHIP_ROLE_CHANGED = "membership_role_changed", "Membership role changed"
        MEMBERSHIP_ACTIVATED = "membership_activated", "Membership activated"
        MEMBERSHIP_DEACTIVATED = "membership_deactivated", "Membership deactivated"
        VENDOR_CREATED = "vendor_created", "Vendor created"
        VENDOR_UPDATED = "vendor_updated", "Vendor updated"
        VENDOR_ACTIVATED = "vendor_activated", "Vendor activated"
        VENDOR_DEACTIVATED = "vendor_deactivated", "Vendor deactivated"
        INVOICE_CREATED = "invoice_created", "Invoice created"
        INVITATION_ISSUED = "invitation_issued", "Invitation issued"
        PASSWORD_SET = "password_set", "Password set"
        INVOICE_EVALUATED = "invoice_evaluated", "Invoice evaluated"
        POLICY_CREATED = "policy_created", "Policy created"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    target_type = models.CharField(max_length=32)
    target_id = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"]),
        ]

    def __str__(self):
        return f"{self.action} by {self.actor} @ {self.organization}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Audit events are append-only and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit events are append-only and cannot be deleted.")


class PasswordSetupToken(models.Model):
    """One-time, expiring token that authorizes setting an account's initial
    password.

    Only the SHA-256 hash of the raw token is stored; the raw token is shown
    exactly once (in the invite response) and relayed out-of-band. An
    ordinary DRF access token is never accepted by the set-password flow, so
    a leaked or filtered access token cannot take over an account that has no
    password yet (Slice 5 spec S4).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_setup_tokens",
    )
    token_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["token_hash"]),
        ]

    def __str__(self):
        return f"setup token for {self.user}"
