# RE:Build Agent 실제 서비스 최종 검증

확인 시각: 2026-09-22T09:37:46.647128+09:00. 현재 제품 완료는 아직 증명되지 않았다. 이 문서는 이전 인증 전 자료인 FINAL_VERIFICATION.md 이후의 실제 검증을 추적한다. 원래 목표·SPEC AC01–16/23–42를 유지하며 시간 제한을 이유로 기준을 줄이지 않는다.

## 확보한 실제 근거

- Supabase Auth·DB RLS·Storage RLS·로그아웃·정리: 실제 임시 사용자로 PASS. 최신 통합 보고서 preflight에도 포함.
- ops/runtime/demo/negative-live-verification-20260922T003011407447Z.json: 실제 두 사용자, 생성한 별도 QA 입력의 조건 변경·원본·중복별칭·승인 무효화·손상 재처리·권한 거부 PASS, 정리 true. 제공 프로젝트 시연과 구별한다.
- ops/runtime/demo/oauth-status-diagnostic.json: 공식 전용 CLI exit0/LOGGED_IN. 토큰은 읽거나 복사하지 않았다. 로그인 자체는 추론 성공 증거가 아니다.
- ops/runtime/demo/partial-real-ui-office-20260922.json: 실제 N01 UI에서 내려받은 ITB/Risk 두 XLSX의 해시·재개봉 성공. 원래 전체 UI run은 FAILED로 보존했으며 이를 전체 성공으로 바꾸지 않았다.
- ops/runtime/demo/pytest-live-followup-20260922.xml: Python179PASS, 실패/오류/건너뜀0, 기존 deprecation2. AI31/Node경계3도 PASS. 주입 저장소 시험과 실제 검증을 구별한다.

## 현재 실행 및 필수 잔여

- 브라우저 실제 P01/P06 과거 자료→N01/N02 업로드→세 결과물 수정/승인/다운로드→원래 저장 객체→프로세스 재시작·새 로그인 복원: 실행 중.
- `ops/demo_provider_verify.py --environment local` 및 `--environment deployed`: 각각 실제 공식 OAuth/OpenAI API-key 모델·Supabase DB usage/Storage Office 통합 실행 중. TestClient를 통한 실제 서비스이며 저장소/AI를 주입하지 않는다. 공개 배포 false, 앱 재생성은 process_restart false로 명시한다.
- 최종 독립 코드/아키텍처 및 전체 불변 조건 검토 진행 중. 범위별 APPROVE/CLEAR를 전체 완료 판정으로 확대하지 않는다.
- 전체 필수 근거 확보 후 원본·원시 세션 확인, 커밋, 실제 OMX strict와 native goal 완료 순서를 진행한다. 누락이 있으면 완료하지 않는다.

## 실행 명령

```powershell
.\ops\demo.ps1 -Action Browser
.\ops\python.ps1 ops/demo_negative_verify.py
.\ops\python.ps1 ops/demo_provider_verify.py --environment local
.\ops\python.ps1 ops/demo_provider_verify.py --environment deployed
```

모든 실제 시험의 자동 승인은 격리 시험 계정의 QA 행위다. 기존 사용자 자료·INPUT 원본은 변경/삭제하지 않는다. 성공·실패·중단 보고서와 정리 결과를 보존한다. 배포·공개 푸시·행사 제출은 이 제품 완료 작업과 분리한다.
