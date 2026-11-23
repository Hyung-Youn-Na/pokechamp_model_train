# EX-199 — laya 후보의 foul-play 엔진 한 턴 가치와 soft target 자료(CPU·GPU)

- 상태: Completed
- 생성일: 2026-11-22
- 책임자: Claude Code
- 관련 exec plan: [EP-239](../plans/EP-239-laya-engine-value-rerank-training.md)
- 관련 decision: [D-217](../decisions/D-217-laya-engine-value-rerank-training.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

사람 래더 결정에서 laya 후보의 순위를 foul-play 엔진 평가로 다시 매긴 soft target을 만든다. 이 target은 사람 선택·laya 1순위와 얼마나 다른가?

## 조건

- 엔진 평가: 따로 빌드하려던 Rust 도구 설치가 이 세션의 권한 검사에서 거부되었다. 그래서 D-217의 대안대로 `src/genx/evaluate.rs`(PyPI sdist 0.0.48)를 Python으로 옮겼다(`integration/laya_value/evaluate.py`). 화상의 물리 기술 수는 foul-play `fp/data/moves.json`의 분류로 센다.
- 검증(`verify_evaluate.py`): foul-play venv의 엔진 `mcts()`로 대조했다. 상대는 Splash만 쓰는 포켓몬 하나이고, 양쪽은 이미 테라스탈해 트리에 테라 선택지가 없다. 이렇게 만든 상태에서는 시험하는 수 아래의 모든 말단 평가가 같으므로, 엔진 평균 점수가 sigmoid(evaluate(후) − evaluate(전))과 같아야 한다. 13개 사례가 모두 2e-3 안에서 일치했다(랭크 3종, 스텔스록·압정·끈적끈적네트와 부츠·비행·부유, 마비, 0 하한, 대타, 도구). 상태가 매 턴 바뀌는 항목(화상·독 피해, 씨뿌리기, 혼란, 벽·순풍 지속시간, 테라 −75, 특성 예외)은 이 방법으로 대조하지 못했고, 소스와 줄 단위로 맞췄다.
- 결정: `laya-compact-imitation/v12-fresh/train`(EX-195, held-out 400경기 밖 래더 경기)의 turn_action 행. 경기 단위로 표본을 뽑는다.
- p·q: EX-196 selected(GPU 4장, v12 입력, 행동 질문과 상대 질문). fp16 autocast(학습과 같은 수치)로 계산한다. 256행 시험에서 fp32보다 3.4배 빨랐고, 확률 차이는 최대 0.0008, 1순위 일치는 256/256이었다. fresh 행은 EX-196이 학습한 행이라 p는 표본 안 추정이다.
- 가치: 후보(p ≥ 0.5 × 최대 p, 최대 3개, 2개 이상일 때)마다, foul-play 추적기(`laya_fp1.tracker`, 리플레이 재생)와 foul-play 세트 표본(`laya_regret.search.sample_states`)으로 상태를 만든다. 상대 수(q ≥ 0.02)마다 한 턴을 펼친다. 가치 = Σ 표본 가중 × q × 갈래 확률 × (evaluate(후) − evaluate(전)), 단위는 엔진 점수다.
- target: 후보 밖은 laya p, 후보 안은 laya p 합 × softmax(가치/τ). τ = 20점(포켓몬 하나 HP의 1/5)이다. 시험 3결정에서 후보 간 가치 차이가 수십 점임을 보고 전체 실행 전에 정했다.
- 규모: v12-fresh train의 turn_action 368,515행(6,707경기). 경기의 5%(시드 20261199)는 held-out으로 떼어 EX-200 target 일치 평가에만 쓴다.
- 실행: `scripts/laya-value-ep239`(infer → values 48 작업자 → targets). 2026-11-22T05:32Z 시작.

## 결과

2026-11-22T07:04Z 완료(infer 05:32Z~06:23Z, values 06:23Z~07:03Z, 6,707경기 2.8경기/초, 오류 5건). 산출물은 `datasets/generated/laya-value/v1/`(`manifest.json`, `train.jsonl`, `heldout.jsonl`)이다.

| 항목 | 값 |
|---|---:|
| turn_action 행 | 368,515 |
| 후보 2개 이상 결정 | 161,259 (43.8%) |
| gold 행(가치가 매겨진 후보 2개 이상) | 161,152 |
| gold 1순위가 laya 1순위와 다름 | 79,364 (49.2%) |
| 사람 선택 = laya 1순위 | 69,421 (43.1%) |
| 사람 선택 = gold 1순위 | 61,691 (38.3%) |
| 사람 선택이 후보 안 | 127,666 (79.2%) |
| train / held-out gold 행 | 153,029 / 8,123 (held-out 335경기) |
| 제외(가치 후보 2개 미만 / 가치 행 없음) | 55 / 52 |

최선 후보 가치 − laya 1순위 가치(엔진 점수)는 p10 0, p50 0, p90 39.0, p99 93.7이다. gold 1순위로 많이 오른 수는 Earthquake 3,185, Knock Off 2,929, 교체(슬롯별 2,172~2,496), Swords Dance 2,491, U-turn 2,145, Stealth Rock 1,807 순이다.

## 결론 및 후속 작업

- 엔진 한 턴 가치는 후보 결정의 절반에서 laya 1순위를 바꾼다. 바뀐 1순위는 사람 선택과 덜 맞는다(38.3% 대 43.1%). 한 턴 평가는 다음 턴 이후(교체 뒤 받아치기, 설치기의 장기 가치)를 보지 못하므로, 이 차이는 엔진 쪽 근시안일 수도 있고 사람 쪽 실수일 수도 있다. 어느 쪽인지는 EX-201 대전으로 본다.
- 후보 밖 확률은 laya p를 그대로 두었으므로 target은 후보 안의 순서만 바꾼다.
- 후속: [EX-200](EX-200-laya-engine-value-training.md)이 이 train 행으로 이어 학습한다(07:04Z 준비 시작).
