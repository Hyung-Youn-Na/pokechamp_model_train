# EX-151 — laya 엔진 판정기 구축과 실전·사람 리플레이 검증

- 상태: Completed
- 생성일: 2026-11-02
- 책임자: Claude Code
- 관련 exec plan: [EP-224](../plans/EP-224-laya-engine-judge-v8.md)
- 관련 decision: [D-201](../decisions/D-201-laya-engine-judge-v8.md)
- 비교 대상: 기존 규칙 `effect_knowledge.option_outcomes`(v4~v7 `; fails`)
- 기준 연구선: `research/model-training`

## 질문 및 목적

고정 Showdown 엔진에 결정 시점 국면을 세워 선택지의 이번 턴 실패를 판정하면, 실전에서 "확정 실패"라고 한 수가 실제로 실패하는가? 규칙 공백·기존 표시·Protean 행을 얼마나 잡는가?

## 가설 또는 qualification 목표

- **정밀도 목표**: 확정 실패로 판정한 모델 기술 중 실제로 통하지 않은 비율 99% 이상. 상대가 같은 턴에 교체한 경우는 분모에서 뺀다. 못 미치면 EX-152로 가지 않는다.
- **보고 지표**: 포괄 범위(규칙 공백 448, 기존 표시 678, Protean·Libero 43), 기존 규칙과 다른 판정, 사람 리플레이 표시 행 수와 사람이 표시된 수를 고른 비율, 결정당 지연(목표 p50 증가 0.2초 이하).

## 조건 및 변수

| 대상 | 입력 | 실제 결과 |
|---|---|---|
| 실전 9개 실행(EX-143·144·145·147·148·150, EX-147-h2h, EX-148-h2h-v6st·v6ht) | `events.jsonl`의 input 이벤트(서빙 입력 그대로) | 같은 경기 protocol: 다음 기술·턴 경계 전 `-fail`/`-immune`/`-block`(배틀 리포트 정의). 흡수·Magic Bounce 반사·빗나감·Protect도 "통하지 않음"으로 따로 센다 |
| EX-071 train·validation·test | v5 사실값 저장소와 같은 입력(prepared + `laya-item-state/v1`, 입력 해시 확인) | 사람이 표시된 수를 고른 행은 원본 리플레이(`cutoff_line` 이후)로 확인 |

판정기 설계는 D-201 결정 1이다. 판정기 소스 해시(`laya-engine-judge/v1`): `judge.cjs` a3bb97b3…, `judge.py` 381585ad…, `state.py` 02977633….

## 실행

- 판정기: `integration/laya_engine/`(`judge.cjs` 상주 node, `state.py` 국면 구성, `judge.py` 클라이언트). 단위 검사 `pokechamp/.venv/bin/python -m pytest integration/laya_engine/tests`(11건).
- 실전 검증: `python -m integration.laya_engine.validate battles <rows>`, `... summary <rows>`
- 사람 리플레이: `python -m integration.laya_engine.store build`(`laya-engine-judge/v1`), `... human`, `... outcomes`
- 반복: 1차(상대 행동 = 변화기 하나) 정밀도 92.6%로 미달 → 틀린 사례 원인을 분류해 상대 선공 경우를 넓히고 재검증(2차 99.84%) → 사람 리플레이에서 미공개 압정 제거기·대타 파괴·얼음 해제 사례를 보고 보완(3차, 최종). 각 단계 결과는 아래 표의 "반복" 절.

## 결과

### 정밀도(실전, 최종)

| 구분 | 수 |
|---|---:|
| 확정 실패로 판정한 모델 기술 | 1,253 |
| 상대가 같은 턴 교체(분모 제외) | 17 |
| 분모 | 1,236 |
| `-fail`/`-immune`/`-block` | 1,189 |
| 빗나감(명중 판정이 실패보다 먼저) | 28 |
| Magic Bounce 반사 | 15 |
| 흡수 | 2 |
| **실제로 통함** | **2**(둘 다 상대가 같은 턴에 테라스탈해 타입이 바뀜) |
| **정밀도(통하지 않음)** | **99.84%** |
| 엄격 기준(실패 줄만) | 96.2% |

- 라벨별: `fails` 1,087(실패 1,043, 빗나감 27, 반사 15, 흡수 2), `immune` 143(실패 140, 빗나감 1, 상대 테라 2), `absorbed` 6(실패 6).
- 상대 교체를 포함하면 99.60%다.

### 포괄 범위(실제 실패 중 판정기가 확정 실패로 잡은 비율)

