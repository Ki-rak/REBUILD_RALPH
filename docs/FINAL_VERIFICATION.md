# RE:Build Agent 최종 검증 자료 — 인증 전 증거 정리

2026-09-22, 사용자가 요청한 1번 작업의 결과다. 제품은 **미완료**, native goal은 **blocked**다. 이번 작업은 기존 실행 근거를 정리하고 무결성과 누락을 검사하는 작업이다. 인증, 제품 goal 재개, 새 제품 기능, 배포, 공개 푸시는 수행하지 않는다.

## 현재 근거와 한계

| 구분 | 보존된 결과 | 증명하지 않는 것 |
|---|---|---|
| 로컬 제품 회귀 | 이전 실행 Python 140 통과, 기존 경고 2개. 출력 검증 기록과 실제 세션에 남아 있음 | 이번 정리 작업에서 전체 회귀를 다시 실행했다는 의미가 아님 |
| 브라우저·Office | 소유 fixture에서 26개, 생성 파일 재개봉 16개. 새 업로드·근거·승인·3종 출력 | 저장소와 로그인은 TEST_STORAGE_INJECTED; 실제 Supabase 지속성/RLS 아님 |
| OpenAI | 실제 API-key 호출, source 인용, usage 305/1263/1568, 출력 재개봉 | 저장소·승인은 시험용. 로컬 Codex OAuth 성공 아님 |
| Supabase Auth | 실제 제품 HTTP login/me/refresh/logout/revocation, 시험 사용자 정리 | DB/Storage 사용자 권한 검증 아님 |
| Supabase Storage | private bucket 생성·설정 확인 | 사용자 JWT의 Storage RLS 통과 아님 |
| 남은 연결 | 마지막 확인 PENDING_SCHEMA, NOT_LOGGED_IN | 건강 확인 응답이나 mock 테스트로 해결 처리하지 않음 |
| 출력 표시 | 실제 ITB/Risk 렌더 및 5장 심의장표, 긴 한글과 근거/세부 내용 검사 | 모든 가능한 입력에 대한 무제한 표시 보장 아님 |

첫 ITB 실패 PNG는 앞선 작업에서 덮어써져 실제 세션의 이미지 기록만 남았다. 현존하는 중간 PNG를 최초 실패 원본으로 취급하지 않는다. Risk의 수정 전/중간/최종 이미지와 최종 XLSX는 그대로 보존한다.

## 완료 기준별 증거 지도

아래는 SPEC의 제품 기준 36개다. 파일이 존재하거나 시험 코드가 있다는 사실은 실행 성공 증거가 아니다. `근거`는 아래 색인의 실제 기록을 가리키며, 각 기록의 범위를 따라 해석한다. 모든 기준의 **최종 인수 판정은 대기**다. 이는 이미 통과한 국소 시험을 취소하는 것이 아니라 실제 연결과 최종 검토가 아직 끝나지 않았음을 뜻한다.

세부 구현 파일·시험 파일·기록 SHA-256은 [manifest.json](../ops/verification/preauth-20260922/manifest.json)에 있다.

