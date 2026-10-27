# EX-066 — Qwen3.5-4B-Base 공동 q 학습·독립 평가

- 상태: Blocked — 새 프로세스 재로딩 gate 실패
- 등록일: 2026-09-30
- 책임자: Codex
- 승인: 현재 사용자 제공 학습 계획 / D-104·D-105·D-106 / EP-108

## 질문과 모집단

EX-065의 전체 후보 q를 관측 동일가중 MSE로 학습했을 때 팀 단위 독립 test의 q 예측과
최고 후보 선택이 초기 모델·상수 기준선보다 개선되는지 탐색한다. 사전 효능 향상을 전제하지 않는다.
표본 보상 bandit RLCD와 구분하는 full-information MSE/soft-target Brier 학습이다.
q는 고정 자기 팀·실제 숨은 상태·양측 Abyssal 후속 정책 조건부 terminal score다.
독립 배틀 승률·최적 정책·일반 Gen9 OU 효능은 이번 평가로 판단하지 않는다.

데이터는 `/mnt/digicap/combined/hyna/backup/pokechamp/`의 검증된 EX-065 복사본이다.
팀·seed·split 이동/관측 제외0, 같은 split 의미 중복도 원대로 유지한다.

| split | 경기 | 관측 | 후보 |
|---|---:|---:|---:|
| train | 50 | 1639 | 15114 |
| validation | 10 | 320 | 2991 |
| test | 20 | 709 | 6369 |

## 동결 모델·입력·학습 조건

초기 모델 `Qwen/Qwen3.5-4B-Base`, revision `1001bb4d826a52d1f399e183466143f4da7b741b`.
EVE `.venv-eve-rlcd`, 물리 GPU1 A6000 48GB 한 장, 시간 상한 없음·최대3epoch.
D-105로 GPU2를 지정한 뒤 사용 중이면 다른 유휴 GPU를 쓰라는 D-106의 사용자 후속 지시를
적용했다. GPU2가 사용 중이고 GPU1이 유휴임을 확인하여 학습 전에 GPU1로 고정했다.
이전 동결 protocol·준비본·사전검사·CPU 중단 증거를 보존하며 나머지 조건은 유지한다.
공식 text backbone과 기존 어휘만 사용한다. 새 LoRA r8/alpha16/dropout0, 모든 text Linear 모듈,
공유 Linear(2560,1)＋sigmoid, head weight std `0.01/sqrt(2560)`, bias0.
frozen base BF16, LoRA/head FP32, forward BF16, readout/손실 FP32.
AdamW lr5e-5/betas(0.9,0.95)/weight_decay0/clip1, microbatch1/accumulation8.
마지막 배치는 실제 관측 수로 평균한다. epoch당205·총615 optimizer update.
seed20260930, gradient checkpointing, use_cache=False.

JointInput만 입력 경계로 허용한다. 전체 상태/후보를 한 번 렌더링한 다음 후보 순서대로
`ACTION_ID=<JSON ID>\nQ_VALUE=` readout을 추가하고 각 마지막 `=` hidden state를 ID로 연결한다.
후보별 독립 sigmoid이며 후보 간 softmax0. 새 renderer 버전과 Base tokenizer를 사용하고
공식 chat template의 enable_thinking=False, 무절단32768토큰 한도를 적용한다.
기존 EX-065 tokenizer cache는 재사용하지 않는다. train 관측/후보를 epoch별 결정적으로
섞고 ID로 입력/타깃을 함께 재정렬한다. validation/test는 원후보 순서다.

## 사전 검사·모델 선택·test 잠금

Base 파일 SHA-256과 실제 text tensor를 검증한다. train/validation 원입력과3epoch 셔플 입력의
길이·readout/후보 ID·타깃을 전수 검사한다. test는 설정 선택에 사용하지 않는다.
최장 train 및 최소/최대 후보 사례의 GPU forward/backward를 수행하고 유한 손실/경사,
base 불변/업데이트0·VRAM·시간·전체 소요 추정을 기록한다.
필수 사례는 타깃/private 변경 시 토큰 불변, padding 무영향, 단일/13후보, 동률/전q0/1,
길이 경계, 학습 후 base 불변/LoRA·head 변경이다.

초기 상태와 epoch별 체크포인트·validation 전체 q를 보존한다. 학습 checkpoint 중 validation
관측 평균 MSE 최소를 선택하며 정확한 동률이면 이른 epoch다. 새 프로세스로 재로딩하여
validation 전체 q 최대차이≤1e-4를 확인하고 후보 순서 반전의 q 민감도를 validation에서 진단한다.
그 뒤 source/config/data/tokenizer/선택 checkpoint를 잠근 후 test를 초기/선택 모델별1회 평가한다.
상수 기준선은 추가 모델 호출 없이 저장 예측의 동일 관측/후보에 적용한다.
test를 보고 prompt·설정·checkpoint 선택을 변경하지 않는다.

