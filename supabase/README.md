# RE:Build Agent Supabase 연결

대상 프로젝트는 wsziosnttnxefgfbgpeq다. 제품 계정은 Supabase Auth 사용자이며 대시보드 계정과 다르다.

## 현재 확인된 상태

2026-09-21 22:05 KST의 격리된 실제 시험에서 로그인, 세션 갱신, 로그아웃 이후 갱신 차단이 통과했다. 시험 사용자 2명은 삭제했다. DB의 rb_entities 조회는 404였고, rebuild-agent bucket 확인은 400이었다. DB·Storage·RLS 전체 연결 성공으로 해석하지 않는다.

실제 증거는 ops/runtime/supabase-components-20260921T130533Z.json과 ops/runtime/supabase-schema-existence.json이다.

## 적용할 스키마

인증된 프로젝트 SQL Editor 또는 승인된 DB 관리 연결에서 migrations/20260921210000_rebuild_agent_storage.sql 전체를 실행한다. 이 파일은 단일 트랜잭션이며 다음을 구성한다.

- 사용자 소유 rb_entities, 버전/원본 해시/승인/양식 불변 조건
- 사용자 JWT의 auth.uid()를 검사하는 DB RLS
- 비공개 rebuild-agent bucket과 소유자 경로별 읽기·새 객체 쓰기 정책
- 기존 원본을 덮어쓰지 않는 Storage 정책
- RLS를 유지한 원자적 초안 승인 RPC

현재 세션의 publishable/secret key는 제품 REST·Auth·Storage용이다. SQL 관리 인증이나 DB 비밀번호로 간주하지 않는다. 이 Codex 세션에는 호출 가능한 Supabase 관리 플러그인이 없다. 스키마 파일 준비만으로 실제 적용을 완료했다고 기록하지 않는다.

기존 동명 테이블/정책/bucket이 있다면 먼저 소유 프로젝트와 구조를 확인한다. 실패한 트랜잭션은 롤백된다. 성공한 스키마를 되돌리기 위해 기존 사용자 테이블이나 bucket을 자동 삭제하지 않는다.

## 실제 연결 검증

스키마 적용 후 프로젝트 루트의 PowerShell에서 실행한다.

    .\ops\python.ps1 ops/runtime/supabase_live_verify.py

관리 키는 스키마 메타데이터의 limit=0 확인, 격리 시험 사용자 생성, 그 시험 데이터 정리에만 사용한다. 실제 DB·Storage 교차 접근 시험은 두 사용자의 JWT로 실행한다. 시험 ID가 아닌 기존 데이터는 정리하지 않는다.

종료 코드 0 및 PASSED, auth_login_verified, db_rls_verified, storage_rls_verified, logout_verified, cleanup_complete가 모두 참이어야 해당 검증이 통과다. PENDING_SCHEMA는 미완료다. 그 뒤 실제 제품에서 신규 업로드→근거→검토/승인→출력과 서버 재시작 후 지속성을 별도로 검증한다.

키 값이나 인증 응답 본문을 보고서에 복사하지 않는다. .env와 ops/private는 Git에서 제외한다.

## 실제 제품 HTTP 인증 검증

2026-09-21 22:36 KST: 최신 로컬 제품 서버의 /api/auth/login, /me, /refresh, /logout을 실제 Supabase 시험 계정으로 실행했다. 로그인·본인 확인·세션 갱신·로그아웃·로그아웃 후 갱신 차단·잘못된 비밀번호 거부·인증 응답 no-store가 통과했고 시험 계정은 삭제했다.

증거: ops/runtime/product-auth-live-20260921T133655Z.json. 재현 스크립트: ops/runtime/product_auth_live.py. 이는 실제 제품 HTTP 인증 성공이며 DB/Storage/RLS와 OAuth의 미완료 상태를 바꾸지 않는다.
