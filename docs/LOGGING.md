# RE:Build Agent 로그 보존

## 실제 세션 로그

현재 루트 세션 (준비→개발 기록 포함): `01a0c294-1149-70e2-8a8a-c9634b1f450f`, 순서 1, Codex Desktop.

처음 발견한 원기록 (아래 회전 구간도 함께 보존):

`C:\Users\GS\.codex\sessions\2026\09\21\rollout-2026-09-21T15-07-58-01a0c294-1149-70e2-8a8a-c9634b1f450f.jsonl`

원본을 수정하지 않고 다음 명령으로 시각별 사본과 manifest를 만든다.

```powershell
python -X utf8 ops/export_session.py
```

다른 날짜·세션은 명시한다.

```powershell
python -X utf8 ops/export_session.py --session-id <실제-세션-ID> --session-order 2 --session-date 2026/09/22
```

기본 실행은 지정 루트 세션·날짜의 가장 최신 회전 구간을 선택한다. 도구는 지정 세션의 metadata/cwd를 확인하고, 완성된 JSONL 레코드 경계까지만 복사한다. JSONL 파싱·bytes·SHA-256·이벤트 수·첫/마지막 timestamp를 기록한다. 알려진 키 형태(OpenAI·Supabase sb_secret·GitHub·Google·JWT) 및 키 환경변수 값은 검사하여 발견 시 사본만 마스킹한다. 원기록은 보존한다. 인증 파일은 읽지 않는다.

15:19:22 KST 시험: 177개 이벤트, 2,365,737 bytes, 원본/사본 SHA-256 일치, 패턴 검사 일치 0건, JSONL 파싱 PASS. 실제 도구 실행이 포함된 현재 준비 세션의 스냅샷이며 제품 개발 완료 로그가 아니다.

신규 사본: `ops/sessions/<session-id>/<export-timestamp>-segment-<순서>/rollout.raw.jsonl` 또는 마스킹이 필요하면 `rollout.redacted.jsonl`. 인덱스: `ops/sessions/index.jsonl`. 재실행은 새 폴더를 만들며 이전 로그를 덮어쓰지 않는다.

중요한 한계:

- 현재 세션은 계속 기록 중이다. 마지막 assistant 응답과 세션 종료 이후 기록은 다음 번 export에서 포함한다. 제출 전 마지막 스냅샷의 끝 시각과 종료 여부를 확인한다.
- 사용자 제공 이미지에서 주요 JSONL 1개가 필수임을 확인했다. 실제 /goal 입력과 에이전트 결과가 같은 세션에 있어야 한다. 스키마·용량·업로드 필드는 아직 확인되지 않았다.
- 이 방법은 기록된 메시지·도구 이벤트를 보존한다. 기록되지 않은 내부 추론이나 시간을 복원하지 않는다.
- 비밀 패턴 검사만으로 모든 민감정보 부재를 보장할 수 없다. 제출본을 별도 검토하고 원본 인증정보나 `.env`는 포함하지 않는다.

## 작업 기록과 실제 원기록 구분

`ops/activity.jsonl`에는 recorded_at, session_id, sequence, phase, action, changes, verification, status, failures/recovery, human_intervention, evidence를 기록한다. 이는 보조 작업일지이며 원시 세션 로그의 대체물이 아니다. 소급 요약은 retrospective=true와 근거를 명시한다.

`STATE.json`은 현재 상태이고 `ops/activity.jsonl`은 append-only 이력이다. 세션이 나뉘면 새 ID와 순서, 이전 ID, 재개 원인을 기록한다. 결과물 생성 이벤트와 Builder 개발 이벤트를 구분한다.

실제 자율 실행 시간은 공식 측정 규칙이 확인되어야 산정한다. 대기·중단·앱 uptime·도구 실행 시간을 임의로 합쳐 자율개발 시간이라 하지 않는다.

## CLI 대안

공식 문서는 `codex exec --json`의 JSONL 이벤트 저장을 지원한다. 현재 CLI 0.154.0 help에서도 확인했다. 다만 이 환경의 CLI는 미로그인이라 실제 모델 호출/이벤트 스트림 시험은 아직 수행하지 않았다. 현재 Desktop 로그 내보내기 성공과 CLI 실행 가능을 혼동하지 않는다.

