# RE:Build Agent 실행 계획

상태: v1.1. 최신 UI06과 AI 인증 분리 반영. 전체 goal 미시작; 인증 adapter는 별도 사용자 지시로 구현 중. 17:00/17:30 예정 시각 경과를 실제 제출/Hands-off로 간주하지 않는다.

## 현재 완료된 준비

- [x] 원본 398개 목록·해시 확보. INPUT 191개, EVALUATOR 202개, 루트 자료 4개, 데이터 안내 1개.
- [x] 인수인계 2개·체크리스트·목업·INPUT 규칙·평가 README 읽기.
- [x] P01·P06·N01과 출력 양식 7개·프로젝트 목록, 총 40개 실제 파일 읽기 성공.
- [x] Python/Node/Git/문서 라이브러리·SQLite/FTS5·로컬 HTTP 시험.
- [x] 현재 Codex 원시 세션 로그 복사·JSONL 파싱·SHA-256 일치 시험.
- [x] 이전 대화에서 하네스 후보 OMX·Ouroboros와 실제 행사 일정표 복구.
- [x] OMX 0.21.5 프로젝트 전용 npm 설치 및 Windows 버전 명령 성공.
- [x] OMX 프로젝트 설정·상태/재개 smoke·SPEC과 실행 규칙 연결. doctor 17 통과/3 경고/0 실패, 준비 검증 15 통과.
- [ ] P0 ITB 분석표 준비와 승인된 패키지 설치 완료; 운영진 키 수령 후 LLM 연결 검증.
- [ ] /goal 본문 최종 확인·17:00까지 제출 확인.
- [ ] 17:30 사용자 /goal 입력과 Hands-off 전환.

## 시간별 계획 (KST)

| 시간 | 목표 | 완료 증거 |
|---|---|---|
| 9/21 15:08–15:35 | 자료·실행 환경·로그·하네스 조사 | inventory, 원본 hash, 로그 export manifest |
| 15:35–16:05 | OMX 설정·짧은 상태/실패/재개 시험, 승인된 의존성 준비 | harness smoke, 실제 명령과 제한 기록 |
| 16:05–16:30 | SPEC·필수 제출물 확정, Vercel/영속 저장소·GitHub/Drive 접근 및 키 배포 안내 점검 | 승인 시각·SPEC hash·접근 가능 여부 |
| 16:30–16:45 | Supabase·Provider·로그인 요구 반영 및 /goal 최종본 | 설치/연결 목록, SPEC·GOAL·OMX steering 일치 |
| 16:45–17:00 | /goal 제출 | 실제 접수 확인; 자동 제출로 가정하지 않음 |
| 17:00–17:25 | 마지막 로그·설정·재개·마감 조건 확인 | 준비 검증 PASS, 잠금할 문서 hash |
| 17:30 | 사용자 /goal 입력, Hands-off 시작 | 실제 goal·세션 ID·시각 |
| 17:30–21:00 | P01+N01→ITB XLSX 전체 흐름 | 최초 전체 UI 성공·다운로드 파일 |
| 21:00–9/22 02:00 | 승인/근거 회귀와 첫 웹 데모 배포·영속성·LLM 호출·공개 저장소 검증 | AC01–16·18·20·23–28 증거 |
| 02:00–06:00 | 필수 제출물 초본, 이후 여유가 있으면 확장 | 발표 5페이지 이하·영상 시나리오·로그 연결 |
| 06:00–09:00 | 대형 변경 중단, 공개 데모 회귀·실제 시연 녹화·발표 정리 | AC17–22 자료와 접근 검증 |
| 09:00–10:00 | 기능 동결, 영상/발표·주요 JSONL·필수 링크 준비 | 제출 5종·별도 작업 근거 체크리스트 |
| 10:00–11:00 | 공식 봉인 해제 후 사람 검수 | 시연·출처·파일 확인 기록 |
| 11:00–11:40 | 최종 패키지·로그·실행 안내 정리 | 재개봉/파일 hash 검증 |
| 11:40–12:00 | 제출·접수 확인·백업 | 실제 제출 증빙 |

06:00/09:00/11:00은 내부 운영 제안이다. 17:30 실행, 10:00 봉인 해제, 12:00 제출은 사용자 설명 및 제공 행사 일정표에 근거한다. 봉인 중 예외 개입 허용 범위는 확인되지 않았다.

## 제품 구현 작업 (아직 미구현)

