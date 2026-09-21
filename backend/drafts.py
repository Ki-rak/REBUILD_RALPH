"""Canonical editable sections and visible-layout contract for review decks."""
from copy import deepcopy
import json
import math
import re
import unicodedata

SLIDE_IDS = ("overview", "itb", "applicability", "risks", "decisions")
SLIDE_TITLES = ("사업 개요", "ITB 주요 조건", "과거 사례 적용성", "위험 및 대응", "미확정 사항과 의사결정")

# These limits match the 13.333 x 7.5 inch output geometry used by exports.py.
SLIDE_TITLE_MAX_CHARS = 80
SLIDE_TITLE_LINE_UNITS = 60
SLIDE_TITLE_MAX_RENDERED_LINES = 2
SLIDE_BODY_MAX_CHARS = 650
SLIDE_BODY_LINE_UNITS = 88
SLIDE_BODY_MAX_RENDERED_LINES = 12
SLIDE_VISIBLE_SOURCE_LIMIT = 3
_GENERATED_EXCERPT_LIMIT = 100
_GENERATED_ITEM_LIMIT = 4


def _text(value):
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if item not in (None, ""))
    return "" if value is None else str(value)


def _references(rows, field):
    unique = {}
    for row in rows:
        for ref in row.get(field, []):
            unique[(ref.get("source_id"), ref.get("document_id"), ref.get("locator"), ref.get("quote"))] = deepcopy(ref)
    return list(unique.values())


def _all_references(rows):
    """Normalize every evidence role into the validated top-level SourceRef list."""
    unique = {}
    for row in rows:
        priority = ("current_refs", "historical_refs", "source_refs", "mitigation_refs", "reference_refs", "excluded_refs")
        fields = list(priority) + [field for field in row if field not in priority]
        for field in fields:
            if not (field.endswith("_refs") or field in {"refs", "source_ref"}):
                continue
            values = row.get(field)
            if isinstance(values, dict):
                values = [values]
            if not isinstance(values, list):
                continue
            for ref in values:
                if isinstance(ref, dict):
                    key = (ref.get("source_id"), ref.get("document_id"), ref.get("locator"), ref.get("quote"))
                    unique.setdefault(key, deepcopy(ref))
        evidence = row.get("severity_evidence")
        if isinstance(evidence, dict):
            evidence_groups = [evidence]
            evidence_groups.extend(sample for sample in evidence.get("samples", []) if isinstance(sample, dict))
            for group in evidence_groups:
                for field in ("source_refs", "refs", "case_refs", "risk_refs", "severity_refs"):
                    values = group.get(field) or []
                    if isinstance(values, dict):
                        values = [values]
                    for ref in values if isinstance(values, list) else []:
                        if isinstance(ref, dict):
                            key = (ref.get("source_id"), ref.get("document_id"), ref.get("locator"), ref.get("quote"))
                            unique[key] = deepcopy(ref)
    return list(unique.values())


def _display_units(text):
    units = 0
    for character in str(text):
        if character == "\t":
            units += 4
        elif unicodedata.east_asian_width(character) in {"W", "F", "A"} or character in "WMwm@%&" or (character.isascii() and character.isalpha() and character.isupper()):
            units += 2
        else:
            units += 1
    return units


def _wrapped_line_count(text, line_units):
    if not text:
        return 0
    return sum(max(1, math.ceil(_display_units(line) / line_units)) for line in str(text).split("\n"))


def slide_visible_text(row):
    """Return the exact canonical text written to a slide body."""
    return "\n".join(filter(None, (
        _text(row.get("current")), _text(row.get("decision")),
        _text(row.get("rationale")), _text(row.get("missing_information")),
    )))


def _bounded_excerpt(value, max_units=_GENERATED_EXCERPT_LIMIT):
    text = re.sub(r"\s+", " ", _text(value)).strip()
    if _display_units(text) <= max_units:
        return text
    output = []
    units = 0
    for character in text:
        width = _display_units(character)
        if units + width > max_units - 2:
            break
        output.append(character)
        units += width
    return "".join(output).rstrip() + " …"