| 기준 | 확인 대상 | 근거 ID | 남은 확인 |
|---|---|---|---|
| AC01 | 폴더 승인 전 무처리 | layout | 실제 사용자 DB에서 승인 전후 부작용 없음 확인 |
| AC02 | 신규 원본 선저장·해시 | browser, mixed | 실제 Storage bytes와 추출 SourceRef 대조 |
| AC03 | 4대 형식·표·locator | layout | 최종 회귀 및 실제 저장본 MD/JSON 확인 |
| AC04 | 승인 정정 조항만 대체 | layout, code_review | 최종 회귀; 실제 프로젝트 입력 비교 |
| AC05 | 관측·설계·단위 구별 | layout, output_review | 최종 회귀와 신규 입력 의미 대조 |
| AC06 | 유효 SourceRef·변조 차단 | layout, code_review | 실제 원본 접근·권한 및 두 AI 결과 근거 검증 |
| AC07 | ITB 3개 이상 항목 | office, layout | 실제 저장소 경로로 항목·근거·검토사항 확인 |
| AC08 | 승인 결합·변경 무효화 | browser, code_review | 실제 DB 원자 승인·동시 변경·다른 사용자 차단 |
| AC09 | XLSX 재개봉·표시 | office, layout, output_review | 실제 저장소 다운로드 파일 재개봉 |
| AC10 | 같은 해시 중복·별칭 | layout | 실제 DB 중복 재시도·별칭 보존 |
| AC11 | 손상·스캔·미지원 격리 | mixed, layout | 실제 저장소 혼합 인입 후 정상 자료 계속 처리 |
| AC12 | 입력 변경·근거 부족 보류 | layout, browser | 신규 두 입력 및 무관 자료로 실서비스 재검증 |
| AC13 | API 없는 정직한 경로 | browser, ai_tests | 최종 회귀; 실제 로컬 미연결/연결 상태 구분 |
| AC14 | 평가 자료 런타임 제외 | layout, code_review | 최종 경계 검토; holdout 원문 읽지 않음 |
| AC15 | 재시작 전체 UI 경로 | blocked, browser | 실제 서버 재시작·새 로그인·전체 재사용 미검증 |
| AC16 | 원본·실제 로그 보존 | originals, raw_index | 현재 작업 snapshot 추가·최종 결과 포함 구간 확인 |
| AC23 | 실제 AI 호출·근거 | openai, blocked | 로컬 OAuth 제품 호출과 실제 DB 저장 검증 |
| AC24 | 원본·승인·출력 영속성 | blocked | 실제 프로세스 재시작 및 새 세션 복원 미검증 |
| AC25 | Provider 프로필·상태 | profiles, mobile, code_review | 실제 DB 프로필 복원·인증 변경 후 호출 상태 확인 |
| AC26 | 로그인·세션·로그아웃 | auth | 실제 DB 결합 전체 흐름 및 최종 회귀 |
| AC27 | SSO 설정·미연결 표시 | profiles, browser | 최종 화면 확인; 사내 IdP 실제 연결은 제외 |
| AC28 | 사용자별 DB·Storage 격리 | blocked, auth | 두 실제 사용자 JWT와 무인증으로 RLS/API 부정 시험 |
| AC29 | DB 미등록 신규 업로드 E2E | browser, office | 실제 DB 사전 hash 부재→새 source→승인→3출력→재조회 |
| AC30 | 다른 입력·무관 근거·무효화 | layout, browser | 실제 DB에서 변경·무관 입력 결과 차이와 승인 무효화 |
| AC31 | 프로젝트 시작·자료 귀속 | browser, mobile | 실제 로그인 계정 프로젝트·자료 재접속 확인 |
| AC32 | 보유량·승인·정확한 최신 상태 | layout, mixed, browser | 실제 DB 승인·변경·권한 상실 시 상태 검증 |
| AC33 | 지식조회 모드·맥락·범위 | scope, profiles | 실제 사용자·프로젝트 격리 및 SourceRef 열기 |
| AC34 | 공통 양식 버전·승인 보호 | browser, office | 실제 Storage 사용자별 버전·재시작 복원 |
| AC35 | ITB 주요정보·트리거 | office, layout, output_review | 실제 저장소 신규 자료 XLSX 재개봉 |
| AC36 | 근거 기반 Risk·강도 공란 | office, layout, code_review | 실제 저장소 신규 Risk XLSX 및 근거 표본 대조 |
| AC37 | 5항목 심의 편집·PPTX | office, slides, output_review | 실제 저장소 승인본 PPTX 재개봉·근거 대조 |
| AC38 | 실자료 노드·양쪽 근거 | browser, scope | 실제 신규 업로드 후 graph source 및 원문 권한 확인 |
| AC39 | 로컬 공식 OAuth 전용 | blocked, ai_tests | 전용 공식 로그인 후 제품 실제 호출; key fallback 금지 |
| AC40 | 서버 OpenAI API key 전용 | openai, ai_tests | 최종 adapter 회귀; 이미 실제 호출한 배포용 경로와 배포 분리 |
| AC41 | 인증·최소 환경·비밀 경계 | ai_tests, code_review, openai | 최종 AI 회귀와 실제 OAuth 오류·비밀 비노출 점검 |
| AC42 | Windows·기록·독립 strict | blocked, native, omx_plan, omx_source, architecture, cleanup | cleaner→최종 회귀→독립 두 리뷰→실제 OMX strict; 연속 실행 보장 아님 |

