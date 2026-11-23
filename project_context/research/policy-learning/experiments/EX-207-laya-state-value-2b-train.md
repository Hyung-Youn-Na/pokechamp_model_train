# EX-207 — 2-B 리플레이 승패 기반 신경망 상태가치 모델 V_phi(poke_engine.State) 데이터 추출 및 학습(GPU 0·1)

- 상태: Completed
- 생성일: 2026-11-23
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-243](../plans/EP-243-laya-multiturn-search-value-distill.md)
- 관련 decision: [D-219](../decisions/D-219-laya-multiturn-search-and-value.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

`evaluate.rs`의 하드코딩 편향(`USED_TERA=-75`, 장판 과대평가, 스윕 위협 과소평가)을 대체·보정하기 위해, 실제 Showdown 리플레이에서 복원한 `poke_engine.State`의 수치·엔티티 피처로부터 **최종 경기 승률 $V_\phi(\text{State}) \in [0, 1]$**을 밀리초 단위로 예측하는 경량 신경망 가치 모델을 학습하고, held-out 경기에서 `sigmoid(evaluate(s))` 대비 보정·판별력(Brier·LogLoss·AUC)과 EX-203 편향 사례 교정 여부를 측정한다.

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 원자료 | `v12-fresh` 등 기존 학습 리플레이(`Tracker`로 `poke_engine.State` 복원 + 실제 승패 라벨). 평가용 Blim 64팀(6종 일치) 및 held-out 경기(5% 시드 분할) 엄격 제외 |
| 모델 | `poke_engine.State` 직접 입력 경량 Entity-Attention / Residual MLP (`<1ms` 배치 추론 on GPU 0) |
| 자원 | 데이터 추출: CPU 48~64워커(`nice 19`, `mem-guard 40`, 배틀 비충돌 시); 학습: **GPU 0·1 전용**(GPU 2·3 미사용) |
| 출력 | `datasets/generated/laya-state-value/v1/`, `runs/model-training/EX-207/checkpoints/selected` |

## 결과

- **데이터셋 (`datasets/generated/laya-state-value/v1/`)**: `v12-fresh` 6,372경기 추출(Blim 평가 64팀 일치 **291경기**·무승부 3경기·`EX-199` held-out 335경기 제외), 총 **356,514행**(오류 6건). 경기 ID 단위 90/5/5 분할: `train` 321,367행(5,470경기, 승률 0.4925) / `calib` 17,448행(304경기, 0.4923) / `val` 17,699행(304경기, 0.4935).
- **1차 시도 진단(교정 완료)**: 종·특성·도구·기술 임베딩과 고정 실수치(6스탯)를 포함한 530k Transformer는 5,470경기 지문을 1에폭 만에 암기해 과적합(`val AUC 0.6446`, `val LogLoss 0.6610`).
- **최종 채택 모델 (`clean_deepsets_v2`, `52,033` params, 물리 GPU 1 단독 학습)**:
  - 종·기술 ID 및 고정 실수치(지문 6차원)를 제거한 순수 상태 동역학 23차원 + 글로벌 35차원, 구조적 제로섬 반대칭성(`V(swap(s)) == 1 - V(s)`), 에폭당 40,000행 서브샘플링·16에폭(`best_epoch=16`, `T=0.907`, train `0.5937` ≈ val `0.5948` 무과적합).
  - **held-out 304경기 (`n=17,699`) 비교**:
    - **`V_phi` (`clean_deepsets_v2`)**: **`LogLoss 0.5967` · `Brier 0.2063` · `ROC-AUC 0.7389` · `Acc 66.55%` · `ECE 0.0258`**
    - `evaluate.rs` (원본): `LogLoss 0.6424` · `Brier 0.2197` · `ROC-AUC 0.7235` · `Acc 65.96%` · `ECE 0.0780`
    - `evaluate.rs` (온도 보정 `T=1.408`): `LogLoss 0.6147` · `Brier 0.2130` · `ROC-AUC 0.7235` · `Acc 65.96%` · `ECE 0.0319`
  - **구간별 AUC (vs `evaluate.rs`)**: 초반(`T1–10`) `0.6213 vs 0.6092`(+0.0120), 중반(`T11–25`) **`0.7691 vs 0.7549`**(+0.0143), 후반(`T26+`) **`0.8283 vs 0.8168`**(+0.0114).
  - **정적 편향 교정 확인**: 동등 6v6 테라 사용 페널티 `0.281(eval_rs)` → `0.453(V_phi)`(5배 완화), 5v6 `Court Change` 장판 반전 자살 왜곡 `+72.5%p(eval_rs)` → `+6.5%p(V_phi)`(11배 완화).
- **체크포인트**: `runs/model-training/EX-207/checkpoints/selected` (`selection.json` 기록 완료; 오프라인 검증은 보고 전용이며 실전 배틀 효과는 [EX-208](EX-208-laya-search-2b-vs-foulplay-unlimited.md)에서 평가, D-191).
