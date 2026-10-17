"""Organization API views.

Read-only tenant access (OrganizationViewSet) plus organization-scoped
administration of memberships and user accounts. Administration is gated by
IsActiveOrganizationFinanceAdmin in every management view: any organization
the actor does not administer resolves to 404 (no existence disclosure), and
rule violations inside the organization return 403. Every change and its audit
record commit in one transaction.
"""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404

from rest_framework import generics, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AuditEvent, Organization, OrganizationMembership
from .permissions import IsActiveOrganizationFinanceAdmin, IsActiveOrganizationMember
from .serializers import (
    MembershipCreateSerializer,
    MembershipSerializer,
    MembershipUpdateSerializer,
    OrganizationSerializer,
    UserActivationSerializer,
    UserCreateSerializer,
)

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
