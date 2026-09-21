"""Canonical editable sections for the five-slide review deck."""
from copy import deepcopy

SLIDE_IDS = ("overview", "itb", "applicability", "risks", "decisions")
SLIDE_TITLES = ("사업 개요", "ITB 주요 조건", "과거 사례 적용성", "위험 및 대응", "미확정 사항과 의사결정")


def _text(value):
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if item not in (None, ""))
    return "" if value is None else str(value)


def _references(rows, field):
    unique = {}
    for row in rows:
        for ref in row.get(field, []):
            unique[(ref.get("source_id"), ref.get("quote"))] = deepcopy(ref)
    return list(unique.values())


def build_slide_rows(comparisons):
    """Aggregate every topic once into section bodies; these bodies are then editable."""
    overview = [row for row in comparisons if row.get("id") in {"owner", "duration", "budget", "jv", "contract"}]
    groups = (overview, comparisons, comparisons, comparisons, comparisons)
    result = []
    for index, (section_id, title, rows) in enumerate(zip(SLIDE_IDS, SLIDE_TITLES, groups)):
        lines = []
        for row in rows:
            heading = _text(row.get("title") or row.get("id"))
            if index in (0, 1):
                detail = _text(row.get("current")) or "REVIEW_REQUIRED"
            elif index == 2:
                detail = "\n".join(filter(None, [
                    "신규: " + (_text(row.get("current")) or "REVIEW_REQUIRED"),
                    "과거: " + (_text(row.get("past")) or "REVIEW_REQUIRED"),
                    _text(row.get("differences")), _text(row.get("decision")),
                    _text(row.get("rationale")),
                ]))
            elif index == 3:
                severity = row.get("severity")
                detail = "\n".join(filter(None, [
                    _text(row.get("rationale")),
                    "대응: " + (_text(row.get("mitigation")) or "REVIEW_REQUIRED"),
                    "강도: " + ("REVIEW_REQUIRED" if severity is None else str(severity)),
                    _text(row.get("severity_rationale")),
                ]))
            else:
                detail = _text(row.get("missing_information")) or "REVIEW_REQUIRED: 최종 검토 필요"
            lines.append(heading + "\n" + detail)
        missing = list(dict.fromkeys(str(item) for row in rows for item in row.get("missing_information", [])))
        result.append({
            "id": section_id, "title": title,
            "current": "\n\n".join(lines) or "REVIEW_REQUIRED: 관련 원문 정보가 없습니다.",
            "past": "", "differences": [], "decision": "REVIEW_REQUIRED", "rationale": "",
            "missing_information": missing, "source_refs": _references(rows, "source_refs"),
            "current_refs": _references(rows, "current_refs"),
            "historical_refs": _references(rows, "historical_refs"),
            "severity": None, "mitigation": "",
        })
    return result


def validate_slide_rows(rows):
    if [row.get("id") for row in rows] != list(SLIDE_IDS):
        raise ValueError("FIVE_SLIDE_SECTIONS_REQUIRED")