# D-075 — 판단 오류 비중단 적용 JEV 재실행

- 상태: Accepted
- 날짜: 2026-09-21
- 승인: 사용자 중단 실험 재실행 지시

D-074의 판단 오류 비중단 규칙을 JEV 실행기에 구현·검증하고 새2경기를 수행한다.
조건은 [EX-049](../experiments/EX-049-jev-judgment-repeat.md), 구현 계약은 C-045/046,
진행·검증은 [EP-066](../plans/EP-066-jev-judgment-repeat.md)이다.
choice-action-v3는 합법 choice를 그대로 실행한다. 보조 점수는 진단이며 실행 불가능 응답은
해당 경기만 실패로 종료한다. 기존 v1/v2 감사와 EX-047/048의 동결 자료·판정은 유지한다.
기술·통신 오류와 상한을 판단 오류로 완화하지 않는다. 추가 재시도·대체행동·보충0이다.

준비 오류 복구: EX-049 API0/cwd 실패 후 RD11.1에 따라 [EX-050](../experiments/EX-050-jev-judgment-recovery.md)으로 같은 승인·상한을 연결한다. 추가 유료 수집 예산은 없다.
