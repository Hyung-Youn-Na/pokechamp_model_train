# Bounded Memory 지식 계층 템플릿 정리 (L1–L5)

> AgenticSTS의 핵심 설계 — **bounded memory contract**. 모든 결정 d는 상태 s_d에서
> 5개 지식 계층으로부터 **타입-검색(typed retrieval)**된 새로운 사용자 메시지로 이루어진다.
>
> ```
> u_d = π(L1, L2(s), L3(s), L4(s), L5(s))
> ```
>
> 원시 교차-결정 트랜스크립트는 결코 프롬프트에 추가되지 않는다. 따라서 프롬프트 크기는
> 실행 길이에 무관하게 **제한(bounded)**된다. 결정마다 시스템 프롬프트(L1)는 캐시된 채로
> 두고, L2 결정 템플릿 + L3 지식 + L4 메모리 + L5 스킬만 상태에서 fresh하게 조립되어
> 한 번의 user message로 들어간다.

---

## 0. 5계층 한눈에 보기

| 계층 | 내용 | 변이성 | 저장 위치 | 코드 |
|---|---|---|---|---|
| **L1** | 4개 정적 시스템 프롬프트 (COMBAT / COMBAT_BOSS / DECKBUILD / STRATEGIC) | **불변** | `src/brain/prompts/system.py` | `system.py` |
| **L2** | 상태 타입별 결정 프롬프트 템플릿 (스키마 + 합법적 액션 형식) | **불변** | `src/brain/prompts/*.py` | `map.py` `event.py` `rest.py` `shop.py` `reward.py` `card_select.py` `hand_select.py` `treasure.py` `potion.py` `distill.py` |
| **L3** | 게임 지식 (카드/몬스터/포션/유물/이벤트/키워드) | 정적, 패치 갱신 | `src/knowledge/` + `data/knowledge/` | `injector.py` + `*_lookup.py` |
| **L4** | 에피소드 메모리 (포스트런 요약·가이드) | 포스트런 기록 | `src/memory/` → `AgenticSTS-Data/memory/` | `retriever.py` `prompt_injector.py` `models_v2.py` |
| **L5** | 스킬 라이브러리 (트리거 제어 전술 가이드) | 제어된 기록 | `src/skills/` → `AgenticSTS-Data/skills/` | `models.py` `composer.py` `mistake_discovery.py` |

**불변성 규칙(load-bearing).** 포스트런 LLM은 **L4 메모리 / L5 스킬 / 동적 도구만** 기록할 수 있고
**L1/L2는 결코 편집하지 않는다.** 과거 Prompt Evolution(PE) 파이프라인이 10일간 33개의
L1/L2 패치를 제안했으나 **33/33이 A/B 검증에서 실패** (30 INVALID_B, 2 개선 없음, 1 커버리지 부족).
이후 PE는 제거되었고 L1/L2는 인간이 PR 또는 `scripts/apply_patch.py`(게임 버전 업데이트용)로만 편집한다.
→ `docs/superpowers/specs/2026-04-18-pe-deprecation-negative-result.md`

---

## 1. 결정별 프롬프트 조립 파이프라인

하나의 결정 d가 만들어지는 순서 (`src/agent/loop.py` → `src/brain/v2_engine.py`):

1. **상태 관찰** — `GET /state` → `GameState`(`src/state/game_state.py`, frozen Pydantic).
2. **모델 티어 라우팅** — `_get_v2_tier(state_type)`가 4티어 중 하나 선택
   (`fast` / `strategic` / `analysis` / `evolution`).
3. **시스템 프롬프트 선택 (L1)** — `get_system_prompt(state_type)`가
   `_STATE_SYSTEM_MAP`에서 상태 타입 → 4개 시스템 프롬프트 중 하나 매핑.
   `cache_control: {"type":"ephemeral"}`로 캐싱(4개 모두 정적).
4. **결정 프롬프트 템플릿 조립 (L2)** — 상태 타입별 빌더(`build_*_prompt`)가
   `## 상태 / 덱 / 유물 / Available Cards / Decision Format` 블록을 생성.
5. **지식 주입 (L3)** — `KnowledgeInjector.inject_*`가 토큰 예산 내에서
   카드/몬스터/포션/키워드/인카운터 메커닉을 주입.
6. **메모리 검색·주입 (L4)** — `retriever.query_for_decision`이 결정 타입별로
   도메인 스토어/가이드/단기기억에서 힌트를 모아 `WorkingContext`를 만들고
   `prompt_injector.format_working_context`가 결정 타입별 헤더로 포장해 주입.
7. **스킬 주입 (L5)** — `SkillLibrary.query`가 트리거 매칭으로 스킬을 검색하고
   `composer.compose_skill_context`가 `## Expert Knowledge (retrieved skills)` 블록 생성.
8. **실행** — `<decision>` JSON → `decision_parser` → `POST /action`.

모든 L2/L3/L4/L5 주입은 `## Your Task` 섹션 **앞**에 삽입된다
(`composer.inject_skills_into_prompt`, `prompt_injector._insert_before_task`).

---

## L1 — 불변 시스템 프롬프트

**위치:** `src/brain/prompts/system.py`
**변이성:** 불변 (인간 PR / 게임 버전 패치로만 변경)
**캐싱:** 4개 모두 정적 → Anthropic `cache_control: ephemeral` (system 메시지에 적용)

