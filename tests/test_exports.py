from __future__ import annotations

import io
from pathlib import Path

from openpyxl import load_workbook
from pptx import Presentation

from backend.exports import build_output

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "data" / "REBUILD_INPUT_v1" / "REBUILD_INPUT_v1" / "03_OUTPUT_TEMPLATES"


def _source(path: str = "02_ITB.pdf", locator: str = "page 2", quote: str = "450 m3/day") -> dict:
    return {"source_id": "doc-1:block-1", "document_id": "doc-1", "source_path": path, "sha256": "a" * 64, "revision": "Rev01", "approval_status": "APPROVED", "locator_type": "pdf_page", "locator": locator, "quote": quote, "url": "http://127.0.0.1:8780/#source=doc-1"}


def test_itb_export_preserves_template_and_adds_key_facts_with_sources() -> None:
    draft = {
        "kind": "itb",
        "title": "Blue Line ITB analysis",
        "items": [{"item_id": "ITB-01", "itb_clause": "Discharge", "current_condition": "450 m3/day", "historical_case": "Fresh-water settlement only", "differences": "Saline site", "decision": "ADAPT", "source_refs": [_source()], "review_required": "Confirm treatment design"}],
        "key_facts": [{"fact": "Discharge allowance", "value": 450, "unit": "m3/day", "source_refs": [_source()]}],
    }
    payload, mime, extension = build_output(draft, TEMPLATES / "ITB_Analysis_Template.xlsx")
    workbook = load_workbook(io.BytesIO(payload), data_only=False)
    sheet = workbook["ITB"]
    assert mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert extension == ".xlsx"
    assert [sheet.cell(5, column).value for column in range(1, 9)] == ["항목 ID", "ITB 조항", "신규 조건", "과거 사례", "조건 차이", "적용 판단", "원문 근거", "확인 필요 사항"]
    assert sheet["A6"].value == "ITB-01"
    assert "02_ITB.pdf" in sheet["G6"].value and "page 2" in sheet["G6"].value
    facts = workbook["Key Facts"]
    assert facts["A2"].value == "Discharge allowance"
    assert facts["B2"].value == 450 and facts["C2"].value == "m3/day"
    assert "Sources" in workbook.sheetnames
    sources = workbook["Sources"]
    assert sheet["G6"].hyperlink.target == "#'Sources'!A2"
    assert sources["J2"].hyperlink.target == "http://127.0.0.1:8780/#source=doc-1"
    assert sources["D2"].value == "a" * 64


def test_itb_empty_evidence_is_review_required() -> None:
    payload, _, _ = build_output({"type": "itb", "items": [{"item_id": "ITB-EMPTY", "itb_clause": "Unknown"}]}, TEMPLATES / "ITB_Analysis_Template.xlsx")
    sheet = load_workbook(io.BytesIO(payload))["ITB"]
    assert sheet["A6"].value == "ITB-EMPTY"
    assert sheet["G6"].value == "REVIEW_REQUIRED"
    assert "REVIEW_REQUIRED" in sheet["H6"].value


def test_risk_export_leaves_unknown_rating_fields_blank_and_reopens() -> None:
    draft = {"kind": "risk", "items": [{"risk_id": "R-01", "risk": "Saline discharge treatment", "cause": "Site conditions differ", "impact": "Permit delay", "mitigation": "Confirm treatment train", "source_refs": [_source("09_Field.txt", "line 4", "saline groundwater")]}]}
    payload, mime, extension = build_output(draft, TEMPLATES / "Risk_Register_Template.xlsx")
    workbook = load_workbook(io.BytesIO(payload), data_only=False)
    sheet = workbook.active
    values = [[cell.value for cell in row] for row in sheet.iter_rows()]
    flat = [value for row in values for value in row if value is not None]
    assert mime.endswith("spreadsheetml.sheet") and extension == ".xlsx"
    assert "R-01" in flat and any("REVIEW_REQUIRED" in str(value) for value in flat)
    risk_row = next(cell.row for cell in sheet["A"] if cell.value == "R-01")
    assert sheet.cell(risk_row, 9).hyperlink.target == "#'Sources'!A2"
    row = next(row for row in values if "R-01" in row)
    header_row = next(row for row in values if any("발생" in str(v) or "가능" in str(v) for v in row if v))
    for index, header in enumerate(header_row):
        if header and any(token in str(header) for token in ("발생가능성", "가능성", "강도", "점수", "Probability", "Score")):
            assert row[index] in (None, "")


