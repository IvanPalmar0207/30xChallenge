"""Accounts app views: safe profile, login, logout, and initial password
setup via one-time invitation tokens."""

import hashlib
from datetime import UTC, datetime as dtlib

from django.conf import settings as dj_settings
from django.contrib.auth import authenticate, get_user_model, logout
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

from apps.organizations.models import AuditEvent, PasswordSetupToken
from apps.organizations.audit import _audit

from .serializers import (
    LoginSerializer,
    MeSerializer,
    SetPasswordSerializer,
    UserPublicSerializer,
)




def _set_refresh_cookie(response, raw_refresh: str) -> None:
    """Store the refresh token in an HttpOnly cookie (JS never reads it)."""
    response.set_cookie(
        dj_settings.REFRESH_COOKIE_NAME,
        raw_refresh,
        max_age=7 * 24 * 60 * 60,  # matches REFRESH_TOKEN_LIFETIME (7 days)
        httponly=True,
        secure=dj_settings.REFRESH_COOKIE_SECURE,
        samesite=dj_settings.REFRESH_COOKIE_SAMESITE,
        path="/api/v1/auth/",
    )


def _read_refresh(request) -> str | None:
    """Prefer the JSON body (legacy) and fall back to the HttpOnly cookie."""
    body = request.data.get("refresh")
    if isinstance(body, str) and body:
        return body
    return request.COOKIES.get(dj_settings.REFRESH_COOKIE_NAME)


class HashedRefreshToken(RefreshToken):
    """RefreshToken whose emission does NOT auto-store the raw token in the
    blacklist table (SimpleJWT's RefreshToken.for_user writes the plaintext
    JWT to OutstandingToken — see its classmethod). We register hashes
    explicitly in _record_outstanding."""

    @classmethod
    def for_user(cls, user):
        # Deliberately call the BASE Token.for_user (no outstanding write).
        # pylint: disable=no-member
        return super(RefreshToken, cls).for_user(user)


def _hash_token(raw: str) -> str:
    """Never store refresh tokens in clear text: only a SHA-256 hash is kept."""
    return hashlib.sha256(raw.encode()).hexdigest()


def _record_outstanding(refresh: RefreshToken) -> None:
    """Register a JWT refresh so it can be blacklisted later (hashed token)."""
    user_id = refresh.payload.get("user_id")
    user = None
    if user_id is not None:
        try:
            user = get_user_model().objects.get(pk=user_id)
        except get_user_model().DoesNotExist:
            user = None
    exp = refresh.payload.get("exp")
    # update_or_create: if the library ever stored the raw JWT for this jti
    # (SimpleJWT's RefreshToken.for_user does), converge it to the hash.
    OutstandingToken.objects.update_or_create(
        jti=refresh.payload["jti"],
        defaults={
            "user": user,
            "created_at": timezone.now(),
            "expires_at": dtlib.fromtimestamp(exp, tz=UTC)
            if exp
            else timezone.now(),
            "token": _hash_token(str(refresh)),
        },
    )


def _blacklist_refresh(raw: str) -> None:
    """Validate the presented refresh and revoke it (by jti, hashed record).

    Raises TokenError for invalid, expired, or already-blacklisted tokens.
    """
    refresh = RefreshToken(raw)  # verify() checks signature, expiry and blacklist
    outstanding, _ = OutstandingToken.objects.update_or_create(
        jti=refresh.payload["jti"],
        defaults={
            "user": None,
            "created_at": timezone.now(),
            "expires_at": dtlib.fromtimestamp(
                refresh.payload["exp"], tz=UTC
            ),
            "token": _hash_token(raw),
        },
    )
    BlacklistedToken.objects.get_or_create(token=outstanding)

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
        refresh = HashedRefreshToken.for_user(user)
        _record_outstanding(refresh)
        response = Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserPublicSerializer(user).data,
            }
        )
        _set_refresh_cookie(response, str(refresh))
        return response


class RefreshView(APIView):
    """POST /api/v1/auth/refresh/ — mint a new access token (and, under
    rotation, a new refresh) from a valid refresh token.

    The presented refresh is blacklisted after rotation; reuse answers 401.
    Expired, invalid, or blacklisted refresh tokens answer the same 401 with
    no internal detail. Refresh tokens are never stored in clear text.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        raw = _read_refresh(request)
        if not raw:
            return Response(
                {"detail": "A refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(raw)
        except (TokenError, KeyError):
            return Response(
                {"detail": "Token is invalid or expired."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        user_id = token.payload.get("user_id")
        user = None
        if user_id is not None:
            try:
                user = get_user_model().objects.get(pk=user_id)
            except get_user_model().DoesNotExist:
                user = None
        if user is None or not user.is_active:
            return Response(
                {"detail": "Token is invalid or expired."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        data = {"access": str(token.access_token)}

        if getattr(dj_settings, "SIMPLE_JWT", {}).get("ROTATE_REFRESH_TOKENS", True):
            _blacklist_refresh(raw)  # revoke the presented refresh (hashed)
            new_refresh = HashedRefreshToken.for_user(user)
            _record_outstanding(new_refresh)
            data["refresh"] = str(new_refresh)

        response = Response(data, status=status.HTTP_200_OK)
        _set_refresh_cookie(response, str(new_refresh))
        return response


class LogoutView(APIView):
    """POST /api/v1/auth/logout/ — revoke the presented refresh token.

    With JWT the access token is short-lived (10 minutes); revocation is
    enforced on the refresh token, which is what can mint new access tokens.
    A revoked refresh answers 401 on its next use. Session-authenticated
    requests flush the session instead.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        raw = _read_refresh(request)
        if raw:
            try:
                _blacklist_refresh(raw)
            except (TokenError, KeyError, ValueError):
                raise ValidationError("Invalid or expired refresh token.")
            response = Response(status=status.HTTP_204_NO_CONTENT)
            response.delete_cookie(
                dj_settings.REFRESH_COOKIE_NAME, path="/api/v1/auth/"
            )
            return response
        # Backward-compatible session flush for non-JWT callers.
        if request.user.is_authenticated:
            logout(request)
            return Response(status=status.HTTP_204_NO_CONTENT)
        raise ValidationError("A refresh token is required.")


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
                user__is_active=True,
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
