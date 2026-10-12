# EP-010 — 원본 fallback 병렬32판

- Status: Completed
- 생성일: 2026-09-07
- 책임자: Codex
- 관련: D-018 / EX-016 / C-010–C-013

## 목표와 범위

사용자 계획 및 [D-018](../../decisions/D-018-upstream-fallback.md)에 따라 parent 전용 upstream
정책과 계측/보고서를 구현·검증하고 glm-upstream-fallback32-v1 32슬롯을 실행한다.
Pinned source와 과거 원자료를 보존한다. Cloud 설정·일정·watchdog1200초는 불변이다.

## 완료 기준

- [x] 원본 fixture/시도/변환/RNG/provider 중단·중복 방지 및 기존 회귀 통과
- [x] 팀6/12 양진영 fake provider 로컬2판 완료와 fallback 전송 기록
- [x] source/config/32슬롯 봉인 후 동시성10/10 실행 (보충 없음)
- [x] 전체/유효 fallback 지표·비용·승패·시간·무결성·viewer·credential/소유자 정리 보고
- [x] 실행 계획/실험/STATUS 갱신

## 중단 조건

Authority 충돌은 기록·보고한다. Cloud 시작부터4시간, 신규 작업3시간45분 중지.
Provider 장애는 해당 경기 중단, hard-stop은 기존 정책을 유지한다.

## 진행

- 2026-09-07: 현재 계약과 원본 함수 확인, 사용자 승인에 따른 D-018 조건 변경 등록.

- 2026-09-07: 원본 AST IO/예외 계측, 별도 정책/추출, 실제 반환 객체 출처와 전체·유효 지표 구현.
  고정18 fixture 통과. 최종 로컬 v2 팀6/12 양진영2/2유효,43 choose 판단 중41 fallback,
  410 fake 응답/369 추가 호출,4 actor seals. 원자료는 `.pokechamp-data/upstream-fallback-local2-v2/`.
  최초 회귀122개 통과; 추가 전체 회귀는 로컬경기 포트 경합4건 및 fixture 설정1건을 발견,
  fixture를 수정하고 로컬 종료 후 순차 재검증 중이다. Cloud는 아직 미시작.

- 실행 봉인: source 41개, core-repeat32 일정/팀이 EX-014와 일치.
  최종142 tests/Ruff 통과. Cloud 시작 epoch 1788760375.64703,
  신규 중지 1788773875.64703, 정리 기한 1788774775.64703.

## 결과 및 증거

142 tests/Ruff, 최종 fake 로컬2/2, Cloud 유효32/32, 실제20.95분.
원본 출력 정책·계측·분모별 보고 및 source/bundle/viewer/credential/소유자 정리 검증을 완료했다.
초기 포트 경합 회귀는 로컬 종료 후 순차 실행하여 해소했다. Cloud 경기 보충은 없다.
[EX-016](../../experiments/EX-016-upstream-fallback.md)에 승패·fallback·비용·시간과 증거를 보존한다.
