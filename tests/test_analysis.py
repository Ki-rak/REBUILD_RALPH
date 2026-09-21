from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import io
import pytest
from openpyxl import Workbook
from backend.extraction import extract_document
from backend.analysis import compare, fingerprint, knowledge_graph, validate_refs

def doc(did, text, revision="Rev00", status="APPROVED", filename="contract.txt", project="new", family="contract-main"):
    result = {"id":did, "project_id":project, "filename":filename, "sha256":sha256(text.encode()).hexdigest(),
              "revision":revision, "approval_status":status,
              "blocks":[{"id":"b1","text":text,"locator":"line 1","locator_type":"line"}]}
    if family is not None:
        result["metadata"] = {"contract_family": family}
    return result

def row(result, key):
    return next(r for r in result["rows"] if r["id"] == key)

def test_approved_amendment_changes_only_its_clause_and_draft_does_not_replace():
    base = doc("base", "Clause 20.1 Notice within 23 calendar days.\nContract type: lump sum.")
    amendment = doc("amend", "Clause 20.1 Notice within 17 calendar days.", "Rev01", filename="approved_addendum.txt")
    draft = doc("unapproved", "Clause 20.1 Notice within 5 calendar days.", "Rev02", "FOR REVIEW", "draft_addendum.txt")
    result = compare([base, amendment, draft], [])
    notice = row(result, "notice")
    assert "17 calendar days" in notice["current"]
    assert "23 calendar days" not in notice["current"]
    assert "5 calendar days" not in notice["current"]
    assert "lump sum" in row(result, "contract")["current"]
    assert notice["excluded_refs"][0]["document_id"] == "unapproved"
    validate_refs(result["rows"], [base, amendment, draft])

def test_unknown_design_never_becomes_permit_or_observation():
    current = doc("new", "Groundwater design inflow: TBD.\nDischarge permit: 450 m3/day.")
    historical = doc("old", "Observed groundwater inflow: 60 m3/h.", project="past")
    result = compare([current], [historical])
    water = row(result, "groundwater")
    assert water["decision"] == "REVIEW_REQUIRED"
    assert "TBD" in water["current"]
    assert "60" not in water["current"]
    assert water["severity"] is None
    assert water["current_refs"] and water["historical_refs"]

def test_fresh_numeric_input_changes_rows_fingerprint_and_actual_graph():
    old = doc("history", "Notice within 30 calendar days.", project="past")
    new1 = doc("new1", "Notice within 11 calendar days.")
    new2 = doc("new2", "Notice within 19 calendar days.")
    first, second = compare([new1], [old]), compare([new2], [old])
    assert row(first,"notice")["current"] != row(second,"notice")["current"]
    assert fingerprint([new1,old]) != fingerprint([new2,old])
    graph = knowledge_graph(second, [new2,old], [{"id":"new","name":"New"},{"id":"past","name":"Past"}])
    ids = {n["id"] for n in graph["nodes"]}
    assert "doc:new2" in ids and "doc:new1" not in ids
    assert all(e["source"] in ids and e["target"] in ids for e in graph["edges"])

def test_invented_source_and_modified_quote_are_rejected():
    current = doc("new", "Notice within 11 calendar days.")
    rows = compare([current], [])["rows"]
    forged = deepcopy(rows)
    forged[0]["source_refs"][0]["quote"] = "Notice within 1 calendar day."
    with pytest.raises(ValueError, match="SOURCE_QUOTE_MISMATCH"):
        validate_refs(forged, [current])
    forged = deepcopy(rows)
    forged[0]["source_refs"][0]["sha256"] = "0"*64
    with pytest.raises(ValueError, match="SOURCE_VERSION_MISMATCH"):
        validate_refs(forged, [current])

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "REBUILD_INPUT_v1" / "REBUILD_INPUT_v1"


def actual(relpath, did, project):
    path = INPUT / relpath
    result = extract_document(path.read_bytes(), path.name, did, project)
    assert result["extraction_status"] == "EXTRACTED"
    result["metadata"]["source_path"] = relpath.as_posix()
    return result


def actual_p01_n01():
    past_root = Path("01_PAST_PROJECTS/P01_Haeon_Metro_Package_2")
    new_root = Path("02_NEW_PROJECTS/N01_Haeon_Blue_Line_Package_4")
    historical = [
        actual(past_root / "01_Project_Brief_and_Lessons.docx", "p01-brief", "past-p01"),
        actual(past_root / "02_ITB_and_Contract_Rev00.pdf", "p01-itb", "past-p01"),
        actual(past_root / "03_Commercial_Risk_Procurement.xlsx", "p01-risk", "past-p01"),
    ]
    current = [
        actual(new_root / "01_Project_Brief_and_Lessons.docx", "n01-brief", "new-n01"),
        actual(new_root / "02_ITB_and_Contract_Rev00.pdf", "n01-itb", "new-n01"),
        actual(new_root / "03_Commercial_Risk_Procurement.xlsx", "n01-risk", "new-n01"),
        actual(new_root / "11_Addendum_Rev01.pdf", "n01-add01", "new-n01"),
        actual(new_root / "11_Addendum_Rev02.pdf", "n01-add02", "new-n01"),
    ]
    return current, historical


