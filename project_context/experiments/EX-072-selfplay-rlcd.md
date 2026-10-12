# EX-072 — 자기대국과 RLCD 확률 보정: 단일 GPU 24시간

- 상태: Completed — 실험 완료, 성능 개선 미입증
- 승인: 2026-10-02 사용자 제공 계획 / [D-114](../decisions/D-114-selfplay-rlcd.md)
- 작업: [EP-116](../exec-plans/completed/EP-116-selfplay-rlcd.md)
- runtime: [C-056](../CONTRACTS.md#c-056-selfplay)
- experiment_tag: `ex072-selfplay-rlcd`

## 동결 연구 조건

EX-071 `checkpoint-0001720`의 가중치만 출발점으로 사용한다. optimizer·학습 시계·난수는
새 실험이다. 실제 선택 행동과 정상 종료 결과만 학습하며 분기/반사실적 결과 실험은 없다.
학습 수집·dev·보정·test의 모델은 모두 temperature1 categorical sampling을 사용한다.
행동 정책 개선과 실제 선택 행동 이후 승무패 확률을 함께 평가한다. 기존 EX-071 greedy
평가를 이번 기준선으로 재사용하지 않는다. PPO 단독군은 없으며 RLCD 확률 보정 발상의
변형인 결합 방식 전체만 해석한다. PPO 원문: https://arxiv.org/abs/1707.06347.

### 모델·학습

EX-071과 같은 BF16 동결 Base·FP32 LoRA/행동 head, 기존 LoRA 구조, dropout0이다.
같은 backbone forward의 decision/candidate 표현을 이어 `Linear(2d,256)→Tanh→Linear(256,3)`
W/D/L head에 넣는다. 마지막 linear는0으로 초기화하여 처음은 각1/3이며 행동 정책은 불변이다.
입력 의미·후보 순서·정밀도 경계는 C-055를 재사용하되 greedy 선택은 적용하지 않는다.

`L = L_PPO + 0.5 L_WDL + 0.1 L_BC`.
PPO는 clip0.2, `L_WDL=½Σ(p−onehot(result))²`이며 선택한 행동에만 적용한다.
정상 종료 reward W/D/L=1/0.5/0, 모든 결정에 같은 G, gamma1이다.
수집 당시 동결 모델의 `q=P(W)+0.5P(D)`, `b=Σπold qold`, `A=G−b`는 detach한다.
GAE·advantage 정규화·entropy·중간 보상은 없다.
AdamW lr1e-5, betas(0.9,0.999), weight_decay0.01, gradient clip1이다.
각 라운드에서 결과와 무관한 seed hash 순으로 최대1536결정·2epoch, step당 RL16/BC4를
각각 평균하며 최대768정책 update이다. 마지막 불완전 minibatch도 각각 실제 개수로 평균한다.
BC는 EX-071 train만 사용한다. 이전 라운드 PPO/WDL 자료는 재사용하지 않는다.
step 적용 전 해당 RL batch의 전체 후보 분포 평균 KL(old||current)>0.02이면 그 step은
적용하지 않고 라운드를 끝낸다. rollout old 분포·baseline·입력/후보 순서는 고정한다.

### 팀·일정·분모

seed20261002. registry의 정상화·합법성 통과 팀 중 원 replay corpus와 기존 평가 구성 제외,
새92팀을 train64/dev8/test20으로 분리한다. 같은 구성의 세트 변형은 같은 split이다.
팀·상대·진영·대국 seed·과거 snapshot 배정은 첫 update 전에 동결한다.
기존 모방학습과 세트 통계 중복 가능성이 있어 새로운 자기대국/팀 구성 holdout으로 한정한다.

최대4라운드×64경기. 각각 현재 동결 정책32·이전 snapshot 균등16·Abyssal8·Tera8이다.
첫 라운드 과거 snapshot은 초기 정책이며 쌍마다 진영 교환·지정 learner만 학습한다.
64시도 완료·정상48이상·유효512결정 이상일 때만 학습한다. 미달 라운드는 미완료다.
후보1개는 자동 선택으로 학습에서 제외한다. 제출했으나 마비/풀죽음으로 미실행된 선택은 유효다.
경기 한도1200초/500턴, 실패·통신·비정상·중단을 W/D/L로 바꾸지 않는다. 재경기·대체·재질의0.
정확한 입력·후보 순서·선택·전체 log probability·WDL·baseline·모델/RNG identity를 보존한다.

| 단계 | 최대 경기 | 조건 |
|---|---:|---|
| 자기대국 | 256 | 4×64 |
| 정책 dev | 120 | 초기+최대4후보, 각각4팀쌍×양진영×3상대 |
| head 보정 | 64 | train, 초기48/Abyssal8/Tera8 |
| 보정 채택 dev | 24 | 새 seed, 같은 관측/행동에 두 head 비교 |
| 최종 test | 120 | 초기·선택 각60,10팀쌍×양진영×3상대 |
| 합계 | 584 | 실패도 시도 예산에 포함 |

### 선택·보정·평가

평가 상대 초기/Abyssal/Tera는 같은 경기 수, 종합 가중치는0.75/0.125/0.125다.
완료 dev 학습 후보 중 최고 가중 점수·동점 이전 라운드를 선택한다. 초기 정책은 후보가 아니다.
선택 정책의 backbone/LoRA/행동 head를 동결하고 새 train64경기에서 최대2048표현을
seed hash로 고른다. WDL head만2epoch, lr1e-4·나머지 optimizer 동일, batch16이다.
새 dev24의 같은 관측/행동에서 경기내 평균→상대평균→고정 가중 half-Brier가 엄격히
낮을 때만 채택한다. 동점/불완전은 원 head 유지이며 보정 전후 행동 정책 불변을 검증한다.

정책/head 잠금 후 초기·선택 각60 test를 팀·진영·시뮬레이터 seed 대응시킨다.
정책 점수와 W/D/L 비율·상대별 원시 결과를 보고한다.10팀쌍 단위 paired bootstrap10000회
95% 점수차 구간, 예정 평가 완료 및 하한>0일 때만 개선이다. 그 외 추정치/불확실성을 보고한다.
실제 선택 행동의 half-Brier/NLL/고정10bin reliability를 보정 전/후·train 결과 빈도 상수와
비교한다. 오차는 경기내 평균→상대평균→가중, reliability도 경기/상대 가중이다.
test로 재선택/조정하지 않으며 미선택 행동의 반사실적 확률은 검증 대상이 아니다.

### 시간·자원·검증·복구

CPU 준비 후 첫 GPU preflight부터 최초24시간, GPU3→2→0 유휴 순서로 UUID 고정, GPU1 보존.
0–16h preflight/수집/학습/dev,16–18h 보정/채택,18–23h45m test, 마지막15m 저장/보고/정리.
각 단계는 조기 완료 시 다음 단계로 이동할 수 있으나 원래 절대 마감은 늘리지 않는다.
마감에는 새 경기/update 시작을 금지하고 진행 중 작업도 최종24시간 안에 정리한다.
dev 완료 학습 후보0이면 학습 미완료로 종료한다. 자동 예산 연장0.

CPU: ratio/clip/baseline·WDL/Brier·terminal·순서·split·sampling 재현성.
GPU: train최대32개로 메모리/유한 gradient, update0. 첫8학습경기는 라운드64에 포함하여
선택/기록/종료 연결 감사. 학습 전 old log probability 일치·base동결·LoRA/head변경 검증.
15분 및 단계 경계에서 완료 step 기준 원자 checkpoint; optimizer/RNG/cursor/동결정책/
buffer/원래 시간 상한 보존. 계획된 학습 중1회 SIGTERM/재시작 실검증, 중단 경기 재경기0.
5분 상태 저장, 사용자 보고는 단계 전환·오류·완료 중심.

RD11.1/C-018·RD11.2/C-046 적용. 공유 구현 결함은 의존 단계 중지, 원본/소스/실패 보존,
별도 재현·독립 회귀 후 동일 조건·마지막 완료 step·원 시계로 재개 가능하다.
입력/처치 영향 자료와 그 후속은 무효이며 재수집 허용0으로 미시도 슬롯만 남은 예산 안에 진행한다.
무결성/영향범위를 입증하지 못하면 의존 실험을 미완료로 종료한다. OOM/길이/비유한값을
절단·표본 제거·처치/정밀도/하이퍼파라미터 변경으로 통과시키지 않는다.

필수 검증·학습·보정 판단·최종 평가·C-047 이동 오프라인 뷰어·자료/가중치/보고·정리가
모두 끝나야 전체 완료다. 실험 완료와 성능 개선을 분리하고 빠진 단계·분모·원인을 명시한다.

<a id="final-results"></a>

## 실행 결과

CPU 준비·필수 검증·네 라운드 학습·선택·보정 판단·잠긴 test·최종 보고·뷰어·봉인·소유 자원
정리를 모두 완료했다. 실제 실행 증거는 `.pokechamp-data/experiments/ex072-selfplay-rlcd/`에 있다.
최초 시계는 2026-10-02 11:59:54 KST에 시작했으며 정확한 시작/절대 마감은 `clock.json`이 소유한다.
물리 GPU3/UUID `GPU-fd337c1e-b087-b26d-4dc0-a195c2b3a8d6`에서 학습·평가를 마치고 GPU를 반환했다.
예정584경기는 모두 정상 종료했고 실패·무효·미실행은0이다. 원 시계 기준42,309.66초
(11시간45분9.66초), 2026-10-02 23:45:04 KST에 모든 완료 gate를 통과했다. 별도 GPU1/EX-066은 유지했다.

최초 최종화의 `httpx` 누락과 후속 브라우저 검증에서 발견한 큰 정수 표시 손실은
[EP-117](../exec-plans/completed/EP-117-selfplay-finalization-recovery.md)의 별도 CPU 정정본으로 교정했다.
원 실패 보고·봉인·`completed.json`과 실패한 v2 staging은 보존한다. test 결과를 확인한 뒤의
표시/검증 환경 수정이며 원자료·가중치·지표·평가 기준을 바꾸지 않았다. 원 검증기로584경기와
브라우저 대표1,032결정·리플레이 제어를 확인했고, 별도 전수 대조로21,899결정의 모든 JSON
payload 값·타입 보존을 확인했다. 외부 요청·JavaScript 오류는0이다.
현재 완료 판정은 `corrections/latest.json`이 가리키는 `finalization-v3/completed.json`이다.

### 정책·head 선택 결과

초기 sampling 정책의 dev 가중 점수는0.234375였다. 학습 후보 네 개의 dev는 모두24/24경기를
정상 완료했으며 다음 결과로 round-2를 선택했다. 모든 라운드는 다음 미적용 batch의 KL 한도로
종료했다. 전체 적용 정책 update는275개이며 선택 snapshot까지의 누적 update는248개다.

| 후보 | 라운드 적용 update | dev 가중 점수 | 선택 |
|---|---:|---:|---|
| round-1 | 77 | 0.609375 | 아니요 |
| round-2 | 171 | 0.687500 | 예 |
| round-3 | 20 | 0.593750 | 아니요 |
| round-4 | 7 | 0.515625 | 아니요 |

보정용64경기·유효2,529결정에서 선택한2,048표현으로 WDL head만2epoch·256update 학습했다.
행동 정책 불변 검사는 통과했다. 별도 dev24경기·701결정의 가중 half-Brier는
0.2761709359→0.2871806507로 악화되어 보정 head를 채택하지 않았다.
NLL은0.8903500381→0.7922144085였으나 채택 기준은 사전에 정한 half-Brier다.
최종 정책은 round-2와 보정 전 head이며 `evaluation-lock.json`으로 test 전에 잠갔다.

### 잠긴 test 결과

초기와 선택 정책이 각각60/60경기를 정상 완료했다. 원자료에서 별도로 재집계한 상대별 결과,
팀쌍 대응·bootstrap, 확률 오차와 reliability가 원 보고와 일치했다.

| 상대 | 초기 정책 승/무/패 | 선택 정책 승/무/패 |
|---|---:|---:|
| 초기 sampling 정책 | 11/0/9 | 13/0/7 |
| Abyssal | 1/0/19 | 2/0/18 |
| abyssal-tera-v1 | 0/0/20 | 1/0/19 |

고정 가중 종합 점수는 **0.418750→0.506250**, 차이는 **+0.087500**이다.
10팀쌍·10,000회 paired bootstrap의95% 구간은 **[-0.093750, 0.287500]**이다.
하한이0을 넘지 않아 **성능 개선은 입증되지 않았다**. PPO/WDL/BC 결합 방식의 관측 결과이며
RLCD 보조 손실만의 인과 효과나 다른 상대·팀 전체로의 일반화는 주장하지 않는다.

선택 정책 test60경기·실제 선택2,019결정의 확률 평가는 다음과 같다.

| WDL 예측 | 가중 half-Brier | 가중 NLL |
|---|---:|---:|
| 보정 전: 채택 head | 0.272218500 | 0.880822032 |
| 보정 후: 비교 전용 | 0.264177136 | 0.744360570 |
| train 결과 빈도 상수 | 0.251089478 | 0.695329059 |

상수는 정상 train256경기의 `[W,D,L]=[0.47265625,0,0.52734375]`다. 두 head 모두 이 상수보다
test 오차가 컸다. test에서 보정 후 오차가 낮았더라도 dev에서 잠근 head를 바꾸지 않았다.
승·무·패별 고정10bin reliability와 전체 분모는 정정 결과 JSON에도 같은 값으로 보존한다.

### 산출물·검증 근거

- [정정 최종 보고](../../.pokechamp-data/experiments/ex072-selfplay-rlcd/corrections/finalization-v3/report.md) ·
  [전체 결과·reliability](../../.pokechamp-data/experiments/ex072-selfplay-rlcd/corrections/finalization-v3/result.json) ·
  [584경기 오프라인 뷰어](../../exports/battle_viewers/ex072-finalization-v3/index.html)
- [최종 정책·head](../../.pokechamp-data/experiments/ex072-selfplay-rlcd/snapshots/final.pt): round-2/보정 전 head,
  SHA-256 `2edc3711aa91fe926daaafd396bfff1e6ebc25d808555892bd7687a5c0537500`.
  [완전 재시작 checkpoint 위치](../../.pokechamp-data/experiments/ex072-selfplay-rlcd/latest.json),
  [팀·BC·일정 manifest](../../.pokechamp-data/experiments/ex072-selfplay-rlcd/prepared/manifest.json)도 보존한다.
- [CPU152검사](../../.pokechamp-data/experiments/ex072-selfplay-rlcd/verification/cpu.json),
  GPU preflight·첫8감사·실제 SIGTERM 재개·base 동결/head 갱신·정책 불변의 원 receipt는 `verification/`에 있다.
- [독립 통계/원본/전수 JSON 검토](../../.pokechamp-data/experiments/ex072-selfplay-rlcd/verification/finalization-v3/independent-review.json) ·
  [전584경기 이동 후 브라우저 검증](../../.pokechamp-data/experiments/ex072-selfplay-rlcd/corrections/finalization-v3/viewer-check.json) ·
  [게시 링크·checkpoint·시계·자원 종료 확인](../../.pokechamp-data/experiments/ex072-selfplay-rlcd/verification/finalization-v3/publication-check.json).
