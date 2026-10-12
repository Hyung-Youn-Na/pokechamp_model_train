# D-053 — EX-039 선봉 정책 비교 실행 승인

- 상태: Accepted
- 날짜: 2026-09-14
- 근거: [명시적 사용자 지시](../exec-plans/evidence/ep041/user-instruction.txt)

사용자는 EX-039 준비에서 끝내지 않고 실제 비교·분석·보고·정리까지 수행하도록 지시했다.
D-052/C-033의 준비 한정을 이번 EX-039에 한해 확장한다. 상세 동결 조건의 원문은
[EX-039](../experiments/EX-039-b2-lead-proposal.md), 구현·진행은 [EP-041](../exec-plans/active/EP-041-b2-lead-comparison.md)다.
사용자가 [후속 지시](../exec-plans/evidence/ep041/user-money-amendment.txt)로 금액을 고려 대상에서 제외했다. 금액 상한을 적용하지 않고 요청/시간 상한을 유지한다.
나머지 승인 범위를 재확인하지 않는다. 별도 유료 smoke 없이 첫 제출 슬롯의 대응쌍2경기를 본32에 포함해 기술 gate로 사용한다.
gate 성공 후 같은 source·원장·최초 시계로 나머지30을 제출하며 실패 시 재시도 없이 후속 제출을 중단한다.
기존 Blocked와 실험은 재개하지 않는다. C-032 설명 annotation 제외와 C-018 영향범위 중단·보존을 유지한다.
전투 정책·모델·팀은 유지하며 parent 실행/예산/평가/보고 연결 구현만 승인한다.

사용자는 수집 중 계정 사용량을 알린 뒤 진행 중 경기는 유지하고 미제출 경기는 보류하도록 명시적으로 지시했다. 이 후속 운영 지시를 우선 적용하며, [원문·적용 기록](../exec-plans/evidence/ep041/operator-submission-hold.json)을 보존한다. 이미 제출된20경기의 종료·부분 분석은 계속하고 미제출12경기를 자동 제출하지 않는다. 동일 source·처치·원장·최초 요청/수집/정리 시계와 재시도0은 유지한다. 보류는 상한 초기화·중단 후 재수집 승인으로 해석하지 않는다.

이후 사용자는 감시도 모두 종료하도록 지시했다. 현재 실행과 감시를 정리하고 미실행 슬롯을 보존하며 자동 재개하지 않는다. [종료 지시 원문](../exec-plans/evidence/ep041/closure/user-instruction.txt)과 [종료 기록](../exec-plans/evidence/ep041/closure/report.md)을 연결한다. 공급자 설정 변경이나 새 수집 조건은 이 종료 지시에서 확정하지 않았다.