def test_review_deck_uses_five_slide_template_and_embeds_sources_and_unknowns() -> None:
    draft = {
        "kind": "slides", "title": "Blue Line review",
        "business": [{"text": "Package 4 overview", "source_refs": [_source("brief.docx", "paragraph 2", "Package 4")]}],
        "itb": [{"text": "Discharge allowance 450 m3/day", "source_refs": [_source()]}],
        "applicability": [{"text": "Adapt settlement method for salinity", "source_refs": [_source("past.docx", "paragraph 15", "fresh water")]}],
        "risks": [{"text": "Treatment design unconfirmed", "source_refs": [_source("field.txt", "line 4", "saline")]}],
        "unknowns": [{"text": "Pump capacity", "source_refs": []}],
    }
    payload, mime, extension = build_output(draft, TEMPLATES / "Review_Deck_Template.pptx")
    deck = Presentation(io.BytesIO(payload))
    all_text = "\n".join(shape.text for slide in deck.slides for shape in slide.shapes if hasattr(shape, "text_frame"))
    assert mime == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    assert extension == ".pptx" and len(deck.slides) == 5
    assert "Package 4 overview" in all_text and "450 m3/day" in all_text
    assert "02_ITB.pdf" in all_text and "REVIEW_REQUIRED" in all_text
    links = [run.hyperlink.address for slide in deck.slides for shape in slide.shapes if hasattr(shape, "text_frame") for paragraph in shape.text_frame.paragraphs for run in paragraph.runs if run.hyperlink.address]
    assert "http://127.0.0.1:8780/#source=doc-1" in links


def _comparison_row() -> dict:
    return {
        "id": "discharge",
        "title": "방류 조건",
        "current": "허용량 450 m3/day",
        "past": "과거 담수 침전 사례",
        "differences": ["염수 조건", "허용량과 설계량 구분"],
        "decision": "REVIEW_REQUIRED",
        "rationale": "동일 의미인지 설계 검토가 필요합니다.",
        "missing_information": ["펌프 설계량 미확정"],
        "source_refs": [_source()],
        "severity": None,
        "mitigation": "처리 공정을 확인하세요.",
    }


def test_server_comparison_rows_map_to_itb_columns_without_serializing_lists() -> None:
    payload, _, _ = build_output({"kind": "itb", "rows": [_comparison_row()]}, TEMPLATES / "ITB_Analysis_Template.xlsx")
    sheet = load_workbook(io.BytesIO(payload))["ITB"]
    assert sheet["A6"].value == "discharge"
    assert sheet["B6"].value == "방류 조건"
    assert sheet["C6"].value == "허용량 450 m3/day"
    assert sheet["D6"].value == "과거 담수 침전 사례"
    assert "염수 조건" in sheet["E6"].value
    assert "펌프 설계량 미확정" in sheet["H6"].value


def test_server_comparison_rows_populate_all_review_deck_sections() -> None:
    payload, _, _ = build_output({"kind": "slides", "title": "심의 초안", "rows": [_comparison_row()]}, TEMPLATES / "Review_Deck_Template.pptx")
    deck = Presentation(io.BytesIO(payload))
    slide_text = ["\n".join(shape.text for shape in slide.shapes if hasattr(shape, "text_frame")) for slide in deck.slides]
    assert "방류 조건" in slide_text[0]
    assert "허용량 450 m3/day" in slide_text[1]
    assert "염수 조건" in slide_text[2]
    assert "처리 공정을 확인하세요." in slide_text[3]
    assert "펌프 설계량 미확정" in slide_text[4]

