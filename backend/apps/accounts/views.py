"""Accounts app views: safe profile, login, logout, and initial password
setup via one-time invitation tokens."""

import hashlib

from django.contrib.auth import authenticate, logout
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.organizations.models import AuditEvent, PasswordSetupToken
from apps.organizations.views import _audit

from .serializers import (
    LoginSerializer,
    MeSerializer,
    SetPasswordSerializer,
    UserPublicSerializer,
)


class LoginRateThrottle(AnonRateThrottle):
    """Anonymous throttle for the login and set-password endpoints.

    Rate is documented and deliberate: 30 attempts per minute per IP slows
    brute force without a new dependency. DRF throttling is built in.
    """

    scope = "login"
    rate = "30/min"


class MeView(APIView):
    """GET /api/v1/auth/me/ — the authenticated user's safe profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)


class LoginView(APIView):
    """POST /api/v1/auth/login/ — exchange credentials for a DRF token.

    Wrong credentials and inactive accounts answer the same uniform 401, so
    the endpoint never discloses whether an email exists (no user
    enumeration). The response contains only the token and a safe identity
    payload; passwords and staff flags are never returned.
    """

    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        # ModelBackend rejects inactive users (user_can_authenticate), so an
        # inactive account is indistinguishable from wrong credentials.
        user = authenticate(request, username=email, password=password)
        if user is None:
            raise AuthenticationFailed("Invalid email or password.")
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "user": UserPublicSerializer(user).data}
        )


class LogoutView(APIView):
    """POST /api/v1/auth/logout/ — revoke the current token.

    DRF tokens do not expire automatically (documented limitation); logout is
    the explicit revocation path. For session-authenticated requests the
    session is flushed instead. A revoked token answers 401 on its next use.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        auth = request.auth
        if auth is not None and hasattr(auth, "key"):
            Token.objects.filter(key=auth.key).delete()
        else:
            logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SetPasswordView(APIView):
    """POST /api/v1/auth/set-password/ — set an account's initial password.

    Authorized exclusively by a one-time invitation token (SHA-256 hashed in
    the database, 72h TTL, single use). An ordinary or filtered DRF access
    token is never accepted here, so a leaked access token cannot take over
    an account that has no password yet. The raw token and the password are
    never stored or logged.
    """

    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    serializer_class = SetPasswordSerializer

    def post(self, request):
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_token = serializer.validated_data["setup_token"]
        password = serializer.validated_data["password"]
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        record = (
            PasswordSetupToken.objects.filter(
                token_hash=token_hash,
                used_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .select_related("user")
            .first()
        )
        if record is None:
            raise ValidationError("Invalid or expired setup token.")
        with transaction.atomic():
            record.user.set_password(password)
            record.user.save(update_fields=["password"])
            record.used_at = timezone.now()
            record.save(update_fields=["used_at"])
            _audit(
                actor=record.user,
                organization=None,
                action=AuditEvent.Action.PASSWORD_SET,
                target_type="user",
                target_id=record.user.id,
                metadata={"method": "setup_token"},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
