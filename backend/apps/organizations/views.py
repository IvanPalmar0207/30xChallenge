"""Organization API views.

Read-only tenant access (OrganizationViewSet) plus organization-scoped
administration of memberships and user accounts. Administration is gated by
IsActiveOrganizationFinanceAdmin in every management view: any organization
the actor does not administer resolves to 404 (no existence disclosure), and
rule violations inside the organization return 403. Every change and its audit
record commit in one transaction.
"""

import hashlib
import logging
import secrets
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, status, viewsets
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    AuditEvent,
    Invoice,
    Organization,
    OrganizationMembership,
    PasswordSetupToken,
    Policy,
    PolicyDecision,
    Vendor,
)
from .permissions import (
    IsActiveOrganizationFinanceAdmin,
    IsActiveOrganizationInvoiceCreator,
    IsActiveOrganizationMember,
    IsActiveOrganizationMemberInUrl,
)
from .serializers import (
    InvoiceCreateSerializer,
    InvoiceSerializer,
    MembershipCreateSerializer,
    MembershipSerializer,
    MembershipUpdateSerializer,
    OrganizationSerializer,
    PolicyCreateSerializer,
    PolicyDecisionSerializer,
    PolicySerializer,
    UserActivationSerializer,
    UserCreateSerializer,
    VendorCreateSerializer,
    VendorSerializer,
    VendorUpdateSerializer,
)

logger = logging.getLogger(__name__)