### M1. 승인된 원본 인입과 출처가 있는 변환

대상: `backend/intake.py`, `backend/extractors.py`, `backend/storage.py`, `tests/test_intake.py`, `tests/test_extractors.py`.

- [ ] 승인 전에는 변환·DB 등록이 없고 승인 후에만 처리되는 실패 시험 작성.
- [ ] 원본 bytes·hash·이름을 보존하는 업로드/등록 구현.
- [ ] DOCX 문단/표, XLSX 셀·수식·캐시, PPTX slide/shape, PDF page와 단위가 있는 SourceBlock 추출.
- [ ] 실패·OCR 필요·미지원 입력 격리, 동일 hash의 별칭 처리.
- [ ] AC01–03·10·11·16 통과 기록. 원본 398개 불변 확인.

### M2. 검색·개정·적용성·근거 검증

대상: `backend/search.py`, `backend/reasoning.py`, `backend/evidence.py`, `tests/test_revision.py`, `tests/test_applicability.py`.

- [ ] Rev01 승인과 Rev02 미승인 처리, 정정되지 않은 조항 유지 시험.
- [ ] source block 검색과 조건 비교; 판정별 이유·양쪽 근거·빠진 정보 연결.
- [ ] P01 담수 처리와 N01 염수 조건 차이, 통지기한 28→14일, 미확정 설계 배수량 시험.
- [ ] SourceRef 역조회와 hash 검사. 유효 근거가 없으면 REVIEW_REQUIRED.
- [ ] API 연결 상태/규칙 기반 표시를 분리. AC04–06·12–14 통과 기록.

### M3. 검토·승인·실제 ITB XLSX

대상: `backend/approvals.py`, `backend/exports.py`, `tests/test_approval_export.py`.

- [ ] 승인 전 export 차단, 수정·입력 변경 시 승인 무효화 시험.
- [ ] ITB 양식 8열에 최소 3개 확인된 항목과 근거/검토사항 작성.
- [ ] 승인 버전에 대해서만 실제 파일 생성; 출력 파일명에 원본과 다른 경로 사용.
- [ ] 파일 재읽기·한글/표/원문 근거 표시 확인. AC07–09·16 통과 기록.

### M4. 실제 UI 전체 경로

대상: `frontend/index.html`, `frontend/styles.css`, `frontend/app.js`, `backend/server.py`, `tests/e2e.mjs`.

- [ ] 목업의 프로젝트·지식 자료실·지식조회·근거 패널을 실제 API/상태로 연결.
- [ ] 선택·등록 승인·신규 업로드·Search/AI Insight 상태·비교·검토·승인·다운로드 연결.
- [ ] API 미연결, 처리 중, 입력 없음, 실패, 검토 필요, 승인 상태 표시.
- [ ] 브라우저에서 원문 근거 클릭과 실제 XLSX 다운로드. 재시작 후 재현. AC01–16 전체 평가.

### M5. 기능 확장과 제품 완료 검증

- [ ] P0 통과 후 Risk Register의 근거 있는 강도 후보·출처·검토 상태 검증, 그래프·추가 자료 순으로 진행.
- [ ] N02와 추가 조사 PDF는 별도 신규 프로젝트로 검증. 근거가 늘어도 설계 펌프량을 임의 확정하지 않음.
- [ ] `README.md`, `KNOWN_LIMITATIONS.md`, 시연 순서, 검증 결과, 의존성·라이선스, 로그·세션 인덱스 포함.
- [ ] 제출 패키지에서 키·인증·캐시·가상환경 제외, 원기록 별도 보존.

제품 테스트 파일·명령은 M1에서 실제 생성한 뒤 등록한다. 현재 존재하는 준비 명령과 예정된 제품 명령을 혼동하지 않는다. 매 작업은 관련 실패 재현→최소 구현→검증→STATE/활동 로그 저장 순서다.

## 복구·종료

같은 실패 3회는 원본·변경을 보존하고 해당 작업을 보류한다. P0 회귀는 확장을 멈추고 복구한다. 권한·인증·정책 예외가 필요하면 제한을 기록하고 독립 작업을 계속한다. 마감 또는 실제 완료 시 증거를 보존하고 종료한다. 로그인되지 않은 CLI를 무인 반복 호출하지 않는다.

## 제출 준비 우선순위 보정

