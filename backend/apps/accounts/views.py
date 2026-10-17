"""Accounts app views."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import MeSerializer


class MeView(APIView):
    """GET /api/v1/auth/me/ — the authenticated user's safe profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)
