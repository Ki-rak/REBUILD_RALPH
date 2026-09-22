# RE:Build Agent — 제공 data 폴더로 시연·실제 연결 검증

기존 자료와 신규 자료는 **승인된 INPUT 원본**을 사용한다. 원본은 수정하지 않으며 평가 자료·정답·preflight 변환본을 지식으로 넣지 않는다. 준비·시연과 제품 완료를 구분한다.

## 실제 자료 선택

INPUT 루트: `D:\REBUILD_RALPH\data\REBUILD_INPUT_v1\REBUILD_INPUT_v1`

| 구분 | 실제 폴더 | 등록 가능한 원본 |
|---|---|---:|
| 전체 과거 자료 | `01_PAST_PROJECTS/P01_*` ~ `P15_*` | 15개 프로젝트 / 155개 파일 |
| 기본 과거 자료 | `P01_Haeon_Metro_Package_2`, `P06_Cheongra_Desalination_Intake` | 2개 프로젝트 / 21개 파일 |
| 첫 신규 자료 | `02_NEW_PROJECTS/N01_Haeon_Blue_Line_Package_4` | 11개 파일 |
| 두 번째 신규 자료 | `02_NEW_PROJECTS/N02_Dasol_East_Water_Treatment` | 7개 파일 |
| 표준 양식 | `03_OUTPUT_TEMPLATES` | 제공 양식 7종; 출력 지원은 ITB/Risk/심의장표 |

N01은 승인 Rev01과 미승인 Rev02를 모두 포함한다. 자료 선택에서 미승인 문서를 감추지 않고 제품이 구별하는지 확인한다. `04_INCREMENTAL_UPDATES`와 `05_OPTIONAL_OCR`는 첫 시연에서 제외한다. 원본 `00_START_HERE/IMPORT_PLAN.md`와 같은 경계다.

다음 명령은 파일명·크기·SHA-256 목록만 작성한다. DB 등록이나 지식화는 하지 않는다.

```powershell
Set-Location D:\REBUILD_RALPH
.\ops\demo.ps1 -Action Inventory
```

## 1. Supabase 준비

2026-09-22 실제 연결 재검증에서 프로젝트 `wsziosnttnxefgfbgpeq`의 Auth·DB RLS·Storage RLS·로그아웃·시험 계정 정리가 통과했다. 현재 프로젝트에는 SQL을 다시 실행할 필요가 없다. 적용 주체는 관측하지 않았다. 새 환경을 구성할 때만 준비된 `supabase/migrations/20260921210000_rebuild_agent_storage.sql`을 인증된 SQL Editor에서 적용한다. secret/publishable key는 SQL 관리 인증을 대신하지 않는다.

현재 `.env`의 프로젝트 URL·publishable key·secret key·승인 서명 키를 보존한다. SQL 적용 후 다음을 실행한다.

```powershell
.\ops\demo.ps1 -Action Check
```

`status=PASSED`, auth_login/db_rls/storage_rls/logout/cleanup 검증이 모두 true여야 통과다. `PENDING_SCHEMA`이면 준비가 끝나지 않았다. 이 명령은 임시 시험 계정으로 격리 검증 후 정리한다. 실제 서비스 검증을 하지 않고 PASS로 표시하지 않는다.

시연 로그인에는 제품용 Supabase Auth 이메일/비밀번호 계정이 필요하다. 대시보드 계정과 다르다. 이 도구는 기존 계정 비밀번호를 재설정하거나 계정 인증정보를 저장하지 않는다. 계정이 없다면 해당 프로젝트 Authentication의 Users에서 만든다.

## 2. 시연 서버와 과거 자료 준비

PowerShell 창 A:

```powershell
.\ops\demo.ps1 -Action Start
```

`http://127.0.0.1:8790/`에서 제품 계정으로 로그인한다. Start는 실행 중에만 환경을 local로 고정해 Codex OAuth 경로를 사용한다. 종료 후 이전 환경을 복원한다. 기존 8780/8770 시안·서버와 주소를 구분한다. 8790이 사용 중이면 `-Port 8791`처럼 본인이 사용할 포트를 지정하고 Seed에도 같은 값을 전달한다.

PowerShell 창 B에서 선택한 과거 자료만 승인·등록한다. 비밀번호는 출력되지 않는 입력창에 입력한다.

