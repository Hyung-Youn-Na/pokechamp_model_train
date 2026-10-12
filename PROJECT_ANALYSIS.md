# AgenticSTS 프로젝트 분석 문서

> **한 줄 요약**: AgenticSTS는 *Slay the Spire 2*를 플레이하는 **bounded-memory LLM 에이전트** 연구 모노레포로, 모든 결정을 "5개 지식 계층에서 타입 검색으로 조립한 fresh 사용자 메시지"로 내리며, 실행 길이에 무관하게 프롬프트 크기를 일정하게 유지한다.

- **논문**: *AgenticSTS: A Bounded-Memory Testbed for Long-Horizon LLM Agents* (arXiv:2607.02255, EMNLP 2026 ARR 심사 중)
- **저자**: Cheng, Jiang, Sun, Li, Li, Cao, Liu, Zhang, Jin, Zhang — Alaya Studio / Shanda AI Research (상하이교통대·남개대·USTC·상하이혁신연구원 공동)
- **분석 기준일**: 2026-07-08

---

## 1. 프로젝트 개요

### 1.1 무엇을 만드는가

AgenticSTS는 긴 호라이즌(long-horizon) LLM 에이전트를 위한 **bounded-memory 테스트베드**다. 구체적으로:

- **대상 게임**: *Slay the Spire 2*(Steam) — 닫힌 규칙의 확률적 덱 빌딩 게임. 한 run에 수백 개의 전술·전략 결정이 필요해 long-horizon 벤치마크로 적합.
- **에이전트**: 게임을 HTTP API로 관찰(`GET /state`)·판단·행동(`POST /action`)하는 Python 에이전트. run 사이에는 L4(에피소드 메모리)·L5(스킬 라이브러리)·동적 도구를 작성하며 자기 진화.
- **핵심 디자인 계약(bounded memory contract)**: 모든 결정 $d$는 상태 $s_d$에서 5개 지식 계층으로부터 타입 검색해 조립한 fresh 사용자 메시지 $u_d = \pi(L_1, L_2(s_d), L_3(s_d), L_4(s_d), L_5(s_d))$로 내린다. **raw cross-decision 트랜스크립트는 결코 append되지 않는다.** 결과적으로 프롬프트 크기가 run 길이에 무관하게 bounded 상태를 유지하고, 단일 계층을 독립적으로 ablation 할 수 있다.

### 1.2 왜 의미 있는가

대부분의 long-horizon LLM 에이전트는 "모든 것을 append" 계약(과거 관측·도구 호출·반성을 매 프롬프트에 누적)을 쓴다. 이 경우 컨텍스트가 무한히 증가하고, 오래된 trace가 결정에 재유입되며, 에이전트가 개선되었을 때 *어느 메모리 컴포넌트가 기여했는지 알 수 없다*. AgenticSTS는 반대 계약을 구현·검증·릴리스한다.

**릴리스가 제공하는 6가지**(README 요약):

1. **bounded memory contract** — 결정 프롬프트를 $u_d = \pi(L_1..L_5)$로 구성. capped top-k 검색으로 run 길이와 무관하게 프롬프트 크기 일정(트랜스크립트 인터페이스는 $\Omega(d \cdot \bar s)$로 성장).
2. **ablatable 평가 표면** — 컨텍스트가 named slot으로 모델에 도달하므로 프롬프트 엄격성·규칙·에피소드·스킬을 독립적으로 on/off 가능. 5셀 fixed-A0 행렬에서 **가장 큰 win-rate 차이**가 **L5 스킬 활성화**와 일치(+2/10, 동일 프롬프트 셋업). 단 N=10에서는 방향성이지 통계적 유의는 아님(Fisher exact p≈0.37).
3. **두 가지 스킬 생성 경로** — *실수 기반 발견*(mistake-driven discovery: 전투 패배 분석 → pre-write A/B gate → 4-level write gate)과 *템플릿 채우기*(Mode B). Mode B는 hand-authored 시드 라이브러리와 **동일 6/10 점추정**에 도달 → "스킬 계층의 존재"와 "누가 산문을 썼는지"를 분리.
4. **난이도 사다리 증거** — 릴리스된 사다리에서 postrun-writable L4+L5 스트림은 **A6–A8** 도전, no-postrun 스트림은 A2–A4에서 정지(fixed-A0 win-rate 분석과는 별개의 endpoint 스트림).
5. **차수級 효율** — accumulating-context StS2 에이전트 2종 대비 ~**4× 적은 floor당 wall-clock**, **66–90× 적은 score 점당 fresh LLM 토큰**. 토큰 비교는 honest-but-asymmetric(본 프로젝트는 추정치, 경쟁자는 measured fresh non-cached 토큰).
6. **재사용 가능 연구 산출물** — 298개 condition-tagged 궤적, SHA-anchored frozen L4+L5 스냅샷, 결정 시점 프롬프트 기록, Wilson/bootstrap 분석 스크립트.

### 1.3 세 하위 프로젝트와 라이선스

| 하위 디렉토리 | 역할 | 스택 | 라이선스 | 독자 문서 |
|---|---|---|---|---|
| `AgenticSTS/` | **에이전트** | Python 3.12+ | **Apache-2.0** | `CLAUDE.md`(내부 아키텍처+플레이북), `AGENTS.md`(기여 가이드), `README.md` |
| `AgenticSTS-Mod/` | **C# 게임 모드**(HTTP 브리지) | .NET 9 / Godot 4.5 / Harmony | **AGPL-3.0** | `README.md`, `VENDOR.md` |
| `AgenticSTS-Data/` | **동결된 연구 산출물**(L4/L5 스토어, run 아카이브) | 데이터 전용 | **CC-BY-4.0** | `README.md` |

> **라이선스 주의**: `AgenticSTS/`의 Apache-2.0은 `AgenticSTS-Mod/`로 연장되지 않는다. 모드를 수정·배포하면 AGPL-3.0 조건이 적용된다. Mega Crit(STS2 개발사)과는 무관한 독립 연구 프로젝트이며, 게임은 별도 구매 필요.

---

## 2. 시스템 구성과 연결

```
┌─────────────┐   HTTP (localhost:8128)    ┌──────────────────┐
│  AgenticSTS │ ← GET /state, POST /action→│  AgenticSTS-Mod  │
│   (에이전트) │ ← GET /events/stream (SSE) │ (C# 게임 모드)    │
│  Python     │                             │ .NET9/Godot4.5   │
└──────┬──────┘                             └────────┬─────────┘
       │ postrun 쓰기 (L4/L5/도구)                    │ Harmony 패치
       ▼                                             ▼
┌─────────────────┐                          ┌─────────────────┐
│ AgenticSTS-Data │                          │  Slay the Spire  │
│ (동결 산출물)    │                          │   2 (게임 본체)   │
│ CC-BY-4.0       │                          │  sts2.dll        │
└─────────────────┘                          └─────────────────┘
```

- **에이전트**(`AgenticSTS/`) → 게임을 HTTP로 관찰·판단·행동; run 사이에 L4/L5 + 동적 도구 작성.
- **모드**(`AgenticSTS-Mod/`) → 게임 위에 HTTP API(`GET /state`, `POST /action`, `GET /events/stream`)를 `localhost:8128`에 노출. CharTyr/STS2-Agent의 포크.
- **데이터**(`AgenticSTS-Data/`) → 논문 표/그림을 계산하는 SHA-anchored 동결 스냅샷(L4+L5 + `runs/history.jsonl`). frozen-store commit SHA `1888a62`.

### 2.1 다중 저장소 배선

세 하위 프로젝트는 **sibling**으로 checkout 되도록 설계됐다. 에이전트는 데이터 저장소를 향해 L4/L5/runs를 라우팅한다.

```bash
# /workspace 처럼 세 개를 sibling 으로 배치
export STS2_DATA_REPO="$(cd ../AgenticSTS-Data && pwd)"   # L4/L5/runs를 데이터 저장소로
export STS2_MACHINE_ID=$(hostname -s)                     # 병렬 머신 provenance 태그
cd AgenticSTS && cp .env.example .env && uv sync
```

- `STS2_DATA_REPO` **설정 시**: 모든 runtime/postrun 쓰기(메모리·스킬·evolution·`runs/history.jsonl`)가 데이터 저장소로 간다.
- **미설정 시**: `AgenticSTS/data/`로 폴백(로컬 개발용).
- 모든 스토어 접근자는 `AgenticSTS/src/storage/paths.py`를 거친다.

실제 플레이에는 게임本体·게임 `mods/`에 배포된 모드(사전 빌드 DLL at `AgenticSTS-Mod/build/mods/STS2AIAgent/`)·`.env`의 최소 1개 LLM 자격증명이 추가로 필요하다.

---

## 3. 핵심 아키텍처 — bounded memory contract

중앙 디자인(세 부분에 걸친): **모든 결정은 5개 지식 계층에서 타입 검색으로 조립한 fresh 사용자 메시지로 내려진다. raw cross-decision 트랜스크립트는 결코 append되지 않는다.** 프롬프트 크기가 run 길이에 무관하게 bounded 상태를 유지한다.

```
u_d = π(L1, L2(s), L3(s), L4(s), L5(s))
```

| 계층 | 내용 | 가변성 | 거주지 |
|---|---|---|---|
| **L1** | 4개 static 시스템 프롬프트(COMBAT / COMBAT_BOSS / DECKBUILD / STRATEGIC) | **Immutable** | `AgenticSTS/src/brain/prompts/system.py` |
| **L2** | 상태-타입 결정 프롬프트(스키마 + legal-action 포맷) | **Immutable** | `AgenticSTS/src/brain/prompts/` |
| **L3** | 게임 지식(카드·몬스터·포션·유물·이벤트·키워드) | 정적, patch-refreshed | `AgenticSTS/src/knowledge/` + `data/knowledge/` |
| **L4** | 에피소드 메모리(postrun 요약) | Postrun-writable | `AgenticSTS/src/memory/` → `AgenticSTS-Data/memory/` |
| **L5** | 스킬 라이브러리(triggered 전략 가이드) | Gated-writable | `AgenticSTS/src/skills/` → `AgenticSTS-Data/skills/` |

### 3.1 immutability 규칙 (load-bearing)

과거 prompt-evolution 파이프라인이 33개의 postrun-authored L1/L2 패치를 제안했으나, **33개 모두 A/B 검증에서 실패**했다. 그래서 **postrun LLM은 L4 메모리 / L5 스킬 / 동적 도구만 작성할 수 있다** — L1/L2는 절대 건드리지 못한다. 인간은 PR(서면 정당화와 함께) 또는 게임-버전 업데이트용 `scripts/apply_patch.py`로 L1/L2를 편집한다. (상세는 §10.1 "PE 폐기 negative result")

### 3.2 라우팅

dispatcher가 각 결정을 4개 모델 티어 중 하나로 라우팅한다 — `fast`(자명한 플레이), `strategic`(일반), `analysis`(postrun 추출), `evolution`(스킬 발견). 4개 static 시스템 프롬프트는 캐시 가능; 모든 per-run 상태는 사용자 메시지에만 존재한다. 전투는 라운드당 최대 3 메시지; 이전 라운드는 typed state로 요약된다. 결과: in-game action마다 1회 호출 대신 **run당 중앙값 ~67회 strategic LLM 호출**.

### 3.3 raw 로그는 RAG로 쓰지 않는다

이 게임에서는 거의 동일해 보이는 상태가 반대 전략적 의미를 가질 수 있다(카드 순서, 유물 콤보, 경로 이력). 그래서 에이전트는 *요약과 triggered 가이드*를 검색하지, nearest-neighbor 로그 조각을 검색하지 않는다.

---

## 4. AgenticSTS (에이전트) — 코드 구조

> **규모**: `src/` = **62,165 Python 라인**, `tests/` = **212 파일 / 46,035 라인**, `scripts/` ≈ **80개**.

### 4.1 디렉토리 구조와 책임

