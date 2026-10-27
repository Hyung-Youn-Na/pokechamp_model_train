# 배틀 정책 학습·개선 — 실행 계약

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="c-059-abyssal-rl-next"></a>

<a id="c-059--82라운드-계승단일-추가-주기"></a>
## C-059 — 82라운드 계승·단일 추가 주기

[D-118](decisions/D-118-abyssal-rl-next.md)/[EX-075](experiments/EX-075-abyssal-rl-next.md)의
`abyssal_rl_next`는 C-055/056/057 및 C-058의 복원·분산·슬롯·시계·알람/뷰어 경계를
유지하며 부모/실행 identity만 EX-074/EX-075로 변경한다. 지정 부모는 EX-074 local25/
전체82라운드와 정확히 일치하는 optimizer504상태·4rank RNG checkpoint여야 한다.
이전 누적2674=2164+510과 이번 추가 update를 분리하고 local1/전체83부터 기록한다.
과거 PPO buffer·최종 선택77라운드 모델을 출발 상태로 대체하지 않는다.

새 test128은 원 제외 대상과 EX-073/074 전체 split에서 격리한다. 팀/슬롯/seed를 첫 update
전에 동결하고 test는 정책/head 잠금 이후에만 생성한다. `run --resume`는 동결 EX-075 내부
identity·source·manifest·checkpoint·원 시계가 일치할 때만 허용한다. 부모 계승은 이전
실험의 재개가 아니다. source 동결 전에 문서를 완료하고 동결 중 변경하지 않는다.

C-058의 모델 비호출·영속 중복 방지 단계 알람, 정상 단계 응답 비대기, 전 경기 export와
최대12경기 오프라인 브라우저 표본 확인을 이번에도 적용한다. 전수/점진 브라우저 검사0,
원자료/독립 감사·봉인 유지다. 첫 GPU부터12시간/48GPU시간 **1회**만 실행하고 내부
재개·복구로 시계를 늘리거나 다음 주기를 자동 시작하지 않는다. 상세 protocol·완료는 EX-075다.

<a id="c-058-abyssal-rl-continue"></a>

<a id="c-058--마지막-학습-상태-계승별도-실험과-단계-알람"></a>
## C-058 — 마지막 학습 상태 계승·별도 실험과 단계 알람

[D-117](decisions/D-117-abyssal-rl-continue.md)/[EX-074](experiments/EX-074-abyssal-rl-continue.md)의
`abyssal_rl_continue`는 C-055/056 입력·행동 확률과 C-057 분산·실패 격리 경계를 유지한다.
prepare는 CPU에서 지정 부모의 identity·해시·57라운드 가중치·optimizer504상태·4rank RNG를
검증하고 새 manifest에 연결한다. EX-073 final 선택/보정 checkpoint를 부모로 대체하지 않는다.
초기 계승은 가중치/optimizer/RNG와 train 순환만 이어받고 과거 PPO buffer를 재사용하지 않는다.
local/global round와 추가/기존 누적 update를 별도 기록한다. 새 test·모든 슬롯/seed는 update
이전에 동결한다. test는 완전 dev 기반 정책/head 잠금 이후에만 생성한다.

prepare/verify/run/status/finalize를 제공하며 `run --resume`는 이번 experiment identity·
source·manifest·checkpoint·원 시계가 일치하는 EX-074 내부 재개만 허용한다.
이번 최초 GPU 검사 시계와 절대 마감은 복구/재개에 불변이다. 단계 receipt와 전달 원장은
영속 저장하고 모델 비호출 감지기는 승인된 사건만 대화에 전달한다. 종료/마감은 중복 병합하며
알람 응답을 기다리는 단계 gate를 만들지 않는다. 전체 rank 장애 정지·소유 자원 정리를 유지한다.

C-047의 전 경기 export·원자료 연결·봉인은 유지하되 EX-074의 브라우저 확인만 명시적
표본 예외를 적용한다. 전수/점진 전수 브라우저 검사는 실행하지 않고 단계별 슬롯 ID 첫/마지막,
최대12경기만 확인한다. 원자료 연결 감사와 독립 통계는 생략하지 않는다.
예산·수치 기준·분모·완료 조건은 EX-074를 따르며 EX-073의 동결 자료와 당시 판정은 보존한다.

<a id="c-057-abyssal-rl"></a>

<a id="c-057--abyssal-전용-동기-4gpu-정책-학습"></a>
## C-057 — Abyssal 전용 동기 4GPU 정책 학습

