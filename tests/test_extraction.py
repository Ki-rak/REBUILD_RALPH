from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import pytest
from openpyxl import Workbook
from pypdf import PdfWriter

import backend.extraction as extraction_module
from backend.extraction import extract_document

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "REBUILD_INPUT_v1" / "REBUILD_INPUT_v1"


def _extract(path: Path) -> dict:
    data = path.read_bytes()
    return extract_document(data, path.name, "doc-1", "project-1")


def _xlsx_with_cached_formula() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Calculation"
    sheet["A1"], sheet["A2"], sheet["A3"] = 2, 3, "=SUM(A1:A2)"
    raw = io.BytesIO()
    workbook.save(raw)
    source = zipfile.ZipFile(io.BytesIO(raw.getvalue()))
    target = io.BytesIO()
    with source, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as output:
        for item in source.infolist():
            payload = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                payload = payload.replace(b"<f>SUM(A1:A2)</f><v></v>", b"<f>SUM(A1:A2)</f><v>5</v>")
            output.writestr(item, payload)
    return target.getvalue()


def test_real_docx_extracts_content_tables_and_human_locators() -> None:
    path = INPUT / "01_PAST_PROJECTS" / "P01_Haeon_Metro_Package_2" / "01_Project_Brief_and_Lessons.docx"
    result = _extract(path)
    assert result["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["extraction_status"] == "EXTRACTED"
    assert (result["id"], result["project_id"], result["filename"]) == ("doc-1", "project-1", path.name)
    assert result["markdown"].strip()
    assert any(b["locator_type"] == "docx_paragraph" for b in result["blocks"])
    assert any(b["locator_type"] == "docx_table_cell" for b in result["blocks"])
    assert any(b.get("table") for b in result["blocks"])


def test_text_parser_uses_uploaded_bytes_and_detects_content_metadata() -> None:
    first = extract_document(b"Revision: Rev07\nStatus: FOR REVIEW\nDischarge limit 125 m3/day\n", "neutral.txt", "doc-a", "project-a")
    second = extract_document(b"Revision: Rev08\nStatus: APPROVED\nDischarge limit 450 m3/day\n", "neutral.txt", "doc-b", "project-a")
    assert first["sha256"] != second["sha256"]
    assert (first["revision"], first["approval_status"]) == ("Rev07", "FOR REVIEW")
    assert (second["revision"], second["approval_status"]) == ("Rev08", "APPROVED")
    assert "125 m3/day" in first["markdown"] and "450 m3/day" in second["markdown"]
    assert any(b.get("unit") == "m3/day" for b in first["blocks"])


@pytest.mark.parametrize(("filename", "payload", "locator_type"), [
    ("note.md", b"# Heading\nEvidence line\n", "text_line"),
    ("note.txt", "한글 근거 14 days\n".encode(), "text_line"),
    ("table.csv", b"item,value,unit\nflow,450,m3/day\n", "csv_cell"),
    ("message.eml", b"From: owner@example.com\r\nSubject: Review\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nReview body", "eml_body_line"),
])
def test_plain_formats_preserve_locators(filename: str, payload: bytes, locator_type: str) -> None:
    result = extract_document(payload, filename, "doc", "project")
    assert result["extraction_status"] == "EXTRACTED"
    assert any(b["locator_type"] == locator_type for b in result["blocks"])


def test_xlsx_preserves_formula_cached_value_and_cell_locator() -> None:
    result = extract_document(_xlsx_with_cached_formula(), "calculation.xlsx", "doc", "project")
    formula = next(b for b in result["blocks"] if b.get("formula"))
    assert formula["locator_type"] == "xlsx_cell"
    assert formula["locator"] == "Calculation!A3"
    assert formula["formula"] == "=SUM(A1:A2)"
    assert formula["cached_value"] == 5
    assert formula["original_value"] == "=SUM(A1:A2)"


def test_real_pptx_and_pdf_keep_slide_shape_and_page_locators() -> None:
    pptx = _extract(INPUT / "01_PAST_PROJECTS" / "P01_Haeon_Metro_Package_2" / "04_Closeout_Review.pptx")
    pdf = _extract(INPUT / "02_NEW_PROJECTS" / "N01_Haeon_Blue_Line_Package_4" / "02_ITB_and_Contract_Rev00.pdf")
    assert any(b["locator_type"] == "pptx_shape" for b in pptx["blocks"])
    assert any(b["locator_type"] == "pdf_page" for b in pdf["blocks"])
    assert pdf["extraction_status"] == "EXTRACTED"


def test_scanned_and_corrupt_pdf_are_isolated_with_explicit_status() -> None:
    blank = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(blank)
    scanned = extract_document(blank.getvalue(), "scan.pdf", "scan", "project")
    corrupt = extract_document(b"not a pdf", "broken.pdf", "bad", "project")
    assert scanned["extraction_status"] == "OCR_REQUIRED"
    assert scanned["metadata"]["ocr_required"] is True
    assert corrupt["extraction_status"] == "ERROR"
    assert corrupt["metadata"]["error_type"]


def test_unsupported_format_isolated_without_guessing_metadata() -> None:
    result = extract_document(b"opaque", "archive.bin", "doc", "project")
    assert result["extraction_status"] == "UNSUPPORTED"
    assert result["revision"] is None and result["approval_status"] is None
    assert result["blocks"] == []


def _zip_payload(entries: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries:
            archive.writestr(name, payload)
    return output.getvalue()


def test_office_archive_entry_limit_is_checked_before_parser(monkeypatch) -> None:
    monkeypatch.setattr(extraction_module, "MAX_ARCHIVE_ENTRIES", 2)
    payload = _zip_payload([("a", b""), ("b", b""), ("c", b"")])
    result = extract_document(payload, "many.docx", "doc", "project")
    assert result["extraction_status"] == "ERROR"
    assert result["metadata"]["error_type"] == "ArchiveSafetyError"
    assert "entry count" in result["metadata"]["error"]


def test_office_archive_uncompressed_size_limit_blocks_compressed_bomb(monkeypatch) -> None:
    monkeypatch.setattr(extraction_module, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 1024)
    payload = _zip_payload([("word/document.xml", b"0" * 4096)])
    assert len(payload) < 1024
    result = extract_document(payload, "bomb.docx", "doc", "project")
    assert result["extraction_status"] == "ERROR"
    assert result["metadata"]["error_type"] == "ArchiveSafetyError"
    assert "uncompressed size" in result["metadata"]["error"]

def _pdf_with_ruled_table() -> bytes:
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    commands = ["0.5 w"]
    for x in (50, 200, 400):
        commands.append(f"{x} 580 m {x} 700 l S")
    for y in (580, 610, 640, 670, 700):
        commands.append(f"50 {y} m 400 {y} l S")
    for x, y, text in [(60, 680, "Condition"), (210, 680, "Value"), (60, 650, "Flow"), (210, 650, "450 m3/day"), (60, 620, "Zero"), (210, 620, "0"), (60, 590, "Unknown")]:
        commands.append(f"BT /F1 12 Tf 1 0 0 1 {x} {y} Tm ({text}) Tj ET")
    stream = DecodedStreamObject()
    stream.set_data("\n".join(commands).encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    writer.add_blank_page(width=612, height=792)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_pdf_table_preserves_cells_units_blank_zero_and_page_block_ids() -> None:
    result = extract_document(_pdf_with_ruled_table(), "uploaded-table.pdf", "doc", "project")
    assert result["extraction_status"] == "EXTRACTED"
    pages = [block for block in result["blocks"] if block["locator_type"] == "pdf_page"]
    assert [block["id"] for block in pages] == ["doc:block:1", "doc:block:2"]
    assert [block["locator"] for block in pages] == ["page 1", "page 2"]
    assert pages[1]["extraction_status"] == "OCR_REQUIRED"
    tables = [block for block in result["blocks"] if block["locator_type"] == "pdf_table"]
    assert len(tables) == 1
    assert tables[0]["table"] == [["Condition", "Value"], ["Flow", "450 m3/day"], ["Zero", "0"], ["Unknown", ""]]
    cells = {block["locator"]: block for block in result["blocks"] if block["locator_type"] == "pdf_table_cell"}
    flow = cells["page 1, table 1, row 2, column 2"]
    assert flow["original_value"] == "450 m3/day"
    assert flow["unit"] == "m3/day"
    assert flow["cell_address"] == "R2C2"
    assert flow["bbox"] == [200.0, 122.0, 400.0, 152.0]
    assert flow["coordinate_system"] == "pdf_points_top_left"
    assert cells["page 1, table 1, row 3, column 2"]["original_value"] == "0"
    assert cells["page 1, table 1, row 4, column 2"]["original_value"] == ""
    assert "| Flow | 450 m3/day |" in result["markdown"]
    assert result["metadata"]["table_count"] == 1
    assert result["metadata"]["table_parser"] == "pdfplumber"