AC17–22는 행사 결과·배포·영상·공개 저장소·발표자료·제출용 주요 JSONL에 관한 별도 운영 기준이며 삭제하지 않았다. 사용자 후속 요청까지 이번 제품 실행 범위에서 제외한다. 다만 실제 goal 원문·실행·결과를 정직하게 보존하는 일은 AC16/42와 현재 goal 계약에도 포함된다. 주요 JSONL의 최종 제출 자격은 아직 확인되지 않았다.

## 인증 후 2–6번 재개 순서

시각만으로 재개하거나 완료 판정하지 않는다. 사용자의 재개 지시와 실제 인증 상태를 확인한 뒤, 기존 목표·커밋을 유지하며 다음 순서로 수행한다.

2. **실제 Supabase 연결 완결.** 승인된 관리 경로로 기존 구조를 확인하고 준비 SQL을 적용한다. `supabase/migrations/20260921210000_rebuild_agent_storage.sql` 및 `supabase/README.md`를 따른다. `./ops/python.ps1 ops/runtime/supabase_live_verify.py`를 실행해 schema, 실제 두 사용자 JWT DB/Storage 격리, 무인증 거부, 로그아웃·정리를 확인한다. 관리 키로 성공한 접근을 사용자 RLS 증거로 쓰지 않는다. schema 사전 확인만 통과하거나 정리에 실패하면 완료가 아니다.
3. **공식 로컬 OAuth 제품 호출.** 사용자 전용 로그인 후 `npm --prefix server/ai run status`, 필요 시 `npm --prefix server/ai run smoke`로 상태·실제 adapter 호출을 구분한다. 이어 제품의 AI Insight로 신규 입력을 분석해 실제 호출/모델/usage/SourceRef와 DB 저장을 확인한다. smoke의 고정 근거만으로 제품 호출을 대신하지 않는다. 로컬에 API key가 있어도 fallback은 없어야 한다. 배포용 API-key 경로의 이전 실제 성공 기록과 변경 후 회귀를 별도로 검토한다.
4. **실제 저장소의 신규 업로드·재시작 통합 검증.** 두 개 이상의 새 bytes에 대해 DB/index/cache 사전 hash 부재를 기록한다. 원본→MD/JSON→과거 자료 연결·차이→지식조회/노드/양쪽 근거→편집·승인→ITB XLSX/Risk XLSX/심의 PPTX 다운로드·재개봉을 확인한다. 다른 조건 입력, 무관 자료, 손상 혼합, 중복, 입력/초안/양식 변경에 따른 승인 무효화도 확인한다. 원본 hash·프로젝트/문서/초안/승인/파일 ID를 기록하고 제품 프로세스를 실제 종료·재시작한 뒤 새 인증 세션으로 같은 내용을 재조회한다. 두 번째 사용자의 접근 거부도 확인한다. **이 실제 DB+프로세스 재시작 전체 절차를 자동화한 완료된 runner는 아직 없다.** 기존 browser fixture에 실제 서비스 URL만 넣지 말고 별도 소유 세션/시험 자료를 쓰는 통합 절차를 구성한다.
5. **실패 수정·최종 회귀·독립 리뷰.** 실패 원인을 고치고 영향 시험과 전체 회귀를 수행한다. ai-slop-cleaner 적용 후 재검증하고, 독립 `code-reviewer`와 `architect`가 최신 코드와 실제 서비스 기록을 검토한다. 기존 국소 CLEAR를 전체 APPROVE/CLEAR로 복사하지 않는다. 결함이 있으면 기록·수정·재검증한다. 성공 기준이나 평가 기대값은 완화하지 않는다.
6. **OMX strict 및 기록·커밋 마감.** 아래 계약에 따라 모든 story와 기준의 실제 증거를 확정한다. 그 이후에만 native goal 완료, fresh get_goal 원본 보존, 최종 OMX `--strict` 체크포인트를 수행한다. 실제 세션 구간은 따로 내보내고 사용자 입력·goal 첨부·최종 결과가 함께 있는지 확인한다. 의미 있는 작업마다 로컬 커밋한다. 배포·공개 푸시·영상·발표·행사 제출은 여전히 별도 요청 사항이다.