### 1.1 구조 = `_SYSTEM_BASE` + 문맥별 섹션

모든 변형은 공통 베이스 `_SYSTEM_BASE`(`system.py:15-33`)에 문맥별 섹션을 붙인다.

`_SYSTEM_BASE`가 정의하는 것:
- 정체성: "autonomous Slay the Spire 2 agent … maximize chance of defeating Act 3 boss"
- **출력 형식**: `<decision>` 태그 안에 **유효한 JSON**. `reasoning` 필드 필수.
  전투 plan의 `plan` 배열은 실행 순서(item 1 → item 2 …) 그대로.
- 맵 결정 예시 + 전투 plan 예시(JSON 스키마 형태).

### 1.2 4개 시스템 프롬프트

| 변형 | 대상 상태 | 추가 섹션 | 핵심 철학 |
|---|---|---|---|
| `SYSTEM_COMBAT` (`:37`) | monster / elite / hand_select | Core Combat Rules + **HP Conservation** | HP는 런 전체 자원; 방어 우선, 포션 타이밍 |
| `SYSTEM_COMBAT_BOSS` (`:58`) | boss | Core Combat Rules + **Boss Fight Strategy** | 보스 후 HP 완전 회복; HP를 속도로 교환, 포션 총동원, 스케일링 우선 |
| `SYSTEM_DECKBUILD` (`:80`) | card_reward / card_select / shop | Card & Deck Philosophy + **Two-Phase Framework** + `strategic_note` 출력 | 4차원 평가 + Foundation/Commitment 2단계 |
| `SYSTEM_STRATEGIC` (`:132`) | rest_site / map / event | Run-Wide Strategy + `strategic_note` 출력 | HP 런 자원, Smith 기본값, 포션 타이밍 |

### 1.3 전투 핵심 규칙 (COMBAT / COMBAT_BOSS 공통, 9개)

`system.py:40-48` — 모든 전투 프롬프트에 동일하게 들어가는 기계 규칙:
- 턴 구조(5드로/3에너지/블록 리셋), 핸드 리셋, 핸드 10장 제한,
  블록 리셋, 에너지 리셋(모두 사용), 적 인텐트 가시,
  드로우 즉시 해결, **드로우 파일은 예측이지 예약이 아님**,
  **생성 카드 큐잉**(Blade Dance→Shiv 등 생성 카드의 play를 같은 `plan`에 generator 뒤로 배치).

### 1.4 `strategic_note` 출력 계약 (DECKBUILD / STRATEGIC)

`SYSTEM_DECKBUILD:115-127`, `SYSTEM_STRATEGIC:139-149` — 덱 게임플랜을
**80단어 이내 자연어 한 문장**으로 출력. sticky & actionable:
- 현재 Foundation/Commitment 단계 명시
- 핵심 카드/유물, 시퀀싱, off-turn 역할
- 주요 결핍 조각 + 피해야 할 것
- 엔진 설명은 pivot rule이 허용할 때만 변경

이 `strategic_note`는 포스트런에 `logs/run_*.jsonl`로 기록되어 L4 단기기억
(Strategic Thread)의 원천이 된다 → §L4의 `## Strategic Thread`.

### 1.5 상태 타입 → 시스템 프롬프트 매핑

`_STATE_SYSTEM_MAP` (`system.py:207-221`):

```
monster / elite / hand_select / combat_hand_select  → SYSTEM_COMBAT
boss                                                → SYSTEM_COMBAT_BOSS
card_reward / card_select / shop / bundle_select    → SYSTEM_DECKBUILD
rest_site / map / event / crystal_sphere            → SYSTEM_STRATEGIC
```

`get_system_prompt(state_type)` (`system.py:224`)는 `config.PROMPT_VARIANT`를 읽어
`"full"`(전략 풍부) vs `"baseline"`(기계 규칙 + I/O만, ablation용) 중 선택.

### 1.6 베이스라인 변형 (ablation)

`system.py:152-203` — `PROMPT_VARIANT="baseline"` 시 사용. 전략 휴리스틱(HP 보존·
2-Phase·`strategic_note` 등)을 제거하고 **기계 규칙 + I/O만** 남김.
`SYSTEM_DECKBUILD_BASELINE` / `SYSTEM_STRATEGIC_BASELINE`는
"Choose based on the information available below. Do not include `strategic_note`."만 추가.

---

## L2 — 상태 타입별 결정 프롬프트 템플릿

**위치:** `src/brain/prompts/*.py`
**변이성:** 불변 (인간 PR로만 변경)
**형식:** 각 빌더 함수 `build_*_prompt(gs, ...) -> str`이 마크다운 문자열 반환.
L1 시스템 프롬프트가 아닌 **user message 본문**을 만든다.

### 2.1 공통 레이아웃 (모든 L2 빌더)

```
## <결정 유형>
HP: x/max (r%) | Gold: g | Act: a | Floor: f
Character: … | Deck: N cards
## Relics: …            ← format_relic_hints (context 필터, ~100 토큰)
<지식/메모리/스킬 블록은 이 자리에 v2_engine이 삽입 — L3/L4/L5>
## Available Cards / Options   ← 인덱스 기반 선택지 (뒤쪽에 배치)
## Decision Format       ← v2_engine이 JSON 스키마를 append
```

설계 원칙: **옵션 목록과 결정 스키마는 가장 뒤에** 배치되어 모델이 가장
fresh한 내용으로 읽도록 한다 (`reward.py:101-107` 주석).

