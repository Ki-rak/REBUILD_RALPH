"""HTTP workflow tests use an explicitly injected RLS-shaped fake, never a product fallback."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from uuid import uuid4
import openpyxl
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend.server import create_app, Context
from backend.config import Settings
from backend.storage import ConflictError, NotFoundError

class FakeStorage:
    def __init__(self, owner, records, files):
        self.owner, self.records, self.files = owner, records, files
    def list(self, kind, project_id=None):
        return deepcopy([v for (owner,_),v in self.records.items()
                         if owner==self.owner and v["kind"]==kind and (project_id is None or v["project_id"]==project_id)])
    def get(self, eid):
        return deepcopy(self.records.get((self.owner,eid)))
    def save(self, kind, eid, project_id, payload, expected_version=None):
        previous = self.records.get((self.owner,eid))
        if expected_version is not None and (not previous or previous["version"] != expected_version):
            raise RuntimeError("test conflict")
        entity = {"id":eid,"kind":kind,"project_id":project_id,"payload":deepcopy(payload),
                  "version":previous["version"]+1 if previous else 1}
        self.records[(self.owner,eid)] = entity
        return deepcopy(entity)
    def approve(self, draft_id, expected_version, draft_payload, approval_id, approval_payload):
        previous = self.get(draft_id)
        if not previous or previous["version"] != expected_version:
            raise RuntimeError("test conflict")
        self.save("approval",approval_id,previous["project_id"],approval_payload)
        return self.save("draft",draft_id,previous["project_id"],draft_payload,expected_version)
    def upload_bytes(self, path, data, content_type):
        assert path.split("/")[0] == self.owner
        if path in self.files:
            raise ConflictError("immutable object already exists")
        self.files[path] = bytes(data)
        return {"path":path}
    def download_bytes(self, path):
        if path.split("/")[0] != self.owner:
            raise PermissionError()
        if path not in self.files:
            raise NotFoundError("test object not found")
        return self.files[path]

class FakeAuth:
    def logout(self, token):
        pass

@pytest.fixture
def flow():
    records, files = {}, {}
    owners = {"alice":str(uuid4()),"bob":str(uuid4())}
    def context(token):
        if token not in owners:
            raise HTTPException(401)
        return Context({"id":owners[token],"email":token+"@example.invalid"},FakeStorage(owners[token],records,files),FakeAuth(),token)
    app = create_app(Settings("https://wsziosnttnxefgfbgpeq.supabase.co","test-publishable","local",approval_signing_key="isolated-test-integrity-key-not-production"),context_factory=context)
    return TestClient(app, raise_server_exceptions=False), records, files

def auth(user="alice"):
    return {"Authorization":"Bearer "+user}
def project(client, name="New project", kind="current"):
    r=client.post("/api/projects",json={"name":name,"kind":kind},headers=auth())
    assert r.status_code==201, r.text
    return r.json()["id"]
def upload(client,pid,text,name="fresh.txt"):
    r=client.post(f"/api/projects/{pid}/upload",files={"files":(name,text.encode(),"text/plain")},headers=auth())
    assert r.status_code==200, r.text
    return r.json()["documents"][0]
def draft(client,pid,kind="itb"):
    r=client.post(f"/api/projects/{pid}/drafts",json={"kind":kind,"mode":"rules"},headers=auth())
    assert r.status_code==201, r.text
    return r.json()

def test_new_upload_evidence_approval_actual_xlsx_and_edit_invalidates(flow):
    c,records,files=flow
    old=project(c,"Historical","historical")
    upload(c,old,"Notice period: 28 calendar days.\nLessons learned: late notice causes risk.","history.txt")
    pid=project(c)
    content="Employer: Example Transit.\nNotice period: 14 calendar days.\nContract type: lump sum."
    document=upload(c,pid,content)
    assert document["sha256"]==sha256(content.encode()).hexdigest()
    assert files[document["storage_path"]]==content.encode()
    assert document["blocks"] and document["markdown"]
    d=draft(c,pid)
    assert any(r["historical_refs"] and r["current_refs"] for r in d["rows"])
    assert c.post(f"/api/drafts/{d['id']}/export",headers=auth()).status_code==409
    r=c.post(f"/api/drafts/{d['id']}/approve",json={"confirmed":True,"revision":d["revision"]},headers=auth())
    assert r.status_code==200,r.text
    export=c.post(f"/api/drafts/{d['id']}/export",headers=auth())
    assert export.status_code==200,export.text
    wb=openpyxl.load_workbook(BytesIO(export.content))
    all_values="\n".join(str(cell.value) for sheet in wb for row in sheet for cell in row if cell.value is not None)
    assert "14 calendar days" in all_values and "fresh.txt" in all_values
    changed=deepcopy(d["rows"]); changed[0]["rationale"]="검토자가 수정한 초안"
    edit=c.patch(f"/api/drafts/{d['id']}",json={"rows":changed,"revision":d["revision"]},headers=auth())
    assert edit.status_code==200,edit.text
    assert edit.json()["status"]=="draft"
    assert c.post(f"/api/drafts/{d['id']}/export",headers=auth()).status_code==409

def test_duplicate_and_changed_bytes_update_results_and_invalidate(flow):
    c,records,files=flow
    pid=project(c)
    first=upload(c,pid,"Notice: 13 calendar days.")
    duplicate=upload(c,pid,"Notice: 13 calendar days.","alias.txt")
    assert duplicate["id"]==first["id"] and duplicate["duplicate"]
    assert len(c.get(f"/api/projects/{pid}/documents",headers=auth()).json())==1
    d=draft(c,pid)
    assert c.post(f"/api/drafts/{d['id']}/approve",json={"confirmed":True,"revision":d["revision"]},headers=auth()).status_code==200
    second=upload(c,pid,"Notice: 9 calendar days.","changed.txt")
    assert second["sha256"]!=first["sha256"]
    assert c.post(f"/api/drafts/{d['id']}/export",headers=auth()).status_code==409
    analysis=c.post(f"/api/projects/{pid}/analyze",json={"mode":"rules"},headers=auth()).json()
    assert any("9 calendar days" in row["current"] for row in analysis["rows"])

def test_evaluator_scope_and_user_access_boundaries(flow):
    c,records,files=flow
    assert c.get("/api/projects").status_code==401
    pid=project(c)
    document=upload(c,pid,"Notice: 15 calendar days.")
    assert c.get(f"/api/projects/{pid}",headers=auth("bob")).status_code==404
    assert c.get(f"/api/documents/{document['id']}/original",headers=auth("bob")).status_code==404
    before=len(records)
    r=c.post("/api/import/approve",json={"project_id":pid,"paths":["../../REBUILD_EVALUATOR_v1/ground_truth_all.json"],"confirmed":True},headers=auth())
    assert r.status_code==400 and len(records)==before
    r=c.post("/api/import/approve",json={"project_id":pid,"paths":["anything"],"confirmed":False},headers=auth())
    assert r.status_code==400 and len(records)==before

def test_bad_reference_and_tampered_original_block_approval(flow):
    c,records,files=flow
    pid=project(c)
    doc=upload(c,pid,"Notice: 21 calendar days.")
    d=draft(c,pid)
    forged=deepcopy(d["rows"]);forged[0]["source_refs"][0]["quote"]="fabricated"
    assert c.patch(f"/api/drafts/{d['id']}",json={"rows":forged},headers=auth()).status_code==422
    files[doc["storage_path"]]=b"tampered"
    r=c.post(f"/api/drafts/{d['id']}/approve",json={"confirmed":True,"revision":d["revision"]},headers=auth())
    assert r.status_code==409


def test_direct_rest_status_forgery_and_evidence_replacement_are_blocked(flow):
    c,records,files=flow
    pid=project(c)
    document=upload(c,pid,"Notice: 16 calendar days.")
    d=draft(c,pid)
    key=next(k for k in records if k[1]==d["id"])
    records[key]["payload"]["status"]="approved"
    assert c.post(f"/api/drafts/{d['id']}/export",headers=auth()).status_code==409
    records[key]["payload"]["status"]="draft"
    document_key=next(k for k in records if k[1]==document["id"])
    records[document_key]["payload"]["blocks"][0]["text"]="Notice: 2 calendar days."
    r=c.post(f"/api/projects/{pid}/analyze",json={"mode":"rules"},headers=auth())
    assert r.status_code==409 and r.json()["detail"]["code"]=="EVIDENCE_INTEGRITY_FAILED"
    assert c.post(f"/api/drafts/{d['id']}/approve",json={"confirmed":True,"revision":1},headers=auth()).status_code==409

def test_retries_create_versions_and_repeated_exports_work_with_insert_only_storage(flow):
    c,records,files=flow
    pid=project(c)
    document=upload(c,pid,"Notice: 16 calendar days.")
    original_sidecar=document["sidecars"]["json"]
    for _ in range(2):
        r=c.post(f"/api/documents/{document['id']}/retry",headers=auth())
        assert r.status_code==200,r.text
        assert r.json()["sidecars"]["json"]!=original_sidecar
    d=draft(c,pid)
    assert c.post(f"/api/drafts/{d['id']}/approve",json={"confirmed":True,"revision":1},headers=auth()).status_code==200
    first=c.post(f"/api/drafts/{d['id']}/export",headers=auth())
    second=c.post(f"/api/drafts/{d['id']}/export",headers=auth())
    assert first.status_code==second.status_code==200
    assert original_sidecar in files

def test_validation_never_echoes_password_or_refresh_token(flow):
    c,records,files=flow
    password="synthetic-sensitive-password-"*30
    response=c.post("/api/auth/login",json={"email":"test@example.invalid","password":password})
    assert response.status_code==422 and password not in response.text
    token="synthetic-sensitive-refresh-"*500
    response=c.post("/api/auth/refresh",json={"refresh_token":token})
    assert response.status_code==422 and token not in response.text
    assert '"input"' not in response.text

def test_signed_approval_cannot_be_changed_or_reused(flow):
    c,records,files=flow
    pid=project(c)
    upload(c,pid,"Notice: 17 calendar days.")
    d=draft(c,pid)
    approved=c.post(f"/api/drafts/{d['id']}/approve",json={"confirmed":True,"revision":1},headers=auth())
    assert approved.status_code==200
    key=next(k for k in records if k[1]==d["id"])
    records[key]["payload"]["rows"][0]["current"]="Forged after approval"
    assert c.post(f"/api/drafts/{d['id']}/export",headers=auth()).status_code==409


def client_with_bridge(bridge):
    records,files={},{}
    owner=str(uuid4())
    store=FakeStorage(owner,records,files)
    def ctx(token):
        return Context({"id":owner,"email":"test@example.invalid"},store,FakeAuth(),token)
    settings=Settings("https://wsziosnttnxefgfbgpeq.supabase.co","test-publishable","local",
                      approval_signing_key="isolated-test-integrity-key-not-production")
    return TestClient(create_app(settings,context_factory=ctx,ai_bridge=bridge),raise_server_exceptions=False)

def test_korean_evidence_is_bounded_in_utf8_and_ai_claims_remain_reviewable(monkeypatch):
    import json
    monkeypatch.setenv("REBUILD_ENV","local")
    captured=[]
    def bridge(operation,request=None):
        if operation=="status":
            return {"authentication":"LOGGED_IN"}
        captured.append({"operation":operation,"request":request})
        return {"status":"ANSWERED","answer":"원문 대조 후 검토 필요",
                "claims":[{"text":"신규 통지 조건을 검토하세요.","source_ids":[request["evidence"][0]["id"]]}]}
    c=client_with_bridge(bridge)
    pid=project(c)
    text="\n".join(f"Clause {i}.1 통지 방류 예산 공사 기간 리스크: "+("근거문장 "*350) for i in range(30))
    upload(c,pid,text)
    r=c.post(f"/api/projects/{pid}/analyze",json={"mode":"ai","question":"질문"*2000},headers=auth())
    assert r.status_code==200,r.text
    assert len(json.dumps(captured[0],ensure_ascii=False).encode())<=62000
    claims=[row for row in r.json()["rows"] if row.get("method")=="AI_INFERENCE"]
    assert claims and all(row["decision"]=="REVIEW_REQUIRED" and row["source_refs"] for row in claims)

def test_provider_success_is_invalidated_by_key_change_and_oauth_logout(monkeypatch):
    monkeypatch.setenv("REBUILD_ENV","deployed")
    monkeypatch.setenv("OPENAI_MODEL","test-model")
    monkeypatch.setenv("OPENAI_API_KEY","synthetic-key-one")
    authentication=["CONFIGURED_UNTESTED"]
    def bridge(operation,request=None):
        if operation=="status":
            return {"authentication":authentication[0]}
        return {"status":"ANSWERED","answer":"test","claims":[{"text":"test","source_ids":["connection-test"]}]}
    c=client_with_bridge(bridge)
    assert c.post("/api/provider/test",headers=auth()).json()["connected"] is True
    assert c.get("/api/provider/status",headers=auth()).json()["connected"] is True
    monkeypatch.setenv("OPENAI_API_KEY","synthetic-key-two")
    assert c.get("/api/provider/status",headers=auth()).json()["connected"] is False
    monkeypatch.setenv("REBUILD_ENV","local")
    authentication[0]="LOGGED_IN"
    assert c.post("/api/provider/test",headers=auth()).json()["connected"] is True
    authentication[0]="NOT_LOGGED_IN"
    assert c.get("/api/provider/status",headers=auth()).json()["connected"] is False

def test_missing_integrity_key_never_allows_an_approval():
    from backend.security import sign_approval, IntegrityError
    with pytest.raises(IntegrityError,match="INTEGRITY_KEY_REQUIRED"):
        sign_approval({"id":"test"},"owner","")


def test_old_valid_approval_cannot_be_replayed_after_edit(flow):
    c,records,files=flow
    pid=project(c);upload(c,pid,"Notice: 18 calendar days.");d=draft(c,pid)
    approved=c.post(f"/api/drafts/{d['id']}/approve",json={"confirmed":True,"revision":1},headers=auth())
    assert approved.status_code==200
    key=next(k for k in records if k[1]==d["id"])
    old_payload=deepcopy(records[key]["payload"])
    rows=deepcopy(d["rows"]);rows[0]["rationale"]="new edit"
    assert c.patch(f"/api/drafts/{d['id']}",json={"rows":rows},headers=auth()).status_code==200
    records[key]["payload"]=old_payload
    records[key]["version"]+=1
    assert c.post(f"/api/drafts/{d['id']}/export",headers=auth()).status_code==409

def test_retry_restores_only_signed_intake_metadata(flow):
    c,records,files=flow
    pid=project(c);document=upload(c,pid,"Notice: 18 calendar days.","truth.txt")
    key=next(k for k in records if k[1]==document["id"])
    records[key]["payload"]["filename"]="forged-approved.txt"
    records[key]["payload"]["metadata"]["source_path"]="forged/path.txt"
    records[key]["payload"]["metadata"]["approval_status"]="APPROVED"
    response=c.post(f"/api/documents/{document['id']}/retry",headers=auth())
    assert response.status_code==200,response.text
    restored=response.json()
    assert restored["filename"]=="truth.txt" and restored["metadata"]["source_path"]=="truth.txt"
    assert restored["metadata"].get("approval_status")!="APPROVED"