최종 회귀의 기존 실행 명령:

```powershell
.\ops\python.ps1 -m pytest tests -q
npm --prefix server/ai test
node tests/ui/frontend_context.cjs
node tests/ui/frontend_errors.cjs
.\ops\python.ps1 tests/ui/run_browser.py browser_flow.cjs
.\ops\python.ps1 tests/ui/browser_workbook.py
```

브라우저 위 명령은 의도적으로 시험 저장소를 사용한다. 실제 Supabase E2E와 별도 기록한다. 추가 UI 시나리오의 명령·소유 fixture 조건은 [browser_README.md](../tests/ui/browser_README.md), 실제 서비스 절차는 [RUNBOOK.md](RUNBOOK.md)에 있다. 재개 시 실제 변경 범위에 맞게 필요한 시험을 선택하며 이미 확보한 근거를 이유 없이 반복하지 않는다.

## OMX 최종 게이트 준비 상태

설치된 OMX 0.21.5의 `dist/ultragoal/artifacts.js`를 읽어 필드 계약을 확인했다. 기본 모드는 advisory이므로 **최종 체크포인트에 `--strict`가 필수**다. [quality-gate.pending.json](../ops/verification/preauth-20260922/quality-gate.pending.json)은 필드와 10개 불변 조건의 검증 대상을 정리한 **의도적으로 통과 불가능한 준비 파일**이다. 이번 작업에서 OMX strict validator를 실행하거나 통과시킨 적은 없다.

최종에는 다음이 실제 증거와 함께 필요하다.

- `aiSlopCleaner.status=passed`, 변경 후 실행 근거.
- `verification.status=passed`, 실제 실행한 commands와 결과.
- `codeReview.recommendation=APPROVE`, `architectStatus=CLEAR`; 각 독립 역할의 완료된 리뷰 근거.
- `architectureInvariantGate.status=passed`; 모든 불변 조건은 `proved`, 구현/시험/리뷰 근거가 있어야 하고 `blockers` 필드가 남아 있으면 안 된다.
- 원래 brief와 승인된 steering의 불변 조건도 빠짐없이 포함한다. 설치 코드의 자동 추출은 영어 heading/inline 선언 패턴을 사용하므로 추출 건수만으로 한국어 SPEC/실제 goal 준수를 판단하지 않는다.

역사적 `.omx/ultragoal/brief.md`는 초기 명칭·선택 기술·행사 운영안을 담는다. 원문은 보존하고 현재 사용자 지시, 실제 `ops/runtime/GOAL_ENTERED.md`, 최신 SPEC, 승인된 ledger와 현재 goals.json을 함께 적용한다. 현재 G001 in_progress/4 pending/0 complete는 실제 연결을 기다리는 기록이다. 준비 파일을 만들었다고 story 상태를 완료로 바꾸지 않는다. `native goal=null` 등 HARNESS의 과거 문구는 현재 상태가 아니다.

최종 checkpoint 명령의 형태만 참고한다. 아래 자리표시자는 실행 명령이 아니며, pending 파일을 넣어서는 안 된다.

