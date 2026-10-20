# D-140 — Planner 역할·승리 경로·자원 관리 안내

- 상태: Accepted
- 날짜: 2026-10-15
- 승인: 현재 사용자의 planner 계산 해석 중심 안내를 역할 기반 거시 전략으로 변경 요청

새 planner 설정의 기본 안내를 역할·양측 승리 경로·핵심 자원 보존/소모 중심으로 바꾼다.
현재 Gen9 OU singles에 맞춰 경쟁 싱글 전략 문헌의 일반 원칙을 참고한다. 과거 세대의 포켓몬별
세트·위협 순위나 VGC 더블 규칙은 채택하지 않으며 모든 프로 선수의 유일한 방식이라고 주장하지 않는다.

`prompts.guide`의 별도 파일을 role/compact·conditional 지시문과 함께 동결한다.
계산식 장문과 일반 규칙 목록을 붙이는 기존 방식은 guide가 없는 과거 준비 설정에서 보존한다.
현재 관측·후보·피해/스피드 값과 수행 모델 입력은 유지하고, 수치는 역할 계획의 가능성을 검토하는
보조 근거로 해석한다. 역할은 고정 종족 라벨이 아닌 현재 대진에서 수행할 임무이며,
상대 role_summary는 가능한 가설이고 실제 세트·의도라는 확정 사실이 아니다.

원문 근거·적용 범위는 [설계 메모](../../docs/pokechamp-planner-macro-strategy.md), 방법은
[RD planner절](../RESEARCH_DESIGN.md#jev-planner-environment), runtime은
[C-071](../CONTRACTS.md#c-071-planner-role-guide), 진행은
[EP-146](../exec-plans/completed/EP-146-planner-role-resource-guide.md)을 따른다.
출력6필드·호출정책·모델·평가·기존 실행/봉인은 보존하며 실제 API/GPU/배틀 실험은 이번 범위 밖이다.