class Conflict(APIException):
    """HTTP 409 for state-machine conflicts (e.g. repeated evaluation)."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict."
    default_code = "conflict"

User = get_user_model()


class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    """Organizations the authenticated user may access.

    Security: the queryset is scoped to the request user's ACTIVE memberships
    in ACTIVE organizations. Every other case — unknown UUID, inactive
    membership, inactive organization, or membership in a different
    organization — resolves to the same 404, so the API never discloses
    whether another organization exists (consistent authorization behavior).
    """

    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated, IsActiveOrganizationMember]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Organization.objects.none()
        return (
            Organization.objects.filter(
                status=Organization.Status.ACTIVE,
                memberships__user=user,
                memberships__is_active=True,
            )
            .distinct()
            .order_by("name")
        )


def _audit(actor, organization, action, target_type, target_id, metadata=None):
    """Create one audit event.

    Any failure propagates so the caller's atomic block rolls back the
    accompanying change: a change is never reported successful unless its
    audit record persisted (Slice 2 spec S6).
    """
    return AuditEvent.objects.create(
        actor=actor,
        organization=organization,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        metadata=metadata or {},
    )


class MembershipListCreateView(generics.ListCreateAPIView):
    """List and create memberships of the URL organization (admin only)."""

    permission_classes = [IsAuthenticated, IsActiveOrganizationFinanceAdmin]

    def get_queryset(self):
        return (
            OrganizationMembership.objects.filter(
                organization_id=self.kwargs["organization_pk"]
            )
            .select_related("user", "organization")
            .order_by("user__username")
        )

    def get_serializer_class(self):
        if self.request.method == "GET":
            return MembershipSerializer
        return MembershipCreateSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["organization"] = self.get_organization()
        return context

    def get_organization(self):
        return get_object_or_404(Organization, pk=self.kwargs["organization_pk"])

    def perform_create(self, serializer):
        organization = self.get_organization()
        try:
            with transaction.atomic():
                membership = serializer.save(organization=organization)
                _audit(
                    actor=self.request.user,
                    organization=organization,
                    action=AuditEvent.Action.MEMBERSHIP_CREATED,
                    target_type="membership",
                    target_id=membership.id,
                    metadata={
                        "user": str(membership.user_id),
                        "role": membership.role,
                    },
                )
        except IntegrityError:
            # Race backstop: the serializer's validate() already rejects
            # existing memberships; this covers concurrent creation.
            raise ValidationError(
                "This user already has a membership in this organization."
            )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        response_serializer = MembershipSerializer(
            serializer.instance, context=self.get_serializer_context()
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


class MembershipDetailView(generics.RetrieveUpdateAPIView):
    """Read or update one membership of the URL organization (admin only).

    Allowed changes: role (never FINANCE_ADMIN) and is_active. No delete: an
    inactive membership keeps its historical record.
    """

    permission_classes = [IsAuthenticated, IsActiveOrganizationFinanceAdmin]

    def get_queryset(self):
        return OrganizationMembership.objects.filter(
            organization_id=self.kwargs["organization_pk"]
        ).select_related("user", "organization")

    def get_serializer_class(self):
        if self.request.method == "GET":
            return MembershipSerializer
        return MembershipUpdateSerializer

    def perform_update(self, serializer):
        actor = self.request.user
        membership = serializer.instance
        if membership.user_id == actor.id:
            raise PermissionDenied(
                "You cannot modify your own membership: self-promotion and "
                "accidental self-lockout are prevented."
            )
        if membership.user.is_superuser:
            raise PermissionDenied(
                "Global superuser memberships cannot be modified through "
                "organization endpoints."
            )
        role_before = membership.role
        active_before = membership.is_active
        with transaction.atomic():
            serializer.save()
            membership.refresh_from_db()
            if membership.role != role_before:
                _audit(
                    actor=actor,
                    organization=membership.organization,
                    action=AuditEvent.Action.MEMBERSHIP_ROLE_CHANGED,
                    target_type="membership",
                    target_id=membership.id,
                    metadata={
                        "role_from": role_before,
                        "role_to": membership.role,
                    },
                )
            if membership.is_active != active_before:
                _audit(
                    actor=actor,
                    organization=membership.organization,
                    action=(
                        AuditEvent.Action.MEMBERSHIP_ACTIVATED
                        if membership.is_active
                        else AuditEvent.Action.MEMBERSHIP_DEACTIVATED
                    ),
                    target_type="membership",
                    target_id=membership.id,
                    metadata={"is_active": membership.is_active},
                )


class UserCreateView(generics.CreateAPIView):
    """Create an account plus its first membership (admin only).

    The initial password is unusable: Django stores no credential until a
    separately designed password-setup flow exists, so the new account cannot
    log in yet (documented MVP limitation). No password, hash, or token ever
    appears in the response.
    """

    permission_classes = [IsAuthenticated, IsActiveOrganizationFinanceAdmin]
    serializer_class = UserCreateSerializer

    def get_organization(self):
        return get_object_or_404(Organization, pk=self.kwargs["organization_pk"])

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = self.get_organization()
        email = serializer.validated_data["email"]
        role = serializer.validated_data["role"]
        try:
            with transaction.atomic():
                # create_user() without a password sets an unusable password.
                user = User.objects.create_user(
                    username=email, email=email, is_active=True
                )
                membership = OrganizationMembership.objects.create(
                    user=user, organization=organization, role=role
                )
                _audit(
                    actor=request.user,
                    organization=organization,
                    action=AuditEvent.Action.ACCOUNT_CREATED,
                    target_type="user",
                    target_id=user.id,
                    metadata={"email": email},
                )
                _audit(
                    actor=request.user,
                    organization=organization,
                    action=AuditEvent.Action.MEMBERSHIP_CREATED,
                    target_type="membership",
                    target_id=membership.id,
                    metadata={
                        "user": str(user.id),
                        "role": role,
                    },
                )
        except IntegrityError:
            # Race backstop for concurrent account creation with one email.
            raise ValidationError("A user with this email already exists.")
        return Response(
            {
                "id": user.id,
                "email": user.email,
                "role": membership.role,
                "membership_id": membership.id,
            },
            status=status.HTTP_201_CREATED,
        )


class UserActivationView(generics.UpdateAPIView):
    """Deactivate or reactivate an account that belongs to the URL org (admin
    only). The target user must hold a membership in that organization; any
    other user is indistinguishable from an unknown one (404)."""

    permission_classes = [IsAuthenticated, IsActiveOrganizationFinanceAdmin]
    serializer_class = UserActivationSerializer

    def get_queryset(self):
        return User.objects.filter(
            memberships__organization_id=self.kwargs["organization_pk"]
        )

    def get_organization(self):
        return get_object_or_404(Organization, pk=self.kwargs["organization_pk"])

    def perform_update(self, serializer):
        actor = self.request.user
        target = serializer.instance
        if "is_active" not in serializer.validated_data:
            raise ValidationError("The is_active field is required.")
        if target.id == actor.id:
            raise PermissionDenied("You cannot deactivate your own account.")
        if target.is_superuser:
            raise PermissionDenied(
                "Global superuser accounts cannot be modified through "
                "organization endpoints."
            )
        is_active_after = serializer.validated_data["is_active"]
        with transaction.atomic():
            target.is_active = is_active_after
            target.save(update_fields=["is_active"])
            _audit(
                actor=actor,
                organization=self.get_organization(),
                action=(
                    AuditEvent.Action.ACCOUNT_ACTIVATED
                    if is_active_after
                    else AuditEvent.Action.ACCOUNT_DEACTIVATED
                ),
                target_type="user",
                target_id=target.id,
                metadata={"is_active": is_active_after},
            )


# Lifetime of a one-time password-setup token (Slice 5).
SETUP_TOKEN_TTL_HOURS = 72


class UserInviteView(generics.GenericAPIView):
    """Issue a one-time password-setup token for an account of the URL org
    (admin only).

    The raw token is returned exactly once; only its SHA-256 hash is stored.
    Previous unused tokens for the same user are invalidated, so there is at
    most one active invitation per account. The admin relays the token
    out-of-band (in production this would be emailed). An ordinary access
    token is never accepted by the set-password flow, so a leaked access
    token cannot take over an account that has no password yet.
    """

    permission_classes = [IsAuthenticated, IsActiveOrganizationFinanceAdmin]

    def get_queryset(self):
        return User.objects.filter(
            memberships__organization_id=self.kwargs["organization_pk"]
        )

    def get_organization(self):
        return get_object_or_404(Organization, pk=self.kwargs["organization_pk"])

    def post(self, request, *args, **kwargs):
        user = self.get_object()
        if user.is_superuser:
            raise PermissionDenied(
                "Global superuser accounts cannot be invited through "
                "organization endpoints."
            )
        PasswordSetupToken.objects.filter(user=user, used_at__isnull=True).delete()
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = timezone.now() + timedelta(hours=SETUP_TOKEN_TTL_HOURS)
        with transaction.atomic():
            PasswordSetupToken.objects.create(
                user=user, token_hash=token_hash, expires_at=expires_at
            )
            _audit(
                actor=request.user,
                organization=self.get_organization(),
                action=AuditEvent.Action.INVITATION_ISSUED,
                target_type="user",
                target_id=user.id,
                metadata={"expires_at": expires_at.isoformat()},
            )
        return Response(
            {"setup_token": raw_token, "expires_at": expires_at.isoformat()},
            status=status.HTTP_201_CREATED,
        )


class VendorListCreateView(generics.ListCreateAPIView):
    """List (any active member) or create (FINANCE_ADMIN) vendors of the URL
    organization.

    Reads include inactive vendors so they remain distinguishable from
    nonexistent ones; mutations are reserved for FINANCE_ADMIN. The
    organization is resolved from the URL and never from the request body.
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsActiveOrganizationFinanceAdmin()]
        return [IsAuthenticated(), IsActiveOrganizationMemberInUrl()]

    def get_queryset(self):
        return (
            Vendor.objects.filter(organization_id=self.kwargs["organization_pk"])
            .select_related("organization")
            .order_by("legal_name")
        )

    def get_serializer_class(self):
        if self.request.method == "GET":
            return VendorSerializer
        return VendorCreateSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["organization"] = self.get_organization()
        return context

    def get_organization(self):
        return get_object_or_404(Organization, pk=self.kwargs["organization_pk"])

    def perform_create(self, serializer):
        organization = self.get_organization()
        try:
            with transaction.atomic():
                vendor = serializer.save(organization=organization)
                _audit(
                    actor=self.request.user,
                    organization=organization,
                    action=AuditEvent.Action.VENDOR_CREATED,
                    target_type="vendor",
                    target_id=vendor.id,
                    metadata={"legal_name": vendor.legal_name},
                )
        except IntegrityError:
            # Race backstop: validate() already rejects duplicates; this
            # covers concurrent creation of the same normalized tax_id.
            raise ValidationError(
                "A vendor with this tax identifier already exists in this organization."
            )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        response_serializer = VendorSerializer(
            serializer.instance, context=self.get_serializer_context()
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


class VendorDetailView(generics.RetrieveUpdateAPIView):
    """Read (any active member) or update business data (FINANCE_ADMIN) of
    one vendor.

    `status` is deliberately not writable here: an ordinary update can never
    silently reactivate an inactive vendor. Activation and deactivation are
    explicit, separately authorized operations.
    """

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH"):
            return [IsAuthenticated(), IsActiveOrganizationFinanceAdmin()]
        return [IsAuthenticated(), IsActiveOrganizationMemberInUrl()]

    def get_queryset(self):
        return Vendor.objects.filter(
            organization_id=self.kwargs["organization_pk"]
        ).select_related("organization")

    def get_serializer_class(self):
        if self.request.method == "GET":
            return VendorSerializer
        return VendorUpdateSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["organization"] = self.get_organization()
        return context

    def get_organization(self):
        return get_object_or_404(Organization, pk=self.kwargs["organization_pk"])

    def perform_update(self, serializer):
        vendor = serializer.instance
        changes = {}
        for field in ("legal_name", "tax_id"):
            if field in serializer.validated_data:
                new_value = serializer.validated_data[field]
                if getattr(vendor, field) != new_value:
                    changes[field] = {"from": getattr(vendor, field), "to": new_value}
        if not changes:
            # No business-data change: nothing to persist, nothing to audit.
            return
        try:
            with transaction.atomic():
                serializer.save()
                _audit(
                    actor=self.request.user,
                    organization=vendor.organization,
                    action=AuditEvent.Action.VENDOR_UPDATED,
                    target_type="vendor",
                    target_id=vendor.id,
                    metadata={"changes": changes},
                )
        except IntegrityError:
            raise ValidationError(
                "A vendor with this tax identifier already exists in this organization."
            )


def _change_vendor_status(request, vendor, active):
    """Explicit activation/deactivation with audit, in one transaction.

    Idempotent: setting the same status is a no-op with no audit event. The
    record is never deleted; deactivation preserves its historical identity.
    """
    organization = vendor.organization
    before = vendor.status
    after = Vendor.Status.ACTIVE if active else Vendor.Status.INACTIVE
    if before == after:
        return
    with transaction.atomic():
        vendor.status = after
        vendor.save(update_fields=["status", "updated_at"])
        _audit(
            actor=request.user,
            organization=organization,
            action=(
                AuditEvent.Action.VENDOR_ACTIVATED
                if active
                else AuditEvent.Action.VENDOR_DEACTIVATED
            ),
            target_type="vendor",
            target_id=vendor.id,
            metadata={"status_before": before, "status_after": after},
        )


class VendorActivateView(generics.GenericAPIView):
    """Explicitly activate a vendor (FINANCE_ADMIN only)."""

    permission_classes = [IsAuthenticated, IsActiveOrganizationFinanceAdmin]

    def get_queryset(self):
        return Vendor.objects.filter(
            organization_id=self.kwargs["organization_pk"]
        ).select_related("organization")

    def post(self, request, *args, **kwargs):
        vendor = self.get_object()
        _change_vendor_status(request, vendor, active=True)
        return Response(VendorSerializer(vendor).data, status=status.HTTP_200_OK)


class VendorDeactivateView(generics.GenericAPIView):
    """Explicitly deactivate a vendor (FINANCE_ADMIN only). The record and
    its historical identity are preserved; deactivation never deletes."""

    permission_classes = [IsAuthenticated, IsActiveOrganizationFinanceAdmin]

    def get_queryset(self):
        return Vendor.objects.filter(
            organization_id=self.kwargs["organization_pk"]
        ).select_related("organization")

    def post(self, request, *args, **kwargs):
        vendor = self.get_object()
        _change_vendor_status(request, vendor, active=False)
        return Response(VendorSerializer(vendor).data, status=status.HTTP_200_OK)


class InvoiceListCreateView(generics.ListCreateAPIView):
    """List (any active member) or create (FINANCE_ADMIN/OPERATOR) invoices
    of the URL organization.

    The organization is resolved from the URL and never from the request
    body. Vendors that do not exist or belong to another organization answer
    the same uniform 404 (no existence disclosure); an inactive vendor is a
    controlled 400 validation error.
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsActiveOrganizationInvoiceCreator()]
        return [IsAuthenticated(), IsActiveOrganizationMemberInUrl()]

    def get_queryset(self):
        return (
            Invoice.objects.filter(organization_id=self.kwargs["organization_pk"])
            .select_related("vendor")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.request.method == "GET":
            return InvoiceSerializer
        return InvoiceCreateSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["organization"] = self.get_organization()
        return context

    def get_organization(self):
        return get_object_or_404(Organization, pk=self.kwargs["organization_pk"])

    def create(self, request, *args, **kwargs):
        # Uniform 404 for vendors that do not exist or belong to another
        # organization (HidingByNotExisting). A malformed vendor pk falls
        # through to serializer validation, which answers a controlled 400.
        vendor_pk = request.data.get("vendor")
        if vendor_pk is not None:
            try:
                vendor_uuid = uuid.UUID(str(vendor_pk))
            except (ValueError, TypeError):
                vendor_uuid = None
            if vendor_uuid is not None:
                get_object_or_404(
                    Vendor,
                    pk=vendor_uuid,
                    organization_id=self.kwargs["organization_pk"],
                )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        response_serializer = InvoiceSerializer(
            serializer.instance, context=self.get_serializer_context()
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def perform_create(self, serializer):
        organization = self.get_organization()
        try:
            with transaction.atomic():
                invoice = serializer.save(organization=organization)
                _audit(
                    actor=self.request.user,
                    organization=organization,
                    action=AuditEvent.Action.INVOICE_CREATED,
                    target_type="invoice",
                    target_id=invoice.id,
                    metadata={
                        "invoice_number": invoice.invoice_number,
                        "vendor": str(invoice.vendor_id),
                        "amount": str(invoice.amount),
                        "currency": invoice.currency,
                    },
                )
        except IntegrityError:
            # Race backstop: validate() already rejects duplicates; this
            # covers concurrent creation of the same invoice number.
            raise ValidationError(
                "An invoice with this number already exists for this vendor in this organization."
            )


class InvoiceDetailView(generics.RetrieveAPIView):
    """Read one invoice of the URL organization (any active member)."""

    permission_classes = [IsAuthenticated, IsActiveOrganizationMemberInUrl]
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        return Invoice.objects.filter(
            organization_id=self.kwargs["organization_pk"]
        ).select_related("vendor")


# ---------------------------------------------------------------------------
# Deterministic policy engine (Slice 6)
# ---------------------------------------------------------------------------


def evaluate_invoice(invoice, policy):
    """Deterministic evaluation of one invoice against a policy.

    Precedence is `blocked -> escalated -> approved` with strict
    comparisons: `amount > max_amount` blocks; `amount >
    escalation_threshold` escalates only if not blocked before. Missing
    data escalates (cannot be decided safely). No active policy escalates
    (`no_active_policy`) — an invoice is never approved without a valid,
    applicable policy. Returns (result, reason_code, reason_detail).
    """

    if policy is None:
        return (
            PolicyDecision.Result.ESCALATED,
            "no_active_policy",
            "No active policy is configured for this organization.",
        )
    if policy.allowed_currencies and invoice.currency not in policy.allowed_currencies:
        return (
            PolicyDecision.Result.BLOCKED,
            "currency_not_allowed",
            f"Currency {invoice.currency} is not allowed by the active policy.",
        )
    if policy.max_amount is not None and invoice.amount > policy.max_amount:
        return (
            PolicyDecision.Result.BLOCKED,
            "amount_exceeds_max",
            f"Amount {invoice.amount} exceeds the policy maximum {policy.max_amount}.",
        )
    if (
        policy.escalation_threshold is not None
        and invoice.amount > policy.escalation_threshold
    ):
        return (
            PolicyDecision.Result.ESCALATED,
            "amount_exceeds_escalation_threshold",
            f"Amount {invoice.amount} exceeds the escalation threshold "
            f"{policy.escalation_threshold}.",
        )
    if policy.require_due_date and invoice.due_date is None:
        return (
            PolicyDecision.Result.ESCALATED,
            "due_date_missing",
            "The policy requires a due date.",
        )
    if policy.require_description and not (invoice.description or "").strip():
        return (
            PolicyDecision.Result.ESCALATED,
            "description_missing",
            "The policy requires a description.",
        )
    return (
        PolicyDecision.Result.APPROVED,
        "policy_ok",
        "The invoice complies with the active policy.",
    )


def _policy_snapshot(policy):
    """Unambiguous snapshot of the effective rules at evaluation time."""

    if policy is None:
        return {}
    return {
        "version": policy.version,
        "allowed_currencies": list(policy.allowed_currencies),
        "max_amount": (
            str(policy.max_amount) if policy.max_amount is not None else None
        ),
        "escalation_threshold": (
            str(policy.escalation_threshold)
            if policy.escalation_threshold is not None
            else None
        ),
        "require_due_date": policy.require_due_date,
        "require_description": policy.require_description,
    }


class PolicyListCreateView(generics.ListCreateAPIView):
    """List (any active member) or create a new policy version
    (FINANCE_ADMIN) for the URL organization."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsActiveOrganizationFinanceAdmin()]
        return [IsAuthenticated(), IsActiveOrganizationMemberInUrl()]

    def get_queryset(self):
        return Policy.objects.filter(
            organization_id=self.kwargs["organization_pk"]
        ).order_by("-version")

    def get_serializer_class(self):
        if self.request.method == "GET":
            return PolicySerializer
        return PolicyCreateSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["organization"] = self.get_organization()
        return context

    def get_organization(self):
        return get_object_or_404(Organization, pk=self.kwargs["organization_pk"])

    def perform_create(self, serializer):
        organization = self.get_organization()
        with transaction.atomic():
            policy = serializer.save(organization=organization)
            _audit(
                actor=self.request.user,
                organization=organization,
                action=AuditEvent.Action.POLICY_CREATED,
                target_type="policy",
                target_id=policy.id,
                metadata={
                    "version": policy.version,
                    "is_active": policy.is_active,
                },
            )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        response_serializer = PolicySerializer(
            serializer.instance, context=self.get_serializer_context()
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


class PolicyDetailView(generics.RetrieveAPIView):
    """Read one policy version of the URL organization (any active member)."""

    permission_classes = [IsAuthenticated, IsActiveOrganizationMemberInUrl]
    serializer_class = PolicySerializer

    def get_queryset(self):
        return Policy.objects.filter(
            organization_id=self.kwargs["organization_pk"]
        )


class InvoiceEvaluateView(generics.GenericAPIView):
    """Evaluate one invoice against the organization's active policy.

    The engine decides deterministically; the requester never chooses the
    outcome. The decision, the invoice status transition, and the audit
    event commit in one transaction; any failure rolls back everything.
    Concurrency: the invoice row is locked with select_for_update() where
    the database supports it (PostgreSQL); the unique constraint on
    PolicyDecision.invoice is the universal backstop. SQLite concurrency is
    not claimed as validated.
    """

    permission_classes = [IsAuthenticated, IsActiveOrganizationInvoiceCreator]

    def get_organization(self):
        return get_object_or_404(Organization, pk=self.kwargs["organization_pk"])

    def post(self, request, *args, **kwargs):
        organization = self.get_organization()
        invoice = get_object_or_404(
            Invoice.objects.select_for_update(),
            pk=self.kwargs["pk"],
            organization_id=organization.id,
        )
        if invoice.status != Invoice.Status.RECEIVED:
            raise Conflict("This invoice has already been evaluated.")
        policy = (
            Policy.objects.filter(organization=organization, is_active=True)
            .order_by("-version")
            .first()
        )
        try:
            result, reason_code, reason_detail = evaluate_invoice(invoice, policy)
        except Exception:
            # Fail safe: never approve on an internal error, never leave a
            # partial decision or state change, never expose internals.
            logger.exception("Invoice evaluation failed unexpectedly")
            return Response(
                {"detail": "Internal server error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        rules_snapshot = _policy_snapshot(policy)
        with transaction.atomic():
            invoice.status = result
            invoice.save(update_fields=["status", "updated_at"])
            decision = PolicyDecision.objects.create(
                organization=organization,
                invoice=invoice,
                result=result,
                reason_code=reason_code,
                reason_detail=reason_detail,
                policy_id=policy.id if policy else None,
                policy_version=policy.version if policy else None,
                rules_snapshot=rules_snapshot,
                evaluated_by=request.user,
            )
            _audit(
                actor=request.user,
                organization=organization,
                action=AuditEvent.Action.INVOICE_EVALUATED,
                target_type="invoice",
                target_id=invoice.id,
                metadata={
                    "result": result,
                    "reason_code": reason_code,
                    "policy_version": policy.version if policy else None,
                    "decision_id": str(decision.id),
                },
            )
        return Response(
            {
                "invoice_id": str(invoice.id),
                "result": result,
                "reason_code": reason_code,
                "reason_detail": reason_detail,
                "policy_version": policy.version if policy else None,
            },
            status=status.HTTP_200_OK,
        )


class InvoiceDecisionView(generics.RetrieveAPIView):
    """Read the policy decision for one invoice (any active member)."""

    permission_classes = [IsAuthenticated, IsActiveOrganizationMemberInUrl]
    serializer_class = PolicyDecisionSerializer
    # The URL names the INVOICE (invoices/<uuid:pk>/decision/), so the
    # generic lookup must match PolicyDecision.invoice_id, not the decision's
    # own primary key: without this, every read answers empty (the invoice
    # UUID never equals the decision UUID).
    lookup_field = "invoice_id"
    lookup_url_kwarg = "pk"

    def get_queryset(self):
        return PolicyDecision.objects.filter(
            organization_id=self.kwargs["organization_pk"],
        )