| 모듈 | 책임 | 핵심 파일 |
|---|---|---|
| `agent/` | observe → decide → act 코어 루프 + 페이즈 전환 | `loop.py`(**10,793줄**, 시스템 최대 파일 — 모든 상태 타입 처리 통합), `state_machine.py` |
| `brain/` | 결정 엔진·4-tier 라우팅·프롬프트(L1/L2)·동적 도구·evolution | `v2_engine.py`(결정 엔진), `v2_backend.py`(멀티프로바이더 백엔드), `conversation.py`(전투 다중턴), `evolution_engine.py`, `dynamic_tools.py`, `llm_router.py`, `prompts/system.py`(L1), `prompts/*`(L2: map/event/rest/shop/reward/card_select/hand_select/treasure/potion/distill) |
| `memory/` | L4 HCM: 도메인 스토어 + 추출기 + retriever + guide 통합 + write gate | `models_v2.py`(HCM 모델), `retriever.py`(결정-타입 인식 통합 검색), `write_gate.py`(4-level), `guide_consolidator.py`, `short_term.py`, 각 `*_store.py`/`*_extractor.py` |
| `skills/` | L5 라이브러리: 발견·write gate·merge·composer·시드 | `mistake_discovery.py`(실수 기반, 유일 스킬 생성 경로), `prewrite_ab.py`, `merge_pipeline.py`, `lifecycle.py`, `composer.py`, `dedup.py`, `seeds/*.json` |
| `knowledge/` | L3 정적 게임 데이터 lookup + 토큰-예산 주입 | `card_lookup.py`(577 카드), `monster_lookup.py`(121 몬스터), `potion_lookup.py`(64), `event_lookup.py`(68), `relic_lookup.py`, `injector.py`(토큰-예산), `web_searcher.py` |
| `mcp_client/` | C# 모드 HTTP 서버 통신 | `client.py`(async httpx), `actions.py`(액션 빌더), `upstream_models.py`(Pydantic), `sse_client.py`(이벤트 → state refresh) |
| `state/` | 게임 상태 Pydantic 래핑 + RunState 누적기 | `game_state.py`, `state_parser.py`, `run_state.py`(fitness 함수) |
| `monitor/` | WebSocket EventBus + REST history | `server.py`(FastAPI), `event_bus.py`, `summarizer.py`(백그라운드 Haiku 4.5) |
| `log/` | JSONL 구조화 로깅(전체 state 스냅샷 + EventBus push) | `session_logger.py` |
| `runs/` | RunRecord + RunHistoryStore(append-only JSONL) + ascension 통계 | `history.py`, `ascension_stats.py` |
| `postrun/` | postrun 컨텍스트 빌드 | `context_builder.py`(**1,432줄**) |
| `storage/` | 경로 해석(모든 스토어 접근자가 거침) | `paths.py` |
| `config.py` | 전역 설정 + `_MODEL_FAMILIES` 레지스트리 | — |

### 4.2 한 게임 run의 데이터 흐름

1. **관찰**: `agent/loop.py`가 `mcp_client/client.py`로 `GET /state` 호출 → `state/state_parser.py`가 raw JSON을 frozen Pydantic `GameState`로 파싱.
2. **결정**: `brain/v2_engine.py`가 상태 타입을 판별해 `_get_v2_tier()`로 티어 선택 → `brain/v2_backend.py`로 LLM 호출. 프롬프트는 `memory/retriever.py`(L4) + `skills/composer.py`(L5) + `knowledge/injector.py`(L3)가 조립.
3. **행동**: 결정 → `mcp_client/actions.py`가 `POST /action`(play_card, buy_card 등) 빌드 → `mcp_client/sse_client.py`가 이벤트로 state refresh.
4. **전투**: `brain/conversation.py`가 다중턴 히스토리 누적. 라운드당 최대 3 메시지(combat_start + "ok" + 최신 라운드 state), 이전은 typed state로 요약. 전투 종료 시 메모리 추출용 요약 생성.
5. **postrun**: run 종료 후 memory 추출 → rule distillation(5 run마다) → guide 통합(5 run마다) → 실수 기반 스킬 발견(매 run) → self-evolution 순서로 `_safe_post_run()` 실행.

### 4.3 4-tier model routing

`brain/v2_engine.py::_get_v2_tier(state_type)`가 상태 타입별 티어를 dispatch:

| 티어 | 용도 | 비고 |
|---|---|---|
| `fast` | 전투 single-card, 포션, hand_select, treasure, map step | thinking off(proxy compat) |
| `strategic`(streaming) | 전투 플랜, rest, shop, event, card_reward, card_select, route 선택 | thinking on |
| `analysis` | postrun 반성, distillation, guide 통합, 스킬 발견 | — |
| `evolution` | self-evolution tool-use 루프 | — |

`config._MODEL_FAMILIES` 레지스트리 — 패밀리 하나 고르면 네 티어의 model→effort가 자동 해석(**코드 기준, README보다 최신**):

| 패밀리 | fast | strategic | analysis |
|---|---|---|---|
| `gemini`(기본) | gemini-3-flash-preview (low) | gemini-3.1-pro-preview (low) | gemini-3.1-pro-preview (high) |
| `gpt` | gpt-5.4-mini (low) | gpt-5.4 (medium) | gpt-5.4-thinking (high) |
| `qwen` | qwen3.6-27b (low) | qwen3.6-27b (medium) | **→ gemini-3.1-pro**(high) |
| `claude` | claude-haiku-4-5 (low) | claude-sonnet-4-6 (medium) | claude-sonnet-4-6 (high) |
| `deepseek` | deepseek-v4-pro (low) | deepseek-v4-pro (high) | **→ gemini-3.1-pro**(high) |

- `analysis` 티어가 없는 패밀리(qwen/deepseek)는 gemini로 라우팅 → postrun은 강한 모델로 실행(`STS2_GEMINI_API_KEY` 필요). 이런 패밀리는 자동으로 postrun 비활성화도 아님(analysis 티어 빌려씀).
- **fast/strategic 모델 변경 시 model profile이 rehash**되고 ascension 진행이 A0로 리셋(의도적 — 약한 모델이 강한 모델의 ascension 크레딧을 상속하지 않게).
- 탈출구: 티어별 모델 override(`STS2_FAST_MODEL`), 패밀리별 effort(`STS2_QWEN_EFFORT_STRATEGIC`), 패밀리별 자격증명(`STS2_GPT_API_KEY`/`STS2_GPT_BASE_URL`…). 전체 키 목록은 `.env.example`.

**`_V2_TIER_MAP` 상세 매핑**(`v2_engine.py:228`):
- **fast**: `hand_select`, `treasure`, `map`(step walking), 단순 전투(≤2 카드).
- **strategic**: `monster`, `elite`, `boss`, `card_reward`, `card_select`, `rest_site`, `shop`, `event`, `crystal_sphere`(3종), `bundle_select`, `combat_plan`(전투 플랜 생성).
- V2Engine(`v2_engine.py:248`): `decide_noncombat()`(`:474`), `generate_combat_plan()`(`:571`), `_get_v2_tier()`(`:422`), `_single_call()`(`:634`).
- V2Backend(`v2_backend.py:74`): `acall()`(`:1969`), **헤지드 레이싱**(`:2034` — 동일 프롬프트를 2프로바이더에 동시 호출 후 승자 채택, 레이턴시·가용성 헷지). 120s 타임아웃, 프롬프트 캐싱, 스트리밍.

### 4.4 L4 메모리 / L5 스킬 시스템

**L4(HCM = Hierarchical Categorical Memory)** — `memory/models_v2.py`가 도메인 모델 정의:
- `CombatEpisode`(enemy_key × character 검색), `RouteMemory`(act × character), `CardBuildMemory`(character × archetype), `CardMemory`(character × card_name, 종단적), `EventMemory`, 통합 `Guide`(CombatGuide/RouteGuide/DeckGuide/EventGuide).
- `memory/retriever.py`가 결정-타입 인식 통합 검색 → `WorkingContext`. 토큰 예산: combat 300, route 250, deck 300, rest/event 150/450, 전체 상한 600.
- 각 도메인별 `*_store.py`(저장) + `*_extractor.py`(ShortTermMemory → 추출).

**L5(스킬 라이브러리)** — `skills/models.py`가 `Skill + SkillTrigger` frozen dataclass. trigger는 명시적 trigger + prose policy로 구성:
```json
{
  "skill_id": "stub_the_silent_boss",
  "name": "The Silent - Boss Strategy",
  "category": "boss",
  "trigger": {
    "state_types": ["boss"], "enemy_names": [], "min_act": 0, "max_act": 99,
    "hp_below": 1.0, "hp_above": 0.0, "min_deck_size": 0, "max_deck_size": 999,
    "requires_cards": [], "character": ["the silent"],
    "any_of_relics": [], "requires_hand_capabilities": [], "requires_enemy_powers": []
  },
  "content": "TBD - filled by Mode B postrun",
  "source": "stub", "status": "pending_fill",
  "confidence": 0.5, "usage_count": 0, "success_count": 0, "failure_count": 0,
  "priority": 92, "tier": "general"
}
```
- `skills/composer.py`가 검색된 스킬을 프롬프트 컨텍스트로 조립. 프롬프트당 최대 7개(덱빌딩은 3개 — archetype hopping 방지).
- `skills/library.py`가 로드·쿼리·persist·merge seeds.

### 4.5 쓰기 게이트(write gate)와 실수 기반 스킬 발견

**실수 기반 발견**(`skills/mistake_discovery.py` — 2026-04-19에 cohort 기반을 대체한 **유일 스킬 생성 경로**):

1. **플래깅**: per-combat `loss_ratio`를 enemy-median Baseline A, act×combat_type×character Baseline B와 비교해 고손실 에피소드 플래그.
2. **LLM critic**: 라운드 trace를 읽고 스킬 후보 제안 또는 `no_skill_needed`/`bad_luck`/`unavoidable_mechanic`/`descriptive_rhythm` 방출(`critic_prompt.py`).
3. **후보 검증**: 이름/내용/trigger 제약 강제.
4. **pre-write A/B**(`prewrite_ab.py`): 실수 라운드마다 B=3 결정을 후보 주입해 resample, `skill_harmful` 판정 0 + `sum(hits) >= ceil(total × 2/3)`(strict 2/3) 요구.
5. **4-level write gate**(`memory/write_gate.py`): 생존자는 `confidence = 0.40 + 0.05 × len(mistake_round_indices)`, `status="probation"`으로 진입. 시드 스킬은 비활성화 면제(하한 0.40).

**write-gate reap + skill-merge**(2026-04-20, `STS2_WRITE_GATE_REAP_ENABLED` 기본 off):
- `defer_to_judge` 후보는 `WriteGate._pending_skills`에 대기 → `flush_judge_round` 판정 → `ADD` persist, `UPDATE` replace, `REJECT` drop, `MERGE`는 `merge_pipeline.py::run_merge_pair`에 위임(dual-anchor A/B 검증: 양쪽 strict 2/3 + zero-harmful). 감사 추적: `data/evolution/write_gate_log.jsonl` ([2026-08-07 정정] 원래 `reap_log.jsonl`로 기술했으나 코드/데이터 대조 결과 실제 감사 추적 파일은 `write_gate_log.jsonl`임 — 본 문서 §6.1·§6.4의 미존재 정정과 일치시킴).

**write gate 4-레벨 캐스케이드**(`write_gate.py::check`, 정확한 임계값):