- [x] 제출 이미지 원본 보존, D1–D5/E1–E3와 AC17–22 문서화.
- [ ] 17:30 전 GitHub 공개 저장소, Drive 업로드, 데모 호스팅의 사용 가능한 계정·경로 확인. 현재 GitHub CLI 미로그인, Drive·호스팅 접근 미검증.
- [ ] 최초 전체 흐름이 완성되는 즉시 데모 배포와 공개 저장소 재현성을 확인. 후순위 기능에 밀리지 않게 진행.
- [ ] 최대 5페이지 행사용 발표자료와 실제 동작 영상 작성·재생 검증.
- [ ] 실제 /goal 원문·주요 세션 ID 지정; 입력과 최종 결과가 함께 기록된 이후 주요 JSONL export.
- [ ] 제출 화면의 다섯 결과물 및 별도 작업 근거 입력을 각각 확인. `ops/submission-manifest.json`의 상태/링크/hash 갱신.

기존 준비용 ZIP과 로그 스냅샷은 보존한다. 이들은 최종 주요 JSONL이나 다섯 제출물의 대체물이 아니다.

## Vercel·운영진 API 키 준비

- [x] 웹 배포 Vercel 필수 조건 해제·GPT Sites 허용, 운영진 키 수령 대기.
- [x] Vercel 공식 런타임·로컬 SQLite 영속성·본문 크기·Secret 설정 제약 조사.
- [x] 빈 서버 환경 템플릿과 Git/배포 제외 규칙 준비.
- [ ] 봉인 전 Vercel 프로젝트 연결·영속 DB/객체 저장소·키 배포 시각/사용 안내 확인.
- [ ] 키 수령 후 작은 실제 호출 → 출처 검증 → 로컬/배포 동일 응답 계약 시험.
- [ ] Vercel 새 인스턴스·재배포 후 저장/승인 유지와 다운로드 검증. 저장소 연결을 마지막 제출 단계로 미루지 않는다.

공급자·모델·한도·계정 권한·비용 조건은 미확정이다. 현재 키가 없다는 점을 영구적인 API 미사용 결정으로 해석하지 않는다.

## 추가 구현·준비 작업

- [x] 스킬·플러그인 실제 경로/활성 설정 목록과 연결 카탈로그 재확인: docs/CAPABILITIES.md.
- [x] OMX doctor 17 PASS/3 WARN/0 FAIL 재확인; native goal=null. 외부 CLI worker 미인증.
- [x] Supabase DB 확정·배포 후보 Vercel/GPT Sites; Provider·로그인 계약 작성.
- [x] 사내 LLM·SSO 실제 연결은 사용자 결정으로 연기, 설정 기능과 미설정 표시를 이번 범위에 포함.
- [x] 승인된 Python 3.12 환경과 프로젝트 JS 도구 설치·import/version 시험. Python 17 PASS, Node 2 PASS. Vercel CLI 보류.
- [ ] M1에서 Supabase schema·소유권·Storage RLS와 사용자 세션 연결 기반 구성.
- [ ] M2에서 Provider profile·비밀정보 경계·실제 연결 시험과 근거 검증 구현.
- [ ] M4에서 기본 로그인/로그아웃/만료, Provider 설정, SSO 미설정 안내 화면·브라우저 검증.
- [ ] AC25–28 실제 증거 기록. 사내 미연결을 blocker로 올리거나 완료로 둔갑시키지 않음.

추가 기업 연동보다 첫 ITB 흐름과 필수 제출물 완성을 우선한다. 17:00 제출 마감은 변경하지 않는다. 실제 제출 접수·17:30 goal 입력·계정 인증을 자동 완료로 가정하지 않는다.

## 신규 업로드 시연 우선순위

- [x] 신규 지시를 SPEC AC29–30·GOAL·하네스 계획·제출 확인 기준에 반영.
- [ ] P01/N01 개발 기준선 다음, 후순위 기능 확장 전에 DB 미등록 신규 자료로 전체 경로 검증.
- [ ] 지원 형식의 별도 합성 파일과 내용 변경본 준비; 기존 원본 및 평가 정답과 분리.
- [ ] 업로드 전 hash 부재 → 실제 업로드·변환·기존 근거 연결 → 검토·승인 → XLSX 다운로드 증거 기록.
- [ ] 수치·단위·계약/현장 조건 변경 시 비교/초안 갱신, 미연결 근거는 REVIEW_REQUIRED, 입력 변경 시 재승인 검증.
- [ ] 배포본과 영상에서 같은 신규 업로드 흐름 검증. 녹화 재시도 시 이미 처리된 입력은 신규라고 표시하지 않고, 미등록 새 입력으로 시연하거나 재실행임을 명시.

