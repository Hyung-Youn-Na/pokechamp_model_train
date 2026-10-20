# D-136 — 교정된 v6의 새64경기 평가 승인

- Status: Accepted
- Date: 2026-10-13
- 승인: 수정본으로 별도 새64경기를 실행하자는 제안에 대한 사용자의 “승인하겠습니다. 재개해주세요.”

EX-086의 진영/포켓몬 대상 구분 결함과 사후 집계 경로 충돌을 교정·CPU 검증한 소스로
27B→9B 각32경기를 새로 실행한다. EX-086/087과 EP-140의 실패·미실행·원자료·뷰어·봉인은
변경하지 않는다. 새 실험은 EX-088/089, 실행 단위는 EP-141이다. 이전26추론은 별도 사용량으로
연결하며 새 성적에 계승하지 않는다.

기존 질문·처치 의도·모델/revision·정책·대진·자원·최대8사전추론/단일 적재·감사·뷰어·해석은
유지한다. 새 조건의 원문은 [EX-088](../experiments/EX-088-jev27b-v6-corrected.md)과
[EX-089](../experiments/EX-089-jev9b-v6-corrected.md), runtime은
[C-067](../CONTRACTS.md#c-067-jev-public-memory-v6), 진행은
[EP-141](../exec-plans/completed/EP-141-jev-v6-corrected-evaluation.md)이다.