### 2.2 L2 빌더 카탈로그

| 파일 | 빌더 | 상태 타입 | 특징 |
|---|---|---|---|
| `map.py` | `build_route_selection_prompt` / `build_map_step_prompt` | map | **2 시나리오**(A: 전체 루트 선택, B: [HERE] 마커 단계 걷기) |
| `event.py` | `build_event_prompt` | event | 6-요소 이벤트 평가 프레임워크 |
| `rest.py` | `build_rest_prompt` | rest_site | 5-요소 휴식 평가, Smith 기본값, 유물 인식 |
| `shop.py` | `build_shop_prompt` | shop | 골드 예산 인식 |
| `reward.py` | `build_card_reward_prompt` / `build_relic_select_prompt` | card_reward / relic_select | 5-요소 카드 평가 + act 인식 + Boss DPS 체크 + Build Trajectory |
| `card_select.py` | `build_card_select_prompt` / `build_pack_selection_prompt` | card_select / bundle_select | 모드 인식(UPGRADE/REMOVE/ENCHANT), upgrade 효과 룩업, 덱 일관성 티어 |
| `hand_select.py` | `build_hand_select_prompt` | hand_select / combat_hand_select | 모드 인식 핸드 선택(discard vs exhaust) |
| `treasure.py` | `build_treasure_prompt` | treasure | 4-요소 유물 평가 |
| `potion.py` | `build_potion_decision_prompt` | potion 사용 | 타입 분류된 포션 결정(damage/block/buff/heal/utility) |
| `distill.py` | `build_distill_prompt` | (포스트런) | 교차 실행 규칙 증류 |

### 2.3 map.py — 2 시나리오 분리 (가장 독특한 구조)

**시나리오 A** `build_route_selection_prompt` (`map.py:20`) — 액트 시작 또는
재계획 트리거 시. 후보 루트 전체를 `routes_text`로 받아 풀 컨텍스트 선택.
```
## Route Selection
HP/Gold/Act/Floor … | Potions | Relics | Strategic Thread | Re-plan reason
## Candidate Routes (from current position to Boss)
<routes_text>
Choose the route … {"route": <number>, "reasoning": "..."}
```

**시나리오 B** `build_map_step_prompt` (`map.py:75`) — 계획이 존재하는 일반 노드 결정.
현재 루트에 `[HERE]` 마커 + 다음 추천 노드 표시. 사용자가 루트에서 벗어날 수 있음
("You may deviate from the route. Explain why if you do.").
```
## Map Navigation
HP/Gold/Act/Floor
Current route: … [HERE] …
Next recommended: <type>(c,r) -- step N of route
Available nodes: - [index=] <type> at c,r  <- route recommends
```

### 2.4 reward.py — 카드 보상 (5-요소 + Boss DPS + Build Trajectory)

`build_card_reward_prompt` (`reward.py:33`):
- `## Card Reward` 헤더 + HP/Gold/Act/Floor + `format_deck_section` + `format_regent_economy`
- 유물, `## Upcoming Act Boss`(`guide_store` 제공 시)
- 포션 슬롯 결정(슬롯 full + claimable 포션 보상일 때만, `reward.py:54-69`)
- `## Available Cards`: `[index=N] Name+ (costE, type, rarity): rules [d dmg | b block | xN hits]`
  + 인라인 경고 + generated cards 인라인 + tier annotation
- **Boss DPS 체크** (`reward.py:209-233`, non-Regent·non-baseline): 보스 HP 목표 →
  필요 DPS 추정 → 딜링 부족 시 데미지 우선, 충분 시 SKIP으로 덱 얇게 유지
- **Build Trajectory 체크** (`reward.py:236-244`): 아키타입 헌신, 희귀도, 스케일링>고정
- `format_card_notes`(흔히 오해되는 카드 메커닉 주석)
- **Regent** 전용: boss-DPS 프레임 생략, `format_regent_offering_summary` 평가 결과(Skip 권장)로 대체

### 2.5 card_select.py — 모드 인식 카드 선택

`build_card_select_prompt` (`card_select.py:179`):
- `kind` + `prompt`에서 모드 추정: `UPGRADE` / `REMOVE` / 기타 SELECT
- 모드별 안내 (`card_select.py:318-324`):
  - UPGRADE: "biggest dimension boost (cost reduction > doubled dmg/block > added draw). Never upgrade basic Strike/Defend."
  - REMOVE: "Curses/Statuses first, then weakest card. Check deck still functions after removal."
- upgrade 모드 시 `_lookup_upgrade_info`가 knowledge DB의 C# DSL
  (`UpgradeValueBy(2m)` 등)을 가독 텍스트로 번역해 카드 옆에 부착 (`card_select.py:51-85`)
- 선택 카드 수: `min_select`/`max_select` + prompt 텍스트 파싱("any number of cards"/"Choose N cards")

### 2.6 출력 스키마 — `## Decision Format`

각 L2 빌더는 옵션 목록까지만 만들고, **`## Decision Format`(JSON 스키마)는 `v2_engine`이
공통으로 append**한다. 스키마는 상태 타입별로 다르지만 공통 계약:
- `<decision>{ … }</decision>` 태그
- `reasoning` 필드 필수 (L1 `_SYSTEM_BASE`에서 강제)
- 전투: `plan` 배열(실행 순서) + `end_turn` + `note_to_future_self` + `analysis`
- 덱빌드/전략: `strategic_note`(80단어 이내) + 인덱스 기반 선택 필드

