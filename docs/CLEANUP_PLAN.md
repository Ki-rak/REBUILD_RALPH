# RE:Build Agent bounded cleanup plan

2026-09-21 21:25 KST. Scope: backend/server.py, backend/exports.py, frontend/app.js and narrow regression tests. No architecture rewrite or new dependencies.

Behavior lock: full Python suite 88 PASS; AI adapter suite previously 25 PASS. Independent browser tests remain separate.

Fallback classification:
- Authentication context opens an HTTP client before get_user and fails without closing it. Repair ownership/finally; keep sanitized rejection.
- Risk workbook calculation flags use a silent AttributeError catch. Explicitly create openpyxl CalcProperties only when a valid workbook lacks metadata, then set flags; preserve computed-formula contract.
- File download/open attempts JSON then text on the same consumed Response. Read once by content type and preserve HTTP failure.
- Drag/drop suppresses file assignment errors. Report failure and preserve existing file selection.
- Extraction failures preserve originals and explicit FAILED/OCR_REQUIRED status: grounded fail-safe boundary; retain.
- Provider failure remains UNKNOWN/disconnected, never auth fallback: grounded fail-safe boundary; retain.
- Catch-all public HTTP boundary suppresses raw credential-bearing messages while returning SERVICE_UNAVAILABLE: grounded security boundary; retain.

Pass order: remove redundant failure branch, repair resource ownership/error reporting, add narrow regressions, rerun relevant suites. No unrelated renaming or new abstraction. Separate implementer and reviewer required.
## Acceptance follow-up cleanup plan — 2026-09-22

Scope: committed backend/analysis.py, backend/drafts.py, backend/server.py, frontend/app.js/styles.css, tests/ui/run_browser.py and fixture target helper. XLSX output repair is reviewed separately after its behavior lock is complete. No architecture rewrite or new dependency.

Behavior lock: analysis/boundary/profile28 and independent31PASS; frontend context9/errors3; owned8784 provider6/mobile9; fixture-boundary4 and independent6. Preserve complete sources, rating eligibility, strict OAuth/API separation and honest test boundaries.

Order: inspect fallbacks and fail-open behavior; check dead code/duplicates; clarify error/role boundaries; confirm regressions. Retain duplicate provider version checks at distinct asynchronous boundaries because they prevent different races. Keep risk role and numeric statistical eligibility separate. Keep explicit fixture denial on missing environment/boundary/runID. No speculative abstraction or formatter-wide churn.
## XLSX bounded cleanup plan — 2026-09-22

Scope: backend/exports.py and tests/test_exports.py only. Before further cleanup, lock full text, literal strings, generated formulas, missing ratings, zero values, item-to-source relationships and original templates. Preserve excerpt+detail as an explicit presentation contract, not a hidden truncation fallback. Reuse existing chunk/SourceRef/write helpers; separate ITB/Risk columns reflect different templates. Inspect masking defaults/dead code/duplication/naming, then targeted and full regression. No architecture or dependency change justified. Root authors this plan; acceptance_architecture independently reviews it. Product completion still requires live services and final strict gate.


## 실제 서비스 검증 도구 bounded plan — 2026-09-22

Scope: ops/demo_browser.cjs, ops/demo_browser_verify.py, ops/demo_live_server.py, ops/demo.ps1, backend/storage.py 및 해당 회귀. 이미 수정된 HTTP400/NoSuchKey와 단계별 유한 timeout 계약을 보존한다.

Behavior lock: Python165PASS(읽기/쓰기 budget 추가 전), Storage36PASS, browser target Node3PASS 및 Windows 소유 자식 프로세스 종료1PASS. 실제 UI 통합 검증은 별도로 진행한다.

Fallback inventory: HTTP400 exact NoSuchKey는 관측된 provider 프로토콜 정규화이며 masking fallback이 아니다. 명시 timeout 인수를 보존하고 timeout에 쓰기 자동 재실행을 금지한다. 스크린샷 실패 무시는 핵심 실패 상태/종료코드를 유지하는 부가 진단 경계다. process-tree 정리 실패는 명시 오류로 남기므로 성공으로 숨기지 않는다. 규칙과 OAuth/API-key 경로를 전환하지 않는다. Mock/injected와 actual서비스를 분리한다.

순서: 1) 무용 코드 확인, 2) 이미 공유하는 서버/계정 정리/Office/영속성 helper 재사용 확인, 3) 오류·credential 경계 및 소유권 점검, 4) 회귀 재실행과 독립 리뷰. 스타일만을 위한 광범위 재구성·새 의존성 설치는 하지 않는다. writer/reviewer 분리, 전체 서비스/최종 gate 성공은 실제 증거 후에만 기록한다.

## Final bounded pass — 2026-09-22 after actual service repairs
Scope: frontend/app.js/styles.css draft evidence and verified DB status; backend/ai.py and server/ai providers finite timeout; backend/storage.py read disconnect; ops/demo.py/report identity and ops/demo_browser.cjs export diagnostic.
Behavior lock: Python182, AI33, frontend context10/errors3, storage38, report collision RED-to-GREEN, Chromium120refs/3types/mobile. These precede cleanup review; no unrelated refactoring planned.
Fallback inventory: exact GET RemoteProtocolError retry once is a grounded transport recovery, tested exhausted and no write replay. General timeout/auth/HTTP errors propagate. Provider budgets are finite, with no auth fallback. Browser screenshot failure cannot become PASS. Historical failed reports remain immutable.
Pass order: inspect dead code, duplication, naming/error boundaries, tests. Preserve actual SourceRefs and approvals. Writer root, independent reviewers demo_tools_review/demo_tools_architecture. Any absent live restart evidence remains a product gate blocker. No speculative abstraction/dependency or design system rewrite.
