"""Accounts app serializers (identity and memberships)."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.organizations.models import OrganizationMembership

User = get_user_model()


class MembershipSummarySerializer(serializers.Serializer):
    """One active membership: organization reference plus the scoped role."""

    organization_id = serializers.UUIDField(source="organization.id")
    organization_name = serializers.CharField(source="organization.name")
    role = serializers.CharField()


class MeSerializer(serializers.ModelSerializer):
    """Safe identity profile for /auth/me/.

    Deliberately excludes password, tokens, and staff/superuser flags: global
    administrative status is a separate concept and must never be presented
    as organization authority (implementation contract, invariant: approval
    authority is never implicit).
    """

    memberships = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "memberships"]

    def get_memberships(self, obj):
        qs = (
            obj.memberships.select_related("organization")
            .filter(is_active=True)
            .order_by("organization__name")
        )
        return MembershipSummarySerializer(qs, many=True).data
