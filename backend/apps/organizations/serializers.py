"""Organization API serializers."""

from django.contrib.auth import get_user_model

from rest_framework import serializers

from .models import Organization, OrganizationMembership, OrganizationRole

User = get_user_model()

# Roles an administrator may assign through the API. FINANCE_ADMIN is
# intentionally absent: no delegation rule exists yet, so granting it would
# exceed the actor's own authority (Slice 2 spec S4). Only a future, explicit
# delegation contract may add it.
GRANTABLE_ROLES = [
    OrganizationRole.OPERATOR,
    OrganizationRole.APPROVER,
    OrganizationRole.AUDITOR,
]


def _reject_non_grantable_role(value):
    if value == OrganizationRole.FINANCE_ADMIN:
        raise serializers.ValidationError(
            "Granting FINANCE_ADMIN is not permitted: no delegation rule exists."
        )
    return value


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "status", "created_at", "updated_at"]
        read_only_fields = fields


class MembershipUserSerializer(serializers.ModelSerializer):
    """Read-only minimal user reference shown inside membership payloads."""

    class Meta:
        model = User
        fields = ["id", "username", "email"]


class MembershipSerializer(serializers.ModelSerializer):
    user = MembershipUserSerializer(read_only=True)
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = OrganizationMembership
        fields = [
            "id",
            "user",
            "organization",
            "role",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class MembershipCreateSerializer(serializers.Serializer):
    """Create a membership for an existing user in the URL's organization."""

    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    role = serializers.ChoiceField(choices=GRANTABLE_ROLES)

    def validate_role(self, value):
        return _reject_non_grantable_role(value)

    def validate(self, attrs):
        organization = self.context.get("organization")
        user = attrs["user"]
        if organization is not None and OrganizationMembership.objects.filter(
            user=user, organization=organization
        ).exists():
            raise serializers.ValidationError(
                "This user already has a membership in this organization."
            )
        return attrs

    def create(self, validated_data):
        organization = validated_data.pop("organization")
        return OrganizationMembership.objects.create(
            **validated_data,
            organization=organization,
        )


class MembershipUpdateSerializer(serializers.ModelSerializer):
    """Update a membership's role and/or active state (partial updates)."""

    class Meta:
        model = OrganizationMembership
        fields = ["role", "is_active"]

    def validate_role(self, value):
        return _reject_non_grantable_role(value)


class UserCreateSerializer(serializers.Serializer):
    """Create an account plus its first membership (scoped to the URL org).

    The normalized email doubles as the username, so a person has exactly one
    account across all organizations and identity is unique per email address
    without a separate username field. The client can never influence
    is_superuser/is_staff/global permissions: writable fields are whitelisted
    here and everything else is ignored.
    """

    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=GRANTABLE_ROLES)

    def validate_email(self, value):
        email = value.strip().lower()
        if len(email) > 150:
            raise serializers.ValidationError(
                "Email must be at most 150 characters."
            )
        if User.objects.filter(username=email).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )
        return email

    def validate_role(self, value):
        return _reject_non_grantable_role(value)


class UserActivationSerializer(serializers.Serializer):
    """Deactivate or reactivate an account (scoped to the URL organization)."""

    is_active = serializers.BooleanField()