```text
node ops/omx.mjs ultragoal checkpoint --goal-id <actual-final-story-id> --status complete --evidence <verified-evidence> --codex-goal-json <fresh-real-complete-goal.json> --strict --quality-gate-json <actual-final-quality-gate.json>
```

## 증거 묶음 재검증·보존

```powershell
.\ops\python.ps1 ops/verify_evidence_bundle.py --check-local-raw
.\ops\python.ps1 ops/verify_evidence_bundle.py --require-complete
```

첫 명령은 36+6 기준 범위, 참조/해시, 준비 게이트의 미통과 상태와 로컬 원시 snapshot을 검사한다. 두 번째 명령은 미완료이므로 **exit 2 / BLOCKED가 정상 기대 결과**다. 이 도구는 준비 파일 전용이며 제품 완료 인증기나 OMX strict validator를 대체하지 않는다. 최종 gate를 만들 때 준비 기록을 덮어쓰지 않고 새 증거 세트를 만든다.

검토 ZIP은 `--bundle ops/exports/<새 이름>.zip`으로 만들 수 있다. 파일 목록은 manifest의 명시적인 경로만 사용하고 재개봉 후 bytes를 대조한다. 이미 존재하는 ZIP은 덮어쓰지 않는다. 이 ZIP에는 선택한 실행 기록·리뷰·구현/시험 소스·Office/렌더 근거가 들어간다. 원시 세션, .env, OAuth 인증 디렉터리, evaluator, 전체 원본 자료 폴더, node_modules 전체는 넣지 않는다. 설치된 OMX validator 소스 한 파일은 버전 계약 확인용으로 포함한다. 행사 제출 ZIP이나 완전한 소스 배포 패키지가 아니다.

원시 JSONL은 기존 `ops/sessions`에서 구간별 원본 snapshot으로 보존하고, manifest에는 경로·해시·이벤트 수만 연결한다. 병합·합성하지 않는다. 활성 snapshot에는 이번 작업 이후의 최종 응답이 없을 수 있으므로 최종 결과 자격을 자동 부여하지 않는다. 나중에 입력과 최종 결과를 실제 원기록에서 검증해야 한다.

## 근거 색인

