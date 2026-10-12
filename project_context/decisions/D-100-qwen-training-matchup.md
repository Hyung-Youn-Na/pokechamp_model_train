# D-100 — Qwen 학습 원대진 실전 진단

- 상태: Accepted
- 날짜: 2026-09-29
- 승인 근거: 사용자의 “해당 qwen 모델 기반으로 배틀 실험… 학습에서 사용된 jev 1경기 매치업 데이터와 같은 매치업” 지시.

EX-061 최종 모델을 GPU1에서 서빙하여 EX-058 battle-19의 원대진을 새 1경기로 실행한다.
Abyssal p1/team6·Qwen p2/team2, 원 게임/actor seed와 공개 preview 성별을 유지한다.
사용자가 원대진을 지정했으므로 D-091의 새 팀 후보 목록 제한에는 이 재현 대진만 예외다.
현재 신규 팀 선택 기준과 기존 EX-062/EP-103의 Blocked·원자료는 바꾸지 않는다.

방법과 해석은 [RD](../RESEARCH_DESIGN.md#qwen-training-matchup), runtime은
[C-049](../CONTRACTS.md#c-049-qwen-local), 조건·분모·복구는
[EX-063](../experiments/EX-063-qwen-training-matchup.md), 진행은
[EP-104](../exec-plans/completed/EP-104-qwen-training-matchup.md)가 소유한다.
원 JEV는 12턴 패배했지만 새 승리를 보장하지 않는다. 학습 대진 개발 진단으로 분류하며
학습 전 Qwen 배틀 기준선이 없으므로 학습의 인과 효과나 일반 성능 개선을 주장하지 않는다.
