# 공통 실행·운영 측정 — 연구 설계

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="0-d-012-기준선-pilot의-현재-설계"></a>
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

<a id="01-d-016-운영-동시성-측정"></a>
## 0.1 D-016 운영 동시성 측정

[D-016](decisions/D-016-model-concurrency.md)의 corpus/순서/30분 calibration/선택 규칙,
동일 source 8판 순차·병렬 비교와 조건부 32판, 총 4시간 stopping rule을 채택한다.
실측 운용 상한은 해당 계정·모델·요청 조건 범위다. Batch wall time을 시간 분모로 쓰며
전송 실패·출력 실패·미실행 slot·fallback을 분리 보존한다. 모든 단계는 별도 실험 ID다.
소표본 운영 진행 기준이며 효능, 정상 minimax, 서버 내부 병렬 처리의 확증이 아니다.

<a id="보존된-운영-검증의-범위"></a>
### 보존된 운영 검증의 범위

[EP-007](plans/EP-007-model-concurrency.md)의 운영 측정도 완료했다. EX-004에서
C*=10을 선택했고, EX-011/012의 동일 source 8판 비교는 각각 유효 6/8과 관측 속도비
3.39배로 진행 기준을 통과했다. EX-013은 32 slot을 37.22분에 처리했지만 유효 완료는
20판이며 출력 오류 4건과 watchdog 8건을 보존했다. 전체 실측은 125.23분이었다.
이는 해당 요청 조건의 운영 evidence이며 L1-L5 효능이나 정상 minimax 성능의 검증이 아니다.
32판 모두 정상 완료하는 소요시간은 미검증이며 세부 한계는 실험 기록과 STATUS에 있다.

상속된 runtime, test, five-condition harness와 frozen archive는 존재하지만
[`D-002`](../governance/decisions/D-002-reset-research-direction.md)에 따라 새 연구의 qualification 또는 efficacy
evidence로 자동 승계되지 않는다. EP-001 smoke는 새 treatment나 metric을 검증하지 않으며 pilot,
efficacy evaluation, ablation 또는 replication이 아니다. L1-L5 이식 연구선의 후속 설계에서는
OQ-001·OQ-002를 포함한 operational research/transfer design을 명시적으로 정해야 한다.
이 문서는 그 결정을 대신하거나 해당 후속 작업을 자동 시작하지 않는다.

<a id="d-017-요청-조건-변경과-운영-검증"></a>
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

<a id="d-018-원본-fallback-운영-조건"></a>
## D-018 원본 fallback 운영 조건

[D-018](decisions/D-018-upstream-fallback.md)에 따라 `action_policy="upstream"`에 한해
C-010/C-012의 출력 terminal·후보 prompt 규칙 대신 원본 프롬프트/추출/행동 변환/재시도/fallback을
적용한다. Provider·환경·무결성 종료는 유지한다. 필드 부재는 strict다. 정상 fallback 완료는
유효하며 전체/유효 각각 실제 전송 판단과 경기 분모를 보고한다. D-017 gate는 EX-016에
적용하지 않는다. 고정 fixture·로컬2판 후32슬롯10/10을 실행하며 Cloud4시간/신규3시간45분
중지와 retry_transient=0을 봉인한다. 이전 결과와 정상 minimax/효능/최대 처리량 주장은 분리한다.


<a id="d-045-전체-cloud-기본-동시성8"></a>
## D-045 전체 Cloud 기본 동시성8

[D-045](decisions/D-045-cloud-concurrency-default8.md)의 명시적 사용자 지시를 채택한다.
새 Cloud 병렬 실행과 gate/요청 검증은 기본8을 선언하고 순차1·명시1–10을 유지한다.
새 Z.ai 준비에는 아래 D-056의 기본4 예외가 우선한다.
별도 동시성 측정의 명시적인1–10 조건은 변경하지 않는다. 기존 실행/정책 identity와 결과는 소급 변경하지 않는다.
동시성은 새로운 execution evidence에 별도로 봉인하며 보고·추정·검증은 그 값을 사용한다.
이 운영 기본값 변경은 timeout 원인의 입증이나 개선 효과의 실험 결과가 아니다.
EP-033은 비실험 구현·로컬 검증이며 기존 Blocked 재개나 추가 유료 실험을 포함하지 않는다.

<a id="d-058-새-응답-대기연결-재시도-기본값"></a>
## D-058 새 응답 대기·연결 재시도 기본값

새 요청의 전송 정책은 [C-038](CONTRACTS.md#c-038-transport-retry)을 따른다.
논리적인 모델 요청과 HTTP 시도를 별도 분모로 기록한다. 재시도는 새 경기/표본/출력 재질의가 아니다.
기존 EX의 retry0·300초 및 중단 상태는 유지한다. §11.1의 도구 결함 복구는 이번 명시적
연결 재시도보다 넓은 재시도를 허용하지 않는다. 공급자 반반 비교의 세부 설계는 미정이다.

<a id="d-060-새-공급자-오류-재시도"></a>
## D-060 새 공급자 오류 재시도

새 전송 기본값은 [C-038](CONTRACTS.md#c-038-transport-retry)의 provider-retry-v2다.
연결·timeout·5xx·429의 고정1/2/4초 최대3재시도 및 최종429 전체 중단을 채택한다.
재시도는 같은 논리 요청의 전송이며 표본·경기 추가나 출력 재추첨이 아니다.
과거 EX-042 및 모든 동결 실행의 정책·결과·Blocked는 보존한다. 새 유료 실험 승인은 아니다.

<a id="d-084-provider-재시도3회"></a>
## D-084 provider 재시도3회

사용자의 명시적 지시로 새 JEV 전송 재시도를3회로 고정한다. 기술 오류의 최종 중단은
허용 재시도 소진 뒤 적용하며 판단 오류 처리는 RD11.2를 유지한다. 재시도는 별도 배틀이나
독립 표본으로 세지 않으며 사용량·실패 분모에 포함한다. 과거 동결 실험의 중단·판정은 보존한다.
