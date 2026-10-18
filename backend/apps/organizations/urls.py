from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    GlobalOrganizationDetailView,
    GlobalOrganizationListCreateView,
    GlobalUserListView,
    InvoiceApprovalView,
    InvoiceDecisionView,
    InvoiceDetailView,
    InvoiceEvaluateView,
    InvoiceListCreateView,
    MembershipDetailView,
    MembershipListCreateView,
    OrganizationViewSet,
    PolicyDetailView,
    PolicyListCreateView,
    UserActivationView,
    UserCreateView,
    UserInviteView,
    VendorActivateView,
    VendorDeactivateView,
    VendorDetailView,
    VendorListCreateView,
)

router = DefaultRouter()
router.register("organizations", OrganizationViewSet, basename="organization")

urlpatterns = [
    path("", include(router.urls)),
    # Global organization administration (final slice — superuser only).
    # These routes live OUTSIDE the tenant URL space on purpose: they are
    # gated by IsGlobalSuperAdmin in the view, never by membership.
    path(
        "admin/organizations/",
        GlobalOrganizationListCreateView.as_view(),
        name="global-organization-list-create",
    ),
    path(
        "admin/organizations/<uuid:pk>/",
        GlobalOrganizationDetailView.as_view(),
        name="global-organization-detail",
    ),
    path(
        "admin/users/",
        GlobalUserListView.as_view(),
        name="global-user-list",
    ),
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
    # One-time password-setup invitation (Slice 5). FINANCE_ADMIN only; the
    # raw token is returned once and only its hash is stored.
    path(
        "organizations/<uuid:organization_pk>/users/<int:pk>/invite/",
        UserInviteView.as_view(),
        name="organization-user-invite",
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
    # Invoice management (Slice 4). Reads: any active member of the active
    # organization; creation: FINANCE_ADMIN or OPERATOR only. No update or
    # delete in this slice; status is server-assigned.
    path(
        "organizations/<uuid:organization_pk>/invoices/",
        InvoiceListCreateView.as_view(),
        name="organization-invoice-list",
    ),
    path(
        "organizations/<uuid:organization_pk>/invoices/<uuid:pk>/",
        InvoiceDetailView.as_view(),
        name="organization-invoice-detail",
    ),
    # Deterministic policy engine (Slice 6). Policy reads: any active
    # member; policy creation: FINANCE_ADMIN only (immutable versions).
    # Evaluation: FINANCE_ADMIN/OPERATOR trigger, the engine decides.
    path(
        "organizations/<uuid:organization_pk>/policies/",
        PolicyListCreateView.as_view(),
        name="organization-policy-list",
    ),
    path(
        "organizations/<uuid:organization_pk>/policies/<uuid:pk>/",
        PolicyDetailView.as_view(),
        name="organization-policy-detail",
    ),
    path(
        "organizations/<uuid:organization_pk>/invoices/<uuid:pk>/evaluate/",
        InvoiceEvaluateView.as_view(),
        name="organization-invoice-evaluate",
    ),
    path(
        "organizations/<uuid:organization_pk>/invoices/<uuid:pk>/decision/",
        InvoiceDecisionView.as_view(),
        name="organization-invoice-decision",
    ),
    # Human approval (Phase 2). APPROVER only; one decision per invoice.
    path(
        "organizations/<uuid:organization_pk>/invoices/<uuid:pk>/approval/",
        InvoiceApprovalView.as_view(),
        name="organization-invoice-approval",
    ),
]
