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
    from backend.analysis import insight_source_refs
    documents=[doc("current-water","Groundwater: 45 m3/h."),doc("past-water","지하수 유입량 60 m3/h.","past")]
    irrelevant=[{"source_id":str(i),"document_id":"notice","project_id":"current","quote":"Notice period 14 days"} for i in range(30)]
    selected=insight_source_refs({"rows":[{"source_refs":irrelevant}]},documents,"지하수 조건을 비교해줘","current")
    assert [r["document_id"] for r in selected[:2]] == ["current-water","past-water"]
