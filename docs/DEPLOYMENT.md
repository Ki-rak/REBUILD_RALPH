# RE:Build Agent 배포 운영

2026-09-22 최신 사용자 지시에 따라 UI 복원·검증 → GitHub main 푸시 → Vercel production 배포를 진행한다. 이전 배포 보류 기록은 당시 상태이며 현재 승인에 적용하지 않는다. 배포 성공은 제품 전체 완료 판정과 별도다.

- 저장소: https://github.com/Ki-rak/REBUILD_RALPH, production branch main.
- Vercel: PLAI Developer League 2026 / g-19. 기본 주소 https://rebuild-ralph.vercel.app.
- Supabase: wsziosnttnxefgfbgpeq. 사용자 세션의 DB/RLS/Storage/Auth만 제품에서 사용한다.
- 서버: Python 3.12, FastAPI backend.server:app; frontend 정적 자산을 같은 출처에서 제공한다.
- 배포 AI: Python/httpx에서 공식 OpenAI Responses API. 로컬 개발·데모는 공식 Codex OAuth 경로를 유지한다. 인증 fallback은 없다.

## 비밀 설정

사용자가 g-19의 production·preview에 OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL, SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, REBUILD_APPROVAL_SIGNING_KEY, REBUILD_ENV=deployed 등록을 명시 승인했다. 7개 모두 등록 확인했다. 값은 문서·Git·브라우저에 포함하지 않는다. Supabase 관리자 키와 Codex OAuth 토큰은 전송하지 않았다. 로컬 .env, .env.local, .vercel, ops/private는 Git/배포에서 제외한다.

## 배포 번들과 제한

.vercelignore와 vercel.json excludeFiles로 평가 자료·원시 로그·개발 도구·로컬 OAuth·검토 시안을 제외한다. 제공 INPUT은 README에서 전체 창작 합성 데이터임을 확인했다. 01_PAST_PROJECTS와 02_NEW_PROJECTS는 데모 폴더 목록/승인 기능의 원본, 03_OUTPUT_TEMPLATES는 출력 양식으로 사용한다. 신규 프로젝트 자료를 자동 인입하거나 정답으로 미리 저장하지 않는다. 원본 내용은 변경하지 않는다.

Vercel 요청 제한을 고려해 배포 UI는 파일 및 한 번의 업로드 합계를 3.8 MB로 제한하며 초과 시 분할 업로드를 안내한다. 로컬은 기존 파일당 20 MiB다. 함수 실행 상한은 300초, 모델 요청은 유한 시간 제한을 둔다. Supabase가 영속 저장소이며 함수 메모리/로컬 SQLite를 영속성 근거로 사용하지 않는다.

## 실행 및 검증

프로젝트 CLI는 tools/vercel의 vercel 59.25.0이다. 인증은 ops/private/vercel-config에만 저장한다.

```powershell
git -c safe.directory=D:/REBUILD_RALPH push origin HEAD:main
node tools/vercel/node_modules/vercel/dist/index.js deploy --prod --yes --scope plai-developer-league-2026 --global-config ops/private/vercel-config
```

배포 후 실제 URL의 /api/health, /api/config, 화면 자산, 로그인, 원본 업로드·지식화·승인·출력을 확인한다. CLI Ready만으로 전체 API/제품 검증 성공을 선언하지 않는다. 당시 Git commit, deployment ID, alias, 검증 결과와 남은 항목은 STATE.json, ops/activity.jsonl 및 docs/FINAL_VERIFICATION_LIVE.md에 기록한다.

공식 기준: [FastAPI](https://vercel.com/docs/frameworks/backend/fastapi), [Python runtime](https://vercel.com/docs/functions/runtimes/python), [함수 제한](https://vercel.com/docs/functions/limitations). Google Drive 영상 연결은 사용자가 담당하며 제품 배포와 별도로 추적한다.
