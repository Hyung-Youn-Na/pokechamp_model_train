# EP-108 — EX-065 기반 Base 공동 q 학습

- 상태: Blocked
- 생성일: 2026-09-30
- 책임자: Codex
- 승인 근거·범위: 현재 사용자 제공 계획·GPU2 지정·유휴 GPU 대체 지시 / D-104·D-105·D-106
- 관련: C-051/C-052, EX-065/EX-066

## 목표와 범위

EX-065 공개 로더·JointInput을 재사용하여 공동 readout 모델과 prepare/preflight/train/evaluate/verify
CLI를 구현하고 승인된 학습·독립 평가·재현 보고를 완료한다. 동결 조건의 원문은
[EX-066](../experiments/EX-066-joint-q-training.md)이다.
INDEX/CHARTER·STATUS·exec-plan 색인·겹치는 EP-103을 확인했다. 기존 배틀/Blocked·원자료·
  token cache·가중치는 보존한다. 새 배틀·외부 모델 API·세 환경 비교·AgenticSTS 변경은 포함하지 않는다.
별도 agent 위임은 사용하지 않는다.

## 완료 기준

- [x] ADR/EP/EX·domain authority 등록, Base revision·가중치·파일 해시 확인
- [x] readout/ID/타깃·입력 격리·순서·padding·경계 검사와 train/validation/3epoch 길이 전수 검사
- [x] 선택한 유휴 GPU1 최장/후보 경계 forward/backward 사전검사·유한 손실/경사·업데이트0
- [ ] 초기/3epoch/완전 optimizer 체크포인트, validation 선택·새 프로세스 재로딩 대조
- [ ] 잠금 후 모델별 test1회·기준선/선택력/중복/그룹 bootstrap·비용 보고
- [ ] 체크포인트·예측·source/data/tokenizer 해시·명령·봉인·GPU 정리와 상태 갱신

비배틀 작업이므로 C-047 viewer는 해당 없음. 필수 검증을 통과하지 못하면 완료로 표시하지 않는다.

## 진행과 검증

- 2026-09-30 — 승인 범위·관련 원문 확인 후 등록. EX-065 복사본과 EVE 환경이 존재하며 GPU1 유휴 확인.
  아직 신규 모델 forward·학습·test 평가0. 산출물은 `.pokechamp-data/experiments/ex066-joint-q-training/`에 보존한다.
- 중단된 대화 이후 상태를 확인하고 작업을 이어갔다. Base 고정 revision 다운로드 완료,
  공동 모델/renderer·체크포인트/재개·평가 잠금·CLI를 구현했다. 새40검사는 통과했으며,
  기존 수집 회귀를 EVE에서 호출한 의존성 오류와 native 환경의 cwd 오류는 검사 실행기를
  교정했다. 실제 입력/처치/학습/test에 영향0, 실패 로그와 교정 검사는 verification에 보존한다.
- 새 학습40·기존 수집14검사 모두 통과(실패/오류/skip0). Base 공식 LFS 체크섬과
  train/validation·3epoch 셔플 입력의 전수 무절단 token/readout 검사를 진행 중이다.
  [검사 원문](../../../../.pokechamp-data/experiments/ex066-joint-q-training/verification/tests.json).
- 원순서 train/validation와3epoch 셔플 입력 총6,876개 전수 token/readout 검사를 완료했다.
  타깃/private 변형1,959관측의 토큰 불변·후보/타깃 ID 정합성·분할 분모·그룹/의미 중복
  split 격리를 확인했다. 최대 train29,660/validation26,912토큰, 절단/제외0이며 test 토큰화0이다.
  공식 Base revision의 LFS SHA-256 대조를 완료했고 GPU1 text tensor·forward/backward
  사전검사를 진행한다. [준비 원문](../../../../.pokechamp-data/experiments/ex066-joint-q-training/prepared/manifest.json).
- 최초 GPU preflight는 text tensor426개·세 경계 사례 forward/backward 후 오른쪽 token-padding
  q 차이 기준에서 중지했다. 독립 재현의 최대 차이0.00015920400619506836, 무패딩 반복 차이0,
  optimizer/test0이다. 원 source/준비 자료/STOP/로그는 `versions/preflight-v1/`에 보존했다.
  실제 microbatch1의 전체 유효 prefix는 유지하고 마스크된 padding만 backbone 앞에서 제거하도록
  입력 정규화를 교정했다.55회귀 검사 통과, 동일 토큰·설정과 기존 무패딩 q 불변을 독립 GPU에서
  확인하기 전 학습 진입은 계속 차단한다. 최초 시계·비용/실패를 유지하며 evidence-gated
  preflight recovery receipt만 이 기술 결함의 재검사를 허용한다.
  [독립 재현](../../../../.pokechamp-data/experiments/ex066-joint-q-training/diagnostics/padding-v1.json).