| 레벨 | 조건 | 결과 | 위치 |
|---|---|---|---|
| 1 | 정확한 `name`/`skill_id` 매치 | UPDATE(기존 대체) | `:654` |
| 2 | trigger 태그 Jaccard ≥ `TRIGGER_JACCARD_SAME_CONTEXT=0.60` | 동일 컨텍스트 → judge 연기 | `:727` |
| 3a | L1/L2/L3 임베딩 코사인 ≥ `L1_L2_L3_REJECT_COSINE=0.70` | REJECT(불변 프롬프트 중복) | `:711` |
| 3a | L1/L2/L3 코사인 ∈ [0.55, 0.70) | judge에게 연기 | `:711` |
| 3b | L4/L5 이웃 코사인 ≥ `L4_L5_AUTO_REJECT_COSINE=0.85` | REJECT | `:724` |
| 3b | 코사인 ∈ [0.70, 0.85) + Jaccard ≥ 0.60 | 병합 후보 | `:724` |
| 3b | 코사인 ∈ [0.70, 0.85) + Jaccard < 0.60 | ADD(새 스킬) | `:724` |
| 3b | 코사인 ∈ [0.55, 0.70) | judge에게 연기 | `:724` |
| 4 | judge 배치(`flush_judge_round` `:1025`) | ADD/UPDATE/REJECT/MERGE; MERGE→`merge_pipeline` | — |

- 임베딩: `text-embedding-3-large`, 디스크 파일 캐시, 실패 시 `_fast_llm_dup_check` LLM 폴백. `l1_l2_l3_index.json`이 L1/L2/L3 임베딩 인덱스(write-gate의 `l1_cosine` 검색이 이것을 질의 → PE 불변성 규칙을 기계적으로 강제).

**실수 발견 정확한 수치**(`mistake_discovery.py:207 run_mistake_discovery()`):
- `loss_ratio = total_damage_taken / max(hp_before, 1)`.
- Baseline A: 해당 enemy의 역사적 `loss_ratio` 중앙값(≥3 에피소드). Baseline B: 같은 act×combat_type×character의 최근 10개 평균.
- 델타 임계값(실수 플래그): **몬스터 0.10 / 엘리트 0.15 / 보스 0.20**(베이스라인 대비 초과분).
- 6단계 파이프라인: 베이스라인+실수 필터(`:260`) → 병렬 LLM 비평(`:172`, 라운드 스냅샷으로 의무 counterfactual) → 후보→Skill(`:319`) → 캐스케이드 중복 제거(`:361`) → 사전 작성 A/B(`:411`) → 영속(`:423`).
- 사전 작성 A/B(`prewrite_ab.py:268 validate_candidate()`): `fetch_prompt_a`가 로그에서 **바이트 정확 원본 프롬프트** 검색 → 후보 주입 → temp 0.7에서 `redecide_b` N=3 병렬 resample → `run_judge`(skill_helps/skill_unclear/skill_harmful) → `aggregate_strict`: **`skill_harmful` 0 + `sum(hits) >= ceil(total × 2/3)`** 통과.
- 승격 시 `confidence = 0.40 + 0.05 × len(mistake_round_indices)`, `status="probation"`.

**라이프사이클**(`lifecycle.py:74 update_skill_usage_from_run()`):
- per-combat 베이스라인 결과 어트리뷰션 → `CONFIDENCE_MULT`: 개선 ×1.10, 동일 ×0.98, 악화 ×0.85.
- `apply_retirement_policy`(`:192`): `confidence < 0.30 AND usage_count >= 10` 또는 `consecutive_unimproved_runs >= 3` → 비활성화. **시드 스킬은 면제**(하한선 0.40, `:215-219`).
- 병합 파이프라인(`merge_pipeline.py:192 run_merge_pair()`): **듀얼 앵커 A/B** — 신규·기존 각각 앵커로 N=3 replay(temp 0.7, 총 6회), 양쪽 모두 strict 2/3 + zero-harmful 통과해야 병합. 단일 카드/비전투 앵커는 MERGE→REJECT 다운그레이드.

### 4.6 포스트런 파이프라인 순서

`_safe_post_run()` 실행 순서(**코드 기준**, `agent/loop.py:2980`):
1. **memory 추출** — `memory_manager` 도메인별 `*_extractor.py` 실행(combat/route/card_build/event/card_memory).
2. **가이드 통합** — `CONSOLIDATION_EVERY_N_RUNS=1`(매 run; CLAUDE.md의 "5 run마다"는 구버전).
3. **스킬 라이프사이클 단계**(순서): `record_outcome` → noncombat 점수(`noncombat_scorer.py`) → 실수 기반 발견(`mistake_discovery.py`) → library 저장 → 은퇴 스윕 → 카테고리 캡 → 베이스라인 어트리뷰션 → 은퇴 정책 적용 → 재저장.
4. **Mode B 스텁 채우기** — `pending_fill` 스텁을 postrun이 채움.
5. **self-evolution** — `evolution_engine.py:273 run_evolution()`: 멀티턴 도구-사용 루프, `EVOLUTION_MAX_ROUNDS=5`, `READ_ONLY_ROUNDS=2`(순 3 라운드 작성), 3단계 디스패치(`:794`: 도구 작성 → 정적 쿼리 → 동적).
6. **판사 플러시** — `flush_judge_round`로 병합 큐 드레인.

> 비-전투 스킬 발견은 2026-04-23 제거 — 비-전투 지식은 authored seeds + run-derived guides에서만 옴.

**postrun 스위치**: `config.postrun_effectively_enabled()`는 (1) `STS2_POSTRUN_ENABLED=false`이거나 (2) 활성 패밀리에 `analysis` 티어가 없고 `STS2_ANALYSIS_MODEL` override도 없으면 False → `_safe_post_run()`이 memory/skills/evolution/judge 단계 전에 short-circuit. 약한 모델 테스트 시 L4/L5 스토어 오염 방지에 유용. 게임플레이 시간 JSONL 로깅은 영향 없음.

### 4.7 tools 아키텍처

- **gameplay API = 6 도구만**(5 static query + 1 decision). 동적 도구는 gameplay에 노출 안 됨.
- 동적 도구는 `ToolPreprocessor`(pre-LLM 힌트) + `PlanVerifier`(post-plan 검사) + `EvolutionEngine`(직접 dispatch)로 소비.
- 동적 도구는 AST-sandboxed `.py` 파일(`data/evolution/tools/`)로 postrun이 작성.

**경로 해석 단일 체크포인트**(`storage/paths.py:44 data_root()`): 모든 런타임/postrun 스토어 접근자가 거침. 해석 순서: `STS2_DATA_REPO`(절대 경로) > `STS2_DATA_DIR` > 형제 `../AgenticSTS-Data`. **미설정 시** `AgenticSTS/data/`로 폴백(로컬 전용 dev). 런-레벨 기록은 별도 해석(`runs/history.jsonl`). `postrun_effectively_enabled()`(`config.py:1003`)이 False면 `_safe_post_run()`이 단기 종료.

---

## 5. AgenticSTS-Mod (C# 게임 모드)

> **규모**: 10 C# 파일 / **15,739 라인**. .NET 9 / Godot 4.5. CharTyr/STS2-Agent 포크(merge-base `30e39ea`).

> ⚠️ **중요 정정(코드 기반)**: README·루트 CLAUDE.md·`.csproj`가 "Harmony" 스택을 표방하고 `0Harmony.dll`을 참조하지만, 소스 전체에 `HarmonyPatch`/`HarmonyLib`/`Prefix`/`Postfix`/`Transpiler` 사용이 **0건**이다. 즉, 이 포크는 **Harmony 후킹을 하나도 쓰지 않는다**. 모드는 (1) 게임 퍼블릭 싱글톤 API 직접 접근(`CombatManager.Instance.DebugOnlyGetState()`, `RunManager.Instance.DebugOnlyGetState()`, `ActiveScreenContext.Instance.GetCurrentScreen()`), (2) 게임 액션 큐에 enqueue(`RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(...)`), (3) 카드 모델 퍼블릭 메서드(`card.TryManualPlay(target)`), (4) Godot UI 노드 직접 조작(`SubmenuStack.Push`/`ForceClick`), (5) 프레임 대기 안정화 감지(`NGame.ToSignal(SceneTree.ProcessFrame)`), (6) 리플렉션(`BindingFlags.NonPublic`)으로 게임을 제어한다. `0Harmony.dll`은 `Private=false` 출력 미복사 컴파일 전용 참조일 뿐.

### 5.1 부트스트랩과 스레드 마셜링

- **진입점** `ModEntry.cs:9` — `[ModInitializer]` 어트리뷰트로 게임 모딩 프레임워크가 `Initialize()` 호출. 4단계 부트스트랩: shutdown hook 등록 → `GameThread.Initialize()`(게임 스레드 `SynchronizationContext`·thread ID 캡처) → `EnglishLocResolver.Initialize()`(`res://localization/eng/*.json` 46종 로드) → `GameEventService.Start()` → `HttpServer.Start()`.
- **핵심 계약 — 스레드 마셜링** `GameThread.cs:32-64`의 `InvokeAsync<T>()`: HTTP 리스너는 .NET 스레드풀에서 돌지만 게임 상태는 Godot 메인 스레드에서만 안전. 캡처한 `_syncContext.Post`로 작업을 게임 스레드로 마셜링. 이미 게임 스레드면 동기 fast-path. async 오버로드는 `TaskCompletionSource`+`RunContinuationsAsynchronously`로 교착 회피. **모든 상태 접근/액션 실행이 `await GameThread.InvokeAsync(...)` 패턴**을 따른다.

### 5.2 HTTP API 설계

모드가 `localhost:8128`(2026-04-28에 8080→8128 변경, Clash/프록시 충돌 회피)에 REST API 노출. 포트는 `HttpServer.cs:21`의 `DefaultPort=8128`, 환경변수 `STS2_API_PORT`(1~65535)로 override. 호스트는 `127.0.0.1`+`localhost` 둘 다 바인딩(`HttpListener` Host 헤더 prefix 매칭으로 `Host: localhost`가 `127.0.0.1` prefix에 안 걸려 404 떨어지는 것 방지, 크로스플랫폼 안전 — Windows URL ACL 불필요).

`Router.cs::HandleAsync`가 메서드+경로 `if` 체인으로 라우팅(프레임워크 라우터 없음):

| 엔드포인트 | 위치 | 동작 |
|---|---|---|
| `GET /health` | `Router.cs:34` | 서비스명·모드 버전(0.5.5)·프로토콜 버전(`2026-04-06-v1`)·게임 버전 |
| `GET /state` | `Router.cs:54` | `GameThread.InvokeAsync(GameStateService.BuildStatePayload)` → `{ok, request_id, data}` |
| `GET /debug/nodes` | `Router.cs:68` | Godot 노드 트리 디버그 덤프 |
| `GET /actions/available` | `Router.cs:82` | 현재 legal 액션명 배열 |
| `GET /events/stream` | `Router.cs:96` → `HandleEventStreamAsync` | SSE 스트림(§5.8) |
| `POST /action` | `Router.cs:103` | `ActionRequest` 역직렬화 → `GameThread.InvokeAsync(() => GameActionService.ExecuteAsync(...))` |
| 기타 | `Router.cs:123` | 404 `not_found` |

- 응답은 `WriteJsonAsync`로 직렬화(`WriteIndented=true`, `PropertyNamingPolicy=null` → 필드명 snake_case 유지). 에러는 `ApiException`(`StatusCode`/`Code`/`Details`/`Retryable`)을 잡아 `{ok:false, error:{code,message,details,retryable}}` 봉투. 요청마다 `request_id` 부여.
- 핵심 파일: `GameStateService.cs`(**9,316줄**, 시스템 최대 — 상태 직렬화), `GameActionService.cs`(**4,980줄** — 액션 주입), `Server/Router.cs`(268), `Server/HttpServer.cs`(200), `Server/JsonHelper.cs`, `Server/ApiException.cs`, `Game/GameThread.cs`(102), `Game/EnglishLocResolver.cs`(358).

### 5.3 커스텀 파일 (upstream 대비)

`VENDOR.md`가 포크 변경 사항을 기록. 주 커스텀 파일: `GameActionService.cs`, `GameStateService.cs`, `EnglishLocResolver.cs`.

