# EX-197 — laya 한 턴 읽기 선택 대 foul-play, Blim 128경기(CPU)

- 상태: Completed
- 생성일: 2026-11-22
- 책임자: Claude Code
- 관련 exec plan: [EP-238](../plans/EP-238-laya-opponent-prediction-one-turn-read.md)
- 관련 decision: [D-216](../decisions/D-216-laya-opponent-prediction-one-turn-read.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

내 후보와 상대 예측 분포로 한 턴 결과를 계산해 고르면 foul-play 상대 성적이 오르는가(D-216 결정 2, 보고 전용)?

## 조건

- 모델: EX-196 selected(상대 예측 포함). 같은 EX-174 Blim 128슬롯, foul-play 3초 × 4, CPU 서빙.
- 선택 규칙(`integration/laya_foe/serve_read.py`, `read.py`, `read_worker.py`):
  1. laya 확률 p(v12 입력)를 구한다. turn_action이면 같은 상태로 상대 질문(EX-195 선택지)에 답한 상대 분포 q도 구한다.
  2. 후보는 p ≥ 0.5 × 최대 p인 행동이고, p순으로 최대 3개다. 후보가 2개 이상일 때만 읽는다.
  3. foul-play 추적기(`laya_fp1.tracker`, 경기마다 하나, 모든 결정을 받음)에서 foul-play 자신의 세트 표본(`laya_regret.search.sample_states`)을 뽑는다. 표본마다 후보 × 상대 행동(q ≥ 0.02) 쌍을 `poke_engine.generate_instructions`로 한 턴 펼친다. 결과 상태를 점수 매긴다. 점수는 포켓몬마다 HP 비율 + 생존 0.25 − 상태이상 0.1, 활성 랭크 단계당 0.04이고, 내 쪽에서 상대 쪽을 뺀다. 확률로 가중해 평균한다.
  4. 가치가 가장 높은 후보가 laya 1순위보다 0.05 넘게 높으면 그 후보를 고른다. 아니면 laya 1순위를 고른다.
  5. 서빙 확률은 laya p에서 고른 수와 1순위의 값을 맞바꾼 것이다. 등록된 argmax 정책이 고른 수를 둔다. 응답마다 `read`(p, q, 후보, 가치, 선택, 작업 시간·표본·오류)를 남긴다. 작업자 오류가 나면 1순위로 둔다.
- 실행기: `integration/laya_foe/battle_read.py`. `laya_fp1.battle_fp1`의 Fp1Session(작업자에서 조기 기록 세션 위에 씌움)과 fp1 audit, `laya_v12.battle_v12`의 v12 검사·identity를 쓴다. 스크립트 `scripts/laya-read-ep238`(EX-196 완료 뒤 EX-198과 병행, 포트 8100~8103).
- 비교: 같은 슬롯 EX-193(v12 argmax), 같은 모델 argmax [EX-198](EX-198-laya-v12-foe-argmax-vs-foulplay.md).
- 한계: 점수는 한 턴짜리 휴리스틱이라 근시안적이다. 그래서 laya가 비슷하게 망설일 때만 바꾸도록 제한했다. 래더 봇(laya-play)에는 foul-play 추적기가 없어 이번에는 래더로 보지 않는다.

## 결과

보고: `runs/model-training/EX-197/report.md`, 뷰어 `exports/battle_viewers/ex197/index.html`. 실행 2026-11-21T23:26Z~2026-11-22T05:07Z.

- 40승 73패, 미완료 15(모두 경기 1,200초 한도, 마지막 턴 86~122). 정상 종료 113/128 < 120이라 판정은 보류다. 평균 0.354 [0.259, 0.455].
- 같은 슬롯 차이: EX-193 대비 +0.027 [-0.084, +0.143](113슬롯), EX-174 대비 +0.009 [-0.097, +0.105], EX-198(같은 모델 argmax) 대비 +0.028 [-0.081, +0.132](109슬롯, 경기 클러스터 bootstrap, 별도 계산). 모두 구별되지 않는다.
- 읽기: 응답 7,431회 중 turn_action 6,628회에서 상대 질문을 계산했다. 그중 2,781회에서 읽었고(후보 2개 이상), 1,136회(41%)에서 laya 1순위를 바꿨다. 작업자 오류는 0이고, 작업 시간은 중앙값 0.11초, p95 0.68초다.
- 바꾼 수에는 회복·방어 기술(Roost, Rest, Recover, Protect)과 Body Press, Earthquake, Knock Off가 많았다.
- 지연: 서빙 응답 중앙값 9.66초(EX-198 2.5초). 원인은 서빙 포화다. 서빙 하나가 전역 lock으로 4경기를 한 결정씩 처리한다. 상대 질문 forward를 turn_action마다 계산해 결정당 처리 시간이 1.45초에서 2.73초로 늘었고, 점유율이 100%가 되었다. 읽기 작업자와 CPU 경합은 원인이 아니다(EP-238 진행 로그).

## 결론 및 후속 작업

한 턴 읽기는 foul-play 상대 성적을 구별되게 바꾸지 못했다. 해석에는 세 가지 한계가 있다.
1. 점수는 자체 설계였다(foul-play 기준이 아님). poke-engine 0.0.48 `src/genx/evaluate.rs`와 비교하면 랭크(+1당 30점 대 HP 4%)와 상태이상(화상 최대 −50 대 −10)을 몇 배 작게 매겼다. 해저드·도구·대타·벽·테라도 없다. 그래서 회복기를 높게, 능력치를 올리는 수를 낮게 보았다.
2. 지연 때문에 긴 경기 15개가 잘렸다(EX-198은 6개).
3. 한 턴만 본다.
후속: 점수를 foul-play 엔진 평가로 바꿔 사람 데이터의 후보 순위를 다시 매긴 target으로 학습하는 계획을 등록한다(EP-239). 성능 평가 대전은 시간 제한 없이 돌린다(사용자 지시 2026-11-22).
