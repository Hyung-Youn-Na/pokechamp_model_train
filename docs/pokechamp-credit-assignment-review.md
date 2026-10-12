# 턴 단위 credit assignment를 위한 RLCD + PPO 설계 검토

- 작성일: 2026-10-06
- 상태: **검토 메모 — 승인된 연구 설계·실험이 아니다.** 아래 제안을 실행하려면 별도 EX 승인과
  등록이 필요하다. 연구 방법의 원문은 [RESEARCH_DESIGN](../project_context/RESEARCH_DESIGN.md)이며,
  이 문서는 그것을 대체하거나 변경하지 않는다.
- 범위: 작성 시점에 실행 중이던 [EX-075](../project_context/experiments/EX-075-abyssal-rl-next.md)에는
  영향이 없다.

## 검토 대상 아이디어

Gen9 OU 배틀 에이전트를 학습할 때 "승리한 경기의 모든 결정에 같은 positive return"을 주는 대신,
각 결정의 품질에 따로 credit을 주려는 아이디어다. 원 제안의 요점은 다음과 같다.

- `V(s)`(현재 상태의 승리 확률)와 `Q(s,a)`(행동 후 승리 확률)를 이용한다.
- 후보 신호: `r_t = V(s_{t+1}) − V(s_t)`, `A = Q(s,a) − V(s)`, 반사실 advantage
  `Q(s,a) − mean_a Q` 또는 `Q(s,a) − max_{a'≠a} Q`.
- KO 같은 사건 보상은 sack·pivot·tempo 희생을 잘못 평가하므로 피하고, 숨은 정보와 확률 요소를
  고려해 belief state를 평가한다.
- 경기 뒤쪽 턴부터 모든 합법 행동으로 분기해 결과가 바뀌는 "인과적 결정 지점"을 찾고, 이를
  RLCD 선호 데이터나 PPO reward/advantage로 쓴다.
- `(state, candidate) → 기대 결과` 형태의 JEV식 evaluator로 후보를 직접 비교한다.

## 용어 정리

- **RLCD**: 이 프로젝트에서는 *RL for Calibrated Decisions*를 뜻한다. Brier 같은 proper scoring
  rule로 확률을 보정하는 방법이며, Yang et al. 2023의 contrastive distillation과는 무관하다
  ([rlcd-lite README](../.tools/rlcd-lite/upstream/README.md)). EVE는 bandit 형태
  (`r = c − p_a`, [EVE README](../.tools/eve-rlcd/upstream/README.md))이고, EX-072 이후 학습은 선택
  행동의 W/D/L half-Brier를 PPO에 결합한 변형이다([D-114](../project_context/decisions/D-114-selfplay-rlcd.md)).
- **JEV**: TypeSafe의 typed-decision API다. 후보 중 하나를 고르고 choice 확률과 confidence를
  돌려준다. 후보별 value를 내지 않는다. 이 프로젝트에서 "JEV 계열"은 세 오픈소스 RLCD 환경을
  가리킨다([D-096](../project_context/decisions/D-096-pokemon-training-objective.md)).
- **후보별 Q 모델**: `(state, candidate) → Q`를 실제로 학습한 것은 Kev
  ([EX-066](../project_context/experiments/EX-066-joint-q-training.md))다.

### 수치 출처 표기

- 표시가 없는 수치는 저장소 문서의 기록값이다.
- **[계산]** 표시는 이번 검토에서 원자료로 직접 계산한 값이다. 문서 기록값이 아니며, 특히
  유의성 수치는 paired 검정으로 다시 확인해야 한다.
- **[가설]** 표시는 검증되지 않은 주장이다.

---

## A. 핵심 평가

**결론:** 방향은 맞다. "결과가 아니라 결정의 품질에 credit을 준다"는 목표 자체는 옳다. 하지만
지금 formulation을 그대로 구현하면 **노이즈를 정답으로 학습**할 위험이 크다. 반드시 고쳐야 할 점이
다섯 가지 있다.

1. **reward와 advantage를 혼동하고 있다.**
   - 목적(승률)은 그대로 두고 **advantage 추정기**를 바꿔야 한다.
   - 턴별 reward를 새로 정의하면 목적 자체가 달라진다.
2. **Q가 정의되어 있지 않다.** Q(s,a)의 값은 다음 세 가지를 정해야 확정된다.
   - 이탈한 뒤 누가 이어서 두는가(후속 정책)
   - 상대 정책
   - 정보 조건(실제 상태인가, belief인가)

   실제 사례: [EX-065](../project_context/experiments/EX-065-joint-q-data.md)에서는 후속 정책인
   Abyssal이 Tera를 쓰지 않아 Tera 후보의 가치가 왜곡됐고,
   [EX-067](../project_context/experiments/EX-067-abyssal-tera-joint-q.md)로 다시 수집했다.
3. **rollout 한 번으로 인과를 판정하는 것은 통계적으로 무효다.**
   - [EX-060](../project_context/experiments/EX-060-single-battle-branch-rollouts.md)에서 CRN 분기
     5,344개 중 79%(4,239개)가 원래 선택과 같은 결과였다.
   - EX-065에서는 후보당 32회 rollout을 해도 최선 후보가 동률인 상태가 52%(1,399/2,668)였다.
   - **[계산]** 같은 데이터에서 최선이 차선보다 유의하게 나은 상태는 약 14%뿐이다(EX-067 약 16%).
   - 따라서 "A→패, B→승"을 한 번 관측한 것은 대부분 노이즈다.
4. **privileged rollout 값을 비선형 라벨로 쓰면 숨은 정보가 샌다.**
   - 실제 숨은 정보로 돌린 결과를 argmax 라벨이나 선호쌍으로 바꾸면, 정책은 볼 수 없는 정보를
     아는 것처럼 학습된다.
   - 고정된 팀 풀(train256)에서는 이것이 팀 암기로 이어진다.
