"""Accounts app serializers (identity and memberships)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
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


class UserPublicSerializer(serializers.ModelSerializer):
    """Safe identity payload for the login response.

    Deliberately excludes password, tokens, and staff/superuser flags; the
    client calls /auth/me/ for memberships.
    """

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]


class LoginSerializer(serializers.Serializer):
    """Credentials for POST /api/v1/auth/login/."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        return value.strip().lower()


class SetPasswordSerializer(serializers.Serializer):
    """One-time setup token plus the new password.

    The password is validated with Django's password validators (length,
    common, numeric, similarity). The user is resolved server-side from the
    setup token; the raw token is never stored or logged.
    """

    setup_token = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        validate_password(value)
        return value
