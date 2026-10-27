# EX-005 — 동일 수정 source의 순차 8판 (배틀1/요청1)

- Status: NotRun
- 날짜: 2026-09-07
- Experiment ID: `glm-concurrency-v1-sequential8`
- Study ID: `glm-concurrency-v1`
- 관련 계획: [EP-007](../plans/EP-007-model-concurrency.md)
- 설계·진행·중단·해석 규칙: [D-016](../decisions/D-016-model-concurrency.md),
  [연구 설계](../../../RESEARCH_DESIGN.md) §0.1

## 사전 조건

Max 계정, 다른 Cloud 작업 중지라는 사용자 조건으로 실행한다. glm-5.3-flash/low,
131072 output/provider 기본 context/원본 temperature·seed/요청300초/경기watchdog1200초를 유지한다.
Minimax depth와 알고리즘은 변경하지 않는다. 개발 팀만 사용하며 기존 EX-003은 corpus 근거다.

Calibration corpus는 성공한 IO self_action 및 minimax self_action/opponent_action/tool_choice/
state_value에서 각각 4개, attempt_id·actor·event_seq 순 첫 호출로 고정한다.
Corpus/hash/source/반복순서/비교순서/절대 예산 시각은 실측 호출 전 protocol.json에 seal한다.
1–10 첫 반복은 오름차순, 다음은 seed20260907 shuffle이다. C*는 3반복 오류 없음,
p95<=순차2배, 최고 중앙 JSON/s의95% 이상인 최소 C다. 미측정 수준은 검증되지 않았다.

C*>=2일 때만 EX-005/006을 같은8판 일정으로 사전 고정 순서에 실행한다.
병렬에429/timeout/integrity/격리문제 없음, 유효완료>=순차, batch실경과<순차일 때만
EX-007을 고려한다. 대진별32판일정 추정×1.5가 남은 신규작업 예산에 들어갈 때 시작한다.

실측 전체4시간, 3시간45분 신규배틀/HTTP중단 및 진행경기취소, 마지막15분 응답보존·정리다.
실패를 패배로 세지 않으며 추가slot은 없다. 기존transient 동일slot1회retry만 적용한다.
예정/처리/attempt/유효완료/미실행 분모와 fallback, batch시간/자원시간/요청·token을 구별한다.
소표본 운영 기준이며 효능·정상minimax·완료율차이·서버내부병렬 처리의 확증이 아니다.

## 결과

아직 실측하지 않았다. 선행 단계의 진행 기준을 통과하지 못하면 미실행으로 기록한다.

원래 study의 병렬8판을 구현검토로 중단하여 이 조건은 실행하지 않았다. 수정source의 새ID로 대체한다.
