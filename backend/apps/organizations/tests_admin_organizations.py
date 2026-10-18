"""Integration tests for the global organization administration (final slice).

Covers the superuser-only surface: list, create (with initial FINANCE_ADMIN),
retrieve, update administrative fields, activate/deactivate, candidate-user
lookup, plus the mandated security invariants (anonymous/normal/FINANCE_ADMIN
denied, no client-supplied global privileges, atomic creation with audit
rollback, tenant isolation, inactive accounts, controlled errors, existing
superuser preserved, regression on prior routes). Uses real HTTP requests
through the real JWT pipeline — no authorization mocks.
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    AuditEvent,
    Invoice,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    PasswordSetupToken,
    Vendor,
)

User = get_user_model()

ADMIN_LIST = "/api/v1/admin/organizations/"
ADMIN_USERS = "/api/v1/admin/users/"


def auth(client, user):
    """Authenticate through the real JWT pipeline (same as tests.py)."""
    access = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


class GlobalOrganizationAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organization.objects.create(name="Org A")
        cls.org_b = Organization.objects.create(name="Org B")
        cls.org_inactive = Organization.objects.create(
            name="Org Inactive", status=Organization.Status.INACTIVE
        )

        cls.alice = User.objects.create_user(username="alice", email="alice@example.com", password="x")
        cls.bob = User.objects.create_user(username="bob", password="x")
        cls.normal = User.objects.create_user(username="normal", password="x")
        cls.finance = User.objects.create_user(username="finance", password="x")
        cls.inactive_user = User.objects.create_user(
            username="inactive-user", password="x", is_active=False
        )
        cls.root = User.objects.create_superuser(
            username="root@example.com", email="root@example.com", password="x"
        )

        # finance: FINANCE_ADMIN in org A; bob: APPROVER in org A.
        OrganizationMembership.objects.create(
            user=cls.finance, organization=cls.org_a, role=OrganizationRole.FINANCE_ADMIN
        )
        OrganizationMembership.objects.create(
            user=cls.bob, organization=cls.org_a, role=OrganizationRole.APPROVER
        )
        # supplier data on org A so tenant isolation can be asserted.
        Vendor.objects.create(
            organization=cls.org_a, legal_name="Acme", tax_id="ACME-1"
        )

    def setUp(self):
        self.client = APIClient()

    # --- 1-3. Anonymous / normal / FINANCE_ADMIN are denied ------------------
    def test_anonymous_cannot_list_or_create_organizations(self):
        response = self.client.get(ADMIN_LIST)
        self.assertEqual(response.status_code, 401)
        response = self.client.post(
            ADMIN_LIST,
            {"name": "Ghost Org", "admin_email": "ghost@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_normal_user_cannot_access_global_admin(self):
        auth(self.client, self.normal)
        response = self.client.get(ADMIN_LIST)
        self.assertEqual(response.status_code, 404)
        response = self.client.get(ADMIN_USERS)
        self.assertEqual(response.status_code, 404)

    def test_finance_admin_cannot_create_or_modify_other_organizations(self):
        auth(self.client, self.finance)
        # List: same uniform 404 as a normal user — membership in one org
        # grants no cross-tenant authority and never discloses the surface.
        self.assertEqual(self.client.get(ADMIN_LIST).status_code, 404)
        response = self.client.post(
            ADMIN_LIST,
            {"name": "Rogue Org", "admin_email": "rogue@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        response = self.client.patch(
            f"/api/v1/admin/organizations/{self.org_b.id}/",
            {"status": Organization.Status.INACTIVE},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.org_b.refresh_from_db()
        self.assertEqual(self.org_b.status, Organization.Status.ACTIVE)

    # --- 4. Superadmin can run the allowed operations -----------------------
    def test_superadmin_lists_and_retrieves_organizations(self):
        auth(self.client, self.root)
        response = self.client.get(ADMIN_LIST)
        self.assertEqual(response.status_code, 200)
        names = {item["name"] for item in response.data}
        self.assertIn("Org A", names)
        self.assertIn("Org Inactive", names)

        response = self.client.get(f"/api/v1/admin/organizations/{self.org_b.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Org B")
        self.assertEqual(response.data["status"], Organization.Status.ACTIVE)

    def test_superadmin_updates_name_and_status_with_audit(self):
        auth(self.client, self.root)
        response = self.client.patch(
            f"/api/v1/admin/organizations/{self.org_b.id}/",
            {"name": "Org B renamed", "status": Organization.Status.ACTIVE},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.org_b.refresh_from_db()
        self.assertEqual(self.org_b.name, "Org B renamed")

        events = AuditEvent.objects.filter(
            organization=self.org_b, action=AuditEvent.Action.ORGANIZATION_UPDATED
        )
        self.assertTrue(events.exists())
        self.assertEqual(events.first().actor, self.root)

    def test_superadmin_activates_and_deactivates_organization(self):
        auth(self.client, self.root)
        response = self.client.patch(
            f"/api/v1/admin/organizations/{self.org_b.id}/",
            {"status": Organization.Status.INACTIVE},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.org_b.refresh_from_db()
        self.assertEqual(self.org_b.status, Organization.Status.INACTIVE)
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.org_b,
                action=AuditEvent.Action.ORGANIZATION_DEACTIVATED,
            ).exists()
        )

        response = self.client.patch(
            f"/api/v1/admin/organizations/{self.org_b.id}/",
            {"status": Organization.Status.ACTIVE},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.org_b.refresh_from_db()
        self.assertEqual(self.org_b.status, Organization.Status.ACTIVE)
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.org_b,
                action=AuditEvent.Action.ORGANIZATION_ACTIVATED,
            ).exists()
        )

    # --- 5. Client cannot assign global privileges or arbitrary roles --------
    def test_client_cannot_assign_global_privileges_or_roles(self):
        auth(self.client, self.root)
        response = self.client.post(
            ADMIN_LIST,
            {
                "name": "Privilege Org",
                "admin_email": "privilege-admin@example.com",
                "is_superuser": True,
                "is_staff": True,
                "role": OrganizationRole.OPERATOR,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)  # extra fields are ignored
        admin = User.objects.get(username="privilege-admin@example.com")
        self.assertFalse(admin.is_superuser)
        self.assertFalse(admin.is_staff)
        membership = OrganizationMembership.objects.get(
            user=admin, organization__name="Privilege Org"
        )
        # The role is fixed server-side to FINANCE_ADMIN — never client-chosen.
        self.assertEqual(membership.role, OrganizationRole.FINANCE_ADMIN)
        self.assertEqual(response.data["admin_role"], OrganizationRole.FINANCE_ADMIN)

    # --- 6. Organization + initial membership are created atomically ---------
    def test_create_organization_creates_initial_finance_admin_membership(self):
        auth(self.client, self.root)
        response = self.client.post(
            ADMIN_LIST,
            {"name": "Fresh Org", "admin_email": "fresh-admin@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        organization = Organization.objects.get(name="Fresh Org")
        admin = User.objects.get(username="fresh-admin@example.com")
        membership = OrganizationMembership.objects.get(
            organization=organization, user=admin
        )
        self.assertEqual(membership.role, OrganizationRole.FINANCE_ADMIN)
        self.assertTrue(membership.is_active)
        # Audits for org + membership + account (and a setup invitation) exist.
        actions = set(
            AuditEvent.objects.filter(
                organization=organization
            ).values_list("action", flat=True)
        )
        self.assertIn(AuditEvent.Action.ORGANIZATION_CREATED, actions)
        self.assertIn(AuditEvent.Action.MEMBERSHIP_CREATED, actions)
        self.assertIn(AuditEvent.Action.INVITATION_ISSUED, actions)
        # The account-created audit records the actor with no organization
        # context (the account predates the tenant).
        self.assertTrue(
            AuditEvent.objects.filter(
                actor=self.root, action=AuditEvent.Action.ACCOUNT_CREATED
            ).exists()
        )
        # A fresh account has an unusable password and one usable setup token.
        self.assertFalse(admin.has_usable_password())
        self.assertEqual(
            PasswordSetupToken.objects.filter(
                user=admin, used_at__isnull=True
            ).count(),
            1,
        )
        self.assertIn("setup_token", response.data)

    # --- 7. Audit failure rolls the whole creation back ----------------------
    def test_audit_failure_rolls_back_organization_creation(self):
        auth(self.client, self.root)
        # Surface the 500 instead of letting Django's test client re-raise.
        self.client.raise_request_exception = False

        def boom(**kwargs):
            raise RuntimeError("audit failure")

        with mock.patch("apps.organizations.views._audit", side_effect=boom):
            response = self.client.post(
                ADMIN_LIST,
                {"name": "Doomed Org", "admin_email": "doomed@example.com"},
                format="json",
            )
        self.assertEqual(response.status_code, 500)
        # Nothing survives: no partial organization, no orphan account.
        self.assertFalse(Organization.objects.filter(name="Doomed Org").exists())
        self.assertFalse(
            User.objects.filter(username="doomed@example.com").exists()
        )

    # --- 8. Tenant isolation is preserved -------------------------------------
    def test_tenant_isolation_preserved_after_global_operations(self):
        auth(self.client, self.root)
        # Superadmin creates and then deactivates org B.
        self.client.post(
            ADMIN_LIST,
            {"name": "Isolated Org", "admin_email": "isolated@example.com"},
            format="json",
        )
        isolated = Organization.objects.get(name="Isolated Org")
        self.client.patch(
            f"/api/v1/admin/organizations/{isolated.id}/",
            {"status": Organization.Status.INACTIVE},
            format="json",
        )

        # org A user still sees only org A's data through tenant routes.
        auth(self.client, self.finance)
        response = self.client.get("/api/v1/organizations/")
        names = {item["name"] for item in response.data}
        self.assertEqual(names, {"Org A"})
        self.assertNotIn("Isolated Org", names)
        response = self.client.get(f"/api/v1/organizations/{isolated.id}/")
        self.assertEqual(response.status_code, 404)

    # --- 9. Inactive users / memberships / organizations grant nothing ------
    def test_inactive_user_gets_no_global_access(self):
        auth(self.client, self.inactive_user)
        # SimpleJWT's default auth rule rejects inactive accounts at the
        # authentication stage, so the guarded surface answers 401.
        self.assertEqual(self.client.get(ADMIN_LIST).status_code, 401)

    def test_deactivated_organization_no_longer_serves_members(self):
        auth(self.client, self.root)
        self.client.patch(
            f"/api/v1/admin/organizations/{self.org_a.id}/",
            {"status": Organization.Status.INACTIVE},
            format="json",
        )
        # finance was a FINANCE_ADMIN of active Org A; after deactivation the
        # tenant route must 404 (inactive organization grants no access).
        auth(self.client, self.finance)
        response = self.client.get(f"/api/v1/organizations/{self.org_a.id}/")
        self.assertEqual(response.status_code, 404)
        # Reactivate for later tests.
        auth(self.client, self.root)
        self.client.patch(
            f"/api/v1/admin/organizations/{self.org_a.id}/",
            {"status": Organization.Status.ACTIVE},
            format="json",
        )

    # --- 10. Invalid input yields controlled errors, never HTTP 500 ----------
    def test_invalid_inputs_return_controlled_errors(self):
        auth(self.client, self.root)
        cases = [
            {"name": "", "admin_email": "a@example.com"},
            {"name": "Org A", "admin_email": "a@example.com"},  # duplicate name
            {"name": "Bad Email Org", "admin_email": "not-an-email"},
            {"name": "x" * 201, "admin_email": "m@example.com"},  # too long
        ]
        for payload in cases:
            response = self.client.post(ADMIN_LIST, payload, format="json")
            self.assertEqual(response.status_code, 400, msg=payload)

        # Invalid status on update.
        response = self.client.patch(
            f"/api/v1/admin/organizations/{self.org_b.id}/",
            {"status": "maybe"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

        # Unknown organization id -> uniform 404, still structured.
        response = self.client.get(
            "/api/v1/admin/organizations/00000000-0000-0000-0000-000000000000/"
        )
        self.assertEqual(response.status_code, 404)

    # --- 11. Existing superuser account keeps its data and privileges --------
    def test_existing_superuser_reused_without_changing_privileges(self):
        auth(self.client, self.root)
        response = self.client.post(
            ADMIN_LIST,
            {"name": "Root Org", "admin_email": "root@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)  # root reused: no new account
        root = User.objects.get(username="root@example.com")
        self.assertTrue(root.is_superuser)
        self.assertTrue(root.is_staff)
        self.assertTrue(root.has_usable_password())
        membership = OrganizationMembership.objects.get(
            user=root, organization__name="Root Org"
        )
        self.assertEqual(membership.role, OrganizationRole.FINANCE_ADMIN)

    # --- 12. Prior routes keep working after the global surface ---------------
    def test_prior_routes_still_work(self):
        # Global surface did not touch the tenant admin routes.
        auth(self.client, self.finance)
        response = self.client.get("/api/v1/organizations/")
        self.assertEqual(response.status_code, 200)
        response = self.client.get(f"/api/v1/organizations/{self.org_a.id}/vendors/")
        self.assertEqual(response.status_code, 200)
        response = self.client.get(f"/api/v1/organizations/{self.org_a.id}/invoices/")
        self.assertEqual(response.status_code, 200)

    # --- Candidate users endpoint ----------------------------------------------
    def test_superadmin_lists_candidate_users_without_sensitive_data(self):
        auth(self.client, self.root)
        response = self.client.get(f"{ADMIN_USERS}?q=alic")
        self.assertEqual(response.status_code, 200)
        usernames = {item["username"] for item in response.data}
        self.assertIn("alice", usernames)
        for item in response.data:
            self.assertEqual(set(item.keys()), {"id", "username", "email"})

    def test_user_search_requires_superadmin(self):
        auth(self.client, self.finance)
        self.assertEqual(self.client.get(ADMIN_USERS).status_code, 404)