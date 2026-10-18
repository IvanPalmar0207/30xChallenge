"""
Invoice extraction endpoint.

POST /api/v1/organizations/{organization_pk}/extraction/
Content-Type: multipart/form-data  •  Body: file=<PDF|JPEG|PNG, max 10 MB>

Returns structured invoice field candidates extracted by the configured AI
provider, verified by the configured verifier (currently NullVerifier — see
docs/jev-integration.md), and validated by deterministic rules.

This endpoint does NOT create an invoice.  The client reviews the result,
corrects fields as needed, and confirms through the existing
POST /organizations/{org}/invoices/ endpoint.

Permissions: IsActiveOrganizationInvoiceCreator (FINANCE_ADMIN + OPERATOR).
"""
from __future__ import annotations

from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.permissions import IsActiveOrganizationInvoiceCreator

from .serializers import ExtractionResultSerializer
from .services.ai_extractor import ExtractionConfigError, ExtractionError, get_extractor
from .services.field_validator import validate_fields
from .services.file_processor import FileValidationError, process_document
from .services.jev_verifier import get_verifier


class InvoiceExtractionView(APIView):
    """
    Extract structured invoice fields from an uploaded PDF or image.

    Responses:
      200  ExtractionResult JSON — candidate fields for human review
      400  file_required | invalid_file
      404  org not found / inactive / wrong role (uniform 404 via permission)
      503  provider_not_configured | extraction_failed
    """

    permission_classes = [IsActiveOrganizationInvoiceCreator]
    parser_classes     = [MultiPartParser]

    def post(self, request: Request, organization_pk: str) -> Response:
        # 1. File presence
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"error": "file_required", "message": "Attach a file as 'file'."},
                status=400,
            )

        # 2. File validation (magic bytes, size, extension, PDF text extraction)
        try:
            doc = process_document(file)
        except FileValidationError as exc:
            return Response(
                {"error": "invalid_file", "message": str(exc)},
                status=400,
            )

        # 3. Extractor factory (raises when provider is not configured)
        try:
            extractor = get_extractor()
        except ExtractionConfigError as exc:
            return Response(
                {"error": "provider_not_configured", "message": str(exc)},
                status=503,
            )

        # 4. AI extraction
        try:
            raw_result = extractor.extract(doc)
        except ExtractionConfigError as exc:
            return Response(
                {"error": "provider_not_configured", "message": str(exc)},
                status=503,
            )
        except ExtractionError as exc:
            return Response(
                {"error": "extraction_failed", "message": str(exc)},
                status=503,
            )

        # 5. Deterministic field validation
        validated = validate_fields(raw_result)

        # 6. Jev verification (NullVerifier until Jev identity confirmed)
        verification = get_verifier().verify(raw_result)

        payload = {
            "extraction_id":        raw_result.extraction_id,
            "provider_used":        raw_result.provider_used,
            "model_used":           raw_result.model_used,
            "verification_status":  verification.overall.value,
            "verification_message": verification.message,
            "raw_text_extracted":   raw_result.raw_text_extracted,
            "fields": {
                name: {
                    "value":            f.value,
                    "evidence":         f.evidence,
                    "confidence":       f.confidence,
                    "validation_errors": f.validation_errors,
                }
                for name, f in validated.fields.items()
            },
            "cross_field_errors": validated.cross_field_errors,
            "warnings":           raw_result.warnings,
        }

        serializer = ExtractionResultSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=200)
