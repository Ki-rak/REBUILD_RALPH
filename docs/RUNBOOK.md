# RE:Build Agent 개발 실행과 복구

이 문서는 제품 소스의 로컬 실행법이다. 배포·공개 게시·행사 제출은 별도 작업이다.

## 실행

작업 폴더는 D:\REBUILD_RALPH다. 고정 Python 의존성은 requirements.txt와 requirements-dev.txt, AI Node 의존성은 server/ai/package-lock.json을 사용한다. 이 작업 환경에서는 .venv 및 server/ai/node_modules 설치와 실행을 검증했다.

PowerShell에서 다음을 실행한다.

    .\ops\python.ps1 -m uvicorn backend.server:app --host 127.0.0.1 --port 8780 --no-access-log

주소는 http://127.0.0.1:8780/ 이다. 실제 제품은 Supabase 인증·DB·Storage를 사용한다. tests/ui/browser_server.py의 8782 서버는 합성 계정과 메모리 저장소를 주입한 시험 환경이며 실제 서비스 성공 근거가 아니다.

## 서버 환경

.env는 비밀이며 Git/배포 산출물에 포함하지 않는다. .env.example에 키 이름만 보존한다.
- REBUILD_ENV=local 또는 demo: 공식 Codex OAuth만 사용한다. 미로그인일 때 API key로 전환하지 않는다.
- REBUILD_ENV=deployed: OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL=https://api.openai.com/v1를 사용한다. 실제 배포 실행은 별도 승인 범위다.
- SUPABASE_URL은 지정 프로젝트 https://wsziosnttnxefgfbgpeq.supabase.co다. 서버의 일반 사용자 작업은 publishable key와 사용자 JWT로 RLS를 따른다.
- SUPABASE_SECRET_KEY는 격리된 실제 서비스 검증용 관리 작업에만 사용한다. 브라우저로 전달하지 않는다.
- REBUILD_APPROVAL_SIGNING_KEY는 충분히 긴 서버 전용 영속 키다. 최초 환경에서 생성된 값을 비밀 저장소에 보존한다. DB가 유지된 채 키만 교체하면 기존 근거·승인 서명이 무효화된다. 복구 시 기존 키를 복원하거나 명시적인 원본 재처리·재검토를 수행하며 기존 승인을 자동 재서명하지 않는다.

공식 로컬 OAuth 로그인은 사용자의 직접 인증이 필요한 단계다. server/ai/scripts/login.js 안내를 따른다. 토큰을 추출하거나 Desktop 인증을 복사하지 않는다.

## 실제 Supabase 초기 구성

supabase/migrations/20260921210000_rebuild_agent_storage.sql은 추가 테이블·사용자별 RLS·private bucket·원자 승인 RPC를 만든다. 인증된 프로젝트 SQL Editor 또는 승인된 관리 연결로 적용한다. 현재 코드 준비와 모의 시험은 이 SQL의 실제 적용 증거가 아니다. 기존 데이터와 정책을 확인하며 README의 복구 경계를 따른다.

기본 로그인 계정은 해당 Supabase Auth에 존재해야 한다. Supabase 대시보드 로그인 계정과 제품 Auth 계정은 별개다. 제품은 사내 SSO를 성공한 것으로 표시하지 않으며 설정 프로필만 제공한다.

실제 격리 검증:

    .\ops\python.ps1 ops/runtime/supabase_live_verify.py

이 검증은 임의 식별자의 시험 사용자 2명을 생성하여 DB/Storage 격리를 확인하고 그 시험 데이터만 정리한다. schema가 없으면 PENDING_SCHEMA로 종료하고 성공으로 처리하지 않는다. 기존 사용자 자료는 정리 대상이 아니다.

## 자료와 양식