- 사용자 GPU2 지시를 D-105로 등록했다. 진행 중인 CPU 재준비를 종료하고 source·부분 준비·
  STOP을 `versions/prepare-gpu1-interrupted/`에 보존했다. 학습 update/test0, 최초 시계 유지.
  wrapper·물리 GPU lock·실행 receipt를 GPU2에 맞춰 재동결하고, 승인된 GPU 차이만 허용하는
  복구 대조와 독립 padding 검증을 수행한다.
- GPU2 소유 lock·CUDA_VISIBLE_DEVICES·nvidia-smi의 물리 인덱스와 GPU1 거부를 포함한
  새42·기존14, 총56검사 통과(실패/오류/skip0). GPU2 준비를 진행하며 소스 변경 없이
  원 준비본과 token/cache 파일을 전수 대조한다.
- GPU2를 다른 프로세스가 사용하여 대기 중 사용자가 다른 유휴 GPU 대체를 명시했다(D-106).
  GPU1 유휴를 확인하고 GPU2 완전 준비/source/protocol을 `versions/prepared-gpu2/`에 보존했다.
  학습 전 GPU1로 고정하여 새 설정으로 동결하며 최초 시계·모든 과거 증거를 유지한다.
- GPU1/2 물리 라우팅·다른 GPU 거부를 포함한57검사 통과(실패/오류/skip0).
  독립 GPU1 진단에서 원 무패딩 q와의 최대 차이0,17padding/무패딩 반복 차이0,
  Base/LoRA/head 불변·optimizer0을 확인했다. CPU 준비를 완료한 뒤 동일 cache와 source를
  대조하고 복구 receipt로 최장/후보 경계 사전검사에 진입한다.
  [독립 교정 검증](../../../../.pokechamp-data/experiments/ex066-joint-q-training/diagnostics/padding-v2.json).
- GPU1 새 준비의6,876입력·1,959격리 검사·train/validation/3epoch 무절단 전수 검사를 완료했다.
  세 준비본의 data/Base/tokenizer/분모/준비 파일10개·길이 통계 전부 동일하고 GPU 이외 조건도
  원 동결과 동일하다. 최종 source/protocol을 산출물 안에 보존하고 recovery receipt 검증을
  통과하여 GPU1 최장/후보 경계 preflight를 시작했다. 학습/test0.
  [복구 원문](../../../../.pokechamp-data/experiments/ex066-joint-q-training/recovery-receipt.json).
- GPU1 최장29,660토큰·1/13후보 forward/backward가 모두 유한 손실/경사를 통과했다.
  최대 할당31,253,715,968bytes, Base/trainable 불변·업데이트0·padding차이0.
  경계 seconds/token 추정은 학습 계산101.55시간이며 validation/checkpoint 비용은 별도다.
  성공 receipt로 원 STOP을 해결했다. 연속 실행기 `run-pipeline.py`를 독립 session에서 시작하여
  초기 validation·3epoch 학습 → 새 프로세스 재로딩 → test각1회 → 최종 검증/봉인 순으로
  진행한다. 실패 시 의존 단계를 중지하며 자동 test 재시도0. 최종 봉인 중에는 변하는 실행기
  상태/로그를 별도 `.pokechamp-data/jobs/ex066-joint-q-training/`에 기록한다.
  [GPU 사전검사](../../../../.pokechamp-data/experiments/ex066-joint-q-training/preflight/report.json).
- 초기 validation 단계·optimizer update0에서 유한한0경사의 잘못된 거부를 독립 CPU 사례로
  재현했다. 실제 학습은 아직 미진입이며 초기 checkpoint/RNG를 유지하여 기술 중단했다.
  원 source/준비/preflight/중단을 `versions/zero-gradient-v1/`에 보존했다. runtime의 해당2행
  제거만 허용하는 receipt와 전q0/1 MSE0·0경사/누락·NaN·Inf 회귀를 검증하여 같은 설정과
  초기 checkpoint에서 재개한다. 반복 초기 validation 비용·최초 시계·실패 증거는 보존한다.
  [독립 재현](../../../../.pokechamp-data/experiments/ex066-joint-q-training/diagnostics/zero-gradient-v1.json).
