# EP-239 — foul-play 엔진 평가 target 학습과 시간 제한 없는 foul-play 평가

- 상태: Completed
- 생성일: 2026-11-22
- 책임자: Claude Code
- 승인 근거·범위: 사용자 지시(2026-11-22 대화, "EX-197 끝나면 그 순서대로 계획 등록하고 진행해주세요", "그리고 성능을 보기 위한 실험은 시간 제한을 모두 해제하고 테스트 해주세요"), [D-217](../decisions/D-217-laya-engine-value-rerank-training.md)
- 관련 plan: [EP-238](EP-238-laya-opponent-prediction-one-turn-read.md)(Completed), [EP-236](EP-236-laya-v11rtc-foulplay-distill-rl.md)(Paused)
- 기준 연구선: `research/model-training`

## 범위와 불변 조건

- 새 패키지 `integration/laya_value/`. 기존 패키지·자료·봉인은 바꾸지 않는다(감싸기). foul-play(소스·venv)는 수정하지 않는다. 엔진 빌드는 `.tools/poke-engine-eval/`에 따로 둔다.
- EX-195 held-out 400경기와 EX-174 Blim collection은 학습에 쓰지 않는다.

## 절차

1. [EX-199](../experiments/EX-199-laya-engine-value-targets.md): 엔진 평가 빌드·검증, EX-196 p·q 계산(GPU), 한 턴 가치와 soft target 자료(CPU).
2. [EX-200](../experiments/EX-200-laya-engine-value-training.md): EX-196에서 1 epoch 이어 학습 → 잠긴 test, held-out 모방·상대 예측, target 일치 평가.
3. [EX-201](../experiments/EX-201-laya-engine-value-vs-foulplay-unlimited.md): EX-200 argmax 대 foul-play 128경기, 시간 제한 없음.
4. [EX-202](../experiments/EX-202-laya-v12-foe-vs-foulplay-unlimited.md): EX-196 argmax 대 foul-play 128경기, 시간 제한 없음(EX-201의 같은 슬롯 대조군, 병행).
5. 효과가 보이면 래더 대전을 등록한다.

## 완료 기준

- [x] EX-199 자료
- [x] EX-200 학습·평가 보고
- [x] EX-201·202 경기 보고
- [x] 후속(래더) 등록 또는 중단 사유 기록(EX-203)

## 진행

- 2026-11-22 — 등록.
- 2026-11-22 — Rust 도구 설치(엔진에 `evaluate` 바인딩을 빌드하려던 것)가 권한 검사에서 거부되었다. 대안으로 `evaluate.rs`를 Python으로 옮기고 엔진 `mcts()`로 13개 사례를 대조했다(모두 일치, EX-199).
- 2026-11-22 — EX-199 시작(05:32Z, `scripts/laya-value-ep239`). EX-202 대조군 대전은 EX-200을 기다릴 필요가 없어 바로 시작했다(05:37Z, `scripts/laya-battles-ep239 EX-202`). 시간 제한은 `integration/laya_value/battle_value.py`에서만 푼다. 대상은 경기 1,200초→10^8초, 실험 10시간→10^4시간, 양쪽 턴·결정 수 300/600→10^6이다. `scripts/laya-train-ep239`는 EX-199를 기다렸다가 EX-200 → 평가 → EX-201을 진행한다.
- 2026-11-22 — EX-199 완료(07:04Z). gold 행 161,152개, 이 중 49.2%에서 1순위가 laya 1순위와 달라졌다. 사람 선택과의 일치는 gold 1순위 38.3%, laya 1순위 43.1%다. EX-200 준비·measure를 거쳐 학습을 시작했다(약 2.8시간 예상).
- 2026-11-22 — EX-202가 06:52Z에 foul-play 엔진 panic(Taunt) 한 건으로 전체가 멈췄다(37/128). `actor_unlimited`에서 엔진 panic을 그 경기의 미완료로 바꾸고, 산출물을 `halt-1/`에 보존한 뒤 07:08Z에 남은 90슬롯을 재개했다. 자세한 내용은 EX-202에 있다.
- 2026-11-22 — EX-200·EX-202 완료. 사용자 지시("EX 200 모델로 레더 대전을 다음날 오전 8시까지 진행해주세요")로 [EX-203](../experiments/EX-203-laya-engine-value-ladder.md)(EX-200 공식 래더, GPU 3, 2026-11-23 08:00 KST까지)을 추가해 EX-201과 병행한다.
- 2026-11-23 — EX-201 완료(48-80, 0.375, EX-202 대비 +0.055 [−0.040, +0.156]). EX-203 래더 완료(104판 53승 51패, 레이팅 1332→1505, 상대 평균 1472). 엔진 target 쪽으로 정책은 옮겨 갔지만, foul-play 대전에서 개선은 신뢰구간 안에서 입증되지 않았다. 완료로 닫는다.
- 2026-11-23 — 완료 뒤 사용자 요청으로 [EX-204](../experiments/EX-204-laya-engine-value-ladder-loss-analysis.md)(EX-203 고레이팅 패배 분석)를 덧붙였다.
