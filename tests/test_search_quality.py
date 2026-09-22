from backend.analysis import search_documents


def doc(key, text, pid="current"):
    return {"id":key,"project_id":pid,"filename":key+".txt","sha256":"a"*64,"blocks":[{"id":"b1","text":text,"locator":"paragraph 1"}]}


def test_korean_question_particles_and_explicit_topic_terms_find_originals():
    documents=[doc("a","지하수 유입량은 35 m3/h입니다."),doc("b","Groundwater inflow was 60 m3/h.","past"),doc("c","Meeting attendees and delivery addresses.")]
    hits=search_documents(documents,"지하수에 대해서 알려줘")
    assert {h["source_ref"]["document_id"] for h in hits} == {"a","b"}
    assert all(h["source_ref"]["quote"]==h["text"] for h in hits)
    assert search_documents(documents,"알려줘 설명해줘") == []


def test_ai_question_evidence_is_relevant_and_contains_both_project_scopes():
    from backend.analysis import insight_source_refs, compare
    documents=[doc("current-water","Groundwater: 45 m3/h."),doc("past-water","지하수 유입량 60 m3/h.","past")]
    irrelevant=[{"source_id":str(i),"document_id":"notice","project_id":"current","quote":"Notice period 14 days"} for i in range(30)]
    comparison=compare(documents[:1],documents[1:])
    comparison["rows"].insert(0,{"source_refs":irrelevant})
    selected=insight_source_refs(comparison,documents,"지하수 조건을 비교해줘","current")
    assert [r["document_id"] for r in selected[:2]] == ["current-water","past-water"]


def test_ai_evidence_never_crowds_out_effective_contract_with_unapproved_hits():
    from backend.analysis import compare, insight_source_refs
    def contract(key, days, status="APPROVED", revision="Rev00", project="current", filename="contract.txt"):
        item=doc(key, f"Clause 20.1 Notice within {days} calendar days.", project)
        item.update(approval_status=status, revision=revision, filename=filename, metadata={"contract_family":"main"})
        return item
    drafts=[contract(f"draft-{i}",5,"FOR REVIEW","Rev02",filename="draft_addendum.txt") for i in range(25)]
    base=contract("base",23)
    amendment=contract("amendment",17,revision="Rev01",filename="approved_addendum.txt")
    past=contract("past",28,project="past")
    current=drafts+[base,amendment]
    comparison=compare(current,[past])
    selected=insight_source_refs(comparison,current+[past],"Notice period", "current")[:25]
    assert {r["document_id"] for r in selected} == {"amendment","past"}
    assert any("17 calendar days" in r["quote"] for r in selected)


def test_search_ignores_generic_document_request_words():
    documents = [doc("generic", "기존프로젝트 자료 문서 정보입니다. Meeting delivery document."), doc("water", "지하수 유입량 45 m3/day, 승인 조건 확인.")]
    assert search_documents(documents, "기존프로젝트 자료를 보여줘") == []
    assert search_documents(documents, "Please show me the project documents") == []
    assert [hit["source_ref"]["document_id"] for hit in search_documents(documents, "기존프로젝트 자료에서 지하수에 대한 내용을 보여줘")] == ["water"]


def test_pdf_search_returns_focused_excerpt_with_original_locator_and_identity():
    target = "Groundwater inflow allowance is 450 m3/day; observed inflow was 35.5 m3/day."
    full = "Contract cover and meeting attendance.\n" * 40 + target + "\nDelivery addresses and administrative requirements. " * 40
    document = doc("contract", full)
    document["blocks"][0].update(locator_type="pdf_page", locator="page 7")
    hit = search_documents([document], "지하수 유입량 관련 자료를 찾아줘")[0]
    assert len(hit["text"]) <= 520
    assert "450 m3/day" in hit["text"] and "35.5 m3/day" in hit["text"]
    assert hit["source_ref"]["locator"] == "page 7"
    assert hit["source_ref"]["quote"] == full
    assert hit["source_ref"]["source_id"] == "contract:b1"
    assert document["blocks"][0]["text"] == full
    assert hit["source_text_length"] == len(full)
    assert hit["text"] == full[hit["excerpt_start"]:hit["excerpt_end"]]
    assert hit["is_excerpt"] is True


def test_search_prefers_specific_matches_and_bounds_single_long_line():
    specific = "Administrative preamble " * 70 + "groundwater inflow 450 m3/day approved" + " administrative appendix" * 70
    hits = search_documents([doc("broad", "Groundwater conditions pending."), doc("specific", specific)], "groundwater inflow documents please")
    assert hits[0]["source_ref"]["document_id"] == "specific"
    assert "groundwater inflow 450 m3/day" in hits[0]["text"]
    assert len(hits[0]["text"]) <= 520
    assert hits[0]["text"] in specific


def test_short_pdf_page_still_focuses_on_matching_sentence():
    text = "회의 참석자는 세 명입니다. 지하수 유입량은 45 m3/day입니다. 문서 배포 일정은 월요일입니다."
    hit = search_documents([doc("short-page", text)], "지하수 알려줘")[0]
    assert hit["text"] == "지하수 유입량은 45 m3/day입니다."
    assert hit["source_ref"]["quote"] == text
    assert hit["is_excerpt"] is True
