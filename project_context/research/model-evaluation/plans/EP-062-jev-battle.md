# EP-062 — JEV 전용 배틀 입력과 2경기 테스트

- 상태: Blocked
- 생성일: 2026-09-21
- 책임자: Codex
- 승인: 현재 대화의 계획 구현 지시. Choice·간결한 관측·JEV 선봉·Abyssal 상대를 선택했다.
- 관련: D-071, C-045, EX-047. INDEX/CHARTER와 active plan 범위를 확인했다.

## 목표·범위

parent integration에 JEV 독립 배틀 프로필·공식 관측 투영·슬롯 실행·검증·viewer를 추가한다.
기존 B/B2·Blocked 실행·원자료·canonical submodule은 보존한다.
실행 조건과 비용·중단 경계 원문은 [EX-047](../experiments/EX-047-jev-battle.md)이다.

## 완료 기준

- [x] 전용 입력/질문·선봉/행동·확률 검증·비동기 연결 구현
- [x] 오프라인·모의 HTTP·무유료 로컬 배틀 및 관련 회귀 검증
- [ ] 실제 2경기 정상 종료·입력/선택/전송 전수 감사
- [x] 한국어 보고·viewer·증거 봉인·자원 정리·상태 동기화

## 진행

- 구현 전 승인 범위와 프로토콜을 등록했다. 실제 API 호출0.

## 중단·복구

RD11.1/C-018을 적용하고 본 수집 중 첫 오류에서 전체 중단한다. 소규모 연결 진단이므로
유료 복구·재시도·보충0이며 원자료·최초 시계·누적 요청을 보존한다.

- 최종 로컬2경기 정상 종료·92모의 요청/94전송·공식 cutoff 재생과 입력/응답/슬롯 전수 감사 통과. 관련107검사와 후속 JEV57검사·compileall 통과. [검증 receipt](../../../exec-plans/evidence/ep062/verification.json). 실제 API0.

- 실제 EX-047은17요청·16전송 후 확률합0.99 응답에서 중단했다. 정상완료0/2로 실험 미완료이며 재시도/추가 호출0.
- 입력17개 공식 재생·16전송 일치·거부1개 무전송·원문/소스 보존·viewer/보고·정리를 완료했다. 실행 source295파일을 봉인했고 사후에는 거부 응답 감사 지원만 추가했다.
- [최종 보고](../../../exec-plans/evidence/ep062/report.md), [실제 감사](../../../exec-plans/evidence/ep062/live-audit.json), [정리](../../../exec-plans/evidence/ep062/closure.json). 현재 수집·감시 없음.2경기 정상 종료 기준 미달로 Blocked 보존.

- 후속 [EP-063](EP-063-jev-probability-validation.md)에서 사용자 지적으로 새 합계 검사를 제거하고 저장17응답을 오프라인 검증했다. EX-047 실제 재개0이며 완주 미완료는 유지한다.
