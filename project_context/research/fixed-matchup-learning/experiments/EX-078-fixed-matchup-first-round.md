# EX-078 — 첫1라운드 학습 체크포인트

- 상태: Completed — D-125 복구·첫라운드 진단 완료; 원실행 Incomplete 보존
- 결정: [D-123](../decisions/D-123-fixed-matchup-first-round.md)
- 계획: [EP-127](../plans/EP-127-fixed-matchup-first-round.md)

## 목적·조건

사용자 요청은1라운드 학습 과정과 첫 체크포인트 확인이다. 정책 성능 개선 검증이 아니다.
EX-076/077의 고정A/B·공개 입력 경계·P0·4층 모델·MCTS64/depth32/Exp3/T1·
AdamW/CE+MSE/batch256/최대2epoch64step·정상종료±1/0을 그대로 사용한다.
EX-077의 봉인된 P0를 hash/가중치 동등성으로 계승한다. 이전 경기 자료는 학습에 넣지 않는다.
EX-076와 동일한 미실행 train round1 일정32경기를 수집하며 양측 P0를 고정한다.
32경기가 모두 정상 완료해야 학습한다. 실패/미완료를 삭제·대체하거나 학습 목표로 쓰지 않는다.
CPU worker16/batch32는 EX-077 benchmark128의 최선 설정을 출처로 고정 계승한다.

## 원실행 범위·예산·gate (동결 이력)

단일GPU1회, 새 GPU 검증 시작부터8시간: 검증1시간/학습6시간/최종화1시간.
경기1200초·300턴, RAM48GiB/GPU40GiB/disk50GiB 등 기존 자원 상한을 유지한다.
새pilot/dev/test/2라운드 이상은0이다. test640 비용 gate는 이 진단의 실행조건이 아니다.
기존pilot 균형·검열·하루 내 전체 실행 가능성은 미확정이며 통과로 표시하지 않는다.
GPU 수치·재로딩·경계 기술 gate를 다시 확인하고32정상경기 감사 뒤 업데이트한다.
체크포인트는 모델/optimizer/RNG/replay IDs/최초시계를 포함한다. 저장·재로딩 후 유한값,
P0 대비 가중치 변화, 동일입력 예측 일치≤1e-5를 확인한다.

## 완료·복구

RD11.1/C-018 적용. 자동 추가 주기·재수집·대체0. 이미 완료한 동일identity 단위만 재개 가능하며
예약 미완료가 있으면 학습을 보류한다. 기술 결함은 원자료 보존·독립 검증 후 원상한 내 처리한다.
실제 학습step>0·round1 완전 checkpoint·재로딩검증·전수 감사/export·첫/마지막2경기
오프라인 이동 브라우저·봉인·GPU 반환을 완료 기준으로 한다. 다음 단계는 사용자 검토 후 결정한다.
경로: `.pokechamp-data/experiments/ex078-fixed-matchup-first-round/`.

## D-124 이후 현재 시간 규범

경기·검증·학습·최종화·전체 실행의 벽시계 상한을 모두 없앤다. `game_seconds`,
`total_seconds`, 각 `stage_seconds`는 명시적 `null`이며 시간은 측정·기록만 한다.
예상 소요시간으로 진입/중단을 결정하지 않는다. 단일1라운드32경기·탐색64/depth32·
300턴·학습step/epoch·자원·무결성·수동 중지 조건은 유지한다. 통신 장애 검출 timeout과
종료 정리 유예는 별도 운영 조건이다. 이번 변경으로 새 실행/재수집을 시작하지 않는다.
실행 때는 새identity로 원source/판정과 구분하며 원31정상경기를 검증 없이 버리거나 재수집하지 않는다.

## 원실행 결과

32경기 중31정상,1경기가143턴/1200초에 시간초과하여 정상32 요건 미달로 학습을 보류했다.
업데이트0·round0만 보존. 원자료 전수감사·첫/마지막2경기 브라우저·봉인·GPU 반환 완료.
[원보고](../../../../.pokechamp-data/experiments/ex078-fixed-matchup-first-round/final/report.md).

## D-125 승인된 복구

원identity `5cae56015b43256e6adcc7d7d3f49216ff3b118a6e7d526e4046adddcc774000`의
정상31은 source/모델/일정/hash/감사 검증 후 계승한다. 시간초과 슬롯
`train-1-selfplay-001-B-p2`만 동일조건/seed로1회 재수집한다. 원실패는 별도 부모에 보존한다.
경기/단계/전체 시간상한은 null이며 원최초시각과 누적경과를 기록한다. P0·업데이트0
checkpoint의 모델/optimizer/RNG/replay 상태를 유지하고 새identity와 null 시계 연결만 변경한다.
32정상 후1라운드 업데이트·재로딩검증·감사/뷰어·봉인·GPU 반환을 수행한다.
추가 재수집/다음라운드/dev/test0. 단계알람으로 관리한다.
새경로 `.pokechamp-data/experiments/ex078-fixed-matchup-first-round-untimed/`.

## 복구 최종 결과

정상31 계승·실패1 재수집 후32/32 정상, 첫라운드44update 및 완전 체크포인트·
재로딩/전수 감사·뷰어/봉인·자원 반환을 완료했다.
[복구 보고](../../../exec-plans/evidence/ep129/report.md). 원실행의 시간초과·학습0 판정은 보존한다.
사용자 후속 요청으로 동일 학습 관측의 P0/round1 기술통계를 별도 산출했다.
[사후 비교](../../../exec-plans/evidence/ep130/report.md). 새 대결·독립 성능 평가는 수행하지 않았다.