### 2.7 보조 포매터 (L2 내부 헬퍼)

`_relic_fmt.py`(유물 시너지, context 필터) · `_intent_fmt.py`(인텐트 파싱, `compute_total_incoming`) ·
`_deck_fmt.py`(덱 포맷, `strip_bbcode`) · `_pile_fmt.py`(조건부 draw/discard/exhaust) ·
`_target_fmt.py`(타겟 범위) · `_card_clarifications.py`(오해 카드 주석 + `BOSS_HP_TARGETS`) ·
`_keyword_fmt.py`(키워드 용어집: rules_text 스캔 → 정의 주입) · `_generated_fmt.py`(생성 카드 인라인) ·
`_boss_guide_fmt.py` · `_potion_slot_fmt.py` · `_regent_economy_fmt.py` · `_card_name.py`

---

## L3 — 게임 지식 주입

**위치:** `src/knowledge/injector.py`(주입) + `src/knowledge/*_lookup.py`(룩업) + `data/knowledge/`(데이터)
**변이성:** 정적. 게임 버전 업데이트 시 `scripts/sync_upstream_data.py` +
`scripts/extract_mechanics_from_dll.py`로 재생성. `data/knowledge/`의 일부
(`upstream/`, `*_dll.json`, `afflictions.json`, `powers.json`, `localization/`,
decompiled `*.md`)는 **재배포 불가**(AGPL/독점 파생) → gitignored/export-ignored.

### 3.1 KnowledgeInjector 토큰 예산

`injector.py:18-22` (1 토큰 ≒ 4자):
| 섹션 | 문자 예산 | 토큰 |
|---|---|---|
| 카드 메커닉 | `_CARD_BUDGET_CHARS=1600` | ~400 |
| 몬스터 패턴 | `_MONSTER_BUDGET_CHARS=800` | ~200 |
| 포션 메커닉 | `_POTION_BUDGET_CHARS=600` | ~150 |
| 인카운터 | `_ENCOUNTER_BUDGET_CHARS=200` | ~50 |

> L3는 스킬(600)·메모리(400)과 **별도 예산**을 갖는다 (`injector.py:1-5` 모듈 docstring).

### 3.2 주입 함수 (결정 타입별)

| 함수 | 언제 | 출력 |
|---|---|---|
| `inject_combat_knowledge` (`injector.py:25`) | 전투 | `## Card Mechanics` + `## Enemy Patterns` + `## Potion Mechanics` |
| `inject_reward_knowledge` / `inject_shop_knowledge` (`:64`/`:73`) | 카드 보상/상점 | `## Card Mechanics (from game data)` |
| `inject_event_knowledge` (`:78`) | 이벤트 | Ancient 이벤트 플래그만 (옵션 설명은 L2가 직접 출력, 중복 회피) |
| `inject_encounter_knowledge` (`:99`) | 전투 시작 | `## Encounter: <name>` (type/act, weak 여부) |
| `inject_keyword_glossary` (`:119`) | 핸드 카드 | `## Keyword Glossary` (rules_text 스캔한 키워드 정의) |

### 3.3 카드 메커닉 라인 형식

`_build_card_knowledge_lines` (`injector.py:144`):
```
- <display_name>: <enrichment_summary>
```
중복 제거(`+` 접미사 정규화), 예산 초과 시 break. `kb.cards.get_enrichment_summary(name)`가
카드 메커닉을 인간 가독 요약으로 반환.

### 3.4 룩업 DB (GameKnowledge 파사드, `src/knowledge/knowledge.py`)

| 룩업 | 항목 수 | 파일 |
|---|---|---|
| `card_lookup` | 577 카드 | `card_lookup.py` |
| `monster_lookup` | 121 몬스터 | `monster_lookup.py` |
| `potion_lookup` | 64 포션 | `potion_lookup.py` |
| `potion_classifier` | 5 타입 분류 | `potion_classifier.py` |
| `event_lookup` | 68 이벤트 | `event_lookup.py` |
| `relic_lookup` | 289 유물 | `relic_lookup.py` |
| `encounter_lookup` | 87 인카운터 | `encounter_lookup.py` (decompiled) |
| `keyword_lookup` | — | `keyword_lookup.py` (upstream keywords.json) |
| `power_lookup` / `enchantment_lookup` / `act_lookup` | — | — |

`web_searcher.py` — 보스 전략 가이드를 **Opus 4.6** 웹 검색으로 보강 (보스 결정 전용).

> L3는 "정적 지식" 계층이다 — 포스트런이 **학습하지 않는다.** 카드/몬스터별 경험은
> L4 `CardMemory`로, 전술 규칙은 L5 스킬로 간다. L3는 게임 데이터만 제공한다.

---

## L4 — 에피소드 메모리 (HCM: Hierarchical Categorical Memory)

**위치:** `src/memory/`(모델·스토어·추출기) → `AgenticSTS-Data/memory/`(영속)
**변이성:** 포스트런 기록. 라이프사이클: 단기기억 → 포스트런 추출 → 스토어 → 가이드 통합.
**영속 파일:** `memory/rules.json`, `memory/v2/{combat_episodes,route_memories,card_builds,event_memories}.jsonl`,
`memory/v2/{guides,card_memories}.json`

