"""Integration tests for secure login (Phase 2, Slice 5) — JWT contract.

Real API requests with real token authentication (JWT Bearer). Covers login,
logout, throttling, the one-time invitation flow and initial password setup.
The only mocks target AuditEvent.objects.create to prove audit-failure
rollback.

JWT contract: POST /auth/login/ returns {access, refresh, user}; access is a
stateless Bearer token (10 min), refresh can mint new access tokens (7 days).
POST /auth/logout/ takes the refresh token and blacklists it.
"""

import hashlib
import uuid
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

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
    access = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
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

    def url_refresh(self):
        return "/api/v1/auth/refresh/"

    def url_set_password(self):
        return "/api/v1/auth/set-password/"

    def url_invite(self, org_id, user_id):
        return f"/api/v1/organizations/{org_id}/users/{user_id}/invite/"

    def login_payload(self, password=PASSWORD, email=None):
        return {"email": email or "login@example.com", "password": password}

    def do_login(self, **overrides):
        return self.client.post(self.url_login(), self.login_payload(**overrides), format="json")

    # --- login --------------------------------------------------------------
    def test_login_success_returns_token_and_safe_user(self):
        response = self.do_login()
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["username"], "login@example.com")
        self.assertNotIn("password", str(response.data))

    def test_login_tokens_work_on_me_and_org_endpoints(self):
        response = self.do_login()
        access = response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 200)
        self.assertEqual(
            self.client.get(f"/api/v1/organizations/").status_code, 200
        )

    def test_login_wrong_password_returns_401(self):
        response = self.do_login(password="WrongPass123!")
        self.assertEqual(response.status_code, 401)

    def test_login_unknown_email_returns_401_same_message(self):
        wrong = self.do_login(password="WrongPass123!")
        unknown = self.client.post(
            self.url_login(),
            {"email": "nobody@example.com", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong.data["detail"], unknown.data["detail"])

    def test_login_inactive_user_returns_401_same_message(self):
        response = self.client.post(
            self.url_login(),
            {"email": "inactive@example.com", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_login_normalizes_email(self):
        response = self.client.post(
            self.url_login(),
            {"email": "  LOGIN@EXAMPLE.COM ", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_login_response_has_no_secrets(self):
        response = self.do_login()
        body = str(response.data).lower()
        self.assertNotIn("password", body)
        self.assertNotIn("secret", body)

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

    # --- refresh ------------------------------------------------------------
    def test_refresh_issues_new_access_and_rotates(self):
        refresh = str(RefreshToken.for_user(self.user))
        response = self.client.post(self.url_refresh(), {"refresh": refresh}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        # Rotation: the presented refresh is now blacklisted.
        reused = self.client.post(self.url_refresh(), {"refresh": refresh}, format="json")
        self.assertEqual(reused.status_code, 401)

    def test_refresh_garbage_rejected(self):
        response = self.client.post(self.url_refresh(), {"refresh": "garbage"}, format="json")
        self.assertEqual(response.status_code, 401)

    # --- logout -------------------------------------------------------------
    def test_logout_revokes_refresh(self):
        login = self.do_login()
        access = login.data["access"]
        refresh = login.data["refresh"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 200)
        self.client.credentials()
        self.assertEqual(self.client.post(self.url_logout(), {"refresh": refresh}, format="json").status_code, 204)
        # The revoked refresh can no longer mint access tokens.
        response = self.client.post(self.url_refresh(), {"refresh": refresh}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_logout_does_not_revoke_other_users_refresh(self):
        login = self.do_login()
        own_refresh = login.data["refresh"]
        other_refresh = str(RefreshToken.for_user(self.nomember))
        self.assertEqual(
            self.client.post(self.url_logout(), {"refresh": own_refresh}, format="json").status_code, 204
        )
        other = self.client.post(self.url_refresh(), {"refresh": other_refresh}, format="json")
        self.assertEqual(other.status_code, 200)

    def test_logout_requires_refresh(self):
        self.assertEqual(self.client.post(self.url_logout(), {}, format="json").status_code, 400)
        self.assertEqual(
            self.client.post(self.url_logout(), {"refresh": "bad"}, format="json").status_code, 400
        )

    # --- throttling ----------------------------------------------------------
    def test_login_throttled(self):
        for _ in range(30):
            response = self.client.post(
                self.url_login(),
                self.login_payload(password="WrongPass123!"),
                format="json",
            )
            self.assertEqual(response.status_code, 401)
        response = self.do_login()
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

    def test_invite_audit_failure_rolls_back_everything(self):
        auth(self.client, self.admin_a)
        first = self.client.post(self.url_invite(self.org_a.id, self.user.id))
        self.assertEqual(first.status_code, 201)
        previous = PasswordSetupToken.objects.get(
            user=self.user, used_at__isnull=True
        )
        events_before = AuditEvent.objects.filter(
            target_id=str(self.user.id),
            action=AuditEvent.Action.INVITATION_ISSUED,
        ).count()
        client = APIClient(raise_request_exception=False)
        auth(client, self.admin_a)
        with mock.patch.object(
            AuditEvent.objects, "create", side_effect=RuntimeError("audit failed")
        ):
            response = client.post(self.url_invite(self.org_a.id, self.user.id))
        self.assertEqual(response.status_code, 500)
        active = PasswordSetupToken.objects.filter(
            user=self.user, used_at__isnull=True
        )
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.first().pk, previous.pk)
        self.assertEqual(active.first().token_hash, previous.token_hash)
        events_after = AuditEvent.objects.filter(
            target_id=str(self.user.id),
            action=AuditEvent.Action.INVITATION_ISSUED,
        ).count()
        self.assertEqual(events_after, events_before)

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
        login = self.do_login()
        access_token = login.data["access"]
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
        auth(self.client, self.admin_a)
        invite = self.client.post(self.url_invite(self.org_a.id, self.user.id))
        response = self.client.post(
            self.url_set_password(),
            {"setup_token": invite.data["setup_token"], "password": "NewStrongPass456!"},
            format="json",
        )
        self.assertEqual(response.status_code, 204)
        event = AuditEvent.objects.get(
            target_id=str(self.user.id), action=AuditEvent.Action.PASSWORD_SET
        )
        self.assertEqual(event.actor, self.user)
        self.assertIsNone(event.organization)
        meta = str(event.metadata).lower()
        self.assertNotIn("password", meta)
        self.assertNotIn("secret", meta)
        self.assertNotIn(str(invite.data["setup_token"]), meta)

    def test_set_password_audit_failure_rolls_back(self):
        auth(self.client, self.admin_a)
        invite = self.client.post(self.url_invite(self.org_a.id, self.user.id))
        raw_token = invite.data["setup_token"]
        client = APIClient(raise_request_exception=False)
        with mock.patch.object(
            AuditEvent.objects, "create", side_effect=RuntimeError("audit failed")
        ):
            response = client.post(
                self.url_set_password(),
                {"setup_token": raw_token, "password": "NewStrongPass456!"},
                format="json",
            )
        self.assertEqual(response.status_code, 500)
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password("NewStrongPass456!"))
        active = PasswordSetupToken.objects.filter(user=self.user, used_at__isnull=True)
        self.assertTrue(active.exists())
        self.assertIsNone(active.first().used_at)

    def test_set_password_rejects_token_of_inactive_account(self):
        # An inactive account cannot use its setup token: the invitation is
        # bound to an active login path, so deactivation cancels pending setup.
        self._make_setup_token(self.inactive_user)
        response = self.client.post(
            self.url_set_password(),
            {"setup_token": "known-raw-token", "password": "NewStrongPass456!"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.inactive_user.refresh_from_db()
        self.assertFalse(self.inactive_user.check_password("NewStrongPass456!"))
        # The token remains pending (not burned) because the user is inactive.
        token = PasswordSetupToken.objects.get(user=self.inactive_user)
        self.assertIsNone(token.used_at)

    def test_set_password_does_not_change_roles_or_global_privileges(self):
        # Setup only sets the initial credential: role, memberships, and
        # global flags are preserved. The client cannot smuggle them in.
        auth(self.client, self.admin_a)
        invite = self.client.post(self.url_invite(self.org_a.id, self.user.id))
        response = self.client.post(
            self.url_set_password(),
            {
                "setup_token": invite.data["setup_token"],
                "password": "NewStrongPass456!",
                # Attempted privilege injection must be ignored.
                "role": OrganizationRole.FINANCE_ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 204)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        membership = OrganizationMembership.objects.get(user=self.user)
        self.assertEqual(membership.role, OrganizationRole.OPERATOR)

    def _make_setup_token(self, user, hours=1):
        PasswordSetupToken.objects.create(
            user=user,
            token_hash=hashlib.sha256(b"known-raw-token").hexdigest(),
            expires_at=timezone.now() + timedelta(hours=hours),
        )