"""RE:Build Agent product API. All durable data lives behind Supabase user RLS."""
from dataclasses import dataclass, asdict, is_dataclass
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Literal
from urllib.parse import quote
from uuid import uuid4
import json
import mimetypes
import re
from tempfile import TemporaryDirectory

from fastapi import FastAPI, Depends, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, ConfigDict

from .config import Settings, ROOT, INPUT_ROOT, TEMPLATE_ROOT
from .analysis import compare, fingerprint, knowledge_graph, search_documents, validate_refs
from .ai import AIError, call_bridge, provider_configuration, configuration_revision
from .auth import SupabaseAuth
from .storage import SupabaseStore, NotFoundError
from .extraction import extract_document
from .exports import build_output
from .drafts import build_slide_rows, validate_slide_rows
from .templates import TemplateCatalog, TemplateError
from .security import IntegrityError, APPROVAL_FIELDS, sign_document, verify_document, sign_approval, verify_approval, seal_intake, restore_intake

PRODUCT = "RE:Build Agent"
SLIDE_ERROR_MESSAGES = {
    "SLIDE_CONTENT_TOO_LONG": "심의장표 본문의 분량이 한 장의 표시 한도를 넘었습니다. 핵심 내용·결정·검토 의견을 줄여 다시 저장하세요.",
    "SLIDE_TITLE_TOO_LONG": "심의장표 제목의 분량이 표시 한도를 넘었습니다. 제목을 줄여 다시 저장하세요.",
    "FIVE_SLIDE_SECTIONS_REQUIRED": "심의장표는 정해진 다섯 장 구성이 필요합니다.",
}
TEMPLATES = {
    "itb": ("ITB_Analysis_Template.xlsx", "ITB 분석표", True),
    "risk": ("Risk_Register_Template.xlsx", "Risk Register", True),
    "slides": ("Review_Deck_Template.pptx", "심의장표", True),
    "contract": ("Contract_Review_Template.docx", "계약 검토", False),
    "onepager": ("Custom_Committee_OnePager.docx", "심의 요약", False),
    "lessons": ("Lessons_Learned_Template.docx", "Lessons Learned", False),
    "comparison": ("Project_Comparison_Template.xlsx", "프로젝트 비교", False),
}
SUPPORTED = {".docx", ".pptx", ".xlsx", ".pdf", ".md", ".txt", ".csv", ".eml"}
MIME = {".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
def now():
    return datetime.now(timezone.utc).isoformat()

def fail(code, message, status=400):
    raise HTTPException(status, detail={"code": code, "message": message})

def unwrap(entity):
    if entity is None:
        return None
    return {**entity.get("payload", {}), **{key: entity[key] for key in
            ("id", "kind", "project_id", "version", "created_at", "updated_at") if key in entity}}

def entity_payload(entity):
    return {k: v for k, v in entity.items() if k not in {"version", "updated_at"}}

def to_dict(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return vars(value)

@dataclass
class Context:
    user: dict
    store: object
    auth: object
    token: str

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
class Login(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)
class Refresh(StrictModel):
    refresh_token: str = Field(min_length=1, max_length=10000)
class NewProject(StrictModel):
    name: str = Field(min_length=1, max_length=150)
    kind: Literal["current", "historical"] = "current"
class ImportApproval(StrictModel):
    project_id: str
    paths: list[str] = Field(min_length=1, max_length=100)
    confirmed: bool
class Analyze(StrictModel):
    mode: Literal["rules", "ai"] = "rules"
    question: str = Field(default="", max_length=4000)
class DraftRequest(Analyze):
    kind: Literal["itb", "risk", "slides"]
    template_id: str | None = None
    template_version: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
class DraftEdit(StrictModel):
    rows: list[dict] = Field(max_length=100)
    template_id: str | None = None
    template_version: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    revision: int | None = None
class Approval(StrictModel):
    confirmed: bool
    revision: int
class Profile(StrictModel):
    type: Literal["corporate_llm", "sso", "provider"]
    name: str = Field(default="", max_length=100)
    protocol: str = Field(default="", max_length=40)
    endpoint: str = Field(default="", max_length=500)
    model: str = Field(default="", max_length=120)

class ProfileEdit(Profile):
    version: int = Field(ge=1)
class ProjectProviderSelection(StrictModel):
    profile_id: str | None = Field(default=None, max_length=100)
    version: int = Field(ge=1)


def create_app(settings=None, context_factory=None, ai_bridge=call_bridge):
    settings = settings or Settings.from_environment()
    app = FastAPI(title=PRODUCT, docs_url=None, redoc_url=None)
    app.state.settings = settings

    @app.middleware("http")
    async def response_headers(request: Request, call_next):
        # No CORS: local OAuth service is only reachable from its own origin.
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": {"code": "ORIGIN_REJECTED", "message": "동일 출처 요청만 허용합니다."}}, 403)
        if settings.environment in {"local", "demo"} and request.url.hostname not in {"127.0.0.1", "localhost", "::1", "testserver"}:
            return JSONResponse({"detail": {"code": "LOCAL_ONLY", "message": "로컬 전용 환경입니다."}}, 403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; frame-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        fields = [".".join(str(x) for x in item.get("loc", []) if isinstance(x, (str, int)))
                  for item in error.errors()]
        return JSONResponse({"detail": {"code": "INVALID_REQUEST",
                            "message": "입력 형식 또는 길이를 확인하세요.", "fields": fields}}, 422)

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        # Never serialize third-party exception messages (may contain headers/URLs).
        code = getattr(error, "code", "")
        if code in {"VERSION_CONFLICT", "STALE_VERSION", "CONFLICT"}:
            return JSONResponse({"detail": {"code": "VERSION_CONFLICT", "message": "다른 변경이 있습니다. 새로고침 후 다시 시도하세요."}}, 409)
        return JSONResponse({"detail": {"code": "SERVICE_UNAVAILABLE", "message": "저장 또는 인증 서비스 요청에 실패했습니다. 기존 데이터는 보존됩니다."}}, 503)

    def context(authorization: str | None = Header(default=None)):
        if not authorization or not authorization.startswith("Bearer ") or len(authorization) > 10000:
            fail("AUTH_REQUIRED", "로그인이 필요합니다.", 401)
        token = authorization[7:]
        if context_factory:
            yield context_factory(token)
            return
        auth = store = None
        try:
            try:
                settings.validate()
                auth = SupabaseAuth(settings.supabase_url, settings.publishable_key)
                user = to_dict(auth.get_user(token))
            except Exception:
                fail("SESSION_INVALID", "로그인 세션이 만료되었거나 인증 서버에 연결할 수 없습니다.", 401)
            store = SupabaseStore(settings.supabase_url, settings.publishable_key, token)
            yield Context(user, store, auth, token)
        finally:
            if hasattr(store, "close"):
                store.close()
            if hasattr(auth, "close"):
                auth.close()

    def save(ctx, kind, payload, project_id=None, expected_version=None):
        return unwrap(ctx.store.save(kind, payload["id"], project_id, entity_payload(payload), expected_version=expected_version))

    def get(ctx, eid, kind):
        entity = unwrap(ctx.store.get(eid))
        if not entity or entity.get("kind") != kind:
            fail("NOT_FOUND", "접근 가능한 항목이 없습니다.", 404)
        return entity

    def list_entities(ctx, kind, project_id=None):
        return [unwrap(e) for e in ctx.store.list(kind, project_id=project_id)]

    def event(ctx, action, project_id=None, **details):
        save(ctx, "event", {"id": str(uuid4()), "action": action, "at": now(), **details}, project_id)

    def inputs(ctx, project_id):
        get(ctx, project_id, "project")
        projects = list_entities(ctx, "project")
        past_ids = {p["id"] for p in projects if p.get("project_kind", "current") == "historical" and p["id"] != project_id}
        docs = list_entities(ctx, "document")
        current = [d for d in docs if d.get("project_id") == project_id]
        past = [d for d in docs if d.get("project_id") in past_ids]
        for document in current + past:
            try:
                verify_document(document, ctx.user["id"], settings.approval_signing_key)
            except IntegrityError as e:
                fail(str(e), "등록된 근거의 무결성을 확인할 수 없습니다. 원본 재처리가 필요합니다.", 409)
        return current, past, projects

    def invalidate(ctx, project_id, reason):
        projects = list_entities(ctx, "project")
        is_historical = any(p["id"] == project_id and p.get("project_kind") == "historical" for p in projects)
        for draft in list_entities(ctx, "draft"):
            if draft.get("status") == "approved" and (is_historical or draft.get("project_id") == project_id):
                history = draft.get("approval_history", [])
                history.append({"approved_at": draft.get("approved_at"), "revision": draft["revision"],
                                "invalidated_at": now(), "reason": reason})
                draft.update(status="draft", approval_history=history, approved_at=None, reviewer=None)
                save(ctx, "draft", draft, draft["project_id"], draft["version"])

    def template_info(tid):
        if tid not in TEMPLATES:
            fail("TEMPLATE_NOT_FOUND", "표준 양식을 찾을 수 없습니다.", 404)
        filename, title, supported = TEMPLATES[tid]
        path = TEMPLATE_ROOT / filename
        if not path.is_file():
            fail("TEMPLATE_UNAVAILABLE", "원본 양식이 없습니다.", 503)
        data = path.read_bytes()
        return {"id": tid, "name": title, "filename": filename, "sha256": sha256(data).hexdigest(),
                "version": sha256(data).hexdigest()[:12], "generation_supported": supported,
                "source_path": "data/REBUILD_INPUT_v1/REBUILD_INPUT_v1/03_OUTPUT_TEMPLATES/" + filename,
                "size": len(data)}

    def template_catalog(ctx):
        provided = {tid: (template_info(tid), TEMPLATE_ROOT / spec[0]) for tid, spec in TEMPLATES.items()}
        return TemplateCatalog(ctx.store, ctx.user["id"], settings.approval_signing_key, provided)

    def resolve_template(ctx, tid, version=None, persist=False):
        try:
            return template_catalog(ctx).resolve(tid, version, persist)
        except TemplateError as error:
            fail(str(error), "선택한 양식 버전을 확인할 수 없습니다.", 404 if str(error).endswith("NOT_FOUND") else 409)

    def template_for(ctx, kind, tid, version=None):
        tid = tid or kind
        if tid != kind:
            fail("TEMPLATE_TYPE_MISMATCH", "출력 종류에 맞는 표준 양식을 선택하세요.")
        return resolve_template(ctx, tid, version, persist=True)[0]

    def original_bytes(ctx, document):
        try:
            trusted = restore_intake(document, ctx.user["id"], settings.approval_signing_key)
        except IntegrityError as e:
            fail(str(e), "원본 인입 기록의 무결성을 확인할 수 없습니다.", 409)
        data = ctx.store.download_bytes(trusted["storage_path"])
        if sha256(data).hexdigest() != trusted["sha256"]:
            fail("ORIGINAL_HASH_MISMATCH", "저장된 원본의 해시가 다릅니다. 검토가 필요합니다.", 409)
        return data

    def convert(ctx, document, data):
        try:
            document = restore_intake(document, ctx.user["id"], settings.approval_signing_key)
        except IntegrityError as e:
            fail(str(e), "서명된 인입 기록이 필요합니다.", 409)
        if sha256(data).hexdigest() != document["sha256"]:
            fail("ORIGINAL_HASH_MISMATCH", "원본 해시가 다릅니다.", 409)
        try:
            extracted = extract_document(data, document["filename"], document["id"], document["project_id"])
            result = {**document, **extracted, "storage_path": document["storage_path"], "created_at": document["created_at"]}
            result["metadata"] = {**extracted.get("metadata", {}), **document.get("metadata", {})}
            result["aliases"] = document.get("aliases", [])
        except Exception:
            result = {**document, "extraction_status": "FAILED", "error_code": "EXTRACTION_FAILED",
                      "blocks": [], "markdown": "", "error": "문서를 변환하지 못했습니다. 원본은 저장되어 있으며 재처리할 수 있습니다."}
        result["parser_version"] = "extractor-v1"
        result["extraction_signature"] = sign_document(result, ctx.user["id"], settings.approval_signing_key)
        base = document["storage_path"].rsplit("/", 1)[0] + "/conversion-" + str(document["version"] + 1) + "-" + uuid4().hex[:12]
        ctx.store.upload_bytes(base + "/knowledge.md", result.get("markdown", "").encode("utf-8"), "text/markdown; charset=utf-8")
        ctx.store.upload_bytes(base + "/knowledge.json", json.dumps(result, ensure_ascii=False).encode("utf-8"), "application/json")
        result["sidecars"] = {"markdown": base + "/knowledge.md", "json": base + "/knowledge.json"}
        return save(ctx, "document", result, document["project_id"], document["version"])

    def ingest(ctx, project_id, filename, data, source_path=None):
        get(ctx, project_id, "project")
        filename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
        if not filename or len(filename) > 240 or any(ord(c) < 32 for c in filename):
            fail("INVALID_FILENAME", "유효한 파일명이 필요합니다.")
        digest = sha256(data).hexdigest()
        for doc in list_entities(ctx, "document", project_id):
            if doc.get("sha256") == digest:
                alias = source_path or filename
                if alias not in doc.get("aliases", []):
                    doc.setdefault("aliases", []).append(alias)
                    doc = save(ctx, "document", doc, project_id, doc["version"])
                return {**doc, "duplicate": True}
        document_id = str(uuid4())
        storage_path = f"{ctx.user['id']}/{project_id}/{document_id}/original{Path(filename).suffix.lower()}"
        # Store original before registration or conversion; retain it on extraction failure.
        ctx.store.upload_bytes(storage_path, data, mimetypes.guess_type(filename)[0] or "application/octet-stream")
        payload = {"id": document_id, "project_id": project_id, "filename": filename,
            "sha256": digest, "size": len(data), "storage_path": storage_path, "created_at": now(),
            "extraction_status": "STORED", "blocks": [], "markdown": "", "revision": None,
            "approval_status": "UNKNOWN", "metadata": {"source_path": source_path or filename},
            "aliases": [source_path or filename]}
        seal_intake(payload, ctx.user["id"], settings.approval_signing_key)
        doc = save(ctx, "document", payload, project_id)
        invalidate(ctx, project_id, "새 입력 또는 문서 버전 추가")
        result = convert(ctx, doc, data)
        event(ctx, "document_ingested", project_id, document_id=document_id, sha256=digest,
              extraction_status=result["extraction_status"])
        return {**result, "duplicate": False}

    def file_response(data, filename, mime=None):
        return Response(data, media_type=mime or mimetypes.guess_type(filename)[0] or "application/octet-stream",
                        headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(filename)})

    @app.get("/api/health")
    def health():
        return {"product": PRODUCT, "status": "running", "persistence": "supabase", "environment": settings.environment}

    @app.get("/api/config")
    def config():
        return {"product": PRODUCT, "supabase_url": settings.supabase_url, "publishable_key": settings.publishable_key,
                "provider": provider_configuration(), "upload_limit_bytes": settings.upload_limit}

    @app.post("/api/auth/login")
    def login(body: Login):
        auth = None
        try:
            settings.validate()
            auth = SupabaseAuth(settings.supabase_url, settings.publishable_key)
            session = to_dict(auth.login(body.email, body.password))
            # Only this authentication response carries the session token; no tokens in logs.
            return session
        except Exception:
            fail("LOGIN_FAILED", "로그인에 실패했습니다. 계정 정보와 Supabase 연결을 확인하세요.", 401)
        finally:
            if auth and hasattr(auth, "close"):
                auth.close()

    @app.post("/api/auth/refresh")
    def refresh_session(body: Refresh):
        auth = None
        try:
            settings.validate()
            auth = SupabaseAuth(settings.supabase_url, settings.publishable_key)
            return to_dict(auth.refresh(body.refresh_token))
        except Exception:
            fail("SESSION_EXPIRED", "세션을 갱신할 수 없습니다. 다시 로그인하세요.", 401)
        finally:
            if auth and hasattr(auth, "close"):
                auth.close()

    @app.get("/api/auth/me")
    def me(ctx=Depends(context)):
        return {"id": ctx.user["id"], "email": ctx.user.get("email")}

    @app.post("/api/auth/logout")
    def logout(ctx=Depends(context)):
        ctx.auth.logout(ctx.token)
        return {"logged_out": True}

    @app.get("/api/projects")
    def projects(ctx=Depends(context)):
        return [{**p, "kind": p.get("project_kind", "current")} for p in list_entities(ctx, "project")]

    @app.post("/api/projects", status_code=201)
    def new_project(body: NewProject, ctx=Depends(context)):
        if not body.name.strip():
            fail("PROJECT_NAME_REQUIRED", "프로젝트 이름을 입력하세요.")
        p = save(ctx, "project", {"id": str(uuid4()), "name": body.name.strip(), "project_kind": body.kind, "created_at": now()})
        event(ctx, "project_created", p["id"])
        return {**p, "kind": p["project_kind"]}

    @app.get("/api/projects/{pid}")
    def project(pid: str, ctx=Depends(context)):
        p = get(ctx, pid, "project")
        return {**p, "kind": p.get("project_kind", "current")}

    @app.get("/api/projects/{pid}/documents")
    def documents(pid: str, ctx=Depends(context)):
        get(ctx, pid, "project")
        return list_entities(ctx, "document", pid)

    @app.post("/api/projects/{pid}/upload")
    async def upload(pid: str, files: list[UploadFile] = File(...), ctx=Depends(context)):
        get(ctx, pid, "project")
        if not 1 <= len(files) <= 20:
            fail("UPLOAD_COUNT_LIMIT", "한 번에 1~20개 파일을 선택하세요.")
        results = []
        for uploaded in files:
            data = await uploaded.read(settings.upload_limit + 1)
            await uploaded.close()
            if len(data) > settings.upload_limit:
                results.append({"filename": uploaded.filename, "error_code": "FILE_TOO_LARGE", "extraction_status": "REJECTED",
                                "error": "파일 크기가 20MB 제한을 초과했습니다."})
                continue
            if not data:
                results.append({"filename": uploaded.filename, "error_code": "EMPTY_FILE", "extraction_status": "REJECTED"})
                continue
            results.append(await run_in_threadpool(ingest, ctx, pid, uploaded.filename or "document", data))
        return {"documents": results}

    @app.get("/api/documents/{did}/original")
    def original(did: str, ctx=Depends(context)):
        doc = get(ctx, did, "document")
        ext = Path(doc["filename"]).suffix.lower()
        safe_mime = "application/pdf" if ext == ".pdf" else "text/plain" if ext in {".txt", ".md", ".csv", ".eml"} else "application/octet-stream"
        return file_response(original_bytes(ctx, doc), doc["filename"], safe_mime)

    @app.get("/api/documents/{did}/knowledge")
    def knowledge(did: str, ctx=Depends(context)):
        return get(ctx, did, "document")

    @app.post("/api/documents/{did}/retry")
    def retry(did: str, ctx=Depends(context)):
        doc = get(ctx, did, "document")
        invalidate(ctx, doc["project_id"], "문서 재처리")
        result = convert(ctx, doc, original_bytes(ctx, doc))
        event(ctx, "document_reprocessed", doc["project_id"], document_id=did)
        return result

    def candidates():
        result = []
        for folder in ("01_PAST_PROJECTS", "02_NEW_PROJECTS"):
            root = INPUT_ROOT / folder
            if not root.is_dir():
                continue
            for p in sorted(root.rglob("*")):
                resolved = p.resolve()
                if p.is_file() and not p.is_symlink() and resolved.is_relative_to(root.resolve()) and p.suffix.lower() in SUPPORTED:
                    result.append({"path": p.relative_to(INPUT_ROOT).as_posix(), "filename": p.name,
                                   "size": p.stat().st_size, "project_folder": p.parent.name, "kind": "historical" if folder.startswith("01") else "current"})
        return result

    @app.get("/api/import/candidates")
    def import_candidates(ctx=Depends(context)):
        return {"candidates": candidates(), "confirmation_required": True}

    @app.post("/api/import/approve")
    def import_approved(body: ImportApproval, ctx=Depends(context)):
        if not body.confirmed:
            fail("IMPORT_APPROVAL_REQUIRED", "등록할 원본 목록을 확인하고 승인하세요.")
        get(ctx, body.project_id, "project")
        allowed = {c["path"]: c for c in candidates()}
        if any(p not in allowed for p in body.paths):
            fail("IMPORT_PATH_REJECTED", "승인 가능한 INPUT 목록 밖의 경로입니다.")
        result = []
        event(ctx, "folder_import_approved", body.project_id, paths=body.paths)
        for rel in dict.fromkeys(body.paths):
            path = (INPUT_ROOT / rel).resolve()
            if not path.is_relative_to(INPUT_ROOT.resolve()) or path.stat().st_size > settings.upload_limit:
                fail("IMPORT_PATH_REJECTED", "허용된 경로 또는 파일 크기를 벗어났습니다.")
            result.append(ingest(ctx, body.project_id, path.name, path.read_bytes(), rel))
        return {"documents": result}

    @app.get("/api/search")
    def search(q: str = "", project_id: str | None = None, scope: Literal["all", "current", "historical"] = "all", ctx=Depends(context)):
        if project_id:
            cur, past, _ = inputs(ctx, project_id)
            docs = cur if scope == "current" else past if scope == "historical" else cur + past
        else:
            docs = list_entities(ctx, "document")
        return {"items": search_documents(docs, q[:4000]), "mode": "search", "ai_used": False,
                "limitations": "키워드 원문 일치 검색입니다. 의미 유사도나 적용 확률을 표시하지 않습니다."}

    def provider_selection(ctx, pid):
        selected_project = get(ctx, pid, "project")
        return {"project_version": selected_project["version"], "profile_id": selected_project.get("provider_profile_id")}

    def verify_provider_selection(ctx, pid, snapshot):
        if snapshot != provider_selection(ctx, pid):
            fail("PROVIDER_CONFIGURATION_CHANGED", "분석 중 프로젝트의 AI 구성이 변경됐습니다. 현재 설정을 확인하고 다시 실행하세요.", 409)

    def analysis_result(ctx, pid, body):
        selected_project = get(ctx, pid, "project")
        selection = {"project_version": selected_project["version"], "profile_id": selected_project.get("provider_profile_id")}
        if body.mode == "ai" and selected_project.get("provider_profile_id"):
            get_profile(ctx, selected_project["provider_profile_id"])
            fail("PROFILE_NOT_CONNECTED", "선택한 사내 구성은 아직 연결되지 않았습니다. 설정에서 기본 OpenAI로 변경하거나 규칙 비교를 사용하세요.", 503)
        cur, past, _ = inputs(ctx, pid)
        result = compare(cur, past)
        result["input_fingerprint"] = fingerprint(cur + past)
        if body.mode == "ai":
            evidence, seen, ref_map = [], set(), {}
            question = body.question or "신규 프로젝트 조건과 과거 근거를 비교하고 적용 조건과 불확실성을 설명하세요."
            for row in result["rows"]:
                for ref in row["source_refs"]:
                    sid = ref["source_id"]
                    if sid in seen or len(evidence) >= 25:
                        continue
                    scope = "현재 프로젝트" if ref["project_id"] == pid else "과거 사례"
                    candidate = {"id": sid, "text": ref["quote"][:1800],
                        "location": (scope + " | " + str(ref.get("revision")) + " | " + str(ref.get("approval_status")) +
                                     " | " + ref["filename"] + " / " + str(ref["locator"]))[:500]}
                    candidate_request = {"operation": "analyze", "request": {"question": question, "evidence": evidence + [candidate]}}
                    if len(json.dumps(candidate_request, ensure_ascii=False).encode("utf-8")) > 62000:
                        continue
                    seen.add(sid)
                    ref_map[sid] = ref
                    evidence.append(candidate)
            if not evidence:
                fail("EVIDENCE_REQUIRED", "AI 검토에 사용할 원문 근거가 없습니다.", 422)
            verify_provider_selection(ctx, pid, selection)
            try:
                answer = ai_bridge("analyze", {"question": question, "evidence": evidence})
            except AIError as error:
                fail(error.code, "AI 연결 또는 호출에 실패했습니다. 규칙 비교로 자동 전환하지 않습니다.", 503)
            verify_provider_selection(ctx, pid, selection)
            result["provider_selection"] = selection
            for index, claim in enumerate(answer.get("claims", [])):
                refs = [ref_map[sid] for sid in claim["source_ids"] if sid in ref_map]
                result["rows"].append({"id": f"ai-{index+1}", "title": "AI 적용 검토", "current": "", "past": "",
                    "differences": [], "decision": "REVIEW_REQUIRED", "rationale": claim["text"],
                    "missing_information": ["AI 해석을 원문과 대조하여 검토하세요."], "source_refs": refs,
                    "current_refs": [ref for ref in refs if ref["project_id"] == pid],
                    "historical_refs": [ref for ref in refs if ref["project_id"] != pid],
                    "severity": None, "mitigation": "", "method": "AI_INFERENCE"})
            result.update(mode="ai", ai_used=True, ai_insight=answer, answer=answer.get("answer"), provider=provider_configuration())
        event(ctx, "analysis_completed", pid, mode=body.mode, input_fingerprint=result["input_fingerprint"],
              execution=result.get("ai_insight", {}).get("execution"),
              usage=result.get("ai_insight", {}).get("usage"))
        return result

    @app.post("/api/projects/{pid}/analyze")
    def analyze(pid: str, body: Analyze, ctx=Depends(context)):
        return analysis_result(ctx, pid, body)

    @app.get("/api/projects/{pid}/knowledge")
    def graph(pid: str, ctx=Depends(context)):
        cur, past, projects = inputs(ctx, pid)
        return knowledge_graph(compare(cur, past), cur + past, projects)

    @app.get("/api/templates")
    def templates(ctx=Depends(context)):
        catalog = template_catalog(ctx)
        return [{**template_info(tid), "kind": tid, "versions": catalog.versions(tid)} for tid in TEMPLATES]

    @app.get("/api/templates/{tid}/original")
    def template_download(tid: str, version: str | None = None, ctx=Depends(context)):
        info, data = resolve_template(ctx, tid, version)
        return file_response(data, info["filename"])

    @app.post("/api/templates/{tid}/versions", status_code=201)
    async def register_template(tid: str, file: UploadFile = File(...), ctx=Depends(context)):
        template_info(tid)
        data = await file.read(settings.upload_limit + 1)
        await file.close()
        if not data or len(data) > settings.upload_limit:
            fail("TEMPLATE_SIZE_INVALID", "양식 파일 크기를 확인하세요.", 413)
        try:
            info = await run_in_threadpool(template_catalog(ctx).register, tid, file.filename or "", data)
        except TemplateError as error:
            message = ("심의장표는 제공 양식과 같은 가로형 슬라이드 크기가 필요합니다. 원본 양식의 크기를 유지하세요."
                       if str(error) == "SLIDE_TEMPLATE_SIZE_UNSUPPORTED"
                       else "제공 양식의 항목 구조를 유지한 유효한 파일을 선택하세요.")
            fail(str(error), message, 422)
        event(ctx, "template_version_registered", template_id=tid, template_sha256=info["sha256"])
        return info

    @app.get("/api/projects/{pid}/drafts")
    def drafts(pid: str, ctx=Depends(context)):
        get(ctx, pid, "project")
        return [{**item, "kind": item["output_kind"]} for item in list_entities(ctx, "draft", pid)]

    @app.post("/api/projects/{pid}/drafts", status_code=201)
    def create_draft(pid: str, body: DraftRequest, ctx=Depends(context)):
        info = template_for(ctx, body.kind, body.template_id, body.template_version)
        result = analysis_result(ctx, pid, body)
        cur, past, _ = inputs(ctx, pid)
        if result["input_fingerprint"] != fingerprint(cur + past):
            fail("INPUT_CHANGED", "분석 중 입력 자료가 변경됐습니다. 최신 자료로 다시 생성하세요.", 409)
        draft_rows = build_slide_rows(result["rows"]) if body.kind == "slides" else result["rows"]
        if body.mode == "ai":
            verify_provider_selection(ctx, pid, result["provider_selection"])
        draft = save(ctx, "draft", {"id": str(uuid4()), "project_id": pid, "output_kind": body.kind, "type": body.kind,
            "title": info["name"], "revision": 1, "status": "draft", "created_at": now(), "rows": draft_rows,
            "provider_selection": result.get("provider_selection"),
            "mode": result["mode"], "ai_used": result["ai_used"], "ai_insight": result.get("ai_insight"),
            "template_id": info["id"], "template_version": info["sha256"], "template_sha256": info["sha256"],
            "input_fingerprint": fingerprint(cur + past, info["sha256"]), "approval_history": [],
            "product": PRODUCT}, pid)
        event(ctx, "draft_created", pid, draft_id=draft["id"], revision=1)
        return {**draft, "kind": draft["output_kind"]}

    @app.get("/api/drafts/{did}")
    def draft_detail(did: str, ctx=Depends(context)):
        draft = get(ctx, did, "draft")
        return {**draft, "kind": draft["output_kind"]}

    @app.patch("/api/drafts/{did}")
    def edit_draft(did: str, body: DraftEdit, ctx=Depends(context)):
        draft = get(ctx, did, "draft")
        if body.revision is not None and body.revision != draft["revision"]:
            fail("VERSION_CONFLICT", "초안이 변경되었습니다. 새로고침 후 다시 검토하세요.", 409)
        cur, past, _ = inputs(ctx, draft["project_id"])
        try:
            if draft["output_kind"] == "slides":
                validate_slide_rows(body.rows)
            validate_refs(body.rows, cur + past)
        except ValueError as e:
            message = SLIDE_ERROR_MESSAGES.get(str(e), "유효하지 않은 원문 근거가 있습니다.")
            fail(str(e), message, 422)
        info = template_for(ctx, draft["output_kind"], body.template_id or draft["template_id"], body.template_version or draft.get("template_version") or draft["template_sha256"])
        if draft["status"] == "approved":
            draft.setdefault("approval_history", []).append({"approved_at": draft.get("approved_at"),
                "revision": draft["revision"], "invalidated_at": now(), "reason": "초안 또는 양식 변경"})
        draft.update(rows=body.rows, revision=draft["revision"] + 1, status="draft", approved_at=None, reviewer=None,
                     template_id=info["id"], template_version=info["sha256"], template_sha256=info["sha256"],
                     input_fingerprint=fingerprint(cur + past, info["sha256"]))
        saved = save(ctx, "draft", draft, draft["project_id"], draft["version"])
        event(ctx, "draft_edited", draft["project_id"], draft_id=did, revision=saved["revision"])
        return {**saved, "kind": saved["output_kind"]}

    def verify_draft(ctx, draft, verify_originals=False):
        info, _ = resolve_template(ctx, draft["template_id"], draft.get("template_version") or draft["template_sha256"])
        cur, past, _ = inputs(ctx, draft["project_id"])
        if draft["template_sha256"] != info["sha256"] or draft["input_fingerprint"] != fingerprint(cur + past, info["sha256"]):
            fail("DRAFT_STALE", "입력 또는 양식이 변경됐습니다. 초안을 갱신하고 재승인하세요.", 409)
        try:
            if draft["output_kind"] == "slides":
                validate_slide_rows(draft["rows"])
            validate_refs(draft["rows"], cur + past)
        except ValueError as e:
            message = SLIDE_ERROR_MESSAGES.get(str(e), "원문 근거를 검증할 수 없습니다.")
            fail(str(e), message, 409)
        if verify_originals:
            referenced = {r["document_id"] for row in draft["rows"] for field in ("source_refs", "current_refs", "historical_refs") for r in row.get(field, [])}
            for doc in cur + past:
                if doc["id"] in referenced:
                    original_bytes(ctx, doc)
        return info

    @app.post("/api/drafts/{did}/approve")
    def approve_draft(did: str, body: Approval, ctx=Depends(context)):
        draft = get(ctx, did, "draft")
        if not body.confirmed:
            fail("APPROVAL_REQUIRED", "초안과 원문 근거 검토 후 명시적으로 승인하세요.")
        if body.revision != draft["revision"]:
            fail("VERSION_CONFLICT", "승인할 초안 버전이 다릅니다.", 409)
        verify_draft(ctx, draft, verify_originals=True)
        if draft["status"] == "approved":
            try:
                verify_approval(draft, unwrap(ctx.store.get(draft.get("approval_id", ""))), ctx.user["id"], settings.approval_signing_key)
            except IntegrityError as e:
                fail(str(e), "서버 승인 서명을 확인할 수 없습니다.", 409)
            return {**draft, "kind": draft["output_kind"]}
        draft.update(status="approved", approved_at=now(), reviewer=ctx.user["id"], approval_id=str(uuid4()),
                     approved_entity_version=draft["version"] + 1)
        draft["approval_signature"] = sign_approval(draft, ctx.user["id"], settings.approval_signing_key)
        snapshot = {"id": draft["approval_id"], "draft_id": did, "project_id": draft["project_id"],
                    "approval_signature": draft["approval_signature"],
                    "signed_draft": {field: draft.get(field) for field in APPROVAL_FIELDS}}
        result = unwrap(ctx.store.approve(did, draft["version"], entity_payload(draft),
                                        draft["approval_id"], snapshot))
        event(ctx, "draft_approved", draft["project_id"], draft_id=did, revision=draft["revision"], input_fingerprint=draft["input_fingerprint"])
        return {**result, "kind": result["output_kind"]}

    @app.post("/api/drafts/{did}/export")
    def export_draft(did: str, request: Request, ctx=Depends(context)):
        draft = get(ctx, did, "draft")
        if draft["status"] != "approved":
            fail("APPROVAL_REQUIRED", "승인된 초안만 최종 파일로 생성할 수 있습니다.", 409)
        try:
            snapshot = unwrap(ctx.store.get(draft.get("approval_id", "")))
            verify_approval(draft, snapshot, ctx.user["id"], settings.approval_signing_key)
        except (IntegrityError, ValueError) as e:
            fail("APPROVAL_INTEGRITY_FAILED", "유효한 서버 승인과 승인 스냅샷이 필요합니다.", 409)
        info = verify_draft(ctx, draft, verify_originals=True)
        export_copy = deepcopy({**draft, "kind": draft["output_kind"]})
        for row in export_copy["rows"]:
            for field in ("source_refs", "current_refs", "historical_refs", "excluded_refs"):
                for ref in row.get(field, []):
                    ref["url"] = str(request.base_url).rstrip("/") + "/#source=" + quote(ref["document_id"], safe="")
        _, template_bytes = resolve_template(ctx, draft["template_id"], draft.get("template_version") or draft["template_sha256"])
        with TemporaryDirectory(prefix="rebuild-template-") as temporary:
            template_path = Path(temporary) / info["filename"]
            template_path.write_bytes(template_bytes)
            output, mime, extension = build_output(export_copy, template_path)
        # Recheck after generation to close edits that happen while an exporter runs.
        current = get(ctx, did, "draft")
        if current["version"] != draft["version"] or current["status"] != "approved":
            fail("VERSION_CONFLICT", "파일 생성 중 초안이 변경되었습니다.", 409)
        verify_draft(ctx, current)
        name = f"RE_Build_Agent_{draft['output_kind']}_r{draft['revision']}.{extension.lstrip('.')}"
        path = f"{ctx.user['id']}/{draft['project_id']}/{did}/r{draft['revision']}-{sha256(output).hexdigest()[:12]}.{extension.lstrip('.')}"
        try:
            existing = ctx.store.download_bytes(path)
            if sha256(existing).digest() != sha256(output).digest():
                fail("OUTPUT_INTEGRITY_FAILED", "기존 출력 파일의 해시를 확인할 수 없습니다.", 409)
        except NotFoundError:
            ctx.store.upload_bytes(path, output, mime)
        event(ctx, "output_generated", draft["project_id"], draft_id=did, revision=draft["revision"],
              output_sha256=sha256(output).hexdigest(), storage_path=path)
        return file_response(output, name, mime)

    @app.get("/api/management")
    def management(ctx=Depends(context)):
        projects, docs = list_entities(ctx, "project"), list_entities(ctx, "document")
        past_ids = {p["id"] for p in projects if p.get("project_kind") == "historical"}
        arrivals = sorted(docs, key=lambda d: d.get("created_at", ""), reverse=True)
        registered = {alias for d in docs for alias in d.get("aliases", [])}
        # No unapproved conversion: compare only candidate names and sizes here.
        pending = []
        registered_hashes = {alias: d["sha256"] for d in docs for alias in d.get("aliases", [])}
        for candidate in candidates():
            path = candidate["path"]
            # Hashing is change detection only; conversion still requires explicit consent.
            if path not in registered or sha256((INPUT_ROOT / path).read_bytes()).hexdigest() != registered_hashes.get(path):
                pending.append(candidate)
        problematic = [d for d in docs if d.get("extraction_status") not in {"EXTRACTED", "SUCCESS", "COMPLETE", "COMPLETED", "READY", "success", "extracted"}]
        return {"historical_projects": len(past_ids), "historical_documents": sum(d.get("project_id") in past_ids for d in docs),
            "project_count": len(projects), "document_count": len(docs), "new_documents": arrivals[:30],
            "documents": docs, "projects": [{**p, "document_count": sum(d.get("project_id") == p["id"] for d in docs),
                "file_types": sorted({Path(d["filename"]).suffix.lstrip(".").upper() for d in docs if d.get("project_id") == p["id"]})} for p in projects],
            "template_count": len(TEMPLATES), "new_document_count": len(arrivals),
            "checked_at": now(), "scope": "현재 사용자 자료 및 허용된 INPUT 폴더",
            "up_to_date": not pending and not problematic, "unregistered_count": len(pending),
            "message": "최신 상태입니다." if not pending and not problematic else "새로 유입된 자료 또는 확인할 문서가 있습니다."}

    @app.get("/api/provider/status")
    def provider_status(ctx=Depends(context)):
        profiles = list_entities(ctx, "setting")
        configuration = provider_configuration()
        revision = configuration_revision(settings.approval_signing_key)
        matching = [p for p in profiles if p.get("setting_type") == "provider_test" and p.get("configuration_revision") == revision]
        last = sorted(matching, key=lambda p: p.get("tested_at", ""), reverse=True)
        result = {**configuration, **(last[0].get("result", {}) if last else {})}
        if configuration["environment"] in {"local", "demo"}:
            try:
                authentication = ai_bridge("status").get("authentication", "UNKNOWN")
            except AIError:
                authentication = "UNKNOWN"
            result["authentication"] = authentication
            result["connected"] = bool(result.get("connected") and authentication == "LOGGED_IN")
        public_profiles = [{k: v for k,v in p.items() if k != "configuration_revision"}
                           for p in profiles if p.get("setting_type") != "provider_test"]
        return {**result, "profiles": public_profiles, "tested_at": last[0].get("tested_at") if last else None,
                "supabase_connected": True, "supabase_status": "USER_AUTH_AND_DB_READ_VERIFIED"}

    @app.post("/api/provider/test")
    def provider_test(ctx=Depends(context)):
        try:
            status = ai_bridge("status")
            if status.get("authentication") not in {"LOGGED_IN", "CONFIGURED_UNTESTED"}:
                result = {**provider_configuration(), **status, "connected": False}
                save(ctx, "setting", {"id": str(uuid4()), "setting_type": "provider_test", "configuration_revision": configuration_revision(settings.approval_signing_key),
                    "tested_at": now(), "provider": result["provider"], "model": result["model"], "result": result})
                return result
            result = ai_bridge("analyze", {"question": "원문 통지 기한을 근거와 함께 답하세요.",
                "evidence": [{"id": "connection-test", "text": "The notice period is 14 calendar days.", "location": "격리된 연결 시험 입력"}]})
            event(ctx, "provider_connection_test", provider=provider_configuration()["provider"], inference="SUCCEEDED")
            response = {**provider_configuration(), **status, "inference": "SUCCEEDED", "connected": True, "result": result}
            save(ctx, "setting", {"id": str(uuid4()), "setting_type": "provider_test", "configuration_revision": configuration_revision(settings.approval_signing_key), "tested_at": now(),
                "provider": response["provider"], "model": response["model"], "result": response})
            return response
        except AIError as e:
            configuration = provider_configuration()
            save(ctx, "setting", {"id": str(uuid4()), "setting_type": "provider_test", "configuration_revision": configuration_revision(settings.approval_signing_key), "tested_at": now(),
                "provider": configuration["provider"], "model": configuration["model"],
                "result": {"connected": False, "inference": "FAILED", "error_code": e.code}})
            fail(e.code, "실제 연결 시험에 실패했습니다. 설정과 인증 상태를 확인하세요.", 503)

    def get_profile(ctx, profile_id):
        profile = get(ctx, profile_id, "setting")
        if profile.get("type") not in {"corporate_llm", "sso", "provider"} or profile.get("setting_type"):
            fail("NOT_FOUND", "접근 가능한 연결 프로필이 없습니다.", 404)
        return profile

    def validate_profile(body):
        if body.endpoint and (not body.endpoint.startswith("https://") or re.search(r"(?i)token=|key=|password=|@", body.endpoint)):
            fail("UNSAFE_PROFILE_ENDPOINT", "인증정보 없는 HTTPS 주소만 입력하세요.")

    @app.get("/api/settings/profiles")
    def profiles(ctx=Depends(context)):
        return [profile for profile in list_entities(ctx, "setting")
                if profile.get("type") in {"corporate_llm", "sso", "provider"} and not profile.get("setting_type")]

    @app.post("/api/settings/profiles")
    def save_profile(body: Profile, ctx=Depends(context)):
        validate_profile(body)
        return save(ctx, "setting", {"id": str(uuid4()), **body.model_dump(), "status": "NOT_CONFIGURED",
                                    "created_at": now(), "active": False})

    @app.patch("/api/settings/profiles/{profile_id}")
    def edit_profile(profile_id: str, body: ProfileEdit, ctx=Depends(context)):
        previous = get_profile(ctx, profile_id)
        if previous["version"] != body.version:
            fail("VERSION_CONFLICT", "다른 변경이 있습니다. 프로필을 다시 열어 수정하세요.", 409)
        if previous["type"] != body.type:
            fail("PROFILE_TYPE_MISMATCH", "연결 유형은 변경할 수 없습니다. 다른 유형은 새 프로필로 등록하세요.", 422)
        validate_profile(body)
        changed = {**previous, **body.model_dump(exclude={"version"}), "status": "NOT_CONFIGURED", "active": False}
        return save(ctx, "setting", changed, expected_version=body.version)

    @app.get("/api/projects/{pid}/provider")
    def project_provider(pid: str, ctx=Depends(context)):
        project = get(ctx, pid, "project")
        selected = get_profile(ctx, project["provider_profile_id"]) if project.get("provider_profile_id") else None
        return {"project_id": pid, "project_version": project["version"], "selected_profile": selected,
                "runtime_policy": "ENVIRONMENT_BOUND_OPENAI", "default_provider": provider_configuration(),
                "active": False if selected else None,
                "status": "NOT_CONFIGURED" if selected else "ENVIRONMENT_DEFAULT"}

    @app.put("/api/projects/{pid}/provider-profile")
    def select_project_provider(pid: str, body: ProjectProviderSelection, ctx=Depends(context)):
        project = get(ctx, pid, "project")
        if project["version"] != body.version:
            fail("VERSION_CONFLICT", "프로젝트 설정이 바뀌었습니다. 새로고침 후 다시 선택하세요.", 409)
        if body.profile_id:
            selected = get_profile(ctx, body.profile_id)
            if selected["type"] not in {"corporate_llm", "provider"}:
                fail("LLM_PROFILE_REQUIRED", "AI에는 LLM 구성 프로필만 선택할 수 있습니다.", 422)
        updated = save(ctx, "project", {**project, "provider_profile_id": body.profile_id}, expected_version=body.version)
        event(ctx, "project_provider_configuration_selected", pid, profile_id=body.profile_id, connected=False)
        return {**updated, "kind": updated.get("project_kind", "current")}

    frontend = ROOT / "frontend"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app

app = create_app()
