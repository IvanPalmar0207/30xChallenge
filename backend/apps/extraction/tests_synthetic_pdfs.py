"""
Synthetic PDF fixture tests (Etapa 2).

Each fixture in test-artifacts/synthetic-invoices/ is exercised by a real test
that verifies the DOCUMENT pipeline (process_document: magic bytes, text
layer, warnings, controlled errors) and/or the DETERMINISTIC GATE
(validate_fields) and/or the API end-to-end with the mock provider (no real AI
calls, no invoice creation).

Extraction is tested SEPARATELY from the invoice lifecycle: nothing here
creates, approves or pays an invoice.
"""

import io
import os
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from django.contrib.auth import get_user_model

from .services.file_processor import FileValidationError, process_document
from .services.field_validator import validate_fields
from .services.ai_extractor import (
    MOCK_SCENARIO_SUCCESS,
    RawExtractionResult,
    RawFieldResult,
)

User = get_user_model()

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "test-artifacts" / "synthetic-invoices"


def fixture_bytes(filename: str) -> bytes:
    with open(FIXTURES_DIR / filename, "rb") as fh:
        return fh.read()


def upload(content: bytes, filename: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(filename, content, content_type="application/octet-stream")


DIGITAL_CASES = {
    # filename → markers that must appear in the extracted text layer
    "C001-digital-full.pdf": ["INV-2026-0001", "1300.00", "USD", "Acme Logistics"],
    "C002-multipage.pdf":    ["INV-EUR-2026-42", "700.00", "EUR", "page 2 of 2"],
    "C003-table-and-totals.pdf": ["FAC-2026-0173", "952000.00", "COP"],
    "C004-date-decimal-formats.pdf": ["1.500,00", "ARS"],
    "C005-optional-missing.pdf": ["FE-2026-0912", "PEN"],
    "C006-required-missing.pdf": ["MXN", "Misterio"],
    "C007-contradictory-totals.pdf": ["1200.00", "BRL"],
    "C008-taxid-number-formats.pdf": ["2026/INV/0048/CH", "990.00", "CHF"],
    "C009-currencies.pdf":   ["CAD", "JPY", "GBP", "28750.00"],
}


class DocumentPipelineTests(TestCase):
    """Verify every fixture against the real document processor."""

    def test_digital_pdfs_have_selectable_text_layer(self):
        for filename, markers in DIGITAL_CASES.items():
            with self.subTest(filename=filename):
                doc = process_document(upload(fixture_bytes(filename), filename))
                self.assertFalse(doc.is_image, filename)
                self.assertTrue(doc.raw_text_extracted, f"{filename}: no text layer")
                self.assertIsNotNone(doc.text_content, filename)
                for marker in markers:
                    self.assertIn(
                        marker, doc.text_content,
                        f"{filename}: missing marker {marker!r}",
                    )

    def test_multipage_pdf_combined_text(self):
        doc = process_document(upload(fixture_bytes("C002-multipage.pdf"), "C002-multipage.pdf"))
        self.assertIn("page 2 of 2", doc.text_content or "")

    def test_images_are_detected_as_images_without_text_layer(self):
        for filename in ("C010-scanned-rotated.jpg", "C013-lowquality.jpg"):
            with self.subTest(filename=filename):
                doc = process_document(upload(fixture_bytes(filename), filename))
                self.assertTrue(doc.is_image, filename)
                self.assertFalse(doc.raw_text_extracted, filename)

    def test_empty_pdf_rejected_controlled(self):
        with self.assertRaises(FileValidationError) as ctx:
            process_document(upload(b"", "C012-empty.pdf"))
        self.assertIn("File is empty", str(ctx.exception))

    def test_corrupt_pdf_warns_never_crashes(self):
        doc = process_document(upload(fixture_bytes("C011-corrupt.pdf"), "C011-corrupt.pdf"))
        # Magic bytes match, so the file is accepted; the parse failure becomes
        # a warning and the text layer is absent (fail-open for warning).
        self.assertFalse(doc.raw_text_extracted)
        self.assertTrue(
            any("could not be parsed" in w.lower() for w in doc.warnings),
            doc.warnings,
        )

    def test_wrong_extension_rejected(self):
        with self.assertRaises(FileValidationError):
            process_document(upload(fixture_bytes("C001-digital-full.pdf"), "C001.docx"))


class DeterministicGateTests(TestCase):
    """Verify field validation rules with raw extraction values (no AI)."""

    def _result(self, fields: dict[str, tuple[str | None, str | None]]) -> RawExtractionResult:
        return RawExtractionResult(
            extraction_id="00000000-0000-0000-0000-000000000001",
            provider_used="test",
            model_used="test",
            fields={k: RawFieldResult(v, e) for k, (v, e) in fields.items()},
            raw_text_extracted=True,
        )

    def test_european_decimal_comma_is_known_limitation(self):
        """C004: '1.500,00' is NOT normalized to 1500.00.

        Documented limitation: field_validator._validate_amount strips commas
        before its European-decimal branch runs, so the branch is unreachable
        and '1.500,00' validates as '1.50' (and '1500,00' would become
        '150000.00'). The gate does not support European decimal commas; this
        test pins the CURRENT real behaviour so the limitation is visible.
        """
        result = self._result({
            "amount": ("1.500,00", "Total ARS 1.500,00"),
            "currency": ("ARS", "ARS"),
            "issue_date": ("2026-08-14", "14/08/2026"),
            "due_date": ("2026-09-12", ""),
            "invoice_number": ("2026-00001452", "2026-00001452"),
            "vendor_name": ("Gimnasio Elan SRL", "Gimnasio Elan SRL"),
            "vendor_tax_id": ("30-71234567-8", "30-71234567-8"),
            "description": (None, None),
        })
        valid = validate_fields(result)
        # Current (limitation) behaviour — see docstring.
        self.assertEqual(valid.fields["amount"].value, "1.50")
        self.assertEqual(valid.fields["currency"].value, "ARS")
        self.assertFalse(valid.fields["amount"].validation_errors)

    def test_dot_decimal_normalized(self):
        result = self._result({
            "amount": ("1,500.00", "Total 1,500.00"),  # US thousands separator
            "currency": ("USD", "USD"),
        })
        valid = validate_fields(result)
        self.assertEqual(valid.fields["amount"].value, "1500.00")
        self.assertFalse(valid.fields["amount"].validation_errors)

    def test_plain_decimal_normalized(self):
        result = self._result({"amount": ("320.5", "320.5")})
        valid = validate_fields(result)
        self.assertEqual(valid.fields["amount"].value, "320.50")
        self.assertFalse(valid.fields["amount"].validation_errors)

    def test_non_iso_date_rejected_deterministically(self):
        """C004 raw date in dd/mm/yyyy fails the ISO gate with a clear error."""
        result = self._result({
            "issue_date": ("14/08/2026", "14/08/2026"),
        })
        valid = validate_fields(result)
        self.assertIsNone(valid.fields["issue_date"].value)
        self.assertTrue(
            any("not a valid date" in e for e in valid.fields["issue_date"].validation_errors)
        )

    def test_contradictory_totals_keep_declared_amount(self):
        """C007: subtotal+IVA = 1190 but the declared total is 1200.00.

        The extractor never derives totals; the declared amount is kept and no
        invented cross-field total reconciliation is applied (documented
        limitation of the deterministic gate).
        """
        result = self._result({
            "amount": ("1200.00", "Total declared 1200.00"),
            "currency": ("BRL", "BRL"),
            "invoice_number": ("NF-2026-0842", "NF-2026-0842"),
            "issue_date": ("2026-06-05", "2026-06-05"),
            "due_date": ("2026-07-05", "2026-07-05"),
            "vendor_name": ("Contradicciones Ltda", "Contradicciones Ltda"),
            "vendor_tax_id": ("BR-12.345.678/0001-90", "BR-12.345.678/0001-90"),
            "description": (None, None),
        })
        valid = validate_fields(result)
        self.assertEqual(valid.fields["amount"].value, "1200.00")
        self.assertFalse(valid.fields["amount"].validation_errors)

    def test_missing_required_fields_are_absent_not_invented(self):
        """C006: document lacks invoice number and amount → absent fields."""
        result = self._result({
            "vendor_name": ("Misterio & Co", "Misterio & Co"),
            "vendor_tax_id": ("MX-ABC123XYZ", "MX-ABC123XYZ"),
            "currency": ("MXN", "MXN"),
            "issue_date": ("2026-07-01", "2026-07-01"),
        })
        valid = validate_fields(result)
        self.assertEqual(valid.fields["invoice_number"].confidence, "absent")
        self.assertEqual(valid.fields["amount"].confidence, "absent")
        self.assertEqual(valid.fields["due_date"].confidence, "absent")

    def test_tax_id_and_invoice_number_normalized(self):
        """C008: uppercase normalization on varied tax id / number formats."""
        result = self._result({
            "vendor_tax_id": ("che-123.456.789 MKW VAT", "che-123.456.789 MKW VAT"),
            "invoice_number": ("2026/INV/0048/CH", "2026/INV/0048/CH"),
        })
        valid = validate_fields(result)
        self.assertEqual(valid.fields["vendor_tax_id"].value, "CHE-123.456.789 MKW VAT")
        self.assertEqual(valid.fields["invoice_number"].value, "2026/INV/0048/CH")
        self.assertFalse(valid.fields["vendor_tax_id"].validation_errors)

    def test_lowercase_currency_normalized_not_rejected(self):
        result = self._result({"currency": ("usd", "Total usd")})
        valid = validate_fields(result)
        self.assertEqual(valid.fields["currency"].value, "USD")
        self.assertFalse(valid.fields["currency"].validation_errors)

    def test_non_alpha_currency_rejected(self):
        result = self._result({"currency": ("USD1", "USD1")})
        valid = validate_fields(result)
        self.assertIsNone(valid.fields["currency"].value)
        self.assertTrue(valid.fields["currency"].validation_errors)

    def test_zero_and_negative_amounts_rejected(self):
        for bad in ("0.00", "-5.00"):
            valid = validate_fields(self._result({"amount": (bad, bad)}))
            self.assertTrue(
                valid.fields["amount"].validation_errors,
                f"{bad} should be rejected",
            )

    def test_issue_after_due_cross_field_error(self):
        result = self._result({
            "issue_date": ("2026-12-01", "2026-12-01"),
            "due_date": ("2026-01-01", "2026-01-01"),
        })
        valid = validate_fields(result)
        self.assertTrue(
            any("after due_date" in e for e in valid.cross_field_errors)
        )

    def test_blank_invoice_number_rejected(self):
        valid = validate_fields(self._result({"invoice_number": ("   ", "   ")}))
        self.assertTrue(valid.fields["invoice_number"].validation_errors)


@override_settings(AI_PROVIDER="mock", AI_MOCK_SCENARIO=MOCK_SCENARIO_SUCCESS)
class ApiWithFixtureTests(TestCase):
    """End-to-end extraction API using a real synthetic fixture and the mock
    provider. No real AI call, no invoice created."""

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Synthetic Fixture Org")
        cls.operator = User.objects.create_user(username="synth_op", password="x")
        OrganizationMembership.objects.create(
            organization=cls.org, user=cls.operator, role=OrganizationRole.OPERATOR)

    def setUp(self):
        self.client = APIClient()

    def test_extraction_endpoint_processes_digital_fixture(self):
        self.client.force_authenticate(self.operator)
        with open(FIXTURES_DIR / "C001-digital-full.pdf", "rb") as fh:
            blob = fh.read()
        response = self.client.post(
            f"/api/v1/organizations/{self.org.id}/extraction/",
            {"file": SimpleUploadedFile("C001-digital-full.pdf", blob, "application/pdf")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["provider_used"], "mock")
        self.assertTrue(data["raw_text_extracted"])
        self.assertEqual(data["verification_status"], "not_configured")
        self.assertIn("invoice_number", data["fields"])
        # The extraction result never creates an invoice.
        self.client.force_authenticate(self.operator)
        invoices = self.client.get(f"/api/v1/organizations/{self.org.id}/invoices/")
        self.assertEqual(invoices.status_code, 200)
        self.assertEqual(invoices.json(), [])

    def test_empty_fixture_rejected_by_api(self):
        self.client.force_authenticate(self.operator)
        response = self.client.post(
            f"/api/v1/organizations/{self.org.id}/extraction/",
            {"file": SimpleUploadedFile("C012-empty.pdf", b"", "application/pdf")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_file")
