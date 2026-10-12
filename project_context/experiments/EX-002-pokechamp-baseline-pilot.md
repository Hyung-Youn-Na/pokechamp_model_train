# EX-002 — 중단 처리 검증 후 PokéChamp 기준선 pilot

- 상태 (Status): Completed
- 완료일: 2026-09-07 (Asia/Seoul)
- 생성일: 2026-09-06
- 관련 plan: [EP-004](../exec-plans/completed/EP-004-pokechamp-baseline-pilot.md)
- 관련 decision: [D-012](../decisions/D-012-adopt-pokechamp-baseline-pilot.md)
- 선행 cohort: [EX-001](EX-001-pokechamp-baseline-pilot.md), Stopped; 결과를 합치지 않음

## 질문과 사전 protocol

RQ-B0: 고정 환경에서 기존 minimax/IO/규칙 봇의 완료 성적, 신뢰성, 호출량과 시간은 얼마인가?
방향성 가설 없이 탐색적 추정을 수행한다. Pilot으로 RQ1의 개선 여부를 support/reject하지 않는다.

Gen9 OU, seed 20260906, 개발 팀 [1,2,5,6,9,11,12,13], 확증 팀 [3,4,7,8,10].
Minimax(K=2 optimized), IO, Abyssal, OneStep, Random의 10개 대진, 공통 2개 team/seed block,
각 block의 team/진영 교환 2경기: 40개 예정 slot. 본 실험 N은 승인하지 않는다.
LLM glm-5.3-flash/Ollama Cloud, low, context 8192, output 512. 호출별 원본 temperature 유지.
Showdown timer off, provider request 120초, 경기 watchdog 1200초. 각 경기의 server와 각 actor는
새 process다. Source snapshot, 팀 checksum, actual seed와 실행 순서는 source seal로 고정한다.

## 재시도·중단·분모

일시 provider transport/rate-limit/timeout만 동일 slot에 한 번 재시도한다. Actor 한쪽이라도
비재시도 오류이면 다른 쪽 transient 오류로 재시도 허용을 덮어쓰지 않는다. Output/algorithm/
watchdog 중단은 패배가 아니다. Auth/model/configuration/integrity는 batch 중단이다.
모든 attempt를 보존한다. 예정 slot, 처리 slot, attempts, 유효 완료, 실패 사유를 별도 보고한다.
IO/minimax 핵심 점수는 Abyssal·OneStep 각각의 (W+0.5D)/N의 동일 가중 평균이며 한 상대의
유효 완료가 없으면 null이다. Shared team/seed block을 묶어서 분산을 계산하되 pilot 2개
block의 분산은 불안정하며 CI/우월성 claim을 내리지 않는다. 과금 근거 없이 금액을 만들지 않는다.

## 격리와 수정 내역

확증 trace를 개발·메모리에 넣지 않는다. EX-001과 qualification은 분모에서 제외한다.
수정은 peer failure/watchdog의 추가 호출 차단, cancellation marker 경쟁 방지, failure 우선순위,
서로 다른 benchmark ID 간 runtime lock과 역할별 validation metadata다. 선택 정책이나
프롬프트를 결과에 맞추어 조정하지 않았다. EX-001의 일곱 slot을 포함해 40개 schedule을 새로
실행하여 서로 다른 source의 결과를 조용히 합치지 않는다.

## Evidence 및 결과

40/40 예정 slot, 40 attempts를 처리했다. 유효 완료 31 (77.5%), 실패 9다. 무승부와 재시도는
없다. Actor 자체 원인은 output_contract 8회, watchdog 1회다. 규칙 봇 자체 오류는 없다.
실행기 원본 summary에는 output_contract 4회, algorithm 5회로 기록됐다. Worker 종료를
polling 전에 관찰하면 일반 분류가 실제 원인을 가리는 경쟁 조건이 있었으며, actor별 원자료로
다음 표를 산출했다. 재시도·batch 중단 대상인 transient/auth/model/configuration/integrity
actor 오류는 0회여서 이 분류 차이로 누락된 재시도나 batch 중단은 없다. 원 summary를 수정하지 않았다.

| 방법 | 예정 경기 | 유효 완료 | 자체 종료 오류 | 상대 오류에 따른 중단 |
|---|---:|---:|---|---:|
| minimax | 16 | 9 | output_contract 4, watchdog 1 | 2 |
| IO | 16 | 12 | output_contract 4 | 0 |
| Abyssal | 16 | 13 | 없음 | 3 |
| OneStep | 16 | 13 | 없음 | 3 |
| Random | 16 | 15 | 없음 | 1 |

### 정상 완료 조건부 성적