def test_user_edited_review_fields_survive_all_output_formats() -> None:
    row = _comparison_row()
    row.update({
        "decision": "ADAPT_AFTER_REVIEW",
        "rationale": "Browser reviewer verified the uploaded notice period.",
        "mitigation": "Preserve the reviewer mitigation exactly.",
        "missing_information": ["Confirm the final permit owner."],
    })

    itb_bytes, _, _ = build_output({"kind": "itb", "rows": [row]}, TEMPLATES / "ITB_Analysis_Template.xlsx")
    itb = load_workbook(io.BytesIO(itb_bytes))["ITB"]
    assert "ADAPT_AFTER_REVIEW" in itb["F6"].value
    assert "Browser reviewer verified the uploaded notice period." in itb["F6"].value
    assert "Confirm the final permit owner." in itb["H6"].value

    risk_bytes, _, _ = build_output({"kind": "risk", "rows": [row]}, TEMPLATES / "Risk_Register_Template.xlsx")
    risk = load_workbook(io.BytesIO(risk_bytes)).active
    assert "Browser reviewer verified the uploaded notice period." in risk["C6"].value
    assert risk["G6"].value == "Preserve the reviewer mitigation exactly."
    assert "Confirm the final permit owner." in risk["J6"].value

    slide_bytes, _, _ = build_output({"kind": "slides", "rows": [row]}, TEMPLATES / "Review_Deck_Template.pptx")
    deck = Presentation(io.BytesIO(slide_bytes))
    text = "\n".join(shape.text for slide in deck.slides for shape in slide.shapes if hasattr(shape, "text_frame"))
    assert "Browser reviewer verified the uploaded notice period." in text
    assert "Preserve the reviewer mitigation exactly." in text
    assert "Confirm the final permit owner." in text

def test_itb_long_content_uses_readable_summary_and_lossless_detail_sheet() -> None:
    current = "\n".join(f"Current condition line {index}: 450 m3/day must remain source-backed." for index in range(1, 15))
    historical = "\n".join(f"Historical comparison line {index}: observed value." for index in range(1, 20))
    differences = [f"Difference {index}: verify applicability and scope." for index in range(1, 18)]
    reference_context = "\n".join(f"Risk register reference {index}: =C{index}*D{index}" for index in range(1, 12))
    refs = [_source("contract.pdf", "page 2", "450 m3/day"),
            {**_source("risk.xlsx", "Risk!E8", "=C8*D8"), "source_id": "doc-2:block-2", "document_id": "doc-2"}]
    row = {
        "id": "discharge", "title": "Discharge allowance", "current": current,
        "past": historical, "differences": differences, "reference_context": reference_context,
        "decision": "REVIEW_REQUIRED", "rationale": "Reviewer rationale " * 20,
        "missing_information": ["Confirm permit owner " * 15], "source_refs": refs,
    }
    payload, _, _ = build_output({"kind": "itb", "rows": [row]}, TEMPLATES / "ITB_Analysis_Template.xlsx")
    workbook = load_workbook(io.BytesIO(payload), data_only=False)
    main = workbook["ITB"]
    detail = workbook["Review Detail"]
    facts = workbook["Key Facts"]

    assert "전체 내용: Review Detail 시트" in main["C6"].value
    assert len(main["C6"].value) < len(current)
    assert main["C6"].hyperlink.target == "#'Review Detail'!A2"
    assert "근거 2건" in main["G6"].value and "전체 SourceRef" in main["G6"].value
    assert main["G6"].hyperlink.target == "#'Sources'!A2"
    assert 36 < main.row_dimensions[6].height <= 120

    assert detail["D2"].value == current
    assert detail["E2"].value == historical
    assert detail["F2"].value == "\n".join(differences)
    assert detail["I2"].value == reference_context
    assert detail["J2"].value == 2

    assert "전체 내용: Review Detail 시트" in facts["B2"].value
    assert facts["B2"].hyperlink.target == "#'Review Detail'!A2"
    assert "근거 2건" in facts["D2"].value
    assert facts.row_dimensions[2].height <= 120


def test_itb_detail_and_source_quotes_preserve_values_beyond_excel_cell_limit() -> None:
    current = "승인 원문 450 m3/day\n" * 2_400
    quote = "근거 인용 450 m3/day\n" * 2_400
    ref = {**_source("long-contract.pdf", "page 12", quote), "quote": quote}
    payload, _, _ = build_output({
        "kind": "itb",
        "rows": [{"id": "long", "title": "Long approved clause", "current": current,
                  "decision": "REVIEW_REQUIRED", "source_refs": [ref]}],
    }, TEMPLATES / "ITB_Analysis_Template.xlsx")
    workbook = load_workbook(io.BytesIO(payload), data_only=False)

    detail = workbook["Review Detail"]
    assert "".join(str(detail.cell(row, 4).value or "") for row in range(2, detail.max_row + 1)) == current
    sources = workbook["Sources"]
    assert "".join(str(sources.cell(row, 9).value or "") for row in range(2, sources.max_row + 1)) == quote
    assert detail.max_row > 2 and sources.max_row > 2