def _comparison_detail(row):
    fields = (
        ("항목", row.get("title") or row.get("id")),
        ("신규 조건", row.get("current")),
        ("과거 근거", row.get("past")),
        ("차이", row.get("differences")),
        ("참고 위험 검토 기록", row.get("reference_context")),
        ("판단", row.get("decision")),
        ("판단 근거", row.get("rationale")),
        ("대응", row.get("mitigation")),
        ("위험 강도", row.get("severity")),
        ("수치 성격", json.dumps(row.get("value_classes"), ensure_ascii=False, sort_keys=True) if row.get("value_classes") else None),
        ("미확정 정보", row.get("missing_information")),
    )
    lines = [f"{label}: {_text(value)}" for label, value in fields if value not in (None, "", [])]
    evidence = row.get("severity_evidence")
    if isinstance(evidence, dict):
        for key in ("sample_count", "project_count", "unique_case_count", "distribution", "scale", "reason"):
            value = evidence.get(key)
            if value not in (None, "", {}, []):
                rendered = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else _text(value)
                lines.append(f"위험 강도 근거 {key}: {rendered}")
        for index, sample in enumerate(evidence.get("samples", []), 1):
            if not isinstance(sample, dict):
                continue
            for key in ("project_id", "severity", "scale", "value_classes"):
                value = sample.get(key)
                if value not in (None, "", {}, []):
                    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else _text(value)
                    lines.append(f"위험 강도 표본 {index} {key}: {rendered}")
            for field in ("risk_refs", "severity_refs"):
                refs = sample.get(field) or []
                labels = [f"{ref.get('source_id') or ref.get('document_id') or 'source'} @ {ref.get('locator') or 'locator unavailable'}"
                          for ref in refs if isinstance(ref, dict)] if isinstance(refs, list) else []
                if labels:
                    lines.append(f"위험 강도 표본 {index} 근거 역할 {field} ({len(labels)}건): " + "; ".join(labels))
    for field, refs in row.items():
        if not field.endswith("_refs") or not isinstance(refs, list) or not refs:
            continue
        labels = []
        for ref in refs:
            if isinstance(ref, dict):
                labels.append(f"{ref.get('source_id') or ref.get('document_id') or 'source'} @ {ref.get('locator') or 'locator unavailable'}")
        if labels:
            lines.append(f"근거 역할 {field} ({len(labels)}건): " + "; ".join(labels))
    return "\n".join(lines)


def _section_excerpt(rows, section_index):
    if not rows:
        return "REVIEW_REQUIRED: 관련 원문 정보가 없습니다."
    lines = ["근거 기반 원문 발췌 · 전체 내용은 상세 보기와 발표자 노트에서 확인"]
    for row in rows[:_GENERATED_ITEM_LIMIT]:
        heading = _text(row.get("title") or row.get("id"))
        if section_index in (0, 1):
            detail = _text(row.get("current")) or "REVIEW_REQUIRED"
        elif section_index == 2:
            detail = " / ".join(filter(None, (
                "신규 " + (_text(row.get("current")) or "REVIEW_REQUIRED"),
                "과거 " + (_text(row.get("past")) or "REVIEW_REQUIRED"),
                _text(row.get("decision")),
            )))
        elif section_index == 3:
            severity = row.get("severity")
            condition = _bounded_excerpt(row.get("current") or "REVIEW_REQUIRED", 26)
            mitigation = _bounded_excerpt(row.get("mitigation") or "REVIEW_REQUIRED", 26)
            detail = (f"조건 {condition} / 대응 {mitigation} / 강도 "
                      + ("REVIEW_REQUIRED" if severity is None else str(severity)))
        else:
            detail = _text(row.get("missing_information")) or "REVIEW_REQUIRED: 최종 검토 필요"
        lines.append(f"• {heading}: {_bounded_excerpt(detail)}")
    if len(rows) > _GENERATED_ITEM_LIMIT:
        lines.append(f"• 외 {len(rows) - _GENERATED_ITEM_LIMIT}개 항목 · 전체 내용은 상세 보기와 발표자 노트")
    return "\n".join(lines)


def build_slide_rows(comparisons):
    """Build five editable sections with bounded excerpts and lossless detail fields."""
    overview = [row for row in comparisons if row.get("id") in {"owner", "duration", "budget", "jv", "contract"}]
    groups = (overview, comparisons, comparisons, comparisons, comparisons)
    result = []
    for index, (section_id, title, rows) in enumerate(zip(SLIDE_IDS, SLIDE_TITLES, groups)):
        missing = list(dict.fromkeys(str(item) for row in rows for item in row.get("missing_information", [])))
        missing_summary = [f"미확정 정보 {len(missing)}건 · 상세 보기와 발표자 노트에서 확인"] if missing else []
        detail_text = "\n\n".join(_comparison_detail(row) for row in rows) or "관련 원문 정보가 없습니다."
        visible = _section_excerpt(rows, index)
        source_refs = _all_references(rows)
        result.append({
            "id": section_id, "title": title, "current": visible,
            "past": "", "differences": [], "decision": "REVIEW_REQUIRED", "rationale": "",
            "missing_information": missing_summary,
            "detail_text": detail_text, "excerpted": visible != detail_text,
            "source_refs": source_refs,
            "current_refs": _references(rows, "current_refs"),
            "historical_refs": _references(rows, "historical_refs"),
            "severity": None, "mitigation": "",
        })
    validate_slide_rows(result)
    return result


def validate_slide_rows(rows):
    """Validate canonical section shape and conservative wrapped-text fit."""
    if [row.get("id") for row in rows] != list(SLIDE_IDS):
        raise ValueError("FIVE_SLIDE_SECTIONS_REQUIRED")
    for row in rows:
        title = _text(row.get("title"))
        if len(title) > SLIDE_TITLE_MAX_CHARS or _wrapped_line_count(title, SLIDE_TITLE_LINE_UNITS) > SLIDE_TITLE_MAX_RENDERED_LINES:
            raise ValueError("SLIDE_TITLE_TOO_LONG")
        body = slide_visible_text(row)
        if len(body) > SLIDE_BODY_MAX_CHARS or _wrapped_line_count(body, SLIDE_BODY_LINE_UNITS) > SLIDE_BODY_MAX_RENDERED_LINES:
            raise ValueError("SLIDE_CONTENT_TOO_LONG")
