from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    MembershipDetailView,
    MembershipListCreateView,
    OrganizationViewSet,
    UserActivationView,
    UserCreateView,
)

router = DefaultRouter()
router.register("organizations", OrganizationViewSet, basename="organization")

urlpatterns = [
    path("", include(router.urls)),
    # Organization-scoped administration endpoints. The <uuid:> converters
    # reject malformed UUIDs with a plain 404 at routing time.
    path(
        "organizations/<uuid:organization_pk>/memberships/",
        MembershipListCreateView.as_view(),
        name="organization-membership-list",
    ),
    path(
        "organizations/<uuid:organization_pk>/memberships/<uuid:pk>/",
        MembershipDetailView.as_view(),
        name="organization-membership-detail",
    ),
    path(
        "organizations/<uuid:organization_pk>/users/",
        UserCreateView.as_view(),
        name="organization-user-create",
    ),
    path(
        "organizations/<uuid:organization_pk>/users/<int:pk>/",
        UserActivationView.as_view(),
        name="organization-user-detail",
    ),
]
