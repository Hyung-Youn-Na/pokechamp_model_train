# D-043 — Protect 만료 정규화 교정

- 상태: Accepted
- 날짜: 2026-09-11

사용자가 EX-036에서 발견된 만료 PROTECT 잔존 오류의 구현·오프라인 검증을 명시적으로 승인했다.
B 정규화만 공개 protocol의 발생 이후 turn/upkeep·교대·기절·명시적 해제로 수명을 판정한다.
parser_effects는 원형 보존하고 계산용 effects에서 입증된 만료만 제거하며 공개 활성 누락을 보완한다.
근거 부족·모순은 제거하지 않는다. 계산기의 현재 PROTECT 거부는 유지한다.

이는 기존 현재 효과 의미를 복구하는 bugfix이며 CLI/입력 schema/프롬프트/계산식/calculator-input-v2를
변경하지 않는다. 내부 수명 자료는 입력에 추가하지 않고 별도 재현 보고서에 event/line 근거를 남긴다.
새 source hash와 protect-expiry-v1 검증으로 식별하고 과거 qualification을 재사용하지 않는다.
A·공통 parser·pinned submodule·과거 기록·EX-036 중단 및 EP-030 Blocked는 보존한다.
유료 재실행·비교 완료·다른 효과 지원 확대는 승인 범위 밖이다.
[EP-031](../exec-plans/completed/EP-031-protect-expiry.md)에 완료 기준을 등록한다.
