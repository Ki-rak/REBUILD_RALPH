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
- 단위/HTTP 제한/시간초과/근거/인증 분리 및 usage 회귀 검증 31건 PASS.
- API key 경로: gpt-5-mini 실제 Responses 호출, ANSWERED 및 유효 근거 ID PASS. 이 결과는 배포나 제품 전체 E2E 성공이 아니다.
- 로컬 Codex OAuth: 공식 CLI에서 NOT_LOGGED_IN. 실제 추론은 미완료.
- 기존 모델 설정이 실제 계정 모델 목록에 없어, 확인된 gpt-5-mini로 로컬 비밀 설정의 모델 항목만 수정했다.

공식 모델 문서: https://developers.openai.com/api/docs/models/gpt-5-mini
증거: ops/preflight/ai-deployed-live-smoke.json, ops/runtime/openai-preflight.json.

## 실제 호출과 usage

분석 응답은 기존 status/answer/claims를 유지하며 adapter가 검증 후 추가한 execution 및 usage를 함께 반환한다. bridge도 같은 결과를 JSON으로 전달한다. LLM이 작성한 JSON에 usage 등을 끼워 넣으면 기존 엄격한 답변 schema 검증에서 거부한다.

- execution.provider/auth_mode: 실제 선택한 openai-responses/OPENAI_API_KEY 또는 codex-oauth/CHATGPT_OAUTH.
- execution.state/source: 검증된 호출 성공만 SUCCEEDED/MODEL_CALL. OAuth는 공식 turn.completed 이벤트도 있어야 성공으로 처리한다.
- execution.cache_hit: 현재 두 adapter는 결과 캐시 없이 직접 호출하므로 false. 이는 공급자 prompt cache 사용 여부와 다르다.
- execution.model: OpenAI가 응답에 보고한 실제 모델. Codex SDK 0.155.1의 완료 이벤트에는 모델 정보가 없으므로 null. 요청한 모델은 requested_model로 별도 표시하며 실제 응답 모델로 추정하지 않는다.
- usage.input_tokens/output_tokens/total_tokens/cached_input_tokens: 공급자가 보고한 음이 아닌 정수만 보존한다. 미제공·유효하지 않은 값은 null. 실제 0은 0으로 유지하며 없는 total을 합산해서 만들지 않는다.
- OpenAI cached_input_tokens는 usage.input_tokens_details.cached_tokens에서 가져온다. Codex는 공식 turn.completed.usage.cached_input_tokens를 사용한다. SDK에는 total_tokens가 없으므로 해당 값은 null이다.
- 실패는 기존 안전한 오류 코드로 반환하며 성공 usage나 캐시 결과를 만들지 않는다. 비용은 계산하거나 추정하지 않는다.

2026-09-21 usage 실호출 검증: 배포 adapter의 gpt-5-mini 요청은 실제 응답 모델 gpt-5-mini-2025-08-07, input 246 / output 229 / total 475 / cached input 0을 반환했다. 유효 SourceRef 1개, 호출 3,401ms. 이 검증은 adapter 최소 호출이며 Supabase 제품 전체 E2E나 로컬 OAuth 성공이 아니다. 로컬 OAuth 실호출은 사용자 공식 로그인 완료 전까지 미검증이다.

SDK 근거: 설치된 server/ai/node_modules/@openai/codex-sdk/dist/index.d.ts의 Usage 및 TurnCompletedEvent 타입.