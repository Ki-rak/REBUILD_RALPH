# RE:Build Agent — Codex 로그인 후 미로그인 표시 진단

2026-09-22. 범위: 로컬 AI 인증 상태 확인과 복구 방법. 제품 전체 완료 검증이 아니다.

## 확인한 사실

- 사용자는 CMD에서 `codex auth login`으로 열린 URL의 브라우저 인증을 완료했다고 보고했다.
- 현재 PATH의 일반 CLI는 0.154.0, 제품 전용 CLI는 0.155.1이다. 두 CLI의 정식 로그인 명령은 `codex login`이며 `auth`는 정식 하위 명령 목록에 없다.
- 제품은 `server/ai/scripts/runtime.js` → `cliContext()` → `buildCodexEnvironment()`에서 `CODEX_HOME`을 `D:\REBUILD_RALPH\ops\private\codex-ai`로 고정한다. 로그인·상태 조회·SDK 추론이 이 프로젝트 전용 저장소를 사용한다.
- 실제 `npm --prefix server/ai run status` 결과는 `environment=local`, `provider=codex-oauth`, `authentication=NOT_LOGGED_IN`, `inference=NOT_TESTED`다. 전용 경로의 `auth.json`은 없었다. 인증 파일 내용이나 토큰은 읽지 않았다.
- 공통 `C:\Users\GS\.codex\auth.json`의 존재만 확인했다. 존재 자체는 유효 로그인 증거가 아니며, 현재 도구 실행 계정의 공통 경로 CLI 상태 조회도 NOT_LOGGED_IN이었다. 사용자가 CMD에서 완료한 인증의 저장 위치·유효성을 확인했다고 주장하지 않는다.
- `/api/provider/status`는 로컬 환경에서 매번 공식 CLI 상태를 다시 조회한다. 저장된 과거 연결 시험 결과만으로 NOT_LOGGED_IN을 반환하는 구조는 아니다.
- 점검 시 loopback 1455 포트를 잠시 바인딩 후 닫는 검사가 통과했다. 기본 웹 주소에 대한 HEAD 요청은 HTTP403이었다. 이는 로그인 endpoint나 브라우저 흐름 실패를 재현한 것이 아니므로 네트워크 차단을 원인으로 단정하지 않는다.

가장 직접적인 설명은 사용자가 수행한 일반 CLI 인증과 제품의 전용 인증 범위가 다르다는 것이다. 전용 인증 절차의 성공과 같은 전용 경로의 상태를 함께 확인해야 한다.

## 복구 순서 — CMD

사용자 본인의 일반 CMD에서 실행한다. `codex auth login`이나 일반 CLI 로그인 대신 프로젝트가 제공하는 명령을 사용한다.

```bat
cd /d D:\REBUILD_RALPH
npm --prefix server/ai run login
```

이 명령에서 새로 열린 공식 브라우저 인증을 완료하고, CMD에 로그인 성공이 표시되어 명령이 종료될 때까지 기다린다. 이어 같은 CMD에서 확인한다.

```bat
npm --prefix server/ai run status
```

`authentication=LOGGED_IN`이어야 전용 CLI 인증 성공이다. 이때 `inference=NOT_TESTED`는 정상이며 실제 모델 호출 성공과 구별한다. RE:Build Agent 설정을 다시 열고 **실제 연결 시험**을 실행하여 `connected=true`와 `inference=SUCCEEDED`를 확인한다.

PowerShell에서는 프로젝트 루트의 `.\ops\demo.ps1 -Action Login`도 같은 로그인 스크립트를 실행한다. 로그인 토큰 복사, 사용자 공통 설정 변경, API key fallback은 필요하지 않으며 수행하지 않는다.

## 전용 로그인 성공 후에도 같은 현상이 남는 경우

1. 브라우저 성공 화면뿐 아니라 명령 종료 결과와 바로 뒤 `run status` 결과를 비교한다.
2. 전용 `run status`가 LOGGED_IN인데 웹 화면만 다르면 웹 서버의 실행 사용자·프로젝트 경로·실행 환경을 확인한다. 다른 checkout/계정/서버를 보고 있는지 먼저 구별한다.
3. 상태가 LOGGED_IN이지만 실제 연결 시험이 실패하면 반환된 안전한 오류 코드로 모델 호출·한도·시간 제한을 별도 진단한다. 로그인 실패로 합치지 않는다.
4. 브라우저 callback 자체가 실패하는 경우 공식 문서는 device code 인증을 대안으로 안내한다. 현재 프로젝트 login 래퍼는 추가 인수를 전달하지 않으므로 `npm ... run login -- --device-auth`가 작동한다고 가정하지 않는다. 이 경우 전용 인증 경로를 유지하는 별도 보완이 필요하다.

실제 전용 브라우저 재인증과 모델 호출은 이 진단에서 수행하지 않았다. 사용자의 인증 확인 후 성공 여부를 재검증해야 한다.

공식 근거: [OpenAI Codex Authentication](https://learn.chatgpt.com/docs/auth) — CODEX_HOME별 인증 저장소, 공식 로그인, device code 인증. 로컬 근거: `server/ai/scripts/login.js`, `server/ai/scripts/runtime.js`, `server/ai/src/provider.js`, `server/ai/src/runtime-config.js`, `backend/server.py`의 Provider 상태 경로.
