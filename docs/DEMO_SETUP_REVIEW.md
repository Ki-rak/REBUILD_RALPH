# RE:Build Agent — 실제 INPUT 시연 도구의 독립 검토

이번 검토는 ops/demo.py, ops/demo.ps1, ops/demo_live_verify.py, ops/demo_live_server.py, tests/test_demo.py, tests/test_demo_live.py, docs/LOCAL_DATA_DEMO.md의 변경 범위다. 전체 제품 final gate가 아니다.

## code-reviewer

- 검토자: /root/demo_tools_review
- 최초 REQUEST_CHANGES: 실제 Storage 경로와 정리 경로 불일치 및 orphan 누락, 불완전한 과거 추출의 성공 처리.
- 수정: run metadata 확인, owner-prefix 전체 실제 Storage 목록과 빈 상태 재확인, 그 후 DB/Auth 정리. 선택 해시 다중집합 일치·EXTRACTED 강제.
- 최종 APPROVE, 추가 issue0. 검토자가 Python5파일 AST·PowerShell parse 및 no-network cleanup/추출 거부 probe를 실행했다.

## architect

- 검토자: /root/demo_tools_architecture
- 최초 BLOCK: 위 정리 오류, export 재생성이 저장 파일 소실을 숨기는 검증, 로컬 Start가 deployed 환경을 상속하는 인증 오류.
- 수정: 최초 output_generated 경로·해시 보존 후 실제 재시작/새 로그인에서 같은 객체를 export 전에 확인. Start만 process-local 환경 고정/복원. 과거 원본/sidecar 검증도 포함.
- 최종 CLEAR, 추가 blocker0. 검토자가 JUnit163건, 실패·오류·건너뜀0 및 실제 BLOCKED 보고서를 직접 읽었다.

## 실행 근거와 한계

Root가 새 회귀23건 및 전체163건을 실행해 exit0을 확인했다. 실제 P01/P06 21개와 N01/N02 18개의 원본, 6개 실제 XLSX/PPTX 생성·재개봉·저장 파일 누락 부정 사례를 포함한다. 이 시험의 저장소는 TEST_STORAGE_INJECTED다. 실제 Supabase 검증은 PENDING_SCHEMA, Codex OAuth는 NOT_LOGGED_IN/NOT_TESTED다. 이 검토를 실제 서비스/제품 완료 또는 OMX strict 통과로 사용할 수 없다. 원본 및 기존 인증정보는 변경하지 않았다.

근거 파일: ops/runtime/demo/pytest-local-data-20260922.xml, ops/runtime/demo/live-verification-20260921T223907451750Z.json, ops/runtime/demo/setup-verification-20260922.json. 실제 대화·도구 기록은 별도 원시 세션 snapshot에 보존한다.


## Browser verifier / bounded transfer budget — 2026-09-22

Scopes: ops/demo_browser.cjs, ops/demo_browser_verify.py, tests/ui/demo_target.test.cjs, tests/test_demo_browser.py, ops/demo.ps1, backend/storage.py, tests/test_storage.py.

code-reviewer APPROVE/0 issues; architect CLEAR. Initial browser boundary review WATCH (redirect credentials and parent-only timeout cleanup) resolved by redirect refusal/exact origin checks before credentials, child stdin, owned process-tree cleanup and bounded deadlines. SHA dedup requires every filename alias and EXTRACTED state. Exact stored outputs must exist before post-restart export.

Actual Windows process-tree cleanup1PASS, Node destination/identity/duplicate coverage3PASS, fresh full Python174PASS, AI31PASS, JS/PowerShell syntaxPASS. Independent reviewer re-ran Node3 and timeout3 tests/PowerShell parsing; prior isolated storage classifier independent7PASS. Narrow budget change keeps explicit timeout and finite connect/pool20/read/write60 seconds; no writes automatically replayed.

Two reviewers reviewed parent's bounded cleaner plan independently; neither modified files. Actual UI run remains in progress; these reviews do not prove its success, OAuth, product completion or final OMX strict.