| 영역 | 요약 |
|---|---|
| 선택/덱 | Crystal Sphere 지원, `save_and_quit`, 덱 선택 강화, live 선택 카드 state, `cancel_selection`, Smith 화면 upgrade-preview, 멱등 `confirm_selection` |
| 전투 상태 | 런타임 power 설명 보존; structured pile cards(`draw_cards`/`discard_cards`/`exhaust_cards`) |
| 맵/보스 | `boss_encounter_id`/`second_boss_encounter_id`를 top-level payload에 노출 |
| 보상 | 보상/카드보상 화면에서 `discard_potion` unblock; atomic `resolve_rewards`; reward 옵션에 structured `card_type`/`rarity`/`energy_cost` |
| 번들 | `NChooseABundleSelectionScreen`용 전용 `bundles[]` payload |

### 5.4 상태 직렬화 (`BuildStatePayload`, `GameStateService.cs:169`)

게임 스레드에서 25개 이상 서브 페이로드를 조립해 `GameStatePayload`(`:7979-8044`) 반환. 조립 순서: `ActiveScreenContext.GetCurrentScreen()` → `CombatManager.DebugOnlyGetState()` → `RunManager.DebugOnlyGetState()` → screen/run/map/event/shop/reward/bundles/agent_view 각 빌드. 최종 페이로드는 `state_version=10`, `run_id`, `screen`, `in_combat`, `turn`, `combat_type`, `boss_stage`, `is_final_boss`, `act`, **`boss_encounter_id`/`second_boss_encounter_id`**(VENDOR 커스텀), `available_actions[]`, combat/run/map/selection/event/shop/rest/reward/bundles/modal/agent_view 서브 객체.

- **전투 상태** `BuildCombatPayload`(`:3316`): player HP/block/energy/powers/orbs + **구조화된 pile 카드** `draw_cards`/`discard_cards`/`exhaust_cards`(VENDOR 커스텀), hand/enemies 직렬화.
- **카드** `BuildHandCardPayload`(`:5490`): `card_id`, `name`(영문화), `upgraded`, `card_type`, `target_type`, `requires_target`, `valid_target_indices`, `energy_cost`, `rules_text`/`resolved_rules_text`, `dynamic_values`, `playable`+`unplayable_reason`, 계산된 미리보기 `damage`/`block`/`hits`/`total_damage`, `target_previews`(각 타겟별 `card.UpdateDynamicVarPreview`로 실제 데미지 계산).
- **적** `BuildEnemyPayload`(`:5640`): `enemy_id`, `name`, HP, `block`, `is_alive`/`is_hittable`, `powers`, `intent`. `BuildEnemyIntentPayload`(`:5768`)가 인텐트 타입별 분기(AttackIntent → `GetSingleDamage`/`Repeats`/`GetTotalDamage`, StatusIntent → `CardCount`).
- **맵 노드** `BuildMapGraphNodePayload`(`:5842`): `row`/`col`/`node_type`/`state`/`visited`/`is_current`/`is_available`/`is_start`/`is_boss`/`is_second_boss`/`parents[]`/`children[]`.
- **가용 액션** `BuildAvailableActionNames`(`:3041`): `CanXxx(currentScreen, combatState, runState)` 형태 50개 이상 가드 메서드(`CanEndTurn`/`CanPlayAnyCard`/`CanChooseMapNode`/`CanBuyShopCard`/`CanChooseEventOption`/`CanCrystalSphereSetTool` 등) 순차 호출 → legal 액션명 리스트. 모달 떠 있으면 `confirm_modal`/`dismiss_modal`만 반환.

### 5.5 EventOption.HoverTips 추출 (3단 폴백)

핵심 발견: **이벤트 옵션 hover 데이터는 transient UI-only state가 아니다**. canonical 소스는 `EventOption.HoverTips`(`IHoverTip` 컬렉션). `BuildEventPayload`(`:4931`) → 각 옵션마다 cards/relics/potions/curses 추출. **3단 폴백 전략**:

1. **HoverTips 경로(우선)**: `GetEventHoverTips`(`:6373`)가 옵션이 `EventOption`이면 `.HoverTips ?? empty` 반환, 아니면 리플렉션 `TryGetMemberValue("HoverTips")`. 그 뒤 `ExtractEventHoverTipCards/Relics/Potions`(`:6394+`)가 각 tip의 `.Card`/`.CanonicalModel is CardModel|RelicModel|PotionModel`로 모델 추출. 게임이 미리 렌더링한 `CanonicalModel`을 최우선으로 사용해 정확도 확보.
2. **멤버 리플렉션 경로**: HoverTips 비어있으면 후보 멤버명(`"Card"`/`"CardReward"`/`"PreviewCard"` 등)으로 `TryGetMemberValue` → `CardModel` 탐색.
3. **텍스트 파싱 경로**: 그래도 비어있면 옵션 설명에서 정규식/이름 매칭으로 카드 정보 추출(`ExtractTextCardInfos`). 유물/포션은 `TryBuildRandomRelicPlaceholder`/`TryBuildRandomPotionPlaceholder`로 "random relic/potion" 자리표시자 생성. 저주 위험은 HoverTips `CardType.Curse` + 멤버 리플렉션 + 텍스트 정규식 삼중 경로.

> **역공학 규칙**: C# 모드 작업 시 `sts2.dll`을 `ilspycmd`로 검사한 뒤 UI-only라고 가정하라. UI-node 스크래핑보다 model-level 추출(`CardModel`, `RelicModel`, `PotionModel`, `EventOption.HoverTips`) 선호. reflection probe는 게임 업데이트 시 조용히 깨지므로 `sts2.dll` 변경 후 재검증 필수.

### 5.6 EnglishLocResolver — 로케일 독립성

`EnglishLocResolver.cs`의 목적: 플레이어 UI는 14개 지원 로케일 중 어느 것이든 구동되지만 **HTTP API는 항상 영문**을 내보낸다. `LocManager`의 활성 로케일 상태는 건드리지 않는다.
- `Initialize()`가 `res://localization/eng/{table}.json` 46종 로드 → 리플렉션으로 `LocManager._tables` private 필드·`CultureInfo`/`StringComparer` 프로퍼티 setter 바인딩.
- `WithEnglishTables<T>(Func<T>)`(`:264`): `_tables`를 영문 테이블로 잠시 교체해 `action()` 실행 후 `try/finally`로 원복(게임 스레드에서만 호출 → UI 렌더가 교체된 테이블을 보지 않게).
- `Resolve(LocString)`(`:328`): 변수 없으면 원시 영문 템플릿, 있으면 영문 규칙(복수형 등) 적용. 누락 엔트리면 raw entry key 반환(활성 로케일 텍스트 절대 누출 금지).

### 5.7 액션 주입 (`GameActionService.ExecuteAsync`, `:75`)

`request.action`을 lower-case trim 후 switch 표현식(`:79`)으로 50개 액션을 핸들러에 매핑: `end_turn`, `play_card`, `continue_run`, `abandon_run`, `save_and_quit`, `choose_map_node`, `resolve_rewards`, `claim_reward`, `choose_reward_card`, `select_deck_card`, `cancel_selection`, `confirm_selection`, `proceed`, `open_chest`, `choose_treasure_relic`, `choose_event_option`, `crystal_sphere_*`(3종), `choose_rest_option`, `open_shop_inventory`, `buy_card`, `buy_relic`, `buy_potion`, `remove_card_at_shop`, `select_character`, `embark`, `use_potion`, `discard_potion`, `run_console_command`, `confirm_modal`, `dismiss_modal`, `return_to_main_menu`, 멀티플레이어 4종, ascension ± 2종. 매핑 안 되면 `ApiException(409, "invalid_action")`.

**공통 패턴**(모든 핸들러): (1) 화면/전투 상태 획득 → (2) `GameStateService.CanXxx` 가드 검증(실패 시 409) → (3) `request.*` 필드 검증 → (4) 게임 API/노드 조작 실행 → (5) `await WaitForXxxTransitionAsync(timeout)`로 프레임 단위 폴링하며 안정 감지 → (6) `ActionResponsePayload`(`{action, status, stable, message, state}`) 반환.

**대표 핸들러**:
- `end_turn`: `RunManager.ActionQueueSynchronizer.RequestEnqueue(new EndPlayerTurnAction(me, roundNumber))`(`:171`) → 라운드 번호 변경으로 안정 감지.
- `play_card`(`:233`): `card_index`로 손패 선택, `ResolveCardTarget`으로 타겟 결정, `card.TryManualPlay(target)`(`:295`)로 게임 퍼블릭 메서드 호출.
- `buy_card`(`:2949`): `GetMerchantCardEntries`로 상점 목록, `entry.IsStocked` 검증, `entry.OnTryPurchaseWrapper(inventory)`로 구매.
- `choose_event_option`(`:2373`): Crystal Sphere 분기. 이벤트 종료 시 `proceedButton.ForceClick()` 또는 `NEventRoom.Proceed()`; 진행 중이면 `RunManager.EventSynchronizer.ChooseLocalOption(option_index)`(`:2474`).
- 리플렉션 경로: `InvokePrivateVoid`(`:4860`, `BindingFlags.NonPublic`)이 게임이 퍼블릭 API로 노출 안 하는 내부 조작 처리.

> **핵심 계약**: 액션 응답에 갱신된 **전체 `GameStatePayload`**를 실어 보낸다 → Python 에이전트가 폴링/재시도 없이 단일 요청-응답으로 다음 결정. 안정되면 `stable=true, status="completed"`, 타임아웃이면 `stable=false, status="pending"`.

### 5.8 SSE 이벤트 스트림 (`GET /events/stream`, 폴링 diff 기반)

`GET /events/stream`은 **폴링 기반 diff 스트림**(게임 자체 이벤트 훅이 없어 — §5.1의 Harmony 미사용과 일관). 두 컴포넌트 협력:

**`GameEventService.cs`**(폴링·diff 발행):
- **폴링 루프** `PollLoopAsync`(`:148`): `GameThread.InvokeAsync(GameStateService.BuildStatePayload)`로 `DefaultPollIntervalMs`=120ms(환경변수 `STS2_EVENT_POLL_MS`, 16~5000 범위)마다 전체 상태 빌드 → `ProcessState`.
- **StateDigest diff** `ProcessState`(`:173`) + `StateDigest.FromState`(`:341`): 직전 상태와 현재 상태의 요약(RunId/Screen/InCombat/Turn/AvailableActions/ActionSignature/…)을 비교해 typed 이벤트 발행 — `session_started`/`screen_changed`/`combat_started`/`combat_ended`/`combat_turn_changed`/`player_action_window_opened`/`player_action_window_closed`/`route_decision_required`/`reward_decision_required` 등 9종+.
- **구독자 관리** `Subscribe()`(`:100`): 용량 256의 `BoundedChannel`(`DropOldest`) 만들어 `_subscribers` 딕셔너리에 등록. 구독 시점 스냅샷이 있으면 즉시 `stream_ready` 이벤트 전송. `Publish`가 모든 구독자 채널에 `TryWrite`; 쓰기 실패(가득 참)한 구독자는 stale로 제거.
- **이벤트 봉투** `GameEventEnvelope`: `{event_id, type, timestamp_utc(ISO 8601 "O"), data}`.

**`Router.HandleEventStreamAsync`**(`:180`, SSE 프레이밍):
- 응답 헤더 `text/event-stream`/`SendChunked`/`Cache-Control: no-cache`/`Connection: keep-alive`/`X-Accel-Buffering: no`(nginx 버퍼링 방지).
- `GameEventService.Subscribe()`로 구독 → `:stream opened` 주석 프레임.
- 루프: `subscription.Reader.WaitToReadAsync`와 15초 `Task.Delay`를 `Task.WhenAny`로 경합. 15초 하트비트가 이기면 `:heartbeat` 주석; 데이터가 이기면 `WriteSseEventAsync`로 `id: {event_id}\n` + `event: {type}\n` + JSON 줄 단위 `data: {line}\n` + 빈 줄 종료 + `FlushAsync`.
- 클라이언트 단절/취소는 200 정상 종료.

