# EX-071 — Qwen 4B 리플레이 모방 학습과 첫 배틀 평가

- 상태: Completed
- 등록일: 2026-10-01
- 완료일: 2026-10-02
- 승인: 현재 사용자 제공 실행 계획 / [D-113](../decisions/D-113-qwen-replay-imitation.md)
- 실행: [EP-115](../exec-plans/completed/EP-115-qwen-replay-imitation.md)
- 계약: [C-055](../CONTRACTS.md#c-055-imitation)
- 산출물: `.pokechamp-data/experiments/ex071-qwen-replay-imitation/`

## 질문·처치·해석

기존 리플레이의 관측된 선택을 모방한 새 Qwen3.5-4B 정책이 동일 초기 모델 대비 인간 선택
재현과 독립 실배틀에서 어떤 차이를 보이는가? 방향성 향상을 전제하지 않는 첫 탐색 평가다.
행동 선택 확률·NLL·일치율을 승률/q와 구분한다. 초기·선택 모델의 같은 입력/정밀도/대진 비교이며
기존 Kev/q의 성적이나 L1-L5 전체 효과와 동일시하지 않는다. 자기대국은 수행하지 않는다.

## 데이터·복원·분할 동결 조건

- 출발 목록은 EP-100의 `exports/replay-eligibility/gen9ou-local-v1/candidate-reviewed108.txt`
  2,793경기다. 승패/rating으로 추가 선별하지 않고 양측 관측 가능한 선택을 쓴다.
- Metamon revision `0a00a759c9a4382a2877088d828302ec294a05a5`의 replay parser를 별도 CPU
  환경에서 사용한다. 로컬 gzip 원본·결정 로그 위치 어댑터를 추가하며 LLM으로 자료를 만들지 않는다.
- 기존 검토108종 팀 corpus에서 공개된 원래 기술·도구·특성·Tera와 일치하고 현재 규칙상 합법인
  세트를 출현 빈도로 가중하여 고정 해시로 하나 선택한다. 같은 경기/관점 내에서 유지하고
  확인/추정·출처를 감사 metadata에 저장한다. 일치하는 세트가 없으면 해당 관점을 제외한다.
- 기존 평가팀의 동일6종 구성은 리플레이와 보완 통계에서 제외한다. 양측 관점·동일 경기/중복과
  동일6종 팀 공유를 연결 성분으로 묶고, 그룹 크기 내림차순·seed `20261001`로 약80/10/10을
  나눈다. 다음 그룹은 목표 크기 대비 현재 채움 비율이 최소인 split으로, 동률은 고정 해시로
  배정한다. 실제 비율·최대 그룹·제외/마스킹 분모를 보고한다.
- 선봉·기술·자발/강제/피벗 후 교체·Tera를 구분한다. 마비·풀죽음·행동 전 기절 등 미공개 선택은
  mask하고, Sleep Talk 등 호출/자동 행동을 새 선택으로 만들지 않는다. 미지원 사례는 격리한다.
- C-055의 동일 offline/live serializer를 사용한다. 현재 상태·아군 세트·상대 공개 정보·필드·
  직전4턴과 현재 턴의 공개 이력·후보를 포함한다. 최대8,192토큰; 초과는 절단 없이 제외·집계한다.
- validation 최대512, test 최대1,024를 그룹별 순환과 고정 해시로 미리 정한다. 후보1개와
  mask는 감사 자료에 유지하되 학습·선택 평가 분모에서 분리한다. 평가팀/seed는 학습 전에 동결한다.

## 모델·학습·자원 동결 조건

| 항목 | 값 |
|---|---|
| Base | `Qwen/Qwen3.5-4B-Base` revision `1001bb4d826a52d1f399e183466143f4da7b741b` |
| 구조 | 고정 Kev Choice readout, 새 LoRA·새 pointer head, 기존 학습 가중치 사용0 |
| LoRA | r16, alpha32, dropout0.05, Kev `all` target modules |
| 정밀도 | frozen Base BF16, LoRA/head/loss FP32, forward BF16; train/eval/serve 동일 unmerged |
| 목적/최적화 | 실제 선택의 관측 평균 CE, AdamW lr5e-5 betas(.9,.999) wd.01, clip1 |
| 배치 | microbatch1, accumulation16, gradient checkpointing |
| 증강 | 후보 순서와 정답 ID 함께 셔플; fake/removal/none 증강0 |
| 학습 상한 | 최대3epoch, GPU preflight·학습·validation 합계 최초 시계부터24시간 |
| GPU | 실행 직전 유휴3→2→0 순으로1장 고정; 기존 GPU1 작업 보존 |

train의 길이·후보 수·결정 종류를 대표하는 최대32개로 업데이트0 forward/backward를 수행한다.
p95 처리시간×1.2와 accumulation16으로 최대 업데이트를 계산한다. 남은24시간에서4시간을
validation·저장에 남기고3epoch 상한과 작은 값을 학습 전에 고정한다. update 수가0이면
예산 내 학습 불가로 보고하고 임의로 예산/설정을 확대하지 않는다. 첫10% warmup 후 cosine.

초기와 예정 update25/50/75/100% 지점(ceil, 중복 제거)에 checkpoint를 저장한다. 고정 validation
최대512의 NLL이 가장 낮은 학습 checkpoint를 선택하며 동률은 이른 checkpoint다.
15분마다 LoRA/head/optimizer/scheduler/Python·NumPy·Torch·CUDA RNG/데이터 위치/누적 시간과
hash를 원자 저장한다. 중간 accumulation이 있으면 경사 또는 재현 가능한 완전 경계를 저장한다.
재개는 같은 설정/원자료/초기 시계에서만 허용한다. Base 불변·trainable 갱신·유한 수치를 검증한다.

## 오프라인 평가

모델 선택·설정을 잠그고 초기/선택 모델을 같은 고정 test에서 각1회 평가한다.
전체·결정 종류·Tera 소모 전후별 NLL/일치율과 평가 분모를 보고한다. 저장 예측의 분석은
재호출이 아니며 추정 정보 비율·복원 실패·제외·중복·단일 후보 분모도 보고한다.
checkpoint 재로딩 및 serving 저장 표본의 확률 대조를 통과해야 진입한다.

## 실배틀 평가

기존 reviewed108 후보 목록에서 모든 출발 리플레이 및 기존 평가팀과 다른6종 구성의 합법 팀
10개를 고정 해시 순서로 골라5대진을 만든다. 동일 구성을 중복 선택하지 않는다.
팀·진영·simulator/상대 seed와 순서를 학습 전에 동결한다.

- 초기/선택 모델 ×5대진 ×진영 교환 ×상대2종(Abyssal, `abyssal-tera-v1`) =40경기.
- 평가 전체 최초 시계부터6시간, 경기당1,200초·500턴; 종료/정리에 필요한 시간도 보존한다.
- 시간/턴 제한은 미완료이며 패배/무승부로 바꾸지 않는다. 추가/재경기·재질의·fallback0.
- 후보1개는 모델 호출 없이 유일한 합법 행동 제출. 전송 직전 rqid·합법 후보를 재확인한다.
- 승/무/패·정상 완료율·평균점수 `(승+0.5무)/정상 종료`·전후 차이·추론 지연을 보고한다.
- 같은 팀 대진을 block으로 묶어 양 모델이 정상 종료한 대응 slot의 차이를 계산한다.
  대진 block을10,000회 복원 추출(seed20261001)하여 percentile95% CI를 산출한다.
  대응 누락과 실제 block/slot 분모를 밝히고, 정상 경기별 평균차와 대응 차이를 구분한다.
  작은 첫 평가의 한계와 개선 불확실성을 그대로 보고한다.

## 필수 검증·중단·복구

미래 상대 정보/같은 턴 미공개 선택·승패·이름/metadata 변형의 과거 입력 불변, Tera 소모,
피벗/강제 교체의 중간 경계, 호출 기술·도구 교환·mask를 원문 사례로 검사한다.
분할 간 경기/팀 그룹·후보/라벨 및 순서변경 매핑을 전수 확인한다. 저장/재로딩·재개,
Base 불변/LoRA·head 변화·유한 손실/경사와 같은 unmerged 서빙 확률을 검증한다.

RD11.1/C-018의 증거 보존→영향 단계 중지→재현→수정/독립 검증을 적용한다.
CPU 자료 준비/감사 오류는 원본을 보존한 새 버전으로 교정하고 학습 전에 다시 동결할 수 있다.
학습 중 기술 중단은 입력/처치/수치 경로 불변과 완전 checkpoint로 재개 가능한 경우에만
같은24시간 시계에서 복구한다. 실제 입력/처치가 바뀌는 재학습과 test/배틀 재수집은0이다.
공유 입력·수집/정밀도/무결성 결함은 영향을 받는 단계 및 의존 결과를 중지한다.
RD11.2/C-046에 따라 합법적인 나쁜 선택은 계속 실행하고 실행 불가능 응답은 해당 경기 격리다.
모든 실패/무효/미완료/미실행 분모·원본/정정 연결을 보존하고 gate를 완화하지 않는다.

## 산출물·현재 결과

재현 dataset/manifest/hash, 초기·중간·선택/재개 checkpoint, 시간·학습량·메모리,
잠긴 test 예측·40 slot 전체 원장, 한국어 보고와 C-047 행동 선택 확률 뷰어를 제공한다.
완료는 첫 학습·정해진 평가·보고 수행이며 성능 향상과 별도다. 결과를 보고 자동으로
추가 학습/탐색을 시작하지 않는다. CPU 자료·전수 감사, GPU3의 첫 학습·validation 선택,
잠긴 test 각1회·고정40경기와 보고·오프라인 뷰어·소유 자원 정리를 완료했다.
학습 후 원 제어 종료 증거와 독립 감사를 보존하고 미시도 후속 단계만 같은 조건으로 이어갔다.
[최종 결과와 해석](#final-results), [통합 보고](../../.pokechamp-data/experiments/ex071-qwen-replay-imitation/final/report.md),
[40경기 뷰어](../../exports/battle_viewers/ex071/index.html)를 제공한다.

### CPU v1 보존과 교정

전체 복원 v1의 구조·분할·후보 전수 감사는 통과했으나, 실패104경기를 조사하여 공개
battle-only forme 재등장의 원래 슬롯 연결 결함을 확인했다. Ogerpon-Wellspring-Tera55,
Ogerpon-Teal-Tera46, Mimikyu-Busted3이며 같은 Timeline이 live에도 적용된다.
동결 평가팀에도 Ogerpon-Wellspring이 있어 v1은 GPU 진입 자격이 없다.
폼 변경 후 Embody Aspect를 원래 특성으로 수집한 보완 경계도 함께 교정한다.

원본·v1 데이터/소스/구조 감사와 제외 분모는 산출물 `versions/recovery-v1/archive.json`에
해시·이전/새 위치 연결과 함께 보존했다. 원인 재현은 `diagnostics/recovery-forme-v1.json`이다.
CPU v2는 알려진 공개 battle-only forme의 원래 슬롯과 원래/변경 특성 구분만 교정하며,
원본 목록·연결 분할·corpus·평가팀/seed·입력 필드·모델/학습 조건은 유지한다.
당시 GPU 사전검사·학습·배틀은0이고 최초24시간 시계는 시작하지 않았다.

교정본은 CPU26검사와 실제114경기 검증을 통과했다. 원실패104경기에서 parser 실패가
사라졌고9,431결정·8,512라벨이 복원됐으며, 이전 비교10경기의528결정은 그대로다.
전체814 prefix에서 offline/live 상태가 일치했다. `diagnostics/replay-v2/gate.json`과
`source-freeze.json`을 연결하여 v2 전체 자료 재생성에 진입했다. v1 수치는 현재
학습/평가 분모로 사용하지 않는다.

교정 gate의 `smogtours-gen9ou-884619` p2는228턴 Sludge Bomb의 복원 PP0과 실제 선택이
불일치해 기존 guard로 관점 전체를 격리했다. 원인으로 Neutralizing Gas/Pressure 상호작용이
의심되지만 확정하지 않았으며, 해당 라벨은 학습에 넣지 않는다. 이는 공개 forme 교정과
구분한 복원 한계이며 추가 처치·자료 조건을 도입하지 않는다.

### CPU v2 확정 자료

전체2,793경기에서 역사 평가팀 중복82경기를 제외했다. 대상5,422관점 중3,886관점과
170,759결정을 복원했으며 parser 실패0이다. 선택 평가 가능158,715개를
train130,411/validation13,467/test14,837로 분리했고 실제 고정 사용량은
train130,411/validation512/test1,024다. 미공개 선택10,047개·단일 후보2,023개는
학습/정확도 분모에서 제외하며 두 집계는 일부 겹친다. 별도 격리 결정2,871개,
자동 행동155개와 관점 제외(일치 합법 세트 없음1,366·미지원 원래 정보168·세트/메뉴 불일치2)를
보존했다. 상태8,192토큰 초과 제외는0이다.

170,759개 결정의 분할·그룹·경기·후보/라벨·순서 매핑 및 원자료 해시 전수 감사를 통과했다.
`audit-gate.json`은 환경195파일과 필수 검사 증거26개를 결합한다. 원본/분할/corpus/대진
정적9파일은 v1과 byte 단위로 동일하며 `correction-completed.json`에 이전/새 자료 해시와
분모 차이를 기록했다. 최종 기준은 `prepared/manifest.json`이다.

### GPU 사전검사·학습량 동결

GPU3 `GPU-fd337c1e-b087-b26d-4dc0-a195c2b3a8d6`의 RTX A6000을 고정했다.
대표32표본 forward/backward가 유한 손실·경사로 통과했고 Base와 새 LoRA/head는
변하지 않았다(optimizer update0). p95 표본2.177374638초에1.2배·accumulation16을
적용한 update 추정은41.805593053초이며, 검증/저장4시간을 남겨 예정1,720update,
27,520표본으로 동결했다. 저장/validation 지점은430/860/1,290/1,720이다.
최초24시간 시계는2026-10-01 08:36:01.262105 UTC부터이며 재개로 초기화하지 않는다.
원문은 `preflight/report.json`, `training-clock.json`, `resource.json`이다.

초기 validation512개는 NLL2.645076956·행동 일치율0.134765625였다. test 결과가 아니다.
필수 중단/재개 검증은1update·18표본에서 한 번 수행했다. 부분 경사500개·Adam 상태500개가
FP32 유한 값으로 저장됐고 scheduler step1·Python/NumPy/Torch/CUDA RNG와 원 시계·cursor를
확인했다. 재개 PID는19번째 표본부터 이어가고32표본에서2번째 update를 완료했다.
원 시계·learning manifest·초기 validation 해시는 그대로다. 고정1,720update 학습을 이어갔고
학습 종료 후 최종 연속성 검사를 `execution/resume-completed.json`에 기록했다.

25% 지점430update/6,880표본 checkpoint를 저장하고 validation512개를 완료했다.
NLL1.897102880·행동 일치율0.283203125이며 모델 선택용 중간 값이다.
저장 파일 해시를 다시 대조해 Base426 tensor 불변, LoRA496·head4 tensor 갱신을 확인했다.
당시 완료432update의 번호는 연속했고 주기 재개 checkpoint13개가 보존돼 있었다.
GPU1의 기존 실행은 유지했다. 당시 학습은 진행 중이며 test·배틀은 미실행이었다.
이 값으로 배틀 개선을 판정하지 않는다.

### 학습 완료와 제어 프로세스 종료 보존

학습은2026-10-01 22:22:40 UTC에 예정1,720update/27,520표본을 완료했다.
사전검사부터 최종 validation까지49,598.874초(약13시간47분)다. validation NLL은
430/860/1,290/1,720update에서 각각1.897102880/1.830320212/1.806851078/1.793074506으로,
사전 NLL 규칙에 따라1,720update를 선택했다. 해당 행동 일치율은0.28515625다.
이는 validation 결과이며 test·배틀 결과가 아니다.

23:40 UTC 상태 확인에서 원 제어 PID3419626와 학습 PID3425945는 없었고, 원 제어 로그는
train-resume 시작에서 끝났다. 종료 원인은 미확정이며 exit code를 만들어 기록하지 않는다.
학습 단계 완료 event·resource release·네 checkpoint/validation·1,720개 update는 온전하다.
reload/test/battle 경로와 평가 예약은 아직 없었다. 원 기록을
`execution/controller-loss-v1/manifest.json`으로 보존했고, 파일 해시·Base 불변·원 시계와
learning manifest/초기 validation 불변·부분 재개 이후 update 연속성을 재확인했다.
`execution/resume-completed.json`은 실제 저장 증거에 근거해 최종 연속성 검사를 닫는다.
독립 감사 후 완료된 학습을 유지하고 미시도 평가만 기존 CLI로 이어갔다. 학습 재실행·
test/배틀 재수집·조건/소스 변경·시계 초기화는0이다.

### 잠긴 test 첫 평가

초기/선택 모델의 실제 재로딩과 각8개 저장 validation의 HTTP 확률 대조를 통과하고
모델·test 설정을 잠갔다. test1,024개를 각 모델에서 정확히1회 평가했다.
NLL은2.581497253→1.716763927, 행동 일치율은0.158203125→0.3125로 변했다.
인간 선택 재현의 전체 지표 개선이며 배틀 성능으로 해석하지 않는다.
선택 모델의 Tera 정답20개 일치율은0(초기0.25), 해당 NLL은1.907907104→4.114734000으로
악화됐으며, 선봉/강제 교체 일치율도 각각0.4194→0.3871/0.2586→0.2155였다.
종류·Tera 전후별 전체 분모/결과는 `evaluation/report.json`과 각 저장 예측에 보존한다.
첫 고정40경기 실배틀 평가로 이어갔다.

<a id="final-results"></a>

### 고정40경기·최종 판정

2026-10-02 UTC에 예정40경기 전부가 정상 종료했다. 초기/선택 모델 각각20경기이며
실패·무효·미완료·미실행은 모두0이다. 초기1승0무19패에서 선택3승0무17패로 변했고,
평균 점수는0.05→0.15다. 공통 정상20/20 slot·5/5대진의 대응 차이는+0.10이며,
대진 단위 bootstrap10,000회95% 구간은[-0.10, +0.30]이다.
**배틀 개선은 불확실하다.** 5대진의 첫 탐색 평가이며 이 구간이0을 포함하는 것을
효과가 없다는 증거로 해석하지 않는다. 전체 test의 인간 선택 재현 개선과 Tera·선봉·강제 교체
세부 지표 악화를 함께 보고하며 오프라인 개선을 배틀 효과로 바꾸어 주장하지 않는다.

배틀 단계는1,196.008초(약19분56초)로6시간 상한 안에서 끝났다. 추론 지연은 초기738회
평균0.4731초/p950.5166초, 선택727회 평균0.4893초/p950.5290초였다. 단일 후보의
무추론 전송은 이 추론 지연 분모와 구분한다. [전체 원장·분모·대응 분석](../../.pokechamp-data/experiments/ex071-qwen-replay-imitation/battle/result.json)에 보존했다.

모든 경기의 입력/확률/선택/명령·결과 감사와 actor/서버 정리가 통과했다. 폴더 이동 후
네트워크를 차단한 실제 Chromium에서40페이지·265결정의 오프라인 표시를 확인했고
브라우저 오류0·원자료 불변이었다. 독립 저장 test 재집계와 배틀·뷰어 payload 전체 체크섬
검증을 통과했다. 소유 제어·평가·배틀·내보내기·감시 실행을 종료하고 GPU3를 반환했으며,
별도 EX-066/GPU1을 보존했다. 승인된 학습·평가·보고의 완료 기준을 충족했고 추가 학습·
자기대국·경기는 수행하지 않았다.

- [통합 보고와 증거 해시](../../.pokechamp-data/experiments/ex071-qwen-replay-imitation/final/report.json) ·
  [독립 최종 검증](../../.pokechamp-data/experiments/ex071-qwen-replay-imitation/final/verification.json) ·
  [오프라인 뷰어 검사](../../.pokechamp-data/experiments/ex071-qwen-replay-imitation/final/viewer-check.json) ·
  [문서·자원·증거 연결](../../.pokechamp-data/experiments/ex071-qwen-replay-imitation/final/completion.json)
- [원 제어 종료 증거](../../.pokechamp-data/experiments/ex071-qwen-replay-imitation/execution/controller-loss-v1/manifest.json) ·
  [후속 실행 독립 감사](../../.pokechamp-data/experiments/ex071-qwen-replay-imitation/diagnostics/controller-continuation-v1.json) ·
  [후속 단계 완료](../../.pokechamp-data/experiments/ex071-qwen-replay-imitation/execution/completed.json)

### 생성 보고서 표현 보충

`final/report.md`의 정보 경계 문장은 이후 자기 공개 로그 자체를 입력에 넣지 않는다는 뜻이다.
C-055대로 **그 자료에서 복원한 자기 원래 세트는 입력에 포함**하며, 동적 상태·이력과 상대
정보는 결정 직전 공개 prefix까지만 사용한다. 이후 자기 공개까지 모두 사용하지 않은
실험으로 해석해서는 안 된다. 또한 보고서의 대응 누락 관련 문장은 일반 해석 규칙이며,
이번 실행의 실제 대응 누락은0이다. 생성 보고서·해시와 원자료는 그대로 보존하고 이 절로
표현을 보충한다. 처치·정보 경계·평가 규칙을 사후 변경한 것이 아니다.
