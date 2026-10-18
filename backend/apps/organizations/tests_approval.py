"""Integration tests for the human invoice approval workflow (Phase 2).

Real API requests with real JWT auth. Covers: APPROVER authorization,
separation of duties (creator / evaluator), exact one decision per invoice,
state eligibility, organization isolation, inactive memberships/organizations,
transactional audit rollback, and no client-side injection of protected fields.
"""

import uuid
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    AuditEvent,
    Invoice,
    InvoiceApproval,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    PolicyDecision,
    Vendor,
)

User = get_user_model()


def auth(client, user):
    access = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


class ApprovalWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organization.objects.create(name="Approval Org A")
        cls.org_b = Organization.objects.create(name="Approval Org B")
        cls.org_inactive = Organization.objects.create(
            name="Approval Org Inactive", status=Organization.Status.INACTIVE
        )

        cls.approver = User.objects.create_user(username="ap_approver", password="x")
        cls.creator = User.objects.create_user(username="ap_creator", password="x")
        cls.evaluator = User.objects.create_user(username="ap_evaluator", password="x")
        cls.finance = User.objects.create_user(username="ap_finance", password="x")
        cls.operator = User.objects.create_user(username="ap_operator", password="x")
        cls.auditor = User.objects.create_user(username="ap_auditor", password="x")
        cls.nomember = User.objects.create_user(username="ap_nomember", password="x")
        cls.approver_inactive_membership = User.objects.create_user(
            username="ap_approver_inactive", password="x"
        )
        cls.approver_other_org = User.objects.create_user(
            username="ap_approver_b", password="x"
        )
        cls.approver_inactive_org = User.objects.create_user(
            username="ap_approver_org_inactive", password="x"
        )

        def member(u, org, role, active=True):
            OrganizationMembership.objects.create(
                user=u, organization=org, role=role, is_active=active
            )

        member(cls.approver, cls.org_a, OrganizationRole.APPROVER)
        member(cls.creator, cls.org_a, OrganizationRole.OPERATOR)
        member(cls.evaluator, cls.org_a, OrganizationRole.OPERATOR)
        member(cls.finance, cls.org_a, OrganizationRole.FINANCE_ADMIN)
        member(cls.operator, cls.org_a, OrganizationRole.OPERATOR)
        member(cls.auditor, cls.org_a, OrganizationRole.AUDITOR)
        member(cls.approver_inactive_membership, cls.org_a, OrganizationRole.APPROVER, active=False)
        member(cls.approver_other_org, cls.org_b, OrganizationRole.APPROVER)
        member(cls.approver_inactive_org, cls.org_inactive, OrganizationRole.APPROVER)

        cls.vendor_a = Vendor.objects.create(
            organization=cls.org_a, legal_name="Acme", tax_id="ACME-APP"
        )
        cls.vendor_b = Vendor.objects.create(
            organization=cls.org_b, legal_name="Beta", tax_id="BETA-APP"
        )

    def setUp(self):
        self.client = APIClient()

    # --- helpers ------------------------------------------------------------
    def url_invoices(self, org_id):
        return f"/api/v1/organizations/{org_id}/invoices/"

    def url_evaluate(self, org_id, invoice_id):
        return f"/api/v1/organizations/{org_id}/invoices/{invoice_id}/evaluate/"

    def url_approval(self, org_id, invoice_id):
        return f"/api/v1/organizations/{org_id}/invoices/{invoice_id}/approval/"

    def url_policies(self, org_id):
        return f"/api/v1/organizations/{org_id}/policies/"

    def _register(self, org_id, user, number="INV-APP-1", vendor=None, **extra):
        auth(self.client, user)
        payload = {
            "vendor": str(vendor.id if vendor else self.vendor_a.id),
            "invoice_number": number,
            "issue_date": "2026-10-01",
            "amount": "150.00",
            "currency": "USD",
        }
        payload.update(extra)
        return self.client.post(self.url_invoices(org_id), payload, format="json")

    def _policy_escalate(self, org_id):
        auth(self.client, self.finance)
        return self.client.post(
            self.url_policies(org_id),
            {"require_due_date": True, "require_description": False},
            format="json",
        )

    def _policy_block_currency(self, org_id):
        auth(self.client, self.finance)
        return self.client.post(
            self.url_policies(org_id),
            {"allowed_currencies": ["USD"]},
            format="json",
        )

    def _evaluate(self, org_id, invoice_id, user):
        auth(self.client, user)
        return self.client.post(self.url_evaluate(org_id, invoice_id))

    def _pending_invoice(self, number="INV-APP-1"):
        """Returns (org_id, invoice_id) of an invoice the engine escalated."""
        reg = self._register(self.org_a.id, self.creator, number=number)
        invoice_id = reg.data["id"]
        self._policy_escalate(self.org_a.id)
        ev = self._evaluate(self.org_a.id, invoice_id, self.evaluator)
        self.assertEqual(ev.status_code, 200, ev.data)
        self.assertEqual(ev.data["result"], PolicyDecision.Result.ESCALATED)
        return self.org_a.id, invoice_id

    def _decide(self, org_id, invoice_id, user, decision="approved"):
        auth(self.client, user)
        return self.client.post(
            self.url_approval(org_id, invoice_id), {"decision": decision}, format="json"
        )

    # --- 1/2 authorized approval and rejection ------------------------------
    def test_approver_can_approve_eligible_invoice(self):
        org_id, invoice_id = self._pending_invoice()
        inv = Invoice.objects.get(pk=invoice_id)
        self.assertEqual(inv.status, Invoice.Status.PENDING_APPROVAL)
        self.assertIsNotNone(inv.created_by)  # creator is registered
        resp = self._decide(org_id, invoice_id, self.approver, "approved")
        self.assertEqual(resp.status_code, 200, resp.data)
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.APPROVED)
        ap = InvoiceApproval.objects.get(invoice=inv)
        self.assertEqual(ap.decision, InvoiceApproval.Decision.APPROVED)
        self.assertEqual(ap.decided_by, self.approver)

    def test_approver_can_reject_eligible_invoice(self):
        org_id, invoice_id = self._pending_invoice()
        resp = self._decide(org_id, invoice_id, self.approver, "rejected")
        self.assertEqual(resp.status_code, 200, resp.data)
        inv = Invoice.objects.get(pk=invoice_id)
        self.assertEqual(inv.status, Invoice.Status.REJECTED)
        self.assertEqual(
            InvoiceApproval.objects.get(invoice=inv).decision,
            InvoiceApproval.Decision.REJECTED,
        )

    # --- 3 anonymity --------------------------------------------------------
    def test_anonymous_cannot_decide(self):
        self._pending_invoice()
        self.client.credentials()  # ensure the request is truly anonymous
        org_id = self.org_a.id
        invoice = Invoice.objects.get(invoice_number="INV-APP-1")
        resp = self.client.post(
            self.url_approval(org_id, str(invoice.id)),
            {"decision": "approved"},
            format="json",
        )
        self.assertEqual(resp.status_code, 401)

    # --- 4 only APPROVER role ----------------------------------------------
    def test_finance_operator_auditor_cannot_decide(self):
        org_id, invoice_id = self._pending_invoice()
        for u in (self.finance, self.operator, self.auditor):
            resp = self._decide(org_id, invoice_id, u, "approved")
            self.assertEqual(resp.status_code, 404, f"{u} should be denied")

    # --- 5/6 inactive membership / organization -----------------------------
    def test_inactive_membership_cannot_decide(self):
        org_id, invoice_id = self._pending_invoice()
        resp = self._decide(
            org_id, invoice_id, self.approver_inactive_membership, "approved"
        )
        self.assertEqual(resp.status_code, 404)

    def test_inactive_organization_cannot_be_used(self):
        auth(self.client, self.approver_inactive_org)
        resp = self.client.post(
            self.url_approval(self.org_inactive.id, uuid.uuid4()),
            {"decision": "approved"},
            format="json",
        )
        self.assertEqual(resp.status_code, 404)

    # --- 7 cross-organization isolation -------------------------------------
    def test_cross_org_invoice_cannot_be_decided(self):
        org_id, invoice_id = self._pending_invoice()
        # The APPROVER of org B tries to decide an org A invoice.
        auth(self.client, self.approver_other_org)
        resp = self.client.post(
            self.url_approval(org_id, invoice_id), {"decision": "approved"}, format="json"
        )
        self.assertEqual(resp.status_code, 404)
        # Referencing the id from org A through org B's URL also yields 404.
        resp2 = self.client.post(
            self.url_approval(self.org_b.id, invoice_id), {"decision": "approved"}, format="json"
        )
        self.assertEqual(resp2.status_code, 404)

    # --- 8/9 separation of duties -------------------------------------------
    def test_creator_cannot_approve_own_invoice(self):
        # APPROVER cannot even create invoices by API (creation is F/A+OPERATOR);
        # simulate a record whose creator is the approver.
        invoice = Invoice.objects.create(
            organization=self.org_a,
            vendor=self.vendor_a,
            invoice_number="INV-APP-8",
            issue_date="2026-10-01",
            amount="150.00",
            currency="USD",
            created_by=self.approver,
        )
        self._policy_escalate(self.org_a.id)
        ev = self._evaluate(self.org_a.id, str(invoice.id), self.evaluator)
        self.assertEqual(ev.status_code, 200, ev.data)
        resp = self._decide(self.org_a.id, str(invoice.id), self.approver, "approved")
        self.assertEqual(resp.status_code, 403)

    def test_evaluator_cannot_approve_invoice_they_evaluated(self):
        org_id, invoice_id = self._pending_invoice()
        # force: mark the approver as the evaluator to exercise the check
        decision = PolicyDecision.objects.get(invoice_id=invoice_id)
        decision.evaluated_by = self.approver
        decision.save(update_fields=["evaluated_by"])
        resp = self._decide(org_id, invoice_id, self.approver, "approved")
        self.assertEqual(resp.status_code, 403)

    # --- 10-11 blocked / invalid states -------------------------------------
    def test_blocked_invoice_cannot_be_approved(self):
        self._policy_block_currency(self.org_a.id)
        reg = self._register(self.org_a.id, self.creator, number="INV-APP-BLK", currency="EUR")
        invoice = Invoice.objects.get(invoice_number="INV-APP-BLK")
        ev = self._evaluate(self.org_a.id, str(invoice.id), self.evaluator)
        self.assertEqual(ev.status_code, 200)
        self.assertEqual(ev.data["result"], PolicyDecision.Result.BLOCKED)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.BLOCKED)
        resp = self._decide(self.org_a.id, str(invoice.id), self.approver, "approved")
        self.assertEqual(resp.status_code, 400)

    def test_deciding_an_already_approved_invoice_is_rejected(self):
        org_id, invoice_id = self._pending_invoice()
        self.assertEqual(self._decide(org_id, invoice_id, self.approver, "approved").status_code, 200)
        # second/contradictory decision
        resp = self._decide(org_id, invoice_id, self.approver, "rejected")
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_decision_requires_unique_per_invoice(self):
        # Even if the state were 'stale-pending', the DB unique rejects a second.
        org_id, invoice_id = self._pending_invoice()
        self.assertEqual(self._decide(org_id, invoice_id, self.approver, "approved").status_code, 200)
        with self.assertRaises(IntegrityError):
            InvoiceApproval.objects.create(
                invoice=Invoice.objects.get(pk=invoice_id),
                organization=self.org_a,
                decision=InvoiceApproval.Decision.REJECTED,
                decided_by=self.approver,
            )

    # --- 14 protected fields cannot be injected -----------------------------
    def test_protected_fields_cannot_be_injected(self):
        org_id, invoice_id = self._pending_invoice()
        auth(self.client, self.approver)
        resp = self.client.post(
            self.url_approval(org_id, invoice_id),
            {
                "decision": "approved",
                "decided_by": str(self.creator.id),
                "organization": str(self.org_b.id),
                "created_at": "2030-01-01T00:00:00Z",
                "id": str(uuid.uuid4()),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        ap = InvoiceApproval.objects.get(invoice_id=invoice_id)
        self.assertEqual(ap.decided_by, self.approver)  # not the injected value
        self.assertEqual(ap.organization, self.org_a)

    # --- 15 audit data -------------------------------------------------------
    def test_audit_records_actor_org_target_action(self):
        org_id, invoice_id = self._pending_invoice()
        self._decide(org_id, invoice_id, self.approver, "approved")
        event = AuditEvent.objects.get(
            target_id=invoice_id, action=AuditEvent.Action.INVOICE_APPROVED
        )
        self.assertEqual(event.actor, self.approver)
        self.assertEqual(event.organization, self.org_a)
        self.assertEqual(event.metadata["decision"], "approved")
        self.assertIn("approval_id", event.metadata)
        meta = str(event.metadata).lower()
        self.assertNotIn("password", meta)
        self.assertNotIn("token", meta)

    # --- 16 audit failure rolls back ----------------------------------------
    def test_audit_failure_rolls_back_decision_and_state(self):
        org_id, invoice_id = self._pending_invoice()
        auth(self.client, self.approver)
        client = APIClient(raise_request_exception=False)
        auth(client, self.approver)
        with mock.patch.object(
            AuditEvent.objects, "create", side_effect=RuntimeError("audit failed")
        ):
            resp = client.post(
                self.url_approval(org_id, invoice_id), {"decision": "approved"}, format="json"
            )
        self.assertEqual(resp.status_code, 500)
        inv = Invoice.objects.get(pk=invoice_id)
        self.assertEqual(inv.status, Invoice.Status.PENDING_APPROVAL)
        self.assertFalse(InvoiceApproval.objects.filter(invoice=inv).exists())

    # --- 17 legacy created_by NULL ------------------------------------------
    def test_legacy_invoice_without_creator_supported(self):
        invoice = Invoice.objects.create(
            organization=self.org_a,
            vendor=self.vendor_a,
            invoice_number="INV-APP-LEGACY",
            issue_date="2026-10-01",
            amount="100.00",
            currency="USD",
            created_by=None,
        )
        self.assertIsNone(invoice.created_by)
        self._policy_escalate(self.org_a.id)
        ev = self._evaluate(self.org_a.id, str(invoice.id), self.evaluator)
        self.assertEqual(ev.status_code, 200)
        self.assertEqual(ev.data["result"], PolicyDecision.Result.ESCALATED)
        resp = self._decide(self.org_a.id, str(invoice.id), self.approver, "approved")
        self.assertEqual(resp.status_code, 200, resp.data)

    # --- 18/19 approved & blocked engine outcomes unchanged -----------------
    def test_engine_approved_outcome_keeps_behavior(self):
        auth(self.client, self.finance)
        self.client.post(
            self.url_policies(self.org_a.id),
            {"allowed_currencies": ["USD"], "max_amount": "1000.00"},
            format="json",
        )
        reg = self._register(self.org_a.id, self.creator, number="INV-APP-OK", amount="100.00")
        invoice = Invoice.objects.get(invoice_number="INV-APP-OK")
        ev = self._evaluate(self.org_a.id, str(invoice.id), self.evaluator)
        self.assertEqual(ev.status_code, 200)
        self.assertEqual(ev.data["result"], PolicyDecision.Result.APPROVED)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.APPROVED)  # engine-approved stays
        self.assertFalse(InvoiceApproval.objects.filter(invoice=invoice).exists())

    # --- 20 escalated -> pending --------------------------------------------
    def test_escalated_enters_human_workflow(self):
        org_id, invoice_id = self._pending_invoice()
        inv = Invoice.objects.get(pk=invoice_id)
        self.assertEqual(inv.status, Invoice.Status.PENDING_APPROVAL)
        self.assertEqual(
            PolicyDecision.objects.get(invoice=inv).result, PolicyDecision.Result.ESCALATED
        )

    # --- 21 duplicate evaluation still protected ----------------------------
    def test_duplicate_evaluation_still_conflicts(self):
        org_id, invoice_id = self._pending_invoice()
        resp = self._evaluate(self.org_a.id, invoice_id, self.evaluator)
        self.assertEqual(resp.status_code, 409)

    # --- 22 malformed decision value ----------------------------------------
    def test_invalid_decision_value_rejected(self):
        org_id, invoice_id = self._pending_invoice()
        auth(self.client, self.approver)
        resp = self.client.post(
            self.url_approval(org_id, invoice_id), {"decision": "superchau"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)


class ApprovalIsolationWithBOrgTests(TestCase):
    """Cross-organization approval from a creator in org A."""

    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organization.objects.create(name="Isol A")
        cls.org_b = Organization.objects.create(name="Isol B")
        cls.approver = User.objects.create_user(username="iso_ap", password="x")
        cls.creator = User.objects.create_user(username="iso_cr", password="x")
        cls.evaluator = User.objects.create_user(username="iso_ev", password="x")
        cls.finance = User.objects.create_user(username="iso_fi", password="x")
        OrganizationMembership.objects.create(
            user=cls.approver, organization=cls.org_a, role=OrganizationRole.APPROVER
        )
        OrganizationMembership.objects.create(
            user=cls.creator, organization=cls.org_a, role=OrganizationRole.OPERATOR
        )
        OrganizationMembership.objects.create(
            user=cls.evaluator, organization=cls.org_a, role=OrganizationRole.OPERATOR
        )
        OrganizationMembership.objects.create(
            user=cls.finance, organization=cls.org_a, role=OrganizationRole.FINANCE_ADMIN
        )
        cls.vendor_a = Vendor.objects.create(
            organization=cls.org_a, legal_name="Is-A", tax_id="ISO-A-1"
        )

    def setUp(self):
        self.client = APIClient()

    def test_org_b_user_cannot_act_on_org_a_invoice(self):
        # anonymous header can't reach it; a user with no membership in A -> 404
        auth(self.client, self.approver)
        resp = self.client.post(
            f"/api/v1/organizations/{self.org_a.id}/invoices/{uuid.uuid4()}/approval/",
            {"decision": "approved"},
            format="json",
        )
        self.assertEqual(resp.status_code, 404)