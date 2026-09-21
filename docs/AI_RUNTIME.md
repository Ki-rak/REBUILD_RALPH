# RE:Build Agent AI 실행 경계

- 로컬 개발/데모: 공식 @openai/codex SDK/CLI 0.155.1, ChatGPT OAuth. 전용 CODEX_HOME은 ops/private/codex-ai. 사용자 공통 설정·토큰을 복사하지 않는다.
- 배포 adapter: 공식 OpenAI Responses API, 서버 OPENAI_API_KEY. https://api.openai.com/v1 외 endpoint 거부. 모델은 OPENAI_MODEL로 설정한다.
- REBUILD_ENV=local/demo/deployed를 명시한다. 서로 다른 인증 경로로 자동 전환하지 않는다.
- API 요청에는 허용된 SourceRef의 본문·위치만 전달한다. 도구 실행·웹 검색·임의 파일 수정은 금지한다.
- .env와 전용 인증 저장소는 Git·배포 번들·일반 로그에서 제외한다. 키·토큰·헤더·원시 외부 오류를 출력하지 않는다.

명령 (프로젝트 루트에서):

    npm --prefix server/ai test
    npm --prefix server/ai run status
    npm --prefix server/ai run login
    npm --prefix server/ai run smoke

login은 사용자가 자신의 터미널에서 공식 로그인 흐름을 완료하는 작업이다. 인증 코드나 URL을 작업 로그에 복사하지 않는다. 행사 봉인 중 사람 개입 허용 여부는 미확인이다.

2026-09-21 검증:
- 단위/HTTP 제한/시간초과/근거/인증 분리 25건 PASS.
- API key 경로: gpt-5-mini 실제 Responses 호출, ANSWERED 및 유효 근거 ID PASS. 이 결과는 배포나 제품 전체 E2E 성공이 아니다.
- 로컬 Codex OAuth: 공식 CLI에서 NOT_LOGGED_IN. 실제 추론은 미완료.
- 기존 모델 설정이 실제 계정 모델 목록에 없어, 확인된 gpt-5-mini로 로컬 비밀 설정의 모델 항목만 수정했다.

공식 모델 문서: https://developers.openai.com/api/docs/models/gpt-5-mini
증거: ops/preflight/ai-deployed-live-smoke.json, ops/runtime/openai-preflight.json.
