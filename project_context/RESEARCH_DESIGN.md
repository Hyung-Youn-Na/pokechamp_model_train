# 현재 연구 설계 (Research Design)

현재 당면 우선순위는 [D-119](decisions/D-119-fixed-matchup-mcts.md)의 **고정 A/B 공개 상태
자기대국·MCTS 정책 개선 검증**이다. 사용자의 첫1라운드 요청 [D-123](decisions/D-123-fixed-matchup-first-round.md)에
따라 [EX-078](experiments/EX-078-fixed-matchup-first-round.md)의 체크포인트 진단을
[EP-127](exec-plans/active/EP-127-fixed-matchup-first-round.md)에서 수행했으나 시간초과로 학습 전 중단했다.
후속 실행에는 [D-124](decisions/D-124-fixed-matchup-no-time-limit.md)의 시간 상한 해제를 적용한다.
현재 [D-125](decisions/D-125-first-round-single-retry.md)/[EP-129](exec-plans/completed/EP-129-first-round-single-retry.md)으로
정상31을 계승하고 실패1만 재수집해 첫라운드 학습·체크포인트 진단을 완료했다.
EX-076 예산 중단·EX-077 사용자 중지와 기존 Qwen 자료/판정·L1-L5 장기 목표를 보존한다.

- 상태 (Status): Current — 포켓몬 전용 학습 우선; 고정 A/B 공개 상태 MCTS 정책 개선 검증; 실행별 평가 현황은 STATUS, L1-L5 전체 효능 비교는 미정
- 편집 기준일 (As of): 2026-10-07 — D-119 고정 대진 공개 상태 우선 목표·EX-076 조건 등록
- Authority domain: research question, hypothesis, treatment definition, comparison methodology,
  evaluation protocol, interpretation rule

이 문서는 현재 이 프로젝트가 무엇을 어떤 비교와 evidence로 검증하려 하는지에 대한 source of
truth다. 현재 값이 `TBD`라는 사실도 authoritative state의 일부다. 과거 run의 configuration과
result는 [`experiments/`](experiments/)에, 설계 변경의 rationale은
[`decisions/`](decisions/)에 둔다.

이 문서는 [`CHARTER.md`](CHARTER.md)의 project goal과 fundamental invariant를 변경하지 않으며,
[`CONTRACTS.md`](CONTRACTS.md)의 runtime semantics를 재정의하지 않는다. 상속된 code나 paper
artifact를 설명할 때는 현재 연구 설계로 채택했다는 의미가 없도록 아래 status를 사용한다.
현재 system composition과 data/control flow는 [`ARCHITECTURE.md`](ARCHITECTURE.md), 실제 수행
단위는 [`exec-plans/INDEX.md`](exec-plans/INDEX.md), 현재 진행 상태는 [`STATUS.md`](STATUS.md)가
각각 담당한다. Implementation에서 관찰한 동작은 이 문서의 methodology를 자동으로 바꾸지 않는다.

