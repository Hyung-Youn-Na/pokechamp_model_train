# EX-161 — laya 렌더러 v10(정보 전부 + lock + 전략, 2,048토큰) 학습(GPU0)

- 상태: Completed
- 생성일: 2026-11-03
- 책임자: Claude Code
- 관련 exec plan: [EP-227](../plans/EP-227-laya-renderer-v10.md)
- 관련 decision: [D-204](../decisions/D-204-laya-renderer-v10-all-info.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-149](EX-149-laya-v7-opponent-sets-training.md) selected(v7t)
- 기준 연구선: `research/model-training`

## 질문 및 목적

v1~v9 정보와 lock·전략 정보를 모두 넣은 2,048토큰 입력(v10)으로 학습하면 사람 선택 재현이 어떻게 바뀌는가? 배틀 효과는 [EX-162](EX-162-laya-v7t-v10t-battle256.md)가 본다.

## 가설 또는 qualification 목표

- **qualification**:
  - 사전 측정에서 정한 한도로 `v10-all` 길이 초과 제외가 0.5% 이하다(D-204 결정 5).
  - validation 512에서 오프라인 렌더와 서빙 렌더가 같다(`v10 parity`).
  - 단위 검사가 통과하고, 사전검사 loss가 감소하며, 재로딩 logit이 일치한다.
- **판정 없음(보고 전용)**: D-191.
- **보고 지표**: 잠긴 test 1,024행, EX-161 − EX-149 같은 행 차이, replay 클러스터 bootstrap 95%(10,000회, 시드 20261062)
  - 전체 NLL·일치율, 교체 행, 테라 지식 held-out A/B 정답률
  - 정보별 확인 지표(보고 전용, 학습 중단·방법 변경에 쓰지 않음):

