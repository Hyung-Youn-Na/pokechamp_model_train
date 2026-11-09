# D-204 — laya 렌더러 v10: 지금까지의 정보 전부 + lock + 전략 정보, 2,048토큰

- 상태: Accepted
- 날짜: 2026-11-03

## 맥락

- v2t(EX-125) 이후 v3t~v9t는 EX-120 일정 Abyssal 128경기에서 0.78~0.88에 머물렀다. 같은 실행 비교에서 v2 이후 구별된 개선은 없었다. 사람이 짠 팀 비교(EX-159·160)는 중간에 v7t 0.892, v8t 0.872, v9t 0.890, v8lt 0.883으로 구별되지 않았다. 사용자 요청으로 중지했다.
- 버전마다 정보 모듈 하나씩을 따로 더해 왔다. 그래서 v8(엔진 실패 표시)과 v9(상대 위협)는 각각 v7 위에 따로 붙어 있고, v3의 선공 확률은 v4 이후 계보에서 빠져 있다.
- **사용자 결정**(2026-11-03, 대화):
  1. v6h의 4턴 이전 기록(`longhist`)만 빼고 v1~v9 정보를 모두 기본으로 넣는다.
  2. 입력 한도는 2,048토큰을 기본으로 한다.
  3. 기술 선택지에 lock이 걸리는 정보를 넣는다. 미공개 추정(`locked?`)도 포함한다.
  4. 전략 판단용 정보(#33~41)를 모두 넣는다.
  5. 평가는 Abyssal까지만 한다. 1,024 판본 비교(2,048 효과 분리)는 하지 않는다.
  6. 정보별 확인 지표는 결과 보고에서만 본다. 그 지표로 학습을 중단하거나 방법을 바꾸지 않는다.
  7. 학습 시작점은 Claude가 정한다(결정 4).
  8. 설계 단계다. 자료 생성·측정·학습·배틀은 사용자가 시작을 지시할 때 실행한다.

## 결정

### 1. 정보 범위

번호는 설계 대화의 번호다.

| # | 묶음 | 내용 | 출처 |
|---|---|---|---|
| 1~8 | 기본 상태 | 전장(경과 턴 포함), 사이드, 양측 포켓몬, 상대 도구 상태, 수면·맹독 카운터, 최근 2턴 기록 | v1, v5 |
| 9 | 반복 | `streak <move> x<n> (opp hp …)` | v6s |
| 10~11 | 속도 | `speed:` 줄, `first p` | v2, v3. 둘 다 v9 보정 세트로 계산 |
| 12~17 | 기술 선택지 | 위력·상성·STAB, 실효 위력과 이유, `dmg a-b% KO`, 엔진 확정 실패 `fails`/`bounced`, `likely fails`, `balloon?` | v1, v2, v8, v8l, v5 |
| 18~22 | 교체 선택지 | `takes`, `worst`, `entry`, `hit`, `out`, `risk` | v1, v2, v4, v9 |
| 23~26 | 상대 추정 | `opp set`, `opp watch`, 벤치 `likely`, `opp threat`(최악값과 유력값 둘 다) | v7, v9 |
| 27~32 | lock | 아래 2절 | 새로 추가 |
| 33~41 | 전략 | 아래 3절 | 새로 추가 |

- 넣지 않음: 4턴 이전 기록 텍스트(`longhist`). v3의 `opp set`, `opp threat`, `hit …?`는 v7·v9 것이 대체한다. 규칙 기반 `fails`(v4·v7)는 엔진이 국면을 재구성하지 못한 선택지에만 남는다(v8과 같다).
- `opp threat` 형식: `opp threat: worst <move> a-b% to me (<item>?, tera <type>) | likely <move> p<x> a-b%`. 최악값은 v9 규칙(ACTIVE_FLOOR 20)을 따르고, 유력값은 usage 포함 확률 1위 공격기다.

### 2. lock (#27~32)

| # | 위치 | 조건 | 표시 |
|---|---|---|---|
| 27 | 내 기술 선택지 | 내 액티브가 구애 도구(Band·Specs·Scarf)를 들었다. 받은 도구 포함. Klutz, Magic Room, Embargo면 제외. Trick·Switcheroo 선택지 자체에는 붙이지 않는다 | `; locks` |
| 28 | 내 기술 선택지 | Gorilla Tactics | `; locks` |
| 29 | 내 기술 선택지 | Outrage·Thrash·Petal Dance / Rollout·Ice Ball / Uproar | `; locks 2-3t confuse` / `; locks 5t` / `; locks 3t` |
| 30 | ME 줄 | 이미 고정됐다(구애 도구, Gorilla Tactics, 연속 기술 진행 중) | `\| locked <move> (<원인>)` |
| 31 | OPP 줄 | 상대가 공개된 구애 도구나 Gorilla Tactics로 들어온 뒤 기술을 썼다, 또는 연속 기술 진행 중이다 | `\| locked <move> (<원인>)` |
| 32 | OPP 줄 | 상대 도구가 미공개이고, 들어온 뒤 기술을 1번 이상 썼고, usage상 구애 도구 합산 확률이 0.15 이상이다(`opp watch`와 같은 하한) | `\| locked? <move> p<x>` |

### 3. 전략 정보 (#33~41)

모든 피해는 v9 보정 세트(`laya_threat.spreads`)로 계산하고, 상대의 미공개 정보는 공개 정보와 usage로만 채운다.

| # | 위치 | 규칙 | 표시 |
|---|---|---|---|
| 33 | 사이드 줄 다음 | 생존 수, 생존 HP% 합. 상대 HP 미확인은 100 | `board: me 4 alive 310% \| opp 3 alive 180%` |
| 34 | `speed:` 줄 다음(`turn_action`, 양측 액티브 있음) | 내 hits = 상대 현재 HP ÷ (실패 아닌 내 기술 중 최소 피해가 가장 큰 기술), 올림. 상대 hits = 내 HP ÷ `opp threat` 유력값의 최소 피해, 올림. 선후 = 우선도, 그다음 `first p` ≥ .5. 회복은 무시한다 | `duel: me 2 hits (makeitrain) vs opp 3 hits (kowtowcleave), me first -> win` (`lose`, `even`) |
| 35 | `opp team:` 각 생존 벤치 끝(선봉 결정에서는 상대 6마리 전부) | 내 생존 포켓몬 중 (내 최대 피해 − 받는 유력 최대 피해)가 가장 큰 포켓몬. 동점이면 속도 | `\| answer Great Tusk (out 65%, takes 30%, faster)` |
| 36 | `board:` 줄 끝 | 상대 포켓몬 Y가 내 포켓몬 X를 받는다 = Y가 X에게 받는 최대 피해 ≤ 50%이고, Y가 X에게 주는 피해 ≥ min(50%, X 현재 HP). 상대 생존 포켓몬 중 X를 받는 것이 없으면 X가 내 승리 조건이다. 상대 쪽도 대칭으로 계산한다. 각 최대 2마리 | `\| wincon me Dragapult \| opp Kingambit` (`none`) |
| 37 | ME 줄 기술, OPP 줄 `seen` | 내 기술은 남은 PP ≤ 50%일 때 `roost(3/8)`. 상대는 경기 전체 사용 횟수(`history` + `early_history`, 내 액티브가 Pressure면 사용당 2)를 세고, 최대 PP(PP Up 포함)의 50% 이상 썼을 때 표시 | `roost(3/8)`, `roost(5/8 used)` |
| 38 | `opp set` 줄 다음 | 상대 액티브의 회복 수단: 공개된 회복기와 남은 PP 추정, usage 포함 확률 ≥ .25인 회복기, Leftovers·Black Sludge, Regenerator | `opp heals: roost (seen, 3 left?), regenerator .60` |
| 39 | 내 공격기 선택지 | 상대 생존 벤치 중 이 기술 최대 피해가 가장 작은 포켓몬. 그 피해가 액티브 상대가 받는 피해의 절반 이하이거나 0일 때만 표시 | `; opp wall Heatran 12%` |
| 40 | 테라 기술 선택지 | 테라 후 `opp threat` 최악값을 다시 계산해 상성 배수가 바뀔 때 | `; tera takes kowtowcleave 35-41%` |
| 41 | `board:` 줄 다음 | 상대 생존 벤치 중 진입 피해 ≥ 12%인 포켓몬과 그 값. 상대 해저드 제거기(Defog·Rapid Spin·Mortal Spin·Tidy Up·Court Change): 공개된 것과 usage ≥ .25. 내 제거기 보유 포켓몬 | `hazards: opp entry Gholdengo 25%, Dragapult 12% \| opp remover rapidspin .80 \| my remover Great Tusk` |

### 4. 학습 시작점 (Claude 결정)

`convaiinnovations/laya-typed-decisions@e929ae5c` 원본에서 시작한다. v1~v9과 같은 시작점과 설정이다.

- v7t에서 이어서 학습하면 같은 EX-071 학습 행을 4~6 epoch째 다시 보게 된다. EX-157에서도 validation NLL은 이미 epoch 2에 바닥이었다.
- 입력 형식이 크게 바뀐다(2,048토큰, 새 줄 10여 개, 선택지 한도). v7 형식에 맞춰진 가중치를 이어받을 이점이 작다.
- 시작점과 설정이 같아야 v7t와의 차이를 입력 차이로 읽을 수 있다.

### 5. 길이 한도

- 전체 `max_len` 2,048(EX-142와 같다), `head_max_len` 768, 선택지 64.
- 선택지 한도는 laya `common.build_head`에 48로 고정돼 있다. laya에 선택지 한도 인자(`option_max_len`, 기본 48)를 추가한다. 이 값은 `head_max_len`처럼 체크포인트 config에 저장되고 서빙이 읽는다. 기존 체크포인트는 48 그대로다. 이 변경은 laya 저장소의 별도 PR로 하며 `tests/test_hooks_api.py`를 함께 고친다. 학습·서빙은 그 판을 쓰는 새 worktree에서 한다.
- 사전 측정(validation 512)에서 길이 초과 제외가 0.5%를 넘으면 선택지 72·head 896으로 한 번 올린다. 그래도 넘으면 멈추고 보고한다. 정보를 줄이는 순서는 정하지 않는다(사용자 결정 1·2).

### 6. 평가

- 오프라인: 잠긴 test의 NLL·일치율(v7t와 같은 행 차이)과 정보별 확인 지표는 보고만 한다(D-191, 사용자 결정 6).
- 배틀: EX-120 일정 128슬롯에서 v7t와 v10t를 같은 실행으로 둔다(256경기). 상대는 Abyssal이다. 직접 대결과 사람 팀 일정은 두지 않는다(사용자 결정 5).

## 거절한 대안

- **v7t에서 이어 학습**: 결정 4.
- **1,024 안에 줄여 넣기**: 사용자 결정 2. 2,048 효과를 분리하는 1,024 판본도 지금은 두지 않는다(사용자 결정 5).
- **v8·v9를 각각 유지하고 하나만 고르기**: 둘은 서로 다른 칸(실패 표시, 상대 세트 보정·위협)을 다루며 충돌하지 않는다.
- **사람 팀(EX-159) 일정으로 배틀**: 492슬롯이라 비용이 4배다. EX-120 일정이 v2t 이후 모든 결과와 직접 비교된다.

## 근거와 한계

- 정보를 한꺼번에 넣으므로 어떤 정보가 효과를 냈는지 이 실험으로 나눌 수 없다. 정보별 확인 지표는 보고용이다.
- #34~36·#39·#41은 규칙으로 요약한 값이다. 추정 세트가 틀리면 요약도 틀린다. #36의 정확도(실제 끝까지 살아남은 포켓몬과의 일치)를 보고한다.
- 2,048토큰 학습은 v6h 기준 epoch당 약 2.8배 시간이 걸렸다(EX-142). v10은 긴 기록이 없어 그보다 짧을 것으로 본다.
- Abyssal은 테라를 쓰지 않는 규칙 봇 하나다. 래더 효과를 입증하지 않는다.

## 영향

- 새 코드 `integration/laya_v10/`(렌더러, 사실값, lock·전략 계산, 자료, 학습·평가, 배틀 등록). laya_imitation·laya_engine·laya_threat는 고치지 않고 가져다 쓴다.
- laya 저장소: 선택지 한도 인자(별도 PR)
- 자료 `datasets/generated/laya-compact-features/v10`, `laya-compact-imitation/v10-all`
- 산출물 `runs/model-training/EX-161`, `EX-162`, 뷰어 `exports/battle_viewers/ex162/`
