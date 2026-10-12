# D-052 — B2의 별도 LLM 선봉 정책

- 상태: Accepted
- 날짜: 2026-09-14

## 근거·결정

사용자가 EP-036 교정 source의 B2에 선봉 한 마리 선택을 추가하고 무유료 검증까지 완료하도록 명시했다.
새 `b2-llm-lead-v1` 정책에서 B2 전달을 허용하는 C-033을 추가한다. C-031의 EX-038 한정과 당시 hash는 그대로 유지한다.
actor별 `team_preview_policy` 기본값은 `seeded_random`, opt-in은 `llm_lead`다.
두 조건의 전투 중 B2 구성은 같으며 현재 모델 설정을 상속한다. 구현·로컬 검증만 승인했고 실제 수집은 미승인이다.

동기 upstream preview를 async 메서드로만 교체하면 coroutine이 전송되는 문제가 있으므로 parent 요청 경계에서
동기 backend를 별도 thread에 실행하고 완료를 기다린 후 검증된 명령을 전송한다.
공개 preview가 자기 상세 request보다 먼저 올 수 있으므로 첫 공개 알림 때 RNG 순열을 보존하고
두 신호를 모두 받은 뒤 입력을 고정한다. 이후 protocol은 읽지 않는다.
기존 actor RNG의 shuffle을 한 번 수행한 뒤 선택 슬롯만 이동한다. 중복 preview는 최초 요청/결과를 재사용하고 중복 전송을 막는다.
전용 prompt는 자기 제출 슬롯/알려진 정보와 상대 공개 preview만 받고 엄격한 단일 JSON 슬롯을 출력한다.
기존 Cloud의 admission·예산·시계·원문 보존을 재사용하며 실패는 명시적 선발 실패다.

## 대안·제한

Pinned VGC `llm_vgc_player.py:1393`의 4마리 선택·무작위 fallback은 참고 evidence다.
Gen9 OU 6마리 유지/선봉 하나/실패 폐쇄 계약과 다르므로 해당 구현은 복사하지 않는다.
EX-038은 A 대 B2이며 parser 결함으로 중단됐다. 과거 B와의 부분 성적 유사성은 동등성/압축 효과 근거가 아니다.
새 로컬 성공은 과거 유효화·provider 검증·승률 개선이 아니다.

검증 및 구현 범위는 [EP-040](../exec-plans/completed/EP-040-llm-lead.md), 계약은 [C-033](../CONTRACTS.md#c-033-llm-lead)를 따른다.