def test_actual_approved_addendum_replaces_only_explicit_changes_and_review_draft_is_excluded():
    current, historical = actual_p01_n01()
    result = compare(current, historical)
    notice = row(result, "notice")
    discharge = row(result, "discharge")
    assert "14 calendar days" in notice["current"]
    assert "28 calendar days" not in notice["current"]
    assert "7 calendar days" not in notice["current"]
    assert "450 m3/day" in discharge["current"]
    assert "600 m3/day" not in discharge["current"]
    assert "300 m3/day" not in discharge["current"]
    assert any(ref["document_id"] == "n01-add02" for ref in notice["excluded_refs"])
    for key, expected in (("contract", "설계시공 일괄"), ("budget", "365"), ("jv", "55%"), ("delay", "8%")):
        item = row(result, key)
        assert expected in item["current"]
        assert any(ref["document_id"] == "n01-itb" for ref in item["current_refs"])
        assert all(ref["document_id"] != "n01-add01" for ref in item["current_refs"])
    validate_refs(result["rows"], current + historical)


def test_actual_past_issue_and_response_are_linked_with_distinct_value_classes():
    current, historical = actual_p01_n01()
    result = compare(current, historical)
    risk = row(result, "risk")
    water = row(result, "groundwater")
    assert "지하수 유입과 방류허가" in risk["past"]
    assert "차수벽 접합부 주입과 침전조 증설" in risk["mitigation"]
    assert any("차수벽 접합부 주입" in ref["quote"] for ref in risk["historical_refs"])
    assert any(entry["kind"] == "current_design_or_unknown" for entry in water["value_classes"]["current"])
    assert any(entry["kind"] == "historical_observation" for entry in water["value_classes"]["historical"])
    assert "35에서 60 m3/h" not in water["current"]
    assert "35에서 60 m3/h" in water["past"]


def risk_sheet(did, project, impact, scale="1~5"):
    values = {
        "A5": "Risk ID", "B5": "사건 또는 위험", "C5": f"가능성 {scale}", "D5": f"영향 {scale}",
        "A6": f"{did}-R1", "B6": "지하수 유입과 방류허가", "C6": 3, "D6": impact,
    }
    blocks = []
    for index, (cell, value) in enumerate(values.items(), 1):
        blocks.append({"id": f"b{index}", "text": str(value), "original_value": value,
                       "locator": f"Risk!{cell}", "locator_type": "xlsx_cell"})
    raw = "|".join(str(value) for value in values.values())
    return {"id": did, "project_id": project, "filename": f"{did}.xlsx", "sha256": sha256(raw.encode()).hexdigest(),
            "revision": "Rev01", "approval_status": "APPROVED", "blocks": blocks}


def test_severity_candidate_requires_three_independent_comparable_same_scale_cases_and_unique_mode():
    current = [doc("new", "Discharge permit: 450 m3/day.")]
    historical = [risk_sheet("h1", "p1", 4), risk_sheet("h2", "p2", 4), risk_sheet("h3", "p3", 5)]
    discharge = row(compare(current, historical), "discharge")
    assert discharge["severity"] == 4
    evidence = discharge["severity_evidence"]
    assert evidence["sample_count"] == 3
    assert evidence["project_count"] == 3
    assert evidence["distribution"] == {"4": 2, "5": 1}
    assert len(evidence["source_refs"]) == 3

    tied = [risk_sheet("t1", "tp1", 4), risk_sheet("t2", "tp2", 4), risk_sheet("t3", "tp3", 5), risk_sheet("t4", "tp4", 5)]
    tied_row = row(compare(current, tied), "discharge")
    assert tied_row["severity"] is None
    assert "동률" in tied_row["severity_evidence"]["reason"]

    same_project = [risk_sheet("s1", "same", 4), risk_sheet("s2", "same", 4), risk_sheet("s3", "same", 4)]
    sparse = row(compare(current, same_project), "discharge")
    assert sparse["severity"] is None
    assert sparse["severity_evidence"]["project_count"] == 1
    assert "3" in sparse["severity_evidence"]["reason"]


def test_severity_candidate_rejects_mixed_scales():
    current = [doc("new", "Discharge permit: 450 m3/day.")]
    historical = [risk_sheet("h1", "p1", 4), risk_sheet("h2", "p2", 4), risk_sheet("h3", "p3", 3, "1~3")]
    discharge = row(compare(current, historical), "discharge")
    assert discharge["severity"] is None
    assert "척도" in discharge["severity_evidence"]["reason"]

