"""Integration tests for GET /api/v1/auth/me/ (safe identity profile)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership, OrganizationRole

User = get_user_model()


def auth(client, user):
    """Authenticate through the real JWT pipeline."""
    access = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


class MeEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organization.objects.create(name="Org A")
        cls.org_b = Organization.objects.create(name="Org B")

        cls.alice = User.objects.create_user(
            username="alice", password="x", email="alice@example.test",
            first_name="Alice", last_name="Test",
        )
        cls.bob = User.objects.create_user(username="bob", password="x")
        cls.carol = User.objects.create_user(username="carol", password="x")
        cls.dave = User.objects.create_user(username="dave", password="x")
        cls.erin = User.objects.create_user(username="erin", password="x")
        cls.root = User.objects.create_superuser(username="root", password="x")

        OrganizationMembership.objects.create(
            user=cls.alice, organization=cls.org_a, role=OrganizationRole.FINANCE_ADMIN
        )
        OrganizationMembership.objects.create(
            user=cls.bob, organization=cls.org_a, role=OrganizationRole.APPROVER
        )
        OrganizationMembership.objects.create(
            user=cls.dave, organization=cls.org_b, role=OrganizationRole.OPERATOR
        )
        OrganizationMembership.objects.create(
            user=cls.erin,
            organization=cls.org_a,
            role=OrganizationRole.OPERATOR,
            is_active=False,
        )

    def setUp(self):
        self.client = APIClient()

    def test_anonymous_me_requires_authentication(self):
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 401)

    # --- Case 11: /me exposes no passwords, tokens, secrets ------------------
    def test_me_has_no_secret_fields(self):
        auth(self.client, self.alice)
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 200)
        # No password-equivalent or token field may ever appear in the payload.
        payload = str(response.data).lower()
        self.assertNotIn("password", payload)
        self.assertNotIn("secret", payload)
        self.assertNotIn("token", payload)

    def test_me_does_not_expose_staff_or_superuser_flags(self):
        # Root's fields are exactly the same shape as anyone else's: global
        # admin status is separate from organization authority.
        auth(self.client, self.root)
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("is_staff", response.data)
        self.assertNotIn("is_superuser", response.data)

    def test_me_returns_identity_and_memberships(self):
        auth(self.client, self.alice)
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(
            sorted(data.keys()),
            sorted(
                [
                    "id",
                    "username",
                    "email",
                    "first_name",
                    "last_name",
                    "memberships",
                    "is_global_admin",
                ]
            ),
        )
        self.assertEqual(data["username"], "alice")
        self.assertEqual(data["email"], "alice@example.test")
        self.assertFalse(data["is_global_admin"])
        self.assertEqual(len(data["memberships"]), 1)
        membership = data["memberships"][0]
        self.assertEqual(membership["organization_id"], str(self.org_a.id))
        self.assertEqual(membership["organization_name"], "Org A")
        self.assertEqual(membership["role"], OrganizationRole.FINANCE_ADMIN)

    def test_me_includes_roles_per_membership(self):
        auth(self.client, self.bob)
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 200)
        roles = {m["role"] for m in response.data["memberships"]}
        self.assertEqual(roles, {OrganizationRole.APPROVER})

    def test_me_shows_only_own_memberships(self):
        auth(self.client, self.dave)
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["memberships"]), 1)
        self.assertEqual(
            response.data["memberships"][0]["organization_id"], str(self.org_b.id)
        )
        # Alice's /me must not reference org B.
        auth(self.client, self.alice)
        response = self.client.get("/api/v1/auth/me/")
        org_ids = {m["organization_id"] for m in response.data["memberships"]}
        self.assertEqual(org_ids, {str(self.org_a.id)})

    def test_me_excludes_inactive_memberships(self):
        auth(self.client, self.erin)
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["memberships"], [])

    def test_superuser_without_membership_has_empty_memberships(self):
        auth(self.client, self.root)
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["memberships"], [])
