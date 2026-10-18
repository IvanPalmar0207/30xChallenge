#!/usr/bin/env python
"""Generate synthetic invoice PDF fixtures for PayBlood extraction tests.

Everything is fictitious. Each document gets a unique case id and a stable
filename. The PDFs are hand-built (no external PDF library needed) so the text
layer is perfectly selectable; pypdf reads them back for verification.

Usage:
    python generate.py            # writes *.pdf + *.jpg/*.png next to this file
    python generate.py --verify   # also re-opens every file and prints checks

Security notes:
    - No real vendor, tax id, address, or personal data.
    - Negative cases contain no executable content (plain bytes only).
    - No API keys or credentials anywhere.
"""

from __future__ import annotations

import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


# ── Tiny PDF builder ──────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def build_pdf(pages: list[list[tuple[str, int]]]) -> bytes:
    """Build a valid single/multi-page PDF with a selectable text layer.

    pages: list of pages; each page is a list of (line_text, font_size).
    Object layout: 1=catalog, 2=pages tree, then per page i (0-based):
    page obj=(3+2i), content obj=(4+2i); fonts after all pages:
    f1=(5+2(n-1)) -> (3+2n), f2=(4+2n).
    """
    n = len(pages)
    font1_no, font2_no = 3 + 2 * n, 4 + 2 * n
    out = bytearray()
    out += b"%PDF-1.4\n"
    objects: list[bytes] = []

    # Object 1: catalog
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    # Object 2: pages tree
    kids = " ".join(f"{3 + i * 2} 0 R" for i in range(n))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())

    for i, lines in enumerate(pages):
        page_no = 3 + i * 2
        content_no = 4 + i * 2
        res = f"<< /Font << /F1 {font1_no} 0 R /F2 {font2_no} 0 R >> >>".encode()
        page_obj = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources {res.decode()} /Contents {content_no} 0 R >>"
        ).encode()
        objects.append(page_obj)

        # Content stream
        stream_parts = ["BT"]
        y = 760
        for line_text, size in lines:
            font = "F2" if size >= 16 else "F1"
            stream_parts.append(f"/{font} {size} Tf")
            if y != 760:
                stream_parts.append(f"0 -{(760 - y + 18):d} Td")
            stream_parts.append(f"({_esc(line_text)}) Tj")
            y -= size + 10 if size < 16 else 26
        stream_parts.append("ET")
        stream_text = "\n".join(stream_parts).encode("latin-1")
        stream_obj = b"<< /Length " + str(len(stream_text)).encode() + b" >>\nstream\n" + stream_text + b"\nendstream"
        objects.append(stream_obj)

    # Fonts
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

    offsets: list[int] = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    return bytes(out)