## 동결 지표와 분석

주지표는 관측별 후보 MSE의 관측 평균이다. 보조지표는 동일 방식 MAE,
soft-target Brier=2*MSE, regret=max(target q)-target q[argmax(pred q)],
동률 허용 최고 후보 선택률이다. 예측 동률은 원후보 첫 ID다.
기준선은 초기 모델/동일 초기 head, 상수0.5, train 관측별 평균 q를 다시 관측 평균한 상수다.
전체와 `max(target q)>min(target q)`인 선택력 관측을 각각 보고한다.
경기/상대팀별 지표, 의미 fingerprint의 첫 관측만 남긴 중복 민감도와 fingerprint별 동일가중
결과를 함께 보고한다. 비교는 동일 저장 test 예측에서 수행한다.
paired cluster bootstrap은5개 test 팀 그룹을 복원추출하고 선택된 그룹의 모든 관측을 포함하여
관측 평균 차이(선택-기준선)를 계산한다. seed20260930/10000반복/percentile95% CI,
전체·선택력 분모를 보고하고 그룹5개라는 불확실성 한계를 명시한다.

## 보존·중단·복구

산출물 루트 `.pokechamp-data/experiments/ex066-joint-q-training/`.
각 checkpoint는 LoRA와 별도 value head, optimizer/RNG/다음 관측 cursor, base/tokenizer revision,
renderer/data/source 해시를 포함한다. 매 완전 optimizer update를 원자적 보존하며 epoch/초기
checkpoint는 별도로 유지한다. 소유 GPU lock을 사용하고 다른 프로세스를 중단하지 않는다.
원 EX-065 자료·기존 가중치·과거 봉인은 읽기 전용이다. 재현 명령·비용·실패 원문·봉인 목록을 남긴다.

RD11.1/C-018 공통 복구를 적용한다. 길이 초과·OOM·입력 누출·비유한 경사는 의존 실행 중지와
증거 보존을 요구하며 절단/관측 제외로 통과시키지 않는다. 처리 설정 변경은 현재 protocol의
자동 복구 범위 밖이다. 일시 기술 중단은 같은 source/config와 마지막 완전 optimizer
checkpoint의 RNG/순서에서 재개한다. 실패 부분 update는 원자료와 연결하여 보존한다.
평가 집계 결함은 저장 예측에서 전조건 재분석하며 test forward 재수집0.
실제 입력/처치 결함은 영향 실행 무효·의존 중지이며 자동 재학습0.
신규 배틀/provider 호출이 없어 RD11.2/C-046 판단 오류와 C-047 viewer는 해당 없음.

## 완료 기준과 결과

선택 checkpoint·관측별 예측·모든 필수 검증·지표/비용 보고·재실행 명령·봉인·자원 정리가
완료되면 개선 여부에 관계없이 Completed다. 2026-10-03에3epoch·615update 학습과 각 epoch의
validation 평가를 마쳤고, validation MSE 최소인 epoch3를 선택했다. 초기 MSE는
0.1915002450342827, 선택 모델은0.1690228678246149이며 최고 후보 선택률은
53.4375%에서54.0625%로 변했다. 이는 validation320관측/2,991후보의 결과다.
새 프로세스 재로딩의 validation q 최대차이0.0018912255764007568이 허용 기준1e-4를
초과하여 의존 실행을 중지했다. test 잠금·예측·평가 결과는 없고 최종 보고·봉인도 미완료다.
원 학습/재로딩 증거와 체크포인트는 보존하며 Blocked를 유지한다. 기존 CPU 회귀는 통과했고 최초 검사 실행기의
환경/cwd 오류는 실제 실행에 영향 없이 교정하고 원문을 보존했다.
증거는 [검사 기록](../../../../.pokechamp-data/experiments/ex066-joint-q-training/verification/tests.json),
학습 결과는 [선택 기록](../../../../.pokechamp-data/experiments/ex066-joint-q-training/training/selection.json),
[epoch3 validation](../../../../.pokechamp-data/experiments/ex066-joint-q-training/training/metrics-epoch3.json),
중단 근거는 [STOP](../../../../.pokechamp-data/experiments/ex066-joint-q-training/STOP.json)을 따른다.

## 사전검사 구현 결함과 교정

