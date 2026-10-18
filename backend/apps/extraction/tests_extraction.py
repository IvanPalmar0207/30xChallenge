"""
Integration and unit tests for AI-assisted invoice extraction (Slice 7).

Test philosophy:
- AI calls use the mock extractor (AI_PROVIDER=mock) so no real API calls are made.
- File validation, field validation, and permissions use real code paths.
- No mocks bypass the permission stack, serializer validation, or the
  deterministic field validator.
"""
import io
import json
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.extraction.services.ai_extractor import (
    ExtractionConfigError,
    ExtractionError,
    OpenAIExtractor,
    OpenRouterExtractor,
    get_extractor,
)
from apps.extraction.services.file_processor import process_document
from apps.organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationRole,
)

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

def auth(client: APIClient, user) -> None:
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def url(org_pk) -> str:
    return f"/api/v1/organizations/{org_pk}/extraction/"


def minimal_pdf() -> bytes:
    """Minimal valid PDF with a text stream (digital, not scanned)."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n"
        b"2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n"
        b"3 0 obj\n<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>\nendobj\n"
        b"4 0 obj\n<</Length 44>>\nstream\n"
        b"BT /F1 12 Tf 72 720 Td (Invoice: INV-001) Tj ET\n"
        b"endstream\nendobj\n"
        b"xref\n0 5\n0000000000 65535 f \n"
        b"trailer\n<</Size 5/Root 1 0 R>>\nstartxref\n200\n%%EOF"
    )


def minimal_jpeg() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), color=(200, 200, 200)).save(buf, format="JPEG")
    return buf.getvalue()


def minimal_png() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), color=(200, 200, 200)).save(buf, format="PNG")
    return buf.getvalue()


def upload(content: bytes, filename: str,
           content_type: str = "application/octet-stream") -> SimpleUploadedFile:
    return SimpleUploadedFile(filename, content, content_type=content_type)


# ── API integration tests ─────────────────────────────────────────────────────

@override_settings(AI_PROVIDER="mock", AI_MOCK_SCENARIO="success")
class ExtractionApiTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org          = Organization.objects.create(name="Extraction Org A")
        cls.org_b        = Organization.objects.create(name="Extraction Org B")
        cls.org_inactive = Organization.objects.create(
            name="Extraction Org Inactive",
            status=Organization.Status.INACTIVE,
        )
        cls.admin    = User.objects.create_user(username="ext_admin",    password="x")
        cls.operator = User.objects.create_user(username="ext_operator", password="x")
        cls.approver = User.objects.create_user(username="ext_approver", password="x")
        cls.auditor  = User.objects.create_user(username="ext_auditor",  password="x")
        cls.member_b = User.objects.create_user(username="ext_member_b", password="x")
        cls.inactive_m = User.objects.create_user(username="ext_inactive_m", password="x")

        OrganizationMembership.objects.create(
            organization=cls.org, user=cls.admin, role=OrganizationRole.FINANCE_ADMIN)
        OrganizationMembership.objects.create(
            organization=cls.org, user=cls.operator, role=OrganizationRole.OPERATOR)
        OrganizationMembership.objects.create(
            organization=cls.org, user=cls.approver, role=OrganizationRole.APPROVER)
        OrganizationMembership.objects.create(
            organization=cls.org, user=cls.auditor, role=OrganizationRole.AUDITOR)
        OrganizationMembership.objects.create(
            organization=cls.org_b, user=cls.member_b, role=OrganizationRole.OPERATOR)
        OrganizationMembership.objects.create(
            organization=cls.org, user=cls.inactive_m,
            role=OrganizationRole.OPERATOR, is_active=False)

    def setUp(self):
        self.client = APIClient()

    # 1 ── Valid JPEG → 200 + fields
    def test_valid_jpeg_returns_extraction_result(self):
        auth(self.client, self.operator)
        res = self.client.post(
            url(self.org.id), {"file": upload(minimal_jpeg(), "inv.jpg")}, format="multipart")
        self.assertEqual(res.status_code, 200)
        self.assertIn("fields", res.data)
        self.assertEqual(res.data["provider_used"], "mock")
        self.assertIn("invoice_number", res.data["fields"])

    # 2 ── Valid PNG → 200 + fields
    def test_valid_png_returns_extraction_result(self):
        auth(self.client, self.admin)
        res = self.client.post(
            url(self.org.id), {"file": upload(minimal_png(), "scan.png")}, format="multipart")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["fields"]["currency"]["value"], "USD")

    # 3 ── Valid digital PDF → 200
    def test_valid_pdf_digital_returns_extraction_result(self):
        auth(self.client, self.operator)
        res = self.client.post(
            url(self.org.id), {"file": upload(minimal_pdf(), "inv.pdf")}, format="multipart")
        self.assertEqual(res.status_code, 200)
        self.assertIn("fields", res.data)

    # 4 ── File too large → 400
    @override_settings(EXTRACTION_MAX_FILE_SIZE_MB=1)
    def test_file_too_large_returns_400(self):
        auth(self.client, self.operator)
        big = minimal_jpeg() + b"\x00" * (1100 * 1024)  # ~1.1 MB
        f = SimpleUploadedFile("big.jpg", big, content_type="image/jpeg")
        res = self.client.post(url(self.org.id), {"file": f}, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["error"], "invalid_file")

    # 5 ── Empty file → 400
    def test_empty_file_returns_400(self):
        auth(self.client, self.operator)
        res = self.client.post(
            url(self.org.id), {"file": upload(b"", "empty.pdf")}, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["error"], "invalid_file")

    # 6 ── Corrupt (wrong magic bytes) → 400
    def test_corrupt_file_returns_400(self):
        auth(self.client, self.operator)
        res = self.client.post(
            url(self.org.id),
            {"file": upload(b"NOTPDF\xff\x00\x01", "inv.pdf")},
            format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["error"], "invalid_file")

    # 7 ── Unsupported extension → 400
    def test_unsupported_extension_returns_400(self):
        auth(self.client, self.operator)
        res = self.client.post(
            url(self.org.id), {"file": upload(minimal_pdf(), "report.docx")}, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["error"], "invalid_file")

    # 8 ── No file in request → 400
    def test_no_file_in_request_returns_400(self):
        auth(self.client, self.operator)
        res = self.client.post(url(self.org.id), {}, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["error"], "file_required")

    # 9 ── Anonymous → 401
    def test_anonymous_returns_401(self):
        res = self.client.post(
            url(self.org.id), {"file": upload(minimal_jpeg(), "inv.jpg")}, format="multipart")
        self.assertEqual(res.status_code, 401)

    # 10 ── AUDITOR → 404
    def test_auditor_cannot_extract_404(self):
        auth(self.client, self.auditor)
        res = self.client.post(
            url(self.org.id), {"file": upload(minimal_jpeg(), "inv.jpg")}, format="multipart")
        self.assertEqual(res.status_code, 404)

    # 11 ── APPROVER → 404
    def test_approver_cannot_extract_404(self):
        auth(self.client, self.approver)
        res = self.client.post(
            url(self.org.id), {"file": upload(minimal_jpeg(), "inv.jpg")}, format="multipart")
        self.assertEqual(res.status_code, 404)

    # 12 ── Cross-org → 404
    def test_cross_org_returns_404(self):
        auth(self.client, self.member_b)       # belongs to org_b only
        res = self.client.post(
            url(self.org.id), {"file": upload(minimal_jpeg(), "inv.jpg")}, format="multipart")
        self.assertEqual(res.status_code, 404)

    # 13 ── Inactive org → 404
    def test_inactive_org_returns_404(self):
        user = User.objects.create_user(username="ext_iorg_t13", password="x")
        OrganizationMembership.objects.create(
            organization=self.org_inactive, user=user, role=OrganizationRole.OPERATOR)
        auth(self.client, user)
        res = self.client.post(
            url(self.org_inactive.id),
            {"file": upload(minimal_jpeg(), "inv.jpg")},
            format="multipart")
        self.assertEqual(res.status_code, 404)

    # 14 ── Inactive membership → 404
    def test_inactive_membership_returns_404(self):
        auth(self.client, self.inactive_m)
        res = self.client.post(
            url(self.org.id), {"file": upload(minimal_jpeg(), "inv.jpg")}, format="multipart")
        self.assertEqual(res.status_code, 404)

    # 15 ── Provider not configured → 503
    @override_settings(AI_PROVIDER="")
    def test_provider_not_configured_returns_503(self):
        auth(self.client, self.operator)
        res = self.client.post(
            url(self.org.id), {"file": upload(minimal_jpeg(), "inv.jpg")}, format="multipart")
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.data["error"], "provider_not_configured")

    # 16 ── Provider error → 503
    @override_settings(AI_MOCK_SCENARIO="error")
    def test_provider_error_returns_503(self):
        auth(self.client, self.operator)
        res = self.client.post(
            url(self.org.id), {"file": upload(minimal_jpeg(), "inv.jpg")}, format="multipart")
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.data["error"], "extraction_failed")

    # 17 ── Simulated timeout → 503
    @override_settings(AI_MOCK_SCENARIO="timeout")
    def test_provider_timeout_returns_503(self):
        auth(self.client, self.operator)
        res = self.client.post(
            url(self.org.id), {"file": upload(minimal_jpeg(), "inv.jpg")}, format="multipart")
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.data["error"], "extraction_failed")

    # 18 ── Malformed AI response → 503
    @override_settings(AI_MOCK_SCENARIO="malformed")
    def test_malformed_ai_response_returns_503(self):
        auth(self.client, self.operator)
        res = self.client.post(
            url(self.org.id), {"file": upload(minimal_jpeg(), "inv.jpg")}, format="multipart")
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.data["error"], "extraction_failed")

    # 19 ── Absent fields (partial scenario) → null values, confidence='absent'
    @override_settings(AI_MOCK_SCENARIO="partial")
    def test_absent_fields_are_not_invented(self):
        auth(self.client, self.operator)
        res = self.client.post(
            url(self.org.id), {"file": upload(minimal_jpeg(), "inv.jpg")}, format="multipart")
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data["fields"]["vendor_tax_id"]["value"])
        self.assertIsNone(res.data["fields"]["due_date"]["value"])
        self.assertEqual(res.data["fields"]["vendor_tax_id"]["confidence"], "absent")

    # 20 ── Verification status is 'not_configured' (NullVerifier)
    def test_verification_status_is_not_configured(self):
        auth(self.client, self.operator)
        res = self.client.post(
            url(self.org.id), {"file": upload(minimal_jpeg(), "inv.jpg")}, format="multipart")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["verification_status"], "not_configured")

    # 21 ── JPEG magic bytes win over .pdf extension → 200 (detected as image)
    def test_jpeg_content_with_pdf_extension_returns_200(self):
        """Magic bytes take priority: JPEG content is accepted even with .pdf extension."""
        auth(self.client, self.operator)
        res = self.client.post(
            url(self.org.id),
            {"file": upload(minimal_jpeg(), "misnamed.pdf")},
            format="multipart")
        self.assertEqual(res.status_code, 200)   # JPEG magic → treated as image, OK


# ── OpenRouter adapter tests ──────────────────────────────────────────────────

class OpenRouterExtractorUnitTests(TestCase):
    """Unit tests for the OpenRouter adapter with HTTP transport simulated."""

    def _document(self):
        return process_document(upload(minimal_pdf(), "router-invoice.pdf", "application/pdf"))

    def _payload(self):
        return {
            "vendor_name": {"value": "Acme Corp", "evidence": "Acme Corp"},
            "vendor_tax_id": {"value": "ACME-1", "evidence": "Tax ID: ACME-1"},
            "invoice_number": {"value": "INV-ROUTER-001", "evidence": "Invoice: INV-ROUTER-001"},
            "issue_date": {"value": "2026-10-01", "evidence": "2026-10-01"},
            "due_date": {"value": "2026-11-01", "evidence": "2026-11-01"},
            "currency": {"value": "USD", "evidence": "USD"},
            "amount": {"value": "100.00", "evidence": "$100.00"},
            "description": {"value": "Consulting services", "evidence": "Consulting services"},
        }

    def _client(self, response=None, side_effect=None):
        create = Mock(side_effect=side_effect, return_value=response)
        completions = Mock(create=create)
        chat = Mock(completions=completions)
        return Mock(chat=chat)

    @override_settings(
        AI_PROVIDER="openrouter",
        AI_API_KEY="wrong-openai-key",
        AI_MODEL="wrong-openai-model",
        OPENROUTER_API_KEY="router-key",
        OPENROUTER_MODEL="openrouter/model",
    )
    def test_openrouter_success_uses_openrouter_env_and_endpoint(self):
        response = Mock(
            choices=[Mock(message=Mock(content=json.dumps(self._payload())))]
        )
        client = self._client(response=response)

        with patch("openai.OpenAI", return_value=client) as ctor:
            extractor = get_extractor()
            self.assertIsInstance(extractor, OpenRouterExtractor)
            result = extractor.extract(self._document())

        ctor.assert_called_once()
        kwargs = ctor.call_args.kwargs
        self.assertEqual(kwargs["api_key"], "router-key")
        self.assertEqual(kwargs["base_url"], "https://openrouter.ai/api/v1")
        self.assertEqual(kwargs["timeout"], 60)
        self.assertEqual(client.chat.completions.create.call_args.kwargs["model"], "openrouter/model")
        self.assertEqual(result.provider_used, "openrouter")
        self.assertEqual(result.model_used, "openrouter/model")
        self.assertEqual(result.fields["invoice_number"].value, "INV-ROUTER-001")

    @override_settings(
        AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY="router-key",
        OPENROUTER_MODEL="openrouter/model",
    )
    def test_openrouter_timeout_becomes_extraction_error(self):
        client = self._client(side_effect=TimeoutError("request timed out"))

        with patch("openai.OpenAI", return_value=client):
            extractor = get_extractor()
            with self.assertRaises(ExtractionError) as ctx:
                extractor.extract(self._document())

        self.assertIn("timed out", str(ctx.exception).lower())

    @override_settings(
        AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY="router-key",
        OPENROUTER_MODEL="openrouter/model",
    )
    def test_openrouter_auth_error_becomes_config_error(self):
        AuthenticationError = type("AuthenticationError", (Exception,), {})
        client = self._client(side_effect=AuthenticationError("bad key"))

        with patch("openai.OpenAI", return_value=client):
            extractor = get_extractor()
            with self.assertRaises(ExtractionConfigError) as ctx:
                extractor.extract(self._document())

        self.assertIn("OPENROUTER_API_KEY", str(ctx.exception))

    @override_settings(
        AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY="router-key",
        OPENROUTER_MODEL="openrouter/model",
    )
    def test_openrouter_rate_limit_becomes_extraction_error(self):
        RateLimitError = type("RateLimitError", (Exception,), {})
        client = self._client(side_effect=RateLimitError("too many requests"))

        with patch("openai.OpenAI", return_value=client):
            extractor = get_extractor()
            with self.assertRaises(ExtractionError) as ctx:
                extractor.extract(self._document())

        self.assertIn("rate limit", str(ctx.exception).lower())

    @override_settings(
        AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY="router-key",
        OPENROUTER_MODEL="openrouter/model",
    )
    def test_openrouter_invalid_json_becomes_extraction_error(self):
        response = Mock(choices=[Mock(message=Mock(content="not json"))])
        client = self._client(response=response)

        with patch("openai.OpenAI", return_value=client):
            extractor = get_extractor()
            with self.assertRaises(ExtractionError) as ctx:
                extractor.extract(self._document())

        self.assertIn("could not be parsed as json", str(ctx.exception).lower())

    @override_settings(
        AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY="router-key",
        OPENROUTER_MODEL="",
    )
    def test_openrouter_requires_explicit_model(self):
        with self.assertRaises(ExtractionConfigError):
            get_extractor()

    @override_settings(
        AI_PROVIDER="openai",
        AI_API_KEY="openai-key",
        AI_MODEL="gpt-4.1-mini",
        OPENROUTER_API_KEY="wrong-router-key",
        OPENROUTER_MODEL="wrong-router-model",
    )
    def test_openai_provider_still_uses_existing_settings(self):
        response = Mock(
            choices=[Mock(message=Mock(content=json.dumps(self._payload())))]
        )
        client = self._client(response=response)

        with patch("openai.OpenAI", return_value=client) as ctor:
            extractor = get_extractor()
            self.assertIsInstance(extractor, OpenAIExtractor)
            result = extractor.extract(self._document())

        kwargs = ctor.call_args.kwargs
        self.assertEqual(kwargs["api_key"], "openai-key")
        self.assertNotIn("base_url", kwargs)
        self.assertEqual(client.chat.completions.create.call_args.kwargs["model"], "gpt-4.1-mini")
        self.assertEqual(result.provider_used, "openai")


# ── Deterministic field validator unit tests ──────────────────────────────────

class FieldValidatorUnitTests(TestCase):
    """Unit tests for the deterministic field validator (no DB, no API calls)."""

    def _raw(self, **override):
        """Build a RawExtractionResult with null fields, applying overrides."""
        from apps.extraction.services.ai_extractor import (
            EXTRACTABLE_FIELDS, RawExtractionResult, RawFieldResult,
        )
        fields = {n: RawFieldResult(None, None) for n in EXTRACTABLE_FIELDS}
        fields.update(override)
        return RawExtractionResult(
            extraction_id="test",
            provider_used="mock",
            model_used="mock",
            fields=fields,
            raw_text_extracted=False,
        )

    # 22 ── Bad date format → validation_error on issue_date
    def test_bad_date_format_produces_validation_error(self):
        from apps.extraction.services.ai_extractor import RawFieldResult
        from apps.extraction.services.field_validator import validate_fields
        raw = self._raw(issue_date=RawFieldResult("not-a-date", "Date: not-a-date"))
        result = validate_fields(raw)
        self.assertGreater(len(result.fields["issue_date"].validation_errors), 0)
        self.assertIsNone(result.fields["issue_date"].value)

    # 23 ── Non-numeric amount → validation_error on amount
    def test_non_decimal_amount_produces_validation_error(self):
        from apps.extraction.services.ai_extractor import RawFieldResult
        from apps.extraction.services.field_validator import validate_fields
        raw = self._raw(amount=RawFieldResult("N/A", "Total: N/A"))
        result = validate_fields(raw)
        self.assertGreater(len(result.fields["amount"].validation_errors), 0)
        self.assertIsNone(result.fields["amount"].value)

    # 24 ── Zero amount → validation_error
    def test_zero_amount_produces_validation_error(self):
        from apps.extraction.services.ai_extractor import RawFieldResult
        from apps.extraction.services.field_validator import validate_fields
        raw = self._raw(amount=RawFieldResult("0.00", "$0"))
        result = validate_fields(raw)
        self.assertGreater(len(result.fields["amount"].validation_errors), 0)

    # 25 ── Invalid currency code → validation_error
    def test_invalid_currency_produces_validation_error(self):
        from apps.extraction.services.ai_extractor import RawFieldResult
        from apps.extraction.services.field_validator import validate_fields
        raw = self._raw(currency=RawFieldResult("US", "$"))
        result = validate_fields(raw)
        self.assertGreater(len(result.fields["currency"].validation_errors), 0)

    # 26 ── issue_date after due_date → cross_field_error
    def test_issue_date_after_due_date_produces_cross_field_error(self):
        from apps.extraction.services.ai_extractor import RawFieldResult
        from apps.extraction.services.field_validator import validate_fields
        raw = self._raw(
            issue_date=RawFieldResult("2024-03-01", "March 1"),
            due_date=RawFieldResult("2024-02-01", "February 1"),
        )
        result = validate_fields(raw)
        self.assertGreater(len(result.cross_field_errors), 0)
        self.assertIn("after due_date", result.cross_field_errors[0])

    # 27 ── Value + evidence → confidence='medium'
    def test_confidence_medium_when_value_and_evidence(self):
        from apps.extraction.services.ai_extractor import RawFieldResult
        from apps.extraction.services.field_validator import validate_fields
        raw = self._raw(
            invoice_number=RawFieldResult("INV-001", "Invoice No: INV-001"),
            currency=RawFieldResult("USD", "$"),
            amount=RawFieldResult("1000.00", "$1,000"),
        )
        result = validate_fields(raw)
        self.assertEqual(result.fields["invoice_number"].confidence, "medium")

    # 28 ── Value without evidence → confidence='low'
    def test_confidence_low_when_value_but_no_evidence(self):
        from apps.extraction.services.ai_extractor import RawFieldResult
        from apps.extraction.services.field_validator import validate_fields
        raw = self._raw(invoice_number=RawFieldResult("INV-001", None))
        result = validate_fields(raw)
        self.assertEqual(result.fields["invoice_number"].confidence, "low")