```powershell
# 기본: P01/P06 과거 21개 문서
.\ops\demo.ps1 -Action Seed -Email "제품계정이메일" -ApprovePast

# 전체 15개 과거 프로젝트 / 155개 원본을 관리하려면 위 대신 실행
.\ops\demo.ps1 -Action Seed -Email "제품계정이메일" -AllPast -ApprovePast
```

`-ApprovePast`는 Inventory와 위 경로의 과거 자료 선택을 확인한 뒤 붙인다. 명령은 제품의 후보 확인→등록 승인 API를 사용하며 같은 이름의 과거 프로젝트를 재사용한다. 같은 bytes는 중복 처리하므로 중단 후 동일 명령을 다시 실행할 수 있다. 누락 또는 추출 실패는 FAILED와 구체적인 오류 코드로 남기고 성공으로 숨기지 않는다. 제품의 적용성 REVIEW_REQUIRED와 도구의 추출 실패는 구분한다.

**Seed는 N01/N02를 등록하거나 신규 프로젝트를 만들지 않는다.** 실제 시연 계정의 업로드 출발점을 보존한다. 이미 신규 파일을 올린 계정이라면 동일 파일을 처음 올린 것으로 표시할 수 없다. 데이터 삭제로 이를 숨기지 말고 별도 시험 계정/새 입력으로 검증한다.

## 3. 시연: 실제 N01 파일 업로드부터

1. 프로젝트 → 새 프로젝트 만들기 → 검토 프로젝트로 `N01_Haeon_Blue_Line_Package_4`를 만든다.
2. 이름 아래 파일 선택에서 실제 N01 폴더의 11개 파일을 선택하고 업로드한다. 이름만 바꾼 파일이나 사전 생성 결과를 쓰지 않는다.
3. 지식조회 Search Mode와 지식 자료실에서 과거↔신규 비교, 양쪽 근거, 문서 노드와 원문을 확인한다.
4. 원문 근거로 승인 정정서의 통지기한14일/방류450m3/day가 적용되고 미승인 Rev02가 유효 계약을 덮지 않는지 확인한다. 다른 조항을 함께 덮어쓰면 실패다.
5. 프로젝트에서 ITB 분석표·Risk Register·심의장표 각각 초안 생성→실제 편집·저장→검토·승인→파일 내보내기를 수행한다. XLSX 두 종류와 5장 PPTX를 열어 확인한다.
6. N02의 7개 파일은 **별도 검토 프로젝트**에 업로드한다. N01과 자료/조건을 합치지 않는다.
7. 수정/추가 입력 시 영향을 받는 기존 승인이 무효화되는지 확인한다. 과거 경험·설계값·허용량을 구별하며 근거 부족은 REVIEW_REQUIRED로 둔다.
8. 창 A에서 Ctrl+C 후 Start 명령을 다시 실행하고 새 로그인으로 원본·초안·승인·파일을 재조회한다.

로컬 AI Insight까지 확인하려면 공식 전용 OAuth 로그인이 필요하다.

```powershell
.\ops\demo.ps1 -Action Login
npm --prefix server/ai run status
```

`NOT_LOGGED_IN`일 때 API-key fallback을 하지 않는다. 로그인 상태와 실제 모델 호출 성공은 다르다.

## 4. 에이전트가 이어서 실행할 실제 서비스 자동 검증

이 명령은 시연 계정과 별개의 임시 사용자 두 명을 만들고, 실제 기본 과거 자료21개와 N01/N02의18개 원본을 사용한다. 제품 HTTP API와 실제 Supabase 사용자 JWT로 처리한다.

```powershell
# 실제 DB/Storage/Auth/RLS + 원본/MD/JSON + 세 출력 + 서버 프로세스 재시작
.\ops\demo.ps1 -Action Verify

# 로컬 OAuth 인증 후 실제 제품 AI 호출까지 포함
.\ops\demo.ps1 -Action Verify -WithAI
```

검증 서버는 기본127.0.0.1:8792의 전용 자식 프로세스이며 자기 실행 ID를 확인한 뒤 사용한다. 두 번의 PID와 새 로그인을 기록해 단순 새로고침을 프로세스 재시작으로 오인하지 않는다. 기존 제품 서버/다른 프로세스는 종료하지 않는다. 재시작 후 재생성하기 전에 최초 결과물의 실제 Storage 경로·SHA-256을 다시 확인한다. 과거·신규 원본과 MD/JSON도 사용자 JWT로 다운로드한다.

