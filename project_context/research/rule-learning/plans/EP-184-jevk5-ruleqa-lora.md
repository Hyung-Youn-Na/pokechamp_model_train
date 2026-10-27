# EP-184 — JevK5 규칙 선택형 추가 LoRA

- 상태: Completed
- 생성일: 2026-10-20
- 승인: 현재 사용자 제공 계획 구현·실행 요청 / D-169
- 원문: [EX113](../experiments/EX-113-jevk5-ruleqa-lora.md), C083, RD11.1
- 연구선/checkout: research/model-training /workspace; 시작commit a4659bf298c7935714f9fbd25246db2d831c5926
- 환경: /ref/kev/.venv, 기존 dirty작업 보존.

## 범위

독립 integration/jevk5_ruleqa_training 및 scripts/jevk5-ruleqa-train 구현·실행·검증.
INDEX/CHARTER/매뉴얼/STATUS/RD/계약 및 EP183·관련 중단 EP108/119/125/126/127 확인.
기존 학습·배틀 실행을 재개하거나 수정하지 않는다. 조건·출력·예산·중단/복구는 EX113 원문.

## 완료 기준

- [x] CPU 검증 및 GPU 사전검사
- [x] 192step·validation 선택·보정·test 각1회
- [x] 비병합adapter·24문항 재로딩·한국어 보고·봉인·자원 반환

## 진행

2026-10-20 승인 등록. 기존 EX107 구조와 JevK5 공식 prompt/학습 구현 조사. 성능 미측정.

- CPU 전수1,920문항의 원자료/분할/누출/공식prompt 검사를 통과(최대5,416토큰).
  독립 CE/gradient·실제 Gloo3rank 누적24평균 등5검사 통과. 첫 fixture는 validation/test에
  3선택지도 있다는 잘못된 가정으로 실패했으며 실제분포(train만34개)를 반영해 교정했다.
- 최초 preflight는 모델 동시적재 중 합산RSS83,500,445,696bytes로64GiB를 초과하여 감시기가
  종료했다. 모델forward/학습update/평가0. GPU/PID/잠금 반환 및 원source/prepared/실패receipt 보존.
  RD11.1에 따라 rank순차적재·Transformers동기적재로 host staging만 교정한다. 상한/모델/자료/손실은
  불변이고 최초시계/사용량은 유지한다. CPU동기/비동기 적재tensor동치 검사 후 사전검사로 검증한다.

- 순차·동기적재 교정 후 GPU 사전검사 통과. 152attention모듈/18,112,512 FP32 LoRA를
  원본safetensors header와 독립대조했다. 3rank 기반 불변·LoRA변경·유한loss/gradient 통과.
  물리GPU최대24,085,790,720bytes·hostRSS57,197,379,584bytes. 긴문항 업데이트120.99초의
  학습예상23,229.82초(초기컴파일 포함·평가/적재 제외). 첫실패 비용/최초시계 유지.
- 본학습→보정→test→CPU복원검사/곡선→export의 단일 파이프라인 시작. 실패 시 자동재시도0.

- 본학습48/192step 진행, step0/16/32/48 완전checkpoint 저장. 기반validation112/192
  (58.33%), T1 NLL1.124824311. 학습48step까지 비정상수치/장치/자원실패0.
  epoch별validation·선택·test는 아직 미실행이며 개선판정은 보류한다.

- epoch1/64step 완료 및 완전checkpoint 저장. validation171/192(89.06%), T1 NLL0.251106927.
  기반validation112/192와 비교한 중간 결과이며 최종선택·test판정은 아직 아니다. epoch2 진행.

- 사용자 후속 요청에 따라 step별 알림을 종료하고 epoch완료/선택·보정/test/최종검증 단계만
  보고하는 저장기록 기반 감지기를 연결했다. 오류는 즉시 보고하며 학습조건은 바꾸지 않는다.
- epoch2/128step 완료. validation175/192(91.15%), T1 NLL0.196466080. epoch3 진행 중.
  선택·보정·test는 아직 미실행이다.

- 3epoch/192step 완료. epoch3 validation176/192(91.67%), T1 NLL0.207878401.
  정확도 우선 기준으로 epoch3을 선택했다(epoch2는175/192·NLL0.196466080).
  validation만 사용한 보정 T는 기반2.065380156, 선택1.412537545로 확정했다. test 단계 진행.

## 결과 및 증거

2026-10-20 승인된3epoch/192step, validation선택·보정, 두모델 test각192문항1회를 완료했다.
선택 비병합adapter·13완전checkpoint·문항별 보정전후확률·학습곡선·규칙별비교·한국어보고를 보존했다.
24validation 새프로세스 재로딩의 선택과 원확률은 모두 동일(최대절대차0)이다.
실제 optimizer/scheduler CPU복원 검사, 소유worker0·GPU프로세스0·공용잠금반환 및 봉인을 확인했다.
실제GPU학습재개·추가학습·test재추론은0이며, 최초 적재실패와 복구증거/사용량은 보존했다.

[최종 보고](../../../exec-plans/evidence/ep184/report.md) ·
[종결 검사](../../../exec-plans/evidence/ep184/completion-audit.json) ·
[검증 로그](../../../exec-plans/evidence/ep184/recovery-tests.log) ·
[보정확률 독립 검사](../../../exec-plans/evidence/ep184/calibrated-probabilities-test.log).
실험 수행 완료와 성능 개선 판정의 상세 근거는 EX113과 보고서를 따른다.
