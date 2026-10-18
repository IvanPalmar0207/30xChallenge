"""Integration tests for organization-scoped vendor management
(Phase 2, Slice 3). Real API requests with real token authentication.

Reads (list/retrieve) are open to any ACTIVE member of the ACTIVE
organization; mutations (create/update/activate/deactivate) are reserved for
FINANCE_ADMIN. No mocks bypass permissions, serializer validation, transaction
handling, or database constraints — the only mocks target AuditEvent.objects
.create to prove audit-failure rollback.
"""

import uuid
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIClient

from .models import AuditEvent, Organization, OrganizationMembership, OrganizationRole, Vendor

User = get_user_model()


def auth(client, user):
    """Authenticate through the real JWT pipeline."""
    access = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


class VendorApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organization.objects.create(name="Vendor Org A")
        cls.org_b = Organization.objects.create(name="Vendor Org B")
        cls.org_inactive = Organization.objects.create(
            name="Vendor Org Inactive", status=Organization.Status.INACTIVE
        )
        cls.admin_a = User.objects.create_user(username="v_admin_a", password="x")
        cls.operator_a = User.objects.create_user(username="v_operator_a", password="x")
        cls.approver_a = User.objects.create_user(username="v_approver_a", password="x")
        cls.auditor_a = User.objects.create_user(username="v_auditor_a", password="x")
        cls.member_a = User.objects.create_user(username="v_member_a", password="x")
        cls.admin_b = User.objects.create_user(username="v_admin_b", password="x")
        cls.admin_inactive = User.objects.create_user(
            username="v_admin_inactive", password="x"
        )
        cls.superuser = User.objects.create_superuser(username="v_root", password="x")
        cls.nomember = User.objects.create_user(username="v_nomember", password="x")
        cls.inactive_user = User.objects.create_user(
            username="v_inactive_user", password="x", is_active=False
        )

        OrganizationMembership.objects.create(
            user=cls.admin_a, organization=cls.org_a, role=OrganizationRole.FINANCE_ADMIN
        )
        OrganizationMembership.objects.create(
            user=cls.operator_a, organization=cls.org_a, role=OrganizationRole.OPERATOR
        )
        OrganizationMembership.objects.create(
            user=cls.approver_a, organization=cls.org_a, role=OrganizationRole.APPROVER
        )
        OrganizationMembership.objects.create(
            user=cls.auditor_a, organization=cls.org_a, role=OrganizationRole.AUDITOR
        )
        OrganizationMembership.objects.create(
            user=cls.member_a, organization=cls.org_a, role=OrganizationRole.OPERATOR
        )
        OrganizationMembership.objects.create(
            user=cls.admin_b, organization=cls.org_b, role=OrganizationRole.FINANCE_ADMIN
        )
        OrganizationMembership.objects.create(
            user=cls.admin_inactive,
            organization=cls.org_inactive,
            role=OrganizationRole.FINANCE_ADMIN,
        )

        cls.v_active = Vendor.objects.create(
            organization=cls.org_a, legal_name="Acme Corp", tax_id="ACME-1"
        )
        cls.v_inactive = Vendor.objects.create(
            organization=cls.org_a,
            legal_name="Beta Ltd",
            tax_id="BETA-2",
            status=Vendor.Status.INACTIVE,
        )
        # Same normalized tax identifier as v_active, but in another org.
        cls.v_b = Vendor.objects.create(
            organization=cls.org_b, legal_name="Acme B", tax_id="ACME-1"
        )

    def setUp(self):
        self.client = APIClient()

    def url_list(self, org_id):
        return f"/api/v1/organizations/{org_id}/vendors/"

    def url_detail(self, org_id, vendor_id):
        return f"/api/v1/organizations/{org_id}/vendors/{vendor_id}/"

    def url_activate(self, org_id, vendor_id):
        return f"/api/v1/organizations/{org_id}/vendors/{vendor_id}/activate/"

    def url_deactivate(self, org_id, vendor_id):
        return f"/api/v1/organizations/{org_id}/vendors/{vendor_id}/deactivate/"

    # --- authentication gates -------------------------------------------------
    def test_anonymous_cannot_list_vendors(self):
        self.assertEqual(self.client.get(self.url_list(self.org_a.id)).status_code, 401)

    def test_anonymous_cannot_create_vendor(self):
        response = self.client.post(
            self.url_list(self.org_a.id),
            {"legal_name": "X", "tax_id": "X-1"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_anonymous_cannot_retrieve_vendor(self):
        self.assertEqual(
            self.client.get(self.url_detail(self.org_a.id, self.v_active.id)).status_code,
            401,
        )

    def test_anonymous_cannot_activate_or_deactivate(self):
        self.assertEqual(
            self.client.post(self.url_activate(self.org_a.id, self.v_inactive.id)).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(self.url_deactivate(self.org_a.id, self.v_active.id)).status_code,
            401,
        )

    # --- reads: any active member --------------------------------------------
    def test_active_member_lists_vendors_including_inactive(self):
        auth(self.client, self.operator_a)
        response = self.client.get(self.url_list(self.org_a.id))
        self.assertEqual(response.status_code, 200)
        statuses = {v["tax_id"]: v["status"] for v in response.data}
        self.assertEqual(statuses["ACME-1"], Vendor.Status.ACTIVE)
        self.assertEqual(statuses["BETA-2"], Vendor.Status.INACTIVE)

    def test_active_member_retrieves_vendor(self):
        auth(self.client, self.operator_a)
        response = self.client.get(self.url_detail(self.org_a.id, self.v_active.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["legal_name"], "Acme Corp")
        self.assertEqual(response.data["organization"]["id"], str(self.org_a.id))

    def test_approver_and_auditor_can_read(self):
        auth(self.client, self.approver_a)
        self.assertEqual(self.client.get(self.url_list(self.org_a.id)).status_code, 200)
        auth(self.client, self.auditor_a)
        self.assertEqual(self.client.get(self.url_list(self.org_a.id)).status_code, 200)

    def test_user_without_membership_cannot_read(self):
        auth(self.client, self.nomember)
        self.assertEqual(self.client.get(self.url_list(self.org_a.id)).status_code, 404)
        self.assertEqual(
            self.client.get(self.url_detail(self.org_a.id, self.v_active.id)).status_code,
            404,
        )

    # --- mutations: FINANCE_ADMIN only ---------------------------------------
    def test_finance_admin_creates_vendor(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            {"legal_name": "Gamma GmbH", "tax_id": "GAMMA-3"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["legal_name"], "Gamma GmbH")
        self.assertEqual(response.data["tax_id"], "GAMMA-3")
        self.assertEqual(response.data["status"], Vendor.Status.ACTIVE)
        self.assertEqual(response.data["organization"]["id"], str(self.org_a.id))
        vendor = Vendor.objects.get(tax_id="GAMMA-3")
        self.assertEqual(vendor.organization, self.org_a)

    def test_operator_cannot_create_vendor(self):
        auth(self.client, self.operator_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            {"legal_name": "X", "tax_id": "X-1"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_approver_cannot_create_vendor(self):
        auth(self.client, self.approver_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            {"legal_name": "X", "tax_id": "X-1"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_auditor_cannot_create_vendor(self):
        auth(self.client, self.auditor_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            {"legal_name": "X", "tax_id": "X-1"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_finance_admin_updates_vendor(self):
        auth(self.client, self.admin_a)
        response = self.client.patch(
            self.url_detail(self.org_a.id, self.v_active.id),
            {"legal_name": "Acme Corporation"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["legal_name"], "Acme Corporation")
        self.v_active.refresh_from_db()
        self.assertEqual(self.v_active.legal_name, "Acme Corporation")

    def test_operator_cannot_update_vendor(self):
        auth(self.client, self.operator_a)
        response = self.client.patch(
            self.url_detail(self.org_a.id, self.v_active.id),
            {"legal_name": "Hacked"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_superuser_without_membership_has_no_bypass(self):
        auth(self.client, self.superuser)
        self.assertEqual(self.client.get(self.url_list(self.org_a.id)).status_code, 404)
        response = self.client.post(
            self.url_list(self.org_a.id),
            {"legal_name": "X", "tax_id": "X-1"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    # --- tenant isolation -----------------------------------------------------
    def test_cross_org_read_blocked(self):
        auth(self.client, self.admin_b)
        self.assertEqual(
            self.client.get(self.url_detail(self.org_a.id, self.v_active.id)).status_code,
            404,
        )
        auth(self.client, self.admin_a)
        self.assertEqual(
            self.client.get(self.url_detail(self.org_b.id, self.v_b.id)).status_code,
            404,
        )

    def test_cross_org_mutation_blocked(self):
        auth(self.client, self.admin_b)
        response = self.client.patch(
            self.url_detail(self.org_a.id, self.v_active.id),
            {"legal_name": "Hacked"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.v_active.refresh_from_db()
        self.assertEqual(self.v_active.legal_name, "Acme Corp")

    def test_organization_ownership_cannot_be_injected(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            {
                "legal_name": "Delta SA",
                "tax_id": "DELTA-4",
                "organization": str(self.org_b.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["organization"]["id"], str(self.org_a.id))
        vendor = Vendor.objects.get(tax_id="DELTA-4")
        self.assertEqual(vendor.organization, self.org_a)

    # --- inactive states ------------------------------------------------------
    def test_inactive_organization_rejects_vendor_operations(self):
        auth(self.client, self.admin_inactive)
        self.assertEqual(
            self.client.get(self.url_list(self.org_inactive.id)).status_code, 404
        )
        response = self.client.post(
            self.url_list(self.org_inactive.id),
            {"legal_name": "X", "tax_id": "X-1"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_inactive_membership_does_not_grant_access(self):
        membership = OrganizationMembership.objects.get(
            user=self.member_a, organization=self.org_a
        )
        membership.is_active = False
        membership.save()
        auth(self.client, self.member_a)
        self.assertEqual(self.client.get(self.url_list(self.org_a.id)).status_code, 404)

    def test_inactive_user_cannot_access_vendor_endpoints(self):
        auth(self.client, self.inactive_user)
        self.assertEqual(self.client.get(self.url_list(self.org_a.id)).status_code, 401)
        response = self.client.post(
            self.url_list(self.org_a.id),
            {"legal_name": "X", "tax_id": "X-1"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    # --- tax identifier normalization and uniqueness --------------------------
    def test_duplicate_tax_id_same_org_rejected(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            {"legal_name": "Another Acme", "tax_id": "ACME-1"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("tax identifier", str(response.data).lower())

    def test_same_tax_id_different_organizations_allowed(self):
        auth(self.client, self.admin_b)
        response = self.client.post(
            self.url_list(self.org_b.id),
            {"legal_name": "Beta B", "tax_id": "BETA-2"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["tax_id"], "BETA-2")

    def test_tax_id_normalization_is_consistent(self):
        auth(self.client, self.admin_a)
        # "  acme-1 " normalizes to ACME-1, which already exists in org A.
        response = self.client.post(
            self.url_list(self.org_a.id),
            {"legal_name": "Dup", "tax_id": "  acme-1 "},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        # A new identifier is stored in its normalized form (strip + upper).
        response = self.client.post(
            self.url_list(self.org_a.id),
            {"legal_name": "Epsilon", "tax_id": "  eps-5 "},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["tax_id"], "EPS-5")
        self.assertEqual(Vendor.objects.get(legal_name="Epsilon").tax_id, "EPS-5")

    def test_tax_id_uniqueness_enforced_at_database(self):
        with self.assertRaises(IntegrityError):
            Vendor.objects.create(
                organization=self.org_a, legal_name="Dup", tax_id="ACME-1"
            )

    def test_invalid_and_missing_fields_controlled(self):
        auth(self.client, self.admin_a)
        self.assertEqual(
            self.client.post(self.url_list(self.org_a.id), {}, format="json").status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                self.url_list(self.org_a.id), {"legal_name": "X"}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                self.url_list(self.org_a.id),
                {"legal_name": "X", "tax_id": "   "},
                format="json",
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                self.url_list(self.org_a.id),
                {"legal_name": "X", "tax_id": "T" * 51},
                format="json",
            ).status_code,
            400,
        )

    # --- activation / deactivation -------------------------------------------
    def test_deactivate_preserves_record(self):
        auth(self.client, self.admin_a)
        response = self.client.post(self.url_deactivate(self.org_a.id, self.v_active.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Vendor.Status.INACTIVE)
        self.v_active.refresh_from_db()
        self.assertEqual(self.v_active.status, Vendor.Status.INACTIVE)
        self.assertTrue(Vendor.objects.filter(pk=self.v_active.pk).exists())

    def test_inactive_vendor_not_reactivated_by_ordinary_update(self):
        auth(self.client, self.admin_a)
        response = self.client.patch(
            self.url_detail(self.org_a.id, self.v_inactive.id),
            {"legal_name": "Beta Renamed"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.v_inactive.refresh_from_db()
        self.assertEqual(self.v_inactive.status, Vendor.Status.INACTIVE)
        # Even an explicit status field in the PATCH body is ignored: the
        # update serializer only accepts legal_name/tax_id, so the vendor
        # stays inactive (no silent reactivation).
        response = self.client.patch(
            self.url_detail(self.org_a.id, self.v_inactive.id),
            {"status": Vendor.Status.ACTIVE},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.v_inactive.refresh_from_db()
        self.assertEqual(self.v_inactive.status, Vendor.Status.INACTIVE)

    def test_only_admin_can_activate_or_deactivate(self):
        auth(self.client, self.operator_a)
        self.assertEqual(
            self.client.post(self.url_activate(self.org_a.id, self.v_inactive.id)).status_code,
            404,
        )
        auth(self.client, self.auditor_a)
        self.assertEqual(
            self.client.post(self.url_deactivate(self.org_a.id, self.v_active.id)).status_code,
            404,
        )

    def test_admin_activates_vendor(self):
        auth(self.client, self.admin_a)
        response = self.client.post(self.url_activate(self.org_a.id, self.v_inactive.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Vendor.Status.ACTIVE)
        self.v_inactive.refresh_from_db()
        self.assertEqual(self.v_inactive.status, Vendor.Status.ACTIVE)

    def test_activation_is_idempotent(self):
        auth(self.client, self.admin_a)
        before = AuditEvent.objects.filter(action=AuditEvent.Action.VENDOR_ACTIVATED).count()
        response = self.client.post(self.url_activate(self.org_a.id, self.v_active.id))
        self.assertEqual(response.status_code, 200)
        after = AuditEvent.objects.filter(action=AuditEvent.Action.VENDOR_ACTIVATED).count()
        self.assertEqual(after, before)

    # --- field injection -----------------------------------------------------
    def test_internal_fields_cannot_be_injected(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            {
                "legal_name": "Zeta",
                "tax_id": "ZETA-6",
                "status": Vendor.Status.INACTIVE,
                "id": str(uuid.uuid4()),
                "created_at": "2000-01-01T00:00:00Z",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Vendor.Status.ACTIVE)
        vendor = Vendor.objects.get(tax_id="ZETA-6")
        self.assertEqual(vendor.status, Vendor.Status.ACTIVE)

    # --- audit trail ----------------------------------------------------------
    def test_audit_events_recorded_for_successful_operations(self):
        auth(self.client, self.admin_a)
        self.client.post(
            self.url_list(self.org_a.id),
            {"legal_name": "Eta", "tax_id": "ETA-7"},
            format="json",
        )
        eta = Vendor.objects.get(tax_id="ETA-7")
        self.client.patch(
            self.url_detail(self.org_a.id, eta.id), {"legal_name": "Eta Renamed"}
        )
        self.client.post(self.url_deactivate(self.org_a.id, eta.id))
        self.client.post(self.url_activate(self.org_a.id, eta.id))

        events = list(
            AuditEvent.objects.filter(target_id=str(eta.id)).order_by("created_at")
        )
        self.assertEqual(
            [e.action for e in events],
            [
                AuditEvent.Action.VENDOR_CREATED,
                AuditEvent.Action.VENDOR_UPDATED,
                AuditEvent.Action.VENDOR_DEACTIVATED,
                AuditEvent.Action.VENDOR_ACTIVATED,
            ],
        )
        for event in events:
            self.assertEqual(event.actor, self.admin_a)
            self.assertEqual(event.organization, self.org_a)
            self.assertEqual(event.target_type, "vendor")

    def test_audit_metadata_contains_no_secrets_or_full_body(self):
        auth(self.client, self.admin_a)
        self.client.post(
            self.url_list(self.org_a.id),
            {"legal_name": "Theta", "tax_id": "THETA-8"},
            format="json",
        )
        theta = Vendor.objects.get(tax_id="THETA-8")
        self.client.patch(
            self.url_detail(self.org_a.id, theta.id),
            {"legal_name": "Theta Renamed", "tax_id": "THETA-9"},
        )
        self.client.post(self.url_deactivate(self.org_a.id, theta.id))

        created = AuditEvent.objects.get(
            target_id=str(theta.id), action=AuditEvent.Action.VENDOR_CREATED
        )
        self.assertEqual(created.metadata, {"legal_name": "Theta"})
        updated = AuditEvent.objects.get(
            target_id=str(theta.id), action=AuditEvent.Action.VENDOR_UPDATED
        )
        self.assertEqual(
            updated.metadata,
            {
                "changes": {
                    "legal_name": {"from": "Theta", "to": "Theta Renamed"},
                    "tax_id": {"from": "THETA-8", "to": "THETA-9"},
                }
            },
        )
        deactivated = AuditEvent.objects.get(
            target_id=str(theta.id), action=AuditEvent.Action.VENDOR_DEACTIVATED
        )
        self.assertEqual(
            deactivated.metadata,
            {"status_before": Vendor.Status.ACTIVE, "status_after": Vendor.Status.INACTIVE},
        )

    def test_update_without_changes_creates_no_audit_event(self):
        auth(self.client, self.admin_a)
        before = AuditEvent.objects.filter(
            target_id=str(self.v_active.id), action=AuditEvent.Action.VENDOR_UPDATED
        ).count()
        response = self.client.patch(
            self.url_detail(self.org_a.id, self.v_active.id),
            {"legal_name": "Acme Corp"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        after = AuditEvent.objects.filter(
            target_id=str(self.v_active.id), action=AuditEvent.Action.VENDOR_UPDATED
        ).count()
        self.assertEqual(after, before)

    def test_audit_failure_rolls_back_vendor_creation(self):
        client = APIClient(raise_request_exception=False)
        auth(client, self.admin_a)
        with mock.patch.object(
            AuditEvent.objects, "create", side_effect=RuntimeError("audit failed")
        ):
            response = client.post(
                self.url_list(self.org_a.id),
                {"legal_name": "Iota", "tax_id": "IOTA-10"},
                format="json",
            )
        self.assertEqual(response.status_code, 500)
        self.assertFalse(Vendor.objects.filter(tax_id="IOTA-10").exists())

    def test_audit_failure_rolls_back_vendor_update(self):
        client = APIClient(raise_request_exception=False)
        auth(client, self.admin_a)
        with mock.patch.object(
            AuditEvent.objects, "create", side_effect=RuntimeError("audit failed")
        ):
            response = client.patch(
                self.url_detail(self.org_a.id, self.v_active.id),
                {"legal_name": "Should Not Persist"},
                format="json",
            )
        self.assertEqual(response.status_code, 500)
        self.v_active.refresh_from_db()
        self.assertEqual(self.v_active.legal_name, "Acme Corp")

    def test_audit_failure_rolls_back_deactivation(self):
        client = APIClient(raise_request_exception=False)
        auth(client, self.admin_a)
        with mock.patch.object(
            AuditEvent.objects, "create", side_effect=RuntimeError("audit failed")
        ):
            response = client.post(self.url_deactivate(self.org_a.id, self.v_active.id))
        self.assertEqual(response.status_code, 500)
        self.v_active.refresh_from_db()
        self.assertEqual(self.v_active.status, Vendor.Status.ACTIVE)

    # --- malformed / unknown resources ----------------------------------------
    def test_malformed_uuid_returns_404(self):
        auth(self.client, self.admin_a)
        self.assertEqual(
            self.client.get(self.url_detail(self.org_a.id, "not-a-uuid")).status_code, 404
        )
        self.assertEqual(
            self.client.post(self.url_activate(self.org_a.id, "not-a-uuid")).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(self.url_deactivate(self.org_a.id, "not-a-uuid")).status_code,
            404,
        )

    def test_unknown_vendor_returns_404(self):
        auth(self.client, self.admin_a)
        unknown = uuid.uuid4()
        self.assertEqual(
            self.client.get(self.url_detail(self.org_a.id, unknown)).status_code, 404
        )
        self.assertEqual(
            self.client.post(self.url_activate(self.org_a.id, unknown)).status_code, 404
        )