def test_itb_detail_maps_every_item_to_all_of_its_source_rows() -> None:
    source_a = _source("A.pdf", "page A", "A")
    source_b = {**_source("B.pdf", "page B", "B"), "source_id": "doc-b:block", "document_id": "doc-b"}
    source_c = {**_source("C.pdf", "page C", "C"), "source_id": "doc-c:block", "document_id": "doc-c"}
    rows = [
        {"id": "one", "title": "One", "current": "value one", "decision": "REVIEW_REQUIRED",
         "source_refs": [source_a, source_b], "current_refs": [source_a], "historical_refs": [source_b]},
        {"id": "two", "title": "Two", "current": "value two", "decision": "REVIEW_REQUIRED",
         "source_refs": [source_a, source_c], "current_refs": [source_a], "reference_refs": [source_c]},
    ]
    payload, _, _ = build_output({"kind": "itb", "rows": rows}, TEMPLATES / "ITB_Analysis_Template.xlsx")
    workbook = load_workbook(io.BytesIO(payload), data_only=False)
    detail = workbook["Review Detail"]

    assert "current_refs: Sources!A2" in detail["L2"].value
    assert "historical_refs: Sources!A3" in detail["L2"].value
    assert "reference_refs: Sources!A4" in detail["L3"].value
    assert "Sources!A4" not in detail["L2"].value
    assert "Sources!A3" not in detail["L3"].value


def test_risk_long_content_has_lossless_detail_links_and_preserves_ratings() -> None:
    narrative = "승인 원문 450 m3/day\n" * 2_400
    mitigation = '=REVIEW_THIS_LITERAL() ' + '대응 방안을 원문과 검토하세요. ' * 40
    ref = _source()
    past_ref = {**_source('past.xlsx', 'Risk!C9', 'historic'), 'source_id': 'past:block', 'document_id': 'past'}
    row = {
        'id': 'long-risk', 'risk': '방류 처리 검토', 'cause': narrative,
        'mitigation': mitigation, 'probability': 2, 'intensity': 3,
        'source_refs': [ref, past_ref], 'current_refs': [ref], 'historical_refs': [past_ref],
        'reference_context': '승인 범위와 실제 설계량을 구분', 'rationale': '별도 판단 근거',
    }
    payload, _, _ = build_output({'kind': 'risk', 'rows': [row]}, TEMPLATES / 'Risk_Register_Template.xlsx')
    workbook = load_workbook(io.BytesIO(payload), data_only=False)
    main = workbook['RiskOutput']
    detail = workbook['Review Detail']
    assert '전체 내용: Review Detail 시트' in main['C6'].value
    assert main['C6'].hyperlink.target == "#'Review Detail'!A2"
    assert main['G6'].hyperlink.target == "#'Review Detail'!A2"
    assert main['I6'].hyperlink.target == "#'Sources'!A2"
    assert 36 < main.row_dimensions[6].height <= 120
    assert main['D6'].value == 2 and main['E6'].value == 3
    assert main['F6'].data_type == 'f' and 'D6*E6' in main['F6'].value
    assert ''.join(str(detail.cell(i, 4).value or '') for i in range(2, detail.max_row + 1)) == narrative
    assert detail['H2'].value == mitigation and detail['H2'].data_type == 's'
    assert detail['K2'].value == row['reference_context']
    assert 'current_refs: Sources!A2' in detail['L2'].value
    assert 'historical_refs: Sources!A3' in detail['L2'].value
    assert '별도 판단 근거' in detail['O2'].value


def test_risk_summary_starts_with_actual_condition_before_generic_rationale() -> None:
    row = _comparison_row()
    row['rationale'] = 'Review applicability and evidence before making any decision. ' * 30
    payload, _, _ = build_output({'kind': 'risk', 'rows': [row]}, TEMPLATES / 'Risk_Register_Template.xlsx')
    workbook = load_workbook(io.BytesIO(payload))
    assert workbook['RiskOutput']['C6'].value.startswith(row['current'])
    assert row['rationale'] in workbook['Review Detail']['D2'].value
    assert row['past'] in workbook['Review Detail']['D2'].value