def test_source_ref_document_metadata_cannot_be_forged():
    current = doc("new", "Notice within 11 calendar days.", revision="Rev03", status="APPROVED", filename="source.txt", project="project-a")
    rows = compare([current], [])["rows"]
    for field, value in (("project_id", "project-b"), ("filename", "forged.txt"), ("revision", "Rev99"), ("approval_status", "FOR REVIEW")):
        forged = deepcopy(rows)
        forged[0]["source_refs"][0][field] = value
        with pytest.raises(ValueError, match="SOURCE_METADATA_MISMATCH"):
            validate_refs(forged, [current])

def test_amendment_never_replaces_same_clause_in_another_project_or_family():
    current = [doc("new", "Notice within 11 calendar days.")]
    past_a = doc("past-a", "Clause 20.1 Notice within 23 calendar days.", project="past-a", family="contract-a")
    past_b = doc("past-b", "Clause 20.1 Notice within 17 calendar days.", revision="Rev01",
                 filename="approved_addendum.txt", project="past-b", family="contract-b")
    notice = row(compare(current, [past_a, past_b]), "notice")
    assert "23 calendar days" in notice["past"]
    assert "17 calendar days" in notice["past"]
    assert {ref["project_id"] for ref in notice["historical_refs"]} == {"past-a", "past-b"}


def test_unclear_contract_family_preserves_both_versions_and_requires_review():
    base = doc("base", "Clause 20.1 Notice within 23 calendar days.", project="same", family=None)
    amendment = doc("amend", "Clause 20.1 Notice within 17 calendar days.", revision="Rev01",
                    filename="approved_addendum.txt", project="same", family=None)
    notice = row(compare([base, amendment], []), "notice")
    assert "23 calendar days" in notice["current"] and "17 calendar days" in notice["current"]
    assert notice["decision"] == "REVIEW_REQUIRED"
    assert any("계약군" in reason for reason in notice["missing_information"])


def test_identical_risk_workbook_sha_is_one_case_even_with_three_project_aliases():
    current = [doc("new", "Discharge permit: 450 m3/day.")]
    original = risk_sheet("shared", "p1", 4)
    aliases = []
    for index, project in enumerate(("p1", "p2", "p3"), 1):
        alias = deepcopy(original)
        alias["id"] = f"alias-{index}"
        alias["project_id"] = project
        aliases.append(alias)
    discharge = row(compare(current, aliases), "discharge")
    assert discharge["severity"] is None
    assert discharge["severity_evidence"]["unique_case_count"] == 1
    assert discharge["severity_evidence"]["project_count"] == 1
    assert "3" in discharge["severity_evidence"]["reason"]


def test_xlsx_row_context_keeps_label_value_and_both_cell_sources():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Terms"
    sheet["A2"] = "Notice period"
    sheet["B2"] = "19 calendar days"
    output = io.BytesIO()
    workbook.save(output)
    document = extract_document(output.getvalue(), "terms.xlsx", "xlsx-doc", "new")
    document["approval_status"] = "APPROVED"
    result = compare([document], [])
    notice = row(result, "notice")
    assert "Notice period" in notice["current"]
    assert "19 calendar days" in notice["current"]
    assert {ref["locator"] for ref in notice["current_refs"]} >= {"Terms!A2", "Terms!B2"}
    validate_refs(result["rows"], [document])

def test_explicit_amendment_target_does_not_replace_second_contract_in_same_project():
    base_one = doc("base-1", "N77-ITB-001 Clause 20.1 Notice within 28 calendar days.", project="shared", family=None)
    base_two = doc("base-2", "N77-ITB-002 Clause 20.1 Notice within 35 calendar days.", project="shared", family=None)
    amendment = doc("add-1", "N77-ADD-001 APPROVED amendment to N77-ITB-001. Clause 20.1 Notice within 14 calendar days.",
                    revision="Rev01", filename="addendum.txt", project="shared", family=None)
    notice = row(compare([base_one, base_two, amendment], []), "notice")
    assert "14 calendar days" in notice["current"]
    assert "28 calendar days" not in notice["current"]
    assert "35 calendar days" in notice["current"]
    assert not any("대상 계약" in reason for reason in notice["missing_information"])


def test_amendment_without_target_preserves_all_when_project_has_multiple_contracts():
    base_one = doc("base-1", "N77-ITB-001 Clause 20.1 Notice within 28 calendar days.", project="shared", family=None)
    base_two = doc("base-2", "N77-ITB-002 Clause 20.1 Notice within 35 calendar days.", project="shared", family=None)
    amendment = doc("add-1", "N77-ADD-001 APPROVED amendment. Clause 20.1 Notice within 14 calendar days.",
                    revision="Rev01", filename="addendum.txt", project="shared", family=None)
    notice = row(compare([base_one, base_two, amendment], []), "notice")
    assert "28 calendar days" in notice["current"]
    assert "35 calendar days" in notice["current"]
    assert "14 calendar days" in notice["current"]
    assert notice["decision"] == "REVIEW_REQUIRED"
    assert any("대상 계약" in reason for reason in notice["missing_information"])