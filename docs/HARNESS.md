# RE:Build Agent 하네스

## 선택과 설치

Oh My Codex(OMX) 0.21.5, MIT, 프로젝트 전용. 사용자에게 Windows 기준 재검토·선택·설치를 위임받았다. 이전 추천 후보 OMX와 Ouroboros를 다시 확인했다. Ouroboros의 공식 Codex 가이드는 Windows 네이티브를 실험적 경로로 다루며 WSL을 권장한다. 현재 WSL 조회는 E_ACCESSDENIED였다. OMX의 Node CLI와 Codex Desktop의 native goal을 결합한다.

- npm 패키지: `tools/omx/package.json`, `package-lock.json`. npm lifecycle scripts를 자동 실행하지 않고 설치했다.
- 프로젝트 설정: `.codex/config.toml`, `.codex/skills` 22개, prompts 31개, native-agent configs 17개.
- 설정 범위: project, team disabled, MCP none, native hooks disabled. 기존 AGENTS.md 유지. 모델과 reasoning effort 강제 지정은 제거했다.
- 네이티브 구성요소: `tools/omx/native-cache/0.21.5/win32-x64/omx-runtime/omx-runtime.exe`. 공식 배포의 체크섬 검증 경로로 설치.
- Windows process-identity가 실제 4.315초 걸려 upstream의 3초 제한을 초과했다. `dist/hooks/session.js`의 해당 Windows 제한만 15초로 조정했다. 원본과 SHA 기록: `ops/patches/omx-0.21.5-session.js.original`, `ops/patches/omx-windows-identity-timeout.json`. 조정 후 프로세스 식별 PASS. 패키지 재설치 시 이 변경은 사라지므로 같은 시험을 다시 한다.
- 진입점 `node ops/omx.mjs ...`는 설치된 OMX CLI에 프로젝트 캐시 경로와 인자를 전달할 뿐이다. 별도의 자율 실행 루프가 아니다.

## 준비 단계에서 검증한 것

`ops/harness-smoke`에서 계획 생성 → 별도 Node 프로세스에서 상태 재읽기 → goal 없는 완료 체크포인트 거부(exit 1) → pending 상태 보존을 확인했다. 이 시험은 제품 개발이나 native goal 실행이 아니다.

전체 진단은 `node ops/omx.mjs doctor`; 결과는 `ops/preflight/omx-doctor.txt`에 보존한다. 자동 훅 미설치, OMX 기본 AGENTS marker 미사용, OMX launcher로 시작하지 않은 현재 세션의 pointer 부재는 선택한 구성의 한계다. 모든 OMX 기능이 검증되었다고 해석하지 않는다.

현재 Codex CLI 0.154.0은 설치됐으나 `codex login status`가 미로그인이다. 따라서 별도 CLI worker의 모델 호출·밤샘 자동 재시작은 미검증이다. 현재 대화의 native `/goal` 실행을 사용하며, 외부 runner나 tmux에 의존하지 않는다. 앱 종료·컴퓨터 재부팅 후 자동 재개를 보장하지 않는다.

## 실행 절차

1. 17:00까지 제출하는 GOAL·SPEC·PLAN·STATE의 범위 확인을 끝내고 파일 hash를 남긴다. 준비 중 상태는 pending으로 유지한다.
2. 17:30 사용자가 GOAL.md의 **앱 입력 문장**으로 native goal을 시작한다. OMX aggregate objective와 정확히 같은 문장을 사용해야 체크포인트가 일치한다. 제품 요구사항은 `.omx/ultragoal/brief.md`와 SPEC에 보존한다.
3. 에이전트는 `node ops/omx.mjs ultragoal complete-goals --json`으로 현재 story를 받고 실제 `get_goal` 결과를 확인한다. 목표가 다르면 숨겨진 상태를 고치거나 목표를 교체하지 않는다. 실행 전 일치 확인이 필요하다.
4. story 구현·검증을 마친 뒤 fresh `get_goal` 도구의 **실제 JSON**을 파일로 보존한다. 직접 만든 goal 스냅샷은 금지한다.
5. 중간 story는 native goal을 active로 유지하고 다음으로 기록한다.

```powershell
node ops/omx.mjs ultragoal checkpoint --goal-id <실제-ID> --status complete --evidence <실제-검증-파일> --codex-goal-json <fresh-get-goal.json>
node ops/omx.mjs ultragoal status --json
```