- 교정 후 새48·기존14, 총62검사 통과(실패/오류/skip0). guard-only receipt가 runtime2행 제거,
  모델/입력/수치 연산·설정/환경 불변과 original latest initial update0을 대조해 source를
  다시 동결했다. GPU1의 최장/1/13후보·유한 손실/경사·padding0·파라미터 불변 재검사 통과.
  새 preflight의 Base/LoRA/head fingerprint가 보존한 초기 checkpoint와 정확히 일치했다.
  원 초기 checkpoint·optimizer/RNG에서 `train --resume` 연속 실행을 재개한다.
  [경계 교정 receipt](../../../../.pokechamp-data/experiments/ex066-joint-q-training/gradient-recovery-receipt.json).
- 초기 validation320관측/2,991후보의 저장 평가 완료(MSE0.1915002450342827).
  실제 첫8관측 optimizer update와 완전 체크포인트를 확인했다. 평균 손실0.17316998913884163,
  유한한 경사 norm7.337003259597341, LoRA/별도 head 모두 변경·adapter496tensors와
  optimizer498states FP32·CUDA RNG1개·파일 무결성 검증 통과. 전체3epoch 학습은 계속 진행 중이다.
  [실제 업데이트 검증](../../../../.pokechamp-data/experiments/ex066-joint-q-training/verification/first-update.json).
- 2026-10-01 08:48 KST — 현황 확인: GPU1 학습·연속 실행기 모두 정상 실행 중이며168/615update,
  epoch1의1,344/1,639관측을 완료했다. 전체 update의 손실/경사가 유한하고 STOP 없음,
  동결 source18개·원자료4개·최신 checkpoint 파일/pointer 해시가 일치했다.
  최근20~50update 평균 처리량 기준 남은 학습은 약54~56시간이며 validation/최종 평가 시간은
  별도다. epoch 종료 후 학습 모델 validation과 독립 test는 아직 미실행이다.
  [학습 진행](../../../../.pokechamp-data/experiments/ex066-joint-q-training/training/progress.json) ·
  [완료 update 원문](../../../../.pokechamp-data/experiments/ex066-joint-q-training/training/updates.jsonl).
- 2026-10-02 13:15 KST — GPU1에서397/615update를 완료하고 epoch2의1,536/1,639관측까지
  학습했다. epoch1 checkpoint와320관측 validation 저장을 완료했다. validation MSE는 초기
  0.1915002450342827에서0.1697373078580894로11.36% 감소했으나 최고 후보 선택률은
  53.4375%에서50.9375%로2.5%p 하락했다. 최종 선택과 독립 test는 미실행이며3epoch를 유지한다.
  완료 update의 손실/경사가 모두 유한하고 STOP 없음, 동결 source·원자료·최신 checkpoint와
  pointer의 해시가 일치했다. 최근20~50update 속도 기준 남은 학습은 약27시간이며 이후
  validation·재로딩·독립 평가 시간은 별도다.
  [epoch1 검증](../../../../.pokechamp-data/experiments/ex066-joint-q-training/training/metrics-epoch1.json).

## 중단과 복구

[INDEX](../../../INDEX.md#workflow)·RD11.1/C-018 및 EX-066의 중단/복구 절을 따른다.
길이 초과·OOM·입력 누출·비유한 경사는 의존 실행을 중지하고 절단/제외/설정 완화로 통과시키지 않는다.
동일 설정·RNG와 마지막 완전 optimizer checkpoint에서만 기술 재개한다.

## 결과와 증거

3epoch·615update 학습과 epoch별 validation 평가·epoch3 선택을 완료했다. 새 프로세스
재로딩 q 최대차이0.0018912255764007568이 허용 기준1e-4를 초과하여 Blocked다.
독립 test 평가·최종 보고·봉인은 미실행이며 학습 완료를 실험 완료로 해석하지 않는다.
[선택 기록](../../../../.pokechamp-data/experiments/ex066-joint-q-training/training/selection.json) ·
[validation 결과](../../../../.pokechamp-data/experiments/ex066-joint-q-training/training/metrics-epoch3.json) ·
[중단 근거](../../../../.pokechamp-data/experiments/ex066-joint-q-training/STOP.json).

- 2026-10-03 — EX-073 자원 사전 확인에서 원 `reload.log`의 q 최대차이
  0.0018912255764007568 >1e-4 재로딩 실패와 GPU 점유0을 확인했다. 실패·가중치·자료를
  보존하며 이번 작업에서는 재개/조건 변경하지 않는다. 미충족 재로딩/test/봉인 기준으로
  Blocked를 기록한다. [원 로그](../../../../.pokechamp-data/experiments/ex066-joint-q-training/reload.log).
