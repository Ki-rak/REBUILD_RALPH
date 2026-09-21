from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")


def test_product_name_and_six_navigation_labels_are_exact():
    assert "RE:Build Agent" in HTML
    for label in ("프로젝트", "지식조회", "지식 자료실", "데이터 관리", "표준 양식", "설정"):
        assert label in JS


def test_api_contracts_are_wired_without_static_preview_inventory():
    required = (
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/me",
        "/api/auth/refresh",
        "/api/projects",
        "/documents",
        "/upload",
        "/original",
        "/api/import/candidates",
        "/api/import/approve",
        "/api/search",
        "/analyze",
        "/knowledge",
        "/api/templates",
        "/drafts",
        "/approve",
        "/export",
        "/api/management",
        "/api/provider/status",
        "/api/provider/test",
        "/api/settings/profiles",
    )
    for route in required:
        assert route in JS
    assert "UI_INVENTORY" not in JS
    assert "P01" not in JS
    assert "N01" not in JS


def test_auth_and_original_download_do_not_put_tokens_in_urls():
    assert "sessionStorage.setItem(tokenKey" in JS
    assert "Authorization" in JS
    assert "URL.createObjectURL" in JS
    assert "access_token=" not in JS
    assert "?token=" not in JS
    assert "rebuild_refresh_token" in JS
    assert "openAuthorized" in JS


def test_truthful_states_and_approval_boundary_are_visible():
    for phrase in ("AI 연결 미확인", "REVIEW_REQUIRED", "데이터 등록 승인", "결과물 최종 승인"):
        assert phrase in JS
    assert "미연결" in JS
    assert "실제 연결 상태는 미설정" in JS
    assert "실제 호출 성공" in JS
    assert "data.up_to_date" in JS


def test_export_source_deep_link_opens_authenticated_evidence():
    assert "source=" in JS
    assert "/knowledge" in JS
    assert "원문 근거" in JS


def test_knowledge_comparison_supports_actual_flat_api_shape():
    assert "typeof pastValue==='string'" in JS
    assert "typeof currentValue==='string'" in JS
    assert "item.historical_refs" in JS
    assert "item.current_refs" in JS


def test_persisted_drafts_revision_safety_and_project_kinds_are_wired():
    assert "/documents`),api(`/api/projects/${encodeURIComponent(state.project.id)}/drafts`" in JS
    assert "state.draftDirty=true" in JS
    assert "template_version:document.querySelector('#draft-bound-version')" in JS
    assert "value=\"historical\"" in JS
    assert "project.kind==='historical'" in JS


def test_graph_retry_and_immutable_template_versions_use_actual_ids():
    assert 'data-row-id="${attr(node.row_id)}"' in JS
    assert 'data-id="${attr(node.document_id)}"' in JS
    assert "state.selectedComparisonId=b.dataset.rowId" in JS
    assert "/retry`" in JS
    assert "['ERROR','OCR_REQUIRED','UNSUPPORTED','FAILED']" in JS
    assert "/versions`" in JS
    assert "?version=${encodeURIComponent(b.dataset.version)}" in JS
    assert "template_version:document.querySelector('#draft-template-version').value" in JS


def test_accessibility_and_mobile_contracts_exist():
    assert 'lang="ko"' in HTML
    assert "본문으로 건너뛰기" in HTML
    assert "aria-modal" in JS
    assert "aria-current" in JS
    assert "prefers-reduced-motion" in CSS
    assert "@media(max-width:420px)" in CSS
    assert "min-height:44px" in CSS


def test_local_font_and_no_external_font_or_script_dependency():
    assert "PretendardVariable.woff2" in HTML
    assert "PretendardVariable.woff2" in CSS
    assert "fonts.googleapis.com" not in HTML + CSS
    assert "https://" not in HTML