최초 GPU preflight의 text426tensor/세 경계 사례 이후 token-padding q 차이 검사가 실패했다.
학습/test0이며 독립 GPU 재현에서17개 오른쪽 padding의 최대 q 차이0.00015920400619506836,
동일 무패딩 반복 차이0이었다. 원본은 `versions/preflight-v1/`와
[독립 재현](../../../../.pokechamp-data/experiments/ex066-joint-q-training/diagnostics/padding-v1.json)에 보존한다.
microbatch1의 유효 prefix 전체를 유지하고 마스크된 padding만 backbone 앞에서 제거하는
입력 정규화를 교정했다. 모델/renderer/tokenizer/학습/지표/기준은 변경하지 않는다.
source는 별도 버전이며 회귀 검사·동일 cache/hash·원 무패딩 q 불변의 독립 GPU 증거가
있는 recovery receipt로 이 preflight만 재검사한다. 최초 시계/원 STOP/실패 비용은 유지하고
다른 중단이나 학습/test 재수집을 허용하지 않는다. RD11.1/C-018의 도구 경계 교정이다.

D-105 지시 시 진행 중인 CPU 재준비는 학습/test0에서 중단했다.
`versions/prepare-gpu1-interrupted/`에 source·부분 준비·STOP을 보존하고 최초 시계는 유지한다.
recovery receipt는 GPU1→2만 승인 원문 해시로 허용하고, 모든 token/cache·원자료·학습 조건
동일성과 독립 padding 증거를 요구한다. 원 padding STOP과 이 CPU 준비 중단만 연결한다.

GPU2 준비 완료 시 다른 프로세스가 GPU2를 사용 중이었다. D-106의 명시적 유휴 GPU 대체
지시로 GPU1을 선택하고 `versions/prepared-gpu2/`에 완전 준비본·source·protocol을 보존했다.
GPU2 모델 호출/학습/test0이며 최초 시계는 유지한다. 새 receipt는 D-106 승인 해시와
원자료·token/cache·GPU 이외 조건 불변을 대조한 뒤 사전검사만 재진입한다.

## 유한한 0 경사 검증 경계 교정

초기 validation 단계에서 optimizer update0일 때 독립 CPU 사례로 검증기의 잘못된 조건을
발견했다. 예측/타깃이 모두0 또는1인 포화 sigmoid는 MSE0·유한한0경사를 갖는데 기존 검사는
전체 경사 norm0을 오류로 처리했다. 이는 비유한 경사 중단 기준에 포함되지 않는 정상 값이다.
원 source·준비·사전검사·중단·초기 checkpoint 증거를 `versions/zero-gradient-v1/`에 보존했다.
checkpoint를 유지한 채 기술 중단하고 해당 거부 조건만 제거한다. 누락/NaN/Inf 경사는 계속
중지한다. 모델/renderer·입력·타깃·loss/optimizer 수치 연산·설정은 변경하지 않는다.

전q0/1의 MSE0·0경사와 누락/비유한 거부의 독립 회귀를 검증하고, 실제 runtime 변경이 해당
거부2행 제거뿐인지 source로 대조한다. 실행기가 지원하는 guard-only re-freeze receipt는
원 token/data/Base 해시·설정/환경 불변과 latest initial cursor update0을 요구한다. 새 GPU
preflight 통과 뒤 동일 초기 checkpoint·optimizer/RNG에서 재개한다. 초기 validation 반복
계산의 비용은 누적하며 학습/test 재수집0, 최초 시계·다른 STOP의 gate는 유지한다.

## 2026-10-03 자원·오류 보존 확인

EX-073 준비 중 확인한 원 [reload.log](../../../../.pokechamp-data/experiments/ex066-joint-q-training/reload.log)는
재로딩 q 최대차이0.0018912255764007568 >1e-4로 중단했다. 현재 GPU 점유0이며 원 가중치·
자료·오류를 보존한다. 이번 확인은 EX-066 복구·재개·독립 test 실행이나 완료 판정이 아니다.

## 별도 후속 배틀 평가

2026-10-08 [EX-081](EX-081-joint-q-battle.md)은 이 epoch3를 변경 없이 GPU0에서 읽어
두 새 프로세스의 원 validation 전수 q 최대차이0을 확인하고 실제20경기를 완료했다(0승20패).
과거 GPU1 단일 관측 불일치 원인은 미확정이며 원 STOP·판정·가중치/자료는 유지한다.
이 후속 결과는 원 EX066의 오프라인 test·최종 보고/봉인 완료를 뜻하지 않는다.