기존 폴더는 승인 전 이름·크기만 표시한다. 새 파일은 Storage 원본→DB 인입→추출→MD/JSON 순서로 처리한다. OCR/암호화/미지원은 명시적 오류와 재처리 상태다. 평가지·정답·holdout은 지식 자료로 읽지 않는다.

공통 양식의 제공 원본은 data/REBUILD_INPUT_v1/REBUILD_INPUT_v1/03_OUTPUT_TEMPLATES에 유지한다. 등록한 새 버전은 사용자별 Storage와 서명된 DB 기록에 별도 보존한다. 출력 종류별 필수 열/슬라이드 구조를 유지해야 하며, 사용자는 초안에서 버전을 명시적으로 선택한다. 다른 새 버전을 등록했다는 이유만으로 기존 승인본을 바꾸지 않는다. 선택 버전 변경·초안 수정·입력 변경 시 재승인이 필요하다.

## 검증과 제한

    .\ops\python.ps1 -m pytest tests -q
    npm --prefix server/ai test
    node tests/ui/frontend_errors.cjs
    node tests/ui/frontend_context.cjs
    .\.venv\Scripts\python.exe -X utf8 tests/ui/run_browser.py browser_flow.cjs
    .\ops\python.ps1 tests/ui/browser_workbook.py

브라우저 시험은 tests/ui/browser_README.md의 소유 fixture 실행기로 시작하고 종료한다. 실행기가 URL/실행 ID를 전달하고 브라우저는 해당 ID를 검증한다. 실제 OpenAI 증거, 모의 DB 시험, 실제 Supabase 검증을 혼합하지 않는다. STATE.json, docs/ARCHITECTURE_REVIEW.md, ops/activity.jsonl에 미완료 연결과 리뷰 결함을 유지한다.
## Windows 런타임 복구와 연결 한계

이 환경에서 .venv/Scripts/python.exe 리다이렉터가 Python 코드 실행 전에 간헐적으로 대기했다. ops/python.ps1은 .venv/pyvenv.cfg에 기록된 실제 Python 실행 파일을 사용하고, 프로세스 범위 PYTHONPATH로 이 프로젝트의 site-packages만 지정한다. 사용자 공통 환경은 복원하며, 명령의 종료 코드를 그대로 반환한다. 이 경로로 전체 Python 108개 검증이 통과했다.

/api/health의 running/persistence=supabase는 서버 구동과 저장소 설정을 뜻한다. 실제 DB/Storage 접근 성공을 뜻하지 않는다. 실제 연결 완료 기준은 supabase/README.md를 따른다.

## 외부 인증 차단에서 재개

2026-09-22 01:20 KST 재검증과 세 번의 연속 goal 작업 기록을 근거로 native goal을 blocked로 기록했다. 제품 완료가 아니다. 상세 근거는 ops/runtime/external-blocker-audit.json에 있다.

1. Supabase 관리 플러그인은 현재 관리자 정책으로 사용할 수 없다. 승인된 SQL Editor/DB 관리 연결이 확보되면 supabase/migrations/20260921210000_rebuild_agent_storage.sql을 기존 구조 확인 후 적용한다. 제품용 API key를 SQL 인증으로 대체하지 않는다.
2. 전용 공식 로그인 명령은 `npm --prefix server/ai run login`이다. 사용자 인증을 마친 뒤 `npm --prefix server/ai run status`와 실제 제품 호출을 확인한다. Desktop 토큰 복사나 API-key fallback을 사용하지 않는다.
3. 실제 두 사용자 DB/Storage/RLS, 신규 업로드 전체 경로, 서버 재시작 복원과 최종 독립 검토·OMX strict 게이트를 수행한다. 기존140/26/16 시험은 실제 서비스 통과를 대신하지 않는다.

봉인 중 사람 개입 예외는 확인되지 않았다. 이 복구 절차는 행사 규칙의 예외나 즉시 개입 허가를 의미하지 않는다. 원래 목표와 데이터, 로그, 커밋을 보존한 상태에서 재개한다.