6. 최종 story는 실제 제품 성공 기준, 변경 검토와 독립 검토 증거를 확보하고 native goal 완료 후 fresh snapshot으로 체크포인트한다. 상태 JSON만으로 완성을 선언하지 않는다. 설치된 Ultragoal 스킬의 최종 검토 절차를 따른다.
7. 각 story 후 STATE·PLAN·활동 로그·실제 세션 export를 갱신한다. 실패 시 native goal 상태 변경은 앱 도구의 규칙을 따르고, OMX ledger에는 실제 실패를 기록한다. 일반적인 난항을 외부 승인이 필요한 막힘으로 바꾸지 않는다.

## 시간·권한 경계

17:30 전에는 실행하지 않는다. 사용자 지시 없이 goal 활성화·백그라운드 실행·인증 변경을 하지 않는다. 9/22 06:00 큰 변경 중단, 09:00 기능 동결, 10:00 공식 봉인 해제, 11:40 패키지 준비, 12:00 마감. 시간 도달만으로 미완성 목표를 완료 처리하지 않는다. 마지막 검증 증거와 남은 문제를 남긴다.

봉인 중 사람 개입 예외·재시작 인정 규정은 미확인이다. 인증·권한 우회, API 키 로그, 사용 한도 회피를 하지 않는다. 설치한 하네스가 제품 AI API를 제공하는 것은 아니다.

## 공식 자료

