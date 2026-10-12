# D-110 — 기존 test 대진의 Kev 본 배틀

- 상태: Accepted
- 날짜: 2026-10-01
- 승인: 사용자가 연결 검증 완료 뒤 추가 사전 검증 없이 본 테스트 경기를 요청하고, 기존80경기 중 test 분할을 먼저 확인하도록 지시했다. 이에 확인된 EX-065 test20 일정으로 본 실행을 구체화한다.
- 관련: [EX-069](../experiments/EX-069-kev-test-battles.md), [EP-112](../exec-plans/active/EP-112-kev-test-battles.md)

EX-065 manifest의 test5팀·팀당4seed, 총20개 고정 대진을 사용한다. 새32대진/64경기 제안은
채택하지 않는다. 자기 팀·p2·상대 Abyssal·simulator/actor seed는 원 manifest를 따른다.
원 test 대진의 메타데이터를 live 경기 설정에 사용하는 범위이며 Kev suite의 잠긴
`test.jsonl`·저장 test 입력/타깃을 읽거나 설정 선택에 사용하는 승인은 아니다.

EX-068에서 재현·실전 연결을 통과한 bf16/T1/merged/fused checkpoint와 입력/선택 구현을
그대로 사용한다. 사용자 지시로 추가 단위검사·validation probe·smoke는 생략한다.
이는 실제 요청의 rqid/합법성/응답 검사, 실행 기록·종료 후 감사/뷰어를 제거하는 지시가 아니다.
서버는 이미 승인된 동일한 방식으로 `/ref/kev`에서 GPU3만 사용하여 시작하고 종료 시 정리한다.

본 실행은 새 EX-069 원장으로20경기를 한 번씩만 시도하며 EX-068의 봉인·admission을 유지한다.
고정 test20경기의 원 Abyssal 결과는 실행 조건을 동결한 뒤 결과 비교에만 읽는다. 원 선택·
숨은 상태·타깃은 Kev 입력에 전달하지 않는다. 과거 시뮬레이터 실행과 새 live 실행의 차이는
명시하고, 통제되지 않은 차이를 학습의 단독 인과 효과로 해석하지 않는다.
