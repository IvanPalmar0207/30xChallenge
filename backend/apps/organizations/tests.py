"""Integration tests for the organizations API (tenant-scoped access)."""

import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import Organization, OrganizationMembership, OrganizationRole

User = get_user_model()


def auth(client, user):
    """Authenticate through the real TokenAuthentication pipeline."""
    token, _ = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


class OrganizationApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organization.objects.create(name="Org A")
        cls.org_b = Organization.objects.create(name="Org B")
        cls.org_inactive = Organization.objects.create(
            name="Org Inactive", status=Organization.Status.INACTIVE
        )

        cls.alice = User.objects.create_user(username="alice", password="x")
        cls.bob = User.objects.create_user(username="bob", password="x")
        cls.carol = User.objects.create_user(username="carol", password="x")
        cls.dave = User.objects.create_user(username="dave", password="x")
        cls.erin = User.objects.create_user(username="erin", password="x")
        cls.frank = User.objects.create_user(username="frank", password="x")
        cls.root = User.objects.create_superuser(username="root", password="x")

        # alice: org A FINANCE_ADMIN (active); bob: org A APPROVER.
        OrganizationMembership.objects.create(
            user=cls.alice, organization=cls.org_a, role=OrganizationRole.FINANCE_ADMIN
        )
        OrganizationMembership.objects.create(
            user=cls.bob, organization=cls.org_a, role=OrganizationRole.APPROVER
        )
        # dave: org B only (cross-tenant isolation target).
        OrganizationMembership.objects.create(
            user=cls.dave, organization=cls.org_b, role=OrganizationRole.OPERATOR
        )
        # erin: inactive membership in org A — must grant nothing.
        OrganizationMembership.objects.create(
            user=cls.erin,
            organization=cls.org_a,
            role=OrganizationRole.OPERATOR,
            is_active=False,
        )
        # frank: ACTIVE membership in an INACTIVE organization — must grant nothing.
        OrganizationMembership.objects.create(
            user=cls.frank,
            organization=cls.org_inactive,
            role=OrganizationRole.OPERATOR,
        )
        # carol (no membership) and root (superuser, no membership).

    def setUp(self):
        self.client = APIClient()

    # --- Case 1: anonymous users cannot access protected endpoints ----------
    def test_anonymous_cannot_list_organizations(self):
        response = self.client.get("/api/v1/organizations/")
        self.assertEqual(response.status_code, 401)

    def test_anonymous_cannot_retrieve_organization(self):
        response = self.client.get(f"/api/v1/organizations/{self.org_a.id}/")
        self.assertEqual(response.status_code, 401)

    def test_garbage_token_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token not-a-real-token-value")
        response = self.client.get("/api/v1/organizations/")
        self.assertEqual(response.status_code, 401)

    # --- Case 2: list only organizations with active membership -------------
    def test_list_contains_only_users_accessible_organizations(self):
        auth(self.client, self.alice)
        response = self.client.get("/api/v1/organizations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item["id"] for item in response.data}, {str(self.org_a.id)}
        )

    def test_list_excludes_inactive_membership(self):
        auth(self.client, self.erin)
        response = self.client.get("/api/v1/organizations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_list_excludes_inactive_organizations(self):
        auth(self.client, self.frank)
        response = self.client.get("/api/v1/organizations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_list_empty_for_user_without_membership(self):
        auth(self.client, self.carol)
        response = self.client.get("/api/v1/organizations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    # --- Case 3: member retrieves own active organization --------------------
    def test_member_retrieves_own_organization(self):
        auth(self.client, self.alice)
        response = self.client.get(f"/api/v1/organizations/{self.org_a.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(self.org_a.id))
        self.assertEqual(response.data["name"], "Org A")
        self.assertEqual(response.data["status"], Organization.Status.ACTIVE)

    # --- Case 4: cross-tenant retrieval blocked ------------------------------
    def test_user_from_org_a_cannot_retrieve_org_b(self):
        auth(self.client, self.alice)
        response = self.client.get(f"/api/v1/organizations/{self.org_b.id}/")
        self.assertEqual(response.status_code, 404)

    # --- Case 5: inactive membership grants nothing --------------------------
    def test_inactive_membership_does_not_grant_access(self):
        auth(self.client, self.erin)
        response = self.client.get(f"/api/v1/organizations/{self.org_a.id}/")
        self.assertEqual(response.status_code, 404)

    # --- Case 6: inactive organization unusable ------------------------------
    def test_inactive_organization_cannot_be_used(self):
        auth(self.client, self.frank)
        response = self.client.get(f"/api/v1/organizations/{self.org_inactive.id}/")
        self.assertEqual(response.status_code, 404)

    # --- Case 7: no membership -> no access -----------------------------------
    def test_user_without_membership_cannot_access(self):
        auth(self.client, self.carol)
        response = self.client.get(f"/api/v1/organizations/{self.org_a.id}/")
        self.assertEqual(response.status_code, 404)

    # --- Case 8: membership uniqueness at the database ------------------------
    def test_membership_uniqueness_enforced(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrganizationMembership.objects.create(
                    user=self.alice,
                    organization=self.org_a,
                    role=OrganizationRole.OPERATOR,
                )

    # --- Case 9: different roles in the same organization ---------------------
    def test_users_hold_different_roles_in_same_organization(self):
        alice_membership = OrganizationMembership.objects.get(
            user=self.alice, organization=self.org_a
        )
        bob_membership = OrganizationMembership.objects.get(
            user=self.bob, organization=self.org_a
        )
        self.assertEqual(alice_membership.role, OrganizationRole.FINANCE_ADMIN)
        self.assertEqual(bob_membership.role, OrganizationRole.APPROVER)
        # Both are read-authorized; role is stored per membership.
        auth(self.client, self.alice)
        self.assertEqual(
            self.client.get(f"/api/v1/organizations/{self.org_a.id}/").status_code, 200
        )
        auth(self.client, self.bob)
        self.assertEqual(
            self.client.get(f"/api/v1/organizations/{self.org_a.id}/").status_code, 200
        )

    # --- Case 10: admin status grants neither membership nor authority --------
    def test_superuser_without_membership_gets_no_access(self):
        auth(self.client, self.root)
        response = self.client.get(f"/api/v1/organizations/{self.org_a.id}/")
        self.assertEqual(response.status_code, 404)
        response = self.client.get("/api/v1/organizations/")
        self.assertEqual(response.data, [])

    # --- Consistent authorization behavior: no existence disclosure -----------
    def test_unknown_uuid_returns_same_404_as_forbidden_org(self):
        auth(self.client, self.alice)
        unknown = self.client.get(f"/api/v1/organizations/{uuid.uuid4()}/")
        self.assertEqual(unknown.status_code, 404)
        foreign = self.client.get(f"/api/v1/organizations/{self.org_b.id}/")
        self.assertEqual(foreign.status_code, 404)
        # Both are 404 — the API does not reveal whether org B exists.

    # --- Case 12: malformed (non-UUID) path values are refused cleanly ---------
    def test_malformed_uuid_returns_uniform_not_found(self):
        # A value that is not a UUID must produce the same controlled 404 as an
        # unknown or foreign organization (audit finding F1). It must never be
        # an unhandled server error and must never leak ORM/validation details.
        auth(self.client, self.alice)
        response = self.client.get("/api/v1/organizations/not-a-uuid/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"detail": "Not found."})
        payload = response.content.decode(errors="replace").lower()
        self.assertNotIn("validation", payload)
        self.assertNotIn("is not a valid uuid", payload)
        self.assertNotIn("traceback", payload)
        self.assertNotIn("exception", payload)
