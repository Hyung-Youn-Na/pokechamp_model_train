# D-141 — Planner/JEV 후보 표시 이름

- 상태: Accepted
- 날짜: 2026-10-15
- 승인: 현재 사용자 `표시 이름을 추가해줘` 지시

새 planner–JEV 입력의 후보 객체에 display_name을 추가한다. 현재 자기 팀/기술 슬롯에서
포켓몬·기술 이름을 해석하고 일반/Tera·선봉/교체를 구분한다. 실행 ID·슬롯·move_ref·후보순서·
명령은 그대로 유지한다. 숫자 ID의 교체가 아닌 모델에 전달되는 설명 추가다.

새 설정의 executor.candidate_display 기본값은 names-v1이다. original과 필드가 없는 과거
동결 설정은 원 입력을 보존한다. 이름 추가는 별도 입력 표현 조건이며 planner on/off 양쪽에
같이 적용한다. 실제 성능 개선은 주장하지 않고 과거 실험·준비본·뷰어는 보존한다.
런타임·검증은 [C-072](../CONTRACTS.md#c-072-candidate-display-names), 진행은
[EP-147](../plans/EP-147-candidate-display-names.md)을 따른다.
