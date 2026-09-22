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
