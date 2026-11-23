# D-219 — 1턴 시야·정적 가치 편향 극복을 위한 다중턴 탐색(2-A)·신경망 상태가치(2-B)·경량 MCTS-Q 재정렬 학습(1-B) (GPU 0·1 전용)

- 상태: Accepted
- 생성일: 2026-11-23
- 책임자: Antigravity (Gemini)
- 관련: [EP-243](../plans/EP-243-laya-multiturn-search-value-distill.md), [D-218](D-218-laya-v13-input-bugfixes.md), [D-217](D-217-laya-engine-value-rerank-training.md), [D-215](D-215-laya-foulplay-distill-then-rl.md), [D-214](D-214-laya-foulplay-primary-ladder-final.md), [D-191](D-191-no-offline-battle-gate.md), [EX-203](../experiments/EX-203-laya-engine-value-ladder.md), [EX-204](../experiments/EX-204-laya-engine-value-ladder-loss-analysis.md), [EX-205](../experiments/EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md)

## 맥락

[EX-203](../experiments/EX-203-laya-engine-value-ladder.md)·[EX-204](../experiments/EX-204-laya-engine-value-ladder-loss-analysis.md) 1500+ 래더 패배 분석과 [EX-199](../experiments/EX-199-laya-engine-value-rerank-targets.md)/[EX-200](../experiments/EX-200-laya-engine-value-rerank-train.md) 코드 감사 결과, `v13` 입력 버그 수정([D-218](D-218-laya-v13-input-bugfixes.md)) 외에 **1턴 시야 및 `evaluate.rs` 1턴 정적 가치 편향**이 핵심 병목으로 확인됐다.

1. **`evaluate.rs` 1턴 편향**: `USED_TERA = -75.0`이 1턴에서는 회수되지 않아 선제 테라를 억제하고, 장판 가중치 합(`+150~+300`)이 Cinderace 생존 가치(`-140`)를 눌러 확정 OHKO 앞 `Court Change` 자살을 유발한다.
2. **1턴 시야 한계**: 3v1 화상 10% Kingambit전(`gen9ou-2718019409` T35)처럼 2턴 이상 수읽기(희생 교체/기습 대응)와 +2 기점 스윕 차단이 불가능하다.
3. **과거 증류·온라인 탐색 교훈**:
   - `EX-182~185`의 전체 MCTS 방문 분포 증류는 실패(−0.080)한 반면, `EX-199/200`의 후보 내부 신뢰 영역 재정렬은 모델이 안정적으로 흡수했다.
   - `EX-197` 온라인 읽기의 결정 지연(`p50 9.66초`)은 CPU 직렬 2회 서빙 때문이었다. 실측 결과 `EX-200`을 물리 **GPU 0**에서 서빙하면 fp32 `batch=2`가 **`44ms`**(VRAM `1.6 GiB`), `poke-engine` Rust MCTS `5,000 iters`가 **`23~127ms`**로 턴당 총 `~0.2~0.3초` 안에 끝난다.
   - 좁은 후보 필터(`p >= 0.5*max_p`)는 `gen9ou-2718019409` T35의 `move:icebeam:normal`(`p=0.054`) 같은 전술 구제 수를 탐색 전에 탈락시키므로, 온라인 탐색은 합법 행동 전체를 탐색한 뒤 `laya` 사전확률과 결합해야 한다.

## 결정

사용자 지시(2026-11-23 대화: GPU 2·3번은 다른 프로젝트에 배정하고 **GPU 0·1번만 사용**, 2-A 먼저 진행, 2-B 포함, 경로 1은 1-B 채택·1-A 보류)에 따라 다음 3단계 체계를 채택한다.

1. **자원 격리(GPU 0·1 전용)**:
   - 모든 추론·서빙·학습은 물리 **GPU 0**(`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`)과 **GPU 1**(`GPU-c7e2d577-573f-0412-1ed6-ad6648efa454`)만 `CUDA_DEVICE_ORDER=PCI_BUS_ID`·UUID 바인딩으로 사용한다. **GPU 2·3은 일절 사용하지 않는다.**
   - CPU 다중턴 타깃 생성은 워커 `48~64`, `nice 19`, 보수적 `mem-guard ≤ 50~60 GB`로 제한하며, 시간 기반 `foul-play` Blim 128경기와 겹쳐 실행하지 않는다.
2. **경로 2-A — 온라인 다중턴 탐색 + `laya` 사전확률 융합 (`EX-206`)**:
   - 새 패키지 `integration/laya_search/`를 두고 기존 패키지(`laya_v10~v13`, `laya_value`, `laya_foe`, `laya_fp1`, `laya_regret`, `laya_distill`, `foulplay`, `.tools/foul-play/src`)는 바이트 단위로 보존한다.
   - GPU 0 서빙(`EX-200` + `v13` 입력)으로 행동 분포 $p$와 상대 분포 $q$를 단일 배치로 계산하고, `turn_action`·`forced_switch`(선택지 2개 이상)에서 `foul-play` venv `search_worker`가 합법 수 제한(`restrict`)된 `poke-engine` MCTS(`5,000 iters`)의 표본 가중 루트 $Q_{\text{mcts}}(a)$를 계산한다.
   - KL-정규화 정책 개선식 $\text{score}(a) = Q_{\text{mcts}}(a) + \lambda \ln\max(p(a), \epsilon)$($\lambda=0.03, \epsilon=10^{-4}$, 마진 `0.015`)로 최종 선택한다.
3. **경로 2-B — 리플레이 승패 신경망 상태가치 $V_\phi(\text{State})$ + 온라인 탐색 (`EX-207`, `EX-208`)**:
   - `evaluate.rs`의 정적 편향(`USED_TERA=-75`, 장판 과대평가)을 교정하기 위해, 학습용 리플레이(`v12-fresh` 등, Blim 평가 64팀 및 held-out 경기 제외)에서 `poke_engine.State`와 실제 경기 승패를 추출해 경량 신경망 상태가치 모델 $V_\phi(\text{State}) \in [0, 1]$을 GPU 0·1에서 학습한다(`EX-207`).
   - 이를 2-A의 `q`-가중 1~2플라이 전개 리프 평가 및 MCTS $Q$와 결합해 Blim 128경기(`EX-208`)로 검증한다.
4. **경로 1-B — 오프라인 경량 MCTS-5k 루트 Q 후보 재정렬 학습 (`EX-209`, `EX-210`)**:
   - 단일 forward 추론 속도를 유지하는 모델 개선 경로로, `1-A`(2플라이 오프라인 타깃)는 보류하고 `1-B`(MCTS `5,000 iters` 루트 $Q$ 기반 후보 내부 신뢰 영역 재정렬, `v13` 입력, ~6만 결정)를 채택한다. GPU 0·1 DDP로 학습(`EX-209`)하고 Blim 128경기(`EX-210`)로 평가한다.

## 결과

[EP-243](../plans/EP-243-laya-multiturn-search-value-distill.md)에서 구현·오프라인 검증·실행(`EX-206~210`)을 순차 추적한다.