> Python 측 `mcp_client/sse_client.py`는 이 스트림을 **wake-up 신호**로 처리 → 이벤트 도착 시 `/state`를 fetch. SSE 불가 시 `MCP_POLL_INTERVAL`(0.15s) 폴링으로 폴백.

### 5.9 빌드 및 배포

```bash
cd ../AgenticSTS-Mod/STS2AIAgent
dotnet build -c Release       # STS2 게임 DLL 참조 (기본 Steam 경로, STS2_DATA_DIR로 override)
# 산출물: bin/Release/net9.0/STS2AIAgent.dll + STS2AIAgent.pck
```

배포: `STS2AIAgent.dll` + `.pck` + `mod_id.json`을 게임 `mods/` 디렉토리로 복사 후 게임 실행(게임 실행 중엔 DLL 잠김). 사전 빌드 DLL은 `build/mods/STS2AIAgent/`에도 tracking → SDK 없이 clone-and-deploy 가능.

### 5.10 업스트림 동기화 (merge, not rebase)

- 포크 관계: CharTyr/STS2-Agent의 **C# 모드만** vendored(MCP 서버·툴링은 제외 — 에이전트가 자체 클라이언트로 HTTP API에 직접 통신).
- **왜 merge인가**: 여러 머신이 `ShandaAI/AgenticSTS-Mod`에서 pull → rebase 후 force-push는 그 clone들을 깬다. merge는 upstream commit SHA를 보존해 `git log <merge-base>..HEAD`가 delta를 그대로 보여준다.
- 동기화: `git fetch upstream && git merge upstream/main && dotnet build -c Release`.
- `fork-base` tag가 merge-base `30e39ea`를 영구 고정.

---

## 6. AgenticSTS-Data (동결 연구 산출물)

> CC-BY-4.0. frozen-store commit SHA `1888a62`.

### 6.1 디렉토리

```
AgenticSTS-Data/
├── memory/                    # L4 HCM (frozen snapshot)
│   ├── rules.json
│   └── v2/
│       ├── combat_episodes.jsonl   # 전투 에피소드
│       ├── route_memories.jsonl    # 경로 메모리
│       ├── card_builds.jsonl       # 덱 빌드 메모리
│       ├── event_memories.jsonl    # 이벤트 메모리
│       ├── guides.json             # 통합 가이드
│       └── card_memories.json      # per-card 종단 기록
├── skills/                     # L5 라이브러리 (frozen snapshot)
│   ├── skills.json
│   └── skill_usage.jsonl
├── evolution/                 # postrun self-evolution 산출물
│   ├── evolution_log.jsonl
│   ├── judge_log.jsonl
│   ├── write_gate_log.jsonl
│   ├── stub_fill_log.jsonl
│   ├── state_snapshots.jsonl
│   ├── embedding_cache.json
│   ├── l1_l2_l3_index.json
│   ├── contexts/, debug/, tools/
├── runs/
│   ├── history.jsonl           # 385 run-level 행 (298 완료)
│   └── ascension_stats.json
└── experiments/                # per-condition ablation 그룹화
```

**데이터 규모**(release snapshot 직접 집계):

| 스토어 | 파일 | 레코드/항목 |
|---|---|---|
| L4 memory/v2 | `combat_episodes.jsonl` | 3,214(~19.6MB, L4 최대) |
| L4 memory/v2 | `event_memories.jsonl` | 1,553 |
| L4 memory/v2 | `card_builds.jsonl` | 556 |
| L4 memory/v2 | `route_memories.jsonl` | 397 |
| L4 memory/v2 | `card_memories.json` | 329 카드 엔트리 |
| L4 memory/v2 | `guides.json` | combat 158 / route 9 / deck 5 / event 138 |
| L4 memory/ | `rules.json` | 규칙 객체(verified_count/violated_count/confidence) |
| L5 skills | `skills.json` | **5 stub**(`pending_fill`) |
| L5 skills | `skill_usage.jsonl` | 1,149 |
| evolution | `evolution_log.jsonl` | 1,375(2.27MB, PE 제안 포함) |
| evolution | `state_snapshots.jsonl` | 100(3.25MB) |
| evolution | `judge_log.jsonl` | 32 |
| evolution | `write_gate_log.jsonl` | 6 |
| evolution | `tools/` | 7 .py(독 특화: poison/block/survival) |

> ⚠️ `evolution/proposals/`와 `reap_log.jsonl`은 문서에서 언급되나 **실제로 미존재**(`find` 결과 없음). PE 제안은 `evolution_log.jsonl`의 `propose_prompt_edit` action으로 기록. write-gate 판정은 `write_gate_log.jsonl`. `retirement_state.json`은 `{}`(폐기 도구 없음). `consolidation_counter.json`/`distill_counter.json` 모두 `{"count": 0}`.

### 6.2 run 카운트 (298 / 312 / 385)

`runs/history.jsonl`은 **385 run-level 행**; **298**이 완료된 승리/패배 게임으로 논문 말뭉치에 들어간다. 나머지는 non-completing harness 행(abort/interrupt/decision-cap)으로 감사·재현용 보존, 논문 통계에서 제외. Hugging Face `ShandaAI/AgenticSTS-trajectories`는 **312-record 분석 superset**(298 + 14 decision-capped `max_steps` run, 전체 per-decision 로그 포함). `outcome in {victory, defeat}`로 필터하면 논문의 298 복원.

**outcome 분포**(직접 집계, 385행 전체): `defeat` 202, `victory` 96, `agent_abort` 66, `max_steps` 15, `interrupt` 6. 완료 = victory 96 + defeat 202 = **298**. 미완료 87행(agent_abort 66 + max_steps 15 + interrupt 6)은 감사·재현성 보존, 통계 제외. `ABORT_OUTCOMES`(`scripts/reproduce/_lib.py:350`) = `{"agent_abort","mcp_error","interrupt","max_steps"}`가 정확히 87행 정의 → 385 − 87 = 298 정합. 312 = 298 + 14 max_steps(HF superset의 per-decision 로그 포함분). 캐릭터는 대부분 `the silent`(373) — `the ironclad`/`the regent`/`静默猎手` 소수. `game_version` `v0.103.1`, `mod_version` `v0.5.4-xc`, `data_schema_version` 2.

> ⚠️ **SHA 정정**: `1888a62`는 이 워크스페이스의 git 객체가 아님(`git cat-file -t 1888a62` 실패; workspace HEAD는 별개). `AgenticSTS-Data/`는 별도 `.git` 없는 평범한 디렉토리. `1888a62`는 **독립 release되는 AgenticSTS-Data 저장소**의 커밋 SHA — SHA anchor는 release repo 속성이지 이 통합 체크아웃의 속성이 아님.

### 6.3 데이터 스키마

**`runs/history.jsonl`(run-level)** 키:
```
run_id, started_at, ended_at, profile_hash, profile_label, model_profile,
character, target_ascension, actual_ascension, outcome, victory,
final_floor, final_hp, final_max_hp, final_gold, fitness, score,
duration_seconds, steps, llm_calls, total_actions,
combats_won, combats_total, completion_reason, end_reason,
use_llm, memory_enabled, skills_enabled
```

**`memory/v2/combat_episodes.jsonl`(L4)** 키:
```
episode_id, run_id, floor, act, enemy_key, character, combat_type, rounds,
hp_before, hp_after, won, terminal_reason, hp_delta,
total_damage_dealt, total_damage_taken, total_cards_played, deck_size, relics,
timestamp, game_version, mod_version, data_schema_version
```

**전체 per-decision 궤적(305 gzipped 로그)** + 경쟁자 캡처 아카이브는 Hugging Face에(현재 private, 익명 기간 종료 후 공개).

**`memory/v2/route_memories.jsonl`** 키: `memory_id, run_id, act, character, nodes[](floor/node_type/hp_before/hp_after/gold_before/gold_after/cards_gained/cards_removed/relics_gained/potions_gained/completion_reason/summary), hp_start, hp_end, gold_start, gold_end, boss_result, victory_run, fitness`.

**`memory/v2/card_builds.jsonl`** 키: `memory_id, run_id, character, deck_events[], card_play_counts[[card,count]], archetype, build_tags, build_summary, primary_plan, damage_engine, defense_engine, cycle_engine, energy_engine, weak_points, analysis_confidence, build_evidence, starting_deck[], final_deck[], key_cards[], coherence_score`.

**`memory/v2/event_memories.jsonl`** 키: `memory_id, run_id, floor, act, event_id, event_title, chosen_option_index, chosen_option_text, all_options[], all_option_details[], hp_before/after, gold_before/after, cards_gained/lost, relics_gained, potions_gained, run_victory, run_final_floor`.

**`memory/v2/guides.json`** — dict 4 카테고리: `combat_guides`(키 `"door:the silent"` 형식, 값 `guide_id/enemy_key/character/guide_text/trigger_model/mechanic_summary`), `route_guides`(키 `"2:the silent"`), `deck_guides`(키 `"the silent:shiv"`), `event_guides`(키 `"NONUPEIPE:"`).

**`skills/skills.json`** 키: `skill_id, name, category, trigger{state_types/enemy_names/min_act/max_act/hp_below/hp_above/min_deck_size/max_deck_size/requires_cards/character/any_of_relics/requires_hand_capabilities/requires_enemy_powers}, tier, content, lessons, examples, priority, source, source_run_ids, version, confidence, usage_count, success_count, failure_count, verified, status, supplements_seed_id, deactivated_runs, active, superseded_by, recent_noncombat_scores, scaffold{topic/scope/dimensions_to_consider/out_of_scope}`. release 주 스토어는 5개 stub(`stub_the_silent_*`, `status:"pending_fill"`, `content:"TBD - filled by Mode B postrun"`). **실제 seed+evolved 스킬 라이브러리는 `experiments/*/gemini-self-evolve/skills/skills.json`**(gem-b-medium: 23개 = 15 seed + 8 evolved) — ablation 격리 규칙의 구현.

### 6.4 evolution/ 아티팩트

- **`contexts/`**(28 타임스탬프 디렉토리): 각 진화 세션 아카이브. `round_1_prompt.md`(진화 시스템 프롬프트 — "Max 3 improvements per run. Quality > quantity", 도구 분류 `author_tool`/`write_skill`/`update_guide`/`update_card_note`/`get_performance_stats`, 강제 워크플로: 스킬 작성 전 `recall_encounter`+`get_performance_stats`, content ≤400자), `round_N_messages.json`(N=1~6 LLM 호출 로그), `summary.json`(섹션별 토큰 추정).
- **`tools/`**(7 .py): `block_sufficiency_check.py`(`_UNKILLABLE_HP_THRESHOLD=1_000_000`), `poison_turns_to_kill.py`, `poison_kill_and_survive_check.py`, `poison_survival_analysis.py`, `poison_block_survival_plan.py`, `silent_exact_mitigation_line.py`(lru_cache, block/Weak/attack-down 상호작용). 각 도구는 `SCHEMA`/`APPLICABLE_STATES`(["monster","elite","boss"])/`execute()`. `tool_stats.json`: `poison_turns_to_kill` 23,573 호출 / 22,433 성공.
- **`l1_l2_l3_index.json`**(1.19MB): L1/L2/L3 프롬프트 임베딩 인덱스(`text-embedding-3-large`). write-gate `l1_cosine` 검사가 이것 질의 → PE 불변성 규칙(load-bearing) 기계적 강제.
- **`embedding_cache.json`**(2.5MB), **`state_snapshots.jsonl`**(100, 진화 컨텍스트 앵커용 동결 게임 상태).

### 6.5 experiments/ — per-condition 격리

