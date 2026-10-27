# 배틀 정책 학습·개선 — 구성 설명

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="d-113-ex-071-리플레이-모방-학습-경로"></a>
## D-113 EX-071 리플레이 모방 학습 경로

`integration/pokechamp/imitation/`은 기존 q 학습·서빙과 독립된 Choice 정책 경로다.
`dataset`이 원본·역사 평가팀 제외·연결 그룹 분할·보완 통계·새 대진을 동결하고,
`metamon_bridge`가 별도 Python3.11 CPU 환경의 pinned parser와 JSONL로 통신한다.
`impute`는 공개된 원래 세트와 일치하는 합법 corpus 세트를 결정적으로 보완한다.
`replay`의 결정 직전 prefix와 공식 실배틀 관측은 같은 `schema.from_snapshot`을 거쳐
`pokemon-imitation-input-v1`이 된다. 정답·승패·이름·출처는 감사 영역에만 보존한다.

`model`은 고정 Kev Choice readout과 새 LoRA/head의 unmerged 정밀도를 공유하며,
`learning`은 최초 시계·업데이트 예산·부분 경사를 포함한 재개·validation 선택·test 잠금을
담당한다. `serving`과 `player`는 저장 확률의 HTTP 대조, 안정된 행동 ID와 실제 명령 슬롯,
전송 직전 rqid/합법 후보 확인으로 이어진다. `battle`이 소유 Showdown/actor/서버의
고정40 slot을 관리하고 `reporting`·`viewer`가 전체 분모와 행동 선택 확률을 표시한다.
`verification`은 CPU 의존성과 실제 validator/Dex 소스·검사 증거를 GPU gate에 묶는다.
진입점은 `scripts/pokechamp-imitation`이며 구현/운영 안내는
[imitation README](../../../integration/pokechamp/imitation/README.md), 실제 검증·실행 상태는
[EP-115](plans/EP-115-qwen-replay-imitation.md)를 따른다. 첫 학습·잠긴 test·
40경기와 오프라인 뷰어까지 완료했으며 실행 소스와 실제 산출물은 해당 완료 기록에 연결한다.

<a id="d-114-ex-072-자기대국확률-보정-경로"></a>
## D-114 EX-072 자기대국·확률 보정 경로

`integration/pokechamp/selfplay/`은 EX-071의 입력·후보/명령 경계와 BF16/FP32 정밀도를
재사용하는 별도 학습 경로다. `prepare`가 제외 구성·새 팀 split·BC와 전체 대진/seed를 동결한다.
`model`의 한 backbone forward가 행동 정책과 W/D/L head를 계산하며 `serving`은 동결 snapshot을
순차 교환하여 temperature1 categorical 선택과 원 분포를 반환한다. `player`/`battle`은
소유 Showdown·두 actor의 전송 증거와 정상 종료를 독립 감사하고 지정 learner의 결정만 연결한다.

