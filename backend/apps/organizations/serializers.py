"""Organization API serializers."""

from django.contrib.auth import get_user_model

from rest_framework import serializers

from .models import (
    Invoice,
    InvoiceApproval,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    Policy,
    PolicyDecision,
    Vendor,
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

    def create(self, validated_data, **kwargs):
        # DRF merges save() kwargs (organization, created_by) into
        # validated_data; created_by is server-set and never client-writable.
        created_by = validated_data.pop("created_by", kwargs.get("created_by"))
        organization = validated_data.pop("organization")
        return Invoice.objects.create(
            **validated_data,
            organization=organization,
            created_by=created_by,
        )


# ---------------------------------------------------------------------------
# Policy engine (Slice 6)
# ---------------------------------------------------------------------------


class PolicySerializer(serializers.ModelSerializer):
    """Read representation of a policy version (immutable)."""

    class Meta:
        model = Policy
        fields = [
            "id",
            "version",
            "is_active",
            "allowed_currencies",
            "max_amount",
            "escalation_threshold",
            "require_due_date",
            "require_description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields



class InvoiceApprovalSerializer(serializers.ModelSerializer):
    """Writable human decision on an invoice. Whitelist: only `decision`
    (approved|rejected) and an optional `rationale`. Actor, organization,
    invoice, timestamps and audit fields are read-only / server-set."""

    class Meta:
        model = InvoiceApproval
        fields = ["id", "invoice", "organization", "decision", "decided_by", "rationale", "created_at"]
        read_only_fields = ["id", "invoice", "organization", "decided_by", "created_at"]

    def validate_decision(self, value):
        if value not in (InvoiceApproval.Decision.APPROVED, InvoiceApproval.Decision.REJECTED):
            raise serializers.ValidationError("Decision must be 'approved' or 'rejected'.")
        return value


class PolicyCreateSerializer(serializers.Serializer):
    """Create a new policy version for the URL organization.

    Rule semantics (documented): `allowed_currencies=[]` means no currency
    restriction; `max_amount` is a hard cap (exceeding it blocks);
    `escalation_threshold` escalates amounts above it (if not blocked
    first); `require_due_date` / `require_description` escalate invoices
    with missing data. When both limits are set, `escalation_threshold`
    must not exceed `max_amount`.
    """

    allowed_currencies = serializers.ListField(
        child=serializers.CharField(max_length=3),
        required=False,
        default=list,
    )
    max_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    escalation_threshold = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    require_due_date = serializers.BooleanField(required=False, default=False)
    require_description = serializers.BooleanField(required=False, default=False)

    def validate_allowed_currencies(self, value):
        normalized = []
        for code in value:
            currency = code.strip().upper()
            if currency not in SUPPORTED_CURRENCIES:
                raise serializers.ValidationError(
                    f"Unsupported currency: {code}. Supported codes: {', '.join(SUPPORTED_CURRENCIES)}."
                )
            normalized.append(currency)
        return normalized

    def validate_max_amount(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                "max_amount must be greater than zero."
            )
        return value

    def validate_escalation_threshold(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                "escalation_threshold must be greater than zero."
            )
        return value

    def validate(self, attrs):
        max_amount = attrs.get("max_amount")
        threshold = attrs.get("escalation_threshold")
        if max_amount is not None and threshold is not None and threshold > max_amount:
            raise serializers.ValidationError(
                "escalation_threshold must not exceed max_amount: amounts above "
                "max_amount are blocked first."
            )
        return attrs

    def create(self, validated_data):
        organization = validated_data.pop("organization")
        Policy.objects.filter(organization=organization, is_active=True).update(
            is_active=False
        )
        last = (
            Policy.objects.filter(organization=organization)
            .order_by("-version")
            .first()
        )
        version = (last.version + 1) if last else 1
        return Policy.objects.create(
            organization=organization, version=version, **validated_data
        )


class PolicyDecisionSerializer(serializers.ModelSerializer):
    """Read representation of a persisted policy decision."""

    class Meta:
        model = PolicyDecision
        fields = [
            "id",
            "invoice",
            "result",
            "reason_code",
            "reason_detail",
            "policy_id",
            "policy_version",
            "rules_snapshot",
            "evaluated_by",
            "created_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Global organization administration (final slice)
# ---------------------------------------------------------------------------
# These serializers back the SUPERADMIN-ONLY global surface. Membership
# creation never exposes writable global flags: only `name` and `admin_email`
# are accepted on create, and only `name`/`status` on update. The client can
# never set is_superuser, is_staff, permissions, or arbitrary roles.


class GlobalOrganizationCreateSerializer(serializers.Serializer):
    """Create an organization atomically with its initial FINANCE_ADMIN.

    The initial administrator is identified by email. If the account already
    exists it is reused untouched (password and privileges preserved); if it
    does not, the view creates it with an unusable password and issues a
    one-time setup token, following the existing account-lifecycle flow. The
    role is fixed to FINANCE_ADMIN and is never client-selectable.
    """

    name = serializers.CharField(max_length=200)
    admin_email = serializers.EmailField()

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError(
                "Organization name must not be blank."
            )
        if Organization.objects.filter(name=name).exists():
            raise serializers.ValidationError(
                "An organization with this name already exists."
            )
        return name

    def validate_admin_email(self, value):
        email = value.strip().lower()
        if len(email) > 150:
            raise serializers.ValidationError(
                "Email must be at most 150 characters."
            )
        return email


class GlobalOrganizationUpdateSerializer(serializers.ModelSerializer):
    """Update the administrative fields the model allows: name and status.

    The tenant ownership of vendors, invoices, policies, and memberships is
    immutable through this surface: no relational field is writable, and the
    unique name constraint is enforced by the model validation.
    """

    class Meta:
        model = Organization
        fields = ["name", "status"]

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError(
                "Organization name must not be blank."
            )
        if Organization.objects.filter(name=name).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError(
                "An organization with this name already exists."
            )
        return name


class GlobalUserCandidateSerializer(serializers.ModelSerializer):
    """Minimal, safe user reference for the initial-admin picker.

    Only identity fields are exposed — never passwords, hashes, tokens,
    memberships, or global privilege flags.
    """

    class Meta:
        model = User
        fields = ["id", "username", "email"]
        read_only_fields = fields