최신 기준이 저장된 P01/N01 결과만 사용하는 시연보다 우선한다. 업로드 화면을 구현했다는 사실만으로 합격하지 않는다.

## 제출 역할 후속 반영

- [x] 준비된 저장소 https://github.com/Ki-rak/REBUILD_RALPH의 public 상태 확인.
- [ ] 로컬 Git 연결·게시할 파일 선별·인증 확인 후 해당 저장소에 구현 코드 게시.
- [ ] Vercel 실제 배포와 신규 업로드 흐름 검증 후 D2 URL 기록.
- [ ] 에이전트: 실제 시연과 영상/파일 준비. 사용자: Google Drive 직접 연결 후 진행. 최종 영상 링크와 접근 확인 전 D3는 대기.

## 완료 판정 정정

제품 완료는 기능·데이터 정확성·반복 사용 가능성의 검증으로 판정한다. 배포 URL, 녹화, 발표자료, GitHub 게시와 행사 제출 준비는 별도 운영 작업이며 제품 완료를 대체하거나 제품 완료 판정에 섞지 않는다. ITB XLSX는 첫 구현 단계다. 그 성공이나 한 번의 시연만으로 프로그램 전체가 완성됐다고 선언하지 않는다. 확정된 기능을 구현·검증하고 후속 결과물·그래프의 진행 상태도 구별해 보고한다. 미구현 기능을 완료한 것으로 처리하지 않는다.

제품 작업: M1–M4 전체 기능과 AC01–16·AC23–38 검증, M5 결과물·그래프 확장 및 기능별 최종 판정. 행사 작업: Vercel·GitHub·영상·발표·세션 제출은 별도 ops/submission-manifest.json에서 추적한다. 행사 작업 대기 중에도 제품의 구현·수정·검증을 계속한다.

## UI·결과물 확정 범위 반영

- [x] 동료 질문별 적용 결정을 docs/UX_DECISIONS.md에 기록.
- [ ] 프로젝트 선택·6개 좌측 메뉴·지식조회 메인 탭·데이터 관리 자동 처리 구현.
- [ ] 공통 양식 버전·자료실 범위/원본 열기·실근거 관계 탐색 구현.
- [ ] ITB 주요정보/과거 이슈 → Risk Register 근거/강도 검토 → 5장 심의 초안·승인 PPTX.
- [ ] AC31–38 및 기존 새 입력·승인·영속성 검증. 화면 설계안은 기능 검증 PASS로 집계하지 않음.

- [x] 수정 화면안 docs/ui-review/index.html 작성·브라우저 10개 확인 통과. 모바일 메뉴 숨김 문제 복구. 이는 설계안 확인이며 제품 기능 AC31–38 합격은 아직 아님.


## 최신 사용자 확정 (2026-09-21, /goal v1.0)

GOAL.md와 ops/GOAL_INPUT.txt의 자체 완결형 원문이 현재 실행 계약이다. 필요한 프로젝트 범위 오픈소스·스킬·플러그인 설치는 이번 지시로 승인됐으며 개별 재승인 없이 설치·버전 기록·구동 검증한다. 각 의미 있는 작업 단위는 검증 후 로컬 Git 커밋하고 실패 체크포인트는 구분한다. Supabase 실제 DB/Storage/Auth/RLS 연결 검증은 필수다. 배포·공개 게시·데모/영상/발표자료·행사 제출은 추후 사용자 요청까지 실행 범위에서 제외한다. 제품 기능 완료까지 OMX 구현→실행/검토→실패 수정→재검증→기록/커밋/체크포인트 루프를 계속한다. 이 문단과 현재 사용자 지시가 이전 설치 승인·배포 운영 문구보다 우선한다.


## UI 수정 06 — 최신 사용자 지시

현재 UI 계약은 docs/UX_DECISIONS.md와 docs/ui-review/index.html이다. 지식조회로 명칭을 변경하고, 새 프로젝트 이름 아래 파일 업로드를 제공한다. ITB 분석표·심의장표·Risk Register의 초안·근거·검토·승인 흐름을 유지한다. 지식 자료실은 목록/관계 보기 전환 없이 기본 지식 연결 노드와 과거↔신규 비교 설명을 함께 보여준다. 데이터 관리에는 과거 프로젝트/문서 보유량과 새로 유입된 문서를 표시하고 실패/처리중 KPI와 등록 대상 섹션은 제거한다. 폴더 자료 확인·승인은 별도 작업에서 유지한다. 실제 양식 폴더는 data/REBUILD_INPUT_v1/REBUILD_INPUT_v1/03_OUTPUT_TEMPLATES이며 제공 7종을 표시한다.

