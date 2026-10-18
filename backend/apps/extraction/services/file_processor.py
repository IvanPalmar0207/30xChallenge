"""
Document intake and validation for AI-assisted invoice extraction.
Fail-closed: rejects files that cannot be positively identified by magic bytes.
Never stores files to disk permanently.
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass, field as dc_field

from django.conf import settings

ALLOWED_EXTENSIONS = frozenset({".pdf", ".jpg", ".jpeg", ".png"})

_PDF_MAGIC  = b"%PDF-"
_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC  = b"\x89PNG\r\n\x1a\n"


class FileValidationError(ValueError):
    """Uploaded file failed format, size, or content validation."""


@dataclass
class ProcessedDocument:
    content_bytes:      bytes
    mime_type:          str       # application/pdf | image/jpeg | image/png
    safe_filename:      str
    file_size_bytes:    int
    is_image:           bool
    text_content:       str | None = None   # populated for digital PDFs only
    raw_text_extracted: bool       = False  # True when text_content has usable data
    warnings:           list[str]  = dc_field(default_factory=list)


def process_document(uploaded_file) -> ProcessedDocument:
    """Validate and minimally process an uploaded document.

    Raises FileValidationError on any security or format check failure.
    Never stores file content to disk.
    """
    filename = _sanitize_filename(getattr(uploaded_file, "name", "") or "")
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Unsupported file type '{ext}'. "
            f"Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )

    data = uploaded_file.read()
    size = len(data)

    if size == 0:
        raise FileValidationError("File is empty.")

    # Max size is read lazily so @override_settings works in tests.
    max_mb    = getattr(settings, "EXTRACTION_MAX_FILE_SIZE_MB", 10)
    max_bytes = max_mb * 1024 * 1024
    if size > max_bytes:
        raise FileValidationError(
            f"File exceeds the {max_mb} MB limit "
            f"({size / (1024 * 1024):.1f} MB uploaded)."
        )

    mime_type, is_image = _detect_format(data, filename)

    text_content       = None
    raw_text_extracted = False
    warnings: list[str] = []

    if mime_type == "application/pdf":
        text_content, raw_text_extracted, warnings = _extract_pdf_text(data)

    return ProcessedDocument(
        content_bytes=data,
        mime_type=mime_type,
        safe_filename=filename,
        file_size_bytes=size,
        is_image=is_image,
        text_content=text_content,
        raw_text_extracted=raw_text_extracted,
        warnings=warnings,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _sanitize_filename(name: str) -> str:
    """Strip directory components and dangerous characters from a filename."""
    safe = os.path.basename(name.replace("\\", "/"))
    safe = safe.replace("\x00", "").strip()
    safe = "".join(c for c in safe if c.isprintable() and c not in '<>:"/|?*')
    return safe or "document"


def _detect_format(data: bytes, filename: str) -> tuple[str, bool]:
    """Identify file format from magic bytes.  Never trusts extension alone.

    Returns (mime_type, is_image).
    Raises FileValidationError for unrecognised or mismatched content.
    """
    if data[:5] == _PDF_MAGIC:
        return "application/pdf", False
    if data[:3] == _JPEG_MAGIC:
        return "image/jpeg", True
    if data[:8] == _PNG_MAGIC:
        return "image/png", True
    ext = os.path.splitext(filename)[1].lower()
    raise FileValidationError(
        f"File content does not match the expected format for '{ext}'. "
        "The file may be corrupt or its extension may be misleading."
    )


def _extract_pdf_text(data: bytes) -> tuple[str | None, bool, list[str]]:
    """Extract text from a digital PDF using pypdf.

    Returns (text_content, raw_text_extracted, warnings).
    Degrades gracefully if pypdf is unavailable or the PDF has no text layer.
    """
    warnings: list[str] = []
    try:
        import pypdf
    except ImportError:
        warnings.append(
            "pypdf is not installed; PDF text extraction unavailable. "
            "Run: pip install 'pypdf>=4.3.0'"
        )
        return None, False, warnings

    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
    except Exception as exc:
        warnings.append(f"PDF could not be parsed: {exc}.")
        return None, False, warnings

    max_pages = getattr(settings, "EXTRACTION_MAX_PDF_PAGES", 10)
    pages     = reader.pages[:max_pages]
    if len(reader.pages) > max_pages:
        warnings.append(
            f"PDF has {len(reader.pages)} pages; "
            f"only the first {max_pages} will be processed."
        )

    parts: list[str] = []
    for page in pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")

    text = "\n".join(parts).strip()
    if not text:
        warnings.append(
            "No text layer found in PDF. "
            "The file may be a scanned image; manual field entry may be required."
        )
        return None, False, warnings

    return text, True, warnings
