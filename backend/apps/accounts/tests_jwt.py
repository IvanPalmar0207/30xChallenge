"""JWT authentication contract tests (auth session upgrade).

Covers: login success/failure, inactive users, access missing/invalid/expired,
refresh valid/expired/invalid/reused-after-rotation, logout revocation, /auth/me/
with and without authentication, and that failed auth keeps uniform 401s.

Also proves the storage rule: refresh tokens are stored only as SHA-256 hashes
in the blacklist app's outstanding table.
"""

import hashlib

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

PASSWORD = "StrongPass123!"


def _expired(tok, lifetime_ms):
    """Turn a token into an already-expired one (same signature)."""
    tok.set_exp(lifetime=lifetime_ms, from_time=timezone.now() - lifetime_ms * 2)
    return tok


class JwtContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="jwt@example.com", password=PASSWORD)
        cls.inactive = User.objects.create_user(
            username="jwt-inactive@example.com", password=PASSWORD, is_active=False
        )

    def setUp(self):
        self.client = APIClient()

    def url_login(self):
        return "/api/v1/auth/login/"

    def url_refresh(self):
        return "/api/v1/auth/refresh/"

    def login(self, **overrides):
        payload = {"email": "jwt@example.com", "password": PASSWORD}
        payload.update(overrides)
        return self.client.post(self.url_login(), payload, format="json")

    # --- login ---
    def test_login_success_emits_pair(self):
        r = self.login()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["access"])
        self.assertTrue(r.data["refresh"])
        self.assertEqual(r.data["user"]["username"], "jwt@example.com")

    def test_login_failure_uniform_401(self):
        bad = self.login(password="WrongPass123!")
        unknown = self.client.post(
            self.url_login(), {"email": "nope@example.com", "password": PASSWORD}, format="json"
        )
        self.assertEqual(bad.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(
            str(bad.data.get("detail")), str(unknown.data.get("detail"))
        )

    def test_login_inactive_user_401(self):
        r = self.client.post(
            self.url_login(),
            {"email": "jwt-inactive@example.com", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(r.status_code, 401)

    # --- access token on /auth/me/ ---
    def test_me_without_auth_401(self):
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 401)

    def test_me_with_invalid_access_401(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 401)

    def test_me_with_valid_access_200(self):
        access = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 200)

    def test_me_with_expired_access_401(self):
        access = RefreshToken.for_user(self.user).access_token
        _expired(access, timedelta(minutes=10))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 401)

    # --- refresh token ---
    def test_refresh_valid_issues_new_pair(self):
        r = self.login()
        response = self.client.post(
            self.url_refresh(), {"refresh": r.data["refresh"]}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)  # rotation on

    def test_refresh_expired_rejected(self):
        refresh = RefreshToken.for_user(self.user)
        _expired(refresh, timedelta(days=7))
        response = self.client.post(
            self.url_refresh(), {"refresh": str(refresh)}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_refresh_invalid_rejected(self):
        response = self.client.post(self.url_refresh(), {"refresh": "junk"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_refresh_reused_after_rotation_rejected(self):
        r = self.login()
        original = r.data["refresh"]
        first = self.client.post(self.url_refresh(), {"refresh": original}, format="json")
        self.assertEqual(first.status_code, 200)
        # Reusing the rotated-away refresh must be rejected (blacklist).
        second = self.client.post(self.url_refresh(), {"refresh": original}, format="json")
        self.assertEqual(second.status_code, 401)

    # --- logout / blacklist ---
    def test_logout_revokes_refresh(self):
        r = self.login()
        raw = r.data["refresh"]
        self.assertEqual(
            self.client.post("/api/v1/auth/logout/", {"refresh": raw}, format="json").status_code,
            204,
        )
        reuse = self.client.post(self.url_refresh(), {"refresh": raw}, format="json")
        self.assertEqual(reuse.status_code, 401)

    def test_logout_invalid_refresh_400(self):
        response = self.client.post("/api/v1/auth/logout/", {"refresh": "junk"}, format="json")
        self.assertEqual(response.status_code, 400)

    # --- storage rule ---
    def test_refresh_stored_only_hashed(self):
        r = self.login()
        raw = r.data["refresh"]
        record = OutstandingToken.objects.latest("id")
        self.assertEqual(record.token, hashlib.sha256(raw.encode()).hexdigest())
        self.assertNotIn(raw, record.token)