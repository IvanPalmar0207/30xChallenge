"""Organization API serializers."""

from django.contrib.auth import get_user_model

from rest_framework import serializers

from .models import (
    Organization,
    OrganizationMembership,
    OrganizationRole,
    Vendor,
    Invoice,
)

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


# ---------------------------------------------------------------------------
# Vendors (Slice 3)
# ---------------------------------------------------------------------------


def _normalize_tax_id(value):
    """Conservative, jurisdiction-agnostic normalization: strip + uppercase.

    Hyphens, internal spaces, and other characters are preserved verbatim;
    no country-specific format validation is performed (documented
    limitation). The normalized value is what gets stored, so the database
    uniqueness constraint operates on the same normalized form.
    """

    normalized = value.strip().upper()
    if not normalized:
        raise serializers.ValidationError(
            "Tax identifier must not be blank."
        )
    if len(normalized) > 50:
        raise serializers.ValidationError(
            "Tax identifier must be at most 50 characters."
        )
    return normalized


class VendorSerializer(serializers.ModelSerializer):
    """Read representation of a vendor (organization ownership read-only)."""

    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = Vendor
        fields = [
            "id",
            "organization",
            "legal_name",
            "tax_id",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class VendorCreateSerializer(serializers.Serializer):
    """Create a vendor in the URL's organization.

    Writable allowlist: legal_name and tax_id only. Status defaults to
    active server-side; organization ownership comes from the URL, never
    from the client; internal/audit fields are not writable.
    """

    legal_name = serializers.CharField(max_length=200)
    tax_id = serializers.CharField()

    def validate_tax_id(self, value):
        return _normalize_tax_id(value)

    def validate(self, attrs):
        organization = self.context.get("organization")
        if organization is not None and Vendor.objects.filter(
            organization=organization, tax_id=attrs["tax_id"]
        ).exists():
            raise serializers.ValidationError(
                "A vendor with this tax identifier already exists in this organization."
            )
        return attrs

    def create(self, validated_data):
        organization = validated_data.pop("organization")
        return Vendor.objects.create(**validated_data, organization=organization)


class VendorUpdateSerializer(serializers.ModelSerializer):
    """Update business data only: legal_name and/or tax_id (partial).

    `status` is deliberately not writable here: an ordinary update can never
    silently reactivate an inactive vendor. Activation/deactivation are
    explicit, separately authorized operations.
    """

    class Meta:
        model = Vendor
        fields = ["legal_name", "tax_id"]

    def validate_tax_id(self, value):
        return _normalize_tax_id(value)

    def validate(self, attrs):
        organization = self.context.get("organization")
        if "tax_id" in attrs and organization is not None:
            queryset = Vendor.objects.filter(
                organization=organization, tax_id=attrs["tax_id"]
            )
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    "A vendor with this tax identifier already exists in this organization."
                )
        return attrs


# ---------------------------------------------------------------------------
# Invoices (Slice 4)
# ---------------------------------------------------------------------------


# Curated, explicit list of supported ISO 4217 currency codes. No other
# codes are accepted; the list is documented in the README and can be extended
# deliberately in a later slice.
SUPPORTED_CURRENCIES = [
    "USD",
    "EUR",
    "GBP",
    "COP",
    "MXN",
    "ARS",
    "BRL",
    "PEN",
    "CLP",
    "CHF",
    "CAD",
    "JPY",
]


def _normalize_invoice_number(value):
    """Conservative normalization: strip + uppercase.

    Consistent with the tax-identifier convention: the normalized value is
    what gets stored, so the database uniqueness constraint operates on the
    stored value while normalization itself is an application-level
    guarantee (documented limitation).
    """

    normalized = value.strip().upper()
    if not normalized:
        raise serializers.ValidationError("Invoice number must not be blank.")
    if len(normalized) > 100:
        raise serializers.ValidationError(
            "Invoice number must be at most 100 characters."
        )
    return normalized


class InvoiceVendorSerializer(serializers.ModelSerializer):
    """Read-only minimal vendor reference shown inside invoice payloads."""

    class Meta:
        model = Vendor
        fields = ["id", "legal_name", "tax_id"]


class InvoiceSerializer(serializers.ModelSerializer):
    vendor = InvoiceVendorSerializer(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "vendor",
            "invoice_number",
            "issue_date",
            "due_date",
            "amount",
            "currency",
            "description",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class InvoiceCreateSerializer(serializers.Serializer):
    """Create an invoice in the URL's organization.

    Writable allowlist: vendor, invoice_number, issue_date, due_date, amount,
    currency, description. Organization ownership comes from the URL; status
    is always `received` server-side; internal/audit fields are not writable.
    """

    vendor = serializers.PrimaryKeyRelatedField(queryset=Vendor.objects.all())
    invoice_number = serializers.CharField()
    issue_date = serializers.DateField()
    due_date = serializers.DateField(required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField(max_length=3)
    description = serializers.CharField(
        required=False, allow_blank=True, max_length=500
    )

    def validate_invoice_number(self, value):
        return _normalize_invoice_number(value)

    def validate_currency(self, value):
        currency = value.strip().upper()
        if currency not in SUPPORTED_CURRENCIES:
            raise serializers.ValidationError(
                f"Unsupported currency. Supported codes: {', '.join(SUPPORTED_CURRENCIES)}."
            )
        return currency

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate(self, attrs):
        organization = self.context.get("organization")
        vendor = attrs.get("vendor")
        if organization is not None and vendor is not None:
            # Defense in depth: the view already answers 404 for vendors that
            # do not exist or belong to another organization.
            if vendor.organization_id != organization.id:
                raise serializers.ValidationError(
                    {"vendor": "This vendor does not belong to this organization."}
                )
            if vendor.status != Vendor.Status.ACTIVE:
                raise serializers.ValidationError({"vendor": "Vendor is inactive."})
            if Invoice.objects.filter(
                organization=organization,
                vendor=vendor,
                invoice_number=attrs["invoice_number"],
            ).exists():
                raise serializers.ValidationError(
                    "An invoice with this number already exists for this vendor in this organization."
                )
        issue_date = attrs.get("issue_date")
        due_date = attrs.get("due_date")
        if issue_date is not None and due_date is not None and due_date < issue_date:
            raise serializers.ValidationError(
                {"due_date": "Due date must not be earlier than the issue date."}
            )
        return attrs

    def create(self, validated_data):
        organization = validated_data.pop("organization")
        return Invoice.objects.create(**validated_data, organization=organization)