5개 조건 디렉토리: `gem-b-low-2026-04-29`(evolution/만), `gem-b-low-fixed-2026-04-30`·`gem-b-medium-2026-05-01`·`mode-b-fixed-2026-05-04`·`mode-b-smoke-2026-05-03`(전체 evolution+memory+skills 미러링). 각 전체 디렉토리는 `gemini-self-evolve/{evolution,memory,skills}/` 구조로 메인 저장소 미러링 → 조건별 isolated 포스트런 스토어. CLAUDE.md ablation 규칙(`--experiment-tag` + 보통 `--no-postrun`)의 데이터 격리 구현. 후기 실험(medium/mode-b)은 `guide_consolidation_log.jsonl` 포함. `experiments/` 최상위에 README/manifest 없음.

---

## 7. 결과

### 7.1 Fixed-A0 ablation — 스킬 계층에서 가장 큰 차이

| Cell | L5 스킬 | L4 에피소드 | 승리 | 평균 점수 |
|---|:---:|:---:|:---:|:---:|
| `baseline-strict`(scaffold 없음) | — | — | 3/10 | 70.4 |
| `prompt-only` | — | — | 4/10 | 69.6 |
| `mode-a`(hand-authored 스킬) | ✅ A | — | **6/10** | **85.5** |
| `mode-b-frozen`(template-filled 스킬) | ✅ B | — | **6/10** | 83.3 |
| `full-frozen`(스킬 + 에피소드) | ✅ A | ✅ | **6/10** | 82.1 |

N=10/cell; Wilson 95% CI [11,60]/[17,69]/[31,83] for 3/10/4/10/6/10. 동일 프롬프트 셋업에서 Δ(prompt)=+1/10인 반면 **Δ(L5)=+2/10** — 관측된 최대 차이가 스킬 계층. **N=10에서 통계적 유의 아님**(Fisher exact p≈0.37; pooled scaffolded-vs-not p≈0.148; CI 겹침) → 방향성으로 읽을 것. bounded contract 자체가 *matched* accumulating-context 설계를 이기는지는 통제된 후속 연구에 남김(paper §Limitations).

### 7.2 Ascension 사다리 & cross-backbone probe

postrun-writable 스트림은 **A6–A8** 도전; no-postrun 스트림은 A2–A4 정지. Gemini-훈련 L4+L5 스택은 다른 backbone에 적용 시 **backbone-sensitive**(경험적 속성, 전제 아님; 진단 probe, 통제된 전이 연구 아님):

| Backbone | 승리 | 점수 | Δ% |
|---|:---:|:---:|:---:|
| Qwen 3.6-27B | 0/5 → 0/5 | 14.6 → **26.9** | **+84.5** |
| DeepSeek V4-Pro | 0/5 → 0/5 | 41.3 → 33.8 | −18.1 |
| Gemini 3.1-Pro | 3/10 → **6/10** | 70.4 → **82.1** | +16.6 |

### 7.3 accumulating-context 에이전트 대비 — 운영 비교, caveat 공개

두 오픈소스 StS2 에이전트(STS2MCP, CharTyr)는 매 결정마다 단일 growing chat 트랜스크립트를 재전송. 동일 strategic 모델(`gemini-3.1-pro-preview`) Silent-A0 run에서: 경쟁자는 **각 0/5**(평균 floor 17.6/5.6), floor당 **~4× wall-clock**(9.9/8.5 vs **2.3**min — 96%가 provider-reported LLM latency), score 점당 **66–90× 더 많은 fresh(non-cached) 토큰**. 본 에이전트 셀은 game build v0.103.1, 경쟁자는 v0.103.3(2026-05-30 minor patch가 배치 사이에 적용; 본 스택은 v0.103.3에서 재검증). CharTyr의 0/5는 부분적으로 `invalid_action` 인터페이스 버그 — 튜닝된 baseline이 아닌 시험 중 에이전트의 속성 충실히 재현. 전체 토큰 회계 caveat(estimate-vs-measured, decision batching, ≥7× upper bound)는 `docs/experiments/competitor_comparison/RESULTS.md`.

**정확한 토큰 회계**(`RESULTS.md`/`RESULTS.json` 검증, relay 총 실험 지출 **$300.57**):

| 에이전트 | memory 모델 | 승리 | 결정/run | total 토큰 | 캐시 커버리지 | fresh 토큰/점수 |
|---|---|---|---|---|---|---|
| **Ours**(full-frozen) | bounded typed per-decision | **6/10** | ~570 | — | — | **~6.4k**(추정, 상한 가정) |
| STS2MCP(Gennadiyev) | full accumulating transcript | 0/5 | 625 | **464M**(464,268,739 prompt + 54,064 completion) | **90%** | **422k** |
| CharTyr | full accumulating transcript | 0/5 | 106 | **84M**(83,736,249 prompt + 10,785 completion) | **82%** | **571k** |

- **fresh-token 격차 66–90×**; 우리의 모든 action을 5k strategic call로 가정(상한)해도 **≥7×** 유지.
- **per-decision 성장 증거**: accumulating-context 설계의 per-call 프롬프트가 한 런 내 **9k → ~500k**로 성장 — 이것 자체가 bounded-memory contract의 증거(우리 컨텍스트는 결정에 걸쳐 flat).
- **결정 경제 비대칭**: 경쟁자는 결정당 1 LLM call; 우리는 ~570 action/런을 ~100 strategic call로 구동(plan execution, fast tier, heuristics). 공개 사이트: "a median of 67 strategic LLM calls per run rather than one call per in-game action".

---

## 8. 보조 도구 — 프런트엔드·리더보드·reproduce·외부 캘리브레이션

### 8.1 frontend(모니터 대시보드, :8081)

React 19 + TypeScript + Vite + Tailwind v4(CSS-first `@import "tailwindcss"`, config 파일 없음) + react-virtuoso(가상화). 라우터/상태관리 라이브러리 없음(plain useState/useRef, 단일 페이지 탭 기반). `AgentDashboard.tsx` + 8 컴포넌트(`AgentTabs`, `CombatView`, `EventCard`, `FilterBar`, `PhaseView`, `RunSelector`, `StatusBar`, `Timeline`) + `hooks`/`types`/`utils`.

**WebSocket 전용(SSE 아님)** — `ws://host:port/ws/events`. 백엔드 `src/monitor/server.py`(FastAPI `create_monitor_app`) + `event_bus.py`(모듈레벨 싱글턴, 구독자별 `queue.Queue(maxsize=2000)`, `deque(maxlen=10000)` 링 버퍼, fire-and-forget emit — "monitor never crashes agent").

- **포트 발견**(`App.tsx`): 5초마다 `SCAN_PORT_START=8081`~`SCAN_PORT_END=8099` 병렬 `fetch('http://host:port/api/status')` — `agent_running` boolean 스키마 게이트로 STS2 모니터 식별. 발견된 모든 대시보드 마운트 유지(비활성은 `display:none`) → 각 WebSocket 백그라운드 live. 탭은 `localStorage`(`sts2_monitor_agents_v1`)에 저장.
- **이벤트 스트림**(`hooks/useEventStream.ts`): WS 프레임 = 하나의 `MonitorEvent` JSON. `id`로 중복 제거. 재연결마다 `GET /api/events/history[?after_id=lastSeenId]`로 누락분 backfill. exp backoff 1s→30s. `ai_summary` 이벤트는 timeline 우회해 `Map<parent_id, summary>`로, `EventCard`가 부모 아래 인라인 렌더. `EventType` 25종(state/llm_call/decision/combat_plan/evolution_round/postrun_artifact/…).
- 백그라운드 Haiku 4.5 summarizer가 LLM thinking + 전투 플랜 요약. 발생원: `session_logger.py::_write_event` + `loop.py`. `monitor_init` 라이프사이클 이벤트(monitor_port/game_port/pid/launch_mode)가 타임라인 첫 항목.

### 8.2 leaderboard(공개 리더보드, :5273)

React 19 + Vite + TypeScript + Tailwind v4(`@theme`) + vitest(jsdom) + recharts + zod + motion/react. **백엔드 없음(100% 정적 배포)**. `npm run test`=`vitest run`, `npm run typecheck`=`tsc -b`(composite/프로젝트 참조 빌드, `--noEmit` 아님). 9 테스트 파일(scoring/schemas/loadSubmissions/useTheme + 4 leaf 컴포넌트; 대형 컴포넌트는 미테스트).

> ⚠️ **리더보드는 `history.jsonl`을 런타임에 읽지 않음**. `src/`에서 history/runs/AgenticSTS-Data 참조 0건. 유일한 fetch는 `loadSubmissions.ts` → `fetch('/data/submissions.json')` → Zod `submissionBundleSchema` 런타임 검증 → `SubmissionBundle`. `public/data/submissions.json`은 **목업 6 submissions**. real pipeline(`history.jsonl → submissions.json`)은 "v0.2 work". `App.tsx`에 hard-coded DEMO 배너("DEMO / MOCK DATA — illustrative only; not the paper's results"). 개발 서버 **포트 5273**(모니터 5173 충돌 회피). 데이터 모델: `Ascension`(0-5)·`RunOutcome`(victory/defeat/abort)·`MethodInfo`·`Aggregate`(ceiling/consistency/progress_score)·`Cost`. 정렬: ceiling desc → progress_score_mean desc.

### 8.3 scripts/reproduce (논문 표/그림 즉시 재계산, LLM 호출 없음, 수 초)

```bash
export STS2_DATA_REPO=../AgenticSTS-Data
python -m scripts.reproduce.reproduce_table_2    # 3/10→6/10 five-cell
python -m scripts.reproduce.reproduce_table_3    # cross-backbone probe
python -m scripts.reproduce.reproduce_fig_3      # 토큰 audit
python -m scripts.reproduce.reproduce_fig_4
bash   scripts/reproduce/recompute_all.sh        # 전체 한 번에
```

`_lib.py`(공통 로드), `snapshots/`(동결 참조, `compare_to_snapshot` tol=1.0/1e-2로 검증 → 불일치 시 exit 1). 각 스크립트가 `history.jsonl`을 읽어 condition 필터 적용 → Wilson CI / bootstrap 점수 출력.

**핵심 메커니즘**(`_lib.py`):
- `filter_cell(records, experiment_tag, limit)`(`:355`): 선택은 **오직 `experiment_tag`(정확 문자열 일치) + `outcome`(ABORT_OUTCOMES 제외)만**. `model_profile`/`model_family`/`profile_hash`/`ascension` **미참조**. completion 필터를 limit 적용 **전**에 수행 → 논문 분모와 동일 분모에 first-N cap. `started_at` 오름차순 후 `[:limit]`.
- `derive_score`(`:137`, Eq.(1)): `s = 100 if victory else floor + (52/3)*bosses`; bosses = 3(win)/2(floor≥34)/1(≥18)/0. `history.jsonl`의 `score`/`fitness` 필드 미사용, outcome+final_floor에서 재계산.
- `wilson_ci(wins,n,z=1.96)`(`:157`) Wilson 95% CI [0,100]%. `bootstrap_ci(scores,n_resamples=5000,seed=42)`(`:174`) 고정 시드 결정론적.
- `FIXED_A0_CELLS`(`:24`): 5개 조건 태그 — `gemini-pilot-2026-05-08-A0-baseline`/`-A0-prompt-only`/`-A0-mode-a-makeup`/`-A0-mode-b-frozen`/`-A0-full-frozen`. `CROSS_BACKBONE_CELLS`(`:34`): Qwen/DeepSeek/Gemini(base+full) — **N=10(Gemini, Table 2 재사용), N=5(Qwen/DeepSeek, probe stream, Table 2와 절대 병합 금지)**.

> ⚠️ **태그 기반 그룹핑의 취약점**: 모든 조건 구분이 `experiment_tag` 문자열에 인코딩 — 스크립트가 `model_profile` 등으로 독립 교차검증 안 함. 태그가 잘못 라벨링되면(`_lib.py:42-50` 코멘트가 `auto-mode-b` 태그의 `postrun_enabled=False` 잘못 라벨링 문서화) 스크립트가 잘못된 그룹핑을 충실히 재현.

