# EX-077 — 하루 내 고정 대진 공개 상태 학습

- 상태: Incomplete — 사용자 요청 중지; 학습/test 미시작
- 결정: [D-122](../decisions/D-122-fixed-matchup-day.md)
- 계획: [EP-126](../plans/EP-126-fixed-matchup-day.md)

## 유지 조건

[EX-076](EX-076-fixed-matchup-mcts.md)의 질문·고정 A/B 팀/hash·공개 정보 경계·모델·
탐색·학습/replay/dev·평가640·성공/불확실성·자원 크기·뷰어/해석 조건을 그대로 편입한다.
Qwen 계승0, 탐색64·깊이32·Exp3·온도1, 무작위 P0 출발을 유지한다.
EX-076-fnt-v2의 동일 P0와 정상uniform32를 source/manifest/hash 연결로 계승한다.
미완료P0 pilot16은 이번 승인으로1회 재측정하며 미시작16과 합쳐32를 완료한다.
이전 실패 기록을 삭제하거나 새로운 정상 결과로 덮어쓰지 않는다.

## 변경한 예산과 실행 gate

사용자 조건에 따라 새 실행의 첫 GPU 검증부터24시간/1GPU1회로 한정한다.
단계 최대1/1/6/15/1시간(검증/pilot/학습/test/최종화). 남는 시간을 학습 연장에 쓰지 않는다.
pilot32 완료 뒤 EX-076과 같은 `2×640×max(묶음시간/32,p95/worker수)`로 test 비용을 추정한다.
test 예상≤15시간이고, 이미 쓴 시간+학습 최대6시간+test 예상+최종화1시간≤24시간일 때만 학습한다.
팀 균형·검열·기술 gate는 유지한다. 예상은 보장이 아니며 실제24시간 상한에서 중단한다.
성능 개선을 적용하면 새 worker/batch 조합을 실측하고 모델 입력 tensor/출력 동등성을 검증한다.
정상uniform32는 재수집하지 않는다. 기존 benchmark는 참고이며 새 source의 비용을 다시 측정한다.

## 복구·보고

RD11.1/C-018을 적용한다. 이번에 명시한 P0 pilot16 재시도 외 자동 재수집/대체0.
공급자 판단 실패는 경기 격리, 공유 경계/비유한/무결성 실패는 의존 단계 중단이다.
최초24시간을 재개·교정으로 갱신하지 않는다. 이전 EX-076의 원시계/실패/Incomplete는 보존한다.
정상 경기 전수 감사/export와 최대12층화 브라우저 표본, 봉인·자원 반환을 완료 절차로 둔다.
실행 경로는 `.pokechamp-data/experiments/ex077-fixed-matchup-day/`이며 성능은 아직 미평가다.

## 중지 결과

사용자가 학습과정 검토 후 결정하기 위해 중지를 요청했다. GPU 검증·benchmark128 통과 후
P0 pilot 중 SIGTERM 종료했다. 기존uniform32 계승, 새P0 정상2/미완료16/미시작14,
실제 학습/update/dev/test0. 전체 시간 예측 gate는 미확정이다.
원자료 감사/export·오프라인 브라우저4표본·봉인·GPU 반환을 완료했으며 자동 재개하지 않는다.
[중지 보고](../../../exec-plans/evidence/ep126/stop-report.md). 실행 당시 동결 원문은 source에 보존한다.
