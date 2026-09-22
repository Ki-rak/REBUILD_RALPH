# RE:Build Agent 추가 의존성 설치안

2026-09-21 실제 npm/PyPI 메타데이터 조회 기준. 사용자가 16:42 이전 후속 답변에서 설치를 승인한 목록이다. 설치·검증을 완료했으며 결과는 STATE.json과 ops/preflight/dependency-verification.json에 있다. 최초 사용자 지시의 “설치 시 확인 필요”를 따른다. 하네스 설치 위임은 OMX에 이미 적용했다.

## 제품 및 검증에 필요한 목록

프로젝트 `.venv`에 Python 3.12로 설치: fastapi 0.136.3, uvicorn 0.49.0, python-multipart 0.0.32, openpyxl 3.1.5, python-docx 1.2.0, python-pptx 1.0.2, pypdf 6.10.0, pdfplumber 0.11.9, httpx 0.28.1, supabase 2.31.0, pytest 8.4.2.

| 묶음 | 목적 |
|---|---|
| FastAPI·Uvicorn·multipart | Python API, 로컬 구동, 파일 업로드 |
| openpyxl·docx·pptx·pypdf·pdfplumber | 실제 문서 추출과 표·출처 보존, XLSX 출력 |
| httpx·supabase | 확인된 LLM HTTP 규격과 Supabase DB/Storage/Auth 연결 |
| pytest | 근거·개정·승인·출력 회귀 검증 |

프로젝트 JavaScript 의존성: `@supabase/supabase-js 2.116.0`(Auth 세션과 브라우저 클라이언트), `esbuild 0.28.2`(브라우저 모듈 번들). Vercel CLI 59.23.2는 최신 사용자 지시로 설치 보류했다. 모두 프로젝트 경로에만 설치한다. 배포 시 Python 의존성 잠금/지원 버전은 실제 빌드로 검증한다.

Supabase CLI 2.117.0은 버전만 확인했고 필수 설치에서 제외했다. 현 범위에서는 SDK·SQL migration과 프로젝트 대시보드로 진행 가능하다. 실제 필요가 확인되면 별도 설치 범위를 갱신한다. Docker·WSL·tmux·추가 하네스는 설치하지 않는다.

기존 문서/브라우저 번들 도구는 준비에 재사용한다. 새 Python 환경은 운영체제 전체 설정을 바꾸지 않고 제품 재현성을 확보하기 위한 것이다. 설치 시 각 패키지의 필수 전이 의존성도 설치되며 Windows용 wheel/번들러 실행 파일을 사용할 수 있다. 기존 사용자 공통 설정은 변경하지 않는다. 버전 충돌 시 이유와 조정 버전을 기록한다.

최종 설치 목록·라이선스·lockfile은 실제 설치 결과로 작성한다. 승인 전에는 설치 완료로 기록하지 않는다. 확인한 주요 라이선스는 FastAPI/Supabase/esbuild MIT, Uvicorn BSD-3-Clause, multipart Apache-2.0, Vercel Apache-2.0이며 개별 전이 의존성은 설치 후 확인한다.

## 실제 설치 검증 결과

프로젝트 `.venv`의 Python 3.12.14에 54개 패키지를 설치했다. 주요 모듈 11개 import, FastAPI HTTP 응답, 원본 DOCX/PPTX/PDF/XLSX 읽기, 의존성 일관성 등 17개 점검이 통과했다. `tools/web`에 Supabase JS 2.116.0과 esbuild 0.28.2를 설치하고 import 및 Windows native transform을 확인했다. Vercel CLI는 설치하지 않았다.

전체 Python 버전은 `requirements-installed.lock.txt`, 실제 패키지 라이선스 메타데이터는 `ops/preflight/python-installed-inventory.json`, Node 잠금은 `tools/web/package-lock.json`에 보존한다. uv 사용 시 `UV_CACHE_DIR=D:\REBUILD_RALPH\ops\cache\uv`를 지정한다. 사용자 기본 캐시 권한 실패를 이 경로로 복구했다. Starlette의 httpx TestClient 사용 중단 예고 경고는 남아 있지만 현재 HTTP 시험은 통과했다. 실제 Supabase/LLM 서비스 연결을 시험한 결과는 아니다.

## v1.1 AI 추가 의존성

공식 Codex TypeScript SDK/CLI를 server/ai/package.json과 lockfile에 고정 설치한다. 기존 OMX 0.21.5 개발 하네스와 별개다. 배포 OpenAI Responses API는 Node의 fetch로 호출하여 추가 라이브러리 의존성을 최소화한다. 추가 스킬 3개는 ops/preflight/skills-local-v11.json에 로컬 원본과 해시를 기록했다. 관리자 비활성 Supabase/OpenAI 플러그인은 설치 완료로 표시하지 않는다. 실제 설치·테스트 결과는 server/ai README와 STATE의 검증 기록이 기준이다.

## 프로젝트 내부 브라우저 검증 의존성 (2026-09-21 21:55 KST)

기존 사용자 스킬 설치에서 사용하던 Microsoft Playwright 1.62.1을 동일 버전으로 tools/web에 고정 설치했다. npm은 2개 패키지를 추가했고 audit 취약점 0개, playwright.chromium import를 확인했다. Apache-2.0 라이선스이며 package-lock.json에 정확한 버전을 보존한다. npm cache는 ops/cache/npm, 설치 시 ignore-scripts를 사용했고 사용자 공통 설정은 변경하지 않았다. 기존 브라우저 실행 바이너리 캐시는 재사용한다. 이후 브라우저 검증은 프로젝트 내부 require 경로를 사용한다.
## 배포 CLI 및 검증 환경 복구 (2026-09-22)
최신 배포 승인으로 tools/vercel에 Vercel 59.25.0(Apache-2.0)을 고정 설치하고 실제 로그인/팀·프로젝트 연결 및 서버 환경변수 등록을 확인했다. 사용자 공통 설정은 변경하지 않았다. Python3.12 실행 파일이 CPU0 상태에서 정체되어 tools/python314-verify에 동일 requirements-dev 핀을 사용하는 별도 Python3.14 검증 환경을 설치한다. 실제 배포 런타임은 .python-version의3.12이며 새 환경 시험과 Vercel 빌드 검증을 구별한다.