def build_image_jpeg(rotate: int | None = None, quality: int = 85) -> bytes:
    """Small synthetic 'scanned' invoice image (fictitious, no text layer)."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (700, 900), "white")
    draw = ImageDraw.Draw(img)
    # Simulated scan: faint gray bands + a black box representing a photo.
    for y in range(0, 900, 60):
        draw.rectangle([0, y, 700, y + 28], fill=(232, 232, 232))
    draw.rectangle([200, 300, 500, 420], outline=(40, 40, 40), width=3)
    if rotate:
        img = img.rotate(rotate, expand=True)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def build_image_png(png_bytes: bytes) -> bytes:
    return png_bytes


# ── Fixture definitions ───────────────────────────────────────────────────────

# page helper: keeps "Total" amounts on the last line with a visible amount.
def _page(title: str, lines: list[str], amount_line: str | None = None) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = [(title, 16)]
    out.append(("This is a synthetic test document - not valid for payment.", 10))
    out.append(("", 10))
    for line in lines:
        out.append((line, 12))
    if amount_line:
        out.append(("", 12))
        out.append((amount_line, 13))
    return out


CASE_A_DIGITAL = {
    "filename": "C001-digital-full.pdf",
    "pages": [
        _page(
            "SYNTHETIC TEST INVOICE - C001",
            [
                "Vendor: Acme Logistics LLC",
                "Tax ID: US-88-1234567",
                "Invoice No: INV-2026-0001",
                "Issue Date: 2026-10-16",
                "Due Date: 2026-10-30",
                "Currency: USD",
                "Description                        Amount",
                "Freight services                     1180.00",
                "Handling                             120.00",
            ],
            "Total                               1300.00",
        )
    ],
}

CASE_B_MULTIPAGE = {
    "filename": "C002-multipage.pdf",
    "pages": [
        _page(
            "SYNTHETIC TEST INVOICE - C002 (page 1 of 2)",
            [
                "Vendor: Northwind Trading GmbH",
                "Tax ID: DE-123456789",
                "Invoice No: INV-EUR-2026-42",
                "Issue Date: 2026-09-01",
                "Due Date: 2026-09-30",
                "Currency: EUR",
                "Line item 1 - consulting                  400.00",
            ],
            None,
        ),
        _page(
            "SYNTHETIC TEST INVOICE - C002 (page 2 of 2)",
            [
                "Line item 2 - training                     200.00",
                "Line item 3 - support                      100.00",
            ],
            "Total EUR                                700.00",
        ),
    ],
}

CASE_C_TABLE = {
    "filename": "C003-table-and-totals.pdf",
    "pages": [
        _page(
            "SYNTHETIC TEST INVOICE - C003",
            [
                "Vendor: Soluciones Andinas S.A.",
                "Tax ID: 900.123.456-7",
                "Invoice No: FAC-2026-0173",
                "Issue Date: 2026-08-14",
                "Due Date: 2026-09-13",
                "Currency: COP",
                "Concepto                       Subtotal          IVA",
                "Servicios de hosting             800000.00       152000.00",
            ],
            "Total COP                       952000.00",
        )
    ],
}

CASE_D_FORMATS = {
    "filename": "C004-date-decimal-formats.pdf",
    "pages": [
        _page(
            "SYNTHETIC TEST INVOICE - C004",
            [
                "Vendor: Gimnasio Elan SRL",
                "Tax ID: 30-71234567-8",
                "Invoice No: 2026-00001452",
                "Issue Date: 14/08/2026",
                "Due Date: 12/09/2026",
                "Currency: ARS",
                "Membresia anual                         1.500,00",
            ],
            "Total ARS                             1.500,00",
        )
    ],
}

CASE_E_OPTIONAL = {
    "filename": "C005-optional-missing.pdf",
    "pages": [
        _page(
            "SYNTHETIC TEST INVOICE - C005",
            [
                "Vendor: Pacifico Express SA",
                "Tax ID: PE-20512345678",
                "Invoice No: FE-2026-0912",
                "Issue Date: 2026-07-20",
                "Currency: PEN",
                "Servicio de mensajeria                     320.50",
            ],
            "Total PEN                             320.50",
        )
    ],
}

CASE_F_REQUIRED_MISSING = {
    "filename": "C006-required-missing.pdf",
    "pages": [
        _page(
            "SYNTHETIC TEST INVOICE - C006",
            [
                "Vendor: Misterio & Co",
                "Tax ID: MX-ABC123XYZ",
                "Issue Date: 2026-07-01",
                "Currency: MXN",
                "This document deliberately lacks invoice number, amount and due date.",
                "Concepto: servicios generales",
            ],
            None,
        )
    ],
}

CASE_G_CONTRADICTORY = {
    "filename": "C007-contradictory-totals.pdf",
    "pages": [
        _page(
            "SYNTHETIC TEST INVOICE - C007",
            [
                "Vendor: Contradicciones Ltda",
                "Tax ID: BR-12.345.678/0001-90",
                "Invoice No: NF-2026-0842",
                "Issue Date: 2026-06-05",
                "Due Date: 2026-07-05",
                "Currency: BRL",
                "Subtotal                              1000.00",
                "IVA                                  190.00",
            ],
            "Total declared                       1200.00",
        )
    ],
}

CASE_H_TAXID = {
    "filename": "C008-taxid-number-formats.pdf",
    "pages": [
        _page(
            "SYNTHETIC TEST INVOICE - C008",
            [
                "Vendor: Swiss Precision AG",
                "Tax ID: che-123.456.789 MKW VAT",
                "Invoice No: 2026/INV/0048/CH",
                "Issue Date: 2026-05-10",
                "Due Date: 2026-06-09",
                "Currency: CHF",
                "Servicios de precision                     990.00",
            ],
            "Total CHF                              990.00",
        )
    ],
}

CASE_I_CURRENCIES = {
    "filename": "C009-currencies.pdf",
    "pages": [
        _page(
            "SYNTHETIC TEST INVOICE - C009A",
            [
                "Vendor: Maple Leaf Supplies",
                "Tax ID: CA-123456789",
                "Invoice No: INV-CAD-7788",
                "Issue Date: 2026-04-02",
                "Due Date: 2026-05-02",
                "Currency: CAD",
                "Suministros                               450.00",
            ],
            "Total CAD                              450.00",
        ),
        _page(
            "SYNTHETIC TEST INVOICE - C009B",
            [
                "Vendor: Rising Sun Trading",
                "Tax ID: JP-9012345678",
                "Invoice No: SI-2026-1122",
                "Issue Date: 2026-04-03",
                "Due Date: 2026-05-03",
                "Currency: JPY",
                "Componentes                               28750",
            ],
            "Total JPY                             28750.00",
        ),
        _page(
            "SYNTHETIC TEST INVOICE - C009C",
            [
                "Vendor: Britannia Logistics",
                "Tax ID: GB-987654321",
                "Invoice No: INV-GBP-0033",
                "Issue Date: 2026-04-04",
                "Due Date: 2026-05-04",
                "Currency: GBP",
                "Freight                                    215.75",
            ],
            "Total GBP                              215.75",
        ),
    ],
}

CASE_J_DIFFICULT = {
    "filename": "C010-scanned-rotated.jpg",
    "pages": [],
}

CASE_K_CORRUPT = {
    "filename": "C011-corrupt.pdf",
    "pages": [],
}

CASE_L_EMPTY = {
    "filename": "C012-empty.pdf",
    "pages": [],
}

CASE_M_LOWQUALITY = {
    "filename": "C013-lowquality.jpg",
    "pages": [],
}


def generate() -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    cases = [
        CASE_A_DIGITAL,
        CASE_B_MULTIPAGE,
        CASE_C_TABLE,
        CASE_D_FORMATS,
        CASE_E_OPTIONAL,
        CASE_F_REQUIRED_MISSING,
        CASE_G_CONTRADICTORY,
        CASE_H_TAXID,
        CASE_I_CURRENCIES,
    ]
    for case in cases:
        files[case["filename"]] = build_pdf(case["pages"])

    files[CASE_J_DIFFICULT["filename"]] = build_image_jpeg(rotate=90, quality=70)
    files[CASE_K_CORRUPT["filename"]] = b"%PDF-1.4\nthis is not a real object graph\n%%EOF\nbroken"
    files[CASE_L_EMPTY["filename"]] = b""
    files[CASE_M_LOWQUALITY["filename"]] = build_image_jpeg(quality=20)
    return files


def write_all(verify: bool = False) -> None:
    files = generate()
    os.makedirs(HERE, exist_ok=True)
    written: list[str] = []
    for name, data in files.items():
        path = os.path.join(HERE, name)
        with open(path, "wb") as fh:
            fh.write(data)
        written.append(path)
        print(f"wrote {name} ({len(data)} bytes)")

    if verify:
        try:
            from pypdf import PdfReader
        except ImportError:
            print("pypdf not available for verification; skipping.")
            return
        for name in sorted(files):
            path = os.path.join(HERE, name)
            with open(path, "rb") as fh:
                data = fh.read()
            if not data:
                print(f"check {name}: EMPTY (expected)")
                continue
            if data[:5] == b"%PDF-":
                try:
                    reader = PdfReader(io.BytesIO(data))
                    text = "".join((p.extract_text() or "") for p in reader.pages)
                    print(f"check {name}: pages={len(reader.pages)} text_len={len(text)}")
                except Exception as exc:  # corrupt case expected to fail parse
                    print(f"check {name}: UNPARSEABLE ({exc})")
            else:
                print(f"check {name}: image-like (magic {data[:4]!r})")
    print(f"done: {len(written)} fixtures")


if __name__ == "__main__":
    write_all(verify="--verify" in sys.argv)