- `browser`: [ops/runtime/browser-report-2026-09-21T16-01-55-875Z.json](../ops/runtime/browser-report-2026-09-21T16-01-55-875Z.json) — TEST_STORAGE_INJECTED; 26 checks, historical execution
- `office`: [ops/runtime/browser-workbook-20260921T160337Z.json](../ops/runtime/browser-workbook-20260921T160337Z.json) — TEST_STORAGE_INJECTED; 16 reopen checks, historical execution
- `layout`: [ops/runtime/output-layout-verification.json](../ops/runtime/output-layout-verification.json) — ROOT_RECORDED_OUTPUT_REVIEW; prior140 tests/2warnings, not rerun in this task
- `mixed`: [ops/runtime/browser-mixed-upload-2026-09-21T13-28-04-176Z.json](../ops/runtime/browser-mixed-upload-2026-09-21T13-28-04-176Z.json) — TEST_STORAGE_INJECTED; 10 mixed-upload checks
- `scope`: [ops/runtime/browser-search-scope-2026-09-21T14-33-57-842Z.json](../ops/runtime/browser-search-scope-2026-09-21T14-33-57-842Z.json) — TEST_STORAGE_INJECTED; 7 search-scope checks
- `slides`: [ops/runtime/browser-slide-limits-2026-09-21T14-15-04-961Z.json](../ops/runtime/browser-slide-limits-2026-09-21T14-15-04-961Z.json) — TEST_STORAGE_INJECTED; 9 slide-limit checks
- `profiles`: [ops/runtime/browser-provider-profiles-2026-09-21T15-07-45-436Z.json](../ops/runtime/browser-provider-profiles-2026-09-21T15-07-45-436Z.json) — TEST_STORAGE_INJECTED; 6 profile checks
- `mobile`: [ops/runtime/browser-mobile-core-2026-09-21T15-07-50-276Z.json](../ops/runtime/browser-mobile-core-2026-09-21T15-07-50-276Z.json) — TEST_STORAGE_INJECTED; 9 mobile checks
- `openai`: [ops/runtime/product-openai-usage-20260921T124924Z.json](../ops/runtime/product-openai-usage-20260921T124924Z.json) — ACTUAL_OPENAI_API_KEY_CALL; TEST_STORAGE_INJECTED and SYNTHETIC_TEST_APPROVAL; not OAuth/DB proof
- `auth`: [ops/runtime/product-auth-live-20260921T133655Z.json](../ops/runtime/product-auth-live-20260921T133655Z.json) — ACTUAL_SUPABASE_AUTH; not DB/Storage/OAuth proof
- `bucket`: [ops/runtime/supabase-bucket-configuration-20260921T135051Z.json](../ops/runtime/supabase-bucket-configuration-20260921T135051Z.json) — ACTUAL_PRIVATE_BUCKET_CONFIGURATION; not user RLS proof
- `blocked`: [ops/runtime/external-blocker-audit.json](../ops/runtime/external-blocker-audit.json) — ACTUAL_LAST_AUTH_CHECKS; PENDING_SCHEMA and NOT_LOGGED_IN, not fresh service recheck
- `originals`: [ops/runtime/original-integrity-current.json](../ops/runtime/original-integrity-current.json) — ORIGINAL_BYTES_HASH_ONLY; prior398-file audit, no source content input
- `raw_index`: [ops/runtime/latest-export-summary.json](../ops/runtime/latest-export-summary.json) — ACTUAL_ACTIVE_SESSION_SNAPSHOTS; not final submission qualification
- `native`: [ops/runtime/native-goal-current.json](../ops/runtime/native-goal-current.json) — ACTUAL_GET_GOAL_RESPONSE; blocked, not complete
- `entered`: [ops/runtime/GOAL_ENTERED.md](../ops/runtime/GOAL_ENTERED.md) — PRESERVED_ACTUAL_GOAL_ATTACHMENT; current contract
- `ai_tests`: [ops/runtime/ai-component-checkpoint.json](../ops/runtime/ai-component-checkpoint.json) — RECORDED_AI_COMPONENT_CHECKPOINT; test source and later review also required
- `acceptance`: [docs/ACCEPTANCE_REVIEW.md](../docs/ACCEPTANCE_REVIEW.md) — HISTORICAL_SCOPED_REVIEW; not final live-dependent APPROVE/CLEAR
- `code_review`: [docs/CODE_REVIEW.md](../docs/CODE_REVIEW.md) — HISTORICAL_SCOPED_REVIEW; not final live-dependent APPROVE/CLEAR
- `architecture`: [docs/ARCHITECTURE_REVIEW.md](../docs/ARCHITECTURE_REVIEW.md) — HISTORICAL_SCOPED_REVIEW; not final live-dependent APPROVE/CLEAR
- `output_review`: [docs/OUTPUT_REVIEW.md](../docs/OUTPUT_REVIEW.md) — HISTORICAL_SCOPED_REVIEW; not final live-dependent APPROVE/CLEAR
- `cleanup`: [docs/CLEANUP_REPORT.md](../docs/CLEANUP_REPORT.md) — HISTORICAL_SCOPED_REVIEW; not final live-dependent APPROVE/CLEAR
- `spec`: [SPEC.md](../SPEC.md) — CONTRACT_OR_IMPLEMENTATION_SNAPSHOT; presence/hash is not execution proof
- `agents`: [AGENTS.md](../AGENTS.md) — CONTRACT_OR_IMPLEMENTATION_SNAPSHOT; presence/hash is not execution proof
- `goal`: [GOAL.md](../GOAL.md) — CONTRACT_OR_IMPLEMENTATION_SNAPSHOT; presence/hash is not execution proof
- `goal_input`: [ops/GOAL_INPUT.txt](../ops/GOAL_INPUT.txt) — CONTRACT_OR_IMPLEMENTATION_SNAPSHOT; presence/hash is not execution proof
- `provider_contract`: [docs/PROVIDER_AUTH.md](../docs/PROVIDER_AUTH.md) — CONTRACT_OR_IMPLEMENTATION_SNAPSHOT; presence/hash is not execution proof
- `runbook`: [docs/RUNBOOK.md](../docs/RUNBOOK.md) — CONTRACT_OR_IMPLEMENTATION_SNAPSHOT; presence/hash is not execution proof
- `browser_runbook`: [tests/ui/browser_README.md](../tests/ui/browser_README.md) — CONTRACT_OR_IMPLEMENTATION_SNAPSHOT; presence/hash is not execution proof
- `dependencies`: [docs/DEPENDENCIES.md](../docs/DEPENDENCIES.md) — CONTRACT_OR_IMPLEMENTATION_SNAPSHOT; presence/hash is not execution proof
- `capabilities`: [docs/CAPABILITIES.md](../docs/CAPABILITIES.md) — CONTRACT_OR_IMPLEMENTATION_SNAPSHOT; presence/hash is not execution proof
- `omx_source`: [tools/omx/node_modules/oh-my-codex/dist/ultragoal/artifacts.js](../tools/omx/node_modules/oh-my-codex/dist/ultragoal/artifacts.js) — CONTRACT_OR_IMPLEMENTATION_SNAPSHOT; presence/hash is not execution proof
- `omx_brief`: [.omx/ultragoal/brief.md](../.omx/ultragoal/brief.md) — CONTRACT_OR_IMPLEMENTATION_SNAPSHOT; presence/hash is not execution proof
- `omx_plan`: [.omx/ultragoal/goals.json](../.omx/ultragoal/goals.json) — CONTRACT_OR_IMPLEMENTATION_SNAPSHOT; presence/hash is not execution proof
- `omx_ledger`: [.omx/ultragoal/ledger.jsonl](../.omx/ultragoal/ledger.jsonl) — CONTRACT_OR_IMPLEMENTATION_SNAPSHOT; presence/hash is not execution proof
- `output_asset_1`: [ops/runtime/xlsx-real-ac35-itb-fixed.png](../ops/runtime/xlsx-real-ac35-itb-fixed.png) — EXISTING_ACTUAL_OFFICE_OR_RENDER; no raw source corpus; scoped layout evidence
- `output_asset_2`: [ops/runtime/xlsx-real-ac35-risk-before-fix.png](../ops/runtime/xlsx-real-ac35-risk-before-fix.png) — EXISTING_ACTUAL_OFFICE_OR_RENDER; no raw source corpus; scoped layout evidence
- `output_asset_3`: [ops/runtime/xlsx-real-ac35-risk-fixed.png](../ops/runtime/xlsx-real-ac35-risk-fixed.png) — EXISTING_ACTUAL_OFFICE_OR_RENDER; no raw source corpus; scoped layout evidence
- `output_asset_4`: [ops/runtime/xlsx-real-ac35-risk-final.png](../ops/runtime/xlsx-real-ac35-risk-final.png) — EXISTING_ACTUAL_OFFICE_OR_RENDER; no raw source corpus; scoped layout evidence
- `output_asset_5`: [ops/runtime/xlsx-real-ac35-itb-final.xlsx](../ops/runtime/xlsx-real-ac35-itb-final.xlsx) — EXISTING_ACTUAL_OFFICE_OR_RENDER; no raw source corpus; scoped layout evidence
- `output_asset_6`: [ops/runtime/xlsx-real-ac35-risk-final.xlsx](../ops/runtime/xlsx-real-ac35-risk-final.xlsx) — EXISTING_ACTUAL_OFFICE_OR_RENDER; no raw source corpus; scoped layout evidence
- `pending_gate`: [ops/verification/preauth-20260922/quality-gate.pending.json](../ops/verification/preauth-20260922/quality-gate.pending.json) — INTENTIONALLY_NONPASSING_OMX_INPUT_TEMPLATE; strict gate not executed
