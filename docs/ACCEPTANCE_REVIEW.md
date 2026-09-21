# RE:Build Agent 독립 완료 기준 검토

2026-09-21 23:24 KST, /root/acceptance_architecture 읽기 전용 검토. 아래는 루트가 전달받은 판정을 요약 기록한 것이다. 기준은 8109130 및 당시 작업 파일, SPEC AC01–16/23–42와 실제 ops/runtime/GOAL_ENTERED.md다. 원래 결론은 **BLOCK**이며 코드 구현과 실서비스 검증을 구별한다. EVALUATOR·holdout·비밀 파일은 읽지 않았다.

## 검증 근거

- B26: ops/runtime/browser-report-2026-09-21T14-13-43-951Z.json — 실제 UI·파서·분석·승인·세 형식 출력, TEST_STORAGE_INJECTED.
- O16: ops/runtime/browser-workbook-20260921T141513Z.json — 16개 원문/편집/출처/양식 재개봉 확인.
- M10: ops/runtime/browser-mixed-upload-2026-09-21T13-28-04-176Z.json — 정상/손상 혼합 업로드, 원본 보존, 실패 재처리.
- S9: ops/runtime/browser-slide-limits-2026-09-21T14-15-04-961Z.json — 승인 전 상세 보기, 분량 거부, 승인본 보존. 출력 검증과 별도다.
- 실제 Auth: ops/runtime/product-auth-live-20260921T133655Z.json — 로그인/본인/갱신/로그아웃/갱신 폐기/오인증 거부. DB/Storage 성공은 아니다.
- 실제 private bucket: ops/runtime/supabase-bucket-configuration-20260921T135051Z.json — 비공개 생성·확인. 사용자 RLS는 미검증.
- 실제 OpenAI: ops/runtime/product-openai-usage-20260921T124924Z.json — input305/output1263/total1568, 근거와 출력 재개봉. 저장소와 승인만 시험용이며 OAuth 성공은 아니다.
- 원본: ops/runtime/original-integrity-current.json — 398개 변경/누락0, 내용 지식화 없이 hash만 대조.
- 로그: ops/runtime/latest-export-summary.json — 실제 세 구간 별도 보존, 마지막3499건 당시 활성 스냅샷. 최종 결과가 포함된 제출 로그로 판정하지 않음.

## 수용 기준별 남은 범위

| 기준 | 로컬 증거 | 최종 미완료 범위 |
|---|---|---|
| AC01 | server import approval, test_api 승인 거부 | 허용 파일 승인 전후 side-effect 검증 보강, 실제 DB/Storage |
| AC02–03 | test_api byte/hash, test_extraction DOCX/XLSX/PPTX/PDF 위치/표/수식 | 실제 Storage 인입 검증 |
| AC04–05 | test_analysis 실제 P01/N01·조항별 정정·값/단위 구분 | 출력의 표시 우선순위 보완 |
| AC06–08 | test_security/test_api 위조·근거·승인 무효화, B26/S9 | 실제 DB 원자 승인, 중첩 PPTX 근거 재검토 |
| AC09 | O16 및 test_exports 내용/링크 재개봉 | 긴 한글 XLSX의 실제 가독성 렌더 |
| AC10–12 | 중복/변경 시험, M10 오류 격리 | 실제 저장소 재실행 |
| AC13–14 | 규칙 경로, AI 오류 표시, INPUT allowlist 차단 | 모의 시험을 실인증으로 표시하지 않음 |
| AC15/24 | B26 새로고침 | 서버 재시작·새 세션 후 실제 Supabase 복원은 미통과 |
| AC16 | 원본 hash, 원시 로그와 활동 로그 | 최종 로그 export는 종료 시 수행 |
| AC23/40 | 실제 deployed OpenAI 호출+usage+근거 | 전체 live 흐름 및 OAuth와 구별 |
| AC25 | 신규 프로필 저장·상태/시험 | 기존 프로필 편집/선택·프로젝트 구성 미구현 발견 |
| AC26–27 | 실제 Auth HTTP, SSO 구성 미설정 UI | 실제 브라우저 세션 복구 보강; 회사 IdP 연결은 제외 |
| AC28–29 | 소유권 fixture/B26 신규hash 부재→출력 | 실제 두 사용자 DB/Storage RLS 및 신규 전체 흐름 미통과 |
| AC30–32 | 입력 변경·프로젝트 귀속·M10 | 무관 자료 연결 없음, 데이터 최신 상태 분기 보강 |
| AC33 | 모드/질의/프로젝트 맥락 | Search UI scope=all 고정 발견 |
| AC34 | immutable template 테스트, B26/O16 | 실제 Supabase 영속성 |
| AC35–37 | 세 형식·강도 표본·편집/승인 | 주요 조건 발췌 우선순위, PPTX PL01/PL03, 실제 출력 가독성 |
| AC38 | 실제 row/source/edge 관계, B26 | 실제 신규 업로드 반영은 AC29와 결합 |
| AC39/41 | 공식 OAuth SDK·최소 환경·무fallback/오류 시험 | 실제 프로젝트 OAuth 로그인·호출 미통과 |
| AC42 | 고정 의존성·로컬 commits·원시 로그·독립 검토 | 최종 cleaner/회귀/아키텍처/실제 OMX strict gate |

