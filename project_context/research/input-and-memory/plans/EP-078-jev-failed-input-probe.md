# EP-078 — 실패 입력 현재 응답 확인

- 상태: Completed
- 생성일: 2026-09-21
- 승인: 사용자 동일 입력 현재 호출 / D-086

## 범위

INDEX/CHARTER·현재 STATUS/색인·겹치는 EP-077/075/064/062 및 C-044/D-084를 확인했다.
[EX-055](../experiments/EX-055-jev-failed-input-probe.md)의 독립 probe를 수행한다.
새 evidence/ep078·등록/상태 문서만 쓰며 과거 source/실험은 변경하지 않는다.

## 완료 기준

- [x] 모의 전송으로 동일 body·횟수·기록 경계 확인
- [x] 승인된 독립 호출·결과/usage·원자료 보존·연결 정리·보고

비배틀 진단이며 중단·복구·분모는 EX-055 원문을 따른다.

## 결과

첫 시도 HTTP200·실측10,515입력 토큰·재시도0. 연결 종료·과거 보존 확인. [보고](../../../exec-plans/evidence/ep078/report.md).
