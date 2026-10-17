"""Integration tests for secure login (Phase 2, Slice 5).

Real API requests with real token authentication. Covers login, logout,
throttling, the one-time invitation flow, and initial password setup. The
only mocks target AuditEvent.objects.create to prove audit-failure rollback.
"""

import hashlib
import uuid
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.organizations.models import (
    AuditEvent,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    PasswordSetupToken,
)

User = get_user_model()

PASSWORD = "StrongPass123!"


def auth(client, user):
    token, _ = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


class LoginApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organization.objects.create(name="Login Org A")
        cls.org_b = Organization.objects.create(name="Login Org B")
        cls.admin_a = User.objects.create_user(username="l_admin_a", password="x")
        cls.operator_a = User.objects.create_user(username="l_operator_a", password="x")
        cls.user = User.objects.create_user(
            username="login@example.com", email="login@example.com", password=PASSWORD
        )
        cls.inactive_user = User.objects.create_user(
            username="inactive@example.com",
            email="inactive@example.com",
            password=PASSWORD,
            is_active=False,
        )
        cls.nomember = User.objects.create_user(
            username="nomember@example.com",
            email="nomember@example.com",
            password=PASSWORD,
        )
        cls.superuser = User.objects.create_superuser(username="l_root", password="x")

        OrganizationMembership.objects.create(
            user=cls.admin_a, organization=cls.org_a, role=OrganizationRole.FINANCE_ADMIN
        )
        OrganizationMembership.objects.create(
            user=cls.operator_a, organization=cls.org_a, role=OrganizationRole.OPERATOR
        )
        OrganizationMembership.objects.create(
            user=cls.user, organization=cls.org_a, role=OrganizationRole.OPERATOR
        )
        OrganizationMembership.objects.create(
            user=cls.inactive_user,
            organization=cls.org_a,
            role=OrganizationRole.OPERATOR,
        )

    def setUp(self):
        self.client = APIClient()
        cache.clear()

    def url_login(self):
        return "/api/v1/auth/login/"

    def url_logout(self):
        return "/api/v1/auth/logout/"

    def url_set_password(self):
        return "/api/v1/auth/set-password/"

    def url_invite(self, org_id, user_id):
        return f"/api/v1/organizations/{org_id}/users/{user_id}/invite/"

    def login_payload(self, **overrides):
        data = {"email": "login@example.com", "password": PASSWORD}
        data.update(overrides)
        return data

    def _make_setup_token(self, user, raw="known-raw-token", hours=72, used=False):
        return PasswordSetupToken.objects.create(
            user=user,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(hours=hours),
            used_at=timezone.now() if used else None,
        )

    # --- login ---------------------------------------------------------------
    def test_login_success_returns_token_and_safe_user(self):
        response = self.client.post(
            self.url_login(), self.login_payload(), format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)
        user_payload = response.data["user"]
        self.assertEqual(user_payload["email"], "login@example.com")
        self.assertNotIn("password", user_payload)
        self.assertNotIn("is_staff", user_payload)
        self.assertNotIn("is_superuser", user_payload)

    def test_login_token_works_on_me_and_org_endpoints(self):
        response = self.client.post(
            self.url_login(), self.login_payload(), format="json"
        )
        token = response.data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 200)
        self.assertEqual(
            self.client.get(f"/api/v1/organizations/{self.org_a.id}/").status_code, 200
        )

    def test_login_wrong_password_returns_401(self):
        response = self.client.post(
            self.url_login(), self.login_payload(password="WrongPass123!"), format="json"
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid email or password.", str(response.data))

    def test_login_unknown_email_returns_401_same_message(self):
        response = self.client.post(
            self.url_login(), self.login_payload(email="nobody@example.com"), format="json"
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid email or password.", str(response.data))

    def test_login_inactive_user_returns_401_same_message(self):
        response = self.client.post(
            self.url_login(),
            self.login_payload(email="inactive@example.com"),
            format="json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid email or password.", str(response.data))

    def test_login_normalizes_email(self):
        response = self.client.post(
            self.url_login(),
            self.login_payload(email="  Login@Example.COM  "),
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_login_response_has_no_secrets(self):
        response = self.client.post(
            self.url_login(), self.login_payload(), format="json"
        )
        payload = str(response.data).lower()
        self.assertNotIn("password", payload)
        self.assertNotIn("secret", payload)
        self.assertNotIn("token_hash", payload)

    def test_login_missing_fields_controlled(self):
        self.assertEqual(
            self.client.post(self.url_login(), {}, format="json").status_code, 400
        )
        self.assertEqual(
            self.client.post(
                self.url_login(), {"email": "login@example.com"}, format="json"
            ).status_code,
            400,
        )

    # --- logout --------------------------------------------------------------
    def test_logout_revokes_current_token(self):
        response = self.client.post(
            self.url_login(), self.login_payload(), format="json"
        )
        token = response.data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 200)
        self.assertEqual(self.client.post(self.url_logout()).status_code, 204)
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 401)

    def test_logout_does_not_revoke_other_users_tokens(self):
        # DRF Token is OneToOne per user, so a logout can only affect the
        # current user's token; another user's token must survive.
        response = self.client.post(
            self.url_login(), self.login_payload(), format="json"
        )
        token_a = response.data["token"]
        other_token, _ = Token.objects.get_or_create(user=self.nomember)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_a}")
        self.assertEqual(self.client.post(self.url_logout()).status_code, 204)
        self.assertFalse(Token.objects.filter(key=token_a).exists())
        self.assertTrue(Token.objects.filter(key=other_token.key).exists())

    def test_logout_requires_authentication(self):
        self.assertEqual(self.client.post(self.url_logout()).status_code, 401)

    def test_logout_flushes_session(self):
        session_client = APIClient()
        session_client.force_login(self.user)
        self.assertEqual(session_client.get("/api/v1/auth/me/").status_code, 200)
        self.assertEqual(session_client.post(self.url_logout()).status_code, 204)
        self.assertEqual(session_client.get("/api/v1/auth/me/").status_code, 401)

    # --- throttling ----------------------------------------------------------
    def test_login_throttled(self):
        for _ in range(30):
            response = self.client.post(
                self.url_login(),
                self.login_payload(password="WrongPass123!"),
                format="json",
            )
            self.assertEqual(response.status_code, 401)
        response = self.client.post(
            self.url_login(), self.login_payload(), format="json"
        )
        self.assertEqual(response.status_code, 429)

    # --- invitation ----------------------------------------------------------
    def test_invite_requires_finance_admin(self):
        auth(self.client, self.operator_a)
        self.assertEqual(
            self.client.post(self.url_invite(self.org_a.id, self.user.id)).status_code,
            404,
        )

    def test_invite_returns_token_and_stores_only_hash(self):
        auth(self.client, self.admin_a)
        response = self.client.post(self.url_invite(self.org_a.id, self.user.id))
        self.assertEqual(response.status_code, 201)
        raw_token = response.data["setup_token"]
        self.assertTrue(raw_token)
        self.assertIn("expires_at", response.data)
        stored = PasswordSetupToken.objects.get(user=self.user, used_at__isnull=True)
        self.assertNotEqual(stored.token_hash, raw_token)
        self.assertEqual(
            stored.token_hash, hashlib.sha256(raw_token.encode()).hexdigest()
        )
        event = AuditEvent.objects.get(
            target_id=str(self.user.id), action=AuditEvent.Action.INVITATION_ISSUED
        )
        self.assertEqual(event.actor, self.admin_a)
        self.assertEqual(event.organization, self.org_a)
        self.assertNotIn("setup_token", str(event.metadata))

    def test_invite_invalidates_previous_unused_tokens(self):
        auth(self.client, self.admin_a)
        self.client.post(self.url_invite(self.org_a.id, self.user.id))
        self.client.post(self.url_invite(self.org_a.id, self.user.id))
        active = PasswordSetupToken.objects.filter(
            user=self.user, used_at__isnull=True
        )
        self.assertEqual(active.count(), 1)

    def test_invite_superuser_rejected(self):
        # A superuser who holds a membership in the org is still not
        # invitable through organization endpoints (403).
        OrganizationMembership.objects.create(
            user=self.superuser, organization=self.org_a, role=OrganizationRole.OPERATOR
        )
        auth(self.client, self.admin_a)
        response = self.client.post(self.url_invite(self.org_a.id, self.superuser.id))
        self.assertEqual(response.status_code, 403)

    def test_invite_unknown_user_404(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_invite(self.org_a.id, self.nomember.id)
        )
        self.assertEqual(response.status_code, 404)

    def test_invite_cross_org_404(self):
        auth(self.client, self.admin_a)
        other = User.objects.create_user(
            username="other@example.com", email="other@example.com", password=PASSWORD
        )
        OrganizationMembership.objects.create(
            user=other, organization=self.org_b, role=OrganizationRole.OPERATOR
        )
        response = self.client.post(self.url_invite(self.org_a.id, other.id))
        self.assertEqual(response.status_code, 404)

    # --- set-password --------------------------------------------------------
    def test_set_password_with_valid_token(self):
        auth(self.client, self.admin_a)
        invite = self.client.post(self.url_invite(self.org_a.id, self.user.id))
        raw_token = invite.data["setup_token"]
        response = self.client.post(
            self.url_set_password(),
            {"setup_token": raw_token, "password": "NewStrongPass456!"},
            format="json",
        )
        self.assertEqual(response.status_code, 204)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStrongPass456!"))
        # The new password works for login.
        self.client.credentials()
        login = self.client.post(
            self.url_login(),
            {"email": "login@example.com", "password": "NewStrongPass456!"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)

    def test_set_password_token_single_use(self):
        self._make_setup_token(self.user)
        payload = {"setup_token": "known-raw-token", "password": "NewStrongPass456!"}
        self.assertEqual(
            self.client.post(self.url_set_password(), payload, format="json").status_code,
            204,
        )
        self.assertEqual(
            self.client.post(self.url_set_password(), payload, format="json").status_code,
            400,
        )

    def test_set_password_expired_token(self):
        self._make_setup_token(self.user, hours=-1)
        response = self.client.post(
            self.url_set_password(),
            {"setup_token": "known-raw-token", "password": "NewStrongPass456!"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid or expired setup token.", str(response.data))

    def test_set_password_invalid_token(self):
        response = self.client.post(
            self.url_set_password(),
            {"setup_token": "garbage-token", "password": "NewStrongPass456!"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_set_password_does_not_accept_access_token(self):
        # A real DRF access token must never be accepted as a setup token.
        login = self.client.post(
            self.url_login(), self.login_payload(), format="json"
        )
        access_token = login.data["token"]
        response = self.client.post(
            self.url_set_password(),
            {"setup_token": access_token, "password": "NewStrongPass456!"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password("NewStrongPass456!"))

    def test_set_password_weak_password_rejected(self):
        self._make_setup_token(self.user)
        response = self.client.post(
            self.url_set_password(),
            {"setup_token": "known-raw-token", "password": "password"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_set_password_audit_event_safe_metadata(self):
        self._make_setup_token(self.user)
        self.client.post(
            self.url_set_password(),
            {"setup_token": "known-raw-token", "password": "NewStrongPass456!"},
            format="json",
        )
        event = AuditEvent.objects.get(
            target_id=str(self.user.id), action=AuditEvent.Action.PASSWORD_SET
        )
        self.assertEqual(event.actor, self.user)
        self.assertIsNone(event.organization)
        self.assertEqual(event.metadata, {"method": "setup_token"})
        meta = str(event.metadata).lower()
        self.assertNotIn("password", meta)
        self.assertNotIn("known-raw-token", meta)
        self.assertNotIn("token_hash", meta)

    def test_set_password_audit_failure_rolls_back(self):
        self._make_setup_token(self.user)
        client = APIClient(raise_request_exception=False)
        with mock.patch.object(
            AuditEvent.objects, "create", side_effect=RuntimeError("audit failed")
        ):
            response = client.post(
                self.url_set_password(),
                {"setup_token": "known-raw-token", "password": "NewStrongPass456!"},
                format="json",
            )
        self.assertEqual(response.status_code, 500)
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password("NewStrongPass456!"))
        record = PasswordSetupToken.objects.get(user=self.user)
        self.assertIsNone(record.used_at)