이번 요청은 UI 수정이다. GOAL.md·ops/GOAL_INPUT.txt·OMX 목표는 사용자 요청에 따라 수정하지 않았으며 후속 /goal 개정 시 최신 UI 계약을 반영해야 한다. 기존 goal의 명칭·화면 지시보다 이번 UI 지시가 우선한다. 이 시안은 백엔드·Supabase·LLM·최종 파일 생성 완료의 증거가 아니다.

UI 06 검증 완료: 브라우저 38개 PASS / page error 0, 실제 양식 7개 byte 일치, 원본 무결성 PASS, GOAL/OMX 계획 hash 불변. 준비 점검의 공통 Codex 설정 기준선 차이는 별도 기록하며 UI 성공으로 덮어쓰지 않는다.


## v1.1 실행 인계와 남은 실제 작업
- [x] UI06 및 두 AI 인증 경로를 /goal 본문에 반영. 본문 4,000자 이하. 원본 보존.
- [x] 공식 SDK/인증 문서와 설치 가능한 스킬·플러그인 상태 확인; OpenAI 문서/UI/검증 스킬 프로젝트 로컬 복사.
- [ ] server/ai adapter 검증·독립 리뷰·로컬 작업 커밋 (결과는 STATE와 작업 로그 참조).
- [ ] 공식 로컬 Codex OAuth 로그인 후 실제 호출; 배포용 key adapter 실제 호출. 준비·모의 검증과 구별.
- [ ] 실제 제품 인입·추출·근거·Supabase DB/Storage/Auth/RLS·세 결과물·Provider 설정 화면에 연결.
- [ ] 서로 다른 신규 업로드 E2E, 재사용/복구/권한/승인 무효화, 최종 strict 검토.
- [ ] 사용자가 실제 /goal 입력하면 현재 시각/남은 시간에 맞춰 순서 조정. 이후 하네스 루프를 기능 완료까지 수행하되 마감만으로 완료 판정을 바꾸지 않음.

검증 명령: `npm --prefix server/ai test`, `npm --prefix server/ai run status` (로그인 상태만), `npm --prefix server/ai run smoke` (실제 호출 시험; 존재/사용법은 server/ai README 확인). 전체 제품 E2E는 구현 후 실제 명령을 추가한다. 준비 검증 `python -X utf8 ops/verify_preparation.py`는 전체 제품 검증이 아니다. 기존 global config baseline 불일치는 해결 전까지 실패로 유지한다.


## 실제 goal 개발 체크포인트 (2026-09-21 21:00 이후)
- [x] 실제 goal 첨부 원문 보존 및 OMX G001 실행 시작. native objective 일치.
- [x] 공식 AI adapter 인증 분리·오류/시간제한·근거 검증 (abcbf58). 배포용 실제 Responses 최소 호출 성공.
- [x] 원문 추출·조항별 정정 비교·세 형식 Office 출력 기초 (ddd5041).
- [x] 신규 업로드→원본/MD/JSON→근거→초안→수정/승인→실제 XLSX의 주입 저장소 통합시험.
- [x] 서버 전용 키로 인입/추출/승인 서명, 승인 DB버전 귀속, 원자 승인 RPC 준비.
- [ ] 독립 코드 리뷰 수정 재검토, 실제 브라우저 출력 재검증.
- [ ] Supabase migration 실제 적용, 두 사용자 DB/Storage RLS·지속성 검증. REST404는 미통과.
- [ ] 공식 로컬 Codex OAuth 로그인 및 실제 제품 호출. CLI 미로그인 상태.
- [ ] cleaner/전체 회귀/독립 architecture+code review/OMX strict gate.
- [ ] 실제 rotated JSONL 구간별 내보내기와 goal 입력/최종 결과 확인.

