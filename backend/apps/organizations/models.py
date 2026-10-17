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
