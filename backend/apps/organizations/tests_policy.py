"""Integration tests for the deterministic invoice policy engine
(Phase 2, Slice 6). Real API requests with real token authentication.

Covers policy versioning and validation, every evaluation outcome with its
reason code, precedence and strict comparisons, no-policy and internal-error
fail-safes, org isolation, roles, repeated-evaluation protection, decision
persistence with the rules snapshot, audit, and rollback. The only mocks
target AuditEvent.objects.create and evaluate_invoice to prove fail-safe
behavior.
"""

import uuid
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIClient

from .models import (
    AuditEvent,
    Invoice,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    Policy,
    PolicyDecision,
    Vendor,
)

User = get_user_model()


def auth(client, user):
    """Authenticate through the real JWT pipeline."""
    access = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


class PolicyEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organization.objects.create(name="Policy Org A")
        cls.org_b = Organization.objects.create(name="Policy Org B")
        cls.org_inactive = Organization.objects.create(
            name="Policy Org Inactive", status=Organization.Status.INACTIVE
        )
        cls.admin_a = User.objects.create_user(username="p_admin_a", password="x")
        cls.operator_a = User.objects.create_user(username="p_operator_a", password="x")
        cls.approver_a = User.objects.create_user(username="p_approver_a", password="x")
        cls.auditor_a = User.objects.create_user(username="p_auditor_a", password="x")
        cls.member_a = User.objects.create_user(username="p_member_a", password="x")
        cls.admin_b = User.objects.create_user(username="p_admin_b", password="x")
        cls.admin_inactive = User.objects.create_user(
            username="p_admin_inactive", password="x"
        )
        cls.superuser = User.objects.create_superuser(username="p_root", password="x")
        cls.nomember = User.objects.create_user(username="p_nomember", password="x")

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
        cls.v_b = Vendor.objects.create(
            organization=cls.org_b, legal_name="Acme B", tax_id="ACME-1"
        )
        cls.inv_received = Invoice.objects.create(
            organization=cls.org_a,
            vendor=cls.v_active,
            invoice_number="INV-100",
            issue_date="2026-10-01",
            amount="100.00",
            currency="USD",
        )
        cls.inv_evaluated = Invoice.objects.create(
            organization=cls.org_a,
            vendor=cls.v_active,
            invoice_number="INV-200",
            issue_date="2026-10-01",
            amount="50.00",
            currency="USD",
            status=Invoice.Status.APPROVED,
        )
        PolicyDecision.objects.create(
            organization=cls.org_a,
            invoice=cls.inv_evaluated,
            result=PolicyDecision.Result.APPROVED,
            reason_code="policy_ok",
            evaluated_by=cls.admin_a,
        )

    def setUp(self):
        self.client = APIClient()

    def url_policies(self, org_id):
        return f"/api/v1/organizations/{org_id}/policies/"

    def url_policy(self, org_id, policy_id):
        return f"/api/v1/organizations/{org_id}/policies/{policy_id}/"

    def url_evaluate(self, org_id, invoice_id):
        return f"/api/v1/organizations/{org_id}/invoices/{invoice_id}/evaluate/"

    def url_decision(self, org_id, invoice_id):
        return f"/api/v1/organizations/{org_id}/invoices/{invoice_id}/decision/"

    def policy_payload(self, **overrides):
        data = {
            "allowed_currencies": ["USD"],
            "max_amount": "1000.00",
            "escalation_threshold": "500.00",
            "require_due_date": False,
            "require_description": False,
        }
        data.update(overrides)
        return data

    def _create_policy(self, org, **overrides):
        return Policy.objects.create(
            organization=org, version=1, **self.policy_payload(**overrides)
        )

    # --- authentication gates -------------------------------------------------
    def test_anonymous_denied_everywhere(self):
        self.assertEqual(self.client.get(self.url_policies(self.org_a.id)).status_code, 401)
        self.assertEqual(
            self.client.post(
                self.url_policies(self.org_a.id), self.policy_payload(), format="json"
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(self.url_evaluate(self.org_a.id, self.inv_received.id)).status_code,
            401,
        )
        self.assertEqual(
            self.client.get(self.url_decision(self.org_a.id, self.inv_received.id)).status_code,
            401,
        )

    # --- policy management -----------------------------------------------------
    def test_finance_admin_creates_policy_version_1(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_policies(self.org_a.id), self.policy_payload(), format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["version"], 1)
        self.assertTrue(response.data["is_active"])

    def test_new_policy_version_deactivates_previous(self):
        auth(self.client, self.admin_a)
        self.client.post(
            self.url_policies(self.org_a.id), self.policy_payload(), format="json"
        )
        response = self.client.post(
            self.url_policies(self.org_a.id),
            self.policy_payload(max_amount="2000.00"),
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["version"], 2)
        self.assertTrue(response.data["is_active"])
        v1 = Policy.objects.get(organization=self.org_a, version=1)
        self.assertFalse(v1.is_active)
        active = Policy.objects.filter(organization=self.org_a, is_active=True)
        self.assertEqual(active.count(), 1)

    def test_only_finance_admin_creates_policy(self):
        for user in (self.operator_a, self.approver_a, self.auditor_a, self.nomember):
            auth(self.client, user)
            response = self.client.post(
                self.url_policies(self.org_a.id), self.policy_payload(), format="json"
            )
            self.assertEqual(response.status_code, 404)

    def test_member_reads_policies(self):
        self._create_policy(self.org_a)
        auth(self.client, self.member_a)
        self.assertEqual(self.client.get(self.url_policies(self.org_a.id)).status_code, 200)
        policy = Policy.objects.get(organization=self.org_a, version=1)
        self.assertEqual(
            self.client.get(self.url_policy(self.org_a.id, policy.id)).status_code, 200
        )

    def test_cross_org_policy_read_blocked(self):
        self._create_policy(self.org_a)
        auth(self.client, self.admin_b)
        self.assertEqual(self.client.get(self.url_policies(self.org_a.id)).status_code, 404)
        policy = Policy.objects.get(organization=self.org_a, version=1)
        self.assertEqual(
            self.client.get(self.url_policy(self.org_a.id, policy.id)).status_code, 404
        )

    def test_policy_validation(self):
        auth(self.client, self.admin_a)
        self.assertEqual(
            self.client.post(
                self.url_policies(self.org_a.id),
                self.policy_payload(max_amount="0.00"),
                format="json",
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                self.url_policies(self.org_a.id),
                self.policy_payload(escalation_threshold="-1.00"),
                format="json",
            ).status_code,
            400,
        )
        # Coherence: escalation_threshold must not exceed max_amount.
        self.assertEqual(
            self.client.post(
                self.url_policies(self.org_a.id),
                self.policy_payload(max_amount="100.00", escalation_threshold="200.00"),
                format="json",
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                self.url_policies(self.org_a.id),
                self.policy_payload(allowed_currencies=["XYZ"]),
                format="json",
            ).status_code,
            400,
        )

    # --- evaluation outcomes ---------------------------------------------------
    def test_evaluate_approved_policy_ok(self):
        self._create_policy(self.org_a)
        auth(self.client, self.admin_a)
        response = self.client.post(self.url_evaluate(self.org_a.id, self.inv_received.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], PolicyDecision.Result.APPROVED)
        self.assertEqual(response.data["reason_code"], "policy_ok")
        self.inv_received.refresh_from_db()
        self.assertEqual(self.inv_received.status, Invoice.Status.APPROVED)

    def test_evaluate_blocked_currency_not_allowed(self):
        self._create_policy(self.org_a, allowed_currencies=["USD"])
        invoice = Invoice.objects.create(
            organization=self.org_a,
            vendor=self.v_active,
            invoice_number="INV-300",
            issue_date="2026-10-01",
            amount="10.00",
            currency="EUR",
        )
        auth(self.client, self.admin_a)
        response = self.client.post(self.url_evaluate(self.org_a.id, invoice.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], PolicyDecision.Result.BLOCKED)
        self.assertEqual(response.data["reason_code"], "currency_not_allowed")

    def test_evaluate_blocked_amount_exceeds_max(self):
        self._create_policy(self.org_a, max_amount="100.00")
        invoice = Invoice.objects.create(
            organization=self.org_a,
            vendor=self.v_active,
            invoice_number="INV-301",
            issue_date="2026-10-01",
            amount="150.00",
            currency="USD",
        )
        auth(self.client, self.admin_a)
        response = self.client.post(self.url_evaluate(self.org_a.id, invoice.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], PolicyDecision.Result.BLOCKED)
        self.assertEqual(response.data["reason_code"], "amount_exceeds_max")

    def test_evaluate_escalated_amount_exceeds_threshold(self):
        self._create_policy(self.org_a, max_amount="1000.00", escalation_threshold="100.00")
        invoice = Invoice.objects.create(
            organization=self.org_a,
            vendor=self.v_active,
            invoice_number="INV-302",
            issue_date="2026-10-01",
            amount="150.00",
            currency="USD",
        )
        auth(self.client, self.admin_a)
        response = self.client.post(self.url_evaluate(self.org_a.id, invoice.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], PolicyDecision.Result.ESCALATED)
        self.assertEqual(response.data["reason_code"], "amount_exceeds_escalation_threshold")

    def test_evaluate_escalated_due_date_missing(self):
        self._create_policy(self.org_a, require_due_date=True)
        invoice = Invoice.objects.create(
            organization=self.org_a,
            vendor=self.v_active,
            invoice_number="INV-303",
            issue_date="2026-10-01",
            amount="10.00",
            currency="USD",
        )
        auth(self.client, self.admin_a)
        response = self.client.post(self.url_evaluate(self.org_a.id, invoice.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], PolicyDecision.Result.ESCALATED)
        self.assertEqual(response.data["reason_code"], "due_date_missing")

    def test_evaluate_escalated_description_missing(self):
        self._create_policy(self.org_a, require_description=True)
        invoice = Invoice.objects.create(
            organization=self.org_a,
            vendor=self.v_active,
            invoice_number="INV-304",
            issue_date="2026-10-01",
            amount="10.00",
            currency="USD",
        )
        auth(self.client, self.admin_a)
        response = self.client.post(self.url_evaluate(self.org_a.id, invoice.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], PolicyDecision.Result.ESCALATED)
        self.assertEqual(response.data["reason_code"], "description_missing")

    def test_evaluate_no_active_policy_escalates_never_approves(self):
        auth(self.client, self.admin_a)
        response = self.client.post(self.url_evaluate(self.org_a.id, self.inv_received.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], PolicyDecision.Result.ESCALATED)
        self.assertEqual(response.data["reason_code"], "no_active_policy")
        self.inv_received.refresh_from_db()
        # Engine decision stays 'escalated'; the invoice enters the human
        # approval workflow as pending_approval.
        self.assertEqual(self.inv_received.status, Invoice.Status.PENDING_APPROVAL)

    def test_evaluate_precedence_blocked_before_escalated(self):
        # amount > max_amount AND > escalation_threshold -> blocked, not escalated.
        self._create_policy(self.org_a, max_amount="100.00", escalation_threshold="50.00")
        invoice = Invoice.objects.create(
            organization=self.org_a,
            vendor=self.v_active,
            invoice_number="INV-305",
            issue_date="2026-10-01",
            amount="150.00",
            currency="USD",
        )
        auth(self.client, self.admin_a)
        response = self.client.post(self.url_evaluate(self.org_a.id, invoice.id))
        self.assertEqual(response.data["result"], PolicyDecision.Result.BLOCKED)
        self.assertEqual(response.data["reason_code"], "amount_exceeds_max")

    def test_evaluate_strict_comparison_at_max_amount(self):
        # amount == max_amount is NOT blocked (strict >).
        self._create_policy(self.org_a, max_amount="100.00")
        invoice = Invoice.objects.create(
            organization=self.org_a,
            vendor=self.v_active,
            invoice_number="INV-306",
            issue_date="2026-10-01",
            amount="100.00",
            currency="USD",
        )
        auth(self.client, self.admin_a)
        response = self.client.post(self.url_evaluate(self.org_a.id, invoice.id))
        self.assertEqual(response.data["result"], PolicyDecision.Result.APPROVED)

    def test_evaluate_amount_equal_to_escalation_threshold_is_approved(self):
        # amount == escalation_threshold is NOT escalated (strict >), so a
        # compliant invoice at exactly the threshold is approved.
        self._create_policy(
            self.org_a, max_amount="1000.00", escalation_threshold="500.00"
        )
        invoice = Invoice.objects.create(
            organization=self.org_a,
            vendor=self.v_active,
            invoice_number="INV-308",
            issue_date="2026-10-01",
            amount="500.00",
            currency="USD",
        )
        auth(self.client, self.admin_a)
        response = self.client.post(self.url_evaluate(self.org_a.id, invoice.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], PolicyDecision.Result.APPROVED)
        self.assertEqual(response.data["reason_code"], "policy_ok")

    def test_evaluate_threshold_equal_to_max_amount_equal_amount_is_approved(
        self,
    ):
        # escalation_threshold == max_amount and amount == max_amount: neither
        # strict comparison fires, so the invoice is approved — "exceeds the
        # maximum" only ever blocks when the maximum is really exceeded.
        self._create_policy(
            self.org_a, max_amount="100.00", escalation_threshold="100.00"
        )
        invoice = Invoice.objects.create(
            organization=self.org_a,
            vendor=self.v_active,
            invoice_number="INV-309",
            issue_date="2026-10-01",
            amount="100.00",
            currency="USD",
        )
        auth(self.client, self.admin_a)
        response = self.client.post(self.url_evaluate(self.org_a.id, invoice.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], PolicyDecision.Result.APPROVED)
        self.assertEqual(response.data["reason_code"], "policy_ok")
        # Contrast under the same policy: the smallest excess blocks.
        invoice_above = Invoice.objects.create(
            organization=self.org_a,
            vendor=self.v_active,
            invoice_number="INV-310",
            issue_date="2026-10-01",
            amount="100.01",
            currency="USD",
        )
        response = self.client.post(
            self.url_evaluate(self.org_a.id, invoice_above.id)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], PolicyDecision.Result.BLOCKED)
        self.assertEqual(response.data["reason_code"], "amount_exceeds_max")

    def test_evaluate_empty_currencies_means_no_restriction(self):
        self._create_policy(self.org_a, allowed_currencies=[])
        invoice = Invoice.objects.create(
            organization=self.org_a,
            vendor=self.v_active,
            invoice_number="INV-307",
            issue_date="2026-10-01",
            amount="10.00",
            currency="EUR",
        )
        auth(self.client, self.admin_a)
        response = self.client.post(self.url_evaluate(self.org_a.id, invoice.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], PolicyDecision.Result.APPROVED)

    # --- fail-safe behavior ---------------------------------------------------
    def test_evaluate_internal_error_500_no_effects(self):
        self._create_policy(self.org_a)
        auth(self.client, self.admin_a)
        with mock.patch(
            "apps.organizations.views.evaluate_invoice",
            side_effect=RuntimeError("boom"),
        ):
            response = self.client.post(
                self.url_evaluate(self.org_a.id, self.inv_received.id)
            )
        self.assertEqual(response.status_code, 500)
        # Exact fail-safe body: no traceback, no internal detail, no extras.
        self.assertEqual(response.data, {"detail": "Internal server error."})
        self.inv_received.refresh_from_db()
        self.assertEqual(self.inv_received.status, Invoice.Status.RECEIVED)
        self.assertFalse(
            PolicyDecision.objects.filter(invoice=self.inv_received).exists()
        )

    def test_evaluate_audit_failure_rolls_back_everything(self):
        self._create_policy(self.org_a)
        client = APIClient(raise_request_exception=False)
        auth(client, self.admin_a)
        with mock.patch.object(
            AuditEvent.objects, "create", side_effect=RuntimeError("audit failed")
        ):
            response = client.post(
                self.url_evaluate(self.org_a.id, self.inv_received.id)
            )
        self.assertEqual(response.status_code, 500)
        self.inv_received.refresh_from_db()
        self.assertEqual(self.inv_received.status, Invoice.Status.RECEIVED)
        self.assertFalse(
            PolicyDecision.objects.filter(invoice=self.inv_received).exists()
        )

    # --- isolation and roles ---------------------------------------------------
    def test_evaluate_cross_org_invoice_blocked(self):
        self._create_policy(self.org_a)
        auth(self.client, self.admin_b)
        self.assertEqual(
            self.client.post(self.url_evaluate(self.org_a.id, self.inv_received.id)).status_code,
            404,
        )

    def test_uniform_404_detail_for_foreign_and_unknown_organization(self):
        # A non-member sees the same public 404 body for an organization that
        # does not exist and for an existing organization it cannot access
        # (HidingByNotExisting: no existence disclosure via error text).
        self._create_policy(self.org_a)
        auth(self.client, self.admin_b)  # FINANCE_ADMIN of org_b, not org_a
        unknown_org = self.client.get(
            f"/api/v1/organizations/{uuid.uuid4()}/policies/"
        )
        foreign_org = self.client.get(self.url_policies(self.org_a.id))
        self.assertEqual(unknown_org.status_code, 404)
        self.assertEqual(foreign_org.status_code, 404)
        self.assertEqual(unknown_org.data, foreign_org.data)
        self.assertEqual(unknown_org.data, {"detail": "Organization not found."})

    def test_evaluate_roles_operator_triggers_engine_decides(self):
        self._create_policy(self.org_a)
        auth(self.client, self.operator_a)
        response = self.client.post(self.url_evaluate(self.org_a.id, self.inv_received.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], PolicyDecision.Result.APPROVED)

    def test_evaluate_approver_and_auditor_cannot_trigger(self):
        self._create_policy(self.org_a)
        for user in (self.approver_a, self.auditor_a):
            auth(self.client, user)
            self.assertEqual(
                self.client.post(
                    self.url_evaluate(self.org_a.id, self.inv_received.id)
                ).status_code,
                404,
            )

    def test_evaluate_inactive_org_rejected(self):
        auth(self.client, self.admin_inactive)
        self.assertEqual(
            self.client.post(self.url_evaluate(self.org_inactive.id, uuid.uuid4())).status_code,
            404,
        )

    # --- repeated evaluation and state machine --------------------------------
    def test_evaluate_repeated_evaluation_conflict(self):
        self._create_policy(self.org_a)
        auth(self.client, self.admin_a)
        self.assertEqual(
            self.client.post(self.url_evaluate(self.org_a.id, self.inv_received.id)).status_code,
            200,
        )
        response = self.client.post(self.url_evaluate(self.org_a.id, self.inv_received.id))
        self.assertEqual(response.status_code, 409)

    def test_evaluate_already_evaluated_invoice_conflict(self):
        self._create_policy(self.org_a)
        auth(self.client, self.admin_a)
        response = self.client.post(self.url_evaluate(self.org_a.id, self.inv_evaluated.id))
        self.assertEqual(response.status_code, 409)

    def test_evaluate_does_not_change_invoice_business_data(self):
        self._create_policy(self.org_a)
        auth(self.client, self.admin_a)
        # Capture the persisted state (Decimal fields are coerced from the
        # string they were created with the moment they are read back).
        self.inv_received.refresh_from_db()
        before = {
            "amount": self.inv_received.amount,
            "currency": self.inv_received.currency,
            "vendor_id": self.inv_received.vendor_id,
            "invoice_number": self.inv_received.invoice_number,
            "id": self.inv_received.id,
        }
        self.client.post(self.url_evaluate(self.org_a.id, self.inv_received.id))
        self.inv_received.refresh_from_db()
        self.assertEqual(self.inv_received.amount, before["amount"])
        self.assertEqual(self.inv_received.currency, before["currency"])
        self.assertEqual(self.inv_received.vendor_id, before["vendor_id"])
        self.assertEqual(self.inv_received.invoice_number, before["invoice_number"])
        self.assertEqual(self.inv_received.id, before["id"])

    # --- decision persistence and reads ---------------------------------------
    def test_decision_persisted_with_snapshot(self):
        policy = self._create_policy(self.org_a, max_amount="1000.00")
        auth(self.client, self.admin_a)
        self.client.post(self.url_evaluate(self.org_a.id, self.inv_received.id))
        decision = PolicyDecision.objects.get(invoice=self.inv_received)
        self.assertEqual(decision.result, PolicyDecision.Result.APPROVED)
        self.assertEqual(decision.reason_code, "policy_ok")
        self.assertEqual(decision.policy_id, policy.id)
        self.assertEqual(decision.policy_version, 1)
        self.assertEqual(decision.evaluated_by, self.admin_a)
        self.assertEqual(decision.rules_snapshot["version"], 1)
        self.assertEqual(decision.rules_snapshot["max_amount"], "1000.00")
        self.assertEqual(decision.rules_snapshot["allowed_currencies"], ["USD"])

    def test_decision_snapshot_unchanged_after_new_policy_version(self):
        # A recorded decision is immutable: creating policy v2 never alters
        # the id, version, or rules snapshot pinned from v1.
        policy_v1 = self._create_policy(self.org_a, max_amount="1000.00")
        auth(self.client, self.admin_a)
        self.client.post(self.url_evaluate(self.org_a.id, self.inv_received.id))
        decision = PolicyDecision.objects.get(invoice=self.inv_received)
        self.client.post(
            self.url_policies(self.org_a.id),
            self.policy_payload(max_amount="2000.00"),
            format="json",
        )
        policy_v2 = Policy.objects.get(organization=self.org_a, version=2)
        self.assertNotEqual(policy_v2.id, policy_v1.id)
        policy_v1.refresh_from_db()
        self.assertFalse(policy_v1.is_active)
        decision.refresh_from_db()
        self.assertEqual(decision.policy_id, policy_v1.id)
        self.assertEqual(decision.policy_version, 1)
        self.assertEqual(decision.rules_snapshot["version"], 1)
        self.assertEqual(decision.rules_snapshot["max_amount"], "1000.00")
        self.assertEqual(
            decision.rules_snapshot["escalation_threshold"], "500.00"
        )
        self.assertEqual(decision.rules_snapshot["allowed_currencies"], ["USD"])
        self.assertFalse(decision.rules_snapshot["require_due_date"])
        self.assertFalse(decision.rules_snapshot["require_description"])

    def test_decision_read_by_any_active_member(self):
        self._create_policy(self.org_a)
        auth(self.client, self.admin_a)
        self.client.post(self.url_evaluate(self.org_a.id, self.inv_received.id))
        auth(self.client, self.member_a)
        response = self.client.get(self.url_decision(self.org_a.id, self.inv_received.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], PolicyDecision.Result.APPROVED)
        self.assertEqual(response.data["reason_code"], "policy_ok")

    def test_decision_read_cross_org_blocked(self):
        self._create_policy(self.org_a)
        auth(self.client, self.admin_a)
        self.client.post(self.url_evaluate(self.org_a.id, self.inv_received.id))
        auth(self.client, self.admin_b)
        self.assertEqual(
            self.client.get(self.url_decision(self.org_a.id, self.inv_received.id)).status_code,
            404,
        )

    def test_decision_read_unknown_invoice_404(self):
        auth(self.client, self.member_a)
        self.assertEqual(
            self.client.get(self.url_decision(self.org_a.id, uuid.uuid4())).status_code,
            404,
        )

    # --- audit -----------------------------------------------------------------
    def test_audit_event_recorded_with_safe_metadata(self):
        policy = self._create_policy(self.org_a)
        auth(self.client, self.admin_a)
        self.client.post(self.url_evaluate(self.org_a.id, self.inv_received.id))
        event = AuditEvent.objects.get(
            target_id=str(self.inv_received.id),
            action=AuditEvent.Action.INVOICE_EVALUATED,
        )
        self.assertEqual(event.actor, self.admin_a)
        self.assertEqual(event.organization, self.org_a)
        self.assertEqual(event.metadata["result"], PolicyDecision.Result.APPROVED)
        self.assertEqual(event.metadata["reason_code"], "policy_ok")
        self.assertEqual(event.metadata["policy_version"], 1)
        self.assertIn("decision_id", event.metadata)
        meta = str(event.metadata).lower()
        self.assertNotIn("password", meta)
        self.assertNotIn("secret", meta)

    def test_policy_creation_audited(self):
        auth(self.client, self.admin_a)
        self.client.post(
            self.url_policies(self.org_a.id), self.policy_payload(), format="json"
        )
        policy = Policy.objects.get(organization=self.org_a, version=1)
        event = AuditEvent.objects.get(
            target_id=str(policy.id), action=AuditEvent.Action.POLICY_CREATED
        )
        self.assertEqual(event.actor, self.admin_a)
        self.assertEqual(event.metadata["version"], 1)

    # --- database backstop -----------------------------------------------------
    def test_one_decision_per_invoice_enforced_at_database(self):
        with self.assertRaises(IntegrityError):
            PolicyDecision.objects.create(
                organization=self.org_a,
                invoice=self.inv_evaluated,
                result=PolicyDecision.Result.APPROVED,
                reason_code="policy_ok",
                evaluated_by=self.admin_a,
            )

    # --- malformed / unknown ---------------------------------------------------
    def test_malformed_uuid_returns_404(self):
        auth(self.client, self.admin_a)
        self.assertEqual(
            self.client.post(self.url_evaluate(self.org_a.id, "not-a-uuid")).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(self.url_decision(self.org_a.id, "not-a-uuid")).status_code,
            404,
        )