`trainer`는 라운드별 새 rollout의 PPO/WDL과 EX-071 train BC를 별도 평균한다. 정책 선택 뒤에는
동결한 표현으로 WDL head만 보정한다. `runner`는 후보 dev·head 채택·잠긴 test까지의 상태를,
`execution`은 UUID 고정 GPU·최초 시계·원자적 완료 step checkpoint·SIGTERM 재개와 정리를 관리한다.
`reporting`은 경기/상대 가중 확률 지표와 팀쌍 bootstrap을 계산하고 `finalize`/`viewer`는
원자료·필수 검증·이동 후 오프라인 재생 gate를 통과한 산출물을 봉인한다.
진입점은 `scripts/pokechamp-selfplay`, 운영 안내는 [selfplay README](../../../integration/pokechamp/selfplay/README.md)다.
조건은 [EX-072](experiments/EX-072-selfplay-rlcd.md), runtime은 [C-056](CONTRACTS.md#c-056-selfplay),
실제 진행과 검증은 [EP-116](plans/EP-116-selfplay-rlcd.md)이 소유한다.

EX-072의 동결 최종화에서 브라우저 의존성 누락과 JavaScript 큰 정수 직렬화 문제가 발견되어,
[EP-117](plans/EP-117-selfplay-finalization-recovery.md)의 별도 CPU 정정 경로를 사용한다.
`scripts/pokechamp-selfplay-finalization-v3.py`는 원 봉인·시계·통계와 실제 검증 증거를 확인하고,
`scripts/selfplay_viewer_exact_json.py`는 새 export의 원문 패널·복사·다운로드만 정확한 Python JSON
문자열로 교정한다. 원 검증기는 그대로 사용하고 원 자료·source freeze·실패한 최종본은 보존한다.
정정 산출물의 상태는 `corrections/latest.json`이 연결하며 원 `completed.json`의 당시 판정을 덮어쓰지 않는다.

<a id="d-116-ex-073-abyssal-전용-동기-4gpu-경로"></a>
## D-116 EX-073 Abyssal 전용 동기 4GPU 경로

`integration/pokechamp/abyssal_rl/`은 EX-072 원본을 보존한 별도 실행기다. prepare가
EX-071/072 및 원 replay 구성을 제외한 split·가능 슬롯·원 BC를 동결한다. rank별 직렬 HTTP
서빙과2동시 배틀을 동기 수집하고, 전역 RL16/BC4의 FP32 gradient SUM·공동 KL로 학습한다.
입력/모델/원자료 감사는 검증된 selfplay/imitation 기능을 재사용한다. checkpoint는 rank별
난수·완료 cursor·optimizer·동결 buffer·최초 시계를 보존한다. 정책/head 잠금 뒤 대응 test만
허용하며 독립 재집계·정확한 JSON/C-047 뷰어 검증은 별도 CPU 경로다.
진입점은 `scripts/pokechamp-abyssal-rl`, 조건 원문은 [EX-073](experiments/EX-073-abyssal-rl.md),
검증·현재 실행 상태는 [EP-119](plans/EP-119-abyssal-rl.md)를 따른다.


<a id="d-117-ex-074-계승-경로"></a>
## D-117 EX-074 계승 경로

승인된 새 경로는 `integration/pokechamp/abyssal_rl_continue/`이며 EX-073 실행기·동결
artifact를 보존한다. CPU 준비에서 부모 checkpoint 출처·가중치/optimizer/RNG와 새 split·
슬롯을 연결하고 실행기가 새 시계·추가 라운드·단계 receipt를 소유한다. 독립 감지기는
모델을 호출하지 않고 receipt/프로세스 상태와 영속 전달 원장을 사용한다.
별도 최종화는 모든 정상 경기 export와 단계별 표본 브라우저 확인을 담당한다.
이 경로의 실행·검증·최종화는 완료했으며 기존 동결 실행은 재개하지 않는다. 확정 조건은
[EX-074](experiments/EX-074-abyssal-rl-continue.md), runtime은
[C-058](CONTRACTS.md#c-058-abyssal-rl-continue), 구현·검증 상태는
[EP-121](plans/EP-121-abyssal-rl-continue.md)이 소유한다.


<a id="d-118-ex-075-계승-경로"></a>
## D-118 EX-075 계승 경로

새 `integration/pokechamp/abyssal_rl_next/`는 EX-074 local25/전체82의 학습 checkpoint를
CPU 출처 검증 후 별도 실행으로 가져온다. 가중치/optimizer/RNG와 train 순환을 이어받고
새 test·경기 seed·슬롯·시계를 동결한다. 추가 update와 기존 누적 이력은 별도 기록한다.
prepare/verify/run/status/finalize와 EX-075 내부 재개, 영속 단계 알람과 전 경기 export/
표본 브라우저 확인을 구현하고 CPU 통합 검증을 통과했다. GPU 검증과 실제 실행은 별도 receipt로 판단한다. 단일12시간 주기 뒤
후속 실행을 자동 시작하지 않는다. 조건은 [EX-075](experiments/EX-075-abyssal-rl-next.md),
runtime은 [C-059](CONTRACTS.md#c-059-abyssal-rl-next), 구현·검증 증거는
[EP-122](plans/EP-122-abyssal-rl-next.md)를 따른다.
