# EX-009 — 수정coordinator 순차8판

- Status: Stopped
- 날짜: 2026-09-07
- Experiment ID: `glm-concurrency-v2-sequential8`
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

병렬EX-008완료후동일source·일정의순차8판을시작했다. 배틀1/계정요청1/모델요청1.

## 중단 결과

예정 8 / 처리 2 / attempt 2 / 유효 완료 0 / 미실행 6.
첫 minimax 경기의 출력 검증 오류 이후, 두 번째 경기의 서버 포트 재사용 사전 검사에서
EADDRINUSE가 발생하여 configuration hard-stop으로 중단했다. 실패를 패배로 계산하지 않는다.
첫 actor 원자료와 시작 전 실패 attempt를 보존했다. 이 불완전 비교로 32판을 실행하지 않았다.

서버 종료 후 worker listener 정리 대기와 TIME_WAIT 구분을 보완한 새 source에서
EX-011/012를 별도 ID로 실행한다. 원래 실측 시계와 EX-004 calibration은 유지한다.
