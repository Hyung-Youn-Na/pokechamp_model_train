# EX-074 — 57라운드 계승·동일 설정 추가12시간 학습

- 상태: Completed — 실험 완료·57라운드 출발 대비 통계적 개선·성능 목표 미달
- 승인: 2026-10-05 사용자 제공 계획 구현·검증·실행 지시 / [D-117](../decisions/D-117-abyssal-rl-continue.md)
- 작업: [EP-121](../plans/EP-121-abyssal-rl-continue.md)
- runtime: [C-058](../CONTRACTS.md#c-058-abyssal-rl-continue)
- experiment_tag: `ex074-abyssal-rl-continue`

## 질문·계승 출처

EX-073의 마지막 완료57라운드 상태에서 설정을 바꾸지 않고 추가 학습했을 때 Abyssal 상대
성능이 개선되는지 평가한다. 비교는 **추가 전57라운드 모델 대 이번 선택 모델**이다.
EX-073의 최고24라운드 모델보다 우수하다는 주장은 이번 비교로 하지 않는다.
EX-073 동결 source·artifact·실행·실패·시간 초과 미완료 판정은 그대로 보존한다.

출발 checkpoint는 `checkpoint-1791097605668237168.pt`다. 첫 GPU 검사 전 CPU에서
57라운드 가중치와 정확히 일치하고 대응 optimizer504개 상태·4rank별 RNG가 존재함을 확인한다.
EX-073 최종 선택·보정 후 checkpoint는 출발점으로 허용하지 않는다. 부모 경로·SHA-256·
원 실험 identity·57라운드 snapshot 및 이번 설정/시계를 manifest에 연결한다.
가중치·대응 optimizer·rank별 RNG를 복원하되 과거 PPO buffer는 폐기하고 새 경기를 수집한다.
기존 누적 update2,164와 추가 update를 구분한다. 추가 라운드는 local1부터, 전체 이력은58부터다.
새 실행 시계를 사용하며 과거와 이번 자원 사용량을 각각 보고한다.

## 동결 학습 조건

입력·후보·모델 구조·정밀도·행동 샘플링은 EX-073과 같다. BF16 Base/FP32 LoRA 및 head,
dropout0, temperature1 categorical sampling, 모든 단계의 기본 Abyssal 상대를 유지한다.
최종 W/D/L reward1/0.5/0, PPO +0.5×선택 행동 WDL half-Brier +0.1×BC,
clip0.2·AdamW lr1e-5/betas(0.9,0.999)/weight_decay0.01·gradient clip1을 유지한다.
초기 WDL·baseline/advantage 정의도 그대로이며 GAE·entropy·중간 보상·advantage 정규화0이다.
전체 RL batch의 후보 분포 평균 KL(old||current)≥0.02이면 해당 step을 적용하지 않고
라운드를 종료한다. KL 완화·모델 구조 변경·중간 전략 보상은 도입하지 않는다.

추가 최대128라운드×64경기, 라운드 최대1,536결정·2epoch다. 전체 GPU 합계 RL batch16/
BC batch4를 각각 실제 표본 수로 평균한다.64시도·정상48·유효512결정 이상일 때만 update한다.
자동 선택 제외·과거 라운드 PPO/WDL 재사용0·실패/중단을 W/D/L로 변환0을 유지한다.

## 자료·후보 선택

EX-073 train256팀·dev32팀·동결 EX-071 train BC3,072개를 그대로 유지한다.
train 팀 순환은57라운드 다음 위치에서 이어받으며 새 경기 seed를 사용한다.
이번 실행 seed는 `20261005`다. 새 test128팀은 기존 train/dev/test 및 원래 제외 대상과
동일6종 구성(세트 변형 포함)이 겹치지 않아야 한다. 합법 팀이 부족하면 기준 완화 없이
실행 전 중단한다. 팀·대진·진영·시뮬레이터/Abyssal/모델 등 모든 난수 seed와 가능한
평가 슬롯을 첫 update 전에 동결한다. 슬롯 identity는 EX-074에 고유해야 한다.

dev는 출발 모델·추가1라운드·이후 추가4라운드마다·마지막 완료 라운드에 후보당64경기,
중복 없이 최대34회 실시한다.16팀쌍×learner 팀 배정2×진영2다. 완전한 dev 후보 중
승률 최고를 선택하며 동률이면 이전 후보를 우선한다. 출발 모델도 후보에 포함한다.
불완전 dev·시간에 잘린 미완료 라운드는 후보에서 제외한다.

선택 정책은 새 train64경기/최대2,048표현으로 WDL head만2epoch/lr1e-4/batch16 보정한다.
행동 정책 동결·나머지 optimizer 설정은 EX-073과 같다. 별도 dev24경기에서 동일 행동의
경기내 평균→경기 평균 half-Brier가 엄격히 개선될 때만 보정 head를 채택한다.
불완전 또는 동점이면 원 head를 유지한다.

## 잠긴 최종 평가·판정

정책·head 선택을 잠근 뒤 출발 모델과 선택 모델을 각각256경기, 총512경기 대응 평가한다.
64팀쌍×learner 팀 배정2×진영2이며 두 모델에 대응 seed를 적용한다. test는1회만 실시하고
잠금 전 결과 생성·열람·기존 test에 따른 재선택은 하지 않는다.
주지표는 승률 W/(W+D+L)와 출발 대비 승률 차이, 무승부 보정점수는 보조다.
64팀쌍 단위 bootstrap10,000회(seed20261005)의 percentile95% 신뢰구간을 계산한다.
통계적 개선은 대응 승률차 구간 하한>0, 성능 목표는 정상 test512경기와 선택 승률≥60% 및
승률 구간 하한>50%로 각각 판정한다. 실험 완료·통계적 개선·성능 목표 달성은 별도다.
추가 학습과 선택·보정을 포함한 이번 구성의 Abyssal 상대 결과이며 PPO 단독·일반 상대·
L1–L5 효과 또는 EX-073 round24보다 우수함으로 확대하지 않는다.

## 자원·시간·복구

CPU 준비를 끝낸 뒤 **첫 GPU 사전검사부터12시간, 최대48GPU시간**이다.
GPU0–3 공용 lock·UUID 전체 확보, 하나라도 사용 중이면 대기하며 기존 작업 종료·자동 축소0이다.
수집은 GPU당 복제본1·동시 배틀2·GPU 내 단일 입력 추론 직렬이다. 요청 전부 종료와
snapshot hash 동일성을 확인한 뒤 rank당 RL4/BC1·FP32 gradient NCCL SUM·동일 optimizer
step·공동 KL 종료로 학습한다. 소유 포트/프로세스/GPU lock만 정리한다.

| 첫 GPU 검사 이후 | 작업 |
|---|---|
| 0–8시간 | GPU 검증·출발 dev·추가 학습 |
| 7시간30분 이후 | 새 학습 라운드 시작 금지 |
| 8–9시간 | 마지막 완료 dev·정책 선택·보정 판단 |
| 9–11시간 | 잠긴 test512경기 |
| 11–12시간 | 독립 감사·보고·뷰어 내보내기·봉인·정리 |

조기 완료하면 다음 단계로 진행한다.8시간 학습 종료는 완료 update 경계에서 처리하고
잘린 라운드의 자료는 보존하되 후보에서는 제외한다. 완료 기준을 충족하지 못하면 미완료다.
15분/단계 경계의 원자 checkpoint에 optimizer·rank별 RNG·cursor·동결 buffer·이번 최초
시계를 저장한다. 한 rank 장애 시 전체 rank 종료 후 마지막 저장 완료 step에서만 복원한다.
`run --resume`는 EX-074 내부 재개만 허용하며 시계·원 checkpoint identity를 초기화하지 않는다.
실제 SIGTERM 뒤 전체 rank 재개를 이번 실행에서 검증한다.
5분 처리량/GPU/승패/update/KL/남은 시간 운영 로그는 실행기 자체가 기록한다.
경기1200초/500턴, 재시도·재경기·대체·재질의·재수집0이다.
[RD11.1](../../../RESEARCH_DESIGN.md#defect-recovery)/C-018·RD11.2/C-046을 적용한다.
공유 결함은 원본 보존·독립 재현·회귀 후 같은12시간 안에서만 복구하며 허용오차 확대·
표본 임의 제거·절단·자동 예산 연장은 하지 않는다. EX-066/103 등 중단 실행은 재개하지 않는다.

## 단계별 알람

실시간 대화형 모니터링은 하지 않는다. 모델을 호출하지 않는 별도 감지기가 상태 파일과
프로세스를 확인하고 아래 사건에만 이 대화로 알람을 보낸다.

1. 학습 종료 및 마지막 dev·선택 완료.
2. 보정 판단 완료 및 test 진입.
3. 전체 최종화 종료.
4. 비정상 종료 또는 절대 마감 도달.

사건별 전달 여부를 영속 기록하여 재시작에도 중복 발송하지 않는다. 전체 종료와 마감 알람이
겹치면 한 번만 전달한다. 정상 단계는 알람 응답을 기다리지 않고 자동 진행한다.
알람 응답은 해당 receipt1회 확인·간단 보고 후 종료하며 반복 조회·대기 루프를 재개하지 않는다.
종료 알람에서는 문서 갱신과 최종 결과 보고까지 수행한다.

## 필수 검증·뷰어·완료

진입점 `abyssal_rl_continue`는 prepare/verify/run/status/finalize를 제공한다.
CPU 검증은 부모 출처/가중치/optimizer/RNG 복원, split 비중복, test 잠금, 새 슬롯 identity·
중복 거부, 결과 무관 표본, 실패 격리, 전역 평균·공동 KL, EX-074 내부 재개/시간 한도,
단계 전환·중복 알람 방지·실패 시 자원 정리를 포함한다. 기존 필수 CPU 검사도 유지한다.
4GPU 동일 입력 logp/WDL 최대 절대차≤1e-5, 단일 대4GPU 동일 배치 gradient
atol1e-5/rtol1e-4, update 파라미터 atol1e-6/rtol1e-5를 유지한다.
Base 불변·LoRA/head 변경·처리량/메모리·실제 SIGTERM 전체 rank 복원을 확인한다.
첫8경기 감사·채택 모든 학습 결정의 old-policy 전분포 재현·정상 경기 원자료/선택 행동/결과
연결 감사·보정 행동 불변·독립 승패/통계 재집계는 유지한다.

사용자의 명시적 예외로 **브라우저 전수 검증과 자동 점진 전수 브라우저 검사는 생략**한다.
모든 정상 경기 뷰어는 C-047 경로에 내보내되, 이동 후 오프라인 브라우저 확인은 train/dev/
보정/보정dev/test초기/test선택 각 단계에서 슬롯 ID순 첫·마지막 정상 경기, 중복 제거 후
최대12경기로 제한한다. 표본 선택은 결과와 무관하며 생략·표본 검증 범위를 보고서에 명시한다.
원자료 해시·봉인은 유지하고 이 예외를 EX-073의 실패 판정에 소급하지 않는다.

최소1개 추가 학습 후보 dev·보정 판단·정상 test512·필수 수치/독립 감사·최종 모델·완전 재개
checkpoint·설정/소스/자료 해시·한국어 보고·전 경기 뷰어와 표본 검증·봉인·소유 자원 정리를
모두 충족해야 실험 완료다. 실제/전체 라운드·추가/누적 update·결정·실패 분모·GPU시간·처리량·
결정 지연·미실행 상한 슬롯을 보고한다. 종료 보고는 성능·미충족 기준·이전/이번 사용 자원과
보고서·뷰어 링크를 제공한다. 등록만으로 구현·검증·실행 완료를 주장하지 않는다.

## 실행 진입 — 2026-10-05

지정 부모57라운드 가중치·optimizer504상태/누적2164step·4rank RNG를 CPU 검증했다.
train256/dev32·BC3072를 정확히 계승하고 신규 합법 test128·가능17048슬롯을 동결했다.
CPU179검사 및 Chromium 의존성 검사를 통과하여 자동 실행에 진입한다.
4GPU 수치·실제 SIGTERM 재개·학습/선택·보정·test·최종화는 자동 gate 순서로 수행하며,
실험/통계적 개선/목표 달성은 아직 미판정이다. 반복 대화형 감시 없이 단계 알람만 사용한다.

- [CPU receipt](../../../../.pokechamp-data/experiments/ex074-abyssal-rl-continue/verification/cpu.json)
- [부모 출처](../../../../.pokechamp-data/experiments/ex074-abyssal-rl-continue/prepared/parent.json)
- [실행 manifest·시계](../../../../.pokechamp-data/experiments/ex074-abyssal-rl-continue/manifest.json)


### 실행 전 문서 동결 중단

시작 기록 갱신이 protocol hash/복사와 겹쳐 source 동결 gate가 시작을 거부했다.
GPU worker·update·배틀0이며 원 시계는 유지한다. 원본·독립 CPU 재현·같은 시계 재진입 검사는
[EP-121](../plans/EP-121-abyssal-rl-continue.md#실행-전-동결-경계-중단복구)에 연결한다.
이 실패를 수치 사전검사 성공이나 실험 완료로 처리하지 않는다.

재검증183검사·브라우저 의존성 검사 통과 후 원 시계를 유지하여 재진입한다.
절대 마감은 2026-10-06 09:50:50 KST(원 시작2026-10-05 21:50:50 KST)다.
시작 전 문서 동결 실패에 소요된 시간도 상한에서 제외하지 않는다.


<a id="final-results"></a>

## 종료 결과 — 2026-10-06

**실험 완료**, 출발57라운드 대비 **통계적 개선**, 기존 승률 목표 **미달**이다.
완료 기준 미충족은 없다. EX-073의 당시 뷰어 timeout·미완료 판정은 그대로 보존한다.

| 잠긴 test 모델 | 정상 경기 | 승/무/패 | 승률 |
|---|---:|---:|---:|
| 출발 EX-073 round57 | 256/256 | 29/0/227 | 11.328125% |
| 추가 round20(전체77)·보정 전 head | 256/256 | 51/0/205 | 19.921875% |

64팀쌍·10,000회 bootstrap(seed20261005)에서 선택 승률95% 구간은15.625–25.0%,
출발 대비 대응 차이는+8.59375%p(95% 구간+3.90625–+13.671875%p)다.
대응 구간 하한>0으로 사전 개선 기준을 만족하나 승률60%/구간 하한50% 목표는 미달이다.
EX-073 최고round24 대비 우월성·일반 상대·PPO 단독·L1–L5 효과를 의미하지 않는다.

추가25라운드(전체82)·510update, 기존2164를 합쳐누적2674update다.
학습 채택38400결정(수집49295), dev9후보를 평가했다. 선택 추가round20 dev는14승50패다.
보정dev24경기 half-Brier가0.04959982369→0.09712205449로 악화되어 보정 전 head를 유지했다.
정상2776경기(train1600/dev576/보정64/보정dev24/test512), 실패·중단0이다.
미시도train6592슬롯은 예약 상한이며 요구 경기 누락이 아니다.

CPU183검사·4GPU 수치·실제 SIGTERM 전체rank 재개·부모 복원·독립 감사83757결정·통계
재집계·정책 불변·test 잠금·봉인이 통과했다. 모든 정상2776경기를 내보냈다.
브라우저 전수/점진 전수 검사는 승인대로 생략했고 여섯 단계별 첫·마지막12경기(429결정)의
이동 후 오프라인 Chromium 검사를 통과했다. 이를 브라우저 전수 검증으로 표시하지 않는다.

기록된 이번 production worker 예약시간은35.3432GPU시간(별도 진단0)이다.
이전 EX-073은83.3996GPU시간으로 별도 보고한다. 실행기는 worker 종료 직후 경과×4 상한을
35.6546GPU시간으로 기록했으며 이는 GPU kernel 활성시간이 아니다.
최종화 종료는2026-10-06 07:02:52 KST, 원 시계부터약9시간12분으로12시간 안이다.
시작 문서 동결 실패 시간도 원 상한에 포함했다. 실행·감지기 종료, GPU compute process0,
전용 포트 listener0을 확인했다. 추가 실행·예산 연장·대화형 반복 모니터링은 없다.

- [최종 보고](../../../../.pokechamp-data/experiments/ex074-abyssal-rl-continue/final/report.md)
- [종료 receipt](../../../../.pokechamp-data/experiments/ex074-abyssal-rl-continue/completed.json)
- [독립 감사](../../../../.pokechamp-data/experiments/ex074-abyssal-rl-continue/final/independent-audit.json)
- [2776경기 뷰어](../../../../exports/battle_viewers/ex074/index.html)
- [최종 선택 모델](../../../../.pokechamp-data/experiments/ex074-abyssal-rl-continue/snapshots/final.pt)
- [마지막 학습 round25 가중치/optimizer/RNG checkpoint](../../../../.pokechamp-data/experiments/ex074-abyssal-rl-continue/training-parent-ready.json)
- [실행 내부 재개 checkpoint 포인터](../../../../.pokechamp-data/experiments/ex074-abyssal-rl-continue/latest.json)
- [종료 후 자원·결과 확인](../../../exec-plans/evidence/ep121/closure.json)
