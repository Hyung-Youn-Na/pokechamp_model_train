# EP-018 — 요약 없는 improved_io A/B 비교

- 상태: Blocked — 구현·검증·중단 보고 완료, Cloud gate 미충족으로 비교 미완료
- 생성일: 2026-09-09
- 책임자: Codex
- 승인: 현재 사용자 계획 전체 구현·검증·조건부 유료 실행, D-030의4시간/4000호출/복구1차.
- 관련: [D-030](../decisions/D-030-io-battle-only.md), C-018/C-019,
  [EX-026](../experiments/EX-026-io-battle-only.md).

## 목표·범위·불변 조건

Parent integration에 독립 A/B profile과 준비/수집/검토/배틀/복구/보고 CLI를 구현한다.
운영 최근10결정 입력, B 요약0, 기존 A fallback, 공유 예산과 원본 보존을 검증한다.
기존 요약 실험·Blocked·halt·시계를 보존하고 요약 prompt/전략/prior/계산기는 유지한다.

## 완료 기준

- [x] 기존 integration 회귀와 추가 계약/예산/복구 검사
- [x] 15장면 운영 입력·독립 의미/실제 입력 도달성 및 사후 피해3 검증·사전 봉인
- [x] fake32 유효32/32·실제 동시성10·격리/정리·B31행동 요약/archive0
- [ ] B Cloud90의 기술/의미 gate 통과
- [ ] smoke8 유효8/8·실제 동시8·요약0 및 본 비교 시간 적합성
- [ ] compare32 유효32/32·16대응·근거 연결 검토·분모/비용/오류/효과 보고
- [x] 증거 보존·자원 정리·상태 갱신

## 중단·복구

[D-029 절차](../../../RESEARCH_DESIGN.md#defect-recovery)/[C-018](../../../CONTRACTS.md#c-018-recovery)
및 D-030 단계 gate를 따른다. 새 profile의 복구 경로 검증 전 유료 복구는 실행하지 않는다.
유료 재수집 최대1차, 영향 A/B 양쪽·공유 영향 전체, 누적180/16/64 및4000요청,
최초4시간/신규3시간45분이다. 과거 halt 삭제/receipt 덮어쓰기/시계 초기화는 금지한다.
결함·독립 검증·무효·원본/수정 identity는 EX-026 하위 봉인 recovery record로 연결한다.

## 진행 및 검증

2026-09-09: 계약·연구 설계·겹치는4개 active plan 확인. 기존 자료/active plan 해시를
[보존 inventory](../../../exec-plans/evidence/ep018/preservation.json)에 기록. 신규 등록, Cloud0.

2026-09-09: 새 profile·요청 원장·복구/재자격·보고 경로 구현. 최종362회귀(147.51초),
변경 범위 Ruff E/F/I/W·compileall·Node13 통과. 기존 broker release fixture의 인터페이스
호환 실패를 수정한 뒤 전체 재검증했다. 운영15입력/독립 의미·도달성 및 사후3 통과.
초기 로컬 기준의 효과 counter=1 가정을 실제 SpA 발동 존재 검사로 교정했으며 Cloud0이다.
[준비 receipt](../../../../.pokechamp-data/io-battle-only/ex026-preflight/prepare/result.json),
[회귀 로그](../../../exec-plans/evidence/ep018/regression-final.log). 같은 source로 fake32 실행 중.

Fake32 유효32/32, 실제 동시10, runtime B16 actor·요약/통합0·격리 오류0·포트 정리 통과.
[사전 검증 봉인](../../../../.pokechamp-data/io-battle-only/ex026-preflight/verification.json)을
확인하고 c0의 행동 Cloud90을 시작한다. 최초 시계·요청 원장은 새 EX-026 study에만 생성한다.


최초 Cloud1/1을6.97초에 봉인한 후 ASCII 검사에서 범위 대시가 거부되어 c0 halt를 보존했다.
입력96933/출력183 tokens, HTTP200, 미확정0이다. 원래 영문 계약과 ASCII 구현의 불일치를
[독립 재현](../../../../.pokechamp-data/io-battle-only/ex026/defects/english-typography-reproduction.json)했다.
기존 응답의 검증 판정만 교정하고 미제출89를 수집할 e1 경로를 추가했다. 로컬37검사에
실제1응답+89미실행의 fake 복구와 총90/원본/시계 불변을 포함해 통과했으며 전체 회귀 재검증 중이다.
새 source의 운영15장면/독립 의미·도달성/사후3은 통과했다. 아직 실제 추가 호출0이다.


## 최종 상태 — 2026-09-09

평가 교정 후 전체 **367 tests(171.63초)**, 추가 복구 검사37건, Ruff/compileall/Node13,
운영15장면·독립 의미/입력 도달성·사후3 및 새 fake32 유효32/32가 통과했다.
새 fake32 실제 동시배틀10·요약/통합0·격리/정리 통과이며 source139개를 고정했다.
[최종 회귀](../../../exec-plans/evidence/ep018/regression-e1.log),
[복구 검증 봉인](../../../../.pokechamp-data/io-battle-only/ex026/defects/english-typography-verification.json).

e1은 원본1응답을 재평가해 재사용하고 미제출 ID 중3개만 새로 수집했다. 네 번째 응답이
설명과 행동 JSON을 한 줄로 출력해 정해진 마지막 줄 JSON 계약을 위반했으므로 중단했다.
총4요청/4봉인/미확정0, 출력 유효3/4, 미실행86/90이다. 4응답 전부를 검토했고
IO-C03의 면역 시점 오류(현재5턴, 면역3턴을 지난 턴으로 서술), IO-C04의 Poison Heal
회복을 누락한 두 번 명중 KO 단정을 확인했다. 모델 오류이며 추가 복구·재수집하지 않는다.
수집을 중단한 원인은 출력 오류이며, 별도 사후 의미 검토에서도 gate 미달이다.

Smoke8과 본 비교32는 모두 미실행, 유효 대응0/16이다. 최초4시간 중24.03분에 정리 검증을
마쳤고 예산 소진으로 중단한 것은 아니다. 입력193,606/출력920 tokens, 요약/통합0,
유료 재수집0이다. 의미 오류율2/4는 수집된 gate 응답의 진단값이며 배틀 오류율/성능이 아니다.
구현·로컬 검증·수집분 검토·중단 보고·정리는 완료했지만 90 gate·8판·32판 완료 기준은
미충족이므로 이 plan은 active 디렉터리의 Blocked로 유지한다.

[최종 보고서](../../../../.pokechamp-data/io-battle-only/ex026/final-report/report.md),
[Cloud 검토 결과](../../../../.pokechamp-data/io-battle-only/ex026/gate-e1/result.json),
[정리 검증](../../../../.pokechamp-data/io-battle-only/ex026/closure-verification.json):
기존41,474파일·기존4개 active plan 불변, 로컬128 actor seal 및 새139 source 일치,
134개 해시 sidecar·새2965파일 credential 검사, pinned submodule/소유 프로세스/포트 정리 통과.
과거 halt/시계와 이번 c0/e1 halt·최초 시계는 보존했다. 요약 실험의 Blocked는 유지한다.