검증 기록과 생성 파일은 `ops/runtime/demo/`에 저장한다. 자동 승인은 격리 시험 계정의 테스트 행위로 표시한다. 종료 시 이 실행에서 만든 사용자 소유의 실제 Storage 객체와 DB 행만 정리하고, 실패하면 `CLEANUP_REQUIRED`와 복구할 owner ID를 남긴다. 사용자 시연 계정·기존 자료는 정리 대상이 아니다.

- `PASSED_RULES_FLOW_AI_NOT_TESTED`: 실제 규칙 경로 검증이며 AI/제품 전체 완료가 아니다.
- `PASSED_WITH_LOCAL_AI`: 이 검증 범위의 실제 로컬 AI까지 확인했다는 뜻이다. 최종 독립 리뷰·OMX strict 완료는 별도다.
- `BLOCKED`/`PENDING_SCHEMA`: 외부 준비 미완료. 원인을 해결한 뒤 다시 실행한다.
- `FAILED`/`CLEANUP_REQUIRED`: 보고서의 stage를 확인하고 원인을 수정한다. 실패 결과를 완료 처리하지 않는다.

자동 검증은 실제 HTTP/DB 흐름의 증거다. 기존 Playwright 소유 fixture 시험은 TEST_STORAGE_INJECTED이며 실제 DB 성공 증거로 바꾸지 않는다. 실제 시연 브라우저 UI 확인과 전체 최종 gate는 추가로 수행한다.

이 연결과 검증이 끝나면 남은 신규입력/복구/권한 검증, 최종 cleaner·회귀·독립 코드/설계 리뷰, 실제 OMX strict 체크포인트와 원시 로그 보존을 이어간다. 배포·공개 푸시·영상·행사 제출은 별도 요청까지 실행하지 않는다.

## 현재 확인 결과 — 2026-09-22T07:43:35.958995+09:00

로컬 전체 Python 시험163건 통과(실패/오류/건너뜀0, 기존 deprecation warning2). 이 중 이번 도구 회귀23건이며 기본 실제 입력39개·Office 결과6개를 포함한다. 제품 저장소를 주입한 시험이므로 실제 Supabase 성공으로 표시하지 않는다. 원본398개 해시가 유지됐고 독립 코드·설계 검토는 이번 도구 범위에서 통과했다.

실제 연결 실행은 `schema_and_rls_preflight`에서 BLOCKED/PENDING_SCHEMA이며 시험용 사용자 생성 전 중단됐다. 공식 로컬 OAuth는 NOT_LOGGED_IN/NOT_TESTED다. SQL 적용→Check→Login→Verify -WithAI→실제 브라우저/남은 제품 검증→최종 독립/OMX strict 순서로 재개한다. 현재 제품은 미완료다. 증거: `ops/runtime/demo/setup-verification-20260922.json`.


## 실제 브라우저 검증 명령

```powershell
.\ops\demo.ps1 -Action Browser
```

별도 임시 Auth 사용자와 전용8793 서버·새 Chromium 창을 사용한다. 과거 P01/P06만 먼저 승인 등록한 뒤 N01/N02 파일은 실제 새 프로젝트 화면에서 업로드한다. 초안 수정·승인·파일 다운로드, 실제 서버 재시작과 새 로그인·기존 승인/저장 객체 복원을 확인한다. UI 승인 행위는 격리 시험 계정의 자동 검증이다.

N01의11개 입력 중 같은 bytes인 복사본이 있어10개 문서로 저장된다. 검증은 고유 SHA-256 일치와11개 원래 파일명 별칭 보존을 모두 요구한다. 데이터가 누락됐는데 중복이라고 처리하지 않는다. 결과는 `ops/runtime/demo/`에 기록한다. PASS가 나오기 전 실행 자체를 성공으로 간주하지 않는다. 실제 시연 계정에는 신규 자료를 미리 넣지 않는다.

이 명령은 규칙 기반 제품 흐름 검증이다. 로컬 AI 인증/모델 추론, 제품 전체 최종 gate와 구별한다. OAuth는 최근 확인에서 NOT_LOGGED_IN/NOT_TESTED다.
