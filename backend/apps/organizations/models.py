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
