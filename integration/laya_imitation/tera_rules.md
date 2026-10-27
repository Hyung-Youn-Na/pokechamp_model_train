# 테라 규칙표 tera-rules-v1 (EX-124 지식 자료의 근거)

지식 행의 정답은 이 규칙과 `tera_rules.json` 상수, 타입표(`dex_gen9_v2.json`), 고정 calc로 계산한다.
1차 근거는 로컬 고정 Showdown 엔진(`pokemon-showdown` `e64915c0e`)이다. 웹 문서는 교차 확인에만 썼다.
웹 문서 텍스트는 학습 자료에 넣지 않는다.

| 규칙 | 엔진 근거 | 웹 확인 |
|---|---|---|
| 배틀당 1회, 한 마리. 테라하면 같은 편 전원 `canTerastallize = null`. 기절해도 복구되지 않는다 | `sim/battle-actions.ts` `terastallize()` | Serebii "once per battle" |
| 그 턴의 기술보다 먼저 처리된다 | `sim/battle-queue.ts` 행동 순서 `terastallize: 106`, 기술 기본 200 | – |
| 교체 후에도 유지된다 | `sim/pokemon.ts` `clearVolatile`이 `terastallized`를 해제하지 않음 | – |
| 방어 타입은 테라 타입 하나. Stellar는 원래 타입 유지 | `sim/pokemon.ts` `getTypes()` | Serebii "changes its entire type to a single pure type" |
| 자속: 원래 타입 1.5 유지, 테라 타입 1.5, 같은 타입이면 2 | `sim/battle-actions.ts` STAB 블록(`terastallized === type && getTypes(false, true).includes(type)` → 2) | Serebii |
| Adaptability와 같은 타입 테라면 2.25 | `ModifySTAB` 이벤트(Adaptability) | Serebii "2.25" |
| 테라 타입 기술 위력 60 미만은 60. 우선도·연속기·가변 위력 예외 | `sim/battle-actions.ts` `basePower < 60 && … terastallized && priority <= 0 && !multihit` | Serebii(예외 목록) |
| Tera Blast: 테라 시 테라 타입, 공격 > 특수공격이면 물리 | `data/moves.ts` `terablast.onModifyType/onModifyMove` | – |
| 상대 테라 타입은 테라 전까지 비공개 | 공개 프로토콜(`-terastallize`)에서만 드러남 | – |

교차 확인 자료: [Serebii Terastal](https://www.serebii.net/scarletviolet/terastal.shtml).
Bulbapedia는 접근이 거부(403)되어 확인하지 못했다.