출처: [OpenAI 비대화형 실행 문서](https://learn.chatgpt.com/docs/non-interactive-mode).

## 두 번째 실제 export

2026-09-21 16:05:32 KST: 532개 이벤트, 6,592,365 bytes, 원본/사본 SHA-256 동일, JSONL 재파싱 PASS. 비밀키 패턴 검출 0건. 전체 종료 로그가 아닌 활성 세션의 해당 시각까지 기록이다. 이후 개발 기록은 `--phase development`, 최종 준비 기록은 `--phase submission`으로 구분한다.

## 확정된 제출 규칙

`docs/SUBMISSION_REQUIREMENTS.md`의 E1–E3를 따른다. E1 실제 /goal 원문, E2 주요 JSONL 1개는 필수다. E3 나머지 JSONL ZIP 1개는 선택이다. 15:19·16:05 준비 스냅샷은 실제 goal 실행 전이므로 E2 충족으로 표시하지 않는다. 이후 개발 스냅샷도 사용자 목표 입력 근거와 최종 결과를 별도로 확인하기 전에는 E2 충족으로 표시하지 않는다. 제출 직전 같은 세션의 실제 goal 입력 이벤트와 결과 보고 이벤트를 확인하고, 이벤트 위치/시각·session_id·SHA를 기록한다. 문자열 검색만으로 goal 실행을 판정하지 않는다. 실제 입력한 목표가 파일을 참조하면 입력 당시 문서와 hash도 보존한다. 다른 세션을 합성하지 않는다.

## 회전 구간 복구와 내보내기 (2026-09-21 21:19 KST)

기존 검색식은 루트 ID로 끝나는 첫 파일만 찾아 18:46 이후 기록을 누락했다. 최신 도구는 원래 파일과 루트 ID 뒤에 UUID가 붙는 회전 파일을 모두 발견하고, 파일명 시작 시각 순으로 번호를 부여한다. 번호 범위는 명시한 날짜이며 날짜가 바뀌면 해당 날짜를 따로 내보낸다. 지정 루트 ID와 다른 파일은 읽지 않는다.

아래 명령은 실제 구간 각각을 별도 폴더·JSONL·manifest로 보존한다. 파일을 합치거나 가상 메시지를 추가하지 않으며 기존 스냅샷과 인덱스 행은 유지한다.

```powershell
python -X utf8 ops/export_session.py --session-id 01a0c294-1149-70e2-8a8a-c9634b1f450f --session-order 1 --session-date 2026/09/21 --phase development --all-segments --goal-reference 152fa17c-8642-4567-9611-5cf82ea37345/goal-objective.md
```

`--all-segments`를 생략하면 가장 최신 구간만 내보낸다. `--goal-reference`는 명시한 참조 문자열의 존재를 메시지 역할별로 검사할 뿐 첨부 파일을 열지 않는다. 결과에는 원문 대신 boolean만 저장한다. 실제 사용자 메시지의 선두 `/goal` 또는 첨부 참조와 assistant 인용·도구 출력은 구분한다. 이 검사는 입력 흔적이며 native goal 실행·완료 판정이 아니다.

각 manifest와 append-only 인덱스에 `root_thread_id`, `native_metadata_session_id`, `filename_segment_id`, `segment_sequence`, 날짜 범위, 발견한 구간 수, 원본/완성 레코드/사본 SHA-256을 기록한다. 실제 3개 파일의 native metadata ID는 모두 루트 ID였다. 파일명 suffix UUID를 native metadata ID로 바꾸어 기록하지 않는다.

| 구간 | filename_segment_id | 기록 범위 (KST) | 이벤트 |
|---|---|---|---:|
| 1 | 없음 | 15:08:13.873–18:46:04.389 | 1,782 |
| 2 | 01a0c35b-bd05-72d3-8f30-fd66d93404d6 | 18:46:04.516–18:48:01.561 | 32 |
| 3 | 01a0c35d-cfa1-7001-980d-14e92ac71775 | 18:48:20.363–21:18:40.255 | 1,744 |

복구 스냅샷 폴더는 `ops/sessions/01a0c294-1149-70e2-8a8a-c9634b1f450f/20260921T211919449935+0900-segment-001`부터 `-003`까지다. 세 사본의 패턴·환경변수 마스킹 수는 0이다. 내보낸 뒤 원본 스냅샷 길이까지의 SHA-256, 완성 레코드 접두부 SHA-256, 사본 SHA-256, 실제 JSONL 재파싱 이벤트 수, 인덱스 manifest 일치를 3개 구간 모두 독립 확인했다. 최신 사본 SHA-256은 `cea86dd012457fe39a02e44866b6aebccfbdaa3430a35aac593006b48da02e24`다.

최신 구간의 `user_goal_reference_seen=true`, `user_goal_command_seen=false`, `assistant_goal_reference_seen=false`를 확인했다. `final_goal_result_assessed=false`, `session_still_active=true`이며 제품 완료·최종 세션 종료·E2 제출 적격을 선언하지 않는다. 제출용 주요 JSONL 선택은 실제 결과 보고가 나온 후 별도 확인한다.

회귀 검증: `.venv\Scripts\python.exe -m pytest tests/test_session_export.py -q`. 실제 로그 대신 합성된 회전 구간으로 최신 선택, 구간별 보존, 기존 인덱스 유지, 미완성 꼬리 제외, 비밀 마스킹, 메시지 역할 구분, metadata/cwd 불일치 거부를 검증한다.