| 묶음 | 지표 |
|---|---|
| 실패 표시 (#15~16) | `fails`·`likely fails` 선택지 확률 합 |
| lock (#27~32) | `locks` 표시 행과 `locked`·`locked?` 표시 행의 일치율과 교체 확률 |
| 위협·risk (#22, 26, 40) | 최악 피해 80% 이상인 교체에 준 확률, 테라 선택 확률 |
| 루프·PP (#9, 37, 38) | 멈춘 `streak` 행에서 같은 수에 준 확률 |
| 매치업·형세 (#33~36) | `duel … lose` 행의 교체 확률, 선봉 결정 일치율, `wincon` 규칙이 실제 끝까지 살아남은 포켓몬과 맞는 비율 |
| 예측 (#39) | `opp wall`로 표시된 포켓몬이 실제로 다음에 들어온 비율, 그 행의 일치율 |

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 위치 |
|---|---|---|---|
| EX-161 selected | EX-149와 같다: 시작 모델 `laya-typed-decisions@e929ae5c`, 3 epoch, soft-CE, 선택지 순서 섞기, lr, seed 0, micro batch 8 × 누적 8, EX-071 분할, 테라 지식 train 57,143행 | 렌더러 v7 → v10, `max_len` 1,024 → 2,048, head 512 → 768, 선택지 48 → 64(사전 측정 규칙으로 확정) | `runs/model-training/EX-161/checkpoints/selected/` |

### 렌더러 v10

D-204 결정 1~3이 규칙을 소유한다.

- 사실값 `laya-compact-features/v10`: v9 보정 세트 안에서 계산한 v5 사실값, v7 사실값, threat(최악·유력), 엔진 판정(`laya-engine-judge/v1`), lock, 전략(#33~41). 상대 PP는 `laya-early-history/v1`로 센다.
- 서빙은 `early_history`를 요청에 넣는다(v6ht와 같은 opt-in 필드).

## 실행

- 실행기: `python -m integration.laya_v10.cli {measure,features,data,parity,train,evaluate}`(이름은 구현 때 확정)
- GPU0. 학습 시간 상한 없음. 중단: 제외 비율 > 0.005(한도를 한 번 올린 뒤), GPU 오류, parity 불일치
- 자동 재실행 없음.

## 결과

- 2026-11-03 05:28Z~19:59Z(GPU0). 보고 `runs/model-training/EX-161/report.md`, 선택 `selection.json`, 로그 `runs/model-training/EP-227.log`.
- **qualification**: 모두 통과.
  - 사전 측정(validation 512)에서 기본 한도(2,048 / head 768 / 선택지 64)로 제외 0. 전체 p99 1,296, 최대 1,370.
  - `v10-all` train 130,411 · validation 512 · test 1,024, 길이 초과 제외 0.
  - parity 512행 불일치 0.
  - 사전검사 loss 2.1553 → 1.9875.
  - 첫 자료 생성은 `strategy._run` 캐시 결함으로 멈췄다. 기록된 행은 없었다(`diagnostics/data-v1/defect.json`). 고친 뒤 다시 생성했다.
- 학습: 187,154행(모방 130,011 + 테라 지식 57,143), 3 epoch 51,412초. validation NLL은 epoch 1 1.5165, epoch 2 1.4414, epoch 3 1.4679였고 **선택 epoch 2**다.

| 모델 | 잠긴 test NLL | 일치율 | ECE |
|---|---:|---:|---:|
| EX-149 v7 | 1.4332 | 45.78% | 0.0302 |
| EX-161 v10 | 1.3686 | 48.63% | 0.0356 |

- 같은 행 차이(EX-161 − EX-149, n 1,018, replay 218):
  - 전체 NLL −0.0610, 95% [−0.0918, −0.0288]. 일치율 +2.55%p.
  - 교체 행(364) NLL −0.0335, 95% [−0.0851, +0.0176].
  - 라벨별: 강제 교체 −0.1122(구간이 0 아래), 기술 −0.0799(구간이 0 아래), 자발 교체 −0.0079, pivot +0.0526, 선봉 −0.0035(일치율 −3.23%p). 뒤의 셋은 구간이 0을 포함한다.
- 정보별 확인 지표(보고 전용):
  - `fails`·`likely fails` 선택지 확률 합: 0.0528 → 0.0313(95% [−0.0278, −0.0156]). argmax 4 → 2.
  - `locks` 표시 행(59): NLL −0.1375 [−0.2675, −0.0076], 일치율 +11.86%p. `locked?` 행(68): +13.24%p, `locked` 행(28): −3.57%p(구간 0 포함).
  - 최악 80% 이상 교체의 확률 합: 0.2064 → 0.1833(95% [−0.0305, −0.0155]). argmax 85 → 65.
  - 멈춘 `streak` 행(18)에서 같은 수의 확률: 0.5728 → 0.6173(95% [−0.0219, +0.1180]). 사람도 18행 중 11행에서 같은 수를 골랐다.
  - `duel lose` 행(285): NLL −0.0498, 일치율 +4.21%p. `opp wall` 행(637): NLL −0.0629, 일치율 +3.30%p.
  - 평가기가 따로 집계하지 않은 지표: lock 행과 `duel lose` 행의 교체 확률, `wincon` 적중 비율, `opp wall` 실제 등장 비율. 테라 선택 확률도 보고서에 없다.
- 테라 지식 held-out: A 전체 96.9 → 96.2%(A3 93.7 → 91.3%, A5 84.7 → 82.3%), B 전체 95.9 → 95.8%.

## 결론 및 후속 작업

- v10은 잠긴 test에서 v7보다 사람 선택을 더 잘 재현한다. 전체 NLL 차이의 구간이 0 아래다.
- 실패·위험 교체 선택지에 주는 확률이 줄었고 lock 표시 행의 재현이 크게 나아졌다. 멈춘 반복 행의 같은 수 확률은 줄지 않았다.
- 정보를 한꺼번에 넣었으므로 어떤 정보가 효과를 냈는지는 나눌 수 없다. 단일 시드다.
- 배틀 효과는 [EX-162](EX-162-laya-v7t-v10t-battle256.md)에 기록했다. 이 체크포인트는 laya-play `v10t`(v1.9.0)로 배포됐고, [EX-167](EX-167-laya-v10-ladder-training.md)의 렌더러 기준이 됐다.
