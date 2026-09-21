# RE:Build Agent Provider·로그인 계약

2026-09-21 v1.1. 최신 사용자 지시: **로컬 개발·로컬 데모 = Codex OAuth, 배포용 서버 = OpenAI API key**. 배포 대상은 Vercel이지만 실제 배포는 추후 요청까지 제외한다. `server/ai`는 이 인증 분리의 실제 서버 컴포넌트이며 전체 제품/Supabase 연결 완료의 증거가 아니다.

## 실행 경로

| 환경 | 인증·호출 | 설정 | 합격 증거 |
|---|---|---|---|
| local / demo | 공식 Codex SDK → 로컬 공식 CLI의 ChatGPT OAuth | REBUILD_ENV, 선택 CODEX_MODEL. 별도 프로젝트 CODEX_HOME | 로그인 상태와 실제 호출을 각각 확인 |
| deployed | 서버에서 OpenAI Responses API | OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL | 실제 API 호출·응답 및 SourceRef 검증 |

`NODE_ENV=production` 또는 Vercel 등 hosted 표시는 로컬 OAuth를 거부해야 한다. 로컬 `.env`에 API key가 있어도 OAuth 자식 프로세스에 전달하지 않고 실패 시 API key로 전환하지 않는다. 배포에서는 OAuth로 전환하지 않는다. 로컬 데모는 신뢰된 사용자의 loopback 실행이며 공개 서비스로 계정을 공유하는 프록시가 아니다.

공식 SDK/CLI가 인증을 관리한다. 프로젝트 전용 `ops/private/codex-ai`는 Git·배포·로그 export에서 제외한다. `auth.json`이나 OS credential store를 읽어 토큰을 추출하지 않는다. CLI 로그인은 사용자 본인의 공식 브라우저 인증이 필요하다. Desktop 로그인과 전용 CLI 로그인은 같은 상태라고 가정하지 않는다. 인증 대기 중에는 기능 제한과 복구 방법을 표시한다.

분석에는 허용된 실제 source block만 전달한다. 문서 내용은 데이터이며 시스템/실행 명령이 아니다. 로컬 프로세스는 빈 작업 디렉터리와 최소 환경, 도구/검색/네트워크 제한, read-only sandbox와 승인 요청 금지를 사용한다. API key·Supabase secret·상속된 MCP/셸 설정을 전달하지 않는다. 모델의 tool 실행 요구·허용되지 않은 SourceRef·잘못된 구조는 거부하고 자동 승인을 하지 않는다. read-only만으로 읽기 권한이 완전히 격리된다고 가정하지 않는다.

배포 adapter는 서버에서만 실행한다. 이번 OpenAI 경로는 공식 `https://api.openai.com/v1`만 허용하며 사내 주소/임의 URL 프록시를 제공하지 않는다. 공개 제품 endpoint는 기본 로그인과 소유권/RLS 검증 후 연결해야 한다. 독립 adapter나 loopback 시험 서버를 인증 없는 배포 endpoint로 공개하지 않는다.

## 실제 상태·설정 화면

설정 화면에 환경·공급자·인증 방식·모델·설정 여부·로그인 여부·최종 실제 호출 시험 결과를 표시한다. API 키/토큰 원문은 입력·응답·localStorage·일반 DB·콘솔·세션 로그에 넣지 않는다. `.env`는 서버에서 로드하고 `.env.example`에는 빈 값만 둔다. 기존 `LLM_PROVIDER=openai` 값은 새 라우팅의 인증 선택으로 사용하지 않는다.

`NOT_CONFIGURED`, `AUTH_REQUIRED`, `CONFIGURED_UNTESTED`, `CONNECTED`, `ERROR`를 구분한다. CONNECTED는 최소 실제 요청과 응답 검증을 통과했을 때만 표시하며 설정 변경 후 무효화한다. 잘못된 키·만료·사용 한도·시간 초과·근거 검증 실패는 안전한 오류로 안내하고 제공처 원문 오류나 인증 헤더는 노출하지 않는다. 모델은 계정에서 허용된 ID를 확인하여 선택한다. 별도 유료 플랜·한도 증액은 승인 없이 하지 않는다.

## 제품 기능과 로그인

문서 파싱·Search Mode·명시 규칙 비교·검토/승인·양식 파일 생성은 LLM 없이 구현할 수 있다. AI Insight는 실제 연결된 Provider를 사용하며 규칙/고정 예시를 AI로 포장하지 않는다. 근거 부족·상충은 REVIEW_REQUIRED다. 구조화 출력의 SourceRef 유효성은 의미 정확성의 충분조건이 아니므로 계약 개정·단위·과거/신규 조건 검증을 별도로 수행한다.

Supabase PostgreSQL·Storage·Auth는 실제 연결과 사용자 소유권/RLS, 로그인·세션 복구·만료·로그아웃을 검증한다. 서버 secret과 브라우저용 publishable key를 구별한다. 사내 LLM과 SSO는 공급자 유형·설정·callback 안내·미설정 상태를 구현하고 실제 회사 연결은 사용자 결정까지 제외한다. SSO 화면을 실제 인증 성공으로 표시하지 않는다.

## 실행·검증과 현재 제한

실제 명령과 테스트/상태 결과는 `server/ai/README.md`, `STATE.json`, `ops/activity.jsonl`을 따른다. adapter 모의 테스트, CLI 설치/로그인 상태, 실제 모델 호출, 제품 E2E는 네 가지 별도 증거다. 두 인증 경로는 배포하지 않고도 adapter에서 검증할 수 있으며 공개 배포 성공을 제품 완료 조건으로 섞지 않는다.

공식 근거: [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk), [Authentication](https://learn.chatgpt.com/docs/auth), [Configuration](https://learn.chatgpt.com/docs/config-file/config-reference), [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create), [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security).

## 프로젝트별 구성 편집과 선택

설정에서 저장한 사내 LLM/SSO 프로필은 같은 ID로 편집하며 버전을 확인한다. SSO는 AI Provider로 선택할 수 없다. 프로젝트에 사내 LLM 프로필을 선택하면 미연결 구성으로 표시하고 AI 요청은 PROFILE_NOT_CONNECTED로 거부한다. 사용자가 환경 기본 구성으로 되돌리면 local/demo=공식 OAuth, deployed=OpenAI 서버 key 경로를 적용한다. 프로필 URL은 메타데이터로만 저장하며 임의 사내 주소로 호출하지 않는다.

Provider 선택이 분석 중 변경되면409 PROVIDER_CONFIGURATION_CHANGED로 결과 저장을 막는다. Search/규칙 비교는 계속 가능하다. 실제 기업 연결은 이번 범위 밖이며 화면 설정 성공을 모델 호출 성공으로 표현하지 않는다.
