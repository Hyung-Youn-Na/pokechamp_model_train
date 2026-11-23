# EP-238 — laya 상대 행동 예측 학습 → 한 턴 읽기 선택 → 입력 통합

- 상태: Completed
- 생성일: 2026-11-22
- 책임자: Claude Code
- 승인 근거·범위: 사용자 지시(2026-11-22 대화: "상대의 수를 읽을 수 있도록 학습할 수 있는 방법이 있을까요?"에 대한 답 뒤 "좋습니다. 해당 순서대로 실험을 진행해주세요. 지금 취침하러 가야되므로 왠만한 문제가 아니면 모두 예정대로 진행하도록 해주세요"), [D-216](../decisions/D-216-laya-opponent-prediction-one-turn-read.md)
- 관련 plan: [EP-229](EP-229-laya-opponent-model-search.md)(Active, 2단계 미등록 — 이 계획이 2단계를 이어받는다), [EP-237](EP-237-laya-observed-public-info-input.md)(v12 입력·모델), [EP-236](EP-236-laya-v11rtc-foulplay-distill-rl.md)(Paused)
- 기준 연구선: `research/model-training`

## 범위와 불변 조건

- 새 패키지 `integration/laya_foe/`. 기존 패키지·자료·봉인은 바꾸지 않는다(감싸기). foul-play는 수정하지 않는다.
- 평가 경기(held-out 400경기, EX-174 Blim collection)는 학습에 쓰지 않는다.

## 절차

1. [EX-195](../experiments/EX-195-laya-foe-prediction-data.md): 상대 예측 행과 새 모방 행 자료(CPU).
2. [EX-196](../experiments/EX-196-laya-v12-foe-training.md): EX-192에서 1 epoch 이어 학습(GPU 0~3) → 상대 예측 held-out, 잠긴 test, 테라 지식 평가.
3. [EX-197](../experiments/EX-197-laya-one-turn-read-vs-foulplay.md): 한 턴 읽기 선택 대 foul-play 128경기(EX-193과 같은 슬롯).
4. 효과에 따라 래더, 입력 통합 학습을 등록한다.

## 완료 기준

- [x] EX-195 자료
- [x] EX-196 학습·평가 보고
- [x] EX-197 경기 보고
- [x] 후속(래더·입력 통합) 등록 또는 중단 사유 기록

## 진행

- 2026-11-22 — 등록. EX-195 자료 생성 시작(`python3 -m integration.laya_foe.data_foe build`).
  - 두 선수의 결정은 같은 v12 train 파일에 섞여 있다. 래더 경기의 93%는 양쪽 행이 다 있다(표본 20만 행). 그래서 두 번 읽어 짝을 맞춘다.
  - EX-192가 쓰지 않은 래더 경기(v12-ladder-merged 밖)는 시간 예산 때문에 잘린 오래된 경기다(`laya_ladder.stores`: 최근 업로드순 예산 컷). 이 경기를 새 모방 행과 held-out으로 쓴다.
- 2026-11-22 — EX-195 완료(16:10Z). 집계: {"no opponent row": 177051, "foe_switch train": 314651, "foe_move train": 801354, "foe_other train": 108431, "imitation fresh": 441606, "imitation heldout": 26901, "foe_move heldout": 13178, "foe_switch heldout": 5053, "foe_other heldout": 1757} 1224436 98. EX-196 measure(0.0219초/행, 1,098,348행, 예상 6.7시간) 뒤 16:13Z에 학습을 시작했다.
- 2026-11-22 — EX-197 구현(`laya_foe/read.py`·`read_worker.py`·`serve_read.py`·`battle_read.py`). EX-192 모델로 사전 mock 2경기를 돌렸다(세션 scratchpad `ex197-pretest`).
  - 첫 시도는 fp1 정보가 전달되지 않았다. 조기 기록 세션(`LimitedSession.generate`)이 부모 `generate`를 부르지 않아서다. 작업자에서 Fp1Session을 가장 바깥에 씌워 고쳤다.
  - 두 번째 시도는 지운 시험 폴더의 Showdown worktree 등록이 남아 `git worktree add`가 실패했다. `git -C pokemon-showdown worktree prune`으로 정리했다.
  - 세 번째 시도는 2/2 완료, audit 통과(fp1 입력 43·44)였다. 읽기는 결정당 0.07~0.35초, 표본 8개였다. 읽기 14결정 중 6결정에서 1순위를 바꿨다(Iron Defense → Body Press 3회 등).
- 2026-11-22 — 대조군 [EX-198](../experiments/EX-198-laya-v12-foe-argmax-vs-foulplay.md)(EX-196 argmax, 포트 8104~8107)을 등록했다. `scripts/laya-read-ep238`이 EX-196 완료를 기다렸다가 EX-197·198을 병행한다.

- 2026-11-22 — EX-196 완료(학습 22:42Z, 평가 23:21Z). 상대 예측 held-out 1순위 15.23% → 48.18%, NLL 2.413 → 1.429. 사람 모방 held-out NLL 1.199 → 1.173, 잠긴 test는 구별되지 않음.
- 2026-11-22 — EX-198 완료(03:22Z): 40-82(미완료 6), 0.328, EX-193 대비 같은 슬롯 -0.008 [-0.118, +0.105]. EX-197은 04:24Z 기준 111/128(33-64, 미완료 14, 모두 1,200초 경기 시간 한도). 한 턴 읽기 2,400회 중 993회가 laya 1순위를 바꿨다.
- 2026-11-22 — EX-197 지연 원인: 서빙 HTTP 응답 중앙값 9.8초(EX-198 2.5초, EX-193 2.1초). 서빙은 전역 lock으로 한 번에 한 결정씩 처리하므로 4경기가 줄을 선다. 요청 구간 합집합으로 본 서빙 점유율은 100%(EX-198 87%), 결정당 처리 시간 상한은 2.73초(EX-198 1.45초)다. 상대 질문 forward를 turn_action 결정 6,000회 모두에서 계산했지만 실제 읽기는 2,522회뿐이었다. read_worker는 중앙값 0.11초, 입력 생성은 0.07초로 원인이 아니다. EX-198 종료(03:22Z) 뒤에도 9.3초로 CPU 경합도 주원인이 아니다. 진행 중 실험은 고치지 않고, 미완료 14경기(1,200초 한도, 약 100턴)는 이 지연의 결과로 해석한다.
- 2026-11-22 — EX-197 완료(05:07Z): 40승 73패, 미완료 15, 0.354. 같은 슬롯 EX-193 대비 +0.027 [−0.084, +0.143], EX-198 대비 +0.028 [−0.081, +0.132]. 구별되지 않는다.
- 2026-11-22 — 종료. 4단계(입력 통합)는 진행하지 않는다. 이유는 두 가지다. EX-197에 효과가 없었다. 또 한 턴 점수가 자체 설계여서 foul-play 엔진 평가(`evaluate.rs`)보다 랭크·상태이상을 몇 배 작게 매겼다. 사용자 지시("그 순서대로 계획 등록하고 진행해주세요")에 따라 엔진 평가로 후보를 다시 매긴 target 학습을 [EP-239](EP-239-laya-engine-value-rerank-training.md)로 잇는다.
