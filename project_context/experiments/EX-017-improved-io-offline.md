# EX-017 — 개선 IO 오프라인 검증

- Status: Stopped
- 날짜: 2026-09-08
- 관련: [D-019](../decisions/D-019-improved-io.md), [EP-011](../exec-plans/active/EP-011-improved-io.md)
- 조건: A=upstream IO, B=개선 fixed IO, C=B+배틀 내 요약. 실제 배틀은 시작하지 않았다.

## 사전 범위와 분모

D-019의 단계1을 진행했다. EX-016의 이미 분석된 개발15개 장면만 사용했으며
확증 팀은 사용하지 않았다. 기대15개 원자료 연결/결정 시점 재생을 모두 수행했다.
그 중 고정 계산기와 실제 결과의 사후 대조3건을 수행하고2건 일치/1건 불일치를 확인했다.
이는15개 의미 rubric 전체 통과나 기술적 완료를 의미하지 않는다.

## 결과와 중단

| 장면 | 고정 계산기 피해 | 원자료 관측 | 판정 |
|---|---|---|---|
| IO-C01 Draco Meteor |576–678, 정답 최대HP415|event17 Hydrapple 기절|기절로 cap된 관측과 일치|
| IO-C02 Earthquake |0–0|event31 Air Balloon Tinkaton 면역|일치|
| IO-C03 Ruination |0–0|event43 Tinkaton100→51/100|불일치; gate 실패|

`@smogon/calc`0.11.0의 미지원 기술을 정상0피해로 취급할 수 없어 단계1에서 중단한다.
원자료를 보존한 후 parent wrapper에 Ruination의 명시적 rejection을 추가했다.
패키지/프롬프트를 수정해 같은 identity의 실험을 이어가지 않았다.

- 병렬 fake12: 예정12/시도0/완료0/실패0/미실행12.
- Cloud 행동 gate: 예정180/시도0; 요약·통합 호출0.
- Cloud smoke12: 예정12/시도0/완료0/실패0/미실행12.
- 비교48: 예정48/시도0/완료0/실패0/미실행48.
- Cloud 호출0, Cloud4시간 시계 미시작. 순차 배틀 전환 및 실패 보충 없음.
- 유효 승패 분모0이므로 점수·조건 차이·속도비를 계산하지 않는다.

## 증거

- [구조 재생 receipt](../../.pokechamp-data/io-improvement/ep011-offline-v1/result.json)
- [사후 불일치 receipt](../../.pokechamp-data/io-improvement/ep011-posthoc-v1/result.json)
- [당시 source seal](../../.pokechamp-data/io-improvement/ep011-posthoc-v1/source.json)

전자는15개 입력의 구조 재생 성공만 기록하며 `offline_gate_passed=false`다.
원본 source/event는 수정하지 않았다. 상대 정답은 `posthoc.py`에서만 읽고 행동 입력에 넣지 않는다.
HP 관측은 반올림 또는 기절 cap이 있으므로 uncapped 실제 server damage를 안다고 주장하지 않는다.

최종 회귀163 tests 및Ruff/Node syntax/compileall,68 source archive hash와 원 receipt seal,
submodule clean 및8100–8109/process 정리를 확인했다. 이는 미실행 배틀의 유효 완료를 뜻하지 않는다.