5. **"RLCD preference data"는 용어 혼동이다.** 위 용어 정리대로 이 프로젝트의 RLCD는 확률 보정
   방법이다. 그래서 RLCD의 자연스러운 자리는 **보정된 evaluator를 학습하는 것**이다.

**가장 큰 실증 리스크**

- 이 프로젝트는 이미 `(state, candidate) → Q` 모델을 학습해 본 적이 있다(Kev, EX-066).
  - 76.8 GPU시간을 들여 best-action 정확도가 53.4%→54.1%, regret이 0.190→0.165로 바뀌는 데 그쳤다.
  - 학습된 Q로 승률이 오른 것은 한 번도 입증되지 않았다(EX-062 Blocked, EX-063 1경기, EX-064 개선 없음).
- 반면 rollout 라벨 자체는 CPU에서 약 0.2초면 하나가 나온다(EX-065). 싸고 빠르다.
- 그래서 **"Q 모델만 잘 학습하면 된다"는 가정이 이 설계에서 가장 위험하다.** 분기한 상태에서는
  rollout 값을 직접 쓰는 쪽으로 설계를 기울여야 한다.
- 또 EX-066은 Abyssal끼리 둔 경기의 상태로 학습했다. 학습자가 실제로 마주치는 상태 분포와
  달랐다는 뜻이다(DAgger가 지적한 covariate shift).

### 질문별 결론

| 질문 | 결론 |
|---|---|
| 최적의 credit assignment | **기본:** terminal reward를 유지하고, 보정된 critic으로 GAE(λ≈0.9) advantage를 계산한다. **보강:** 선택한 결정에서만 CRN 분기 기반 `Q̂ − Σπ_old·Q̂`를 쓴다. "모든 턴에 +1"과 event reward는 둘 다 폐기한다 |
| Q를 직접 학습하면 V보다 유리한가 | on-policy 데이터만 있다면 **아니오**. V가 더 쉽게 학습되고, 고르지 않은 후보의 Q에는 감독 신호가 없다. 반사실 데이터가 있을 때만 유리하며, 분기한 상태에서는 학습된 Q 대신 rollout 값을 직접 쓴다 |
| 반사실 값을 PPO advantage로 바로 쓸 수 있나 | **조건부로 가능.** 후속 정책이 π_old이고, baseline이 Σπ_old·Q̂이고, CRN을 쓰고, π가 실제로 방문한 상태라면 TRPO의 *vine* 추정량이 된다. 그 결정에서는 GAE를 **대체**하고 둘을 합산하지 않는다. 후속 정책이 Abyssal이면 π의 advantage가 아니므로, 별도 teacher 항이나 Q-Prop control variate로만 쓴다 |
| shaping용으로만 쓰고 GAE는 따로? | **shaping에는 쓰지 않는다.** γ=1에서 shaping은 baseline을 바꾸는 것과 같고, GAE critic과 같은 정보를 두 번 계산하게 된다 |
| terminal reward + ΔV를 같이 쓰면 문제없나 | Φ(종단)=0, 라운드 안에서 Φ 고정, Φ가 행동과 무관이라는 조건이면 최적 정책은 바뀌지 않는다. 그래도 네 가지 문제가 있다. ① γ=1과 MC에서는 효과가 0이다. ② critic과 같은 V를 쓰면 이중 계산이다. ③ V(s_T)를 예측값으로 두면 reward hacking이 된다. ④ λ<1이면 Φ의 편향이 그대로 학습된다 |
| stochastic rollout에서 Q 통계량 | **평균 기대 점수** `E[W + 0.5·D]`. 숨은 정보, 우연, 상대, 후속 정책 모두에 대해 기대값을 취한다. 추정 불확실성은 Beta posterior나 paired 검정으로 따로 관리한다 |
| 평균 vs risk-adjusted vs worst-case | **평균.** 결과가 사실상 승/패 이진이라(EX-065 무승부 0) 어떤 위험 선호를 넣어도 승률과 같은 순서가 나온다. worst-case는 동시 선택 게임에서 과도하게 수동적인 정책을 만든다. 위험 조정은 추정 불확실성에만(LCB 필터) 적용한다 |
| 상대 hidden set을 여러 가설로 샘플링해야 하나 | 선형 손실(회귀, advantage-선형 PG)이라면 실제 숨은 정보로 돌린 rollout으로 충분하다. 기대값이 `E[Q\|h]`가 되기 때문이다. argmax, 선호쌍, 상태별 판정처럼 비선형으로 쓸 때는 K=4–8개 가설을 샘플링해야 한다 |
| backward causal search가 계산 가능한가 | 전체 트리 탐색은 **불가능**. 한 수만 이탈하고 나머지는 빠른 후속 정책(Abyssal, CPU)이 두는 방식은 선택한 상태에 한해 **가능**하다(라운드당 약 2 CPU시간). LLM을 후속 정책으로 쓰면 같은 규모에 약 80 GPU시간 이상이 들어 불가능하다. backward 순서 자체는 필요 없다 |
| 중요한 결정을 고르는 기준 | 결정에 의존하는 신호를 쓴다. 단일 후보를 제외하고, leverage `4V(1−V)`에 후보 간 spread·정책 엔트로피·불일치를 곱한다. 데이터가 쌓이면 학습형 regret 예측기로 바꾼다. \|ΔV\|는 운에 좌우되므로 단독으로 쓰면 안 된다 |

---

## B. 추천 전체 architecture

