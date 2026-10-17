from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    MembershipDetailView,
    MembershipListCreateView,
    OrganizationViewSet,
    UserActivationView,
    UserCreateView,
    VendorActivateView,
    VendorDeactivateView,
    VendorDetailView,
    VendorListCreateView,
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
    # Vendor management (Slice 3). Reads: any active member of the active
    # organization; mutations: FINANCE_ADMIN only. Activation/deactivation
    # are explicit operations; the ordinary PATCH never touches status.
    path(
        "organizations/<uuid:organization_pk>/vendors/",
        VendorListCreateView.as_view(),
        name="organization-vendor-list",
    ),
    path(
        "organizations/<uuid:organization_pk>/vendors/<uuid:pk>/",
        VendorDetailView.as_view(),
        name="organization-vendor-detail",
    ),
    path(
        "organizations/<uuid:organization_pk>/vendors/<uuid:pk>/activate/",
        VendorActivateView.as_view(),
        name="organization-vendor-activate",
    ),
    path(
        "organizations/<uuid:organization_pk>/vendors/<uuid:pk>/deactivate/",
        VendorDeactivateView.as_view(),
        name="organization-vendor-deactivate",
    ),
]