### 4.1 HCM 모델 (`src/memory/models_v2.py`)

| 모델 | 저장 | 레코드 수(릴리스 시점) | 스토어 |
|---|---|---|---|
| `CombatEpisode` | 전투 에피소드(라운드·인텐트·피해) | 3,214 | `combat_store.py` |
| `RouteMemory` | 액트별 루트 경로 + HP/결과 | 397 | `route_store.py` |
| `CardBuildMemory` | 덱 빌드(카드 카운트·플랜·엔진·약점) | 556 | `card_build_store.py` |
| `EventMemory` | 이벤트 선택 + 결과 | 1,553 | `event_models.py` |
| `CardMemory` | 카드별 종단 메모(빌드 역할·코어 엔진) | 329 | `card_memory_store.py` |
| `Guides` | 통합 가이드 | combat 158 / route 9 / deck 5 / event 138 | `guide_store.py` |
| `WorkingContext` | 결정별 검색 결과 컨테이너 | — | `retriever.py` |

`rules.json` — 교차 실행 전략 규칙(트리거 태그 기반).

### 4.2 검색 파이프라인 (`retriever.py`)

**결정 타입 분류** `_classify_decision_type` (`retriever.py:114`):
```
is_combat → "combat" | is_map → "route" | card_reward/card_select/shop → "deck"
| event → "event" | rest_site → "rest" | else → "other"
```

**결정별 토큰 예산** `_token_budget` (`retriever.py:129-139`):

| 결정 타입 | 토큰 예산(config) |
|---|---|
| combat | `COMBAT_MEMORY_TOKENS` |
| route | `ROUTE_MEMORY_TOKENS` |
| deck | `DECK_MEMORY_TOKENS` |
| event | `EVENT_MEMORY_TOKENS` |
| rest / rest_event | `REST_EVENT_MEMORY_TOKENS` |
| 기본 | 150 |

**총 상한** `config.MEMORY_TOTAL_TOKEN_CEILING = 600` — 이를 넘으면 `_trim_working_context` 재적용.

### 4.3 결정별 검색 우선순위 (`query_for_decision`, `retriever.py:444`)

`query_for_decision`의 도큐멘테이션(`:459-464`):
```
- Combat: Guide > Episodes > Rules > Short-term timeline
- Route:  Guide > Route memories > Rules
- Deck:   Guide > Build memories > Rules
- Rest/Event: Rules > Reflections
```

**Combat 분기** (`:485-539`):
1. `guide_store.get_combat_guide(enemy_key, character)` — 가이드(confidence≥0.3)
2. `combat_store.query(enemy_key, character, combat_type, limit=5)` → `format_enemy_patterns`
3. (R2+ 조건) 가이드의 `mechanic_summary` → `format_enemy_behavior_summary` → `situation_hints`
   ("## Past Experience"로 주입, R2+에서 가이드보다 우선)

**Route 분기** (`:541-559`): `get_route_guide(act)` + `route_store.query(act, limit=2)` →
`Past Act{act}: node→node | HP x→y | result`

**Deck 분기** (`:561-622`): 덱 아키타입 후보 태그 추론(`_deck_guide_candidate_tags`,
Shiv/Poison 신호 + active_deck_builds + card_memory build_role) →
`get_deck_guide(character, tag)` + `card_build_store.query(limit=2)` →
`Past build: F<floor> | Top: cards | WIN/LOSS | Plan/Dmg/Weak/conf`
+ **카드별 메모리**(`card_memory_store.query_cards`, 제공된 카드에만):
`build_role_hint` + `core_engine_hint` + `effective_note`

**Event 분기** (`:624-667`): `get_event_guide(event_id)` → `_render_event_guide_block`
(스테이지 필터 + 점수순 옵션 + "not in guide — new or unseen" 표시).
가이드 없으면 `event_store.query(limit=3)`에서 과거 에피소드(현재 옵션 텍스트와 매칭되는 것만).

**Strategic Thread** (`:673-677`): 모든 결정에 공통. `short_term.get_strategic_thread`
(L1의 `strategic_note`에서 유래, `note.triggers`로 state_type 필터링).

### 4.4 WorkingContext → 프롬프트 주입 (`prompt_injector.py`)

`format_working_context` (`prompt_injector.py:16`) — 결정 타입별 **섹션 헤더**로 포장:

| WorkingContext 필드 | 헤더 | 부제 |
|---|---|---|
| `situation_hints` | `## Past Experience` | *Enemy mechanics and fight structure* (R2+ 최우선) |
| `combat_guide_hints` + `enemy_pattern_hints` | `## Combat Guide` | R2+면 *Background reference*로 강등(텍스트는 보존) |
| `route_guide_hints` + `route_memory_hints` | `## Route Intelligence` | + **Past Routes** |
| `deck_guide_hints` + `deck_memory_hints` | `## Deck Building Insights` | + **Past Builds** |
| `card_memory_hints` | `## Card-Specific Insights` | 제공된 카드에만 |
| `event_memory_hints` | `## Past Event Experience` | |
| `short_term_hints` | `## Strategic Thread` | *deck-building rationale* |

- **위협 배너** (`:39-40`): `current_threat_level in ("high","lethal")` 시 `## Past Experience`에
  `**SURVIVAL PRIORITY**: <level> threat.` 추가.
