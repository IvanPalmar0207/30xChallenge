"""Integration tests for organization-scoped membership administration
(Phase 2, Slice 2). Real API requests with real token authentication."""

import uuid
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIClient

from .models import AuditEvent, Organization, OrganizationMembership, OrganizationRole

User = get_user_model()


def auth(client, user):
    """Authenticate through the real JWT pipeline."""
    access = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


class MembershipAdminApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organization.objects.create(name="Admin Org A")
        cls.org_b = Organization.objects.create(name="Admin Org B")
        cls.org_inactive = Organization.objects.create(
            name="Admin Org Inactive", status=Organization.Status.INACTIVE
        )
        cls.admin_a = User.objects.create_user(username="admin_a", password="x")
        cls.admin_a2 = User.objects.create_user(username="admin_a2", password="x")
        cls.operator_a = User.objects.create_user(username="operator_a", password="x")
        cls.auditor_a = User.objects.create_user(username="auditor_a", password="x")
        cls.member_a = User.objects.create_user(username="member_a", password="x")
        cls.admin_b = User.objects.create_user(username="admin_b", password="x")
        cls.superuser = User.objects.create_superuser(username="root_admin", password="x")
        cls.nomember = User.objects.create_user(username="nomember", password="x")

        OrganizationMembership.objects.create(
            user=cls.admin_a, organization=cls.org_a, role=OrganizationRole.FINANCE_ADMIN
        )
        OrganizationMembership.objects.create(
            user=cls.admin_a2, organization=cls.org_a, role=OrganizationRole.FINANCE_ADMIN
        )
        OrganizationMembership.objects.create(
            user=cls.operator_a, organization=cls.org_a, role=OrganizationRole.OPERATOR
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

    def setUp(self):
        self.client = APIClient()

    def url_list(self, org_id):
        return f"/api/v1/organizations/{org_id}/memberships/"

    def url_detail(self, org_id, membership_id):
        return f"/api/v1/organizations/{org_id}/memberships/{membership_id}/"

    # --- authentication gates -------------------------------------------------
    def test_anonymous_cannot_list_memberships(self):
        response = self.client.get(self.url_list(self.org_a.id))
        self.assertEqual(response.status_code, 401)

    def test_anonymous_cannot_create_membership(self):
        response = self.client.post(
            self.url_list(self.org_a.id),
            {"user": str(self.member_a.id), "role": OrganizationRole.OPERATOR},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_operator_cannot_manage_memberships(self):
        auth(self.client, self.operator_a)
        self.assertEqual(self.client.get(self.url_list(self.org_a.id)).status_code, 404)
        response = self.client.post(
            self.url_list(self.org_a.id),
            {"user": str(self.nomember.id), "role": OrganizationRole.OPERATOR},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_auditor_cannot_manage_memberships(self):
        auth(self.client, self.auditor_a)
        self.assertEqual(self.client.get(self.url_list(self.org_a.id)).status_code, 404)

    def test_user_without_membership_cannot_manage(self):
        auth(self.client, self.nomember)
        self.assertEqual(self.client.get(self.url_list(self.org_a.id)).status_code, 404)

    # --- finance admin operations ---------------------------------------------
    def test_finance_admin_lists_memberships(self):
        auth(self.client, self.admin_a)
        response = self.client.get(self.url_list(self.org_a.id))
        self.assertEqual(response.status_code, 200)
        usernames = {m["user"]["username"] for m in response.data}
        self.assertEqual(
            usernames,
            {"admin_a", "admin_a2", "operator_a", "auditor_a", "member_a"},
        )

    def test_finance_admin_creates_membership(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            {"user": str(self.nomember.id), "role": OrganizationRole.APPROVER},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["role"], OrganizationRole.APPROVER)
        membership = OrganizationMembership.objects.get(
            user=self.nomember, organization=self.org_a
        )
        self.assertTrue(membership.is_active)
        event = AuditEvent.objects.get(
            action=AuditEvent.Action.MEMBERSHIP_CREATED,
            target_id=str(membership.id),
        )
        self.assertEqual(event.actor, self.admin_a)
        self.assertEqual(event.organization, self.org_a)
        self.assertEqual(event.metadata["role"], OrganizationRole.APPROVER)

    def test_membership_create_whitelists_fields(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            {
                "user": str(self.nomember.id),
                "role": OrganizationRole.OPERATOR,
                "is_superuser": True,
                "is_staff": True,
                "is_active": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.nomember.refresh_from_db()
        self.assertFalse(self.nomember.is_superuser)
        self.assertFalse(self.nomember.is_staff)
        membership = OrganizationMembership.objects.get(
            user=self.nomember, organization=self.org_a
        )
        # Client-supplied is_active is ignored; the server default applies.
        self.assertTrue(membership.is_active)

    def test_admin_from_org_a_cannot_manage_org_b(self):
        auth(self.client, self.admin_a)
        self.assertEqual(self.client.get(self.url_list(self.org_b.id)).status_code, 404)
        response = self.client.post(
            self.url_list(self.org_b.id),
            {"user": str(self.member_a.id), "role": OrganizationRole.OPERATOR},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_inactive_org_rejects_membership_management(self):
        # The actor IS a FINANCE_ADMIN, but the organization is inactive: the
        # management permission requires an ACTIVE organization.
        OrganizationMembership.objects.create(
            user=self.admin_a,
            organization=self.org_inactive,
            role=OrganizationRole.FINANCE_ADMIN,
        )
        auth(self.client, self.admin_a)
        self.assertEqual(self.client.get(self.url_list(self.org_inactive.id)).status_code, 404)

    def test_duplicate_membership_rejected(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            {"user": str(self.member_a.id), "role": OrganizationRole.OPERATOR},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            OrganizationMembership.objects.filter(
                user=self.member_a, organization=self.org_a
            ).count(),
            1,
        )
        self.assertFalse(
            AuditEvent.objects.filter(action=AuditEvent.Action.MEMBERSHIP_CREATED).exists()
        )

    def test_membership_create_unknown_user_rejected(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            {"user": str(uuid.uuid4()), "role": OrganizationRole.OPERATOR},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_membership_create_rejects_finance_admin_role(self):
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            {"user": str(self.nomember.id), "role": OrganizationRole.FINANCE_ADMIN},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            OrganizationMembership.objects.filter(
                user=self.nomember, organization=self.org_a
            ).exists()
        )

    # --- membership updates ---------------------------------------------------
    def test_membership_role_change(self):
        auth(self.client, self.admin_a)
        membership = OrganizationMembership.objects.get(
            user=self.member_a, organization=self.org_a
        )
        response = self.client.patch(
            self.url_detail(self.org_a.id, membership.id),
            {"role": OrganizationRole.APPROVER},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        membership.refresh_from_db()
        self.assertEqual(membership.role, OrganizationRole.APPROVER)
        event = AuditEvent.objects.get(
            action=AuditEvent.Action.MEMBERSHIP_ROLE_CHANGED,
            target_id=str(membership.id),
        )
        self.assertEqual(
            event.metadata,
            {"role_from": OrganizationRole.OPERATOR, "role_to": OrganizationRole.APPROVER},
        )

    def test_membership_deactivate_reactivate(self):
        auth(self.client, self.admin_a)
        membership = OrganizationMembership.objects.get(
            user=self.member_a, organization=self.org_a
        )
        response = self.client.patch(
            self.url_detail(self.org_a.id, membership.id),
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        membership.refresh_from_db()
        self.assertFalse(membership.is_active)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditEvent.Action.MEMBERSHIP_DEACTIVATED,
                target_id=str(membership.id),
            ).exists()
        )
        response = self.client.patch(
            self.url_detail(self.org_a.id, membership.id),
            {"is_active": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        membership.refresh_from_db()
        self.assertTrue(membership.is_active)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditEvent.Action.MEMBERSHIP_ACTIVATED,
                target_id=str(membership.id),
            ).exists()
        )

    def test_membership_update_rejects_finance_admin_role(self):
        auth(self.client, self.admin_a)
        membership = OrganizationMembership.objects.get(
            user=self.member_a, organization=self.org_a
        )
        response = self.client.patch(
            self.url_detail(self.org_a.id, membership.id),
            {"role": OrganizationRole.FINANCE_ADMIN},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        membership.refresh_from_db()
        self.assertEqual(membership.role, OrganizationRole.OPERATOR)
        self.assertFalse(
            AuditEvent.objects.filter(target_id=str(membership.id)).exists()
        )

    def test_admin_cannot_modify_own_membership(self):
        auth(self.client, self.admin_a)
        own = OrganizationMembership.objects.get(
            user=self.admin_a, organization=self.org_a
        )
        response = self.client.patch(
            self.url_detail(self.org_a.id, own.id),
            {"role": OrganizationRole.OPERATOR},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        own.refresh_from_db()
        self.assertEqual(own.role, OrganizationRole.FINANCE_ADMIN)

    def test_admin_cannot_modify_superuser_membership(self):
        auth(self.client, self.admin_a)
        OrganizationMembership.objects.create(
            user=self.superuser,
            organization=self.org_a,
            role=OrganizationRole.OPERATOR,
        )
        membership = OrganizationMembership.objects.get(
            user=self.superuser, organization=self.org_a
        )
        response = self.client.patch(
            self.url_detail(self.org_a.id, membership.id),
            {"role": OrganizationRole.AUDITOR},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        membership.refresh_from_db()
        self.assertEqual(membership.role, OrganizationRole.OPERATOR)

    def test_membership_of_other_org_returns_404(self):
        auth(self.client, self.admin_a)
        foreign = OrganizationMembership.objects.get(
            user=self.admin_b, organization=self.org_b
        )
        response = self.client.patch(
            self.url_detail(self.org_a.id, foreign.id),
            {"role": OrganizationRole.AUDITOR},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        foreign.refresh_from_db()
        self.assertEqual(foreign.role, OrganizationRole.FINANCE_ADMIN)

    def test_membership_unknown_id_returns_404(self):
        auth(self.client, self.admin_a)
        response = self.client.patch(
            self.url_detail(self.org_a.id, uuid.uuid4()),
            {"role": OrganizationRole.AUDITOR},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_role_change_takes_effect_on_next_request(self):
        auth(self.client, self.admin_a)
        # Demote the co-admin: the change must apply to the very next request.
        coadmin_membership = OrganizationMembership.objects.get(
            user=self.admin_a2, organization=self.org_a
        )
        response = self.client.patch(
            self.url_detail(self.org_a.id, coadmin_membership.id),
            {"role": OrganizationRole.OPERATOR},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        auth(self.client, self.admin_a2)
        response = self.client.get(self.url_list(self.org_a.id))
        self.assertEqual(response.status_code, 404)

    def test_inactive_membership_stops_authorizing(self):
        # A member whose membership is deactivated loses all org access.
        auth(self.client, self.admin_a)
        membership = OrganizationMembership.objects.get(
            user=self.member_a, organization=self.org_a
        )
        self.client.patch(
            self.url_detail(self.org_a.id, membership.id),
            {"is_active": False},
            format="json",
        )
        auth(self.client, self.member_a)
        self.assertEqual(
            self.client.get(f"/api/v1/organizations/{self.org_a.id}/").status_code,
            404,
        )
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/auth/me/").data["memberships"], [])

    # --- input hygiene ----------------------------------------------------------
    def test_malformed_uuids_return_404(self):
        auth(self.client, self.admin_a)
        self.assertEqual(
            self.client.get("/api/v1/organizations/not-a-uuid/memberships/").status_code,
            404,
        )
        self.assertEqual(
            self.client.patch(
                "/api/v1/organizations/not-a-uuid/memberships/not-a-uuid/",
                {"role": "OPERATOR"},
                format="json",
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/organizations/not-a-uuid/users/",
                {"email": "x@y.z", "role": "OPERATOR"},
                format="json",
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.patch(
                "/api/v1/organizations/not-a-uuid/users/not-a-uuid/",
                {"is_active": False},
                format="json",
            ).status_code,
            404,
        )

    # --- audit trail --------------------------------------------------------------
    def test_audit_events_are_append_only(self):
        auth(self.client, self.admin_a)
        membership = OrganizationMembership.objects.get(
            user=self.member_a, organization=self.org_a
        )
        self.client.patch(
            self.url_detail(self.org_a.id, membership.id),
            {"role": OrganizationRole.APPROVER},
            format="json",
        )
        event = AuditEvent.objects.get(
            action=AuditEvent.Action.MEMBERSHIP_ROLE_CHANGED
        )
        with self.assertRaises(ValueError):
            event.metadata = {"role_from": "x", "role_to": "FINANCE_ADMIN"}
            event.save()
        with self.assertRaises(ValueError):
            event.delete()

    def test_failed_audit_rolls_back_membership_creation(self):
        client = APIClient(raise_request_exception=False)
        auth(client, self.admin_a)
        with mock.patch(
            "apps.organizations.views.AuditEvent.objects.create",
            side_effect=RuntimeError("audit store failed"),
        ):
            response = client.post(
                self.url_list(self.org_a.id),
                {"user": str(self.nomember.id), "role": OrganizationRole.OPERATOR},
                format="json",
            )
        self.assertEqual(response.status_code, 500)
        self.assertFalse(
            OrganizationMembership.objects.filter(
                user=self.nomember, organization=self.org_a
            ).exists()
        )

    def test_failed_audit_rolls_back_membership_update(self):
        client = APIClient(raise_request_exception=False)
        auth(client, self.admin_a)
        membership = OrganizationMembership.objects.get(
            user=self.member_a, organization=self.org_a
        )
        with mock.patch(
            "apps.organizations.views.AuditEvent.objects.create",
            side_effect=RuntimeError("audit store failed"),
        ):
            response = client.patch(
                self.url_detail(self.org_a.id, membership.id),
                {"role": OrganizationRole.APPROVER},
                format="json",
            )
        self.assertEqual(response.status_code, 500)
        membership.refresh_from_db()
        self.assertEqual(membership.role, OrganizationRole.OPERATOR)

    def test_existing_account_keeps_password_and_privileges(self):
        # Case 21: adding an existing person as a member must never change
        # their credentials or global privileges.
        existing = User.objects.create_superuser(username="existing_root", password="keep-secret")
        auth(self.client, self.admin_a)
        response = self.client.post(
            self.url_list(self.org_a.id),
            {"user": str(existing.id), "role": OrganizationRole.OPERATOR},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        existing.refresh_from_db()
        self.assertTrue(existing.check_password("keep-secret"))
        self.assertTrue(existing.is_superuser)
        self.assertTrue(existing.is_staff)
        membership = OrganizationMembership.objects.get(
            user=existing, organization=self.org_a
        )
        self.assertEqual(membership.role, OrganizationRole.OPERATOR)
