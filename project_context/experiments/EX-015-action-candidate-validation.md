# EX-015 — 식별 수정과 요청 후보 조건 검증

- Status: Completed
- 날짜: 2026-09-07
- 근거: D-017, EP-009, 사용자의 단계 검증·조건부32판 지시

## 사전 조건

새 ID `identity-candidates-v1`. 과거 EX-014의 nickname 오류8판을 pinned 원본에서 재현했고
수정 후16 actor replay의 팀6/객체 동일성이 통과했다. 기존 출력 오류4개도 모두 거부된다.
로컬 `identity-candidates-local8-v1`은 b04팀6/12와 기존 seed/진영을 유지하고 Cloud 역할만
seeded Random으로 대체했다. 8/8 유효 완료,16 actor source seal을 통과했다.

기존 EX-004 고정20개와 EX-014 실패4개를 새 후보/요청으로 봉인했다. source event hash,
관찰 target state, 후보 및 공개/관찰/추정 출처를 보존했다. 동시성1과10 각각3회, 총144회,
실패 보충 없음. 모두 출력 계약/전송 성공, 실제 HTTP겹침10, p95(10)<=2*p95(1)이 gate다.
동시성 순서는1의3회 뒤10의3회다. 최대처리량 탐색이나 과거 C*승계가 아니다.
각 요청 첫 오류는 terminal이고 다음 독립 corpus 요청으로 보충하지 않는다.

Cloud 첫 단계부터4시간, 신규3시간45분 중지,15분 정리. `cloud-intent.json`에 epoch 및
전체 parent source와 corpus hash를 봉인한다. 기준 미달이면 Cloud8/32판을 시작하지 않는다.
통과 시 `identity-candidates-cloud8-v1`(8/10), 8/8 오류0을 통과하고32판 추정*1.5가 남은
예산에 들어갈 때만 `identity-candidates-cloud32-v1`(10/10)을 실행한다. 새8/32판도 실패
재시도/보충0이다. 별도 ID·분모이며 minimax depth 오류와 fallback은 계속 보고한다.

## 원자료

[검증 directory](../../.pokechamp-data/action-validation/identity-candidates-v1/),
[로컬 결과](../../.pokechamp-data/action-validation/identity-candidates-v1/local-result.json),
[corpus](../../.pokechamp-data/action-validation/identity-candidates-v1/corpus.json).

## 완료 결과

144회 모두 처리했고140회가 출력 계약을 통과했다. 오류4건은 전부 corpus23의 현재 사용
불가한 `gigatonhammer` 선택이다(순차3회,동시성10의 마지막1회). 새 후보 검증기가 즉시
거부했으며 교정/재질문/대체 행동은 없다. 이전 상대 행동 실패3상태는 각6반복 모두 통과했다.
HTTP200은144/144, 전송 오류0이다. 요청p95는 순차2392.60ms/동시성10은2690.15ms로
1.124배이며 실제 HTTP겹침10이다. 출력 전체 성공 gate가 실패하여 Cloud8/32판은 미실행이다.

Cloud 실제 batch129.97초(2.17분), prompt296,898/completion7,905 tokens다.
로컬8판 실제 batch37.17초,8/8유효·오류0이었다. Minimax depth 오류는 그대로이며 새 Cloud
배틀이 없어 새 fallback 비율은 없다. 과거 실험·분모와 합치지 않는다. 금액 billing은 제공되지
않아 token으로 보고한다.

122 tests와 변경 파일 Ruff(E/F/I/W,기존 E501 제외)가 통과했다.16 local actor seals,
144개 호출 seal,Cloud38개 parent source hash/archive,기존 corpus20개 source/event 동일성,
EX-014 plan·64 actor seals를 검증했다. 실제 credential 값 비노출,pinned submodule clean,
8100–8109 포트 해제,broker 잔여permit0 및4시간 이내 정리가 통과했다.

[상세 보고서](../../.pokechamp-data/action-validation/identity-candidates-v1/report.md),
[기계 판독 결과](../../.pokechamp-data/action-validation/identity-candidates-v1/report.json),
[로컬 viewer](../../.pokechamp-data/experiments/identity-candidates-local8-v1/index.html).