- **R2+ 강등** (`:48-51`): 전투 2라운드 이후엔 Combat Guide 헤더를 *Background reference*로 강등하지만
  **가이드 텍스트 자체는 잘리지 않는다** (mid-sentence `...` 컷이 실행 가능한 절반을 잃었기 때문).
- 주입 위치: `## Your Task` 앞 (`_insert_before_task`, `:130`).
- `sanitize_deck_guide_hints`가 알려진 bad legacy 라인을 제거 후 주입.

### 4.5 예산 초과 트리밍 (`_trim_working_context`, `retriever.py:713`)

**우선순위(낮을수록 먼저 잘림)** (`:722-733`):
```
enemy_pattern_hints(가장 낮) → route_memory → deck_memory → short_term
→ combat_guide → situation → route_guide → deck_guide
→ card_memory → event_memory(가장 높)
```
- `event_memory`가 가장 높은 우선순위(이벤트 결정의 최상 신호).
- `_trim_hints` (`:147`)는 **경계 단위**로 자른다 — 줄 경우 줄 단위, 한 줄이면 문장 경위(`. ` `! ` `? `),
  못 맞추면 통째로 drop(후속 더 작은 힌트는 `continue`로 계속 검토). mid-word/`...` 컷 금지.

### 4.6 포스트런 기록 순서 (`src/agent/loop.py::_safe_post_run`)

```
memory 추출(CombatEpisode/RouteMemory/CardBuildMemory/EventMemory/CardMemory)
  → 가이드 통합(CONSOLIDATION_EVERY_N_RUNS=1)
  → 스킬 단계(record_outcome / noncombat 점수 / 실수 발견 / 저장 / 은퇴 스윕)
  → Mode B 스텁 채우기
  → 진화(EVOLUTION_MAX_ROUNDS=5, READ_ONLY_ROUNDS=2)
  → 판사 플러시
```

---

## L5 — 스킬 라이브러리

**위치:** `src/skills/`(모델·라이브러리·작성 게이트) → `AgenticSTS-Data/skills/`
**영속 파일:** `skills.json`, `skill_usage.jsonl`, `experiments/`
**변이성:** 제어된 기록(트리거 매칭 + 작성 게이트 + 라이프사이클).

### 5.1 SkillTrigger 스키마 (`models.py:86`)

`@dataclass(frozen=True)` — 모든 조건은 **AND 결합**, 빈/기본값 = "모두 매치".

| 필드 | 타입 | 기본값 | 의미 | 매칭 점수 |
|---|---|---|---|---|
| `state_types` | `frozenset[str]` | `{}` | 활성화 상태 타입(공백=전체) | +1.0 |
| `enemy_names` | `frozenset[str]` | `{}` | 적 이름(접두 매치 지원: "Test Subject" → "#C22") | +2.0 |
| `min_act` / `max_act` | `int` | 0 / 99 | 액트 범위(포함) | +0.5 |
| `hp_below` | `float` | 1.0 | HP 비율이 이 값 미만일 때 활성 | +0.5 |
| `hp_above` | `float` | 0.0 | HP 비율이 이 값 초과일 때 활성 | +0.5 |
| `min_deck_size` / `max_deck_size` | `int` | 0 / 999 | 덱 크기 범위 | — |
| `requires_cards` | `frozenset[str]` | `{}` | hand/deck에 있어야 할 카드(교집합 가중, 수익 체감) | +1.5 + 0.5×(추가) |
| `character` | `frozenset[str]` | `{}` | 하드 캐릭터 필터("silent","regent" 등 정규화명) | +0.5 |
| `any_of_relics` | `frozenset[str]` | `{}` | 최소 1개 유물 존재(하드 필터) | +0.3×N |
| `requires_hand_capabilities` | `frozenset[str]` | `{}` | hand capability 최소 1개 true(하드 필터) | +1.0 |
| `requires_enemy_powers` | `frozenset[str]` | `{}` | 최소 1 적이 이 파워 보유(하드 필터) | +2.0 |

`matches(...)` (`models.py:126`) → `(matches: bool, relevance_score: float)`.
불매치 시 즉시 `False, 0.0`. 매치 시 `max(score, 0.1)`.

**상태 타입 정규화** (`models.py:46`): "combat"→{monster,elite,boss}, "rest"→{rest_site},
"deck_building"→{card_reward,card_select,shop} 등 의미 라벨을 정규 게임플레이 state_type으로 매핑.

### 5.2 Skill 스키마 (`models.py:257`)

| 필드 | 의미 |
|---|---|
| `skill_id` | 12자 uuid |
| `name` | 스킬 이름 |
| `category` | `combat \| deck_building \| map \| event \| rest \| boss \| general` |
| `trigger` | `SkillTrigger` |
| `anchor_exemplars` | 원래 게임플레이 프롬프트로의 역참조(merge A/B 재현용) |
| `tier` | `general`(항상 고려) \| `specific`(트리거 매치 시만) — SkillRL 패턴 |
| `content` | **코어 지식(프롬프트에 주입되는 자연어, ≤400자 권장)** |
| `lessons` | 이 스킬을 **안** 지켰을 때 실패 패턴 |
| `examples` | 적용 예시 튜플 |
| `priority` | 높을수록 먼저 주입(같은 카테고리 내) |
| `source` | `seed \| discovered \| refined \| merged \| stub_filled` |
| `confidence` | 0–1, 시드 0.7 시작 |
| `usage_count` / `success_count` / `failure_count` | 효과 추적 |
| `verified` | 시드는 미리 검증(true), 발견은 probation(false) 시작 |
| `status` | `active \| probation \| deactivated` + `pending_fill`(Mode B 스텁) |
| `consecutive_unimproved_runs` | 은퇴 정책용(3 도달 → 은퇴, 시드 면제) |
| `recent_noncombat_scores` | 최근 3회 비전투 점수 |
| `scaffold` | Mode B 스텁 메타(topic, scope, dimensions_to_consider, …) |

