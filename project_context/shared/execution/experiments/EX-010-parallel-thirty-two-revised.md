# EX-010 — 수정coordinator 조건부32판

- Status: NotRun
- 날짜: 2026-09-07
- Experiment ID: `glm-concurrency-v2-parallel32`
- Study ID: `glm-concurrency-v2`
- 관련계획: [EP-007](../plans/EP-007-model-concurrency.md)
- 방법: [D-016](../decisions/D-016-model-concurrency.md)와 [EX-004](EX-004-model-concurrency-calibration.md).

## 사전 조건과 변경 경계

EX-006을 구현검토로중단한 뒤, hard-stop신호를 attempt완료이전에 감지하는
coordinator로 수정했다. EX-008/009는 동일수정source·동일8판일정이며 병렬→순차순서다.
EX-004의 요청경로 hash, 모델·계정·조건과 원래 예산시계를 검증해 명시적으로 이어쓴다.
Calibration추가호출은없고, 10:28:01 KST시작/14:13:01신규작업중지/14:28:01정리기한을 유지한다.

C*=10. 병렬8판은 배틀8/계정요청10/모델요청10, 순차8판은1/1/1이다.
비교완료후 병렬429/timeout/격리/integrity문제없음, 유효완료>=순차,
batch실경과<순차와 남은예산×1.5 gate를 통과할때만 배틀10/요청10의32판을 실행한다.
실패·중단·미실행분모, 동일slottransient1회retry, depth오류/알고리즘/출력/context/
모델/300초요청/1200초watchdog불변, 소표본운영해석은 D-016을 따른다.

## 결과

아직 실행하지 않았다.

EX-009의 configuration 중단으로 진행 기준을 충족하지 못해 실행하지 않았다.
