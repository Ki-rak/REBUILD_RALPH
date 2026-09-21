# RE:Build Agent AI 인증 분리 및 /goal v1.1

이번 작업은 사용자가 요청한 Provider 경로 구현과 실행 프롬프트 개정이다. 제품 전체 goal은 시작하지 않는다.

## 작업 1: 서버 Provider 모듈
server/ai/ 소유. 공식 @openai/codex-sdk 0.155.1와 CLI 0.155.1를 프로젝트에 고정 설치한다. local/demo는 공식 ChatGPT OAuth만, deployed/production은 OpenAI Responses API key만 허용한다. 조용한 인증 fallback 금지. project-local 별도 CODEX_HOME, 빈 작업 디렉터리, 최소 환경, no shell/web/network/MCP, 읽기 전용 sandbox와 never approvals. 비밀정보는 읽어 출력하지 않고 응답·로그에는 안전한 상태만 반환한다. 인증되지 않은 public AI proxy는 만들지 않는다. 로컬 시험 서버는 loopback와 Host/Origin 검증, 크기/동시성/시간 제한. 실제 로그인 여부와 모델 호출 성공을 분리한다. 근거 id 화이트리스트가 있는 구조화 응답 및 모의 transport 테스트를 구현한다.

## 작업 2: 계약 문서와 goal
부모가 GOAL.md, ops/GOAL_INPUT.txt, .env.example/.env, SPEC/PLAN/STATE, AGENTS, docs 및 OMX pending 계획을 맡는다. UI06, 실제 Supabase, 전체 결과물, 설치·커밋·검토/복구 루프, 완료/봉인/권한 범위를 포함한다. 기존 파일/비밀정보/인증/global config/평가 정답은 보존한다.

## 검증/종료
실제 SDK/CLI 구동과 로그인 상태 확인 + transport 단위·서버 경계 테스트. 실제 OAuth/배포 key 호출은 자격증명이 있을 때만, 없으면 BLOCKED로 기록. 독립 코드 검토와 결함 수정 후 명시 파일만 커밋한다. 전체 제품 완료나 goal 실행으로 기록하지 않는다.