```text
 [수집] π_old vs Abyssal 64경기 ─► 결정 기록 (h, 후보, π_old, p_old, V_old, sim snapshot)
              │                                    │
      전 결정 │                                    │ 선택 결정 (경기당 M개 + ε 무작위)
              ▼                                    ▼
  GAE(λ) advantage · critic λ-target     CPU 분기 rollout (Abyssal 후속, CRN, N 적응)
              │                                    │  → 모든 후보의 Q̂^A(h,c)
              ▼                                    ▼
 ┌────────────── Frozen Qwen3.5-4B-Base (공유) ──────────────────┐
 │ actor-LoRA  → pointer head π(c|h)                              │
 │   L = PPO(Â_GAE) + α·teacher(A^T) + 0.1·BC  (KL 0.02 공동 정지) │
 │ critic-LoRA → q^π head (GAE용) / q^A head (teacher·선택용)      │
 │   L = RLCD Brier + 숨은 정보 aux head (학습 전용)               │
 └────────────────────────────────────────────────────────────────┘
```

- **Track 1 (모든 결정, 저비용):** PPO + GAE. 현재 결정 기록에 `baseline`(=Σπ_old·q_old)과 모든
  후보의 `wdl_probabilities`가 이미 저장되어 있다. 그래서 GAE는 **추가 추론 없이** 계산할 수 있다.
- **Track 2 (선택한 결정, CPU):** π 자신이 방문한 상태에서 분기 rollout을 돌린다. EX-065처럼
  Abyssal끼리 둔 상태를 쓰지 않는 DAgger 방식이다.
- **actor와 critic의 LoRA 분리:** **[가설]** 지금은 WDL gradient가 공유 LoRA를 통해 정책 분포까지
  움직인다. 이것이 KL 조기 정지를 앞당기고 있을 가능성이 있다(I의 ablation 2로 검증).
- **q^π head와 q^A head 분리:** 두 head는 서로 다른 양을 추정한다. q^π는 π가 이어서 둘 때의
  가치이고, q^A는 Abyssal이 이어서 둘 때의 가치다. 섞으면 critic이 편향된다.

---

## C. reward / value / advantage 수식

표기는 다음과 같다.

- `h_t`: 학습자의 t번째 **결정 시점** 관측 이력. 턴이 아니라 결정 단위이며, 기절 후 교체와
  U-turn 후 교체도 포함한다.
- `C(h)`: 그 시점의 합법 후보 집합.
- `G ∈ {1, 0.5, 0}`: 최종 결과 점수.

**C1. 목적과 reward (고정)**

```text
J(π) = E[G],  r_t = 0 (t < T−1),  r_{T−1} = G,  γ = 1
```

**C2. Evaluator (RLCD)**

```text
p_φ(·|h,c) ∈ Δ{W,D,L},   q_φ(h,c) = p_W + 0.5·p_D,   V(h) = Σ_c π_old(c|h)·q_φ(h,c)

y_{T−1} = onehot(G)
y_t     = (1−λ)·p̄_old(h_{t+1}) + λ·y_{t+1},     p̄_old(h) = Σ_c π_old(c|h)·p_old(h,c)
L_RLCD  = ½‖p_φ(h_t,c_t) − y_t‖²                 (고른 후보, on-policy 분포형 TD(λ))
        + ½‖p_φ(h,c) − (W,D,L)/n‖²               (분기한 상태의 모든 후보, full-information)
```

**C3. Track 1 advantage (GAE)**

```text
δ_t = V(h_{t+1}) − V(h_t),   δ_{T−1} = G − V(h_{T−1})
Â_t = Σ_{k≥0} λ^k·δ_{t+k}        (λ = 1이면 현행 G − V(h_t)와 같음)
```

- **정규화 단위:** 라운드 단위(최대 1,536개 결정)의 평균과 표준편차로 정규화한다. step당 RL 표본이
  16개뿐이라 batch 단위 정규화는 불안정하다.
- **privileged critic 옵션:** critic은 `V(h_t, s_t)`처럼 실제 숨은 상태까지 입력으로 받는
  history-state critic을 써도 된다(Baisero & Amato 2022: 편향 없음). 숨은 정보 때문에 생기는 분산을
  줄여 준다.
- **actor 입력 제한:** actor에는 privileged 정보를 절대 넣지 않는다.

**C4. Track 2 반사실 advantage**

```text
Q̂^μ(h,c) = (1/N)·Σ_i score(rollout(s_t, c, μ, seed_i))     seed는 후보와 무관(CRN, EX-065 방식)
V̂^μ(h)   = Σ_c π_old(c|h)·Q̂^μ(h,c)
A^T(h,c) = Q̂^μ(h,c) − V̂^μ(h)
쌍 비교:  b = #{seed: c 승 ∧ c' 패}, d = #{seed: c 패 ∧ c' 승},  z = (b−d)/√(b+d)   (McNemar)
```

