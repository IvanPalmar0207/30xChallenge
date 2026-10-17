"""Organization-scoped authorization.

Every protected organization endpoint resolves the caller's ACTIVE membership
server-side. The client's organization ID is only a lookup key — never proof
of authorization.
"""

from rest_framework import permissions

from .models import Organization


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
