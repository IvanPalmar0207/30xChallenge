"""Organization-scoped authorization.

Every protected organization endpoint resolves the caller's ACTIVE membership
server-side. The client's organization ID is only a lookup key — never proof
of authorization.
"""

from rest_framework import permissions
from rest_framework.exceptions import NotFound

from .models import Organization, OrganizationMembership, OrganizationRole


class IsActiveOrganizationMember(permissions.BasePermission):
    """Require an authenticated user with an ACTIVE membership in the target
    ACTIVE organization.

    The view querysets are already member-scoped; this object-level check is
    the explicit invariant so future endpoints cannot forget it. An inactive
    organization denies membership lookups even for existing members.
    """

    message = "You do not have access to this organization."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return obj.status == Organization.Status.ACTIVE and obj.memberships.filter(
            user=request.user,
            is_active=True,
        ).exists()


class IsActiveOrganizationFinanceAdmin(permissions.BasePermission):
    """Require an ACTIVE FINANCE_ADMIN membership in the ACTIVE organization
    named by the URL's `organization_pk`.

    Management capability is organization-scoped: a role in one organization
    never grants management rights in another. Unknown organizations, inactive
    organizations, inactive memberships, and non-admin members all resolve to
    the same 404, so the management API never discloses whether an
    organization exists or who administers it (HidingByNotExisting, consistent
    with Slice 1). Anonymous requests are answered by IsAuthenticated first.
    """

    message = "You do not have permission to administer this organization."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        organization_pk = view.kwargs.get("organization_pk")
        if not organization_pk:
            return False
        is_admin = OrganizationMembership.objects.filter(
            user=user,
            organization_id=organization_pk,
            organization__status=Organization.Status.ACTIVE,
            is_active=True,
            role=OrganizationRole.FINANCE_ADMIN,
        ).exists()
        if not is_admin:
            raise NotFound("Organization not found.")
        return True


class IsActiveOrganizationMemberInUrl(permissions.BasePermission):
    """Require an ACTIVE membership (any role) in the ACTIVE organization
    named by the URL's `organization_pk`.

    Tenant-scoped read gate for nested resources (e.g. vendors): any active
    member of the active organization may read, while mutations stay reserved
    for FINANCE_ADMIN. Non-members, inactive memberships, and inactive
    organizations all resolve to the same 404 (HidingByNotExisting), so the
    read API never discloses whether an organization exists.
    """

    message = "You do not have access to this organization."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        organization_pk = view.kwargs.get("organization_pk")
        if not organization_pk:
            return False
        is_member = OrganizationMembership.objects.filter(
            user=user,
            organization_id=organization_pk,
            organization__status=Organization.Status.ACTIVE,
            is_active=True,
        ).exists()
        if not is_member:
            raise NotFound("Organization not found.")
        return True


class IsActiveOrganizationInvoiceCreator(permissions.BasePermission):
    """Require an ACTIVE FINANCE_ADMIN or OPERATOR membership in the ACTIVE
    organization named by the URL's `organization_pk`.

    Invoice registration is a business operation open to operators and
    finance admins; approvers and auditors never gain it by implication.
    Unknown organizations, inactive organizations, inactive memberships, and
    unauthorized roles all resolve to the same 404 (HidingByNotExisting,
    consistent with the other organization-scoped permissions).
    """

    message = "You do not have permission to register invoices in this organization."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        organization_pk = view.kwargs.get("organization_pk")
        if not organization_pk:
            return False
        is_creator = OrganizationMembership.objects.filter(
            user=user,
            organization_id=organization_pk,
            organization__status=Organization.Status.ACTIVE,
            is_active=True,
            role__in=[
                OrganizationRole.FINANCE_ADMIN,
                OrganizationRole.OPERATOR,
            ],
        ).exists()
        if not is_creator:
            raise NotFound("Organization not found.")
        return True