IO는 Abyssal 3승/3경기, OneStep 3승/3경기여서 핵심 점수 1.0이다. Minimax는 Abyssal
0승/2경기, OneStep 0승/2경기여서 핵심 점수 0.0이다. IO–minimax 직접 대진은 IO 2승/2경기다.
이는 실패를 제외한 소표본의 기술 통계이며, IO의 일반적 우월성이나 L1-L5 개선 효과를 뜻하지 않는다.

### 비용과 시간

| 방법 | 호출 | 입력 token | 출력 token | decision 중앙값(s) | p95(s) |
|---|---:|---:|---:|---:|---:|
| IO | 473 | 1026084 | 32975 | 2.192 | 3.460 |
| minimax | 2548 | 5305123 | 161454 | 14.942 | 26.089 |

실패 attempt를 포함한다. Provider 사용량 누락 호출은 0개이며 실제 청구 금액은 산출하지 않았다.
전체 attempt 순차 경과 시간의 합은 약 2.85시간이다. 같은 실패율·대전 길이를 가정한 대진별
선형 추정은 예정 1280경기에 약 89.1시간, 2480경기에 약 172.3시간이다. 정상 완료 경기 수를
보장하는 비용 추정이 아니며, 표본이 대진당 4 slot뿐이라 잠정치다.

### 중요 해석 제한

- 유효 완료 minimax 9경기에서 choose 전송 331회 중 outer search 예외 후 action fallback이
  267회(80.7%)였다. 정상 damage-calculator 선택은 58회다. 고정 upstream source의 search
  함수 AST와 seal된 diagnostics의 상대 행 246으로 예외 경로를 식별했다. 보조 worker log의
  267개 메시지는 모두 `name 'depth' is not defined`다. 오류는 upstream 시각화/성능 로그
  경로에 있다. 외부 source를 수정하지 않았으며 이 수치를 오류 없는 minimax 탐색 성능으로
  일반화하지 않는다.
- IO의 출력 오류 4건은 모두 length stop에 따른 invalid JSON이다. Minimax는 상대 행동
  검증 3건, 자기 행동 검증 1건이 실패했다. Tool choice 및 state value 출력 오류는 0건이다.
- 완전한 anchor shared block은 IO 1개, minimax 0개다. 두 방법 모두 관측 block 분산을
  추정할 수 없다. 안정적인 CI, ±5%p 정밀도 또는 개선 효과 검정력을 주장하지 않는다.
  보수적 분산 상한 기반 계획용 block 수만 보고서에 남긴다.
- Confirmatory 팀 5개는 사용하지 않았다. 본 실험 N, 자원 한도 및 L1-L5 treatment는
  미정이며 본 실험을 자동 실행하지 않았다. EX-001/qualification과 결과를 합치지 않았다.

### Evidence

- [파생 결과 보고서](../../.pokechamp-data/benchmarks/baseline-pilot-v3/report.md)
- [기계 판독 결과](../../.pokechamp-data/benchmarks/baseline-pilot-v3/report.json)
- [80개 actor trace/replay 색인](../../.pokechamp-data/experiments/baseline-pilot-v3/index.html)
- 원자료: `POKECHAMP_DATA_ROOT/benchmarks/baseline-pilot-v3/plan.json`, `source/`, `attempts/` 및
  `experiments/baseline-pilot-v3/battles/`. 모든 match/actor seal 검증 통과.

### 실행 후 도구 보완

40 slot 종료 후 최종 actor 결과를 다시 읽어 worker exit의 일반 분류보다 실제 오류의
우선순위를 보존하도록 수정했다. Timeout 재시도와 auth 중단이 빠른 worker 종료에 가려지지
않는 fixture 4개를 추가했다. 이미 완료된 EX-002 source/결과는 원형 보존하며 후속 실행은
새 identity가 필요하다. 분석에는 actor 신뢰성, 실제 action fallback, 대진별 자원 환산을
추가했다. Primary score와 eligibility는 변경하지 않았다.

전체 72 integration tests와 변경 파일 Ruff 통과. 외부 Cloud 호출 없는 실제 양측 actor
회귀 테스트 포함. 80 actor bundle seal과 report 분석 source hash 검증, artifact 1133개
credential 검사, pinned submodule clean 및 server 종료 상태를 확인했다.
분석 코드 사본은 benchmark directory의 `analysis_source.py`에 있다.

## 선행 검증

전체 66 integration tests 통과. 실제 Showdown + 두 actor fixture에서 외부 Cloud 호출 없이
pending 응답/사용량 보존, actor별 호출 1개, 취소 후 choose 0개와 양측 source seal/complete를
확인했다. 변경 파일 Ruff E/F/I/W (100 columns) 통과. Source와 40-slot schedule을 seal한 뒤 실행했다.

분석 코드 SHA256: `44e8099b659ff894012fb9d70082212ce4c47a47428160bf7dcd225e2cd8d249`.