### 8.4 external_calibration (외부 난이도 앵커)

`README.md` + 4 디렉토리(각 `metadata.yaml` + `snapshot.md`, 총 8 파일 — **스크립트/노트북/데이터 없음, md+yaml만**, 2026-05-28 WebFetch 캡처). 외부 숫자는 난이도 캘리브레이션만, matched baseline 아님. **논문 본문(`.tex`/`.bib`)은 레포에 없음** — "논문이 인용하는 것"은 snapshot/metadata에서 옴.

| 앵커 | 역할 | 상태 |
|---|---|---|
| `agi-eval-spire-2026` | **LLM 프론티어 하단 앵커** — 5 모델×9 런 = **0/45 승**(max floor 33). 논문 3/10→6/10을 0/45 배경 대비 제시 | 확인(불일치 없음) |
| `megacrit-newsletter-may2026` | **인간 A0 상단 앵커** — "16% 인간 A0 승률, 240M 커뮤니티 run" | **미검증**(Steam 페이지 JS 렌더 → WebFetch가 chrome만 반환) |
| `sts2fun-community-stats-2026` | **존재/방법론 앵커** — 239,445 커뮤니티 run, 30.1% all-ascension 승률. Figure 1c 인간-참조 행 | 확인(단 30.1%는 all-ascension, A0 아님) |
| `spirecodex-2026` | **테스트베드 특성화 앵커** — 576 카드/293 유물/115 몬스터/87 encounter/66 이벤트 | **부분 검증**(66 events만 일치; cards 403 vs 576, monsters 111 vs 115 불일치 — base+upgrade 카운트 추정) |

> ⚠️ Mega Crit 16%/240M은 이 스냅샷에서 **독립 확인 불가**. AGI-Eval harness 모호성: external_calibration은 0/45를 "AGI-Eval on plain STS2"로, 반면 `competitor_comparison/PROTOCOL.md:104`는 "AGI-Eval's 0/45 on AI-Spire"로 — 두 문서가 AGI-Eval harness 불일치(파일에서 해결 불가).

### 8.5 scripts/ (~80개)

주요: `run_agent.py`(진입점), `run_ablation.py`(오케스트레이터), `inspect_memory.py`(L4/L5 들여다보기), `apply_patch.py`(게임 버전 패치), `sync_upstream_data.py`(L3 resync), `check_mod_api_coverage.py`(API 스키마 검사), `extract_mechanics_from_dll.py`, `data_sync.py`, `migrate_to_data_repo.py`, 다수 `ab_test_*`/`analyze_*`/`smoke_*`/`backfill_*`/`test_*_ab`.

---

## 9. 개발·운영

### 9.1 의존성(pyproject.toml)

- Python ≥3.12. 이름 `sts2-agent-mcp` v0.1.0.
- 핵심: httpx≥0.27, pydantic≥2.0, anthropic≥0.40, numpy≥1.26, scipy≥1.14, rich≥13, filelock≥3.12.
- optional: `monitor`(fastapi/uvicorn/websockets), `dev`(pytest/pytest-asyncio/pytest-cov/ruff), `eval`(matplotlib — 그림 재렌더링용).
- ruff line-length 100, lint E/F/I/W(E501 ignore), pytest asyncio_mode=auto, testpaths=tests.

### 9.2 주요 명령

```bash
# 에이전트(AgenticSTS/에서)
python -m scripts.run_agent --steps 500 --runs 1          # 단일 run
python -m scripts.run_agent --steps 500 --ascension auto   # ascension 사다리
python -m scripts.run_agent --model-family gemini          # 기본; gpt|qwen|claude|deepseek
python -m scripts.run_agent --no-skills --no-memory        # 계층 ablate
python -m scripts.inspect_memory                           # L4/L5 들여다보기

# 논문 표/그림 재현(LLM 호출 없음, 수 초)
export STS2_DATA_REPO=../AgenticSTS-Data
python -m scripts.reproduce.reproduce_table_2    # 3/10→6/10 five-cell
python -m scripts.reproduce.reproduce_table_3    # cross-backbone
bash   scripts/reproduce/recompute_all.sh

# 테스트/린트
pytest                          # 전체(asyncio_mode=auto)
pytest tests/regression/ -v     # golden-log 회귀(checked-in fingerprint)
pytest -k write_gate            # 토픽 필터
ruff check .                    # PR 전(100자, E/F/I/W)

# C# 모드(AgenticSTS-Mod/STS2AIAgent/에서)
dotnet build -c Release         # STS2 게임 DLL 필요, STS2_DATA_DIR로 override

# 프런트엔드
cd AgenticSTS/frontend && npm install && npm run dev   # 라이브 대시보드 :8081
cd AgenticSTS/leaderboard && npm run dev                # 공개 리더보드 :5273
```

### 9.3 설정(config.py + .env)

- 패밀리 하나 고르면 네 티어가 레지스트리에서 해석. 티어별 모델 override(`STS2_FAST_MODEL`), 패밀리별 effort(`STS2_QWEN_EFFORT_STRATEGIC`), 패밀리별 자격증명.
- 주요 스위치: `STS2_MODEL_FAMILY`, `STS2_POSTRUN_ENABLED`, `STS2_EVOLUTION_ENABLED`, `STS2_DATA_REPO`, `STS2_THINK_EFFORT_<TIER>`, per-run flags `--no-skills`/`--no-memory`/`--no-llm`/`--no-postrun`.
- 모드 연결: `STS2_MCP_URL=http://localhost:8128`, `STS2_SSE_ENABLED`, `STS2_ACTION_DELAY=0.6`.
- OpenAI-compat relay 튜닝: strategic read timeout 120s, fast 45s, hedge·failover.
- 모든 자격증명은 `.env`(`.env.example` 템플릿). `.env`는 gitignore.

### 9.4 코드 스타일(AGENTS.md)

- Python 4-space, ruff 강제(100자), `snake_case` 모듈/함수/파일, `PascalCase` 클래스. 프롬프트 빌더는 `src/brain/prompts/`(private formatter는 underscore prefix). 메모리 스토어는 `src/memory/`, 스킬은 `src/skills/`.
- **immutability**: 게임 상태·메모리 레코드는 frozen dataclass. mutation 대신 새 객체 생성.
- 짧은 파일 환영(높은 응집·낮은 결합). 200–400줄 목표, 800에서 분할. 단, 코어 `loop.py`는 10,793줄로 예외적(모든 상태 타입 처리 통합).
- 코드가 하는 일을 재진술하는 주석 금지. 주석은 **WHY** 설명(숨겨진 제약·워크어라운드·불변량).
- shop/rest/card/event/map 결정에 **기계적 fallback 금지** — LLM이 결정. treasure/hand_select만 기계적 로직 허용.

### 9.5 테스트 가이드라인

- 새 테스트는 `tests/test_*.py`, 관찰 가능한 동작에 집중.
- 결정 로직·파서·메모리 추출·MCP/mod API 계약 변경은 **최소 1개 pytest case 또는 스크립트 기반 회귀 검사** 필수.
- golden log가 깨지면 fingerprint 갱신 전 decision count/state-type delta 조사. rubber-stamp 금지.
- **golden-log 회귀**(`tests/regression/test_golden_logs.py`): `GOLDEN_DIR=tests/fixtures/golden_logs/v0.5.3`의 checked-in 로그 재생. `compute_fingerprint()`(`src/regression/log_replay.py:39`) 비교 항목: `error_count`, `decision_types` 세트, `num_decisions`(±5% 또는 ±5 허용). LLM 결정 로직·파서·MCP/mod API 계약 변경 시 회귀 필수 — fingerprint가 바뀌면 delta 조사 후 합리적 변경이면 fingerprint 갱신.
- 커밋: conventional prefix(`feat:`/`fix:`/`docs:`/`refactor:`/`test:`/`chore:`/`perf:`/`ci:`). L1/L2 프롬프트 편집은 명시적 정당화 단락 필요.

### 9.6 ablation 실험 규칙(`CLAUDE.md`)

실험 run은 개인 진행 상태·병렬 multi-agent 실행 안전성·L4/L5 오염 방지를 위해:

1. **항상 `--experiment-tag <tag>`** — session-local AscensionStats. 전역 캐시 안 씀(병렬 race 방지). 동일 tag로 resume 시 이어짐.
2. **`--ascension auto` 권장** — 각 조건이 A0에서 시작, 자기 승리로 자동 진행. 공정 비교.
3. **experiment_tag 설정 시 stats 쓰기 skip** — per-condition/per-ascension win rate는 post-hoc으로 `history.jsonl`에서 도출.
4. **항상 `--no-postrun`** — 아니면 실험 중 L4/L5 스토어 오염.
5. **`--abandon-existing`** 의미 실험 모드에서 반전 — 매 run abandon, clean slate 보장.
6. **multi-agent 병렬**: 각 에이전트가 `--launch-game --api-port=auto --monitor-port=auto`로 독립 포트. distinct `STS2_MACHINE_ID`. 공유 파일은 `runs/history.jsonl`(`append_dedup` 병합 드라이버, 병렬 안전).
7. **per-experiment 데이터 격리**(`self-evolve`만): `<sibling_repo>/experiments/<tag>/<condition_id>/`로 `STS2_DATA_REPO` 격리, `runs/history.jsonl`은 `STS2_RUNS_HISTORY_REPO`로 부모 루트 유지.
8. **resume**: 같은 tag로 재실행 시 남은 run만 launch.
9. **postrun 모델 parity**(`self-evolve`): `analysis_eq_strategic=True`로 gameplay strategic 모델이 postrun도 실행. effort는 독립(`STS2_THINK_EFFORT_STRATEGIC=low STS2_THINK_EFFORT_ANALYSIS=high`).
10. **조건 필터**: `--conditions <kind>`(comma list) — `baseline-strict`/`prompt-only`/`self-evolve`/`full`.

post-hoc 집계는 `outcome in {victory, defeat}`만 카운트; `agent_abort`/`mcp_error`/`interrupt`는 crash이므로 분모에서 제외.

### 9.7 게임 업데이트 플레이북(`CLAUDE.md`)

STS2 신버전 출신 시:
1. **manifest 작성**: 패치 노트 → `data/patches/v<new>.yaml`(Manifest 모델 스키마). 커밋.
2. **dry run**: `python -m scripts.apply_patch --manifest ... --dry-run --skip-llm`. store별 purge 수 리뷰.
3. **전체 적용**: `python -m scripts.apply_patch --manifest ...`. `data/`를 `data.snapshots/v<old>-pre-v<new>/`로 스냅샷, per-store entity-reference purge, LLM이 변경 엔티티 참조 프롬프트 재작성(diff batch 리뷰), `data/version_compatibility.json` bump.
4. **게임 업데이트**: Steam.
5. **모드 재빌드**: `dotnet build -c Release`. reflection 필드 이름 변경 시 수정(`GameActionService.cs`, `GameStateService.cs`). DLL을 게임 `mods/`에 배포.
6. **모드 버전 설정**: `export STS2_MOD_VERSION=v<new>-xc`; `version_compatibility.json` current.mod_version 갱신.
7. **지식 resync**: 모드가 새 `eng/*.json` 배포 후 `python -m scripts.sync_upstream_data --game-version v<new>`.
8. **API 스키마 검사**: 모드 실행 중 `python -m scripts.check_mod_api_coverage`. 누락/미사용 필드 조사.
9. **회귀**: `pytest tests/regression/ -v`. golden log fingerprint 모두 일치 필수.
10. **live smoke**: `python -m scripts.run_agent --steps 50 --runs 1` — 짧은 run 오류 없이 완료 확인.

불변량: 모든 영구 레코드 `(game_version, mod_version)` 추적 가능. `data.snapshots/`은 덮어쓰기 금지. `--dry-run` 항상 사용 가능.

---

## 10. 핵심 설계 결정과 negative results

