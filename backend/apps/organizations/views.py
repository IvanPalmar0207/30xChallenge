"""Organization API views."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Organization
from .permissions import IsActiveOrganizationMember
from .serializers import OrganizationSerializer


class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    """Organizations the authenticated user may access.

    Security: the queryset is scoped to the request user's ACTIVE memberships
    in ACTIVE organizations. Every other case — unknown UUID, inactive
    membership, inactive organization, or membership in a different
    organization — resolves to the same 404, so the API never discloses
    whether another organization exists (consistent authorization behavior).
    """

    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated, IsActiveOrganizationMember]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Organization.objects.none()
        return (
            Organization.objects.filter(
                status=Organization.Status.ACTIVE,
                memberships__user=user,
                memberships__is_active=True,
            )
            .distinct()
            .order_by("name")
        )