일반 절의 미정 항목은 L1-L5 전체 효능 비교 설계와 그 확증 evidence를 가리킨다. 별도로
채택된 pilot·운영 비교·요약 진단의 조건과 평가는 이 문서의 해당 D-XXX 절을 따른다.
당면 학습 목표와 그 미정 설계는 [§1의 포켓몬 전용 학습 절](#pokemon-training-objective)을 따른다.
운영 실험·진단이 등록되지 않았다는 뜻으로 해석하지 않는다. 개별 실행·중단·검증 상태는
[`STATUS.md`](STATUS.md)와 [`experiments/INDEX.md`](experiments/INDEX.md)가 연결하는 record를
확인한다. 설계의 채택 자체는 중단된 실행의 재개 승인이 아니다.

| 표시 | 의미 |
|---|---|
| **Current** | 현재 사용자 지시 또는 project context가 명시적으로 채택한 연구 설계 |
| **Observed** | Source, test 또는 artifact에서 확인한 구현·기록 사실. 그 자체로 연구 의도는 아니다. |
| **Excluded legacy** | 원저자 연구의 evidence이지만 Decision D-002에 따라 현재 설계로 승계하지 않은 항목 |
| **Provisional** | 검토 가능한 후보이나 명시적 승인 전에는 experiment를 구속하지 않는 항목 |
| **Unresolved / TBD** | 현재 evidence만으로 정할 수 없는 항목 |
| **Missing** | 요구되는 evidence 또는 record가 현재 존재하지 않는 상태 |

<a id="current-rules"></a>

## 적용 범위와 읽기 경로

[D-130](decisions/D-130-jev27b-ex058-reproduction.md)에 따라
[EX-082](experiments/EX-082-jev27b-ex058-reproduction.md)의 질문·처치·동결 조건·진입 gate·
자원/시간·분모·실패/복구·비교/해석을 공개 JEV-27B의 EX-058 재현 평가 규범으로 편입한다.
과거 클라우드 모델과 로컬 공개 모델의 고정 대진 탐색 비교이며 다른 실험의 조건은 불변이다.

공통 연구 목적·미정 설계·평가·해석은 §1–15를 따른다. 당면 목표는
[포켓몬 전용 학습](#pokemon-training-objective)이다. 새 기본 IO 테스트는
[§8.1](#io-explanation-review), 도구 결함 복구는 [§11.1](#defect-recovery), 공급자 판단 오류는
[§11.2](#provider-judgment-errors)를 먼저 확인한다.
새 상세 효과 사전의 지식 추가·해석 범위는 [D-057](#d-057-배틀선봉-상세-효과-사전), 선봉의 두 독립 개선은 [D-061](#d-061-선봉-전략규칙-입력-개선)을 따른다.
이 절의 안내는 각 규칙의 기존 적용 시점·예외를 바꾸지 않는다.

§0 및 D별 실험·진단 절은 당시 채택된 범위에 적용되며 새 작업의 실행·검증 목록으로 자동 상속하지 않는다.
`Current` 표시는 설계 채택을 뜻하며 실행 중이라는 뜻은 아니다. 현재 실행 상태는
[실행 계획 색인](exec-plans/INDEX.md), 과거 결과·정정은 [실험 색인](experiments/INDEX.md)에서 찾는다.
새 호출에 적용되는 D별 공통 기본값은 [D-013/014](#0-d-012-기준선-pilot의-현재-설계),
[D-045](#d-045-전체-cloud-기본-동시성8) 및 [C-029](CONTRACTS.md#c-029--새-cloud-기본-동시성8)의 기존 범위를 유지한다.

중복을 줄인 절은 EP-039의 2026-09-14 대조 시점에 정확히 지정한 기존 동결 EX/EP 원문 범위를 이 문서의 규범 내용으로
참조 편입한다. 연구 설계의 domain authority와 원문 소유권은 이전하지 않으며,
참조 문서의 나머지 본문이나 이후 변경을 자동 채택하지 않는다. 참조 원문에 있는 과거 승인·명령은
현재 작업 지시나 중단 실험의 재개 권한이 아니다. 고유 규범은 이 문서에 남긴다.

## 0. D-012 기준선 pilot의 현재 설계

2026-09-06 사용자 승인으로 [D-012](decisions/D-012-adopt-pokechamp-baseline-pilot.md)의
추정 중심 기준선 준비와 [EX-002](experiments/EX-002-pokechamp-baseline-pilot.md)의 40-slot
pilot을 채택했다. 아래 초기 draft의 미정 항목은 L1-L5 효능 비교에 관한 것으로 유지한다.
“승인된 empirical scope/experiment가 없다”는 초기 기술은 이 pilot에는 더 이상 적용하지 않는다.

RQ-B0: 고정 환경에서 기존 minimax/IO/규칙 봇의 유효 완료 성적, 신뢰성, 호출량과 시간은 얼마인가?
방향성 가설 없이 탐색적 추정을 수행한다. Pilot 자체로 RQ1의 개선 여부를 support/reject하지 않는다.
대상·분할·40 slot·분모·재시도·중단 규칙은 EX-002의 사전 protocol을 따른다.
주지표 후보는 IO/minimax의 Abyssal·OneStep 상대 draw-adjusted score의 동일 가중 평균이다.
나머지 대진 승률, 실패율, token/call/decision latency는 진단 지표다. 본 실험 N, CI 및
효능 claim criterion은 pilot 보고 이후 별도 사전등록하며 현재 자동으로 정하지 않는다.

EX-002는 2026-09-07 (Asia/Seoul)에 40 slot/31 유효 완료로 끝났다. 출력 검증 오류 8건과
watchdog 1건을 분리 보존했다. Pinned minimax의 outer search 예외 fallback은 유효 완료
행동의 267/331회였으므로 오류 없는 minimax 성능으로 해석하지 않는다. 완전한 anchor block이
IO 1개/minimax 0개여서 pilot 분산을 추정할 수 없다. 상세 결과·한계·자원 시나리오는 EX-002에
보존하며, 본 실험 N과 효능 비교 설계는 여전히 미정이다.

사용자는 이후 [D-013](decisions/D-013-remove-client-output-cap.md)으로 새 호출의 출력 상한을
모델 공식 최대 128K로 높이고 Cloud 기본 context를 사용하도록 승인했다. EX-002의 512-token
조건 및 결과는 그대로 보존한다. 출력 예산이 달라진 후속 run은 별도 조건/identity로 기록하며
기존 성적·비용 추정과 혼합하지 않는다. 이는 새 pilot/main 실행 또는 효능 claim의 승인이 아니다.

[D-014](decisions/D-014-increase-cloud-request-timeout.md)에 따라 새 요청 timeout은 300초다.
과거 pilot의 120초 설정과 결과는 유지하며 경기 watchdog 1200초는 변경하지 않는다.

[D-015](decisions/D-015-repeat-benchmark-profiles.md)는 사용자 지시에 따라 핵심 4대진의
8판(공통 1 block)·32판(공통 4 blocks) 탐색적 반복 설정을 추가한다. 기존 40판 재현은 보존한다.
새 8판 [EX-003](experiments/EX-003-core-smoke-timing.md)으로 현재 출력/timeout 조건의
시간과 신뢰성을 먼저 재측정한다. 32판 4시간 적합성은 대진별 처리 slot당 시간의 선형 추정과
운영상 여유 50%로 평가하며 통계적 상한이 아니다. 실패·재시도·확증 팀 제외와 해석 제약은
D-015를 따른다. 효능 본 실험이나 정상 minimax 성능을 승인한 것이 아니다.

EX-003은 8 slot/6 유효 완료로 종료됐다. 현재 조건 실측은 44.5분이며 32판 선형 추정에
여유 50%를 더하면 266.9분으로 4시간 예산을 넘었다. 상대 행동 출력 검증 2건과 유효 완료
minimax fallback 74/88회는 운영 한계로 기록한다. 이 결과는 32판 실행, 오류 수정 조건,
L1-L5 효능 또는 작은 승률 차이의 확증으로 확대 해석하지 않는다.

## 0.1 D-016 운영 동시성 측정

[D-016](decisions/D-016-model-concurrency.md)의 corpus/순서/30분 calibration/선택 규칙,
동일 source 8판 순차·병렬 비교와 조건부 32판, 총 4시간 stopping rule을 채택한다.
실측 운용 상한은 해당 계정·모델·요청 조건 범위다. Batch wall time을 시간 분모로 쓰며
전송 실패·출력 실패·미실행 slot·fallback을 분리 보존한다. 모든 단계는 별도 실험 ID다.
소표본 운영 진행 기준이며 효능, 정상 minimax, 서버 내부 병렬 처리의 확증이 아니다.

## 1. 연구 목적 (Research Objective)

### Current state

상위 연구 목적은 **Current**다. AgenticSTS의 L1-L5 계층형 메모리/컨텍스트 구조를
`pokechamp`에 적용하여 성능 개선을 시도한다. 이 방향은 [`CHARTER.md`](CHARTER.md)와
[`D-005`](decisions/D-005-adopt-pokechamp-l1-l5-research-goal.md)가 채택했다.

이 지시는 target system, 이전할 상위 구조와 의도한 outcome 방향을 정하지만, L1-L5의 정확한
`pokechamp` 대응, deliverable, baseline/treatment, performance의 operational definition,
hypothesis, 성공 기준과 evaluation protocol은 아직 정하지 않는다. [`D-002`](decisions/D-002-reset-research-direction.md)는
원래의 bounded-memory hypothesis, roadmap, TODO와 experiment follow-up을 현재 설계로 자동
승계하지 못하게 한다.

채택된 empirical scope에는 기준선 pilot, 운영 비교와 요약 진단이 있다. 각 범위는 이 문서의
해당 D-XXX 절과 연결된 Decision을 따르며, 승인 목록을 이 요약에 중복하여 제한하지 않는다.
등록 evidence 및 중단 상태는 개별 EX record와 STATUS를 따른다. L1-L5 전체 efficacy
comparison은 아직 승인되지 않았으며 다음 두 제약을 유지한다.

1. 새 연구의 efficacy claim은 사용자 승인을 받은 objective, RQ, hypothesis, treatment,
   outcome, protocol이 이 문서에 명시된 뒤에만 평가할 수 있다.
2. 상속된 AgenticSTS implementation과 archive는 L1-L5 구조의 reference이자 선택 가능한 기술적
   baseline/evidence다. 구체적인 code, data, benchmark 또는 과거 result는 현재 baseline이나
   treatment로 자동 채택되지 않는다.

<a id="pokemon-training-objective"></a>

### 당면 목표 — 세 환경을 활용한 포켓몬 전용 모델 학습

[D-096](decisions/D-096-pokemon-training-objective.md)에 따라 **LAYA-RLCD·EVE-RLCD·RLCD-Lite를
활용하여 포켓몬 배틀에 특화된 구조화 행동 선택 모델을 학습하고, 배틀 성능 개선 여부를
평가하는 것**을 현재 우선 목표로 둔다. L1-L5의 장기 목표는 유지한다.
[D-112](decisions/D-112-imitation-self-play-objectives.md)로 Qwen 기반 모델의
[리플레이 모방 학습과 후속 정책 개선](#pokemon-imitation-self-play)을 구체화했으며,
[D-119](decisions/D-119-fixed-matchup-mcts.md)에 따라 당면 우선순위는
[고정 A/B 공개 상태 정책 개선](#fixed-matchup-objective)이다.
여기서 “JEV 계열”은 세 오픈소스의 구조화 결정/RLCD 학습 기반을 뜻하며,
TypeSafe JEV의 원본 가중치나 공식 학습 구현을 확보했다는 뜻이 아니다.

| 활용 환경 | 독립 가상환경 | 준비·검증 원문 |
|---|---|---|
| LAYA-RLCD | `.venv-train` | [EP-096](exec-plans/completed/EP-096-laya-training-environment.md) · [환경 안내](../.tools/laya-rlcd/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md) |
| EVE-RLCD | `.venv-eve-rlcd` | [EP-097](exec-plans/completed/EP-097-eve-rlcd-environment.md) · [환경 안내](../.tools/eve-rlcd/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md) |
| RLCD-Lite | `.venv-rlcd-lite` | [EP-098](exec-plans/completed/EP-098-rlcd-lite-environment.md) · [환경 안내](../.tools/rlcd-lite/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md) |

세 환경의 설치·공개 모델 로딩·최소 추론 검증은 완료했다. 첫 포켓몬 전용 학습은
[D-098/EX-061](#qwen-action-value-first-run)의 고정 개발 실행을 완료했다. 실시간 연결 구현·GPU 대조는 [EX-062](experiments/EX-062-qwen-local-battle.md), 학습 원대진의 실제 배틀 연결 검증은 [EX-063](experiments/EX-063-qwen-training-matchup.md)에서 수행했다. EX-062 중단은 보존하며 독립 배틀 성능은 미평가다.
환경 검증에 사용한 공개 모델을 학습 초기 모델로 자동 확정하지 않는다.

목표 산출물은 포켓몬 관측·합법 행동 후보에 맞춘 학습 입력/출력 정의와 데이터 명세,
환경별 학습 설정·체크포인트·재현 증거, 학습 전후 및 환경별 배틀 평가 보고다.
세 환경을 활용하는 방향을 유지하되, 단기 단계별 활용 환경·초기 모델·비교 조건은 후속 설계에서 정한다.
모든 환경에서 향상이 나온다고 전제하지 않으며, 효과 없음·불확실성·실행 실패도 기록한다.
환경 준비 완료나 학습 손실 감소만으로 배틀 최적화 달성을 주장하지 않는다.

아래 단기 목표에서 정한 방향 외에 다음 구체적 실행 조건은 **TBD**이며,
학습·평가 실행 전에 해당 authority와 bounded plan/실험 기록에서 구체화한다.

- 대상 배틀 format·팀/상대 population, 초기 모델·revision, 관측/이력·합법 후보 및 출력 schema,
  PokéChamp 연결 방식과 fallback 정책.
- 데이터 출처·사용 범위·라벨/교사 생성 방식, train/validation/test 분할 및 중복·정보 누출 방지.
  기존 경기·팀·봉인 평가 자료는 학습 데이터로 자동 편입하지 않으며, 평가용 holdout의
  분리 기준은 학습과 모델 선택 전에 정한다. 의사결정 입력의 관측 가능 정보 경계도 유지한다.
- 학습 알고리즘(SFT/RL 등)·보상·hyperparameter·학습량, GPU 배정·시간/비용 예산·중단 기준.
- 학습 전 기준선·환경 간 통제/차이, 주/보조 지표·분모·불확실성·성공 기준,
  평가 표본·seed·순서·실패/재시도 처리와 재현 identity.

현재 단기 연구 방향은 **고정 A/B 공개 상태에서 작은 전용 모델의 자기대국·MCTS가
탐색 없는 정책을 개선하는지 검증하는 것**이다. D-119가 이번 단계의 D-115 우선순위를 부분 대체한다.
기존 EX-061 개발 학습·EX-065 기반 공동 q 독립 평가의 실행 현황은 STATUS와 해당 EX를 따른다.
기존 JEV 배틀과 입력·관측 연구는 당시 유효성 범위의 참고 근거다. 학습 효과와
입력 변경·초기 모델·메모리 구조의 효과를 구분하며, 함께 바뀌면 전체 구성 차이로 해석한다.
D-096 목표 문서화만으로 실행 protocol을 확정하지 않았으며, 첫 개발 학습은 아래 D-098 절에서 별도로 확정한다.

후속 [D-104/EX-066](experiments/EX-066-joint-q-training.md)은 EX-065 팀 분할과
Qwen3.5-4B-Base의 새 공동 readout을 사용한 전체 타깃 MSE/soft-target Brier 학습을 채택한다.
동결 모델/입력/학습 조건부터 지표·test 잠금·중단/복구 절까지 해당 EX를 이번 실행의 규범으로
참조 편입한다. 독립 오프라인 q 예측 평가이며 배틀 승률·세 환경 비교는 후속으로 유지한다.

2026-10-08 [D-129/EX-081](experiments/EX-081-joint-q-battle.md)은 EX066 선택 epoch3의
원 재현 기준 복구 후 GPU0에서 EX065 test20 대진의 실제 배틀 평가를 별도 승인했다.
처치·재현성·예산·실패/복구·지표/해석은 해당 EX의 동결 원문을 규범으로 참조한다.
EX066 실패·오프라인 test 미완료와 자료를 보존하고 학습 단독 효과를 주장하지 않는다.

[D-105](decisions/D-105-joint-q-gpu2.md)의 사용자 후속 지시에 따라 학습 전에 물리 GPU2로
실행 자원만 변경한다. 이후 GPU2 사용 중 유휴 GPU 대체를 명시한
[D-106](decisions/D-106-joint-q-idle-gpu.md)에 따라 GPU1로 고정했다. 변경 전 protocol·준비본·
사전검사와 최초 시계는 보존하며 나머지 처치·평가는 유지한다.

<a id="pokemon-imitation-self-play"></a>

### 단기 목표 — 고정 대진 공개 상태 정책 개선

<a id="fixed-matchup-objective"></a>

2026-10-07 사용자 지시와 [D-119](decisions/D-119-fixed-matchup-mcts.md)에 따라
[EX-076](experiments/EX-076-fixed-matchup-mcts.md)의 질문·조건·학습/탐색·평가/판정·
예산/gate·복구/완료 절을 이번 고정 대진 실험의 규범으로 편입한다.
작은 무작위 초기 Transformer를 사용하며 Qwen 가중치·이전 자료를 계승하지 않는다.
양측 세트·현재 상태 공개, 실제 상대 선택·미래 RNG 비공개인 진단이다.
탐색 없는 P1−P0 개선을 필수로 평가하며 탐색 자체의 효과는 별도 비교한다.
한 학습 seed·고정 두 팀의 결과를 일반 비공개 Gen9 OU나 L1-L5 효능으로 확대하지 않는다.
EX-076은 예산 gate 중단으로 보존한다. D-122의 후속 지시에 따라
[EX-077](experiments/EX-077-fixed-matchup-day.md)의 유지 조건·변경 예산/gate·복구/보고 절을
규범으로 편입한다. 전체 예상이24시간 이하일 때 단일 GPU로1회 실행한다.

D-123에 따라 현재 실행은 [EX-078](experiments/EX-078-fixed-matchup-first-round.md)의
첫1라운드 체크포인트 진단으로 한정한다. D-124에 따라 EX-078의 현재 시간 규범을
편입하며 경기·단계·전체 벽시계 상한과 시간예측 gate를 적용하지 않는다.
D-125의 EX-078 승인된 복구 절에 따라 정상31 계승·실패1 재수집 후 첫라운드를 이어간다. 목적·범위·예산/gate·완료/복구 절을 규범으로 편입한다.
EX-077은 사용자 중지 상태를 보존하며 전체 평가의 gate 통과나 성능 개선을 주장하지 않는다.

D-126에 따라 현재 추가 학습은 [EX-079](experiments/EX-079-fixed-matchup-stopping.md)의
계승·정기 평가/종료/선택·잠긴 시험·자원/복구/완료를 규범으로 편입한다.
최소12/최대32라운드 및 사전 고정 개발 기준은 수렴의 증명이 아니라 운영 종료 규칙이다.
과거pilot gate 미확정과 EX078의 학습 자료 내 분석을 독립 효능 근거로 간주하지 않는다.

[D-127](decisions/D-127-qwen-matrix-selfplay.md)·[D-128](decisions/D-128-qwen-fixed-shape-serving.md)에 따라 [EX-080](experiments/EX-080-qwen-matrix-selfplay.md)의 질문·조건·모델/입력·행렬 탐색·학습·평가/둔화 종료/선택·잠긴 시험·자원/실패/복구/완료와 D-128 변경 절을 Qwen3.5-0.8B 고정 대진 실험의 규범으로 편입한다. EX-079 실행 중 등록 유예(D-127)를 거쳐 EX-079 종료 후 편입했다. 같은 고정 A/B·공개 상태 진단이지만 탐색(루트 전폭 행렬·MMD 정규화 균형)·모델·P0가 EX-076~079와 달라 결과를 정성 비교만 한다. 둔화 종료·100라운드 상한은 운영 종료 규칙이며 수렴의 증명이 아니다.

### 이전 단기 단계 — Qwen 모방 학습 이후 Abyssal 상대 정책 개선

<a id="abyssal-first-objective"></a>

**D-115 단계의 우선순위(현재 순서는 D-119로 부분 대체):** 2026-10-03 사용자 지시와
[D-115](decisions/D-115-abyssal-first-objective.md)에 따라 **Abyssal 상대를 효율적으로 이기는
정책 학습**을 우선한다. 자기대국 확대는 후순위이며 영구 배제를 뜻하지 않는다.
EX-071 모방 학습과 EX-072 첫 자기대국은 완료했으나 배틀 성능 개선은 입증되지 않았다.
EX-072의 출발 모델은 이미 모방 학습된 모델이므로 미학습 모델 실험으로 해석하지 않는다.

D-115 단계의 설계는 Abyssal 상대 성능을 직접 평가한다. 학습·모델 선택과 분리한
팀/대진 평가에서 승·무·패와 표본 불확실성을 보고하고, 다른 상대의 성능은 별도로 구분한다.
과거 EX-072의 혼합 점수나 test를 새 주지표·모델 선택 자료로 자동 재사용하지 않는다.
[D-116](decisions/D-116-abyssal-rl.md)의 사용자 실행 지시로
[EX-073](experiments/EX-073-abyssal-rl.md)의 동결 조건·모집단·평가·판정·예산·복구·완료 기준을
이번 Abyssal 우선 학습의 규범으로 채택한다. 효율은 실제 GPU시간·시간당 처리량·결정 지연으로
보고한다. EX-072의 결합 손실을 유지하며 이번 상대/규모/분산 구성 전체 효과로 해석한다.

[D-117](decisions/D-117-abyssal-rl-continue.md)의 명시적 추가 실행 지시로
[EX-074](experiments/EX-074-abyssal-rl-continue.md)의 질문·계승 출처·동결 학습 조건·자료/
후보 선택·잠긴 평가/판정·자원/복구·알람·검증/완료 절 전체를 이번 후속 실험의 규범으로 편입한다.
57라운드 학습 상태 계승과 동일 설정 추가 학습의 효과를 새 test로 평가하며, 비교 기준은
57라운드 출발 모델이다. EX-073 최고24라운드 우월성 또는 과거 미완료 해소로 해석하지 않는다.
EX-074만의 브라우저 표본 확인 예외와 새12시간 시계를 명시적으로 채택하며 EX-073의
동결 protocol·실패·시간 초과 미완료 판단은 유지한다. 통계적 개선·성능 목표·절차 완료를 구분한다.

[D-118](decisions/D-118-abyssal-rl-next.md)의 추가12시간1회 요청·82라운드 명시 선택으로
[EX-075](experiments/EX-075-abyssal-rl-next.md)의 질문·계승 출처·명시적 protocol 계승·
자료/선택/평가·실행/완료 절을 이번 실험의 규범으로 편입한다. EX-074 사전 조건을 유지하되
마지막82라운드 출발·새 test·seed20261006·별도12시간1회로 한정한다. 이전 선택77라운드
또는 EX-073 최고24라운드 우월성 비교가 아니며 자동 반복은 승인하지 않는다.
EX-073/074 동결 조건·결과·실패 판정과 test 봉인은 보존한다.

아래 D-112의 두 단계는 채택 당시 방향이며, 추진 순서는 D-115를 거쳐 현재 D-119가 부분 대체한다.
D-113/114는 완료한 각 실행의 규범으로 유지한다.

[D-114](decisions/D-114-selfplay-rlcd.md)의 후속 실행으로
[EX-072](experiments/EX-072-selfplay-rlcd.md)의 동결 연구 조건 전체를 이번 자기대국·보정·평가의
규범으로 편입한다. EX-071과 과거 실행은 유지하며 아래 미정 조건은 EX-072에 한해 구체화한다.
결합 방식 전체의 성능과 실제 선택 행동 확률을 평가하며 RLCD 손실만의 효과는 분리하지 않는다.

[D-113](decisions/D-113-qwen-replay-imitation.md)의 명시적 실행 지시로 첫 단계를 구체화한다.
[EX-071](experiments/EX-071-qwen-replay-imitation.md)의 데이터·분할·통계적 보완·정보 경계,
새 Base/Choice 학습·24시간 상한, validation 선택·잠긴 test와 고정40경기/6시간 평가,
필수 검증·중단/복구·해석을 이번 실행의 규범으로 채택한다. 아래 D-112의 미정 조건은
EX-071에 한해 해당 동결값으로 정해진다. 첫 자기대국은 D-114/EX-072에서 별도로
확정·완료했으며 그 밖의 후속 실행 설계는 미정이다.

[D-112](decisions/D-112-imitation-self-play-objectives.md)에 따라 기존 Qwen 기반 구조화 행동 선택
모델의 학습 방향을 다음 두 단계로 구체화한다. Kev를 포함하되 특정 초기 체크포인트나
출력 schema를 이번 목표 채택으로 확정하지 않는다.

| 단계 | 목표 | 목표 산출물과 평가 |
|---|---|---|
| 1. 리플레이 모방 학습 | 이미 수집한 Smogon/Showdown 리플레이에서 결정 시점의 관측과 실제 선택 행동을 복원하여 행동 선택 정책을 학습한다. | 출처·정보 경계·누락·분할을 기록한 데이터 명세와 학습 체크포인트, 학습 전후 행동 선택 및 독립 배틀 평가 |
| 2. 자기대국을 통한 정책 개선 | 모방 학습 모델을 출발점으로 자기대국의 관측·행동·대국 결과를 수집하고 정책을 반복 갱신한다. | 대국·업데이트·추론 비용의 재현 기록과 체크포인트, 자기대국 전 기준선 대비 별도 배틀 평가 |

**행동 선택의 품질과 실제 배틀 성능을 우선**한다. 리플레이 행동 일치도·학습 손실은
학습 진단이며, 배틀 개선의 대체 지표로 삼지 않는다. 절대 승률의 확률 보정은 별도 평가 문제다.
자기대국 전후 비교는 평가용 상대·팀·seed와 모델 선택 자료의 분리를 사전에 정하며,
개선 여부·불확실성·효과 없음도 같은 기준으로 보고한다.

기존 리플레이의 위치와 규칙 분류 근거는 [EP-100](exec-plans/completed/EP-100-replay-rule-eligibility.md)을
따른다. 규칙상 후보 판정만으로 전문가 품질·관측/합법 행동 복원·학습용 채택이 보장되지는 않는다.
데이터 설계에서는 다음을 구분한다.

- 결정 시점에 플레이어가 알 수 있는 정보만 입력한다. 공개 로그에 없는 자기 팀 정보의
  복원·추정·누락을 구별하고, 이후 공개된 상대 정보나 같은 턴 상대 선택을 입력에 소급하지 않는다.
- 관측 가능한 실제 선택 행동을 모방 타깃으로 삼는다. 식별할 수 없는 선택은 누락/mask로
  처리하는 기준을 정하며, 선택 행동을 승률1·미선택 행동을 승률0으로 바꾸지 않는다.
- 동일 경기의 양측 관점·중복 경기·팀 계열에 대한 분할 기준을 정하고 기존 평가 holdout을
  보존한다. 대국 승패를 모든 후보 행동의 정답 q로 취급하지 않는다.

자료 준비는 기존 리플레이와 CPU 기반 처리를 우선 활용한다. 추가 교사가 필요하면 CPU
규칙·탐색 활용 여부를 후속 설계에서 판단하며, 별도 LLM 합성 라벨 생성은 전제하지 않는다.
자기대국에는 모델 추론과 학습 비용이 발생하므로 경기 수·결정당 추론/탐색량·GPU·시간 예산과
중단 기준을 실행 전에 명시한다. 이번 목표는 추론 비용 없는 자기대국을 뜻하지 않는다.

초기 모델·활용 환경·데이터 채택/복원·출력/손실·자기대국 알고리즘·상대 구성·탐색 사용·
예산·평가 규모/성공 기준은 후속 bounded plan과 EX에서 구체화한다. AlphaZero/MCTS나 특정
강화학습 알고리즘을 자동 채택하지 않는다. 기존 Abyssal 후속 정책 조건부 q의 의미와
EX-066 실행 조건·봉인 자료는 유지하며, 이 절의 목표 문서화 자체로 새 학습·배틀을 시작하지 않는다.

<a id="qwen-action-value-first-run"></a>

### 첫 학습 — EX-060 후보별 조건부 행동가치

[D-098](decisions/D-098-qwen-action-value.md)의 사용자 계획 구현 지시로 첫 실행을 확정한다.
EX-060 전체22관측·167후보를 개발 학습 자료로 사용하고, 후보당32분기의 q=(승+0.5무)/32를
이진 [q,1-q] 타깃으로 둔다. 전체 정보 half-Brier 손실은 관측별 후보 평균 후 관측을 동일 가중한다.
반전만 추출하지 않으며 단일 후보·전체 실패 상태도 유지한다. 입력은 전문 관측과 합법 행동뿐이다.
bandit RLCD와 구분하고 고정 숨은 상태·Abyssal 후속 정책 조건의 교사 값으로 해석한다.
독립 validation/test나 일반 Gen9 OU 배틀 개선 claim은 없다.
모델·처치·예산·지표·성공/중단의 동결 원문은 [EX-061의 동결 실행 조건부터 검증·중단·복구 절](experiments/EX-061-qwen-action-value.md)을 참조 편입한다.
기술 성공과 개발 자료 적합을 분리한다. 후속 독립 배틀 평가는 별도 계획이며 현재 실행하지 않는다.
앞 절의 TBD 중 이 첫 실행에 해당하는 항목만 확정한 것이며 세 환경 비교·일반 성능 설계는 미정이다.
실행 결과와 기술/개발 적합 판정·MAE 증가 한계는 [EX-061 최종 보고](exec-plans/evidence/ep102/report.md)에 보존한다.

<a id="qwen-local-battle"></a>

### Qwen 실시간 연결 — EX-062

[D-099](decisions/D-099-qwen-local-battle.md)로 EX-061 최종 모델의 로컬 서빙·배틀 연결을 승인한다.
[EX-062 동결 protocol](experiments/EX-062-qwen-local-battle.md)을 이번 기술 검증의 조건·분모·
완료/중단 원문으로 채택한다. 개발 자료 재생은 새 일반화 평가가 아니며, Abyssal2경기의 승패는
연결 검증 결과로만 보고한다. EX-061의 교사 q 의미·개발 적합/MAE 한계·후속 독립 평가 경계를 유지한다.

<a id="qwen-training-matchup"></a>

### Qwen 학습 원대진 — EX-063

[D-100](decisions/D-100-qwen-training-matchup.md)의 명시적 후속 지시로 학습에 사용한
EX-058 battle-19 원대진을 새 Qwen p2 대 Abyssal p1 한 경기로 실행한다. 원 팀/진영/seed를
재사용하므로 D-091의 신규 팀 목록 제한에는 이 지정 재현 대진만 예외다. 상세 protocol·분모·
복구/중단·완료 원문은 [EX-063](experiments/EX-063-qwen-training-matchup.md)이다.
학습 대진 개발 진단이며 원 JEV와의 승패 차이를 학습 인과 효과·독립 성능 개선으로 해석하지 않는다.
기존 EX-062의 중단·봉인은 보존한다.

## 2. 연구 질문 (Research Questions)

당면 Qwen 입력 개선의 [D-102](decisions/D-102-qwen-candidate-state.md)는 제공 정보의
결정별 행동 순서·상태 변화 연결을 개발 가설로 둔다. [EX-064](experiments/EX-064-qwen-candidate-state.md)의
저장 관측 3조건과 별도 진단은 조건부 상태 정확성·후보 순위·비용을 분리해 비교한다.
고정 모델의 학습 입력 분포 변화가 포함되며 q의 Abyssal 후속 조건 의미를 유지한다.
정확한 진단 출력은 q가 해당 예측을 사용했다는 증거가 아니며 개발 장면 개선을 독립 승률
개선으로 해석하지 않는다. 새 배틀·재학습·독립 성능 평가는 이 처치 범위 밖이다.

<a id="intermediate-objectives"></a>

### 중간 연구 목표와 최종 목표의 연결

[D-063](decisions/D-063-intermediate-research-objectives.md)에 따라 다음 중간 목표를 채택한다.

> 포켓몬 배틀에서 모델에 제공하는 정보의 종류·표현·이력 범위가 행동 선택과 배틀 성능,
> 비용에 미치는 영향을 평가하고, 이를 바탕으로 L1-L5 메모리 구조에 담을 정보와 관리 방식을 설계한다.

| 단계 | 연구 질문 | 다음 단계에 넘길 산출물 |
|---|---|---|
| 입력 정보 실험 | 현재 상태·게임 규칙·계산 결과 등 어떤 정보와 표현이 도움이 되는가? | 포함·제외·판단 보류할 정보와 근거, 기준 프롬프트 후보 |
| 이력·요약 실험 | 과거 정보 중 무엇을 보존해야 하며, 요약하면 무엇이 손실되는가? | 기억할 내용과 갱신·요약 기준 후보, 손실과 성능·비용의 관계 |
| L1-L5 적용·평가 | 선정한 정보를 계층적으로 관리하면 어떤 차이가 생기는가? | 계층별 대응과 비교 설계, 구조의 효과와 한계에 대한 평가 |

이 단계는 연구 결과와 설계 결정의 연결을 나타내며 새 실행 목록이나 과거 중단 실험의
재개 지시가 아니다. 현재 우선순위는 [포켓몬 전용 학습 목표](#pokemon-training-objective)이며,
입력 정보·이력·요약 연구는 학습 입력과 후속 메모리 설계의 참고 근거로 유지한다.
기존 이력·요약 진단도 당시 조건과 유효성 범위에서 참고하며, 모든 단계가 완료되었다고 전제하지 않는다.

중간 목표의 완료 기준은 사전에 정한 비교 범위를 마치고, 채택·제외·판단 보류할 정보와
그 근거·한계 및 후속 메모리 설계에 반영할 결정을 정리하는 것이다. 성능 향상을 필수 조건으로
두거나 향상이 나올 때까지 실험을 늘리지 않는다. 효과를 확인하지 못한 결과도 불확실성과 함께
기록하며, 근거 부족을 효과 없음으로 단정하지 않는다. 입력·이력 단계의 완료가 L1-L5 전체
효능 검증 완료를 뜻하지 않는다.

### 현재 연구 질문

| ID | Status | Current formulation | 확정에 필요한 것 |
|---|---|---|---|
| **RQ1** | **Current — operationalization TBD** | AgenticSTS의 L1-L5 계층형 메모리/컨텍스트 구조를 `pokechamp`에 적용하면 `pokechamp`의 성능이 개선되는가? | Layer별 대응, 대상 population/version, baseline/treatment, performance metric과 claim criterion 승인 |
| **RQ2** | **Current — operationalization TBD** | 제공하는 정보의 종류와 표현이 행동 선택·배틀 성능·비용에 어떤 영향을 미치는가? | 정보 내용과 표현의 비교 범위, 통제 조건, 행동 변화·성능·비용의 측정 및 완료 기준 |
| **RQ3** | **Current — operationalization TBD** | 제공하는 이력의 범위와 요약 방식이 정보 보존·행동 선택·배틀 성능·비용에 어떤 영향을 미치는가? | 이력 범위·요약 조건, 정보 보존·손실 평가와 비교 protocol |
| **RQ4** | **Current — 당면 목표, operationalization TBD** | 세 RLCD 환경을 활용한 포켓몬 전용 학습이 기준선 대비 행동 선택·배틀 성능에 어떤 변화를 만드는가? | 초기 모델·데이터/분할·학습 처치·통제 조건·평가 지표/분모·예산 및 claim criterion |

RQ4의 단기 비교는 [Qwen 모방 학습·자기대국](#pokemon-imitation-self-play)으로 구체화한다.
모방 학습 전후와 자기대국 전후의 효과를 구분하고, 구체적인 평가 조건은 실행 전에 정한다.

RQ2·RQ3은 RQ1의 메모리 내용·관리 방식 설계를 위한 중간 연구 질문이다. 구체적인 처치·지표·
표본 수·예산·중단 규칙은 새 실험별로 실행 전에 정한다. 행동 선택의 변화 자체를 품질 개선으로
해석하지 않는다. L1-L5 전체 효능 비교에서 무엇을 성능으로 측정할지와 correctness,
reliability, efficiency를 secondary outcome으로 다룰지는 **TBD**다.

상속 repository에는 bounded typed context와 accumulating transcript의 비교, L1-L5 layer의
기여 분해, self-evolution, cross-backbone behavior, cost/latency에 관한 원저자 질문이 나타난다.
근거는 [root README](../README.md),
[`AgenticSTS/docs/reference/ABLATION.md`](../AgenticSTS/docs/reference/ABLATION.md), 과거
competitor report에 있다. 이들은 모두 **Excluded legacy**이며 현재 RQ 번호를 부여하지 않는다.

## 3. 가설 (Hypotheses)

현재 명시적으로 채택된 hypothesis는 없다.

### H1 — TBD

- Status: **Unresolved**
- Claim: **TBD**
- Expected direction: **TBD**
- Comparison: **TBD**
- Supporting evidence rule: **TBD**
- Rejection rule: **TBD**
- Inconclusive rule: **TBD**

상속된 README와 reproduction material의 directional claim 또는 과거 point estimate를 H1으로
승격하지 않는다. `Provisional` hypothesis를 추가할 때도 claim, direction, comparison,
support/reject/inconclusive criterion을 실행 전에 함께 승인해야 한다.

## 4. 실험 단위와 처리 조건 (Experimental Units / Treatments)

### Current treatments

- Experimental unit: Pilot은 경기 slot; 팀/seed와 진영 교환을 shared block으로 묶는다.
- Baseline/control: Pilot은 pinned minimax/IO/Abyssal/OneStep/Random inventory.
- Treatment: L1-L5 효능 treatment는 **TBD**.
- Unit independence 또는 grouping rule: 같은 team/seed를 공유하는 대진은 하나의 block으로 분석한다.

효능 비교의 treatment는 미정이다. Pilot 방법은 minimax, IO, Abyssal, OneStep, Random으로
승인됐다. 다음 표는 재사용 가능성을 평가할 때
참조할 **Observed, Excluded legacy** condition inventory이며 current treatment matrix가 아니다.
정확한 code-level setting은 [`run_ablation.py`](../AgenticSTS/scripts/run_ablation.py)와 관련
[tests](../AgenticSTS/tests/test_run_ablation.py)에서 확인된다.

| Legacy kind | Code에서 관찰된 configuration | 한 condition에 결합된 변화 | Current status |
|---|---|---|---|
| `baseline-strict` | `prompt_variant=baseline`; skills/L4/evolution/postrun/STM/combat conversation/boss HP off; hint filter와 strict knowledge on | Prompt family, context content, state exposure, conversation behavior를 동시에 변경 | Excluded legacy; 단일-factor baseline으로 채택되지 않음 |
| `prompt-only` | Full prompts; skills/L4/evolution/postrun/STM off; combat conversation과 boss HP on | `baseline-strict` 대비 prompt 및 여러 gate가 함께 달라짐 | Excluded legacy |
| `mode-a` | Full prompts와 expert L5 seeds; L4/evolution/postrun/STM off | `prompt-only` 대비 skill retrieval과 authored seed content가 함께 활성화 | Excluded legacy |
| `self-evolve` | Full prompts; L4/L5/evolution/STM/postrun on; expert seeds off; Mode B stubs 및 stub fill on; per-experiment writable store | Memory, skill source, learning, postrun, sequential store growth를 결합 | Excluded legacy; isolation이 필요한 복합 treatment |
| `full` | Code와 tests에서는 full prompts, L4/L5/evolution/STM on, expert seeds 사용, `postrun=False`, shared data root | 여러 layer와 이미 존재하는 store content를 결합 | Excluded legacy; 정의 drift가 있어 현재 treatment로 사용 불가 |

Legacy paper label `mode-b-frozen`과 `full-frozen`은 각각 특정 released artifact에서
code-level `self-evolve`, `full`에 대응한다. 이 mapping은
[`CONTRACTS.md` C-006](CONTRACTS.md)의
legacy reproduction 범위에만 적용하며 새 run 이름을 추측으로 join하지 않는다.

`full`의 postrun setting은 명백히 일치하지 않는다. Reference ABLATION table은 postrun을
`on`으로 설명하지만 `Condition.postrun` default, matrix construction, tests는 `False`와
`--no-postrun`을 확인한다. 이 차이는 **Unresolved treatment-definition conflict**다.

## 5. 독립 변수 (Independent Variables)

L1-L5 전체 효능 비교의 independent variable과 estimand는 **TBD**다. 상속 stack에는 다음 configurable
factor가 관찰되지만, configuration switch라는 이유만으로 연구 변수가 되지는 않는다.

| Observed factor | 구현 surface | 현재 연구 변수 여부 |
|---|---|---|
| Prompt family 및 visibility gate | `STS2_PROMPT_VARIANT`, `STS2_PROMPT_HINT_FILTER`, `STS2_KNOWLEDGE_STRICT`, `STS2_INCLUDE_BOSS_HP` | 미채택 (TBD) |
| Context/memory layer | `STS2_MEMORY_ENABLED`, `STS2_SKILLS_ENABLED`, `STS2_STM_ENABLED`, `STS2_COMBAT_CONVERSATION_ENABLED` | 미채택 (TBD) |
| Skill source와 writable learning | expert seeds, Mode B stubs, postrun/evolution flags, data-root policy | 미채택 (TBD) |
| Model/provider/effort routing | model family, tier별 model/provider/effort | 미채택. Treatment가 아니면 control 또는 stratification 대상일 수 있음 |
| Character, ascension, run progression | `--character`, `--ascension` | 미채택. Population/difficulty definition 후보일 뿐임 |

새 variable은 변경되는 한 요소, 고정되는 요소, 측정하려는 causal contrast를 함께 명시해야
한다. 여러 switch를 묶으면 component별 기여가 아니라 그 bundle의 효과만 해석할 수 있다.

## 6. 통제 변수 (Controlled Variables)

Pilot은 D-012의 model/environment/team/seed/source snapshot을 고정한다. 아래 표는 상속 stack이 제공하는
control/recording capability와 아직 필요한 결정을 구분한다.

| Factor | Observed control 또는 record | Current design status |
|---|---|---|
| Task/population | Legacy harness는 STS2 run을 단위로 받고 character와 ascension을 CLI로 지정 | Target domain은 `pokechamp`; 대상 version, task/population, experimental unit과 difficulty는 TBD |
| Model/provider | `model_profile`에 configured tier model, family, provider, effort와 profile hash를 기록 | 사용할 identity와 fallback 허용 여부 TBD. 실제 per-call route 검증 필요 |
| Sampling parameter | Default `LLM_TEMPERATURE=0`; provider/thinking mode에 따라 temperature가 생략되거나 다른 값이 강제될 수 있음 | Sealing rule TBD |
| Prompt/context family | Ablation env override와 일부 `model_profile` field로 기록 | 어떤 field를 고정할지 TBD |
| Mode B flags | Orchestrator가 env를 명시적으로 override | `model_profile`/`RunRecord`에는 세 Mode B flag가 없어 provenance가 불완전함 |
| Environment version | History append가 `game_version`, `mod_version`, `data_schema_version`을 JSONL에 추가 | 허용 version과 drift policy TBD |
| Data/store state | `data_repo_sha` 기록 가능; `self-evolve`는 writable store를 분리 | Clean/frozen start, snapshot identity, shared-state exception TBD |
| Legal action/runtime contract | Mod state/action API, local parser와 validation boundary는 [`CONTRACTS.md`](CONTRACTS.md)에 정의 | Efficacy control이 아니라 먼저 통과해야 할 technical qualification |
| Run ordering | Legacy orchestrator는 matrix order대로 condition별 run을 연속 실행 | Randomization/blocking/order policy TBD |
| Qualification | State/API tests와 smoke tooling은 존재 | L1-L5 전체 효능 비교용 suite와 threshold는 TBD; 운영 qualification evidence는 해당 EP/EX record 참조 |
| PokéChamp environment qualification | EP-001이 source/tool/server/cloud-adapter contract와 local/cloud smoke를 정의 | Completed — local deterministic smoke, real Cloud probe 및 29/29 valid-action one-battle 통과. Efficacy protocol은 아님 |
| PokéChamp decision observability | D-010/EP-002 bundle이 source SHA, seed, state/protocol, LLM wire call과 sent action을 기록 | Recording/viewer capability는 완료. 운영 run은 개별 EX record에 등록되며 L1-L5 전체 효능 protocol은 아님 |
| Showdown battle timer | Pinned server는 `forcetimer=true`지만 D-011 parent launcher가 process-local `false`로 override한다 | **Current:** 별도 timed-run 지시가 없으면 inactivity timer를 끈다. Timed run은 activation/configuration을 사전 선언·기록하고 untimed run과 같은 condition으로 합치지 않는다. |

## 7. 결과 측정치 (Outcome Measures)

### Current outcomes — L1-L5 전체 효능 비교

- Primary outcome: **TBD**
- Secondary outcomes: **TBD**
- Unit of analysis 및 aggregation: **TBD**
- Uncertainty/statistical procedure: **TBD**

다음은 상속 artifact에서 계산 가능한 **Observed measures**다. 새 연구의 outcome으로 채택된 것은
아니다.

| Available measure | 측정 단위와 관찰된 aggregation | Data source | 제한 |
|---|---|---|---|
| `victory` / `outcome` | Run별 terminal outcome; legacy paper는 `victory`/`defeat`만 denominator로 한 win rate와 Wilson 95% CI 사용 | [`runs/history.jsonl`](../AgenticSTS-Data/runs/history.jsonl), [`reproduce_table_2.py`](../AgenticSTS/scripts/reproduce/reproduce_table_2.py) | 새 연구 denominator와 primary status는 TBD |
| Derived paper score | Run별 `100` if victory, else `floor + (52/3) * bosses`; legacy table은 mean과 percentile-bootstrap 95% CI | [`scripts/reproduce/_lib.py`](../AgenticSTS/scripts/reproduce/_lib.py) | Stored `score`/`fitness`와 동일하다고 가정하면 안 됨 |
| `final_floor` | Run별 도달 floor; legacy report에서 mean 사용 | [`src/runs/history.py`](../AgenticSTS/src/runs/history.py) | Difficulty/termination이 맞지 않으면 비교 불가 |
| `combats_won` / `combats_total` | Run을 합쳐 combat win fraction 계산 가능 | `history.jsonl`, [`ablation_report.py`](../AgenticSTS/scripts/ablation_report.py) | Combat mix와 run length에 민감하며 current metric 아님 |
| `duration_seconds`, `llm_calls`, `total_actions` | Run별 runtime 및 call/action count | `history.jsonl` | 직접적인 latency, token 또는 monetary cost와 같지 않음 |
| Per-call latency/token/cache fields | LLM call별 latency, prompt/completion/cache token | [`session_logger.py`](../AgenticSTS/src/log/session_logger.py), [`PokéChamp observability schema`](../integration/pokechamp/observability/SCHEMA.md) | 두 recording capability가 있으나 현재 연구 bundle과 승인된 aggregation은 없음 |
| Action result status | Action별 `ok`, `soft_fail`, `hard_fail`와 error | `session_logger.py` | Illegal-action/contract-violation rate의 canonical numerator·denominator는 미정 |
| LLM-as-judge quality | Legacy script의 action/reasoning/conciseness rubric | [`eval_decision_quality.py`](../AgenticSTS/scripts/eval_decision_quality.py) | Judge model, rubric validity, sampling protocol이 current design으로 승인되지 않음 |

## 8. 평가 절차 (Evaluation Protocol)

L1-L5 baseline-vs-treatment efficacy comparison procedure는 미정이다. 기준선 pilot의
unit/count/sampling/order/retry/stopping은 D-012와 EX-002에 승인되어 있다.

새 efficacy protocol은 적어도 다음을 실행 전에 명시해야 한다. 이는 현재
[`CHARTER.md`](CHARTER.md), [`CONTRACTS.md` C-006](CONTRACTS.md),
[`experiments/TEMPLATE.md`](experiments/TEMPLATE.md)의 제약을 정리한 것이며 구체적 숫자를 새로
정한 것이 아니다.

1. RQ와 hypothesis, baseline/treatment의 정확한 차이, experimental unit과 population.
2. Primary/secondary outcome, numerator/denominator, aggregation, uncertainty 및 claim threshold.
3. Sample size 또는 stopping rule, order/randomization, incomplete-run 및 retry policy.
4. Model/provider/effort, prompt family, environment version, data snapshot과 mutable-store isolation.
5. Stable `experiment_tag`, condition identity, invalidation criterion, 모든 attempt의 audit trail.
6. Code/harness 변경이 필요하면 별도 active exec plan, 실제 run마다 개별 experiment record와
   durable evidence link.
7. [§11.1](#defect-recovery)의 복구 규칙 적용 여부, 별도 전체 중단 사유·범위,
   재수집 허용 여부·단위·한도, 동일 승인·예산·시계 연결 및 실행기의 지원 여부.

### Observed legacy procedure — not adopted

`run_ablation.py`는 default로 model별 5개 condition, condition당 10 run, `Silent`,
`--ascension auto`, 최대 5000 step을 condition-major order로 실행한다. `agent_abort`와
`mcp_error`를 slot당 최대 3회 retry하고, `interrupt`는 보존하며, `max_steps`는 non-victory
filled slot으로 센다. 반면 paper reproduction의 `filter_cell`은 `max_steps`까지 제외하고
start time 기준 첫 completed run을 고른다. 이 절차와 숫자는 **Excluded legacy**이며 서로 다른
denominator 규칙은 새 protocol을 정하기 전 해소해야 한다.

<a id="io-explanation-review"></a>

### 8.1 기본 IO 테스트의 설명 오류 검토 기본값

[D-050](decisions/D-050-io-explanation-review-opt-in.md)에 따라 2026-09-14 이후 새로 계획하는
**기본 IO 알고리즘 테스트에서는 별도 사용자 지시가 없으면 설명 오류 검토·기입을 수행하지 않는다.**
일반 IO 실행·입출력 동작·성능 확인 및 그 viewer 생성 요청에 설명 평가를 자동 추가하지 않는다.
원본 IO 또는 개선 IO를 시험한다는 이유만으로 과거 실험의 설명 전수 검토를 상속하지 않는다.

- 기본 제외: LLM 설명/reasoning의 사실·진영·시점·계산 주장에 대한 사후 오류 탐색,
  수동/모델 전수 검토, 설명 오류 annotation 추가와 설명 오류율 집계.
- 명시 요청 시 수행: 사용자가 설명 오류 검토·기입 또는 설명 정확성 평가를 요청한 범위를
  해당 plan에 기록한다. 기본값 적용 여부를 매번 확인 질문하지 않는다.
- 계속 수행: 승인된 IO 형식·합법 행동·입력/계산/실제 전달·실행 실패·무결성 검사,
  성능/비용 보고와 원문 응답·provider reasoning 기록/표시. 기술 결함은 기존 규칙대로 처리한다.
- 설명 평가를 하지 않은 새 기본 테스트는 보고서에 `미평가(기본 제외)`로 밝힌다.
  검토 부재만으로 테스트를 미완료 처리하지 않으며 오류0·정상 설명·의미 검증 통과로 주장하지 않는다.

기존 실험의 평가·오류 기록·annotation·미검토·Blocked는 보존한다. 이 기본값은 과거 결과를
소급 재평가하거나 재개하는 지시가 아니다. 별도로 승인된 설명/요약 의미 진단과 그 고정 gate는
해당 명시 범위를 따른다. 아래 실험별 전수 검토 규칙을 새 기본 테스트의 필수 요건으로 자동
복사하지 않는다. 계약 및 실행기 적용 경계는 [C-032](CONTRACTS.md#c-032-io-explanation-review)를 따른다.

## 9. 무작위성과 재현성 (Randomness and Reproducibility)

| Source of variation | Observed state | Reproducibility status |
|---|---|---|
| Game/simulator RNG | Upstream run payload에는 `seed`가 있으나 `RunRecord` schema에는 별도 seed field가 없음 | Run-level exact replay 근거가 불완전함; pin/record policy TBD |
| Model sampling | Default temperature는 0이나 provider와 thinking mode가 parameter를 변경/제거할 수 있고 remote service는 비결정적일 수 있음 | Configured model/effort는 profile에 기록되지만 exact decoding/service identity seal은 없음 |
| Provider routing/fallback | Configured provider/model과 일부 per-call telemetry가 존재 | Fallback이 발생하면 run-level profile만으로 actual route를 완전히 설명하지 못함 |
| Local Python randomness | Skill ranking tie-break와 일부 fallback action이 unseeded `random`을 사용 | Seed 또는 RNG-state record를 확인하지 못함 |
| Run ordering | Legacy orchestrator는 deterministic condition-major loop이고 timestamp를 기록 | Randomized/block order가 아님; time/provider drift와 결합 가능 |
| Sequential learning | Writable `self-evolve` store는 앞선 run의 결과가 뒤 run treatment state를 바꿈 | Run이 independent replicate가 아닐 수 있으며 order를 treatment history로 기록해야 함 |
| Environment/data version | History line에 game/mod/schema version을 append하고 `data_repo_sha`/`machine_id`를 기록할 수 있음 | 값이 비어 있거나 `unknown`일 수 있으며 current acceptance rule은 TBD |
| Analysis resampling | Legacy bootstrap helper는 seed `42`를 사용 | Legacy reproduction에 한정해 pinned됨; current analysis method는 미채택 |

Pilot은 C-010의 sealed plan, 경기별 actual seed와 actor source bundle을 사용한다. Remote
model decoding의 완전한 재현성은 보장하지 않으며 model response identity와 UTC를 기록한다.

## 10. 교란 요인과 타당도 위협 (Confounders and Threats to Validity)

아래 위험은 상속 stack을 새 연구에 재사용할 때 직접 관련되는 항목이다.

| Category | Current risk |
|---|---|
| Treatment coupling | `baseline-strict`와 `self-evolve`는 여러 prompt, memory, conversation, learning flag를 함께 바꾸므로 차이를 한 component에 귀속할 수 없다. |
| Treatment-definition drift | `full`의 postrun 상태가 reference doc과 executable code/tests에서 다르다. |
| Provenance/classification | `RunRecord`에 explicit `experiment_condition_id`와 Mode B flags가 없고 report가 `model_profile`에서 condition을 추론한다. 다른 설정이 같은 label로 합쳐질 수 있다. |
| Store contamination | `self-evolve`에는 isolation path가 있지만 `full`은 shared inherited store를 읽는다. Snapshot/clean-start identity가 없으면 treatment가 달라진다. |
| Sequential dependence | Learning condition에서는 later run이 earlier run과 동일한 treatment state를 공유하지 않는다. Ordinary independent-run CI 해석이 부적절할 수 있다. |
| Denominator drift | Live orchestrator, generic `ablation_report`, paper reproduction이 incomplete/aborted outcome을 동일하게 filter하지 않는다. |
| Model/provider confounding | Tier routing, thinking effort, fallback, postrun model이 condition 또는 시간에 따라 달라질 수 있다. `self-evolve`는 model만 strategic tier에 맞추고 effort는 동기화하지 않는다. |
| Environment drift | Game/mod/data version과 provider service가 batch 사이에 바뀔 수 있다. 기록값이 없는 run은 matched comparison을 약화한다. |
| Unrecorded randomness | Game seed와 local RNG state가 run evidence에 완전하게 보존되지 않는다. |
| Outcome ambiguity | Stored `score`, `fitness`, reproduction derived score가 별개인데 이름만으로 같은 measure로 합칠 위험이 있다. |
| Evidence availability | Run-level archive는 존재하지만 full per-decision trajectory 일부는 이 checkout에 없다고 data README가 명시한다. 세부 correctness/cost audit이 제한될 수 있다. |
| Sample size | Current design에는 N이나 power/precision target이 없다. Legacy N=5/N=10 result를 새 claim의 충분한 evidence로 간주할 수 없다. |

## 11. 무효화 및 즉시 중단 기준 (Invalidation / Hard-stop Criteria)

| Situation | Classification | Required handling |
|---|---|---|
| RQ, hypothesis, treatment contrast, primary outcome, denominator 또는 stopping rule 미정 | Design incomplete | Efficacy experiment와 efficacy claim을 시작하지 않는다. |
| Required experiment record, stable tag/condition identity 또는 provenance 누락 | Missing evidence | 결과를 efficacy evidence로 인정하지 않는다. 원 evidence를 사후 추측으로 채우지 않는다. |
| [`CONTRACTS.md`](CONTRACTS.md)의 state/action/schema/validation boundary 위반 | Technical qualification failure | Attempt를 invalid로 기록하고 research outcome과 분리한다. |
| Model/provider/effort, prompt, environment 또는 data snapshot이 declared condition과 불일치 | Configuration drift | 영향이 사전 규칙으로 허용되지 않았다면 matched comparison에서 제외하고 audit trail을 남긴다. |
| Writable-store leakage 또는 treatment 간 state 공유 | Invalid treatment isolation | 오염된 comparison을 efficacy evidence로 사용하지 않는다. |
| Malformed/missing required raw evidence | Evidence integrity failure | 분석을 중단한다. Runtime loader가 skip한 line도 분모에서 조용히 사라지게 두지 않는다. |
| `agent_abort`, `mcp_error`, `interrupt`, timeout/provider outage | Infrastructure/runtime failure | Research failure나 defeat로 자동 변환하지 않는다. Attempt를 보존하고 predeclared retry/exclusion rule을 적용한다. |
| `max_steps` 또는 그 밖의 non-terminal stop | Censored/incomplete run | 현재 처리 규칙은 Unresolved다. Policy가 정해지기 전에는 efficacy denominator에 포함하지 않는다. |
| Natural `victory`/`defeat` | Potential efficacy unit | Declared population, condition, qualification을 충족할 때만 분석 대상이 된다. |

정확한 qualification suite와 threshold는 **TBD**다. Unit test 또는 smoke success는 기술적
실행 가능성을 보일 수 있지만 hypothesis efficacy를 support하지 않는다.

<a id="defect-recovery"></a>

### 11.1 테스트·평가 도구 결함의 공통 복구 절차

[D-029](decisions/D-029-experiment-defect-recovery.md) 채택(2026-09-09) 후 **새로 승인·등록하는
실험부터** 아래 절차를 기본으로 적용한다. 기존 실험과 이 문서의 D-019~D-028 등 실험별 절에
기록된 전체 중단·재시도·재개 규칙은 당시 실험에 유지한다. 기존 실험의 증거·무효 판정·
`Blocked`를 소급 복구하지 않는다. 새 실험에서 별도 전체 중단 규칙이 필요하면 사유와 범위를
등록한다. §11의 무효화 원칙을 유지하면서 결함의 중지·복구 범위를 아래처럼 판단한다.

1. **발견·보존:** 발견 단계와 증상을 기록하고 당시 source, 입력, 평가 기준, 응답과 보고서를
   보존한다. 모델의 잘못된 답변 자체는 도구 결함과 구별하여 실험별 측정·gate 규칙을 따른다.
   새 실험의 모델 판단 오류는 [§11.2](#provider-judgment-errors)를 따른다.
   도구 결함과 모델 오류가 함께 있으면 둘을 구분해 기록한다.
2. **영향받는 작업 일시 중지:** 의존하는 단계 진입·신규 수집·분석·claim을 필요한 범위에서
   보류한다. 잠재 영향 범위가 불명확하면 공유 의존성을 포함하여 먼저 넓게 중지한다.
   이미 진행 중인 작업의 증거 보존·정리는 해당 실행기와 중단 규칙 안에서 수행한다.
3. **원인·영향 확인:** 원자료에 근거한 재현으로 테스트/평가 구현/기준/실제 수집의 어느
   경계가 잘못됐는지 판별한다. 같은 source·변환·rubric·store를 쓰는 조건 및 후속 결과까지
   추적한다. 영향이 없다는 입증 없이 표본을 유지하지 않는다.
4. **수정·독립 검증:** 중지된 범위의 구현 또는 기준을 별도 버전으로 교정한다. 원자료·별도
   계산·독립 사례로 검증하며 수정 구현의 기대값을 그대로 복제한 검사는 독립 검증이 아니다.
   결함 재현 검사와 관련 회귀 검사가 통과하고 영향 범위·복구 단위를 확정해야 의존 작업을
   재개할 수 있다. 실행 중인 수집의 source·기준을 바꾸지 않는다.
5. **재평가·재실행 및 보고:** 아래 판단표와 등록된 승인·상한·실행기 지원 범위 안에서만
   수행하고, 변경 전후 결과·분모·미완료 및 해석 한계를 함께 기록한다.

| 결함 유형 | 기본 처리 |
|---|---|
| 단위 테스트·fixture·경로만 잘못됨 | 의존하는 단계 진입을 보류하고 수정·재검증한다. 실제 실험의 입력·처치·수집·평가에 영향이 없다는 근거가 있으면 결과를 유지한다. |
| 평가 코드가 사전 기준을 잘못 구현함 | 관련 분석을 보류한다. 사전 기준은 유지하고 구현 수정 후 영향을 받는 모든 조건·응답을 동일하게 재평가한다. 수집이 온전하면 재호출은 필요하지 않다. |
| 정답·rubric 자체가 잘못됨 | 관련 분석을 보류하고 원문 근거로 교정 사유를 기록한다. 결과 확인 후 기준 변경임을 공개하고 기존 평가와 구분된 수정 분석으로 보고한다. 모든 영향 조건·응답에 같은 수정 기준을 적용한다. |
| 실제 입력·처치·수집이 잘못됨 | 영향을 받은 실행과 의존 결과를 무효 처리한다. 수정된 조건에서 비교 구조를 보존하는 필요한 단위를 재수집한다. 기존 응답의 재채점만으로 입력 오류를 해소하지 않는다. |
| 영향 범위가 불명확하거나 증거 무결성이 깨짐 | 공유 의존성을 포함한 잠재 영향 범위를 중지한다. 원자료·source·의존성으로 범위를 입증할 수 없으면 해당 비교 전체를 중단·무효 처리한다. |

정답·rubric 교정인지 입력 설계 오류인지 판단할 때는 사전 목적·원문과 **실제로 전달된 입력에서
요구 사실을 알 수 있는지**를 함께 대조한다. 필요한 입력을 누락한 수집 오류를 rubric 완화로
바꾸어 처리하지 않는다. 두 결함이 함께 있으면 각각 기록하고 입력 오류의 무효화도 적용한다.
검토 중 발견한 모델 오답이나 gate 실패를 테스트 오류로 재분류하여 통과시키지 않는다.

결함 기록은 개별 plan/experiment에 연결하며 다음을 남긴다.

- 발견 단계·시점·결과 확인 여부, 증상과 원자료에 근거한 재현 자료.
- 영향받는 입력·조건·실행·응답·분석, 공유 의존성과 후속 전파, 비영향 판단 근거.
- 수정 전후 source·평가 기준의 버전/해시·차이·교정 사유 및 원문 근거.
- 독립 검증의 방법·결과·근거와 결함 재현 검사·관련 회귀 검사 결과.
- 유지/무효/수정 분석/재수집의 범위·단위, 기존·새 identity 연결, 사용한 승인과 남은 상한.

재실행 단위는 사전 비교 구조를 보존한다. 대응 비교는 필요한 조건 쌍·block을 함께 다루고,
연쇄 메모리 오류는 최초 오염부터 후속 요약·행동·배틀 및 공유 store의 의존 결과까지 포함한다.
검증된 오염 전 경계 또는 clean state에서 다시 시작한다. 재수집할 표본은 결함·의존성으로
정하며 결과가 좋은 표본만 선택해 보존하거나 실패 분모를 삭제하지 않는다. 예정/시도/응답/
실패/무효/미실행/미확정/대응 누락과 복구 시도를 구별하고 반복을 독립 표본으로 늘려 세지 않는다.

기존 원자료·봉인·보고서는 보존한다. 수정 분석과 새 실행은 별도 버전·identity로 원본에
연결하고 전후 source·기준·cohort를 구분한다. 평가 기준 완화로 기존 실험을 통과시킨 것으로
보고하지 않는다. 새 실행도 검증·평가 완료 전에는 유효 결과로 인정하지 않는다.

같은 승인·예산·시간·호출 상한 안의 **허용된 복구**는 재승인을 요구하지 않는다.
상한은 수정·검증·재수집·새 identity로 초기화하지 않으며 최초 시계와 누적 사용량을 연결한다.
새 실험 등록 시 재수집 허용 여부와 한도(금지이면 0), 조건 쌍/연쇄 단위와 정리 여유를 명시한다.
상한 소진·재수집 미승인·필수 정보 부재이면 그 행동을 보류하고 가능한 보존·검증·미완료 보고를
수행한다. 추가 범위는 [INDEX](INDEX.md)의 승인 절차를 따른다. Provider 재시도 정책은 확대하지 않는다.

[C-018](CONTRACTS.md#c-018-recovery)과 [운영 매뉴얼](../integration/pokechamp/README.md#defect-recovery)의
실행기 지원 한계도 적용한다. 이 절차는 halt 삭제·기존 실행 덮어쓰기·시계 초기화의 허가가 아니며
현재 실행기가 지원하지 않는 복구를 명령이나 파일 편집으로 우회하지 않는다.

<a id="provider-judgment-errors"></a>

### 11.2 공급자 판단 오류는 전체 실험 중단 사유가 아니다

[D-074](decisions/D-074-provider-judgment-policy.md)의 사용자 지시에 따라 새 실험은 공급자·모델의
판단 오류를 측정 대상으로 기록하며 전체 중단 gate로 사용하지 않는다. 이 절은 §11.1의 도구
결함과 구분한다. 과거 동결 실험의 당시 규칙·판정·Blocked는 보존한다.

| 유형 | 처리 |
|---|---|
| 전략적으로 나쁜 합법 선택, 설명의 오답·모순·지시 미준수 | 원문과 진단을 남기고 해당 선택으로 경기를 계속한다. 실패·패배도 평가에 포함한다. |
| 확률 합계/반올림, 선택과 최댓값 불일치, 보조 확률·confidence의 누락·범위·키 이상 | 실행할 선택이 명확하고 합법이면 진단으로만 기록한다. 재정규화·최댓값 강제 선택·재질의로 모델 판단을 바꾸지 않는다. |
| 선택 누락·파싱 불가·후보 밖 선택 등 실행 불가능한 응답 | 사전 등록된 출력 복구/fallback이 있으면 그 범위만 적용한다. 없거나 소진되면 해당 경기만 실패로 종료하고 남은 독립 경기를 계속한다. |
| 실제 입력·관측·후보 생성 오류, 전송/수집 결함, 증거 무결성 훼손 | 판단 오류로 완화하지 않고 §11.1 및 기술 계약에 따라 영향 범위를 중지·복구한다. |

판단 오류 빈도나 설명 품질만으로 후속 독립 경기를 막거나 전체 실험을 Blocked로 만들지 않는다.
경기 실패·미완료·대응 누락을 보존하고 예정/시도/완료/실패 분모를 함께 보고한다. 미완료를
승패로 임의 변환하거나 실패를 빼고 성공 표본만 비교하지 않는다. 모든 경기 시도가 끝나도
사전 유효완료·대응쌍 기준 미달이면 비교 미완료로 보고한다.

인증·연결·timeout·429 등 통신 오류는 판단 오류가 아니며 기존 transport/예산/중단 계약을
따른다. 재시도·보충 경기·비용·시간 상한을 이 규칙으로 늘리지 않는다. 입력/관측·요청ID·
실행 후보의 합법성 검증은 유지한다. 전체 중단은 기술적 공유 영향·무결성·승인 상한 등
구체적인 별도 근거와 범위를 기록하며, 새 protocol에 포괄적인 “첫 오류 전체 중단”을 복사하지 않는다.

새 실행 등록 시 이 분류·경기 격리·실행기 지원을 확인한다. 구현 경계와 버전은
[C-046](CONTRACTS.md#c-046-provider-judgment)을 따른다. 문서 개정이 기존 실행기의 동작을
자동 변경하거나 중단 실험을 재개하는 것은 아니다.

## 12. 해석 규칙 (Interpretation Rules)

1. 현재 H1이 비어 있으므로 어떤 기존 또는 신규 result도 현재 hypothesis를 support/reject한
   것으로 분류할 수 없다.
2. Hypothesis support는 사전에 선언한 contrast, expected direction, metric, denominator,
   uncertainty rule을 충족하고 필요한 evidence가 온전할 때만 주장한다.
3. Qualification success는 interface와 evidence pipeline이 의도대로 작동한다는 뜻이며 efficacy
   success가 아니다. Infrastructure failure도 treatment의 연구적 실패가 아니다.
4. 여러 factor가 함께 달라진 comparison은 bundle 차이만 설명한다. 특정 layer, memory contract
   또는 learning algorithm의 독립 기여로 귀속하지 않는다.
5. 다른 model/provider, game version, routing, cadence 또는 interface의 operational comparison은
   caveat를 유지하며 controlled single-variable ablation으로 relabel하지 않는다.
6. 같은 point estimate는 equivalence를 증명하지 않는다. 작은 sample, 겹치는 interval 또는
   nonsignificant result를 효과 없음의 증거로 해석하지 않는다. 현재 equivalence margin,
   significance level, minimum effect는 모두 TBD다.
7. Legacy archive는 새 RQ와 eligibility rule이 명시적으로 연결될 때만 secondary evidence로
   사용할 수 있다. 원저자의 claim을 새 연구 결론으로 그대로 가져오지 않는다.
8. Missing 또는 invalid attempt를 조용히 삭제하지 않는다. 모든 exclusion과 retry는 record와
   denominator 설명에 남긴다.
9. 정보 추가·표현 변경의 효과와 계층형 메모리 구조의 효과를 구분한다. 예를 들어 게임 규칙
   사전 추가의 결과만으로 L1-L5 구조의 기여를 주장하지 않는다. 구조 자체를 비교할 때는
   가능한 한 동일 정보에 접근하는 비계층 기준선을 두고, 정보 접근·예산 등 일치시키지 못한
   차이를 명시한다. 정보와 구조를 함께 바꾼 비교는 그 결합 효과로 해석한다.
10. D-063 이전 실험은 당시 목적·조건·유효성·분모 안에서 중간 목표의 참고 근거로 연결한다.
    새 RQ의 사전 검증 결과로 소급 변경하지 않으며, 기존 무효·미완료·Blocked 판정을 유지한다.

<a id="kev-battle-connection"></a>

### D-108 Kev r1 연결 검증

[EX-068](experiments/EX-068-kev-battle.md)의 validation 재현과 Kev-p2 대 Abyssal-p1 한 경기는
기술적 연결 검사다. 기존 WEAK 오프라인 신호나 이 한 경기의 승패로 배틀 효과를 주장하지 않는다.
원 serializer·자기 팀·bf16/T1을 고정하고 Tera 허용과 사용 이후 학습 분포 밖 상태를 기록한다.
효과 비교는 독립 protocol·같은 상대 팀/seed의 짝지은 기준선·사전 경기 수가 있는 별도 범위다.

[D-109](decisions/D-109-kev-fused-validation.md)는 원 예측 불일치 후 사용자가 승인한 별도
merged·fused 경로의 추가 수락 검사다. 원 입력·dev 비교 기준은 유지하며 원 실패를 보존한다.
이 설정 묶음의 차이를 개별 커널이나 merge의 독립 인과 효과로 해석하지 않는다. 원 시계와
누적 사용량, 승인된 추가3요청 및 전체1경기 경계는 EX-068의 추가 실행 절에서 관리한다.

[D-110](decisions/D-110-kev-test-battles.md) / [EX-069](experiments/EX-069-kev-test-battles.md)는
기존 EX-065 test20 대진의 고정 Kev 정책 본 평가다. 추가 사전검사는 사용자 지시로 생략하고
test 팀/seed 메타데이터를 사용하며, 잠긴 suite의 저장 test 입력/타깃을 읽지 않는다.
표본/지표/원 Abyssal 참고 비교·불확실성·실행 방식 차이의 해석은 EX-069에 사전 고정한다.
EX-068의 연결 검사 및 과거 실패·판정을 소급 변경하지 않는다.

[D-111](decisions/D-111-kev-continuation-question.md) / [EX-070](experiments/EX-070-kev-continuation-question.md)는
후보 질문만 Kev 후속 정책 문구로 바꾼 동일 첫 대진1경기 진단이다. 정확한 질문·통제·상한·분모·
비교를 EX-070에 동결한다. 재학습 없이 현재 Abyssal 후속 정책 학습 타깃은 유지하므로 새 문구가
Kev 후속 승률의 정확한 추정을 보장하지 않는다. 이미 결과를 확인한 단일 대진이며 승률 개선이나
전패 원인을 확정하지 않는다. 후보 p/선택 직접 비교는 동일 JointInput 바이트의 결정에 한정한다.

## 13. 증거 연결 (Evidence Mapping)

| Research item | Required evidence | Current source | Status |
|---|---|---|---|
| 당면 학습 목표 / RQ4 | 명시적 사용자 지시, 학습·평가 설계 및 재현 증거 | [당면 학습 목표](#pokemon-training-objective), [D-096](decisions/D-096-pokemon-training-objective.md), EP-096–098 | **목표 승인·환경 준비 완료; 학습/평가 protocol TBD, 포켓몬 효능 미평가** |
| Research objective / RQ1 | 명시적 사용자 승인과 Charter-compatible formulation | [`CHARTER.md`](CHARTER.md), [`D-005`](decisions/D-005-adopt-pokechamp-l1-l5-research-goal.md), [`STATUS.md`](STATUS.md) | **Objective와 broad RQ 승인; operationalization Unresolved** |
| 중간 연구 목표 / RQ2·RQ3 | 명시적 사용자 승인, 단계별 산출물·완료 기준 및 최종 목표와의 연결 | [이 문서 §2](#intermediate-objectives), [D-063](decisions/D-063-intermediate-research-objectives.md) | **목표와 broad RQ 승인; 새 실험별 operationalization TBD, 목표 달성은 미평가** |
| H1 | Claim, direction, contrast, support/reject/inconclusive rule | 이 문서 §3 | **Missing / Unresolved** |
| L1-L5 전체 효능 baseline/treatments | Exact configuration manifest와 isolation rule | 이 문서 §4; legacy `run_ablation.py`는 참고 가능 | **Missing** — 별도 운영 조건의 부재를 뜻하지 않음 |
| Runtime contract qualification | API/state/action/parser evidence와 declared qualification result | [`CONTRACTS.md`](CONTRACTS.md), [`test_upstream_api_contract.py`](../AgenticSTS/tests/test_upstream_api_contract.py), [`test_upstream_state_parser.py`](../AgenticSTS/tests/test_upstream_state_parser.py) | 운영 검증 상태는 해당 EP/EX record 참조; L1-L5 이전본의 qualification은 미정 |
| Legacy condition behavior | Executable matrix와 regression tests | [`run_ablation.py`](../AgenticSTS/scripts/run_ablation.py), [`test_run_ablation_conditions.py`](../AgenticSTS/tests/test_run_ablation_conditions.py) | **Observed legacy**, definition conflict 있음 |
| Legacy run outcome | Run identity, outcome, floor, config/profile fields | [`AgenticSTS-Data/runs/history.jsonl`](../AgenticSTS-Data/runs/history.jsonl) | Available inherited evidence; current study에는 미등록 |
| Legacy paper aggregation | Cell tags, completed filter, score/CI code | [`scripts/reproduce/`](../AgenticSTS/scripts/reproduce/) | Available inherited method; current protocol로 미채택 |
| 운영 experiment configuration/result | 개별 `EX-XXX` record와 linked raw evidence | [`experiments/INDEX.md`](experiments/INDEX.md), [`STATUS.md`](STATUS.md) | **등록됨** — 유효성·중단·미완료는 개별 record를 따르며 L1-L5 전체 효능 evidence로 승격하지 않음 |
| PokéChamp technical environment | Pinned source/toolchain, loopback server, secret-safe cloud route와 smoke artifact | [`EP-001`](exec-plans/completed/EP-001-pokechamp-reproducible-environment.md), [`C-008`](CONTRACTS.md), local `.artifacts/pokechamp/` | **Complete — local 및 real Cloud qualification 통과; efficacy evidence 아님** |
| Randomness/reproducibility seal | Game seed, decoding/service identity, order, code/data/environment snapshot | PokéChamp schema 및 개별 EX record의 manifest·receipt·source seal | 운영 seal과 한계는 개별 record 참조; L1-L5 전체 효능용 evidence는 미등록 |
| Per-call correctness/efficiency | Full state/decision/action/LLM telemetry와 aggregation definition | [`C-009`](CONTRACTS.md), [`PokéChamp observability schema`](../integration/pokechamp/observability/SCHEMA.md), 개별 EX record | 운영 호출·비용·오류 evidence는 등록됨; L1-L5 전체 효능용 집계와 근거는 미정 |

## 14. 미해결 연구 질문 (Open Research Questions)

이 목록은 implementation TODO가 아니다. Research design을 승인하기 전에 사람이 내려야 할
결정과 필요한 evidence를 나타낸다.

| ID | Question | Why it matters | Resolution evidence/decision |
|---|---|---|---|
| OQ-001 | `pokechamp`의 performance를 어떤 primary outcome과 성공 기준으로 operationalize하며 intended contribution을 어디까지 주장할 것인가? | Broad RQ를 검증 가능한 hypothesis와 claim으로 바꾸는 선행 조건이다. | Metric, denominator, uncertainty 및 claim criterion 승인 |
| OQ-002 | `pokechamp`의 어떤 component에 L1-L5를 어떻게 대응시키고 AgenticSTS의 code/data/contract 중 무엇을 이전 또는 재구현할 것인가? | Treatment identity, implementation scope와 external validity가 달라진다. | Target architecture 및 reuse-boundary decision |
| OQ-003 | 어떤 baseline과 treatment contrast가 핵심 estimand를 식별하는가? | Coupled legacy cells를 그대로 쓰면 component 기여를 분리할 수 없다. | Exact treatment manifest와 rationale |
| OQ-004 | Primary outcome, secondary outcome, success/rejection 기준은 무엇인가? | 결과 선택과 사후 해석 편향을 막는다. | Metric definition, denominator, uncertainty/claim rule 승인 |
| OQ-005 | Unit 수, stopping rule, ordering/randomization, incomplete-run과 retry policy는 무엇인가? | Selection bias, time drift, precision을 결정한다. | Pre-run protocol 및 experiment record |
| OQ-006 | Model/provider/effort와 fallback을 고정할지 연구 변수로 둘지 어떻게 정할 것인가? | Model effect와 treatment effect가 섞이는 것을 막는다. | Routing manifest와 provider-identity policy |
| OQ-007 | Game seed, local RNG, environment/data snapshot을 어느 수준까지 pin 또는 record할 것인가? | Exact replay와 stochastic comparison의 수준을 결정한다. | Reproducibility manifest와 qualification evidence |
| OQ-008 | 298-game legacy corpus와 과거 experiment를 새 RQ의 evidence로 사용할 수 있는가? | 재사용은 비용을 줄이지만 다른 목표·protocol의 selection bias를 가져올 수 있다. | Eligibility/exclusion rule과 provenance review |
| OQ-009 | `full` postrun drift와 outcome denominator 차이를 어떤 canonical definition으로 해소할 것인가? | Treatment identity와 sample inclusion이 불명확하면 비교가 재현되지 않는다. | 별도 accepted decision과 current-state/code 정합화 evidence |

## 15. 현재 연구 단계 (Current Research Stage)

**포켓몬 전용 학습 우선 / 고정 A/B 공개 상태 MCTS 정책 개선 검증.**
[D-096](decisions/D-096-pokemon-training-objective.md)의 [당면 학습 목표](#pokemon-training-objective)와
RQ4를 우선하며, [D-119의 고정 대진 목표](#fixed-matchup-objective)를 당면 방향으로 둔다.
기존 첫 실행 [D-098/EX-061](#qwen-action-value-first-run)과 후속 공동 q 학습·배틀의 실제 상태는
STATUS와 각 EX를 따른다. [D-113/EX-071](experiments/EX-071-qwen-replay-imitation.md)의
첫 모방 학습·평가·보고와 [D-114/EX-072](experiments/EX-072-selfplay-rlcd.md)의
첫 자기대국·평가·정정 최종화를 완료했다. 배틀 개선은 미입증이며 추가 실행 조건은 미정이다.
평가와 미정 설계는 해당 절을 따르며 L1-L5 전체 efficacy design은 여전히 미정이다.
[중간 연구 목표](#intermediate-objectives)와 broad RQ2·RQ3을 채택했으며 기존 운영 실험·진단은
개별 기록의 유효성 범위에서 연결한다. 중간 목표의 완료나 새 실험 실행을 뜻하지 않는다.
최상위 objective와 broad RQ1은 승인되었지만,
L1-L5 전체 효능 비교의 operational RQ, hypothesis, treatment, primary outcome과 evaluation protocol은 아직 승인되지
않았다. [`EP-001`](exec-plans/completed/EP-001-pokechamp-reproducible-environment.md)은 local
source/dependency/server/battle, real Ollama Cloud probe 및 valid-action IO battle을 포함한 technical
environment qualification을 완료했다.
[`EP-002`](exec-plans/completed/EP-002-pokechamp-battle-observability.md)는 opt-in full-fidelity
recording, source seal과 local static viewer capability를 완료했지만 efficacy experiment를 실행하지
않았다.
[`experiments/INDEX.md`](experiments/INDEX.md)에는 qualification, 기준선 pilot, 후속 운영 비교와
요약 진단이 등록되어 있다. 현재 EX-020/021/022는 중단 상태이며 유효 비교 완료로 해석하지
않는다. 최신 실행 상태는 STATUS와 각 EX record를 따른다.

[EP-007](exec-plans/completed/EP-007-model-concurrency.md)의 운영 측정도 완료했다. EX-004에서
C*=10을 선택했고, EX-011/012의 동일 source 8판 비교는 각각 유효 6/8과 관측 속도비
3.39배로 진행 기준을 통과했다. EX-013은 32 slot을 37.22분에 처리했지만 유효 완료는
20판이며 출력 오류 4건과 watchdog 8건을 보존했다. 전체 실측은 125.23분이었다.
이는 해당 요청 조건의 운영 evidence이며 L1-L5 효능이나 정상 minimax 성능의 검증이 아니다.
32판 모두 정상 완료하는 소요시간은 미검증이며 세부 한계는 실험 기록과 STATUS에 있다.

상속된 runtime, test, five-condition harness와 frozen archive는 존재하지만
[`D-002`](decisions/D-002-reset-research-direction.md)에 따라 새 연구의 qualification 또는 efficacy
evidence로 자동 승계되지 않는다. EP-001 smoke는 새 treatment나 metric을 검증하지 않으며 pilot,
efficacy evaluation, ablation 또는 replication이 아니다. 다음 연구 단계는 OQ-001과 OQ-002를
포함한 operational research/transfer design을 명시적으로 정하는
것이며, 이 문서는 그 결정을 대신하지 않는다.

## D-017 요청 조건 변경과 운영 검증

공개 미리보기의 미등장 상대 팀원을 후보에 포함하고 요청별 허용 JSON 목록을 명시한다.
설명 요구를 제거한다. 이는 prompt/관찰 정보 사용 조건 변경이므로 과거 C*=10을 승계하지 않는다.
[D-017](decisions/D-017-battle-identity-action-candidates.md)의24상태×2동시성×3반복, 로컬8판,
Cloud8판→조건부32판 gate와4시간 제한을 채택한다. 최대 처리량이나 효능 확증이 아니다.

상대 요청은 기존 16턴 관찰 history와 actor가 가진 구조화된 target state로 구성하여 자기
강제 교체를 상대 명령으로 전달하던 지시를 제거한다. 기술 후보는 기존
`get_opponent_current_moves()`의 관찰·추정 결과를 그대로 구조화한다. 요청 전 상대 비공개
팀 파일은 읽지 않는다. 로컬8판은 Cloud 역할만 seeded Random으로 대체한 환경 검증이다.
새 Cloud8/32판의 `retry_transient=0`을 execution record에 봉인하여 실패 보충을 하지 않는다.
기존 execution record에서 해당 필드가 없으면 기존 transient1회 재시도를 유지한다.

## D-018 원본 fallback 운영 조건

[D-018](decisions/D-018-upstream-fallback.md)에 따라 `action_policy="upstream"`에 한해
C-010/C-012의 출력 terminal·후보 prompt 규칙 대신 원본 프롬프트/추출/행동 변환/재시도/fallback을
적용한다. Provider·환경·무결성 종료는 유지한다. 필드 부재는 strict다. 정상 fallback 완료는
유효하며 전체/유효 각각 실제 전송 판단과 경기 분모를 보고한다. D-017 gate는 EX-016에
적용하지 않는다. 고정 fixture·로컬2판 후32슬롯10/10을 실행하며 Cloud4시간/신규3시간45분
중지와 retry_transient=0을 봉인한다. 이전 결과와 정상 minimax/효능/최대 처리량 주장은 분리한다.

## D-019 IO 3조건 탐색적 비교 (Current)

[D-019](decisions/D-019-improved-io.md)의 조건·표본·gate·중단 규칙을 사용자 지시에 따라
채택한다. A=upstream IO, B=개선 IO, C=B+배틀 내 요약이다. A 대비 B/C는 출력·오류 정책까지
결합된 전체 개선이며 C−B는 요약 추가의 차이다. L1–L5 전체 효능 설계의 TBD는 유지한다.
개발 b01–b04에서 조건당16판, 전체48판; smoke12판은 비교 분모에서 제외한다.
승패는 상대별 draw-adjusted score와 두 상대 동일 가중 평균으로 계산한다. 같은 block의
완료된 대응만 차이에 사용하고 누락 대응 및 예정/시도/완료/실패/미실행을 별도 보고한다.
요청/역할별 오류·token·지연과 실제 배치 경과 시간을 보고하며 actor 시간 합은 자원 지표다.
조건과 순서 seed20260908을 실행 전 봉인한다. 모든 배틀10/요청10, 재시도0;
Cloud 요청 동시성1은 지연 기준 측정 전용이다. 세부 gate와4시간 예산은 D-019를 따른다.
분석에 이미 사용된 자료의 탐색적 비교이므로 작은 승률 차이로 우월성을 주장하지 않는다.

[D-020](decisions/D-020-project-owned-ruination-patch.md) 이후 B/C는 원본 버전0.11.0과
ruination-v1의 패치 JSON 및 적용 파일 해시로 식별한다. EX-017의 원본 계산 실패와
패치 후 EX-018을 같은 조건의 연속 성공으로 합치지 않는다. 이번 재검증 분모는 기존15장면과
별도 사후3건이며 의미 rubric/전체 offline gate 및 병렬·Cloud gate와 분리한다.

## D-021 특수 기술 오프라인 진단 (Current)

[D-021](decisions/D-021-special-move-diagnostics.md)의 현재 팀1·2·6·12/고정 prior와
고위험 기술을 대상으로 독립 pinned Showdown Gen9 실행과 raw/운영 wrapper를 비교한다.
실행 전 manifest에 후보·조건·제외·미검증 사유와 source hash를 고정한다.
직접 피해의 HP 차감 전 수치와 실제 차감, 타격별 관측 및 HP 재분배를 구별한다.
단타 난수16개 및 명시적 명중/타수 조건은 조건부 수치 검증이며 확률 추정이 아니다.
개별 불일치·미지원은 독립 진단을 계속하고 새 fixture로 불일치를 재현한다.
기준 데이터·source identity·상태 변환·검증기 오류에는 전체 실행을 중단한다.
입력 표현 부족을 임의 보충하거나 정상0을 지원으로 해석하지 않는다.
모든 선정 시험의 결과/미검증 사유 확보와 도구 회귀 통과를 진단 완료로 정의하며
계산기 전체 통과, 의미 rubric 통과 또는 offline gate 통과를 뜻하지 않는다.

## D-022 재실험 (Current)

[D-022](decisions/D-022-resume-io-experiment.md)에 따라 D-019 단계 gate를 EX-020에서 재개한다.
기존15장면 의미 expected/must_not 및 사후3건을 모두 통과해야 offline receipt를 발급한다.
행동180호출, C 입력 요약 별도 분모,30행동 이상4자료×(요약3+통합1)×3=48호출을 구별한다.
실제 발생 계산/입력 오류는 독립 재현 후 패치하고 새 source로 이전 단계를 재검증한다.
패치 전후 cohort는 분리하며 비교 도중 패치는48판 전체 재시작이다. 최초 Cloud부터4시간
(신규 작업3시간45분 중지) 시계는 패치·재검증·재시작에도 유지한다. 다른 D-019 기준은 불변이다.

[D-026](decisions/D-026-continue-io-experiment.md)의 현재 사용자 재개 승인으로 EX-023에서
EX-022 후속 상태 교정을 사용해 D-019/D-022 운영 단계를 새로 실행한다. 표본·조건·low·
gate·4시간 상한은 유지한다. EX-020의 halt/clock 및 EX-021/022 무효 비교는 복구하지 않는다.
새 Cloud 시계는 EX-023 최초 제출에서 시작하며 해당 실행 내 재시작에도 유지한다.

## D-023 요약 harness 진단 (Current)

이 절에서 채택한 조건·절차·평가·해석의 중복 원문은 [EX-021 §실행 전 protocol](experiments/EX-021-summary-harness-diagnostics.md#실행-전-protocol)에 그대로 보존되어 있다.
해당 절의 아래 원문 범위를 이 문서의 규범 내용으로 명시적으로 참조 편입한다.
참조 범위는 “동일 모델·장면에서 의미 명확화와 반복 request 축소의 기여를 분리한다.”부터
“차이가 없거나 오류가 남았다는 이유로 모델 한계를 확정하지 않는다.”까지다.
EX-021에서만 모델 요약 오류는 측정치로 계속 수집하고 provider·환경·무결성·입력 변환 오류에는 전체 중단한다. 운영 gate와 EX-020 halt는 불변이다.

## D-024 상태 정비 후 요약 thinking 진단 (Current)

이 절에서 채택한 조건·절차·평가·해석의 중복 원문은 [EX-022 §질문 및 사전 protocol](experiments/EX-022-state-summary-thinking.md#질문-및-사전-protocol)에 그대로 보존되어 있다.
해당 절의 아래 원문 범위를 이 문서의 규범 내용으로 명시적으로 참조 편입한다.
참조 범위는 “정비된 운영 요약 입력에서 장면당 입력 하나를 만들고 반복 request 원본을 보존한다.”부터
“중단 시 미완료 분모를 보존한다. 운영 적용/EX-020 재개는 결과로 자동 승인하지 않는다.”까지다.
근거: [D-024](decisions/D-024-state-summary-thinking.md).

## D-027 low 요약 지시 개선 IO 재실험 (Current)

[D-027](decisions/D-027-low-summary-prompt-reexperiment.md)에 따라 EX-024에서 요약/통합
지시만 최대3버전 개선한다. 기존 A/B/C·15장면·4원자료·7제목·10/3주기와 모든 역할 low를
유지한다. 사전300+회귀/15/3/18/로컬12 → C요약8 → 별도요약48 → 행동180 → smoke12 →
조건부48판을 수행한다. 원문 독립 기준 사전 봉인 및 연쇄 선행 의미검토 통과가 필수다.
오류/누락0·HTTP겹침10·p95비율≤2·smoke12/12 후50%여유 예상시간이 예산에 들어야 한다.
요약 오류는 버전 중단 후 새 source 사전 검증, 행동출력/provider/환경/무결성은 전체 중단이다.
최초 제출의4시간/3시간45분 시계는 버전 변경에도 유지한다. 조합은 최대3개이고 실패보충은 없다.
모든 gate·48판 유효성·C요약 원문대조·대응분석·정리 완료만 실험 완료다. 개발 자료에서
지시를 개선·선택한 탐색적 비교이며 과거 무효 비교/중단 자료는 복구하지 않는다.

## D-028 고정 이전 메모리 요약 low/max 진단 (Current)

[D-028](decisions/D-028-summary-max-diagnostic.md)의 EX-025는 glm-5.3-flash·v1.1.2와
동일 입력에서 thinking만 low/max로 바꾼다. EX-024 경계22개(첫8/후속10/통합4),
각 조건3반복=132호출이다. 원문 검토된 고정 메모리를 사용하고 새 응답의 연쇄 재사용은 없다.
125필수 사실 재대조·입력별 기준·메모리 근거를 호출 전 봉인하며 평가 기준은 입력에 넣지 않는다.
주지표는 사실/진영/시점/identity/형식 오류 또는 필수 누락이 있는 응답 비율이다.
입력별3반복 후 max−low를 계산하고 종류별 보고 및 원배틀별 평균의 동일 가중 전체를 사용한다.
경계·진영·반복은 독립 표본이 아니다. 가림 검토·보조지표·재발항목·132/4시간 한도·중단은 D-028을 따른다.
오류 감소는 고정 개발입력에서의 탐색적 근거이며 남은 오류는 max로 해결되지 않았음을 보고한다.
모델의 유일 원인, 연쇄 누적, 실배틀 효능·운영 적용·IO 재개는 자동 추론하지 않는다.

실행 상태: EX-025는132응답 수집 후 실제 입력에 없는 과거 HP를 필수 평가한 불일치로
전체 무효·미완료다. 무효 초안126과 미검토6을 보존하며 low/max 효과는 추정하지 않는다.
이 상태 기록은 사전 기준이나 중단 규칙의 변경이 아니다.


## D-030 요약 없는 improved_io A/B 탐색 비교 (Current)

[D-030](decisions/D-030-io-battle-only.md)의 새 EX-026 설계를 채택한다. A는 upstream IO,
B는 교정 관측·고정 prior·계산기·기존 battle_fixed.txt·엄격한 출력 검증이며 요약/통합과
메모리 주입은0이다. 요약 실험은 분리하고 이전 중단 상태는 유지한다. 전체 B 구성의
탐색적 비교이며 prompt 단독 효과 또는 L1-L5 전체 효능으로 해석하지 않는다.

EX-016 개발16대진(Abyssal/OneStep×b01–b04×양쪽)에 A/B를 대응시킨32판,
순서 seed20260908이다. 전체 공개 prefix로 현재 관측을 만들고 최근10결정 원문만 전송한다.
원문과 실제 입력·계산에 근거한 평가를 사전 봉인하며 짧은 설명에 모든 사실의 나열이나
최적 행동을 강제하지 않는다. 로컬15장면/사후3/fake32 후 행동90(15×1/10×3)의 무오류·
HTTP overlap10·병렬p95≤순차2배 gate, b04 smoke8 유효/동시8·요약0을 요구한다.
Smoke 대진별 최대시간의10자리32판 추정×1.5가 남은 신규 작업 시간에 들어갈 때 비교한다.

최초 Cloud4시간/신규3시간45분, 총4000요청(A 추가·실패·미확정 포함), low/temperature0/
seed100/출력131072/context기본/timeout300/동시10/retry0이다. D-029의 복구1차까지
누적 gate180/smoke16/compare64를 허용하며 시계/상한을 보존한다. 실제 입력·처치·수집
결함은 영향 대응 A/B 양쪽 및 공유 영향 전체를 무효화·독립 검증 후 재수집한다.
평가 구현 교정은 온전한 응답을 대칭 재평가, rubric 교정은 별도 사후 수정 분석이다.
모델 오답 재수집은 금지한다. Gate 실패는 후속 배틀을 막고 배틀 출력/provider 오류는
신규 배틀 제출을 중지한다. 합법 완료 설명 사실 오류는 별도 오류율로 기록한다.

조건별 예정/시도/유효/실패/무효/미실행/미확정/복구, 상대별 draw-adjusted score·
두 상대 동일 가중 평균·완료 대응 차이/누락, IO/설명 오류·A fallback·호출/token/HTTP/
배치 시간을 보고한다. Smoke/과거 결과는 본 비교에 합치지 않는다. 사전 gate·smoke8·
compare32/16유효대응·검토/분석/정리 미충족 시 EP-018은 미완료다.

## D-031 행동 필드 설명서 구현 범위

[D-031](decisions/D-031-battle-field-guide.md)은 새 B 행동 v1.1.0의 입력 필드 설명서와
전달 경로의 로컬 구현·검증만 승인한다. 새로운 기본 준비에는 이 버전을 명시적으로 봉인하되
EX-026의 기존 v1.0.0 처치·입력·응답·평가·halt·시계·Blocked는 변경하지 않는다.
기술/특성/item 효과 사전·가설·평가 기준·해석 규칙은 추가하거나 변경하지 않는다.
모델 오류 감소·유료 gate·효능 비교는 이번 완료 기준에 포함되지 않는다. 후속 유료 실험의
등록·승인·gate 없이 이 변경을 EX-026 재개나 성공 처치로 사용하지 않는다.

## D-032 필드 설명서 실제 Cloud 탐색 비교

이 절에서 채택한 조건·절차·평가·해석의 중복 원문은 [EX-027 §설계·승인·복구](experiments/EX-027-battle-guide-live.md#설계승인복구)에 그대로 보존되어 있다.
해당 절의 아래 원문 범위를 이 문서의 규범 내용으로 명시적으로 참조 편입한다.
참조 범위는 “A는 upstream IO·fallback, B는 교정 관측·고정 prior·계산기·필드 설명서 v1.1.0이다.”부터
“전체 B 구성의 개발 대진 탐색적 비교이며 설명서 단독 효과나 L1–L5 전체 효능으로 귀속하지 않는다.”까지다.


## D-033 사전 검증 생략 직접32판 탐색 비교

[D-033](decisions/D-033-battle-guide-direct32.md)의 명시적 사용자 변경을 새 EX-028에만 적용한다. C-014/C-019/C-020의 기존 엄격 gate·출력 중단 경로는 유지한다.

이 절에서 채택한 조건·절차·평가·해석의 중복 원문은 [EX-028 §사전 등록](experiments/EX-028-battle-guide-direct32.md#사전-등록)에 그대로 보존되어 있다.
해당 절의 아래 원문 범위를 이 문서의 규범 내용으로 명시적으로 참조 편입한다.
참조 범위는 “A는 EX-027의 upstream IO·fallback, B는 교정 관측·고정 prior·계산기·필드 설명서 v1.1.0이며 요약·통합·메모리 주입0이다.”부터
“오류 처리 정책을 포함한 전체 구성의 개발 대진 탐색 비교이며 설명서 단독 효과나 L1–L5 효능으로 해석하지 않는다.”까지다.


## D-034 계산기 교정 동일32판

[D-034](decisions/D-034-calculator-entry-calcfix32.md)의 명시적 사용자 승인과 EX-029 사전등록을 채택한다.
기존 D-033 결과·정책은 보존하고, 필수 결함 재현·독립 Showdown 검증·전체회귀 후 새 정책으로 동일32 slot을 실행한다.
EX-028 영향은 별도 정정 분석이며 새 실행과 독립표본으로 합산하지 않는다. 기존 Blocked 재개는 없다.

## D-035 계산기 입력 정확성 로컬 진단

EX-030은 전체 입력 변환·계산·전달의 정확성을 조사하고 지원 범위 결함을 수정한다.
EX-028/029의636개 입력과 pinned Showdown 독립 기준을 사용하며 결과를 승률 개선으로 해석하지 않는다.
기존 응답/판정/봉인/원장/중단은 보존하고 수정 입력의 영향은 별도 분석한다.
과거 모델 행동·승패 복원이나 기존 무효 결과의 복구를 주장하지 않는다. 유료 재실험은 제외한다.


이 로컬 감사의 영향 집계는 기존 시나리오 수치/피해 구조의 교정, 선택 테라 방어 coverage 추가,
필수 상태·버전·설명만의 변경을 분리한다. 기존 수치의 최초 오염 시점과 coverage 누락 시점을
각각 기록하고 두 집합의 합집합 이후 결정/전개/대응 비교를 의존 범위로 표시한다.
이 사후 정확성 분석은 새로운 효능 평가 기준이나 선택된 비영향 표본의 승률 추정이 아니다.
636입력(응답632/무응답4)을 모두 포함하고 기존 주석은 수신 입력에 대한 당시 기록으로 보존한다.
수정 입력의 모델 단독 오류율·행동·승패는 새 응답 없이 복원하지 않는다.
[조사 보고서](exec-plans/evidence/ep023/report.md), [별도 영향 분석](exec-plans/evidence/ep023/impact.md).


## D-036 교정 입력·계산기 동일32판

[D-036](decisions/D-036-calculator-inputfix32.md)의 명시적 사용자 승인에 따라 EX-031에서 새 A16/B16을 실행한다.
C-021 출력복구·실패격리·재수집0을 유지하며 B만 calculator-input-v2/battle-v1.2.0/mechanics-v2다.
EX-028 봉인 대진·설정·순서를 유지하며 qualification과 semantics/runtime patch를 최종 source 및 실제 요청까지 연결한다.
기존 정책 정의/hash/과거 실험은 보존한다. 필수 로컬 검증 뒤 Cloud90/smoke8/별도fake32 없이 직접32판을 실행한다.
EX-028/029 사용량은 각 원본을 한 번씩 연결하고 미확정1건을 유지한다.
전수 검토·분모·보존·실패 정책·완료 판단의 사전 등록은 [EP-024](exec-plans/completed/EP-024-calculator-inputfix32.md)를 따른다.
성능 비교 완료는 유효32판/16대응에만 표시하며 과거 무효 결과 합산·계산기 단독/L1–L5 효과 귀속은 금지한다.


## D-038 수정 완료본 A/B32판

명시적 사용자 지시로 EX-032의 새 A16/B16을 승인한다. D-036의 대진·설정·출력복구·실패격리·전수검토·분모·해석 규칙을 유지한다.
B 계산기의 EP-025 수정본과 기존 v2 입력/프롬프트를 사용한다. EP-025593회귀·독립28조건/16roll·81재생의 봉인을 재사용하고 실행 연결 변경분만 새 검사한다.
최종 source 전체 회귀로 표시하지 않는다. 필수 연결·봉인 후 별도fake32/Cloud90/smoke8 없이 본32판을 새 실행한다.
과거 EX-028/029/031 자체 사용량을 각각 한 번 누적하고 미확정1건을 보존한다. 유효32판/16대응에만 비교 완료를 표시한다.
상세 승인·조건·중단·보고는 [EP-026](exec-plans/completed/EP-026-battle-guide-movefix32.md)에 등록한다.

## D-039 외부 메모리 장애 후 동일 조건 반복

사용자는 외부 프로세스 RAM 급증이 EX-032 중단 원인으로 판단되고 현재 해소됐다고 보고하며
같은 조건의 새32판을 승인했다. 귀속은 사용자 보고로 기록하고 독립 OOM 확정이나 permit 수정으로 표시하지 않는다.
EX-033은 EX-032와 동일한 처치/설정/대진/seed/순서를 사용하고 새 실행 identity·기준 검증 재사용·과거 사용량 연결만 추가한다.
기존 실패·성능 분모·halt는 유지한다. EX-032의 완료분을 새 실행에 합치지 않으며 반복을 독립 표본으로 합산하지 않는다.
기존 최초시계·누적 미확정1건/사용량을 연결한다. 상세 새 실행 승인·중단·검토·완료는
[EP-027](exec-plans/completed/EP-027-external-memory-repeat32.md)을 따른다.


## D-040 Smogon 기반 원본 A 진단 평가 준비

[D-040](decisions/D-040-smogon-diagnostic-design.md)은 명시적 사용자 계획에 따라
[EX-034](experiments/EX-034-smogon-diagnostic-design.md)의 팀 선별·대진·평가·자원 명세와
로컬 검증만 채택한다. 유료 대전·실행기/API 구현은 포함하지 않는다. 방향성 실패 가설 없이
원본 A가 어떤 운용 상황에서 판단하는지 조사할 준비이며 L1–L5 효능 평가가 아니다.

Smogon Sample/Bazaar에서 과제별 후보3개·선정2개, 총12후보/8팀을 기록한다.
셋업·공격 순서, 교체·설치기 누적, 회복·핵심 보존, 날씨 등 제한된 턴의 각1팀은 탐색,
나머지1팀은 후속확인으로 둔다. 동일·유사 변형을 양쪽에 나누지 않는다. 합법성은 pinned
Gen9 OU, 다음은 완전성·운용 근거·기존 팀과 다른 판단 기회를 우선한다. 커뮤니티 평가와
연구자의 과제 적합성 판단을 구분하고 원본 팀·작성자/출처/수집일/hash/불확실성을 보존한다.

탐색4×기존 팀2/6×Abyssal/OneStep×양쪽 팀 배정×반복2의64 slot과 전체 seed/제출 순서를
고정한다. 셀마다 반복2개는 서로 다른 게임 seed와 A의 p1/p2를 한 번씩 쓴다.
진영·게임 난수의 독립 효과나64개 독립 전략 표본을 가정하지 않는다.
A 입력 생성·prompt·모델·upstream fallback은 EX-033 기준으로 유지하며 팀 해설을 추가하지 않는다.

승률/무승부 반영 점수를 정책·팀 배정·과제별로 보고하고 예정/시도/유효완료/실패/무효/미실행을
보존한다. 모든 A 결정(무호출·fallback·실패 경기 포함)을 실제 입력·원응답·전송·공개 prefix와
연결하여 검토한다. 판단 오류·입력의 누락/오류·출력/실행 실패를 구별하고 증거가 부족한 전략
판정은 미확정이다. 원본 노출 한계는 baseline의 특성이고 새 수집 이탈은 C-018 결함이다.
패배 자체로 한계를 확정하지 않으며 승리의 실수도 포함한다. 서로 다른 게임2개 이상의
동일 유형은 후속 가설 후보 기준일 뿐 확증 기준이 아니다. 보류 팀의 확인 조건은 탐색 후 별도 등록한다.

Slot1회/provider retry0/보충·재수집0, 경기별 실패격리·공유 결함의 영향 범위 중단을
기본안으로 한다. 원본 A 파싱 재질의는 provider 재시도와 구분한다.
EX-033 A만의 사용량을 기준으로 추정하고 장기전/입력 증가·watchdog의 완료 한계를 밝힌다.
새 실행기 지원과 유료 상한/시계·실행 승인은 별도이며 EX-033 무상한/gate 생략을 승계하지 않는다.
준비 완료는 실패 사례 발견이나 대전 완료가 아닌 재현 가능한 평가 명세의 검증으로 판단한다.
기존 실험/Blocked/원자료/판정/halt/시계는 유지한다. 세부 기준은 EX-034의 versioned protocol을 따른다.


## D-041 원본 A64 진단 실행

[D-041](decisions/D-041-a-diagnostic64.md)의 명시적 사용자 승인으로 EX-034 준비에서 EX-035 실행으로 진행한다.
EX-034 평가 protocol v1은 유지하고 운영 watchdog만3600초로 변경한다.
새 a-diagnostic64-v1은 A-only, 첫10 검사 후54, 로컬/fake64 필수, Cloud90/smoke8 없음,
최초 요청부터20700초 수집/21600초 총시간·8000요청 원자 예약·동시성10·재수집0이다.
기존 정책/원자료는 보존하며 상세 사전등록은 [EP-029](exec-plans/completed/EP-029-a-diagnostic64.md)를 따른다.
EX-035는 유효64/64·1902결정 전수검토·보존/보고를 완료했다. 결과와 사후 분류 정규화·기회 집계·
해석 한계는 [최종 보고서](exec-plans/evidence/ep029/report.md)에 보존하며 protocol v1을 대체하지 않는다.
후속 가설은 탐색 산출물이고 보류팀 실행이나 새 treatment를 자동 승인하지 않는다.

## D-042 원본 A/B 직접 대결32

[D-042](decisions/D-042-ab-head-to-head32.md)의 현재 사용자 지시와
[EX-036](experiments/EX-036-ab-head-to-head32.md)의 사전등록을 채택한다.
EX-033 전체 A/B 처치는 불변이고 각 진영의 actor_conditions로 연결한다.
공통8000요청/20700초 수집/21600초 총시간,첫10 기술검사 후22,재수집0이다.
주지표는 B의 A상대 승률·무승부보정점수이며 양쪽 유효16대응쌍은 쌍내 B점수 평균을 쓴다.
양쪽 모든 결정을 받은 입력과 결정직전 공개prefix로 검토한다. 기존 정책/Blocked는 유지한다.

## D-044 Protect 수정본 A/B 직접32

[D-044](decisions/D-044-ab-head-to-head32-protectfix.md)와 [EX-037](experiments/EX-037-ab-head-to-head32-protectfix.md)의 현재 명시적 지시를 채택한다.
이 절에서 채택한 조건·절차·평가·해석의 중복 원문은 [EP-032 §목표·범위·승인·불변조건](exec-plans/active/EP-032-ab-head-to-head32-protectfix.md#목표범위승인불변조건)에 그대로 보존되어 있다.
해당 절의 아래 원문 범위를 이 문서의 규범 내용으로 명시적으로 참조 편입한다.
참조 범위는 “현재 사용자 제공 실행 계획을 명시적 승인 근거로 EX-037/EP-032/D-044를 등록한다.”부터
“중단 시에도 수집분 검토/보고/보존/정리와 실제분모·미완료 사유를 기록하며 중단처리 완료를 비교완료로 표시하지 않는다.”까지다.


## D-045 전체 Cloud 기본 동시성8

[D-045](decisions/D-045-cloud-concurrency-default8.md)의 명시적 사용자 지시를 채택한다.
새 Cloud 병렬 실행과 gate/요청 검증은 기본8을 선언하고 순차1·명시1–10을 유지한다.
새 Z.ai 준비에는 아래 D-056의 기본4 예외가 우선한다.
별도 동시성 측정의 명시적인1–10 조건은 변경하지 않는다. 기존 실행/정책 identity와 결과는 소급 변경하지 않는다.
동시성은 새로운 execution evidence에 별도로 봉인하며 보고·추정·검증은 그 값을 사용한다.
이 운영 기본값 변경은 timeout 원인의 입증이나 개선 효과의 실험 결과가 아니다.
EP-033은 비실험 구현·로컬 검증이며 기존 Blocked 재개나 추가 유료 실험을 포함하지 않는다.

## D-046 B 프롬프트 오프라인 최적화

EX-037의 실패 경기 포함 B 입력1060 전체를 B0–B3에 공통 사용하고 응답 유무를 분리한다.
정보 보존은 합법 행동/순서·상태·사실/가설·계산 시나리오/수치/조건 및 최근10결정 복원으로
검사한다. 명시적 제외 항목 이외 손실은 실패다. 원본 검증과 무네트워크 전달 검사를 분리한다.
system/user/구성 요소 문자·UTF-8 byte 평균/중앙값/p95/최대, 단계별 및 누적 절감을 보고한다.
최소 절감률은 강제하지 않는다. 일치 tokenizer 미확인이면 토큰 절감률 미측정이다.
과거 선택 행동 일치는 정답 기준이 아니며 오프라인 통과는 모델 판단력·승률·지연 개선을
뜻하지 않는다. 실제 모델 평가·후속 후보 선택은 이번 범위 밖이고 기존 Blocked를 유지한다.


## D-047 B2 직접대결32

이 절에서 채택한 조건·절차·평가·해석의 중복 원문은 [EX-038 §사전 protocol](experiments/EX-038-ab-head-to-head32-b2.md#사전-protocol)에 그대로 보존되어 있다.
해당 절의 아래 원문 범위를 이 문서의 규범 내용으로 명시적으로 참조 편입한다.
참조 범위는 “2026-09-14 사용자가 EX-037 직접대결 재사용, 코드 버그만 확인한 뒤 바로 본실험 진입을 선택하고 제시된 계획의 구현을 명시적으로 지시했다.”부터
“미달이면 부분 결과와 원인을 보존하고 Blocked로 남긴다. 중단처리 완료는 비교완료가 아니다.”까지다.



## D-052 B2 선봉 정책 구현과 후속 비교 준비

현재 사용자 지시로 Gen9 OU singles의 선봉 선택 하나를 추가한다. 동일 EP-036 교정 source의 B2를
통제/처치에 공통 사용하고 팀/세트·모델/thinking·배틀 prompt·압축·계산·전투 행동 정책은 고정한다.
D-052의 승인 당시에는 `seeded_random` 대 `llm_lead`의 대응 탐색 비교 초안만 준비했고 표본·비용·수집은 미승인이었다.
후속 실제 실행 승인은 아래 D-053과 EX-039를 따른다.
선봉 외 순열의 상대 순서와 actor RNG 소비를 보존한다. 로컬 기술 검증은 효능 평가가 아니다.
EX-038은 A 대 B2 중단 비교이며 과거 B와의 부분 성적 유사성을 B/B2 동등성 또는 압축 효과로 해석하지 않는다.
설명 오류 사후 annotation은 §8.1 기본 제외, 전략적 성능은 미평가다.

## D-053 EX-039 선봉 정책 대응 비교 실행

[사용자 실행 지시](decisions/D-053-b2-lead-comparison.md)에 따라 EX-039의32경기/16대응쌍·첫 대응쌍 기술 gate를 채택한다.
사전 조건·지표·분모·실패·해석 기준의 원문은 [EX-039](experiments/EX-039-b2-lead-proposal.md)다.
금액 상한은 사용자 후속 지시로 제외한다. 기술 gate는 승패·전략·설명 평가로 판정하지 않는다.

## D-055 EX-040 Z.ai 선봉 정책 비교

[EX-040](experiments/EX-040-b2-lead-zai.md)을 새32경기/16대응쌍 비교의 조건·한도·gate·분모·해석 원문으로 채택한다. D-053의 과거 실행은 보존하며 Z.ai 환경의 선봉 정책 비교만 허용한다.

## D-056 Z.ai 기본4·EX-041 재실험

새 Z.ai 기본 동시성은 D-045의 해당 범위에 우선하여4다. 명시 설정과 과거 봉인값은 유지한다.
[EX-041](experiments/EX-041-b2-lead-zai4.md)을 조건·한도·gate·분모·해석 원문으로 채택한다.
EX-039/040과 결과를 합산하지 않으며429 원인이나 동시성 인과 효과를 주장하지 않는다.

<a id="d-057-배틀선봉-상세-효과-사전"></a>

## D-057 배틀·선봉 상세 효과 사전

새 B/B2·선봉 프롬프트에 일반 게임 지식을 추가하는 처치 변경을 명시한다. 상세 원문은 요청당
항목별 한 번 제공하며 기존 관측·prior·계산 의미·출력 정책은 유지한다. 기존 EX에는 소급하지 않는다.
이번 범위는 구현·로컬 검증 및 EX-041 입력의 오프라인 표현 감사다. 성능 비교·유료 호출0이며
문자/byte 증가·중복 제거량은 보고하되 토큰·지연·전략·승률·L1-L5 효능 개선으로 해석하지 않는다.

## D-058 새 응답 대기·연결 재시도 기본값

새 요청의 전송 정책은 [C-038](CONTRACTS.md#c-038-transport-retry)을 따른다.
논리적인 모델 요청과 HTTP 시도를 별도 분모로 기록한다. 재시도는 새 경기/표본/출력 재질의가 아니다.
기존 EX의 retry0·300초 및 중단 상태는 유지한다. §11.1의 도구 결함 복구는 이번 명시적
연결 재시도보다 넓은 재시도를 허용하지 않는다. 공급자 반반 비교의 세부 설계는 미정이다.

## D-059 공급자4+4 분산 선봉 비교

[EX-042](experiments/EX-042-distributed-lead.md)의 조건·배정·지표·분모·gate·중단·해석을 새 실험의 원문으로 채택한다. 공급자별 유효 완료율/완료쌍이 주지표이며 서로 다른 seed·지원 옵션 때문에 공급자 우열 확증으로 해석하지 않는다. 과거 실험과 합산하거나 prompt/재시도의 단독 효과를 주장하지 않는다.

## D-060 새 공급자 오류 재시도

새 전송 기본값은 [C-038](CONTRACTS.md#c-038-transport-retry)의 provider-retry-v2다.
연결·timeout·5xx·429의 고정1/2/4초 최대3재시도 및 최종429 전체 중단을 채택한다.
재시도는 같은 논리 요청의 전송이며 표본·경기 추가나 출력 재추첨이 아니다.
과거 EX-042 및 모든 동결 실행의 정책·결과·Blocked는 보존한다. 새 유료 실험 승인은 아니다.

## D-061 선봉 전략·규칙 입력 개선

matchup-v2는 모든 자기 후보의 초반 이득·방해 선봉·실제 세팅 행동·불리한 대면의 교체와 비용·후반 보존·차선 대비 이유를 비교한다. 공개 상대6종을 검토하며 미제공 정책/확률을 만들지 않는다.
dex-v2는 타입/면역/기술 속성 및 범위 제한 가능성의 일반 지식 추가다. 두 처치는 독립 비교 가능하며 새 준비 기본값만 변경한다.
검증은 오프라인 코드/입력/전송·기존32선봉 재생이다. 특정 슬롯을 정답으로 고정하지 않는다. 원본 명시적 주장의 자기 기술 보유·타입·면역·계획 조건을 검사하고 설명 누락은 기록된 근거 부족으로 분류한다.
내부 고려 부재나 패배 원인을 추론하지 않는다. 새 모델의 오류 재발률·선택 품질·승률·지연 및 L1–L5 효능은 미평가다.

## D-064 교정 B2 개선 선봉 비교

[EX-043](experiments/EX-043-corrected-lead.md)의 조건·표본·중단·지표·완료·해석 규칙을 이번 실험의 원문으로 채택한다. 개선 정책 묶음의 탐색 비교이며 전략/Dex 개별 효과와 L1–L5 구조 효과는 분리하지 않는다. 과거 EX-042 정정·미완료는 유지한다.

## EX-044 직접 본실험

D-065의 명시적 재실행·사전 검사 생략 지시에 따라 [EX-044](experiments/EX-044-direct-corrected-lead.md)를 적용한다. 처치/표본/지표/해석은 EX-043을 유지하고 별도 사전 검증만 skipped_by_user다. 본실험 gate/입력 감사는 유지하며 과거 중단 결과와 합산하지 않는다.

## D-066 공식 관측 소스 전환

새 B/B2 모델·계산 입력의 소스를 공식 client-v1으로 바꾸는 처치 변경이다.
EP-056 검증 완료 후 새 준비에만 기본 적용한다. 기존 계산식/지원 범위·선봉 정책은 유지한다.
100개 보존 결정 경계 전수 재생과 팀6/12 진영 교환2경기(결정적 mock, 경기당600초·재경기0)는
기술적 입력/실행 검증이다. 지연/메모리는 보고하되 모델 판단·승률·L1–L5 효능 근거로 해석하지 않는다.
과거 관측·실험 봉인·실패 판정은 보존하고 새 source로 소급 유효화하지 않는다. 유료 호출은 없다.

## D-067 공식 관측 B2 선봉 정책 비교

[EX-045](experiments/EX-045-official-lead.md)의 조건·표본·지표·gate·중단·완료·해석을 이번 실험 원문으로 채택한다. 공식 관측 공통 입력에서 LLM 선봉 묶음 대 무작위 선봉의 탐색 비교다. 공식 관측 자체·legacy 대비·전략/Dex 개별·L1–L5 효과를 분리하지 않는다. 과거 결과와 합산하지 않는다.

## D-069 비동기 교정본 공식 관측 본실험

[EX-046](experiments/EX-046-async-official-lead.md)의 신규 실행 및 명시적 진입 차이를 채택한다. EX-045의 비교·평가·중단·해석은 유지하고 과거 결과와 합산하지 않는다.

## D-071 JEV Choice 기술 진단

[EX-047](experiments/EX-047-jev-battle.md)의 간결한 공식 관측·Choice/선봉·Abyssal2경기 진단을
채택한다. 계산과 사전을 제외한 별도 처치이며 B2의 표현 변경이나 모델 단독 효과 비교가 아니다.
상한/분모/중단·유료복구0은 EX-047을 따른다. 2경기 승패로 효능을 주장하지 않는다.

## D-072 JEV 수치 표현 호환성 교정

사용자 지적에 따라 확률 합계를 새 JEV 출력 수락 조건에서 제거한다. runtime 원문은 C-045다.
과거 EX-047의 동결 기준·실행 판정·미완료는 보존하고 새 기준의 저장 응답 검증은 별도 오프라인
근거로 기록한다. 실제 실험 재개나 완주를 뜻하지 않는다.

## D-073 JEV 수정본 재실행

사용자 재실행 지시에 따른 [EX-048](experiments/EX-048-jev-repeat.md)의2경기 조건·상한·중단·완료 기준을 채택한다. EX-047과 별도 원장/시계로 수집하고 과거 실패를 보존한다.

## D-081 JEV 대 Abyssal32 탐색 측정

[EX-052](experiments/EX-052-jev-abyssal32.md)의 EX-046 대진 재사용·Abyssal 고정·JEV32경기와
완료쌍 평균점수·분모·기술통계 해석을 채택한다. 모델 우열이나 L1-L5 효능 비교가 아니다.

## D-082 JEV v3 일반 게임 지식 추가

새 JEV v3는 사용자 제공 Gen9 singles 기본 지식과 요청별 상세 효과 사전을 추가하는 처치다.
계약은 C-045를 따른다. EX-052 저장 입력의 오프라인 비교만 수행하며 성능·지연·토큰·승률·
L1-L5 효능을 평가하지 않는다. 과거 v1/v2 실험의 입력·결과·판정은 변경하지 않는다.

## D-083 JEV v3 동일32 전후 비교

[EX-053](experiments/EX-053-jev-v3-abyssal32.md)은 EP-074 전체 처치를 EX-052 동일 대진32경기에
적용한다. EX-052 봉인 v2와 slot_id로 연결한 공통 유효 완료쌍 점수차의 동일가중 평균을
탐색적으로 보고한다. 지식·사전·PP 출처 제거의 개별 효과와 모델 버전 변화의 인과 분리는 하지 않는다.
실행 조건·분모·중단·해석의 실험별 원문은 EX-053이며 D-082의 오프라인 범위를 별도 승인으로 확장한다.

## D-084 provider 재시도3회

사용자의 명시적 지시로 새 JEV 전송 재시도를3회로 고정한다. 기술 오류의 최종 중단은
허용 재시도 소진 뒤 적용하며 판단 오류 처리는 RD11.2를 유지한다. 재시도는 별도 배틀이나
독립 표본으로 세지 않으며 사용량·실패 분모에 포함한다. 과거 동결 실험의 중단·판정은 보존한다.

## D-085 EX-054 동일 조건 재실험

사용자 지시로 EX-053의 v3 동일32경기를 EX-054로 새 실행한다. D-084 provider 재시도3회를 적용하고
EX-052 공통 완료쌍의 탐색적 전후 비교를 유지한다. 재시도 정책·모델 변화는 운영 교란으로 보고한다.
승인·조건·새 시계/예산·분모/중단 원문은 [EX-054](experiments/EX-054-jev-v3-retry32.md)이다.

## D-088 EX-056 직접 본실험

사용자 지시로 [EX-056](experiments/EX-056-jev-direct32.md)의 새32경기·사전 검증 생략·경기별/종료 감사를 채택한다. EX-052 공통 완료쌍 비교·재시도/모델 교란 제한을 유지한다.

## D-089 EX-057 모델 고정 본실험

[EX-057](experiments/EX-057-jev-pinned32.md)은 사용자 지시로 EX-056의 요청 모델만 jev-1.13.0으로 고정한 새32경기다. 사전검증 생략·새 시계·실패 격리/기술 중단·EX-052 공통쌍 비교를 유지하며 모델 요청명 차이를 해석 제한으로 명시한다.


<a id="role-corpus-expansion"></a>

## D-090 팀 데이터 기반 열람 역할 DB

사용자 승인으로 [D-090](decisions/D-090-team-corpus-role-expansion.md)의409종 역할 자료를
오프라인으로 확장한다. 실제 세트와 기계적 효과의 조건 일치는 역할 가능성에 대한 추론이며,
새 역할의 prior/OU 실전성·전략적 적합성은 미평가다. 전세트 커버리지는 자료의 적용 범위를
나타낼 뿐 정확성/성능 지표가 아니다. 새 API/배틀·운영 처치 변경·기존 실험 재개는 포함하지 않는다.

## D-091 현재 팀 후보 제한

사용자 지시에 따라 현재 팀 후보는 [D-091](decisions/D-091-reviewed-species-team-list.md)의
검토 완료108종만으로 구성된 Metamon Gen9 OU 파일 목록으로 제한한다.
[목록과 사용 기준](../export/teams/README.md)을 새 팀 선택의 입력으로 삼는다.
세트별 역할 매칭은 추가 포함 조건이 아니며 검토 완료를 역할 확정/전략적 정확성으로 해석하지
않는다. 새 평가의 대진·표본·예산은 별도 EX에서 고정하며 과거 동결 모집단은 유지한다.

## D-092 JEV 오프라인 표현·정보 생략 비교

현재 사용자 지시에 따라 별도 오프라인 입력을 구현하고 저장 관측의 구조·정보 보존을 검증한다.
효과 인라인/슬롯 통합/방어 타입/로그의 표현 변경, 역할·상성·피해량의 정보 추가, 상대 벤치 요약의
정보 생략, 자기 벤치 선택 축약의 정보 생략을 구분한다. 자기 축약은 동일한 새 상세 입력과
비교하며 선봉·강제교체에는 적용하지 않는다. 대리 토크나이저 수치는 JEV 실측 usage가 아니다.
판단 성능·승률·효능 평가는 없고 구조 검증으로 개선을 주장하지 않는다.
[D-093](decisions/D-093-speed-uncertainty.md)의 명시적 후속 지시로 스피드 확률 요구는 세트별
정성적 비교와 불확실성 표시로 대체한다. 확률 가중치나 위험 선택 정책은 도입하지 않는다.
추천 세트 내부/사이의 불확실성을 보존하고 후보 전체 일치도 해당 유한 지원 내 결과로 한정한다.

## D-094 — 개선 입력 전체 처치 탐색 비교

[EX-058](experiments/EX-058-jev-improved32.md)의 EX-057 동일32경기·공통 완료쌍 비교를 채택한다.
새 후보를 고르는 대신 이번 재현 범위에서 봉인 대진을 유지한다. EP-093 표현/정보 추가/상대
벤치 생략 전체 처치이며 개별 효과·일반 성능 향상을 주장하지 않는다. 상세 protocol은 EX가 소유한다.

## D-095 — 자기 벤치 축약 탐색 비교

[EX-059](experiments/EX-059-jev-compact32.md)의 EX-058 동일32경기 및 공통 유효 완료쌍의 축약−상세
동일가중 점수차를 채택한다. EX-057은 참고 성적이다. 자기 벤치 정보 생략의 탐색 비교이며
일반 성능 향상·성능 동등성·L1-L5 효능을 주장하지 않는다. 상세 protocol은 EX가 소유한다.

## D-097 — 한 경기 조건부 행동 가치 데이터

[EX-060](experiments/EX-060-single-battle-branch-rollouts.md)의 원재현 gate·고정 대진·양측 Abyssal 후속·32반복 수집을 채택한다. 입력은 실전 관측이며 타깃은 실제 숨은 상태와 후속 정책 조건부 값이다. 기존 경기 패배와 다른 후속 정책의 승리를 직접 비교하지 않고 원행동도 같은 조건에서 수집한다. 일반 OU/최적 정책/JEV 성능·확정 우열 claim은 하지 않으며 사용 대진은 개발 자료로 분류한다.

## D-103 — 공동 q 학습 데이터

[EX-065](experiments/EX-065-joint-q-data.md)의 신규80경기·고정 숨은 상태·Abyssal32후속
조건부 q 수집과10경기 파일럿 gate를 채택한다. 상세 모집단/split/분모/복구/오염 관리/
해석은 해당 EX가 소유한다. 공동 입력/로더 구축이며 모델 학습·성능 평가는 수행하지 않는다.

## D-107 — 자발적 Tera 보완 공동 q 데이터

[EX-067](experiments/EX-067-abyssal-tera-joint-q.md)의 동결 정책부터 산출물과 완료까지를
이번 수집의 규범으로 채택한다. 원경기와 후속 양측의 자발적 Tera·이후 관측 보완이 목적이며
고정 휴리스틱의 최적성·배틀 성능 향상을 평가하는 실험은 아니다. 새로운 q는 해당 후속 정책에
조건부이고 기존 EX-065 q/EX-066 학습에 자동 병합하지 않는다.