## 독립적으로 진행할 수정

1. AC33: all/current/historical 선택, scope까지 결과 맥락에 포함, 지연 응답 폐기, 모드 간 선택 유지.
2. AC25: 사용자 소유 프로필의 편집·프로젝트 선택. 회사 adapter 연결 제외와 환경별 OpenAI 인증 고정 유지. 미연결 구성을 실제 호출 성공으로 표시하지 않는다.
3. 모바일: 기존390px 증거는 settings 화면뿐. 프로젝트 생성/업로드·근거 열기·편집/승인·다운로드의 핵심 조작을 확인한다.
4. AC35/37: analysis의 파일/셀 순서 누적→_display 선두12→장표 선두100units 때문에 실제14calendar 승인 조항보다 위험 검토행과 수식이 먼저 보인다. 허위 확정은 아니나 주요 정보 전달 부족이다. 효력 판정은 유지하고 표시용 역할을 구분해 승인 조항·수치/단위 조건을 우선하고 참고 위험 기록을 분리한다. 프로젝트명/파일명 고정 분기나 근거 삭제는 금지한다.
5. AC01/32/30의 승인 전후 side effects, 최신 상태 분기, 무관 근거 없음 검증과 XLSX/PPTX 실제 렌더를 보강한다.

## 외부 선행 조건과 판정

실제 rb_entities 스키마가 없어 승인된 SQL 관리 연결로 prepared migration 적용이 필요하다. 제품 secret/publishable key는 SQL 관리 인증이 아니다. 이후 두 사용자 RLS·업로드·재시작 복원을 검증한다. 공식 전용 Codex 로그인 후 실제 로컬 제품 호출도 필요하다. Desktop 토큰 복사나 API-key fallback은 금지한다.

기존 AR01–12의 scoped 수정은 유지하지만 전체 CLEAR로 확대하지 않는다. 독립 작업·필수 실연결·출력 품질·최종 게이트가 모두 통과하기 전 제품 완료가 아니다. 이 아키텍트는 새 브라우저/시험 실행이나 이미지 도구 시간초과 후 독립 이미지 판정을 주장하지 않았다.

## 검토 이후 변경 기록

- 838b901: 장표 PL01/PL02/PL03의 코드 결함을 재검토하여 scoped closure. Python119, 독립28 PASS. 마지막 렌더와 계약조건 우선순위는 별도다.
- e7f8cca: AC33 범위 선택 구현. 실제 신규 현재/과거 UI 업로드 기반 browser7, context6/errors3 PASS. TEST_STORAGE_INJECTED.
- AC25 및 주요 계약조건 표시, 모바일 검증은 진행 중이다. 위 원래 BLOCK 판정을 덮어쓰지 않는다.

## Acceptance follow-up — 2026-09-22

AC01/30/32 additional injected-storage tests now prove approved intake ordering/no pre-approval side effects, freshness under local mutation/failure/auth loss, and no unrelated historical connection. AC25 profile edit/project selection and both backend/frontend configuration races are implemented and independently closed; actual Provider browser6PASS. AC33 scope selection is committed. Core390px upload/source/edit/approval/download mobile9PASS. Role-based primary conditions and mixed allowance/design labels preserve source values while requiring review; independent31PASS.

Fresh bounded product collection137PASS, owned8785 browser26 and Office16PASS. These do not resolve actual Supabase persistence/RLS or local OAuth. XLSX render review found fixed-height clipping; the detail-sheet repair has an open reviewer finding about per-item supplemental SourceRef association and a remaining CJK wrapping concern. Keep output-quality gate open until repairs and fresh renders are inspected.

Supabase plugin recheck is DISABLED_BY_ADMIN/NOT_AVAILABLE, available dashboard unauthenticated; official dedicated Codex CLI says NOT_LOGGED_IN. Final strict gate stays pending. Product remains incomplete.
## Output review follow-up — 2026-09-22T01:09:54.763632+09:00

AC09/35–37 scoped readability and per-item source preservation findings closed after actual ITB/Risk renders, all actual deck pages across documented root inspections, CJK boundary slide, independent4/probe + final3PASS. Product140/browser26/Office16PASS, browser persistence injected. Original overall BLOCK remains: actual Supabase DB/Storage/RLS/restart, official local OAuth and final live-dependent strict review are not completed.
