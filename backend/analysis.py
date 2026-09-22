"""Deterministic source-bound comparison. This module performs no model inference."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from typing import Any

TOPICS = (
    ("notice", "통지 기한", r"통지|notice|notification"),
    ("discharge", "방류 허용 조건", r"방류|discharge|effluent"),
    ("groundwater", "배수·지하수·수질", r"배수|지하수|염수|염분|염화|담수|펌프|양수|groundwater|chloride|salin|freshwater|pumping|inflow"),
    ("owner", "발주처·사업 개요", r"발주처|발주자|사업명|employer|client|project name"),
    ("duration", "공사 기간·일정", r"공기\b|공사기간|공사 기간|완공|completion|duration|schedule|construction period"),
    ("contract", "계약 방식·조건", r"계약방식|계약 방식|설계시공|실측정산|lump.?sum|design.?build|re.?measurement|fidic|contract type"),
    ("budget", "금액·예산", r"예산|계약금액|계약 금액|budget|contract price|contract value|revenue|수입"),
    ("jv", "공동도급·JV", r"\bJV\b|joint venture|공동도급|지분"),
    ("delay", "지체상금·손해배상", r"지체상금|지체 상금|liquidated damages|delay damages|penalt"),
    ("ground", "지반·시공 조건", r"암반|연약|지반|지층|soil|geolog|rock mass|tunnel|터널"),
    ("environment", "환경·인허가", r"환경|인허가|허가|environment|permit|approval condition"),
    ("risk", "과거 이슈·대응 교훈", r"리스크|위험|교훈|이슈|lessons?|risk|mitigation|issue|중단|stop work"),
)
PATTERNS = [(key, title, re.compile(pattern, re.I)) for key, title, pattern in TOPICS]
PATTERN_BY_KEY = {key: pattern for key, _, pattern in PATTERNS}
UNAPPROVED = re.compile(r"for\s+(?:bid\s+)?review|draft|unapproved|not approved|미승인|검토용|검토 중|초안", re.I)
UNKNOWN = re.compile(r"미확정|미정|확인 필요|미제공|알 수 없|확정값 없음|별도 산정|unknown|not confirmed|not determined|\btbd\b|not available", re.I)
AMENDMENT = re.compile(r"정정|addend|amendment|corrigendum", re.I)
INFORMAL = re.compile(r"회의록|meeting.?minutes|email|e-mail|\.eml$", re.I)
UNCHANGED = re.compile(r"변경하지\s*않|unchanged|not\s+changed", re.I)
LESSON_ID = re.compile(r"\b[A-Z][A-Z0-9]*-LL\d+\b|(?:lesson|교훈)\s*(?:no\.?\s*)?\d+", re.I)
RESPONSE_HEADING = re.compile(r"^(?:대응(?:과\s*후속\s*조치)?|후속\s*조치|response|mitigation)(?:\s|$)", re.I)
APPLICATION_HEADING = re.compile(r"적용할\s*때|적용\s*조건|적용\s*제한|reuse condition|applicab", re.I)
CLAUSE_TOKEN = r"(?:\d+(?:\.\d+)+|(?:ENV|G|QA|PROC|PERF|DOC)\s*\d+)"
CHANGE_CLAUSE = re.compile(rf"(?:변경|change(?:d)?|amend(?:ed)?)\s+(?P<key>{CLAUSE_TOKEN})\b", re.I)
ANY_CLAUSE = re.compile(rf"\b(?P<key>{CLAUSE_TOKEN})\b", re.I)
HEADER_STATUS = re.compile(r"\|\s*(APPROVED|FOR\s+(?:BID\s+)?REVIEW|DRAFT|ISSUED(?:\s+FOR\s+CONSTRUCTION)?|FINAL|SIGNED|승인)\s*\|", re.I)
CELL_LOCATOR = re.compile(r"^(?P<sheet>.+)!(?P<column>[A-Z]+)(?P<row>\d+)$")
SCALE = re.compile(r"(?P<low>\d+(?:\.\d+)?)\s*(?:~|-|–|—|to)\s*(?P<high>\d+(?:\.\d+)?)", re.I)
CONTRACT_CODE = re.compile(r"\b([A-Z][A-Z0-9]*\d+-(?:ITB|CTR|CONTRACT)[-_]\d+)\b", re.I)
OBSERVATION = re.compile(r"관측|실적|실제|측정|증가|중단|발견|observed|measured|actual", re.I)
DESIGN = re.compile(r"설계|산정|용량|미확정|확정값 없음|tbd|design|capacity|not determined", re.I)
ALLOWANCE = re.compile(r"허용|허가|상한|제한|permit|allow|limit", re.I)


def fingerprint(documents, template_sha=""):
    entries = sorted((d["id"], d.get("sha256", ""), d.get("revision"), d.get("approval_status")) for d in documents)
    return hashlib.sha256(json.dumps([entries, template_sha], ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def source_ref(document, block, quote=None):
    return {"source_id": f"{document['id']}:{block['id']}", "document_id": document["id"],
            "project_id": document["project_id"], "filename": document["filename"],
            "source_path": document.get("metadata", {}).get("source_path", document["filename"]),
            "sha256": document["sha256"], "revision": document.get("revision"),
            "approval_status": document.get("approval_status", "UNKNOWN"),
            "locator_type": block.get("locator_type", "unknown"), "locator": block.get("locator", ""),
            "quote": quote or block.get("text", ""), "original_url": f"/api/documents/{document['id']}/original"}


def validate_refs(rows, documents):
    docs = {d["id"]: d for d in documents}
    for row in rows:
        refs = row.get("source_refs", []) + row.get("historical_refs", []) + row.get("current_refs", [])
        for extra in ("excluded_refs", "mitigation_refs", "reference_refs"):
            refs += row.get(extra, [])
        if not refs:
            if row.get("decision") != "REVIEW_REQUIRED":
                raise ValueError("EVIDENCE_REQUIRED")
            continue
        for ref in refs:
            doc = docs.get(ref.get("document_id"))
            if not doc or ref.get("sha256") != doc.get("sha256"):
                raise ValueError("SOURCE_VERSION_MISMATCH")
            expected_metadata = {
                "project_id": doc.get("project_id"),
                "filename": doc.get("filename"),
                "source_path": doc.get("metadata", {}).get("source_path", doc.get("filename")),
                "revision": doc.get("revision"),
                "approval_status": doc.get("approval_status", "UNKNOWN"),
            }
            if any(ref.get(key) != value for key, value in expected_metadata.items()):
                raise ValueError("SOURCE_METADATA_MISMATCH")
            matches = [b for b in doc.get("blocks", []) if f"{doc['id']}:{b['id']}" == ref.get("source_id")]
            if not matches or ref.get("locator") != matches[0].get("locator"):
                raise ValueError("SOURCE_NOT_FOUND")
            if ref.get("locator_type") != matches[0].get("locator_type", "unknown"):
                raise ValueError("SOURCE_METADATA_MISMATCH")
            if not ref.get("quote") or ref["quote"] not in matches[0].get("text", ""):
                raise ValueError("SOURCE_QUOTE_MISMATCH")


def _revision_number(doc):
    match = re.search(r"(?:rev(?:ision)?\s*)?(\d+)", str(doc.get("revision") or ""), re.I)
    return int(match.group(1)) if match else -1


def _doc_status(doc):
    # Prefer the document-control header near the start of a block. Later prose may
    # mention FOR REVIEW as a rule and must not change the document's own status.
    for block in doc.get("blocks", [])[:8]:
        match = HEADER_STATUS.search(block.get("text", "")[:700])
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).upper()
            if value == "APPROVED" or value == "승인" or value.startswith("ISSUED") or value in {"FINAL", "SIGNED"}:
                return "APPROVED"
            return "UNAPPROVED"
    status = str(doc.get("approval_status") or "UNKNOWN")
    if UNAPPROVED.search(status) or UNAPPROVED.search(doc.get("filename", "")):
        return "UNAPPROVED"
    if status.upper() in {"APPROVED", "ISSUED", "ISSUED_FOR_CONSTRUCTION", "FINAL", "SIGNED", "승인"}:
        return "APPROVED"
    return "UNKNOWN"


def _segments(text):
    return [piece.strip() for piece in re.split(r"(?<=[.!?。])\s+", text or "") if len(piece.strip()) >= 4]


def _clause_info(text):
    changed = CHANGE_CLAUSE.search(text)
    match = changed or ANY_CLAUSE.search(text)
    key = re.sub(r"\s+", " ", match.group("key")).upper() if match else None
    return key, bool(changed)


def _lesson_context(document):
    context = {}
    active = False
    phase = None
    topics = set()
    for block in document.get("blocks", []):
        text = block.get("text", "").strip()
        if not text:
            continue
        if LESSON_ID.search(text):
            active, phase = True, "issue"
            topics = {key for key, _, pattern in PATTERNS if key != "risk" and pattern.search(text)}
            context[block["id"]] = {"role": "issue_title", "topics": set(topics)}
            continue
        if not active:
            continue
        if RESPONSE_HEADING.search(text):
            phase = "mitigation"
            continue
        if APPLICATION_HEADING.search(text):
            phase = "applicability"
            continue
        found = {key for key, _, pattern in PATTERNS if key != "risk" and pattern.search(text)}
        if phase == "issue":
            topics.update(found)
        context[block["id"]] = {"role": phase, "topics": set(topics | found)}
        if phase == "applicability":
            active, phase = False, None
    return context


def _is_amendment(document):
    filename = document.get("filename", "")
    header = " ".join(block.get("text", "") for block in document.get("blocks", [])[:2])[:700]
    return bool(AMENDMENT.search(filename) or re.search(r"\b[A-Z][A-Z0-9]*\d+-(?:ADD|AMEND|CORR)[-_]\d+\b|정정서", header, re.I))


def _normalize_contract_id(value):
    return re.sub(r"\s+", "", str(value)).upper() if value else None


def _contract_identity(document, amendment=False):
    metadata = document.get("metadata", {})
    explicit = (metadata.get("contract_id") or metadata.get("contract_identity")
                or metadata.get("contract_family") or document.get("contract_id")
                or document.get("contract_family"))
    if explicit:
        return _normalize_contract_id(explicit), True
    # An amendment's mention of a contract number is a target, not the
    # amendment document's own identity.
    if amendment:
        return None, False
    header = " ".join(block.get("text", "") for block in document.get("blocks", [])[:4])[:2500]
    identities = {_normalize_contract_id(match.group(1)) for match in CONTRACT_CODE.finditer(header)}
    if len(identities) == 1:
        return identities.pop(), True
    return None, False


def _amendment_target(document, amendment=False):
    if not amendment:
        return None
    metadata = document.get("metadata", {})
    explicit = (metadata.get("amends_contract_id") or metadata.get("amendment_target")
                or document.get("amends_contract_id") or document.get("amendment_target"))
    if explicit:
        return _normalize_contract_id(explicit)
    # A single full contract identifier in the amendment body is an explicit
    # target. Multiple identifiers are ambiguous and must not be guessed.
    text = " ".join(block.get("text", "") for block in document.get("blocks", []))
    targets = {_normalize_contract_id(match.group(1)) for match in CONTRACT_CODE.finditer(text)}
    return targets.pop() if len(targets) == 1 else None


def _column_number(label):
    number = 0
    for character in label:
        number = number * 26 + ord(character.upper()) - 64
    return number


def _risk_data_rows(sheets):
    """Classify risk-register rows by table structure, independent of rating completeness."""
    locations = set()
    for sheet, rows in sheets.items():
        header_row = None
        columns = {}
        for number, cells in sorted(rows.items()):
            candidate = {}
            for column, value in cells.items():
                text = str(value or "")
                if re.search(r"사건|위험|risk", text, re.I):
                    candidate["description"] = column
                if re.search(r"가능성|likelihood|probability", text, re.I):
                    candidate["likelihood"] = column
                if re.search(r"영향|강도|impact|severity", text, re.I):
                    candidate["severity"] = column
            if {"description", "likelihood", "severity"}.issubset(candidate):
                header_row, columns = number, candidate
                break
        if header_row is None:
            continue
        for number, cells in rows.items():
            if number <= header_row:
                continue
            description = str(cells.get(columns["description"], "")).strip()
            if description:
                locations.add((sheet, number))
    return locations


def _xlsx_context_facts(document, status, amendment, informal, contract_id, contract_id_known, amendment_target):
    sheets, blocks = _workbook_rows(document)
    risk_rows = _risk_data_rows(sheets)
    facts = []
    for sheet, rows in sheets.items():
        for row_number, cells in sorted(rows.items()):
            ordered = sorted(((column, value) for column, value in cells.items() if value not in (None, "")), key=lambda item: _column_number(item[0]))
            if not ordered:
                continue
            text = " | ".join(str(value) for _, value in ordered)
            if amendment and UNCHANGED.search(text):
                continue
            matched = {key for key, _, pattern in PATTERNS if pattern.search(text)}
            if not matched:
                continue
            refs = [source_ref(document, blocks[(sheet, column, row_number)]) for column, _ in ordered]
            clause, explicit_change = _clause_info(text)
            for key in matched:
                facts.append((key, {"doc": document, "ref": refs[0], "refs": refs, "text": text,
                    "status": status, "amendment": amendment,
                    "explicit_change": explicit_change or bool(amendment and clause), "clause": clause,
                    "informal": informal, "role": "risk_record" if (sheet, row_number) in risk_rows else None, "contract_id": contract_id,
                    "contract_id_known": contract_id_known, "amendment_target": amendment_target}))
    return facts


def _facts(documents):
    result = {key: [] for key, _, _ in PATTERNS}
    for doc in documents:
        heading = " ".join(b.get("text", "") for b in doc.get("blocks", [])[:3])[:1800]
        amendment = _is_amendment(doc)
        lesson = _lesson_context(doc)
        status = _doc_status(doc)
        informal = bool(INFORMAL.search(doc.get("filename", "")))
        contract_id, contract_id_known = _contract_identity(doc, amendment)
        amendment_target = _amendment_target(doc, amendment)
        if amendment_target:
            contract_id, contract_id_known = amendment_target, True
        for key, fact in _xlsx_context_facts(doc, status, amendment, informal, contract_id, contract_id_known, amendment_target):
            result[key].append(fact)
        for block in doc.get("blocks", []):
            if block.get("locator_type") in {"xlsx_cell", "xlsx_sheet"}:
                continue
            block_context = lesson.get(block.get("id"), {})
            active_clause = None
            clause_topics = set()
            for line in _segments(block.get("text", "")):
                if amendment and UNCHANGED.search(line):
                    continue
                line_clause, explicit_change = _clause_info(line)
                if line_clause and line_clause != active_clause:
                    active_clause, clause_topics = line_clause, set()
                clause = line_clause or active_clause
                explicit_change = explicit_change or bool(amendment and line_clause)
                matched = {key for key, _, pattern in PATTERNS if pattern.search(line)}
                if clause:
                    matched.update(clause_topics)
                    clause_topics.update(matched)
                matched.update(block_context.get("topics", set()))
                if block_context.get("role"):
                    matched.add("risk")
                for key in matched:
                    result[key].append({"doc": doc, "ref": source_ref(doc, block, line), "text": line,
                        "status": status, "amendment": amendment, "explicit_change": explicit_change,
                        "clause": clause, "informal": informal, "role": block_context.get("role"),
                        "contract_id": contract_id, "contract_id_known": contract_id_known,
                        "amendment_target": amendment_target})
    return result


def _effective(facts):
    eligible = [fact for fact in facts if fact["status"] != "UNAPPROVED"]
    excluded = [fact for fact in facts if fact["status"] == "UNAPPROVED"]
    amendments = [fact for fact in eligible if fact["amendment"] and fact["explicit_change"]
                  and fact["status"] == "APPROVED" and not fact["informal"] and fact["clause"]]
    ambiguous_target = False
    for change in sorted(amendments, key=lambda fact: _revision_number(fact["doc"])):
        candidates = [fact for fact in eligible
                      if fact is not change and fact["clause"] == change["clause"] and not fact["informal"]
                      and fact["doc"].get("project_id") == change["doc"].get("project_id")
                      and _revision_number(fact["doc"]) < _revision_number(change["doc"])]
        target = change.get("amendment_target")
        if not target:
            known_targets = {fact.get("contract_id") for fact in candidates if fact.get("contract_id_known")}
            unknown_documents = {fact["doc"]["id"] for fact in candidates if not fact.get("contract_id_known")}
            if len(known_targets) == 1 and not unknown_documents:
                target = next(iter(known_targets))
                change["contract_id"] = target
                change["contract_id_known"] = True
            else:
                ambiguous_target = True
        retained = []
        for fact in eligible:
            if fact is change or fact["clause"] != change["clause"] or fact["informal"]:
                retained.append(fact)
                continue
            if fact["doc"].get("project_id") != change["doc"].get("project_id"):
                retained.append(fact)
                continue
            if not target:
                retained.append(fact)
                continue
            if not fact.get("contract_id_known"):
                ambiguous_target = True
                retained.append(fact)
                continue
            if fact.get("contract_id") != target:
                retained.append(fact)
                continue
            if _revision_number(fact["doc"]) >= _revision_number(change["doc"]):
                retained.append(fact)
        eligible = retained
    unique = {}
    for fact in eligible:
        unique.setdefault((fact["doc"]["sha256"], fact["ref"]["locator"], fact["text"], fact.get("role")), fact)
    return list(unique.values()), excluded, ambiguous_target


def _fact_refs(fact):
    return fact.get("refs") or [fact["ref"]]


def _display_priority(fact):
    text = fact["text"]
    has_number_and_unit = bool(re.search(
        r"\d+(?:[,.]\d+)*\s*(?:calendar days|days|일|m3/day|m3/h|mg/L|개월|months|%)", text, re.I))
    return (
        0 if fact["status"] == "APPROVED" else 1,
        0 if fact["amendment"] else 1,
        0 if fact.get("clause") else 1,
        0 if has_number_and_unit else 1,
        fact["doc"].get("sha256", ""),
        fact["ref"].get("locator", ""),
        text,
    )


def _display_groups(facts, key):
    ordered = sorted(facts, key=_display_priority)
    if key == "risk":
        return ordered, []
    primary = [fact for fact in ordered if fact.get("role") != "risk_record"]
    references = [fact for fact in ordered if fact.get("role") == "risk_record"]
    return primary, references


def _display(facts, limit=12):
    return "\n".join(fact["text"] for fact in facts[:limit])


def _value_kind(fact, current):
    text = fact["text"]
    if current:
        if ALLOWANCE.search(text) and (DESIGN.search(text) or UNKNOWN.search(text)):
            return "current_mixed_requires_review"
        if DESIGN.search(text) or UNKNOWN.search(text):
            return "current_design_or_unknown"
        if ALLOWANCE.search(text):
            return "current_allowance"
        return "current_condition"
    if OBSERVATION.search(text):
        return "historical_observation"
    return "historical_contract_or_case"


def _value_classes(facts, current):
    return [{"kind": _value_kind(fact, current), "text": fact["text"], "source_ref": fact["ref"], "source_refs": _fact_refs(fact)} for fact in facts]


def _labeled(facts, current, limit=3):
    labels = {
        "current_mixed_requires_review": "허용 조건·설계/미확정 혼재 — 검토 필요",
        "current_design_or_unknown": "신규 설계값/미확정",
        "current_allowance": "신규 허용량/계약 조건",
        "current_condition": "신규 조건",
        "historical_observation": "과거 관측값",
        "historical_contract_or_case": "과거 계약/사례",
    }
    return "\n".join(f"[{labels[_value_kind(fact, current)]}] {fact['text']}" for fact in facts[:limit])


def _numeric(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    match = re.fullmatch(r"\s*([+-]?\d+(?:\.\d+)?)\s*", str(value or ""))
    if not match:
        return None
    number = float(match.group(1))
    return int(number) if number.is_integer() else number


def _workbook_rows(document):
    sheets = defaultdict(lambda: defaultdict(dict))
    blocks = {}
    for block in document.get("blocks", []):
        match = CELL_LOCATOR.match(block.get("locator", ""))
        if block.get("locator_type") != "xlsx_cell" or not match:
            continue
        key = (match.group("sheet"), match.group("column"), int(match.group("row")))
        value = block.get("original_value", block.get("text"))
        sheets[key[0]][key[2]][key[1]] = value
        blocks[key] = block
    return sheets, blocks


def _risk_records(document):
    sheets, blocks = _workbook_rows(document)
    records = []
    for sheet, rows in sheets.items():
        header_row = None
        columns = {}
        scale = None
        for number, cells in sorted(rows.items()):
            for column, value in cells.items():
                text = str(value or "")
                if re.search(r"사건|위험|risk", text, re.I):
                    columns["description"] = column
                if re.search(r"가능성|likelihood|probability", text, re.I):
                    columns["likelihood"] = column
                if re.search(r"영향|강도|impact|severity", text, re.I):
                    columns["severity"] = column
            if {"description", "likelihood", "severity"}.issubset(columns):
                likelihood_header = str(cells.get(columns["likelihood"], ""))
                severity_header = str(cells.get(columns["severity"], ""))
                ranges = [SCALE.search(value) for value in (likelihood_header, severity_header)]
                if all(ranges) and ranges[0].groups() == ranges[1].groups():
                    scale = f"{ranges[0].group('low')}-{ranges[0].group('high')}"
                header_row = number
                break
            columns = {}
        if header_row is None:
            continue
        for number, cells in sorted(rows.items()):
            if number <= header_row:
                continue
            description = str(cells.get(columns["description"], "")).strip()
            likelihood = _numeric(cells.get(columns["likelihood"]))
            severity = _numeric(cells.get(columns["severity"]))
            if not description or likelihood is None or severity is None:
                continue
            records.append({"project_id": document["project_id"], "document": document, "description": description,
                "likelihood": likelihood, "severity": severity, "scale": scale,
                "case_key": (document.get("sha256"), f"{sheet}!{columns['description']}{number}", f"{sheet}!{columns['severity']}{number}"),
                "description_ref": source_ref(document, blocks[(sheet, columns["description"], number)]),
                "likelihood_ref": source_ref(document, blocks[(sheet, columns["likelihood"], number)]),
                "severity_ref": source_ref(document, blocks[(sheet, columns["severity"], number)])})
    return records


def _severity_evidence(documents, key, pattern):
    base = {"sample_count": 0, "project_count": 0, "unique_case_count": 0, "distribution": {}, "scale": None,
            "source_refs": [], "samples": [], "reason": ""}
    if key == "risk":
        base["reason"] = "서로 다른 위험 유형을 하나의 강도 표본으로 합치지 않습니다."
        return None, base
    records = []
    for document in documents:
        if _doc_status(document) != "APPROVED":
            continue
        records.extend(record for record in _risk_records(document) if pattern.search(record["description"]))
    unique_cases = {}
    for record in records:
        unique_cases.setdefault(record["case_key"], record)
    records = list(unique_cases.values())
    base["unique_case_count"] = len(records)
    grouped = defaultdict(list)
    for record in records:
        grouped[record["project_id"]].append(record)
    samples = []
    ambiguous_projects = []
    for project_id, project_records in grouped.items():
        values = {record["severity"] for record in project_records}
        scales = {record["scale"] for record in project_records}
        if len(values) != 1 or len(scales) != 1:
            ambiguous_projects.append(project_id)
            continue
        first = project_records[0]
        samples.append({"project_id": project_id, "severity": first["severity"], "scale": first["scale"],
                        "risk_refs": [record["description_ref"] for record in project_records],
                        "severity_refs": [record["severity_ref"] for record in project_records]})
    base["sample_count"] = len(samples)
    base["project_count"] = len(samples)
    base["samples"] = samples
    base["source_refs"] = [sample["severity_refs"][0] for sample in samples]
    distribution = Counter(sample["severity"] for sample in samples)
    base["distribution"] = {str(key): value for key, value in sorted(distribution.items(), key=lambda item: item[0])}
    scales = {sample["scale"] for sample in samples}
    if None in scales or len(scales) > 1:
        base["reason"] = "비교 사례의 위험 강도 척도가 동일하게 확인되지 않았습니다."
        return None, base
    base["scale"] = next(iter(scales), None)
    if len(samples) < 3:
        base["reason"] = "동일 척도의 비교 가능한 독립 프로젝트 사례가 최소 3건 필요합니다."
        return None, base
    if ambiguous_projects:
        base["reason"] = "한 프로젝트 안의 비교 사례 강도가 상충하여 후보 강도를 계산하지 않았습니다."
        return None, base
    highest = max(distribution.values())
    modes = [value for value, count in distribution.items() if count == highest]
    if len(modes) != 1:
        base["reason"] = "과거 강도 분포가 동률이므로 후보 강도를 비워 둡니다."
        return None, base
    candidate = modes[0]
    base["reason"] = "동일 척도의 비교 가능한 독립 프로젝트 사례에서 유일 최빈 강도를 후보로 표시합니다. 자동 확정값이 아닙니다."
    return candidate, base


def compare(current_documents, historical_documents):
    current, historical = _facts(current_documents), _facts(historical_documents)
    rows = []
    for key, title, pattern in PATTERNS:
        selected, excluded, current_target_ambiguity = _effective(current[key])
        past, _, historical_target_ambiguity = _effective(historical[key])
        if not selected and not excluded:
            continue
        missing = []
        if not selected:
            missing.append("유효한 신규 조건이 없습니다. 미승인 문서를 계약 조건으로 적용하지 않습니다.")
        if any(fact["status"] == "UNKNOWN" for fact in selected):
            missing.append("원문 승인 상태가 미확인입니다. 계약적 효력은 검토가 필요합니다.")
        if any(_value_kind(fact, True) == "current_mixed_requires_review" for fact in selected):
            missing.append("같은 근거에 허용 조건과 설계/미확정 값이 함께 있어 각각의 수치·단위·대상을 구분해야 합니다.")
        if any(UNKNOWN.search(fact["text"]) for fact in selected):
            missing.append("원문에 미확정 값이 있습니다. 0 또는 과거 수치로 대체하지 않습니다.")
        if not past:
            missing.append("비교 가능한 과거 근거가 등록되지 않았습니다.")
        if excluded:
            missing.append("미승인/검토용 자료는 유효 조건에서 제외했습니다. 제외 근거를 확인하세요.")
        if current_target_ambiguity or historical_target_ambiguity:
            missing.append("정정서의 대상 계약·계약군을 하나로 확인할 수 없어 같은 조항의 모든 버전을 보존했습니다.")
        if key in {"groundwater", "discharge"}:
            missing.append("허용 방류량·신규 설계량·과거 관측량을 구별하여 설계 담당자가 확인해야 합니다.")
        values = {tuple(re.findall(r"\d+(?:[,.]\d+)*\s*(?:calendar days|days|일|m3/day|m3/h|mg/L|개월|months|%)", fact["text"], re.I)) for fact in selected}
        values.discard(())
        if len(values) > 1:
            missing.append("같은 항목에 서로 다른 수치가 있습니다. 조항·적용 범위 확인이 필요합니다.")
        display_selected, current_reference_facts = _display_groups(selected, key)
        display_past, historical_reference_facts = _display_groups(past, key)
        if selected and not display_selected and current_reference_facts:
            missing.append("위험 검토 기록만 확인되어 유효한 신규 계약 조건으로 적용하지 않습니다.")
        if past and not display_past and historical_reference_facts:
            missing.append("과거 위험 검토 기록은 참고 자료이며 비교 가능한 과거 계약 조건이 아닙니다.")
        cur_refs = [ref for fact in display_selected for ref in _fact_refs(fact)][:24]
        old_refs = [ref for fact in display_past for ref in _fact_refs(fact)][:24]
        reference_facts = current_reference_facts + historical_reference_facts
        reference_refs = [ref for fact in reference_facts for ref in _fact_refs(fact)][:48]
        reference_sections = []
        if current_reference_facts:
            reference_sections.append("신규 위험 검토 기록:\n" + _display(current_reference_facts))
        if historical_reference_facts:
            reference_sections.append("과거 위험 검토 기록:\n" + _display(historical_reference_facts))
        reference_context = "\n".join(reference_sections)
        mitigation_facts = [fact for fact in past if fact.get("role") == "mitigation"]
        mitigation_refs = [ref for fact in mitigation_facts for ref in _fact_refs(fact)][:12]
        mitigation = _display(mitigation_facts, 6) or "근거가 있는 과거 대응을 확인한 뒤 담당자가 대응방안을 작성하세요."
        severity, severity_evidence = _severity_evidence(historical_documents, key, pattern)
        differences = ["신규 근거:\n" + (_labeled(display_selected, True) or "유효 조건 없음"),
                       "과거 근거:\n" + (_labeled(display_past, False) or "연결 없음")]
        if reference_context:
            differences.append("참고 위험 검토 기록:\n" + reference_context)
        rows.append({"id": key, "title": title, "current": _display(display_selected), "past": _display(display_past),
            "reference_context": reference_context, "reference_refs": reference_refs,
            "differences": differences,
            "decision": "REVIEW_REQUIRED" if missing else "REFERENCE",
            "rationale": "원문의 동일 검토 항목을 연결했습니다. 신규 계약 허용량·설계값·과거 관측값과 적용 조건을 별도로 표시하며 재사용 적합성을 자동 확정하지 않습니다.",
            "missing_information": missing, "current_refs": cur_refs, "historical_refs": old_refs,
            "excluded_refs": [ref for fact in excluded for ref in _fact_refs(fact)][:16], "source_refs": cur_refs + old_refs + reference_refs,
            "value_classes": {"current": _value_classes(display_selected, True), "historical": _value_classes(display_past, False)},
            "severity": severity, "severity_evidence": severity_evidence,
            "mitigation": mitigation, "mitigation_refs": mitigation_refs,
            "rule_id": "topic-clause-comparison-v2"})
    if not rows:
        rows.append({"id": "unclassified", "title": "검토 항목 확인", "current": "", "past": "", "differences": [],
            "decision": "REVIEW_REQUIRED", "rationale": "지원 검색 항목과 일치하는 추출 근거가 없습니다.",
            "missing_information": ["추출 원문을 확인하고 검토할 조건을 추가하세요."],
            "source_refs": [], "current_refs": [], "historical_refs": [], "severity": None, "mitigation": ""})
    return {"mode": "rules", "method": "명시적 키워드·조항·표 구조 비교", "ai_used": False,
            "limitations": ["모델 추론을 수행하지 않습니다.", "과거 수치·빈도는 신규 설계값이나 발생 확률이 아닙니다.",
                            "위험 강도 후보는 동일 척도의 독립 프로젝트 근거가 충분할 때만 표시합니다."], "rows": rows}


def knowledge_graph(comparison, documents, projects):
    nodes, edges = {}, {}
    docs, names = {d["id"]: d for d in documents}, {p["id"]: p["name"] for p in projects}
    for row in comparison["rows"]:
        refs = row.get("current_refs", []) + row.get("historical_refs", []) + row.get("reference_refs", [])
        if not refs:
            continue
        kid = "knowledge:" + row["id"]
        nodes[kid] = {"id": kid, "type": "knowledge", "label": row["title"], "row_id": row["id"]}
        for ref in refs:
            doc = docs.get(ref["document_id"])
            if not doc:
                continue
            did, pid = "doc:" + doc["id"], "project:" + doc["project_id"]
            nodes[pid] = {"id": pid, "type": "project", "label": names.get(doc["project_id"], "프로젝트")}
            nodes[did] = {"id": did, "type": "document", "label": doc["filename"], "document_id": doc["id"], "source_ref": ref}
            edges[(pid, did)] = {"source": pid, "target": did, "type": "contains", "label": "원본 자료"}
            edges[(did, kid)] = {"source": did, "target": kid, "type": "evidence", "label": "검토 항목 근거", "source_ref": ref}
    return {"nodes": list(nodes.values()), "edges": list(edges.values()), "comparisons": comparison["rows"],
            "mode": comparison["mode"], "limitations": comparison.get("limitations", [])}


def _query_tokens(query):
    stop_words = {
        "알려줘", "알려주세요", "설명해줘", "설명해주세요", "찾아줘", "찾아주세요",
        "보여줘", "보여주세요", "정리해줘", "정리해주세요", "검색해줘", "검색해주세요",
        "대해서", "대한", "관련", "무엇", "어떤", "비교해줘", "비교해주세요",
        "자료", "문서", "정보", "내용", "프로젝트", "기존프로젝트", "신규프로젝트",
        "기존", "과거", "현재", "신규", "전체", "모든", "좀", "대해",
        "please", "show", "me", "the", "a", "an", "of", "for", "in", "and", "about",
        "find", "search", "tell", "explain", "compare", "document", "documents",
        "project", "projects", "data", "information", "related", "all", "what", "which",
    }
    terms = []
    for term in re.findall(r"[\w가-힣]+", query.casefold()):
        if term in stop_words:
            continue
        if re.fullmatch(r"[가-힣]{3,}", term):
            term = re.sub(r"(?:에서는|으로|에서|에게|에는|의|은|는|이|가|을|를|에|와|과)$", "", term)
        if len(term) > 1 and term not in stop_words and term not in terms:
            terms.append(term)
    return terms[:12]


def _search_matches(text, terms, topics):
    folded = text.casefold()
    matched = [term for term in terms if term in folded]
    expanded = [title for title, pattern in topics if pattern.search(text)]
    return matched, expanded


def _search_excerpt(text, terms, topics, limit=520):
    """Return one contiguous excerpt without changing the stored source block."""
    boundaries = [0] + [match.end() for match in re.finditer(r"[.!?](?=\s|$)|\n+", text)]
    if boundaries[-1] != len(text):
        boundaries.append(len(text))
    candidates = []
    for start, end in zip(boundaries, boundaries[1:]):
        matched, expanded = _search_matches(text[start:end], terms, topics)
        if matched or expanded:
            candidates.append((len(matched) * 2 + len(expanded), start, end))
    if not candidates:
        return text[:limit], 0, min(len(text), limit)
    _, start, end = max(candidates, key=lambda candidate: (candidate[0], -candidate[1]))
    if end - start > limit:
        segment = text[start:end]
        positions = [segment.casefold().find(term) for term in terms if term in segment.casefold()]
        positions += [match.start() for _, pattern in topics if (match := pattern.search(segment))]
        anchor = min(positions) if positions else 0
        start += max(0, anchor - 100)
        end = min(end, start + limit)
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return text[start:end], start, end


def search_documents(documents, query):
    terms = _query_tokens(query)
    topics = [(title, pattern) for _, title, pattern in PATTERNS if pattern.search(query)]
    if not terms and not topics:
        return []
    hits = []
    for doc in documents:
        for block in doc.get("blocks", []):
            text = block.get("text", "")
            matched, expanded = _search_matches(text, terms, topics)
            if matched or expanded:
                excerpt, start, end = _search_excerpt(text, terms, topics)
                hits.append({"source_ref": source_ref(doc, block), "text": excerpt,
                             "is_excerpt": start != 0 or end != len(text),
                             "excerpt_start": start, "excerpt_end": end, "source_text_length": len(text),
                             "matched_terms": matched, "expanded_topics": expanded,
                             "reason": "검색어 원문 일치" if matched else "등록된 한·영 업무 용어 일치",
                             "match_count": len(matched), "topic_match_count": len(expanded)})
    hits.sort(key=lambda hit: -(hit["match_count"] * 2 + hit["topic_match_count"]))
    return hits[:100]


def insight_source_refs(comparison, documents, question, project_id):
    """Prioritize question-matched originals and retain both comparison scopes."""
    # Search relevance may rank only evidence already admitted by revision and
    # approval rules. Raw matches include superseded/unapproved contract clauses.
    fallback = [ref for row in comparison["rows"] for ref in row.get("source_refs", [])]
    matched = {hit["source_ref"]["source_id"] for hit in search_documents(documents, question)} if question else set()
    preferred = [ref for ref in fallback if ref["source_id"] in matched]
    ordered, seen = [], set()
    for group in (preferred, fallback):
        current = [ref for ref in group if ref.get("project_id") == project_id]
        historical = [ref for ref in group if ref.get("project_id") != project_id]
        for index in range(max(len(current), len(historical))):
            for scoped in (current, historical):
                if index >= len(scoped):
                    continue
                ref = scoped[index]
                if ref["source_id"] not in seen:
                    seen.add(ref["source_id"])
                    ordered.append(ref)
    return ordered