검증: .venv/Scripts/python.exe -X utf8 -m pytest tests -q; npm --prefix server/ai test;
node tests/ui/browser_flow.cjs; .venv/Scripts/python.exe -X utf8 tests/ui/browser_workbook.py;
.venv/Scripts/python.exe -X utf8 ops/runtime/supabase_live_verify.py.
브라우저 fixture는 TEST_STORAGE_INJECTED이며 실제 Supabase 성공 증거가 아니다.
제품 서버 루프백8780, 격리 시험8782. 실제 배포·공개 푸시는 이번 goal에서 제외한다.

## Review repair checkpoint 2026-09-21T21:44:54.317822+09:00
- [x] Rotated actual logs independently preserved (aec81c3); final-session qualification remains pending.
- [x] Five editable slides/literal Excel strings/auth cleanup (818ab03), targeted24PASS.
- [x] Actual deployed usage retained, AI31PASS.
- [ ] Independent architecture12 findings closure and UI zero-state/restart checks.
- [ ] Template version registration/selection/approval protection final UI+retry checks.
- [ ] Live Supabase and local OAuth; full cleaner/review/strict completion evidence.

## Current implementation checkpoint 2026-09-21T22:32:41.554129+09:00
- [x] CR01 source-snapshot race and CR02 project/mode/query leakage repaired and independently checked.
- [x] Python108, AI31, frontend dynamic7 PASS; browser26/Office16 and mixed-upload10 PASS with TEST_STORAGE_INJECTED.
- [x] User-bound immutable template versions, exact5slide editable flow, dirty approval guard, persisted draft reopen and real source graph verified in injected storage.
- [x] Actual isolated Supabase Auth login/refresh/logout-revocation; test users cleaned.
- [x] Actual deployed OpenAI product draft usage305/1263/1568 and output reopen; storage and reviewer explicitly synthetic.
- [x] Three real active-session snapshots separately exported:1782/32/2751 events; no merged or synthesized records.
- [ ] Presentation layout check at realistic input volume; structural content checks alone do not prove no overflow.
- [ ] Actual Supabase DB/Storage/RLS/restart: prepared SQL requires authenticated management access. Latest verifier PENDING_SCHEMA.
- [ ] Official local OAuth login/inference: latest official status NOT_LOGGED_IN.
- [ ] Final architecture/OMX strict completion gates after all mandatory live checks. Product remains incomplete.

Current commands: .\ops\python.ps1 -m pytest tests -q; npm --prefix server/ai test; node tests/ui/frontend_errors.cjs; node tests/ui/frontend_context.cjs.
Browser and mixed-upload test setup: tests/ui/browser_README.md. Actual service setup and verification: supabase/README.md and docs/RUNBOOK.md.
These current entries supersede stale preparation status above without erasing its history.

## Current acceptance checkpoint — 2026-09-22 00:29 KST

- [x] Condition display role separation and unrated/text-risk preservation:74cef85; mixed allowance/design classification:af35dfb. Independent scoped review closed.
- [x] Provider profile edit/project selection, configuration-race rejection, settings context and mobile hash layout:0344d74. Actual Provider6/mobile9 on owned8784 fixture; context9/errors3PASS.
- [x] Owned browser target URL/run ID and constrained pytest collection:5bf3e7b. Independent boundary6 and root4PASS. AC01/30/32 additional side-effect/freshness/unrelated-source testsPASS.
- [x] Fresh product137PASS (two existing deprecation warnings); owned8785 UI26 and Office16PASS after initial XLSX detail repair. TEST_STORAGE_INJECTED throughout browser evidence.
- [ ] Long XLSX visual verification and independent preservation review; inspect Risk output as well as ITB. Do not declare this complete from structural tests alone.
- [ ] Supabase authenticated SQL migration, user-JWT DB/Storage RLS, whole new-upload flow and process-restart persistence. Plugin directory still DISABLED_BY_ADMIN/NOT_AVAILABLE; in-app dashboard redirects to sign-in. Existing secret/publishable product keys are not SQL-management credentials.
- [ ] Project-local official Codex OAuth login and actual inference. Latest status NOT_LOGGED_IN/NOT_TESTED; no key fallback or Desktop token copying.
- [ ] Final independent review/cleaner/regression and OMX strict gate after all required evidence. Native goal remains active; OMX G001 in_progress,4pending,0complete.

Current browser commands are maintained in tests/ui/browser_README.md. Default `python -m pytest -q` now collects only tests. Exported raw segments remain separate1782/32/4576events at the latest00:16 checkpoint; active snapshots, not final submission evidence. Original398hashes unchanged. Deployment/public push/event preparation remain excluded until requested.