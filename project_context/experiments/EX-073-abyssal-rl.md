# EX-073 — Abyssal 우선 정책 학습: 4GPU·24시간

- 상태: Incomplete — 학습·test·독립 감사 완료, 최종 뷰어 검증 시간 초과
- 승인: 2026-10-03 사용자 제공 계획 구현·실행 지시 / [D-116](../decisions/D-116-abyssal-rl.md)
- 작업: [EP-119](../exec-plans/active/EP-119-abyssal-rl.md)
- runtime: [C-057](../CONTRACTS.md#c-057-abyssal-rl)
- experiment_tag: `ex073-abyssal-rl`

## 동결 연구 조건

EX-071 `checkpoint-0001720` 가중치에서 새 optimizer·난수·시계로 시작한다. 입력·후보·모델
구조·BF16 Base/FP32 LoRA 및 head·dropout0은 EX-072와 같다. 초기 WDL head와 baseline/
advantage 계산도 EX-072와 같다. 행동은 temperature1 categorical sampling, 상대는 모든 단계에서
기본 Abyssal이다. PPO +0.5×선택 행동 WDL half-Brier +0.1×BC, W/D/L reward1/0.5/0,
clip0.2·AdamW lr1e-5/betas(0.9,0.999)/weight_decay0.01·gradient clip1을 유지한다.
GAE·entropy·중간 보상·advantage 정규화0. 라운드 최대1536결정·2epoch, 전 GPU 합계
RL16/BC4를 각각 실제 표본 수로 평균한다. BC는 EX-072 동결 EX-071 train3072개 그대로다.
전체 RL batch의 후보 분포 평균 KL(old||current)이0.02 이상이면 해당 step 적용 없이
라운드 종료 후 새 정책으로 수집한다. 과거 라운드 PPO/WDL 재사용0.

## 모집단·동결 슬롯

seed20261003. 현재 reviewed108 registry의 합법 팀 중 원 replay·기존 평가·EX-07292팀
구성을 제외하고 train256/dev32/test128을 선택한다. 동일6종 구성 세트 변형은 동일 그룹이다.
부족하면 분할 기준을 완화하지 않는다. 팀/대진/진영/시뮬레이터/Abyssal/모델 seed와 모든
가능 슬롯을 첫 update 전에 동결한다. 보류 test의 결과는 정책·head 잠금 전에 생성하지 않는다.

학습 최대128×64=8192경기, 매4라운드에 train256 모두 등장한다.64시도·정상48·유효512결정
이상일 때만 update한다. 자동 선택 제외, 실패·중단은 W/D/L로 변환하지 않는다.
정책 dev는 초기·round1·이후4라운드마다·마지막 완료 라운드의64경기, 중복 없이 최대34회.
16팀쌍×learner 팀 배정2×진영2다. 마지막 후보를 사전에 알 수 없으므로 모든 후보의 가능한
슬롯을 동결하되 실제 dev 시도는34회 이하다. 정상 완료 dev 승률 최대, 동점 이전 라운드,
초기 모델도 후보에 포함한다. 불완전 dev 후보 제외.
보정은 선택 정책 새 train64경기/최대2048표현, 행동 정책 동결·WDL head2epoch/lr1e-4/batch16,
나머지 optimizer EX-072 동일. 새 seed dev24에서 동일 행동의 경기내 평균→경기 평균
half-Brier가 엄격히 개선될 때만 채택한다. 불완전/동점은 원 head 유지한다.
정책/head 잠금 후 초기·선택 각256경기,64팀쌍×배정2×진영2, seed 대응 총512경기 test1회.

## 지표·판정

주지표 승률=W/(W+D+L), 무승부 보정점수 보조.64팀쌍 단위 bootstrap10000회(seed20261003),
선택 정책 승률과 초기 대비 대응 승률차의 percentile95% 구간을 계산한다.
목표 달성은 정상 test512경기와 선택 승률≥0.60 및 구간 하한>0.50 모두 충족할 때다.
개선 주장은 대응 차이 구간 하한>0일 때만 허용한다. 이번 Abyssal 전용 결합 구성의 효과로
한정하며 일반 상대·PPO 단독·L1–L5 효과로 해석하지 않는다. test 조기 열람/재선택0.

## 자원·시간·복구

CPU 준비 뒤 첫 GPU 검사부터24시간/최대96GPU시간. GPU0–3의 공용 lock·UUID를 모두 확보하고
하나라도 사용 중이면 대기한다. 기존 작업 종료/자동 축소0. 수집은 GPU당 정책 복제본1개와
동시 배틀2개, GPU 내 단일 입력 추론 직렬. 동기 학습은 rank당 RL4/BC1, FP32 gradient NCCL
SUM, 동일 optimizer step·공동 KL 종료. 요청 전부 종료·snapshot 해시 일치 후 학습한다.
포트8100–8107/8030–8033의 소유 자원만 정리한다.

0–20h GPU 검증·초기 dev·학습,19h30 이후 새 라운드 금지,20h 완료 update 경계 종료.
시간에 잘린 라운드는 보존하되 후보 제외.20–21h 마지막 완료 dev·선택·보정 판단,
21–23h test,23–24h 최종 검증·보고·봉인·뷰어·정리. 조기 완료 시 다음 단계 가능, 절대 마감 연장0.
15분/단계 경계 원자 checkpoint에 optimizer·rank별 RNG·cursor·동결 buffer·원 시계 저장.
학습 중 실제 SIGTERM 및 전체 worker 재시작1회 검증. 장애 시 전 rank 중지 후 마지막 저장된
완료 step에서만 복원.5분 처리량/GPU/승패/update/KL/남은 시간 기록, CPU 감사·뷰어 점진 수행.
경기1200초/500턴, 재질의·재경기·대체0. RD11.1/C-018·RD11.2/C-046 적용, 공유 결함은 원본
보존·독립 재현·회귀 뒤 같은 조건·원 시계·남은 상한 안에서 복구한다. OOM·길이·비유한값을
절단·표본 제거·조건 완화로 통과시키지 않는다. 기존 EX-066 재로딩 오류·자료 별도 보존.

## 필수 검증·완료

CPU: split·test잠금·중복 슬롯 거부·결과 무관 표본·실패 격리·전역 평균·공동 KL·checkpoint 복원.
GPU:4복제본 동일 입력 logp/WDL 최대 절대차≤1e-5, 단일 대4GPU 동일 배치 gradient
atol1e-5/rtol1e-4, update 파라미터 atol1e-6/rtol1e-5. 실패 뒤 허용오차 확대0.
Base 불변·LoRA/head 변경, 처리량/메모리 실측. 실제 첫8경기 감사 및 학습 채택 모든 결정의
old-policy 전분포 재현·입력/선택/전송/정상 결과 연결. 독립 승패/통계 재집계·보정 행동 불변·
모든 정상 경기 원자료/정확한 JSON 표시 대조·이동 후 오프라인 C-047 뷰어 검증.
최종 모델·완전 재개 checkpoint·설정/소스/자료 해시·한국어 보고/뷰어를 제공한다.
보고에 실제 라운드/결정/update/실패 분모/GPU시간/처리량/결정 지연 포함.
최소1개 학습 후보 dev·보정 판단·전체 test·필수 검증·봉인·뷰어·정리 전부 충족해야 실험 완료.
성능 미달과 미완료를 구분한다. 미실행 상한 슬롯은 시간 제한 실험의 예정 상한으로 구분한다.

## 수치 사전검사 결함·복구 기록

첫 GPU 검사에서 동일 배치 경사가 고정 허용오차를 벗어나 전체 worker가 중지됐다.
학습 step·배틀은0이며 모든 rank의 가중치/RNG 복원을 확인했다. 원본 source·CPU receipt·
실패·checkpoint는 `versions/gpu-preflight-v1/`에 보존했다.
독립 단일 GPU·동일 입력/가중치/RNG 반복에서도350개 경사 텐서가 불일치했다.
strict deterministic 및 `CUBLAS_WORKSPACE_CONFIG=:4096:8`의 별도 진단에서는 초기
fingerprint·출력 digest가 유지되고 반복 경사가 bitwise 일치했다. 원 허용오차의 독립4GPU
검사는 진행 중이다. [EP-120](../exec-plans/completed/EP-120-abyssal-preflight-recovery.md)에
복구 도구 범위·검증·원본 연결을 등록했으며 최초 시계와 누적 상한을 유지한다.

독립4GPU 원 검사에서 출력 차이0, 경사 최대7.450580596923828e-9,
update 최대1.30385160446167e-8로 고정 기준을 통과했고 모든 rank의 가중치/RNG가 복원됐다.
[독립 증거](../../.pokechamp-data/experiments/ex073-abyssal-rl/diagnostics/deterministic-recovery-proof.json)는
초기 출력·입력 동일성, 원 실패, 반복 검사,4GPU 검사, source와 자원 receipt를 연결한다.
복구 교정은 PyTorch의 [결정적 연산 설정](https://docs.pytorch.org/docs/2.8/generated/torch.use_deterministic_algorithms.html)을
명시하며 입력·모델·정밀도·손실·배치·허용오차는 유지한다. production 재개는 새 source CPU 검사와
복구 receipt 검증 후에만 수행한다.

새 source의 CPU132검사·Chromium 검증 후 immutable `recovery.json`을 생성하고 원 초기
checkpoint에서 재개했다. production 사전검사도 동일 수치로 통과하여 baseline_dev에
진입했다. 최초 시계1791027108.5028017·마감1791113508.5028017을 유지한다.

초기 dev 및 round1 후보 dev는 각각 정상64경기·8승56패다. Round1은35회 update 후
KL 한도로 종료했다. 이 중간 dev 결과는 독립 test 성능이나 개선의 근거로 사용하지 않는다.

<a id="final-results"></a>

## 종료 결과 — 2026-10-04

실험 전체는 **미완료**다. 학습·보정·독립 test 및 원자료/통계 감사는 완료했으나 원24시간
한도 안에 최종 오프라인 뷰어 전수 검증을 끝내지 못했다. 성능 목표 미달과 절차 미완료를 구분한다.

| 잠긴 test 모델 | 정상 경기 | 승/무/패 | 승률 |
|---|---:|---:|---:|
| 초기 EX-071 출발 모델 | 256/256 | 20/0/236 | 7.8125% |
| 선택 round24 + 보정 head | 256/256 | 32/0/224 | 12.5% |

64팀쌍·10,000회 bootstrap에서 선택 승률95% 구간은9.375–16.015625%, 초기 대비 대응
차이는+4.6875%p(95% 구간 +0.390625–+8.984375%p)다. 사전 정의 통계 기준상 이번 Abyssal
상대 결합 구성의 개선은 확인했으나 승률60%/구간 하한50% 목표는 미달이다. PPO 단독,
중간 보상 또는 L1–L5의 효과를 의미하지 않는다. 최종화 미완료 상태를 함께 표시한다.

57라운드·2,164 update, 채택 학습 결정87,552개(수집110,403개), dev17후보를 수행했다.
보정 dev24경기의 half-Brier가0.0797936104에서0.0775132911로 감소하여 보정 head를 채택했고,
행동 정책 불변을 확인했다. 정상 총5,336경기(train3,648/dev1,088/보정64/보정dev24/test512),
경기 실패·중단0이며 미시도train4,544슬롯은 예약 상한이다. 독립 감사158,876결정 통과.
기록된 production worker GPU시간82.8572, 별도 진단0.5424, 합계83.3996 GPU시간이다.

최종 뷰어 검증은8,600.84초 timeout으로 실패했다. 완료 gate 중
`all_normal_games_viewer_audit`, `finalization`, `sealed`, `viewer`가 남았으며,
부분 내보내기·봉인 파일 존재만으로 전체 검증을 통과한 것으로 해석하지 않는다.
worker 종료는 원 시계 약21시간, 실패 종료 기록 저장은24시간 마감 후32.70초였다.
추가 학습·평가·검증 재실행 및 예산 연장 없이 종료했다. GPU·전용 포트·실행/브라우저 자원은 해제됐다.

- [최종 보고](../../.pokechamp-data/experiments/ex073-abyssal-rl/final/report.md)
- [결과/해시 종료 receipt](../../.pokechamp-data/experiments/ex073-abyssal-rl/completed.json)
- [독립 감사](../../.pokechamp-data/experiments/ex073-abyssal-rl/final/independent-audit.json)
- [뷰어 — 최종 전수 검증 미완료](../../exports/battle_viewers/ex073/index.html)
- [최종 선택 가중치](../../.pokechamp-data/experiments/ex073-abyssal-rl/snapshots/final.pt)
- [optimizer/RNG 포함 재개 checkpoint 포인터](../../.pokechamp-data/experiments/ex073-abyssal-rl/latest.json)