D-116/EX-073의 별도 abyssal_rl 경로는 C-055 입력/명령·C-056 선택 행동 확률 의미를 유지한다.
GPU0–3 전체 공용 lock/UUID 확보, 동결 복제본당 직렬 추론·2동시 배틀, 전 요청 종료 후
snapshot 동일성 확인을 강제한다. 학습은 전역 RL16/BC4의 실제 표본 평균 손실에 대한
FP32 경사 NCCL SUM과 같은 step, 전역 KL의 같은 종료 결정을 적용한다.
rank·snapshot·global_update·slot 소유권을 기록하고 원자 슬롯 예약으로 재경기를 금지한다.
checkpoint는 완료 step의 모든 rank RNG·optimizer·cursor·동결 buffer·원 시계가 한 묶음이다.
한 rank 장애는 전 worker 종료, 부분 rank 계속 실행0. test는 완료 dev 기반 정책/head 잠금 후만
허용하며 불완전·실패를 W/D/L로 변환하지 않는다. 상세 허용오차·예산·완료 기준은 EX-073이다.
기존 EX-072/066 설정·실행·자료를 덮어쓰지 않는다.

<a id="c-056-selfplay"></a>

<a id="c-056--자기대국-정책선택-행동-승무패-확률"></a>
## C-056 — 자기대국 정책·선택 행동 승무패 확률

D-114/EX-072의 별도 selfplay 경로는 C-055의 입력/정보/명령 경계를 재사용한다.
모든 모델 선택은 temperature1 categorical sampling이며 greedy 규칙은 적용하지 않는다.
행동 ID·정책 확률·행동별 W/D/L 확률은 별도 필드다. WDL은 실제 선택 행동의 정상 결과에만
학습하며 미선택 행동 결과/반사실적 정확성을 주장하지 않는다. 같은 forward 표현·dropout0·
BF16 base/FP32 LoRA·두 head를 사용한다. 수집 당시 전체 log probability·WDL·baseline·
후보 순서·모델/RNG·입력 해시와 실제 전송을 보존한다. 자동 선택은 학습에서 제외한다.
상대 snapshot은 동결하며 PPO 재계산에서 입력/순서를 바꾸지 않는다. 실패를 결과로 바꾸거나
대체/재질의/재경기하지 않는다. 최초 절대 기한과 완료 step을 원자적으로 보존하고 재개로
시계를 새로 만들지 않는다. 상세 gate·분할·시간·학습·복구·분모는 EX-072가 소유한다.

<a id="c-055-imitation"></a>

<a id="c-055--리플레이-모방-학습-입력choice-정책"></a>
## C-055 — 리플레이 모방 학습 입력·Choice 정책

D-113/EX-071의 `pokemon-imitation-input-v1`은 기존 q 계약과 별도다. 모델 전용 immutable
입력은 현재 상태·복원한 아군 원래 세트·현재 공개 상대 정보·필드·직전4턴/현재 턴 공개 이력과
후보만 포함한다. 관점/결정 위치는 감사 metadata에 보존하며 모델 입력에는 선수 이름·승패·
미래 공개 상대 정보·같은 턴 미공개 선택·라벨·seed·추정 출처를 넣지 않는다.
미래 자기 공개는 원래 자기 세트 복원에만 사용하고 도구 교환·호출 기술 등 동적 정보와 구별한다.
현재 상태는 결정 직전 prefix만으로 만들며 offline/live가 같은 직렬화 함수를 사용한다.

출력은 Kev Choice 질문1개다. criteria는 행동 ID와 설명, 타깃은 관측된 실제 선택 ID다.
기술 ID는 기술명과 Tera 여부, 선봉/교체 ID는 자기 팀의 고정 슬롯으로 구분한다.
슬롯은 실전 request의 명령 슬롯과 명시적으로 매핑하고 후보·라벨/셔플 정합성을 검증한다.
확률은 후보 전체의 정규화된 **행동 선택 확률**이며 승률/q가 아니다. 실제 선택에만 CE를
적용하고 미선택을 승률0으로 만들지 않는다. unknown 선택은 mask, 자동 행동은 새 선택이 아니다.

Base BF16, LoRA/head/loss FP32와 BF16 forward의 동일 unmerged 경로로 학습·평가·서빙한다.
상태 최대8,192토큰을 절단하지 않으며 준비 초과 표본은 사유와 함께 제외한다. 후보/질문을
붙인 전체 readout도 절단하지 않는다. live 초과/불량 응답은
무전송·해당 경기 실패, 공유 생성기 결함은 의존 단계 중단이다. 후보1개는 추론 없이 제출한다.
최대 확률을 선택하고 동률은 고정 후보 순서로 처리한다. 전송 직전 rqid·합법 후보를 다시 확인하며
stale/실행 불가능/기한 초과는 무전송, 재질의·대체0이다. 원 입력·확률·선택·명령·지연·분모와
provenance를 보존한다. 데이터/학습·재개·평가 잠금·시간·회복 한도는 EX-071을 따른다.

이 contract는 상속된 implementation이 남아 있는 동안 그것을 보호하고 설명한다. 원저자의
연구 목표, roadmap 또는 experiment backlog를 채택하지 않는다. 새로 승인된 연구 방향은
[`Decision`](../../DECISIONS.md)과 명시적인 contract 수정으로 변경을 제안할 수 있다.