| 묶음 | 실패 | 판정기 |
|---|---:|---:|
| 규칙 공백(D) | 448 | 419 (93.5%) |
| 기존 규칙 표시 | 678 | 600 (88.5%) |
| Protean·Libero 행(F) | 43 | 11 (25.6%) |
| 잠든 채 Sleep Talk 실패(E) | 121 | 121 |
| 상대 같은 턴 교체(A) | 703 | 9 |
| Protect 연속(B)·상대 선택 의존(C) | 232 | 0 |

규칙 공백 세부: 마지막 한 마리 Roar·Whirlwind 176/176, Wish 67/67, First Impression·Fake Out 37/37, Future Sight 34/34, Taunt 20/20, Sleep Talk(깨어 있음) 9/9, Defog 66/83, Mean Look 등 7/13, Court Change 3/9. 놓친 Defog·Court Change는 상대의 미공개 압정 설치 가능성 때문에 확정하지 않은 경우다.

### 기존 규칙과 다른 판정(선택한 수, 상대 교체 제외)

| 경우 | 수 | 실제 |
|---|---:|---|
| 판정기만 표시 | 620 | 620 모두 통하지 않음(Sleep Talk 130, Roar 119, Wish 67, Defog 66, Whirlwind 57, First Impression 37, Future Sight 34, Stun Spore 25, Taunt 20 …) |
| 규칙만 표시, 실제로 통함(규칙 오류) | 178 | Rest 127, Tera Blast 19, Curse 16, Weather Ball 7, Struggle 7, Earthquake 2(상대 Roost 선공) |
| 규칙만 표시, 실제로 실패(판정기가 보수적) | 80 | Substitute 30(상대 선공이 대타를 깰 수 있음), Rest 28(상대 선공으로 만피가 아닐 수 있음), Earthquake 20(미공개 Roost 가능) |

### 확률 실패(`likely fails`, 표시 안 함)

176건 중 132건(75%) 실제 실패. v8 표시에 넣지 않는다.

### 사람 리플레이(EX-071)

| 분할 | 턴 행 | 표시 행 | 표시 선택지 | 사람이 표시된 수 선택 | 비율 |
|---|---:|---:|---:|---:|---:|
| train | 109,864 | 31,025 | 60,838 | 1,087 | 3.5% |
| validation | 424 | 115 | 225 | 3 | 2.6% |
| test | 831 | 220 | 421 | 8 | 3.6% |

사람이 표시된 수를 고른 1,098행(전부 실행됨)의 실제 결과: 상대 교체 349, 통하지 않음 736, 통함 13. 통한 13행은 상대 같은 턴 테라 4, 사람 리플레이 자기 세트 추정 오류 9(Primarina Liquid Voice Psychic Noise 7, Dragapult Infiltrator 1, Alomomola Eject Button 1)다. 판정 논리의 오류는 없었다. `likely fails` 행에서 사람 선택은 1,971행 중 105행이다.

### 지연(실전 68,410결정, 결정당)

p50 0.032초, p90 0.104초, p99 0.349초, 최대 2.23초. 목표(p50 증가 0.2초 이하) 충족. 재현 실패 결정 0, 선택 불가 오류 12선택지.

### 반복

| 판정기 | 정밀도(통하지 않음) | 틀린 사례 |
|---|---:|---|
| 1차: 상대 변화기 하나 + 반응형 기술만 확장 | 92.6% | Defog 40(상대 압정 설치 선공), 회복기 54(상대 공격 선공), Will-O-Wisp(흡수 미집계) 등 |
| 2차: 상대 선공 공격·공개 기술·Roost·압정 경우, 혼란 해제 | 99.84% | 상대 테라 2 |
| 3차(최종): 미공개 압정·벽 제거기, 대타 HP 1, 얼음 해제 | 99.84% | 상대 테라 2 |

## 결론 및 후속 작업

- 정밀도 목표를 충족한다(통하지 않음 기준 99.84%). 엄격 기준 96.2%와의 차이는 빗나감·반사·흡수다. EX-152로 진행한다.
- 확정 실패 표시는 규칙 공백 대부분과 기존 표시 대부분을 잡고, 기존 규칙의 오표시(Rest 등 178건)를 없앤다.
- 남은 한계: 상대 같은 턴 테라·교체, usage 밖 상대 기술, 사람 리플레이의 자기 세트 추정 오류.
- 증거: `runs/model-training/EX-151/validation/`(`battle-rows.jsonl`, `battle-summary.json`, `human.json`, `human-outcomes.jsonl`/`.json`), 판정 저장소 `datasets/generated/laya-engine-judge/v1`