- [OMX](https://github.com/Yeachan-Heo/oh-my-codex)
- [Ouroboros Codex 가이드](https://github.com/Q00/ouroboros/blob/main/docs/runtime-guides/codex.md)


## 제출 규칙 보완

사용자 제공 제출 이미지에 따른 `docs/SUBMISSION_REQUIREMENTS.md`와 AC17–22를 실행 목표에 포함했다. G004/G005 pending objective는 OMX의 supported steering으로 보완한다. 기존 brief는 당시 원문으로 보존하며 최신 SPEC·추가 지시·ledger를 함께 읽는다. 실제 /goal 입력 시점의 목표 문장, brief, 승인된 steering, SPEC, PLAN, AGENTS의 hash를 보존하고 같은 세션에서 결과 보고까지 유지한다.

## 2026-09-21 16:27 이후 재점검

`ops/preflight/omx-doctor.txt`: 17 PASS/3 WARN/0 FAIL. `ops/preflight/integrations-recheck.json`: 현재 native goal=null. `.omx/ultragoal/goals.json`은 5개 pending/attempt=0. Codex CLI는 미로그인이다. 설치·상태 저장 시험 통과와 외부 worker/연속 실행 성공을 구별한다. 최신 Supabase·Provider·로그인/SSO 범위는 원본 brief를 보존하며 지원 steering 명령으로 기록한다.


## 최신 사용자 확정 (2026-09-21, /goal v1.0)

GOAL.md와 ops/GOAL_INPUT.txt의 자체 완결형 원문이 현재 실행 계약이다. 필요한 프로젝트 범위 오픈소스·스킬·플러그인 설치는 이번 지시로 승인됐으며 개별 재승인 없이 설치·버전 기록·구동 검증한다. 각 의미 있는 작업 단위는 검증 후 로컬 Git 커밋하고 실패 체크포인트는 구분한다. Supabase 실제 DB/Storage/Auth/RLS 연결 검증은 필수다. 배포·공개 게시·데모/영상/발표자료·행사 제출은 추후 사용자 요청까지 실행 범위에서 제외한다. 제품 기능 완료까지 OMX 구현→실행/검토→실패 수정→재검증→기록/커밋/체크포인트 루프를 계속한다. 이 문단과 현재 사용자 지시가 이전 설치 승인·배포 운영 문구보다 우선한다.

## v1.1 실행 인계 (최신)

현재 /goal 원문은 GOAL.md 및 ops/GOAL_INPUT.txt이다. 17:00 제출/17:30 실행은 원래 일정이며 실제 접수·실행을 확인하지 않았다. 시각 경과만으로 Hands-off 시작을 기록하지 않는다. 사용자의 실제 /goal 입력 후 실행하며 현재 goal 도구 응답은 null이다.

다섯 pending story를 공식 `ultragoal steer --kind revise_pending_wording` 경로로 UI06·Supabase·두 AI 인증 경로·최종 strict 검증에 맞게 개정했다. 보고서: ops/preflight/goal-v11-steering.json. 전체 자체 완결형 프롬프트는 codexObjective와 일치한다. OMX 0.21.5에는 aggregate objective의 CLI setter가 없으므로 **활성 goal 없음·전 story pending/attempt=0** 확인 후 준비용 codexObjective만 변경하고 원본 백업/hash/사유를 ledger에 기록했다. 이 준비용 조정은 실행 중 목표 변경이나 checkpoint 우회 절차가 아니다. 실행 중에는 공식 steering 및 사용자 지시/goal 규칙을 따른다.

최종에는 ai-slop-cleaner, targeted verification, 독립 code-reviewer/architect 검토와 domain invariants를 확인한다. 결함은 `record-review-blockers`로 남기고 수정·재검증 후 실제 quality-gate-json 및 `--strict`로 완료 체크포인트한다. 설치 기본값이 advisory여도 프로젝트 최종 계약은 strict다. fresh get_goal의 실제 도구 응답만 checkpoint 근거로 사용한다.

제품 로컬 AI용 Codex CLI와 개발 OMX 하네스는 별개다. 로컬 제품 OAuth 로그인 성공이 개발 세션 자동 재시작을 보장하지 않는다. 전원·세션·한도·인증 중단 시 마지막 상태와 커밋을 보존하고 권한 우회 없이 재개 조건을 기록한다.

최신 v1.1은 본 문서와 ledger의 과거 제출 story/AC17–22 포함 표현보다 우선한다. AC17–22 운영 작업은 추후 사용자 요청 전 실행하지 않는다. 실제 두 AI 성공 호출은 필수이지만 실패/한도/시간초과 검증 때문에 실제 사용 한도를 소진시키지 않는다. 오류는 통제된 adapter 시험 또는 실제 발생 증거로 확인한다.


## 2026-09-22 인증 전 증거 정리 — 현재 상태

앞의 준비 단계 `goal=null`/pending 표현은 역사적 기록이다. 실제 사용자가 입력한 첨부 원문은 ops/runtime/GOAL_ENTERED.md에 보존되어 있고 현재 native goal은 blocked다. G001 in_progress/4pending/0complete이며, 이번 사용자 요청은 인증 전 증거 정리만이다. goal 재개나 하네스 상태 변경을 수행하지 않았다.

설치된 OMX0.21.5 strict 필드 계약을 소스에서 확인하고 docs/FINAL_VERIFICATION.md와 ops/verification/preauth-20260922/quality-gate.pending.json에 기록했다. 준비 JSON은 pending/REQUEST_CHANGES/BLOCK이며 final quality gate로 제출할 수 없다. 필드 검토와 준비 검사기 성공은 OMX strict 실행 성공이 아니다. 최종 독립 code-reviewer/architect 증거, 모든 불변 조건의 proof, 실제 검증 commands 및 cleaner 근거가 확보된 뒤 실제 --strict checkpoint를 수행한다.

Windows tmux 팀 실행이나 자동 재시작을 새 완료 조건으로 추가하지 않았다. 설치 성공·기록 보존·현재 세션의 작업과 외부 worker/연속 무중단 실행 보장을 구별한다. 아침 재개 순서와 실제 서비스/fixture 경계는 최종 검증 문서에 있다.


## 제공 INPUT 시연 도구 검증 — 2026-09-22T07:43:35.958995+09:00

이번 사용자 지시의 bounded setup 작업을 검증·독립 검토했다. OMX CLI status를 실제 확인했으며 G001 in_progress/4pending/0complete, native goal blocked다. 목표·ledger·완료 상태를 변경하지 않았다. docs/LOCAL_DATA_DEMO.md의 Verify -WithAI가 실제 서비스까지 통과한 뒤 남은 제품 검증과 최종 strict 절차를 수행한다. 이번 scoped APPROVE/CLEAR와163개 로컬 시험은 최종 quality gate 대체물이 아니다.


## Actual supplied-data integration — 2026-09-22T09:11:54.819628+09:00

- [x] Supabase Auth/DB RLS/Storage RLS/logout/cleanup actual preflight PASS; earlier PENDING_SCHEMA resolved externally (actor not observed). SQL need not be repeated for current project.
- [x] First-export actual HTTP400/NoSuchKey boundary repaired and committed77e4ca2; startup identity route fixed2646ec8. Read/write budget60s, connection/pool20s, explicit overrides and no automatic writes retry.
- [x] Fresh Python174/AI31/Node3PASS, independent scoped APPROVE/CLEAR, bounded cleaner pass. Browser command: `.\ops\demo.ps1 -Action Browser`.
- [ ] Actual P01/P06→N01/N02 UI upload/edit/approval/6outputs/restart. Current run898697175ee54b31bc3b49708e074ad1 is live; no PASS yet. All earlier failed disposable users cleaned.
- [ ] Actual API negative/changed-input/restart evidence and local OAuth model inference. OAuth still NOT_LOGGED_IN/NOT_TESTED; no silent fallback.
- [ ] Full independent/OMX strict completion gate after mandatory services/flows pass. Native goal active; prior turn progress77e4ca2. No deploy/public push.