### 10.1 PE(prompt evolution) 폐기 — negative result(2026-04-18)

10일간(2026-04-06~16) postrun "Prompt Evolution" 파이프라인이 **33개 프롬프트 패치** 제안, **0개 승격·0개 적용**. 30/33은 A/B replay에서 `INVALID_B`(패치된 프롬프트가 LLM 출력을 schema-invalid로 만듦), 2/33은 positive case 개선 없음, 1/33은 테스트 커버리지 부족.

**실패 원인**:
1. 생성기(generator)가 올바른 grounding 부족 — postrun LLM은 `logs/run_*.jsonl`(상태 전이·결정·결과)을 보지만 *특정 프롬프트 표현이 어떻게 특정 reasoning chain으로 이어지는지* 모름.
2. 프롬프트 편집은 고차원 structured intervention — 스킬은 자유 형식 문자열(trigger 시 검색), 작은 오류는 검색 품질만 저하. 프롬프트 편집은 structured-output LLM 호출의 입력 변이, 작은 오류가 출력 스키마를 깸(blast radius 비대칭).
3. A/B gate의 생존자 편향 — 너무 많은 패치가 `INVALID_B`로 실패해, gate가 행동 효과 평価할 기회 자체가 없음.
4. postrun LLM이 실제 원하는 개선 대부분은 프롬프트 수준이 아님 — "문맥적 휴리스틱 가르치기"(언제 rest, 어떤 카드 시너지)는 자연스럽게 trigger를 가진 스킬이지 universal 프롬프트 수정이 아님.

**결정**: PE 제거(소스 1,053줄 + 테스트 3개 삭제). 학습은 전부 L4 memory + L5 skills로 흐름. L1/L2는 인간 작성 + immutable(게임 버전 패치는 `apply_patch.py`, PE와 무관). 이 10일 33/0 기록은 EMNLP 제출에 보고할 가치 있는 clean empirical finding.

> 1356 테스트 통실(1395 − 39 삭제). `grep -E "prompt_patch|prompt_ab|..."`가 `src/`에서 빈 결과.

### 10.2 모델 라우팅 단일 스위치

패밀리 하나 고르면 네 티어 + effort + provider + fallback chain이 자동 해석. fast/strategic 모델 변경 시 model profile rehash → ascension A0 리셋(의도적).

### 10.3 프롬프트 캐싱

4개 시스템 프롬프트(COMBAT/COMBAT_BOSS/DECKBUILD/STRATEGIC)가 static. run-specific 컨텍스트는 항상 사용자 메시지에만. gameplay는 relay-level 자동 prefix 캐싱에 의존(안정적 combat-start prefix). `cache_control: ephemeral`는 postrun 흐름(memory 추출 Turn 1/2/3)에만 사용.

### 10.4 전투 대화 truncation

`CombatConversation.llm_messages`는 항상 정확히 `[combat_start, "ok", 최신 라운드 state]` 반환(3메시지). 내부 `_messages`는 전체 누적하지만 truncation은 **load** 지점(저장 지점이 아님). `add_round_state`가 Strategic Thread·전투 규칙·적 패턴·포션·키워드 glossary를 *매* 라운드 state에 재주입 → truncated 3-메시지 뷰가 자기 완결적.

### 10.5 Stuck recovery

`_force_unstick()`가 `gs.can_proceed` 확인, `available_actions` 사용, 카운터 항상 리셋. **LLM 실패로 run 종료 금지**.

### 10.6 기계적 fallback 금지

shop/rest/card/event/map 결정에 기계적 fallback 없음 — LLM이 결정. 오직 treasure/hand_select만 기계적 로직 허용.

### 10.7 전투 대화·strategic thread

`CombatConversation`이 fight 내 다중턴 히스토리 누적. 플랜 실행 → 라운드 결과 추가 → 다음 라운드가 전체 히스토리 인식. 전투 종료 시 메모리 추출용 요약 생성. `strategic_note`가 tool 응답에서 추출 → STM._strategic_thread → `## Strategic Thread`로 모든 프롬프트에 주입(intent-driven run context, 50단어 제한).

---

## 11. 정량 메트릭 요약

| 항목 | 값 |
|---|---|
| AgenticSTS/src Python 라인 | 62,165 |
| 최대 파일 | `agent/loop.py` 10,793줄(코어 루프) |
| brain 주요 파일 | `v2_backend.py` 2,160 / `conversation.py` 1,537 / `v2_engine.py` 1,486 |
| postrun 주요 | `context_builder.py` 1,432 |
| memory 주요 | `models_v2.py` 1,408 / `guide_consolidator.py` 1,356 / `write_gate.py` 1,242 |
| 테스트 | 212 파일 / 46,035 라인 |
| scripts | ~80개 |
| C# 모드 | 10 파일 / 15,739 라인 |
| C# 최대 파일 | `GameStateService.cs` 9,316 / `GameActionService.cs` 4,980 |
| 설계 스펙 | 50개(`docs/superpowers/specs/`, 2026-03~05) |
| run 아카이브 | 385 행(298 완료) / HF 312 superset |
| L3 지식 | 577 카드, 121 몬스터, 64 포션, 68 이벤트 |
| L4 레코드(release) | combat 3,214 / event 1,553 / card_build 556 / route 397 / card_mem 329 |
| L5(release) | skills 5 stub / skill_usage 1,149 / experiments 23(15 seed+8 evolved) |
| evolution | evolution_log 1,375 / tools 7 .py(poison·block·survival 특화) |
| 경쟁자 토큰 | STS2MCP 464M(0/5) / CharTyr 84M(0/5); 캐시 90%/82%; fresh/점 422k/571k vs ours ~6.4k |
| strategic LLM 호출/run(중앙값) | ~67 |
| frozen-store SHA | `1888a62`(AgenticSTS-Data) |
| mod merge-base | `30e39ea`(CharTyr/STS2-Agent) |

---

## 12. Active TODOs(`CLAUDE.md`)

- [ ] EventMemory/EventGuide 파이프라인(Python 측), boss-impact 분석, event-aware 스킬 발견 (C# `EventOption.HoverTips` 1차 추출은 이미 `GameStateService.cs`에 landing)
- [ ] Smith 카드 업그레이드 비교(업그레이드 후 버전만 보임)
- [ ] P2b: self-evolution 검증 run(10–20 게임), 도구 생성 검증
- [ ] Phase 5(EMNLP): 평가 프레임워크 — win rate, floor 진행, 스킬 evolution 지표
- [ ] 수동 리뷰: `data/evolution/archive_manual_review/`의 진화 도구/스킬
- [ ] 포션 card_select: 발견형 포션이 전투 중 card_select 트리거 — 전투 인식 컨텍스트 필요
- [ ] Batch API: proxy 미지원 — 동기 폴백 사용; Anthropic-direct 전용
- [ ] act-boss 인식 보상/상점 카드 선택: 현재 act 보스/엘리트 정보를 card_reward/shop 프롬프트에 주입
- [ ] 유연한 포션 사용: 슬롯 만석 시 held 포션이 net benefit면 적극 사용; 더 약한 포션 버리고 더 좋은 포션 픽업 허용
- [ ] L1/L2 슬리밍(slimming): 휴리스틱(4-dimension eval, Boss DPS check, Build Trajectory, Smith-default, HP 보존, 포션 타이밍)을 system.py/reward.py/shop.py/rest.py에서 seed 스킬(L5)로 이관. 목표: L1/L2는 게임 메커닉 + 출력 스키마만, 모든 휴리스틱은 L4/L5에
- [ ] write gate + retriever scope filter(dedup/conflict 설계 §2·§3) — cascade dedup(exact → Jaccard → embedding → LLM judge)
- [ ] 스킬 replay eval — live 검증. 코드 수정 landing(sentinel baseline, schedule[0] 테스트, save/quit reload 재시드). live boss fight `STS2_SKILL_EVAL=true`로 A/B 신호 확인 후 default flip
- [ ] non-replay 스킬 분화: 현재 `record_outcome`/`record_noncombat_outcome`이 whole-run win/loss만 사용 → 스킬이 비슷한 confidence로 수렴. 옵션: (A) floor-가중 비전투 점수, (B) decision-impact 계수, (C) per-combat 스킬 귀속

---

## 13. Future Work

- **동일 코드베이스 accumulating-context 셀** — 릴리스는 조직되어 transcript-appending variant가 condition tag·점수·frozen 스토어를 공유하며 행렬에 *한 행 더*로 추가 가능. bounded contract와 가장 깨끗한 정면 대결. `accum-context-A0` 6번째 셀 설계 완료(`docs/superpowers/specs/2026-05-28-accumulating-context-mode.md`, 미구현). `mode-a`와 동일 프롬프트·hand-authored L5·fixed-A0 Gemini 3.1 Pro·N=10. 유일 delta: typed per-decision 검색 → accumulating raw 트랜스크립트.
- **크로스 캐릭터 커버리지** — headline run은 Silent 타겟; L3/L4/L5 재채워지면 다른 캐릭터로 확장.
- **더 타이트한 통계** — scaffolded variant 간 동등성 검증용 더 큰 per-cell 샘플, 3점 probe 대신 smooth backbone-전이 곡선.
- **템플릿 채우기 너머** — Mode B는 인터페이스 내 템플릿 작성 측정; 개방형 자율 스킬 *발명*(새 trigger 분류, 새 템플릿 패밀리)이 다음 운영점.
- **backbone 적응형 스토어** — frozen-stack 전이는 backbone-sensitive(Qwen +84.5%, DeepSeek −18.1%); per-backbone 스토어 적응·스킬 재검증이 격차 해소 가능.
- **더 긴 호라이즌** — 시각 입력·연속 제어·multi-agent 플레이·typed-contract 설계의 크로스 게임 전이는 의도적 비타겟.

---

## 14. 관련 문서 맵

- **파일별 레퍼런스 카탈로그(16문서, 2026-08-07 추가)** → `docs/catalog/CATALOG_00_INDEX.md` — 각 소스 파일의 경로·라인 수·핵심 심볼·용도·동작 원리·의존관계를 코드 수준에서 망라. 본 문서(시스템 서술·why)·`L1_L5_TEMPLATES.md`(프롬프트 심층)·카탈로그(파일별 레퍼런스·what/how) 3-way 분업. Errata 부록에 본 문서의 코드-불일치 레지스트리 통합.
- 내부 아키텍처·Active TODO·게임 업데이트+ablation 플레이북 → `AgenticSTS/CLAUDE.md`
- 기여자 관례(스타일·커밋 prefix·테스트·에이전트 사용 패턴) → `AgenticSTS/AGENTS.md`
- 논문 프레이밍·headline 결과·quick start → 루트 `README.md`
- 하위 프로젝트 개요 → `AgenticSTS/README.md`, `AgenticSTS-Mod/README.md`, `AgenticSTS-Data/README.md`
- 설계 스펙(50개) → `AgenticSTS/docs/superpowers/specs/`(PE 폐기, write-gate 설계, mistake-driven 발견, accumulating-context mode 등)
- 경쟁자 비교 + 토큰 회계 → `AgenticSTS/docs/experiments/competitor_comparison/RESULTS.md`
- 외부 난이도 앵커(AGI-Eval, 커뮤니티 통계) → `AgenticSTS/external_calibration/`

---

*본 문서는 2026-07-08 기준 루트 README·CLAUDE.md·AGENTS.md·config.py·스펙 문서·정량 메트릭 및 3개 병렬 분석 에이전트(Python 코드베이스·C# 모드·데이터/도구)의 결과를 직접 분석해 작성됐다. 모든 경로는 `file_path:line_number` 형식이며, 정확한 임계값·행 번호·레코드 카운트는 코드 기준이다. 문서 곳곳의 ⚠️ 표시는 문서화와 코드/데이터의 불일치 정정이다(Harmony 미사용, SHA `1888a62` 속성, 리더보드 `history.jsonl` 미읽기, 미존재 파일, external_calibration 미검증 등).*