**effective_priority** (`models.py:352`) = `priority × confidence` + 사용 보너스(최대 +20, 양성 결과에만).
**with_usage** (`models.py:400`) — Laplace-smoothed 신뢰도 갱신 + 자동 비활성화(총 5회 이상·신뢰도<0.15).

### 5.3 주입 형식 (`composer.py`)

`compose_skill_context` (`composer.py:18`) — 검색된 스킬을 `## Expert Knowledge` 블록으로 포장:

```
## Expert Knowledge (retrieved skills)
*Apply these strategies to the current situation. Deviate only with good reason.*

**<skill.name>** (<confidence%|seed|new>[ ⚠unverified])
<skill.content>
  - Example: <examples[0]>     ← combat 카테고리 + sequence 키워드일 때만 1개 예시 보존
```

- **위협 필터** (`composer.py:39-50`): `threat_level in ("high","lethal")` 시 생존 관련 스킬만
  (combat/boss 카테고리 또는 hand/enemy-power 트리거). 단, 최소 1개는 유지.
- **slim 포맷**: examples·lessons·category는 원칙적으로 생략(combat sequence 스킬의 예시 1개만 예외).
- **신뢰도 표시**: `usage_count>0`이면 `XX%`, 미사용 시드면 `seed`, 미사용 신규면 `new`.
  미검증이면 ` ⚠unverified`.

`inject_skills_into_prompt` (`composer.py:90`) — `## Your Task` 앞 삽입(없으면 마지막 `## ` 앞).
`inject_candidate_into_prompt` (`composer.py:114`) — A/B 검증용 후보 스킬 주입(`(candidate - under evaluation)` 태그).

**SKILLS_MAX_PER_PROMPT=7**(덱빌딩 결정은 3). `SkillLibrary.query`가 트리거 매칭 +
`effective_priority` 정렬로 상위 N개 선택.

### 5.4 시드 스킬 (7개, `src/skills/seeds/*.json`)

| 시드 | 카테고리 | tier | 신뢰도 | 핵심 |
|---|---|---|---|---|
| `core_combat.json` | combat | general | 0.9 | 6원칙(프리 윈도우/빈 적 데미지 0/드로우 파일/에너지 전사용/집중 사격/포션 타이밍) |
| `core_boss_strategy.json` | boss | general | 0.85 | 보스 전용(포션 총동원/빠른 종료/HP 회복/lookup_enemy/Power 조기) |
| `core_deck_building.json` | deck_building | general | — | 런 전체 덱 빌딩 |
| `core_map_routing.json` | map | general | — | 맵 라우팅·경로 계획 |
| `core_rest_decision.json` | rest | general | — | 휴식·이벤트 결정 |
| `silent_a10_guide.json` | combat | specific | — | Silent Act 1 종료 가이드 |
| `silent_card_notes.json` | deck_building | specific | — | Silent 카드 티어 노트 |

**content 예시** (`core_combat.json:10`):
> "Every combat turn: (1) Read enemy intents — if ALL enemies have non-attack intents …
> it is a FREE offense window … (2) Dead enemies deal zero damage … (3) Check your draw pile …
> (4) Use ALL energy … (5) Multi-enemy: focus fire … (6) Potions don't cost energy …"

### 5.5 작성 게이트 — 4단계 (`src/skills/write_gate.py:627`)

포스트런이 새 스킬/패치를 기록할 때 통과해야 하는 게이트:

| 단계 | 조건 | 결과 |
|---|---|---|
| **1** 정확 매치 | `name` 또는 `skill_id` 정확 일치 | **UPDATE** (`:654`) |
| **2** 트리거 자카드 | 트리거 태그 자카드 ≥ `TRIGGER_JACCARD_SAME_CONTEXT=0.60` | 동일 문맥 간주 |
| **3a** L1/L2/L3 임베딩 | 코사인 ≥ `L1_L2_L3_REJECT_COSINE=0.70` → 거부 / `[0.55,0.70)` → 판사 연기 | L1/L2/L3 영역 침범 차단 (`:711`) |
| **3b** L4/L5 이웃 임베딩 | ≥`L4_L5_AUTO_REJECT_COSINE=0.85` → 거부 / `[0.70,0.85)`+자카드≥0.60 → **MERGE** / `[0.70,0.85)`+자카드<0.60 → 수락 / `[0.55,0.70)` → 판사 연기 (`:724`) | |
| **4** 배치 LLM 판사 | `flush_judge_round` (`:1025`) | **ADD** / **UPDATE** / **REJECT** / **MERGE**(→`merge_pipeline.py`) |

- 임베딩: `text-embedding-3-large` + 파일 캐시 + `_fast_llm_dup_check` 폴백.
- `defer_to_judge` 후보는 `WriteGate._pending_skills`에 대기 → `flush_judge_round` 판정 →
  ADD(저장) / UPDATE(교체) / REJECT(드롭) / MERGE(`run_merge_pair`, dual-anchor A/B).

