# EP-115 — Qwen 4B 리플레이 모방 학습과 첫 배틀 평가

- 상태: Completed
- 생성일: 2026-10-01
- 완료일: 2026-10-02
- 책임자: Codex
- 승인 근거: 현재 사용자 제공 계획의 구현·첫 학습·평가 수행 지시 / D-113
- 관련: [EX-071](../../experiments/EX-071-qwen-replay-imitation.md),
  [C-055](../../CONTRACTS.md#c-055-imitation), D-112, D-091

## 목표와 범위

기존 리플레이를 복원하여 새 Qwen3.5-4B 행동 선택 정책을 학습하고 고정 오프라인·실배틀
평가 및 한국어 보고·뷰어까지 수행한다. 조건·분모·상한·복구 원문은 EX-071을 따른다.
구현 위치는 `integration/pokechamp/imitation/`, `scripts/pokechamp-imitation`, 관련 신규
검사·문서다. upstream parser는 별도 CPU 환경에 고정하고 JSONL로 연결한다.
기존 q/서빙 경로·EX-066/GPU1·환경·원자료·봉인·Blocked를 보존한다. 자기대국은 제외한다.

INDEX·CHARTER·RESEARCH_DESIGN·STATUS와 exec-plan 색인을 확인했다. EP-108/103 및
배틀 runtime과 겹치는 중단 plan을 조사하여 새 실행의 경계와 과거 중단을 구분한다.
Root AGENTS의 Astra 위임 지침에 따라 데이터 복원·학습·실배틀의 독립 조사를 위임하고,
공유 schema·문서·통합 및 필수 검증은 주 에이전트가 조율한다. 같은 파일의 동시 수정은 금지한다.

## 완료 기준

- [x] ADR/EP/EX와 입력·Choice 계약, source/model/data/environment provenance 등록
- [x] 재현 가능한 데이터셋·분할/누락/추정/제외 감사, 입력 누출·중간 경계·후보 정합성 검증
- [x] GPU 사전검사·최대 업데이트 동결, 첫 학습·완전 재개·체크포인트 재로딩 검증
- [x] validation 모델 선택·잠긴 test 각1회, 예정40경기 전체의 정상/실패/미완료/미실행 집계
- [x] 한국어 결과 보고·C-047의 오프라인 행동 선택 확률 뷰어·해시·소유 자원 정리

성능 향상은 완료 조건이 아니다. 미실행·미충족 항목은 완료로 표시하지 않는다.

## 검증

| 변경 경계 | 검사 | 증거/결과 |
|---|---|---|
| 데이터 | 미래 상대·승패·메타데이터 변형 불변, 원문/라벨·보완·그룹/분할 전수 대조 | CPU v2 170,759결정 전수 감사·26개 필수 검사 증거 연결 통과 |
| 모델 | Base 불변, LoRA/head 갱신, 유한 손실/경사, 재개·재로딩, 순서 매핑 | CPU33검사·GPU32표본/1,720update·실제 부분 재개·초기/선택 모델 재로딩/HTTP 확률 대조 통과 |
| 배틀 | 동일 serializer/정밀도, rqid/합법 명령 재확인, 시계/실패/중단/무재시도 | CPU43검사·보존 실제 prefix3종 입력/명령 연결·이동 후 오프라인 Chromium 뷰어 통과 |
| 산출물 | 저장 원문 대조, paired bootstrap·분모, 이동 후 오프라인 열람/출처 해시 | test 각1,024개 독립 재집계·고정40경기 전수 감사·5대진/20대응 slot·원자료/뷰어 전체 체크섬·Chromium40페이지/265결정·소유 자원 정리 통과 |

## 진행

- 2026-10-01 — 사용자 실행 계획을 등록했다. GPU1의 기존 학습 점유와 GPU3/2/0 유휴를
  읽기 전용 확인했다. 실제 GPU 고정은 실행 직전 다시 확인한다. 신규 학습/배틀0.
- 2026-10-01 — CPU 복원 환경과 구현을 준비하고 원본2,793경기·역사 팀 제외82경기·
  연결630그룹·경기 분할2,169/271/271·보완 corpus·고정40대진을 학습 전에 동결했다.
  validator의 forme 정규화 관련 준비 오류와 corpus 제외 단위 정정을 별도 버전/진단으로
  보존했다. GPU/모델 추론 없이 전체 복원·토큰화를 진행 중이다.
- 복원20검사와 실제10경기528결정/487라벨, 선봉·턴 선택·강제·피벗 교체의29 prefix
  offline/live 동일성 검사를 통과했다. 모델 CPU33검사와 실제4B Base·LoRA/head의
  저장→새 Policy 재로딩→optimizer/scheduler/RNG 복원 검사를 통과했다. 이는 실제 GPU
  역전파·갱신·서빙 대조를 대체하지 않는다. 증거는 산출물 `diagnostics/`에 보존했다.
- 실제 첫 학습의 초기 validation과1회 이상 update 후 부분 accumulation에서 소유 PID에
  SIGTERM을1회 보내 완전 checkpoint와 실제 재개를 확인한다. 추가 forward·update·
  validation 재평가는 하지 않으며 최초 시계·자료·처치·GPU·예정 학습량을 유지한다.
  전체 상태 저장 감사와 새 PID의 진행 연속성으로 판단하고, GPU 무중단 경로와의
  bit-exact 비교를 수행했다고 해석하지 않는다. 원 시계 내 검증 가능한 구간이 없으면
  검사를 만들려고 학습량을 늘리지 않는다.
- CPU 전체 복원 v1은157,098결정·145,971개 선택 평가 가능 표본을 만들었으나,
  실패104경기 전부에서 공개 battle-only forme의 재등장을 원래 슬롯으로 연결하지 못하는
  adapter 결함을 확인했다(Ogerpon-Wellspring-Tera55·Ogerpon-Teal-Tera46·Mimikyu-Busted3).
  동일 함수가 live에서도 쓰이고 동결 평가팀에 Ogerpon-Wellspring이 있어 GPU 진입을
  보류했다. v1 자료·소스·검사·원인 진단을 보존하고 알려진 공개 forme의 슬롯 연결만
  교정한 CPU v2를 재검증·재생성한다. 원본 목록·그룹/분할·corpus·평가팀/seed·모델/학습
  조건은 유지한다. 아직 GPU 사전검사·학습·배틀0이며 최초24시간 시계도 시작하지 않았다.
- CPU v2 교정본26검사와 실제114경기 gate를 통과했다. 기존 실패104경기는 parser 실패0,
  9,431결정·8,512라벨로 복원됐고 기존 비교10경기528결정은 v1과 동일하다.
  총814개 offline/live prefix 상태가 일치한다. 특성이 공개되기 전 상대 값을 비워 두는
  경계와 own 현재/원래 특성 구분도 검증했다. 수정본으로 전체 CPU 복원/토큰화를 재생성 중이다.
  `diagnostics/replay-v2/gate.json`, `source-freeze.json`과 원 실패/검사 기대 교정 증거를 보존했다.
- 실행 제어·최종 보고 통합18검사, 소유 CPU parent/별도 session child의 오류 시 정리 검사를
  통과했다. 실제 GPU 단계 간 같은 UUID 유휴 확인, 부분 checkpoint의 전 상태 감사와
  재개 뒤 첫 update 연속성을 실행 제어에 포함했다. 실제 검증 결과는 실행 후 별도로 기록한다.

CPU v2 전체 복원과 전수 감사를 완료했다. Parser 실패0, 복원3,886관점/170,759결정,
선택 평가 가능158,715개이며 학습130,411·validation512·test1,024를 동결했다.
원본/분할/corpus/평가팀·seed의9개 정적 파일은 v1과 byte 단위로 같고, 교정 결과와
이전 버전 연결을 `correction-completed.json`, `audit-gate.json`에 보존했다.
GPU 사전검사 측정으로 업데이트 상한을 정한 뒤 첫 학습·실제 재개 검증·평가를 진행한다.

GPU3의32표본 사전검사를 통과했다(Base·LoRA/head 불변, optimizer update0).
p95=2.1774초, 여유 적용 update 추정41.8056초로 예정1,720update를 동결했다.
checkpoint 지점은430/860/1,290/1,720이며 초기 시계는2026-10-01 08:36:01 UTC다.
현재 초기 validation과 첫 학습을 진행한다. 실제 완료량·재개·평가는 별도 결과로 기록한다.

초기 validation512개를 완료하고 실제1update·18표본(다음 accumulation2/16)에서
소유 학습 PID를1회 중단했다. FP32 유한 경사500개와 Adam 상태500개·scheduler·4종 RNG·
원 시계/자료 위치를 저장했고 새 PID가19번째 표본부터 재개했다. 다음 update는32표본에서
정확히2번째로 완료됐다. 원 시계·learning manifest·초기 validation 해시 불변을 확인했다.
`execution/interruption-check.json`, `resume-first-progress.json`과 `training/updates.jsonl`이
증거이며 GPU 무중단 실행과 bit-exact 비교한 것으로 해석하지 않는다. 고정 학습을 계속한다.

첫25% checkpoint와 같은512개 validation을 완료했다. 저장 파일 무결성·Base 불변·
LoRA/head 갱신과 실제 update 연속성을 확인했다. 중간 수치는 EX-071에 기록하고,
사전 동결한 나머지 학습·평가를 계속한다.

2026-10-01 22:22:40 UTC에1,720update/27,520표본과 네 checkpoint validation을
완료했다. 약13시간47분이며 NLL 기준 최종1,720update를 선택했다. 이후 사용자 상태 질의로
확인한23:40 UTC에는 원 제어 PID와 학습 PID가 없었고 후속 평가 시도는0이었다.
제어 종료 원인은 기록으로 확정하지 않는다. 원 제어 기록·완료 학습 상태를
`execution/controller-loss-v1/`에 보존했다. 네 checkpoint/validation 해시·원 시계·manifest·
초기 validation 불변과1..1,720update 연속성을 확인하여 실제 재개 검증을 닫았다.
학습·처치 코드를 바꾸거나 학습을 재실행하지 않고, 독립 감사 후 기존 CLI의 미시도
evaluate→battle→export만 같은 조건으로 이어간다.

독립 CPU 감사 `diagnostics/controller-continuation-v1.json`이 원 소스·자료·완료/부분 재개
경계·평가 미시도와 후속 호출 범위를 확인했다. 모델/GPU 추가 호출0이다.
원 controller는 수정하지 않고 별도 제어 artifact를 고립 session으로 시작했다.
현재 기존 CLI의 첫 evaluate를 진행하며 최초 시계·체크포인트·고정 대진을 유지한다.

초기/선택 모델을 실제로 재로딩하고 저장 validation 표본의 HTTP 서빙 확률 대조를 통과했다.
동일 unmerged BF16/FP32 경로를 확인하고 모델/test 설정을 잠갔다. 고정 test 각1회 평가를
진행한다. 증거는 `reload/serving-parity.json`, `evaluation-lock.json`이다.

2026-10-02 — 잠긴 test 각1,024개와 고정40경기 전부를 완료했다. 모든 경기가 정상 종료했고
실패·무효·미완료·미실행은0이다. 후속 evaluate/battle/export는 모두 exit0이며 학습·test·
배틀을 반복하지 않았다. 저장 test 예측의 독립 재집계, 전체 경기 입력/전송·결과 감사와
actor/서버 정리, 원자료·내보낸 뷰어의 전체 payload 체크섬 검증을 통과했다.
이동한 폴더에서 네트워크를 차단한 실제 Chromium으로40페이지·265결정 표시를 확인했다.
GPU3를 반환하고 소유 실행·감시를 종료했다. 별도 EX-066/GPU1은 유지한다.
인간 선택 재현의 전체 지표는 개선됐지만 일부 결정 종류는 악화됐고, 배틀 개선은 불확실하다.
수치·분모·해석은 EX-071과 최종 보고를 따른다. 자기대국·추가 학습/경기를 시작하지 않는다.

## 중단·복구

[INDEX](../../INDEX.md#workflow)·RD11.1/C-018 및 EX-071의 단계별 중지/복구를 따른다.
합법적인 나쁜 선택은 계속 실행하고 실행 불가능 응답은 해당 경기로 격리한다.
공유 입력·수집·정밀도·무결성 결함은 영향 단계와 의존 결과를 중지한다.
허용 복구도 원 source·실패 증거·최초 시계·누적 상한을 유지한다.

## 결과와 증거

승인된 첫 학습·평가·보고와 모든 완료 기준을 충족했다. 성능 향상을 완료 판정으로 대신하지
않으며 원 제어 프로세스 종료 원인은 미확정으로 보존한다. 산출물 루트는
`.pokechamp-data/experiments/ex071-qwen-replay-imitation/`이다.

- [한국어 통합 보고](../../../.pokechamp-data/experiments/ex071-qwen-replay-imitation/final/report.md) ·
  [해석·표현 보충과 최종 결과](../../experiments/EX-071-qwen-replay-imitation.md#final-results) ·
  [40경기 오프라인 뷰어](../../../exports/battle_viewers/ex071/index.html)
- [자료·검사·학습·평가 증거와 해시](../../../.pokechamp-data/experiments/ex071-qwen-replay-imitation/final/report.json) ·
  [독립 재집계·전체 체크섬 검증](../../../.pokechamp-data/experiments/ex071-qwen-replay-imitation/final/verification.json) ·
  [최종 문서·자원·증거 연결](../../../.pokechamp-data/experiments/ex071-qwen-replay-imitation/final/completion.json)
- [원 제어 종료 증거](../../../.pokechamp-data/experiments/ex071-qwen-replay-imitation/execution/controller-loss-v1/manifest.json) ·
  [후속 실행 독립 감사](../../../.pokechamp-data/experiments/ex071-qwen-replay-imitation/diagnostics/controller-continuation-v1.json) ·
  [실제 부분 재개 연속성](../../../.pokechamp-data/experiments/ex071-qwen-replay-imitation/execution/resume-completed.json)