- **`max_{c'≠c} Q̂` baseline은 쓰면 안 된다.** 노이즈가 섞인 값들의 최댓값은 위로 편향된다
  (winner's curse). **[계산]** 다른 후보 약 8개, SE 0.039를 넣으면 편향이 약 0.055다. EX-065에서
  최선과 차선의 평균 격차가 0.082이므로 **편향이 신호와 같은 크기**이고, 거의 모든 후보가 음수
  advantage를 받게 된다.
- **uniform 평균도 피하는 게 좋다.** 기대값으로는 편향이 없지만, π가 절대 고르지 않을 쓰레기
  후보까지 평균에 들어간다. 그러면 무난한 후보의 부호가 부풀려지고 분산도 커진다.

**C5. Actor 손실**

```text
L_actor = −E_t[min(ρ_t·Â_t, clip(ρ_t, 0.8, 1.2)·Â_t)]
          − α·E_{h∈B}[ Σ_c π_θ(c|h)·A^T(h,c) ]          ← A^T에 선형
          + 0.1·L_BC                                     (KL(old‖θ) ≥ 0.02이면 step 미적용)
```

- **선형이 핵심이다.** teacher 항이 A^T에 선형이면, 실제 숨은 정보로 돌린 rollout 값을 써도
  기대값은 `E_{s|h}[A^T] = A^T(h,c)`가 된다. argmax, 저온 softmax, 선호쌍으로 바꾸는 순간 이 성질이
  깨진다.
- **이 항의 의미:** Abyssal 후속 정책에 대해 한 수 앞을 개선하는 approximate policy iteration이다.
  π가 greedy(Q^A)에 수렴하면 이론적으로 Abyssal 미러(약 50%) 이상이 보장된다. π가 아직 Abyssal보다
  약한 지금 단계에 맞는 신호다.
- **편향 없는 대안 (Q-Prop):** π가 Abyssal 수준에 가까워지면 이 방식으로 전환한다. Q̂가 무엇이든
  기대 gradient는 원래 PG와 같고, Q̂가 Q^π와 상관이 높을수록 분산이 줄어든다.

  ```text
  Ã_t  = Â_t − (Q̂(h_t,c_t) − V̂(h_t))
  L_qp = −E_t[clip-surrogate(Ã_t)] − E_h[Σ_c π_θ(c|h)·(Q̂(h,c) − V̂(h))]
  ```

**C6. potential shaping 검토**

```text
r'_t = r_t + Φ(h_{t+1}) − Φ(h_t),  Φ(종단) = 0   ⇒   Σ_{k≥t} r'_k = G − Φ(h_t)
```

- γ=1이고 MC면 이것은 **Φ를 baseline으로 쓴 것과 정확히 같다.** 턴 단위 credit은 생기지 않는다.
  턴 단위 credit은 reward 정의가 아니라 λ<1의 bootstrapping에서 생긴다.
- GAE critic V와 함께 쓰면, critic은 잔차 `V^π − Φ ≈ 0`을 배우게 되고 `δ' ≈ ΔΦ`가 된다. 같은
  정보를 두 번 계산하는 셈이다.
- `V(s_T)`를 실제 결과 대신 모델 예측으로 두면 `Σr' = V̂(s_T) − V(s_0)`가 된다. 에이전트가 모델의
  종단 예측을 최적화하게 되고, 이것이 reward hacking이다.

**C7. 운 분해 (후기 단계 옵션)**

```text
V(h_{t+1}) − V(h_t) = [Q(h_t,c_t) − V(h_t)]                  결정 품질
                    + [E_ω V(h'(c_t,b_t,ω)) − Q(h_t,c_t)]    상대의 실제 선택 b_t
                    + [V(h_{t+1}) − E_ω V(h'(c_t,b_t,ω))]    운 (급소·명중·난수)
```

- **방법:** 같은 행동 쌍으로 해당 1턴만 k번 다시 시뮬레이션해 운 항을 추정하고 제거한다.
  backgammon 분석 도구의 luck 계산과 같은 발상이다.
- **비용:** 결정마다 V를 k번 평가해야 하므로 GPU 부담이 크다. 선택한 결정에만 적용한다.

**C8. 중요 결정 점수**

```text
κ(h) = 1[|C(h)|>1] · 4V(h)(1−V(h)) · ( std_c q_φ(h,c) + a·H(π_old)/ln|C| + b·1[argmax q_φ ≠ argmax π_old] )
       + 구조 플래그 (Tera 사용 가능, 기절 후 교체, 랭크업 기술 보유, 상대 KO 사정권, 내 포켓몬 KO 위협)
학습형: R̂(h) ≈ Σ_c π_old(c|h)·[max_{c'} Q̂(h,c') − Q̂(h,c)]      (π의 regret 예측)
```

---

## D. trajectory와 counterfactual rollout 처리

### D1. 저장 단위

- **결정 단위 저장:** 단일 후보 결정은 제외한다. 결정마다 sim snapshot과 PRNG 상태를 함께 저장한다.
- **actor 무상태화:** EX-065에서 cold rollout 시간의 약 80%가 actor snapshot pickling이었다. actor를
  프로토콜 로그만으로 복원할 수 있는 무상태 구조로 만드는 것이 좋다.

### D2. 데이터 포맷

`p_old`, `per_candidate`는 일부 후보만 예시로 적었다.

```json
{"decision_id":"exNNN/r12/g031/d17","turn":14,"kind":"forced_switch",
 "candidates":["move:1","move:1:tera","move:2","switch:3"],
 "pi_old":{"move:1":0.41,"move:1:tera":0.07,"move:2":0.30,"switch:3":0.22},
 "p_old":{"move:1":[0.12,0.0,0.88]}, "v_old":0.17, "outcome":"L",
 "snapshot_ref":"snap/g031/d17.json.zst", "adv_gae":-0.06, "critic_target":[0.05,0.0,0.95],
 "branch":{"follow_up":"abyssal@<sha>","opponent":"abyssal@<sha>","hidden":"truth",
   "n":16,"per_candidate":{"move:1":[2,0,14],"switch:3":[7,0,9]},
   "paired":{"best":"switch:3","second":"move:2","b":6,"d":1,"z":1.89},
   "adv_teacher":{"move:1":-0.07,"switch:3":0.21},
   "selection":{"score":0.83,"reasons":["leverage","spread"],"random":false}}}
```

### D3. 분기 rollout 절차

```python
def branch_q(d, follow_up=ABYSSAL, n0=8, nmax=32, hyps=("truth",)):
    seeds = crn_seeds(d.decision_id, nmax)              # 후보 id는 seed에 넣지 않음
    res = {c: [] for c in d.candidates}
    for i, seed in enumerate(seeds):
        h = hyps[i % len(hyps)]
        for c in d.candidates:
            res[c].append(rollout(d.snapshot, c, follow_up, hidden=h, seed=seed))  # 1/0.5/0
        if i + 1 == n0 and all_identical(res):  break   # 결과 불변 → leverage 없음
        if i + 1 >= n0 and top2_separated(res, z=2.0):  break   # McNemar로 조기 종료
    return {c: mean(r) for c, r in res.items()}, res
```

### D4. 비용

근거는 EX-065 실측값이다. rollout 하나에 0.19 CPU초, 16 worker로 초당 72.9개, 후보 평균 9.2개,
경기당 결정 약 30개([EX-073](../project_context/experiments/EX-073-abyssal-rl.md))다.

| 방식 | 라운드당 rollout 수 | CPU시간 | 16 worker 벽시계 |
|---|---:|---:|---:|
| 전 결정 × N=32 | 565k | 약 30h | 약 2.2h |
| 선택 M=4 × 평균 N=16 | 37.7k | 약 2.0h | **약 9분** |
| 같은 규모, LLM 후속 정책(vine) | 37.7k × 결정 약 15개 | 약 80 GPU시간 이상 | 불가 |

참고로 EX-075의 한 라운드는 수집 약 7.8분, 학습 약 6.5분이었다(r24 기준). 선택 방식이라면 CPU
여유에 따라 학습 단계와 겹쳐서 돌릴 수 있다. LLM 후속 정책 비용은 EX-073의 결정 지연(평균 0.95초,
GPU당 동시 2경기)을 기준으로 추정했다.

### D5. backward 탐색 재해석

- **backward 순서는 의미가 없다.** 각 상태의 반사실 평가는 서로 독립이다. 한 번 이탈하면 그 뒤는
  후속 정책이 두므로, 뒤쪽 턴의 결과에 앞쪽 판정이 의존하지 않는다.
- **쓸모 있는 변형은 point of no return 탐색이다.**
  - 패배한 경기에서 `max_c Q̂(h_t,c) > ε`인 마지막 t를 이분 탐색으로 찾는다. 비용은 O(log T)다.
  - 그 직전 2–3개 결정을 중요 결정 후보로 쓴다. 단조성이 보장되지는 않으므로 heuristic이다.
- **근거:** EX-060에서 패배 경기 22개 결정 중 9개는 이미 모든 후보가 패배였다. 승부가 이미 기운
  상태에 예산을 쓰지 않게 된다.

### D6. 장기 행동을 hacking 없이 평가하는 방법

대상은 sack·pivot·setup·hazard·status·positioning 같은 장기 행동이다.

- **보상을 주지 않는다.** 행동이나 사건에 직접 보상을 걸지 않고, 승률 기준 Q와 advantage로만
  평가한다.
- **행동 공간은 Showdown 명령 단위다.** 후보는 "기술 i(+Tera)" 또는 "교체 j"다. "Sack Ting-Lu" 같은
  표현은 실제 명령이 아니라 사후 분석용 태그다.
- **조건 세 가지가 필요하다.**
  1. **상태 입력에 장기 자산이 담겨야 한다.** 해저드 층수, 스크린·날씨 남은 턴, 맹독 카운터, Tera
     잔여 여부 등이다. V가 보지 못하는 가치는 credit을 받을 수 없다.
  2. **horizon이 충분해야 한다.** λ를 0.9 이상으로 두거나 rollout을 쓴다.
  3. **후속 정책의 역량을 고려해야 한다.**
     - Q^π는 π가 마무리를 못 하면 setup을 과소평가한다(비관 함정).
     - Q^Abyssal에는 Abyssal의 스타일 편향이 들어간다(EX-065 Tera 사례).
- **검증 방법:**
  - 범주별 probe set에서 regret을 추적한다.
  - KO 수나 교체 빈도 같은 행동 통계가 승률과 따로 움직이면 hacking 신호로 본다.

---

## E. belief-state 처리

**현재 상태**

- 지금 RL 입력에서는 상대의 미공개 정보가 null이다. 가설, 확률, 속도 범위가 모두 없다.
- JEV v4/v5 입력에는 Smogon 추천 세트 기반의 "hypothesized" 기술, 피해% 범위, 속도 범위가 있다.
  다만 확률은 없다.

**제안 (단계적)**

1. **가설 생성:** gen9ou 사용 통계와 추천 세트에서 종마다 상위 K개의 완전한 세트를 만든다.
2. **가중치 갱신:** 관측된 증거로 가설의 가중치를 조정한다.
   - 공개 정보 일치: 기술, 아이템, 특성, Tera
   - 행동 순서에서 나오는 속도 제약: 우선도, 트릭룸, 마비, 스카프
   - 관측 피해량과 계산 범위의 비교(우도)
   - 아이템 흔적: 생명의구슬 반동, 먹다남은음식 회복, 구애 고정의 반증, 부스터에너지 발동
3. **입력 표현:**
   - 상대 포켓몬마다 상위 3개 가설만 결정적 포맷으로 넣는다.
     예: `item: Scarf .42 / Booster .31 / 기타 .27; speed 280–372; tera: Fairy .5`
   - 토큰 상한을 둔다. Kev 입력이 평균 14.9k 토큰이었다는 교훈이 있다.
4. **보조 head:** 숨은 속성(아이템, Tera, 미공개 기술, 속도 구간)을 예측하는 head를 둔다.
   - 학습 때는 시뮬레이터의 실제 값으로 감독한다. belief가 표현에 내재화되고, 보정 정도도 측정할
     수 있다.
   - 추론 때 입력은 관측 정보뿐이다.
5. **입력 권한 구분:** critic은 privileged 입력을 받아도 되지만 actor는 받으면 안 된다.
6. **rollout 방식:**
   - 1단계에서는 실제 숨은 정보로 rollout하고 선형 손실에만 쓴다.
   - 2단계에서는 상태별 라벨이 꼭 필요한 곳에만 K=4–8개 가설을 샘플링한다.

**주의점**

- **strategy fusion:** rollout 안에서 우리 쪽 후속 정책이 상대의 실제 세트를 보면 Q가
  과대평가된다(PIMC의 고전적 문제). poke-env Abyssal처럼 각 플레이어가 자기 관측만으로 두게 해야
  한다.
- **팀 암기:** train 팀 256개가 고정되어 있어 상대 세트를 외울 수 있다.
  - 학습 팀의 EV·아이템·Tera를 같은 종 안에서 무작위로 바꾸는 증강을 넣는다.
  - train 팀과 test 팀의 성능 차이를 모니터링한다.

---

## F. PPO와 RLCD의 역할 분리

| | RLCD (evaluator) | PPO (actor) | Teacher 항 |
|---|---|---|---|
| 학습 대상 | 모든 후보의 p(W/D/L \| h,c) | π(c\|h) | π(c\|h), 선택 결정만 |
| 데이터 | on-policy λ-target, rollout 분포 | on-policy 결정 | 분기 rollout |
| 손실 | Brier (proper scoring) | clip surrogate(Â_GAE) | advantage-선형 |
| 역할 | critic, 선택 점수, 분석·뷰어 | 확률적 정책 개선, 혼합 전략 유지 | Abyssal 대비 한 수 개선 |
| 금지 | argmax를 정책으로 쓰기 | A_GAE와 A^T 합산 | privileged 값을 비선형으로 변환 |

**RLCD의 "정답(correctness)" 정의 문제**

RLCD는 정답 c가 있어야 보정할 수 있다(예: EVE의 `r = c − p_a`). 포켓몬에서 정답을 정의하는 방법은
두 가지다.

- **(a) "이 후보를 고른 뒤 승리했다"**: 잘 정의된다. 지금의 W/D/L head가 이 방식이다.
- **(b) "이 후보가 최선이다"**: rollout 노이즈, privileged 정보, 후속 정책에 의존하므로 잘 정의되지
  않는다. **[계산]** 유의한 최선이 있는 상태가 14% 정도뿐이었다.

그래서 RLCD는 **(a) 후보별 승률 보정**으로만 쓰는 것을 권한다. JEV의 choice probability는 "이
후보가 선택될 확률"이지 "후보별 승률"이 아니므로, 둘을 섞으면 안 된다.

**GAE와 반사실 값의 충돌 정리**

두 값은 서로 다른 후속 정책과 baseline으로 추정한 advantage라서 합산하면 안 된다. 상황별 처리는
다음과 같다.

| 상황 | 처리 |
|---|---|
| 분기하지 않은 결정 | Â_GAE |
| 분기 + 후속 정책 π_old (vine) | A^vine으로 **대체** |
| 분기 + 후속 정책 Abyssal | PPO에는 Â_GAE, 그와 별도로 teacher 항(α) 또는 Q-Prop |

**공유 vs 분리**

- base는 공유하고 LoRA를 분리하는 것을 권한다. 비용은 학습할 때 critic forward가 한 번 더 드는
  정도다.
- 대안으로 PPG(Phasic Policy Gradient)식의 주기적 보조 단계를 쓸 수도 있다.

---

## G. 구현 파이프라인

```python
for rnd in rounds:
    games = collect(pi_old, opponent=ABYSSAL, n=64, save_snapshots=True)       # GPU
    recs  = learner_decisions(games, drop_single_candidate=True)
    sel   = select_critical(recs, M=4, eps=1)          # κ(h) 상위 M개 + 무작위 1개
    labels_prev = branch_pool.collect_ready()          # 직전 라운드 분기 결과(1라운드 지연)
    branch_pool.submit(sel, follow_up=ABYSSAL, n0=8, nmax=32)   # CPU, 학습과 중첩
    for g in by_game(recs):
        g.adv, g.critic_tgt = gae_targets(g.decisions, g.G, lam=0.9)
    train_critic(recs, labels_prev)                    # RLCD Brier: q^π ← λ-target, q^A ← rollout
    train_actor(recs, teacher=labels_prev, alpha=0.1, kl_stop=0.02, bc=0.1)
    dev_eval(); probe_regret_eval()

def gae_targets(ds, G, lam):
    adv, tgt = [0.0] * len(ds), [None] * len(ds)
    a, v_next, y_next = 0.0, G, onehot(G)
    for t in reversed(range(len(ds))):
        a = (v_next - ds[t].v_old) + lam * a
        adv[t], tgt[t] = a, y_next
        y_next = (1 - lam) * ds[t].pbar_old + lam * y_next
        v_next = ds[t].v_old
    return adv, tgt
```

**학습 순서**

1. critic warm-up: 기존 EX-073/074/075 기록으로 q^π head를 먼저 학습한다.
2. GAE 단독 단계: GAE와 PPO만 켠다.
3. teacher 단계: probe regret이 개선되는 것을 확인한 뒤 teacher 항을 켠다. α=0.05에서 시작해
   0.1까지 올린다.

**비용·안정성 점검**

| 위험 | 원인 | 대응 |
|---|---|---|
| 계산 비용 | 분기 rollout | 선택 M, 적응형 N, CPU 병렬, 학습 단계와 중첩 |
| off-policy 편향 | 후속 정책이 Abyssal, 라벨 1라운드 지연 | teacher 항 분리, 작은 α, 이후 Q-Prop 전환 |
| 분포 이동 | Abyssal끼리 둔 상태로 학습(EX-066) | π 자신의 상태로 라벨링 |
| 비정상성 | critic·teacher가 매 라운드 바뀜 | 라운드 안에서 고정, critic EMA |
| 수치 안정성 | 큰 δ, 이상치 | 라운드 단위 정규화, δ clip, KL 공동 정지 유지 |

---

## H. 최소 실험 설계

### Stage 0: CPU와 기존 데이터만 사용 (GPU 학습 0)

이 결과가 이후 단계의 go/no-go를 정한다.

- **0a. critic 진단:** EX-073/074/075 기록에 이미 `baseline`과 `outcome`이 있으므로 바로 계산할 수
  있다.
  - 지표: 경기 단계별 AUC·Brier·ECE, explained variance `1 − Var(G−V)/Var(G)`, 경기 안에서의 V 궤적
  - 판단: AUC가 0.5 근처라면 GAE는 이득이 없으므로 critic부터 개선한다.
- **0b. teacher 상한 테스트:** "Abyssal + 한 수 rollout" 플레이어를 Abyssal과 dev 64경기 붙인다.
  - 비용: 결정당 약 4초(16 worker), 64경기에 약 2시간이다.
  - 의미: 이 승률이 **teacher 방식으로 도달할 수 있는 이론적 지점**이다. 실제 숨은 정보 버전이므로
    낙관적인 상한이다.
  - 판단: 이 상한이 60% 미만이면, Abyssal을 후속 정책으로 쓰는 teacher만으로는 목표에 도달할 수 없다.
- **0c. π의 regret 분포:** EX-075 경기에서 무작위로 고른 200개 결정을 분기한다(약 3.3 CPU시간).
  π의 regret 분포와 범주별 분포를 본다.
- **0d. probe benchmark 고정:** on-policy 중요 결정 500–1,000개에 N=64 CRN 라벨을 붙이고 범주
  태그를 단다.
  - 지표: π의 기대 regret `Σπ(max Q − Q)`
  - 용도: 이후 모든 실험이 공유하는 저분산 중간 지표

### Stage 1: GPU, 같은 부모 checkpoint와 같은 예산으로 3개 군 비교

| 군 | 내용 |
|---|---|
| A0 | 현행 (MC, λ=1, 공유 LoRA) |
| A1 | GAE λ=0.9 + critic LoRA 분리 + 라운드 단위 정규화 |
| A2 | A1 + Track 2 teacher (M=4, 적응형 N, α=0.1) |

- **지표 순서:** probe regret → dev → 마지막에 기존 프로토콜의 test512 대응 비교
- **검정력 주의:** 승률이 약 20%일 때 256 대 256 대응 비교의 95% 구간 폭은 약 ±5–7%p다.
  [EX-074](../project_context/experiments/EX-074-abyssal-rl-continue.md)의 결과(+8.6%p, 구간
  +3.9–+13.7)를 보면 작은 효과는 test로 잡을 수 없다. 그래서 반복 판단에는 probe regret을 쓴다.

---

## I. ablation 제안

| # | 비교 | 확인할 질문 |
|---|---|---|
| 1 | MC vs GAE λ ∈ {0.95, 0.9, 0.8} | credit 효과와 편향의 교환 |
| 2 | 공유 LoRA vs 분리 LoRA vs stop-grad; WDL 가중치 0 vs 0.5 | 간섭, KL 조기 정지 원인 |
| 3 | 관측만 쓰는 critic vs privileged critic | 숨은 정보로 인한 분산 감소량 |
| 4 | teacher 없음 vs Abyssal teacher vs Q-Prop | 반사실 신호의 효과 |
| 5 | baseline: π 가중 평균 vs uniform 평균 vs max | 편향 (C4 주장 검증) |
| 6 | 결정 선택: 무작위 vs heuristic vs 학습형 (같은 예산) | CPU시간당 regret 감소량 |
| 7 | N ∈ {4, 8, 16, 32} × CRN 켬/끔 | 라벨 분산, 부호 뒤집힘 비율 |
| 8 | 실제 숨은 정보 vs K=4 가설 | 정보 누출, train 팀과 test 팀 격차 |
| 9 | event Φ shaping(λ=0.8) vs 없음 | sack/pivot 범주의 hacking 재현 |
| 10 | teacher 형태: 선형 vs MPO(belief 평균) vs DPO 쌍 | 목표 형태에 따른 차이 |

---

## J. 예상 failure mode

| failure | 증상 | 대응 |
|---|---|---|
| actor가 evaluator 오차를 착취 | q는 오르는데 dev 승률은 그대로 | 선형 손실, KL, MC 기준 유지, 신선한 결과로 보정 점검 |
| 후속 정책 편향 | 특정 범주(Tera 등)가 쏠림 | 범주별 teacher 감사, 후속 정책 혼합 |
| 비관 함정 (Q^π) | setup 행동이 사라짐 | teacher Q^A, λ를 높게 |
| 낙관 함정 (Q^A) | setup은 늘었는데 스윕 성공률은 낮음 | 범주별 성공률 추적 |
| 운에 끌려간 결정 선택 | 선택된 결정이 급소·빗나감 턴에 몰림 | 결정에 의존하는 선택 기준만 사용 |
| 숨은 정보 누출, 팀 암기 | train 팀 승률만 오름 | 선형 손실 유지, 세트 무작위화 |
| critic이 기저율로 붕괴 | AUC 약 0.5, GAE ≈ MC | Stage 0a에서 사전 차단 |
| 분포 밖 상태에서 과신 | δ 급증, KL 스파이크 | δ clip, 앙상블 불일치로 가중 |
| 이중 계산 | advantage 스케일 폭증 | ΔV reward 금지, A_GAE와 A^T 합산 금지 |
| max baseline 편향 | A^T 평균이 크게 음수 | π 가중 평균 사용 |
| 혼합 전략 붕괴 | 엔트로피 급락 (다른 상대에게 착취당함) | 정책을 확률적으로 유지, argmax 정책 금지 |
| 선택 편향 | evaluator가 평범한 상태에서 보정이 틀어짐 | ε 무작위 결정 포함, 가중치 보정 |

---

## K. 기존 아이디어에서 반드시 수정해야 할 부분

1. **턴별 reward를 새로 정의하는 대신 advantage 추정기를 바꾼다.** reward는 terminal로 고정한다.
2. **Q를 정의할 때 네 가지를 명시한다.** 후속 정책, 상대 정책, 정보 조건, 점수 정의다.
3. **`Q − max_{a'≠a} Q`와 `Q − mean_a Q`를 버리고** `Q − Σπ_old·Q`를 쓴다.
4. **rollout 한 번으로 인과를 판정하지 않는다.** CRN, N=8–32, paired 검정을 쓴다.
5. **backward 순서 탐색을 버린다.** 상태별 독립 평가와 결정 선택, 그리고 패배 경기의
   point-of-no-return 탐색으로 바꾼다.
6. **privileged 값을 argmax나 선호쌍 라벨로 쓰지 않는다.** 선형 손실이나 belief 평균만 쓴다.
7. **"RLCD preference" 대신 RLCD를 보정된 evaluator로 쓴다.** 선호쌍이 꼭 필요하다면 높은 신뢰도의
   쌍만 쓴다(예: 가설 평균 기준 p<0.01).
8. **"sack" 같은 의도를 행동 공간에서 뺀다.** 후보는 Showdown 명령이고, 의도는 분석 태그다.
9. **턴이 아니라 결정 시점을 단위로 쓴다.**
10. **ΔV dense reward와 GAE의 이중 계산을 제거한다.**
11. **학습된 Q의 비중을 줄인다.** 분기한 상태에서는 rollout 값을 직접 쓴다(EX-066 교훈).
12. **라벨을 붙일 상태를 Abyssal끼리 둔 경기가 아니라 π 자신의 경기에서 고른다.**

---

## L. 최종 추천안

> **reward는 승패로 둔다. credit은 모든 결정에는 GAE로, 중요한 결정에는 CRN 반사실 비교로 나눠서
> 준다. RLCD는 정책이 아니라 보정된 평가자(critic/teacher)로 쓴다.**

1. **Stage 0 (CPU):** critic 진단, teacher 상한 테스트, probe set을 만든다. 특히 teacher 상한이 60%를
   넘는지가 전체 방향을 결정한다.
2. **GAE + critic 분리:** 비용이 가장 적고 모든 결정에 효과가 있다. 기존 저장 필드만으로 구현할 수
   있다.
3. **on-policy 중요 결정 분기 + advantage-선형 teacher + 후보별 RLCD evaluator:** 반사실 신호를 넣는
   단계다.
4. **belief 입력, aux head, 가설 샘플링, 운 분해:** 라벨 품질을 올리는 단계다.
5. **더 강한 빠른 후속 정책 확보:** 증류한 소형 정책 등으로 여러 단계의 policy iteration, vine,
   Abyssal 외 상대로 확장한다.

---

## 근거 자료

**저장소 기록**

- 분기 rollout·Q 학습: [EX-060](../project_context/experiments/EX-060-single-battle-branch-rollouts.md),
  [EX-061](../project_context/experiments/EX-061-qwen-action-value.md),
  [EX-065](../project_context/experiments/EX-065-joint-q-data.md),
  [EX-066](../project_context/experiments/EX-066-joint-q-training.md),
  [EX-067](../project_context/experiments/EX-067-abyssal-tera-joint-q.md)
- 자기대국·Abyssal RL: [EX-072](../project_context/experiments/EX-072-selfplay-rlcd.md),
  [EX-073](../project_context/experiments/EX-073-abyssal-rl.md),
  [EX-074](../project_context/experiments/EX-074-abyssal-rl-continue.md),
  [EX-075](../project_context/experiments/EX-075-abyssal-rl-next.md)
- 결정 기록: [D-096](../project_context/decisions/D-096-pokemon-training-objective.md),
  [D-098](../project_context/decisions/D-098-qwen-action-value.md),
  [D-104](../project_context/decisions/D-104-joint-q-training.md),
  [D-114](../project_context/decisions/D-114-selfplay-rlcd.md),
  [D-115](../project_context/decisions/D-115-abyssal-first-objective.md)
- RLCD 환경: [rlcd-lite README](../.tools/rlcd-lite/upstream/README.md),
  [EVE README](../.tools/eve-rlcd/upstream/README.md)
- 코드: [selfplay/objectives.py](../integration/pokechamp/selfplay/objectives.py)(PPO·half-Brier·baseline),
  [branch_rollouts/common.py](../integration/pokechamp/branch_rollouts/common.py)(CRN seed 구성)

**외부 참고문헌**

- PPO: Schulman et al. 2017. GAE: Schulman et al. 2016. TRPO(vine 추정): Schulman et al. 2015.
- Q-Prop: Gu et al. 2017. MPO: Abdolmaleki et al. 2018. PPG: Cobbe et al. 2021.
- DAgger: Ross, Gordon & Bagnell 2011. Expert Iteration: Anthony, Tian & Barber 2017.
- Potential-based shaping: Ng, Harada & Russell 1999.
- 비대칭 critic: Baisero & Amato 2022 (Unbiased Asymmetric RL under Partial Observability).
- PIMC strategy fusion: Frank & Basin 1998; Long et al. 2010.
- Rollout 기반 정책 개선: Tesauro & Galperin 1996.
- 지연 보상 재분배: RUDDER (Arjona-Medina et al. 2019).
- 운을 고려한 credit: Counterfactual Credit Assignment (Mesnard et al. 2021).
- Critical state: Huang et al. 2018 (Establishing Appropriate Trust via Critical States).