### 5.6 실수 발견 — 유일한 스킬 생성 경로 (`mistake_discovery.py:207`)

포스트런 전투마다:
- `loss_ratio = total_damage_taken / max(hp_before, 1)`
- **베이스라인 A**: 해당 적 역사적 중앙값(표본 ≥3)
- **베이스라인 B**: act × combat_type × character 평균
- **델타 임계값**: 일반 몬스터 0.10 / 엘리트 0.15 / 보스 0.20
- 초과 시 → LLM critic이 라운드 트레이스 읽고 후보 스킬 제안(또는 `no_skill_needed`/`bad_luck`/`unavoidable_mechanic`/`descriptive_rhythm`)
- **사전 작성 A/B** (`prewrite_ab.py`): 후보 주입 후 B=3 재샘플, temp 0.7, **strict 2/3 + zero-harmful**(유해 0건) 통과 시에만 게이트 진입
- 통과 스킬: `confidence = 0.40 + 0.05 × len(mistake_round_indices)`, `status="probation"`

### 5.7 라이프사이클 (`lifecycle.py:74`)

- **신뢰도 승수 `CONFIDENCE_MULT`**: 개선 ×1.10 / 동일 ×0.98 / 악화 ×0.85
- **은퇴 조건**: `confidence < 0.30` AND `usage_count >= 10` 또는 `consecutive_unimproved_runs >= 3`
- **시드 면제**: 은퇴 시 신뢰도 하한선 0.40(`apply_retirement_policy`)
- **검증 졸업**(SoK/Voyager 패턴): probation → `MIN_VERIFICATION_USES` 후 success_rate>0.5 시 verified
- **자동 비활성화**: 총 5회 이상 추적 + 신뢰도<0.15

---

## 부록 A — 결정별 토큰 예산 요약

| 계층 | 결정 타입 | 예산 | 비고 |
|---|---|---|---|
| **L1** | 전체 | 정적(캐싱) | `cache_control: ephemeral` |
| **L2** | 결정별 | 변동 | 옵션 목록 + Decision Format이 뒤쪽 |
| **L3** | 카드 400 / 몬스터 200 / 포션 150 / 인카운터 50 | 문자 기준(÷4) | 스킬·메모리와 별도 |
| **L4** | combat `COMBAT_MEMORY_TOKENS` / route `ROUTE_MEMORY_TOKENS` / deck `DECK_MEMORY_TOKENS` / event `EVENT_MEMORY_TOKENS` / rest `REST_EVENT_MEMORY_TOKENS` / 기본 150 | | 총 상한 `MEMORY_TOTAL_TOKEN_CEILING=600` |
| **L5** | 전체 | `SKILLS_MAX_PER_PROMPT=7`(덱빌딩 3) | HIGH/LETHAL 시 생존 필터 |

---

## 부록 B — 결정별 조립 결과(개념적)

하나의 combat 결정 user message(개념적 구성, R1):
```
[L1 system(캐싱)] SYSTEM_COMBAT = _SYSTEM_BASE + Core Combat Rules + HP Conservation

[L2 user 본문]
## Card Reward / ## Combat …        ← build_*_prompt
HP/Gold/Act/Floor/Character/Deck
## Relics: …
## Card Mechanics (from game data)  ← L3 injector
## Enemy Patterns (from game data)  ← L3
## Keyword Glossary                 ← L3
## Past Experience                  ← L4 situation_hints (R2+ 최우선)
## Combat Guide                      ← L4 combat_guide/pattern
## Strategic Thread                  ← L4 short_term (strategic_note 유래)
## Expert Knowledge (retrieved skills) ← L5 composer
  **Core Combat Principles** (90%) <content> …
## Available Cards / Options
## Decision Format (JSON 스키마)    ← v2_engine
```

---

## 부록 C — 코드 위치 색인

| 계층 | 파일:행 |
|---|---|
| L1 | `src/brain/prompts/system.py:15`(BASE), `:37`(COMBAT), `:58`(BOSS), `:80`(DECKBUILD), `:132`(STRATEGIC), `:207`(_STATE_SYSTEM_MAP), `:224`(get_system_prompt), `:152`(베이스라인) |
| L2 | `src/brain/prompts/map.py:20/:75`(A/B), `reward.py:33/:274`, `card_select.py:179/:108`, `event.py`, `rest.py`, `shop.py`, `treasure.py`, `potion.py`, `hand_select.py`, `distill.py` |
| L3 | `src/knowledge/injector.py:18`(예산), `:25/:64/:73/:78/:99/:119`(주입), `knowledge.py`(파사드), `*_lookup.py` |
| L4 | `src/memory/models_v2.py`(HCM 모델), `retriever.py:114`(분류), `:129`(예산), `:444`(query_for_decision), `:713`(_trim_working_context), `prompt_injector.py:16`(format_working_context), `*_store.py`/`*_extractor.py`, `guide_consolidator.py` |
| L5 | `src/skills/models.py:86`(SkillTrigger), `:257`(Skill), `:126`(matches), `composer.py:18/:90`(주입), `library.py`, `mistake_discovery.py:207`, `write_gate.py:627`, `lifecycle.py:74`, `seeds/*.json` |
| 규칙 | `docs/superpowers/specs/2026-04-18-pe-deprecation-negative-result.md`(PE 33/0), `2026-04-26-ablation-baseline-design.md`(베이스라인) |