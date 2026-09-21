# RE:Build Agent 스킬·플러그인·하네스 점검

점검 시각: 2026-09-21 16:27–16:29 KST. 파일 존재, 설정 활성화, 계정 연결, 실제 실행을 구별한다. 상세 경로 목록은 `ops/preflight/capability-inventory.json`, 연결 재점검은 `ops/preflight/integrations-recheck.json`에 보존했다.

## 재사용할 설치 항목

| 용도 | 확인된 스킬/플러그인 | 상태와 이번 사용 |
|---|---|---|
| 명세·계획·검증 | brainstorming, writing-plans, systematic-debugging, test-driven-development, verification-before-completion | 기존 SKILL.md 존재. 명세·검증 절차에 재사용 |
| UI | ui-ux-pro-max, ui-styling | 기존 설치, 제품 화면 구현 시 사용 |
| 브라우저 검증 | playwright-skill, browser, unified-computer-use | 기존 설치/도구 노출. 제품 E2E는 아직 미실시 |
| Office/PDF | documents, spreadsheets, presentations, pdf | 번들 스킬·런타임 존재. 실제 40개 자료 읽기 완료 |
| 공식 문서·설치 관리 | openai-docs, skill-installer, plugin-management, agent-reach | 기존 설치 재사용, 중복 설치 불필요 |
| 작업·로그 | codex-app-tools | 현재 작업 도구 사용 가능. raw JSONL export는 별도 로컬 유틸리티로 검증 |
| 선택 항목 | template-creator, visualize | 로컬 활성화. 이번 핵심 구현의 필수 의존성 아님 |

전체 검색에서 SKILL.md 경로 86개를 찾았다. 동일 스킬의 사용자/번들 중복 경로를 포함하므로 서로 다른 활성 스킬 86개라는 뜻은 아니다. 필요한 문서·UI·검증 스킬은 이미 있고 추가 필수 스킬 설치는 현재 없다.

OMX 프로젝트 스킬 22개: ai-slop-cleaner, analyze, ask, autopilot, autoresearch, best-practice-research, cancel, code-review, configure-notifications, deep-interview, design, doctor, hud, omx-setup, performance-goal, plan, ralplan, skill, ultragoal, ultraqa, visual-ralph, wiki. 프로젝트 prompt 31개, agent TOML 17개도 존재한다. 설치가 모든 스킬의 자동 활성화나 실행 성공을 뜻하지 않는다.

## 외부 연결 플러그인

| 연결 | 현재 재조회 결과 | 대응 |
|---|---|---|
| Supabase | installed=false, DISABLED_BY_ADMIN, NOT_AVAILABLE | 제품 SDK/API와 계정 연결 경로 준비 |
| Vercel | installed=false, DISABLED_BY_ADMIN, NOT_AVAILABLE | CLI 또는 서비스의 일반 배포 경로 준비 |
| GitHub | 카탈로그 연결 불가; 로컬 enabled=true와 불일치 | 로컬 설정만으로 연결됐다고 보지 않음. gh CLI도 미인증 |
| Google Drive | installed=false, DISABLED_BY_ADMIN, NOT_AVAILABLE | 실제 업로드 가능한 계정·브라우저 경로 미검증 |

이는 플러그인 카탈로그의 관리 정책 상태이며 이번 작업의 자동 승인 검토에서 거절된 결과는 아니다. 관리자 정책을 변경하지 않는다. 플러그인 연결 없이도 제품의 정식 SDK/서비스 계정 경로를 준비할 수 있으나 현재 인증됐다고 가정하지 않는다.

로컬 MCP 설정에는 ruflo, google-stitch, node_repl 이름이 있다. 이름 존재만 확인했으며 실제 연결 상태를 보장하지 않는다. 이번 하네스는 OMX로 유지한다. claude-mem 두 설정과 chrome 플러그인은 로컬 비활성 상태다.

## 하네스와 서비스 실행 상태

| 항목 | 확인 결과 |
|---|---|
| OMX | oh-my-codex 0.21.5, 프로젝트 전용 설치 완료 |
| Windows 런타임 | 실행됨. Windows identity timeout 수정과 원본/hash 보존 |
| doctor 재실행 | 17 PASS / 3 WARN / 0 FAIL |
| 경고 | native hooks 비활성, 자체 AGENTS에 OMX marker 없음, 현재 Desktop 세션의 OMX launch pointer 없음 |
| 상태 저장·재개 | 별도 프로세스에서 저장 계획 재읽기 성공 |
| 안전한 실패 | 활성 native goal 없이 완료 checkpoint 시도 거부, 계획 불변 |
| 현재 실행 | native goal=null, 본 계획 5개 모두 pending/attempt=0 |
| 별도 CLI worker | Codex CLI 미로그인; 실행·밤샘·자동 재시작 미검증 |
| 제품·배포 | 제품 구현 전. Vercel/Supabase CLI 없음, 관련 환경변수 없음, 연결·실제 배포 미검증 |

