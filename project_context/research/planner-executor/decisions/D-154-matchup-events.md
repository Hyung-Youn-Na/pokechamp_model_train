# D-154 — 매치업 변화 기반 계획 갱신

- 상태: Accepted
- 날짜: 2026-10-15
- 승인: 현재 사용자 제공 EX-101 계획의 구현·검증·실제1경기 지시

EX-100을 기준으로 주기 호출을 제거하고 공개 교체·현재 출전 폼 변화 사건을 명시 선택한다.
공통 기본값과 기존 실험은 유지한다. 호출의 runtime 의미는 C-070, 처치·한도·검증·해석은
[EX-101](../experiments/EX-101-matchup-events.md), 진행은 EP-160에서 관리한다.
이 지시는 새 경기1회와 기존 상한 안의 사전8추론/API를 승인하며 재경기·대체모델·자동재개는 금지한다.

공개 사건 분류는 [공식 프로토콜](https://github.com/smogon/pokemon-showdown/blob/master/sim/SIM-PROTOCOL.md)의
switch/drag/replace·detailschange/-formechange/-transform 및 식별자 규칙을 따른다.
출전 대상에는 position letter가 있고 비출전 대상에는 없으므로 벤치 폼 변화를 제외한다.
