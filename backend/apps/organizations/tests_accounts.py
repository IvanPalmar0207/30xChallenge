"""Integration tests for organization-scoped account lifecycle (Phase 2,
Slice 2): admin-created accounts, activation/deactivation, authentication
behavior, and CSRF. Real API requests with real token or session auth."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import AuditEvent, Organization, OrganizationMembership, OrganizationRole

User = get_user_model()


def auth(client, user):
    token, _ = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


class AccountLifecycleApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organization.objects.create(name="Lifecycle Org A")
        cls.org_b = Organization.objects.create(name="Lifecycle Org B")
        cls.admin_a = User.objects.create_user(username="lc_admin_a", password="x")
        cls.operator_a = User.objects.create_user(username="lc_operator_a", password="x")
        cls.admin_b = User.objects.create_user(username="lc_admin_b", password="x")
        cls.member_b = User.objects.create_user(username="lc_member_b", password="x")
        cls.superuser = User.objects.create_superuser(username="lc_root", password="x")
        OrganizationMembership.objects.create(
            user=cls.admin_a, organization=cls.org_a, role=OrganizationRole.FINANCE_ADMIN
        )
        OrganizationMembership.objects.create(
            user=cls.operator_a, organization=cls.org_a, role=OrganizationRole.OPERATOR
        )
        OrganizationMembership.objects.create(
            user=cls.admin_b, organization=cls.org_b, role=OrganizationRole.FINANCE_ADMIN
        )
        OrganizationMembership.objects.create(
            user=cls.member_b, organization=cls.org_b, role=OrganizationRole.OPERATOR
        )

    def setUp(self):
        self.client = APIClient()

    def url_users(self, org_id):
        return f"/api/v1/organizations/{org_id}/users/"

    def url_user(self, org_id, user_id):
        return f"/api/v1/organizations/{org_id}/users/{user_id}/"

    # --- authentication gates ------------------------------------------------
    def test_anonymous_cannot_create_account(self):
        response = self.client.post(
            self.url_users(self.org_a.id),
            {"email": "new@example.test", "role": OrganizationRole.OPERATOR},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_operator_cannot_create_account(self):
        auth(self.client, self.operator_a)
        response = self.client.post(
            self.url_users(self.org_a.id),
            {"email": "new@example.test", "role": OrganizationRole.OPERATOR},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    # --- account creation ------------------------------------------------------
    def test_finance_admin_creates_account_with_membership(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_users(self.org_a.id),
            {"email": "New.User@Example.TEST", "role": OrganizationRole.APPROVER},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.data
        self.assertEqual(data["email"], "new.user@example.test")
        self.assertEqual(data["role"], OrganizationRole.APPROVER)
        user = User.objects.get(pk=data["id"])
        self.assertEqual(user.username, "new.user@example.test")
        self.assertTrue(user.is_active)
        # No credential was stored: the account cannot log in until a separate
        # password-setup flow exists (documented MVP limitation).
        self.assertFalse(user.has_usable_password())
        membership = OrganizationMembership.objects.get(
            user=user, organization=self.org_a
        )
        self.assertEqual(membership.role, OrganizationRole.APPROVER)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditEvent.Action.ACCOUNT_CREATED, target_id=str(user.id)
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditEvent.Action.MEMBERSHIP_CREATED,
                target_id=str(membership.id),
            ).exists()
        )

    def test_account_creation_whitelists_fields(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_users(self.org_a.id),
            {
                "email": "sneaky@example.test",
                "role": OrganizationRole.OPERATOR,
                "is_staff": True,
                "is_superuser": True,
                "is_active": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="sneaky@example.test")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)  # server-side default wins

    def test_duplicate_email_rejected(self):
        auth(self.client, self.admin_a)
        self.client.post(
            self.url_users(self.org_a.id),
            {"email": "dup@example.test", "role": OrganizationRole.OPERATOR},
            format="json",
        )
        response = self.client.post(
            self.url_users(self.org_a.id),
            {"email": "DUP@example.test", "role": OrganizationRole.APPROVER},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            User.objects.filter(username="dup@example.test").count(), 1
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditEvent.Action.ACCOUNT_CREATED
            ).count(),
            1,
        )

    def test_invalid_email_rejected(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_users(self.org_a.id),
            {"email": "not-an-email", "role": OrganizationRole.OPERATOR},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_email_longer_than_username_limit_rejected(self):
        auth(self.client, self.admin_a)
        long_email = "a" * 200 + "@example.test"
        response = self.client.post(
            self.url_users(self.org_a.id),
            {"email": long_email, "role": OrganizationRole.OPERATOR},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_account_creation_rejects_finance_admin_role(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_users(self.org_a.id),
            {"email": "fa@example.test", "role": OrganizationRole.FINANCE_ADMIN},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="fa@example.test").exists())

    def test_org_a_admin_cannot_create_account_in_org_b(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_users(self.org_b.id),
            {"email": "cross@example.test", "role": OrganizationRole.OPERATOR},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(User.objects.filter(username="cross@example.test").exists())

    # --- activation / deactivation ---------------------------------------------
    def _create_target(self, email="victim@example.test"):
        auth(self.client, self.admin_a)
        self.client.post(
            self.url_users(self.org_a.id),
            {"email": email, "role": OrganizationRole.OPERATOR},
            format="json",
        )
        return User.objects.get(username=email)

    def test_finance_admin_deactivates_account(self):
        victim = self._create_target()
        response = self.client.patch(
            self.url_user(self.org_a.id, victim.id),
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        victim.refresh_from_db()
        self.assertFalse(victim.is_active)
        event = AuditEvent.objects.get(
            action=AuditEvent.Action.ACCOUNT_DEACTIVATED, target_id=str(victim.id)
        )
        self.assertEqual(event.actor, self.admin_a)
        self.assertEqual(event.metadata, {"is_active": False})

    def test_deactivated_account_cannot_authenticate(self):
        victim = self._create_target()
        token, _ = Token.objects.get_or_create(user=victim)
        response = self.client.patch(
            self.url_user(self.org_a.id, victim.id),
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        # Token authentication must reject the inactive account everywhere.
        self.client.credentials()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 401)
        self.assertEqual(
            self.client.get(f"/api/v1/organizations/{self.org_a.id}/").status_code,
            401,
        )
        # Session authentication must reject it too.
        session_client = APIClient()
        session_client.force_login(victim)
        self.assertEqual(
            session_client.get("/api/v1/auth/me/").status_code, 401
        )

    def test_reactivation_restores_authentication(self):
        victim = self._create_target()
        token, _ = Token.objects.get_or_create(user=victim)
        self.client.patch(
            self.url_user(self.org_a.id, victim.id), {"is_active": False}, format="json"
        )
        response = self.client.patch(
            self.url_user(self.org_a.id, victim.id), {"is_active": True}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        victim.refresh_from_db()
        self.assertTrue(victim.is_active)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditEvent.Action.ACCOUNT_ACTIVATED,
                target_id=str(victim.id),
            ).exists()
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 200)

    def test_activation_requires_is_active_field(self):
        victim = self._create_target()
        response = self.client.patch(
            self.url_user(self.org_a.id, victim.id), {}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        victim.refresh_from_db()
        self.assertTrue(victim.is_active)

    def test_admin_cannot_deactivate_self(self):
        auth(self.client, self.admin_a)
        response = self.client.patch(
            self.url_user(self.org_a.id, self.admin_a.id),
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.admin_a.refresh_from_db()
        self.assertTrue(self.admin_a.is_active)

    def test_admin_cannot_deactivate_superuser_member(self):
        auth(self.client, self.admin_a)
        OrganizationMembership.objects.create(
            user=self.superuser, organization=self.org_a, role=OrganizationRole.AUDITOR
        )
        response = self.client.patch(
            self.url_user(self.org_a.id, self.superuser.id),
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active)

    def test_cannot_deactivate_user_of_other_org(self):
        auth(self.client, self.admin_a)
        response = self.client.patch(
            self.url_user(self.org_a.id, self.member_b.id),
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.member_b.refresh_from_db()
        self.assertTrue(self.member_b.is_active)

    def test_deactivation_preserves_history(self):
        victim = self._create_target()
        membership_id = victim.memberships.get(organization=self.org_a).id
        self.client.patch(
            self.url_user(self.org_a.id, victim.id), {"is_active": False}, format="json"
        )
        victim.refresh_from_db()
        self.assertFalse(victim.is_active)
        # The user row and the membership row still exist unchanged.
        self.assertEqual(
            victim.memberships.get(organization=self.org_a).id, membership_id
        )
        actions = {
            e.action
            for e in AuditEvent.objects.filter(
                target_id=str(victim.id), target_type="user"
            )
        }
        self.assertEqual(
            actions,
            {
                AuditEvent.Action.ACCOUNT_CREATED,
                AuditEvent.Action.ACCOUNT_DEACTIVATED,
            },
        )

    # --- secrets / CSRF ----------------------------------------------------------
    def test_responses_and_audit_metadata_contain_no_secrets(self):
        auth(self.client, self.admin_a)
        r1 = self.client.post(
            self.url_users(self.org_a.id),
            {"email": "clean@example.test", "role": OrganizationRole.OPERATOR},
            format="json",
        )
        victim = User.objects.get(username="clean@example.test")
        r2 = self.client.patch(
            self.url_user(self.org_a.id, victim.id),
            {"is_active": False},
            format="json",
        )
        for response in (r1, r2):
            payload = str(response.data).lower()
            self.assertNotIn("password", payload)
            self.assertNotIn("token", payload)
            self.assertNotIn("secret", payload)
        for event in AuditEvent.objects.all():
            meta = str(event.metadata).lower()
            self.assertNotIn("password", meta)
            self.assertNotIn("token", meta)
            self.assertNotIn("secret", meta)

    def test_session_authenticated_unsafe_requests_require_csrf(self):
        session_client = APIClient(enforce_csrf_checks=True)
        session_client.force_login(self.admin_a)
        response = session_client.post(
            self.url_users(self.org_a.id),
            {"email": "csrf@example.test", "role": OrganizationRole.OPERATOR},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="csrf@example.test").exists())

    # --- transactions -------------------------------------------------------------
    def test_failed_audit_rolls_back_account_creation(self):
        client = APIClient(raise_request_exception=False)
        auth(client, self.admin_a)
        with mock.patch(
            "apps.organizations.views.AuditEvent.objects.create",
            side_effect=RuntimeError("audit store failed"),
        ):
            response = client.post(
                self.url_users(self.org_a.id),
                {"email": "zombie@example.test", "role": OrganizationRole.OPERATOR},
                format="json",
            )
        self.assertEqual(response.status_code, 500)
        self.assertFalse(User.objects.filter(username="zombie@example.test").exists())
        self.assertFalse(
            OrganizationMembership.objects.filter(
                user__username="zombie@example.test"
            ).exists()
        )

    def test_failed_audit_rolls_back_deactivation(self):
        victim = self._create_target()
        client = APIClient(raise_request_exception=False)
        auth(client, self.admin_a)
        with mock.patch(
            "apps.organizations.views.AuditEvent.objects.create",
            side_effect=RuntimeError("audit store failed"),
        ):
            response = client.patch(
                self.url_user(self.org_a.id, victim.id),
                {"is_active": False},
                format="json",
            )
        self.assertEqual(response.status_code, 500)
        victim.refresh_from_db()
        self.assertTrue(victim.is_active)