## 추가 준비 대상

사용자가 설치를 위임한 OMX는 완료했다. 제품용 Python 가상환경·라이브러리와 Supabase/Vercel 관련 의존성은 사용자가 승인한 목록 `docs/DEPENDENCIES.md`로 관리한다. 운영진 키와 서비스 인증은 설치와 별개의 준비 조건이다. 최신 사용자 승인에 따라 Python 패키지 54개와 Supabase JS SDK·esbuild 설치·실행 검증을 완료했다. Vercel CLI는 보류했다.

사용자가 Supabase의 ChatGPT 연결과 프로젝트 생성을 알린 뒤 다시 조회했으나 이 Codex 세션의 카탈로그 결과는 여전히 DISABLED_BY_ADMIN/NOT_AVAILABLE이다. Sites 도구와 스킬은 노출되지만 실제 등록·배포는 아직 미실시다.


## v1.1 재검토 (2026-09-21)
- 프로젝트 .codex/skills에 기존 OMX 22종을 유지하고 openai-docs, ui-ux-pro-max, verification-before-completion을 기존 로컬 원본에서 복사했다. 출처 경로·SKILL.md SHA-256: ops/preflight/skills-local-v11.json. 다음 턴부터 프로젝트 스킬 탐색에 사용 가능하며 이번 턴은 파일을 읽어 적용했다.
- Supabase·OpenAI Developers·Superpowers 플러그인 카탈로그는 DISABLED_BY_ADMIN/NOT_AVAILABLE, 미설치다. 사용자 연결 주장과 이 세션에서의 호출 가능성을 구별한다. 정책 우회 없이 공식 SDK와 로컬 스킬을 사용한다.
- server/ai에는 공식 Codex SDK/CLI를 프로젝트에 버전 고정 설치한다. 상세 버전/구동/제한은 해당 package-lock.json과 README, 검증 보고서에 남긴다. 기존 Python 54개 패키지, Supabase JS, esbuild, Pretendard는 재사용한다.
- OMX는 개발 하네스이며 제품의 OAuth inference용 CLI와 별개다. 설치된 CLI가 로그인되었다거나 밤샘 실행이 검증됐다는 의미가 아니다.

## Actual development update 2026-09-21T22:32:41.554129+09:00

Earlier preparation tables are historical. Current native goal is active; OMX G001 is in progress and no story/native completion is claimed. OMX0.21.5 is project-local and npm dependency inspection passes. Official Codex SDK/CLI0.155.1 and Playwright1.62.1 are pinned project dependencies. Python108/AI31 and actual browser checks pass in their documented scopes.

Git main publication87ed14a was completed only after user approval. Subsequent product commits stay local on goal/product-implementation. Actual OpenAI server-key product call passed; local official OAuth remains NOT_LOGGED_IN. Actual isolated Supabase Auth login/refresh/logout-revocation passed; DB schema/private storage/RLS/persistence remain pending. No callable Supabase management tool was found in this session. Existing application keys do not substitute for SQL-management credentials.

Windows Python redirector stalls were recovered with ops/python.ps1 using the configured base runtime and project site-packages. Original runtime and user-wide settings remain unchanged. Remaining auth/management prerequisites are recorded in STATE.json; installation alone is not a successful service connection.

## Recheck 2026-09-22

Supabase plugin directory still returns installed=false, DISABLED_BY_ADMIN and NOT_AVAILABLE. The project dashboard in the available in-app browser redirects to sign-in. No management token or database password was extracted, and administrator policy was not changed. Recovery requires an approved authenticated SQL-management connection. Existing real Auth/private bucket evidence remains valid; DB schema/RLS/restart are pending.

Official dedicated Codex status runs and returns NOT_LOGGED_IN with inference NOT_TESTED. Product137 regression tests and owned-fixture browser26/Office16, Provider6/mobile9 pass within documented synthetic-storage boundaries. OMX aggregate goal remains active/G001in_progress. No new dependency was installed during these repairs.