# RE:Build Agent 실제 Storage 오류 수정 검토

범위: backend/storage.py, tests/test_storage.py. 전체 제품 완료 검토와 구별한다.

실제 Supabase 사용자 JWT에서 없는 출력 객체 조회가 HTTP400, body statusCode404/code NoSuchKey를 반환했다. 증거: ops/runtime/demo/storage-missing-response.json. 시험 계정 정리 완료. 기존 export는 NotFoundError일 때만 최초 파일을 올리므로 일반 StorageError 때문에 실패했다.

정규화는 지정 버킷의 객체 GET·HTTP400·정확한 NoSuchKey에만 적용한다. 인증 오류 우선 거부, 다른 버킷/쓰기 오류 거부, 승인·입력 버전 검증, x-upsert:false를 유지한다. 응답 본문/헤더/키를 오류에 노출하지 않는다.

검증: 신규 회귀 RED1FAIL5PASS 확인 후 전체 Storage33PASS. 독립 code-reviewer7PASS/APPROVE, architect CLEAR. 양쪽 모두 blocker0이며 실제 비밀/네트워크 접근 없이 검토했다. 실제 브라우저의 신규 업로드→승인→파일→재시작 검증은 이 수정 후 다시 수행 중이며 아직 성공으로 기록하지 않는다.
