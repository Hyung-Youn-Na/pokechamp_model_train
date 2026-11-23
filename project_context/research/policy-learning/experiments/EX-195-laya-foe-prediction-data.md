# EX-195 — laya 상대 행동 예측 자료와 새 모방 행(v12, CPU)

- 상태: Completed
- 생성일: 2026-11-22
- 책임자: Claude Code
- 관련 exec plan: [EP-238](../plans/EP-238-laya-opponent-prediction-one-turn-read.md)
- 관련 decision: [D-216](../decisions/D-216-laya-opponent-prediction-one-turn-read.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

상대의 실제 선택을 라벨로 한 "상대 행동 예측" 행과, EX-192가 쓰지 않은 래더 경기의 모방 행을 만든다(D-216 결정 1).

## 조건

- 실행: `python3 -m integration.laya_foe.data_foe build`(CPU, 한 프로세스, v12 train 파일 두 번 읽기). 원천은 `v12-all/train.jsonl`, `v12-ladder/train.jsonl`이다(EX-191).
- 상대 행: 내 turn_action 행(턴 t)에 같은 경기·같은 턴의 상대 turn_action 행이 있으면 만든다.
  - 상태는 내 v12 상태를 그대로 쓴다.
  - 선택지는 내 상태 문장에서만 만든다. 상대 활성의 본 기술 + `opp set` 유력 기술, "another move not yet seen", 기절하지 않은 상대 후보 교체다.
  - 라벨은 상대의 실제 선택이다. 테라 여부는 합친다. 목록 밖 기술은 other로 둔다. 교체 대상이 선택지에 없으면 행을 버리고 센다.
- 분할(경기 단위, seed 20261195): merged 밖 래더 경기 중 400경기를 held-out으로 둔다. 상대 행과 모방 행 모두 학습에 쓰지 않는다. 나머지 merged 밖 경기는 새 모방 행(`laya-compact-imitation/v12-fresh`)과 상대 행으로 쓴다. merged 경기는 상대 행으로만 쓴다. 상대 train 행은 최대 600,000개(seed 표본)다.
- 출력: `datasets/generated/laya-foe/v1/{foe-train,foe-heldout,imitation-heldout}.jsonl`, `v12-fresh/`, 기록 `runs/model-training/EX-195/`.

## 결과

- 2026-11-21T16:10Z 완료(`runs/model-training/EX-195/build.json`).
  - 원천: 1차 패스 turn_action 라벨 1,421,475개, 경기 26,555개. 그중 merged 밖 래더 경기 7,107개, held-out 400경기.
  - 집계(상대 행 pool, 표본 전): {"no opponent row": 177051, "foe_switch train": 314651, "foe_move train": 801354, "foe_other train": 108431, "imitation fresh": 441606, "imitation heldout": 26901, "foe_move heldout": 13178, "foe_switch heldout": 5053, "foe_other heldout": 1757} 1224436 98
  - 상대 train 행: 표본 600,000개(seed 20261196).
  - 새 모방 행: `v12-fresh` train 441,606행.
  - held-out: 상대 행 19,988개, 모방 행 26,901개.
- 상대 행 라벨 비율(train pool): 기술 65%, 교체 26%, 목록 밖 기술(other) 9%. 교체 대상이 선택지에 없어 버린 행은 없었다.

## 결론 및 후속 작업

- EX-196 학습에 썼다.
