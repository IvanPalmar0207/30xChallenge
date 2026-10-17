"""Integration tests for organization-scoped invoice management
(Phase 2, Slice 4). Real API requests with real token authentication.

Reads (list/retrieve) are open to any ACTIVE member of the ACTIVE
organization; creation is reserved for FINANCE_ADMIN and OPERATOR. No mocks
bypass permissions, serializer validation, transaction handling, or database
constraints — the only mocks target AuditEvent.objects.create to prove
audit-failure rollback.
"""

import uuid
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import (
    AuditEvent,
    Invoice,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    Vendor,
)

User = get_user_model()


def auth(client, user):
    token, _ = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


class InvoiceApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organization.objects.create(name="Invoice Org A")
        cls.org_b = Organization.objects.create(name="Invoice Org B")
        cls.org_inactive = Organization.objects.create(
            name="Invoice Org Inactive", status=Organization.Status.INACTIVE
        )
        cls.admin_a = User.objects.create_user(username="i_admin_a", password="x")
        cls.operator_a = User.objects.create_user(username="i_operator_a", password="x")
        cls.approver_a = User.objects.create_user(username="i_approver_a", password="x")
        cls.auditor_a = User.objects.create_user(username="i_auditor_a", password="x")
        cls.member_a = User.objects.create_user(username="i_member_a", password="x")
        cls.admin_b = User.objects.create_user(username="i_admin_b", password="x")
        cls.admin_inactive = User.objects.create_user(
            username="i_admin_inactive", password="x"
        )
        cls.superuser = User.objects.create_superuser(username="i_root", password="x")
        cls.nomember = User.objects.create_user(username="i_nomember", password="x")
        cls.inactive_user = User.objects.create_user(
            username="i_inactive_user", password="x", is_active=False
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
        cls.v_active2 = Vendor.objects.create(
            organization=cls.org_a, legal_name="Beta Ltd", tax_id="BETA-2"
        )
        cls.v_inactive = Vendor.objects.create(
            organization=cls.org_a,
            legal_name="Gamma GmbH",
            tax_id="GAMMA-3",
            status=Vendor.Status.INACTIVE,
        )
        cls.v_b = Vendor.objects.create(
            organization=cls.org_b, legal_name="Acme B", tax_id="ACME-1"
        )

        cls.inv = Invoice.objects.create(
            organization=cls.org_a,
            vendor=cls.v_active,
            invoice_number="INV-001",
            issue_date="2026-10-01",
            amount="100.00",
            currency="USD",
        )

    def setUp(self):
        self.client = APIClient()

    def url_list(self, org_id):
        return f"/api/v1/organizations/{org_id}/invoices/"

    def url_detail(self, org_id, invoice_id):
        return f"/api/v1/organizations/{org_id}/invoices/{invoice_id}/"

    def payload(self, **overrides):
        data = {
            "vendor": str(self.v_active.id),
            "invoice_number": "INV-900",
            "issue_date": "2026-10-01",
            "amount": "100.00",
            "currency": "USD",
        }
        data.update(overrides)
        return data

    # --- authentication gates -------------------------------------------------
    def test_anonymous_cannot_list_invoices(self):
        self.assertEqual(self.client.get(self.url_list(self.org_a.id)).status_code, 401)

    def test_anonymous_cannot_create_invoice(self):
        response = self.client.post(
            self.url_list(self.org_a.id), self.payload(), format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_anonymous_cannot_retrieve_invoice(self):
        self.assertEqual(
            self.client.get(self.url_detail(self.org_a.id, self.inv.id)).status_code,
            401,
        )

    # --- creation: FINANCE_ADMIN and OPERATOR ---------------------------------
    def test_finance_admin_creates_invoice(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id), self.payload(), format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["invoice_number"], "INV-900")
        self.assertEqual(response.data["status"], Invoice.Status.RECEIVED)
        self.assertEqual(response.data["vendor"]["id"], str(self.v_active.id))
        invoice = Invoice.objects.get(invoice_number="INV-900")
        self.assertEqual(invoice.organization, self.org_a)
        self.assertEqual(invoice.vendor, self.v_active)

    def test_operator_creates_invoice(self):
        auth(self.client, self.operator_a)
        response = self.client.post(
            self.url_list(self.org_a.id), self.payload(), format="json"
        )
        self.assertEqual(response.status_code, 201)

    def test_approver_cannot_create_invoice(self):
        auth(self.client, self.approver_a)
        response = self.client.post(
            self.url_list(self.org_a.id), self.payload(), format="json"
        )
        self.assertEqual(response.status_code, 404)

    def test_auditor_cannot_create_invoice(self):
        auth(self.client, self.auditor_a)
        response = self.client.post(
            self.url_list(self.org_a.id), self.payload(), format="json"
        )
        self.assertEqual(response.status_code, 404)

    def test_superuser_without_membership_has_no_bypass(self):
        auth(self.client, self.superuser)
        self.assertEqual(self.client.get(self.url_list(self.org_a.id)).status_code, 404)
        response = self.client.post(
            self.url_list(self.org_a.id), self.payload(), format="json"
        )
        self.assertEqual(response.status_code, 404)

    # --- reads: any active member --------------------------------------------
    def test_active_member_lists_invoices(self):
        auth(self.client, self.member_a)
        response = self.client.get(self.url_list(self.org_a.id))
        self.assertEqual(response.status_code, 200)
        numbers = {i["invoice_number"] for i in response.data}
        self.assertIn("INV-001", numbers)

    def test_active_member_retrieves_invoice(self):
        auth(self.client, self.member_a)
        response = self.client.get(self.url_detail(self.org_a.id, self.inv.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["invoice_number"], "INV-001")
        self.assertEqual(response.data["amount"], "100.00")
        self.assertEqual(response.data["currency"], "USD")
        self.assertEqual(response.data["status"], Invoice.Status.RECEIVED)

    def test_user_without_membership_cannot_read(self):
        auth(self.client, self.nomember)
        self.assertEqual(self.client.get(self.url_list(self.org_a.id)).status_code, 404)
        self.assertEqual(
            self.client.get(self.url_detail(self.org_a.id, self.inv.id)).status_code,
            404,
        )

    # --- tenant isolation -----------------------------------------------------
    def test_cross_org_read_blocked(self):
        auth(self.client, self.admin_b)
        self.assertEqual(
            self.client.get(self.url_detail(self.org_a.id, self.inv.id)).status_code,
            404,
        )
        auth(self.client, self.admin_a)
        self.assertEqual(self.client.get(self.url_list(self.org_b.id)).status_code, 404)

    def test_cross_org_create_blocked(self):
        # admin_b (org B) cannot create in org A's URL.
        auth(self.client, self.admin_b)
        response = self.client.post(
            self.url_list(self.org_a.id), self.payload(), format="json"
        )
        self.assertEqual(response.status_code, 404)
        # admin_a (org A) cannot create with a vendor that belongs to org B.
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            self.payload(vendor=str(self.v_b.id)),
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    # --- inactive states ------------------------------------------------------
    def test_inactive_organization_rejects_invoice_operations(self):
        auth(self.client, self.admin_inactive)
        self.assertEqual(
            self.client.get(self.url_list(self.org_inactive.id)).status_code, 404
        )
        response = self.client.post(
            self.url_list(self.org_inactive.id), self.payload(), format="json"
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

    def test_inactive_user_cannot_access_invoice_endpoints(self):
        auth(self.client, self.inactive_user)
        self.assertEqual(self.client.get(self.url_list(self.org_a.id)).status_code, 401)
        response = self.client.post(
            self.url_list(self.org_a.id), self.payload(), format="json"
        )
        self.assertEqual(response.status_code, 401)

    # --- vendor rules ---------------------------------------------------------
    def test_nonexistent_vendor_returns_404(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            self.payload(vendor=str(uuid.uuid4())),
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_inactive_vendor_returns_400(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            self.payload(vendor=str(self.v_inactive.id)),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Vendor is inactive.", str(response.data))

    # --- uniqueness and normalization ----------------------------------------
    def test_duplicate_invoice_number_same_vendor_rejected(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            self.payload(invoice_number="INV-001"),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("already exists", str(response.data).lower())

    def test_same_number_different_vendor_allowed(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            self.payload(invoice_number="INV-001", vendor=str(self.v_active2.id)),
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_same_number_same_vendor_different_org_allowed(self):
        auth(self.client, self.admin_b)
        response = self.client.post(
            self.url_list(self.org_b.id),
            self.payload(invoice_number="INV-001", vendor=str(self.v_b.id)),
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_invoice_number_normalization_is_consistent(self):
        auth(self.client, self.admin_a)
        # "  inv-001 " normalizes to INV-001, which already exists for v_active.
        response = self.client.post(
            self.url_list(self.org_a.id),
            self.payload(invoice_number="  inv-001 "),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        # A new number is stored in its normalized form (strip + upper).
        response = self.client.post(
            self.url_list(self.org_a.id),
            self.payload(invoice_number="  inv-777 "),
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["invoice_number"], "INV-777")
        self.assertEqual(Invoice.objects.get(invoice_number="INV-777").invoice_number, "INV-777")

    def test_invoice_number_uniqueness_enforced_at_database(self):
        with self.assertRaises(IntegrityError):
            Invoice.objects.create(
                organization=self.org_a,
                vendor=self.v_active,
                invoice_number="INV-001",
                issue_date="2026-10-01",
                amount="100.00",
                currency="USD",
            )

    # --- amount, currency, dates ---------------------------------------------
    def test_amount_must_be_positive(self):
        auth(self.client, self.admin_a)
        self.assertEqual(
            self.client.post(
                self.url_list(self.org_a.id), self.payload(amount="0.00"), format="json"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                self.url_list(self.org_a.id), self.payload(amount="-5.00"), format="json"
            ).status_code,
            400,
        )

    def test_amount_precision_enforced(self):
        auth(self.client, self.admin_a)
        self.assertEqual(
            self.client.post(
                self.url_list(self.org_a.id), self.payload(amount="100.999"), format="json"
            ).status_code,
            400,
        )

    def test_amount_missing_controlled(self):
        auth(self.client, self.admin_a)
        data = self.payload()
        del data["amount"]
        self.assertEqual(
            self.client.post(self.url_list(self.org_a.id), data, format="json").status_code,
            400,
        )

    def test_currency_must_be_supported(self):
        auth(self.client, self.admin_a)
        self.assertEqual(
            self.client.post(
                self.url_list(self.org_a.id), self.payload(currency="XYZ"), format="json"
            ).status_code,
            400,
        )

    def test_currency_normalized_to_uppercase(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id), self.payload(currency="usd"), format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["currency"], "USD")

    def test_issue_date_required(self):
        auth(self.client, self.admin_a)
        data = self.payload()
        del data["issue_date"]
        self.assertEqual(
            self.client.post(self.url_list(self.org_a.id), data, format="json").status_code,
            400,
        )

    def test_due_date_not_earlier_than_issue_date(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            self.payload(issue_date="2026-10-10", due_date="2026-10-01"),
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_due_date_optional(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id), self.payload(), format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["due_date"])

    # --- protected-field injection -------------------------------------------
    def test_protected_fields_cannot_be_injected(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            self.payload(
                organization=str(self.org_b.id),
                status="approved",
                id=str(uuid.uuid4()),
                created_at="2000-01-01T00:00:00Z",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Invoice.Status.RECEIVED)
        invoice = Invoice.objects.get(invoice_number="INV-900")
        self.assertEqual(invoice.organization, self.org_a)
        self.assertEqual(invoice.status, Invoice.Status.RECEIVED)

    # --- audit trail ----------------------------------------------------------
    def test_audit_event_recorded_for_creation(self):
        auth(self.client, self.admin_a)
        self.client.post(
            self.url_list(self.org_a.id), self.payload(), format="json"
        )
        invoice = Invoice.objects.get(invoice_number="INV-900")
        event = AuditEvent.objects.get(
            target_id=str(invoice.id), action=AuditEvent.Action.INVOICE_CREATED
        )
        self.assertEqual(event.actor, self.admin_a)
        self.assertEqual(event.organization, self.org_a)
        self.assertEqual(event.target_type, "invoice")
        self.assertEqual(
            event.metadata,
            {
                "invoice_number": "INV-900",
                "vendor": str(self.v_active.id),
                "amount": "100.00",
                "currency": "USD",
            },
        )

    def test_audit_metadata_contains_no_secrets_or_full_body(self):
        auth(self.client, self.admin_a)
        self.client.post(
            self.url_list(self.org_a.id),
            self.payload(description="Confidential internal note"),
            format="json",
        )
        invoice = Invoice.objects.get(invoice_number="INV-900")
        event = AuditEvent.objects.get(
            target_id=str(invoice.id), action=AuditEvent.Action.INVOICE_CREATED
        )
        self.assertNotIn("description", event.metadata)
        self.assertNotIn("Confidential", str(event.metadata))

    def test_audit_failure_rolls_back_invoice_creation(self):
        client = APIClient(raise_request_exception=False)
        auth(client, self.admin_a)
        with mock.patch.object(
            AuditEvent.objects, "create", side_effect=RuntimeError("audit failed")
        ):
            response = client.post(
                self.url_list(self.org_a.id), self.payload(), format="json"
            )
        self.assertEqual(response.status_code, 500)
        self.assertFalse(Invoice.objects.filter(invoice_number="INV-900").exists())

    # --- malformed / unknown resources ----------------------------------------
    def test_malformed_uuid_returns_404(self):
        auth(self.client, self.admin_a)
        self.assertEqual(
            self.client.get(self.url_detail(self.org_a.id, "not-a-uuid")).status_code, 404
        )
        self.assertEqual(
            self.client.get(self.url_list(self.org_a.id) + "not-a-uuid/").status_code, 404
        )

    def test_unknown_invoice_returns_404(self):
        auth(self.client, self.admin_a)
        unknown = uuid.uuid4()
        self.assertEqual(
            self.client.get(self.url_detail(self.org_a.id, unknown)).status_code, 404
        )
