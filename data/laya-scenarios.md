# laya 시나리오 대전 목록

NHJ 사람 대전에서 모델이 판단을 그르친 국면을 그대로 다시 열어, 같은 자리에서 다른 모델(v4t, v5t)이 어떻게 두는지 직접 상대하며 비교한다. NHJ-20261028은 v1.1(`laya-v2t-fix`), NHJ-20261029는 v4t가 둔 경기다. 예외적인 상황에서 모델끼리 비교하는 용도다. 성적 판정이나 배틀 진행 여부를 정하는 기준으로는 쓰지 않는다.

- 코드: `/workspace/integration/laya_scenario/` (사용법·구현 상세는 그 안의 `README.md`)
- 원본 경기: `/workspace/data/NHJ-20261028/NHJ-20261028/battle-gen9ou-<번호>/`(34·38·39번), `/workspace/data/NHJ-20261029/NHJ-20261029/battle-gen9ou-126/`
- 국면마다 봇이 그 턴에 받는 모델 입력(`input_sha256`)이 원래 경기와 같은지 확인했다. 따라서 봇 입장에서는 원래 경기와 같은 자리다.

## 시작하는 법

```bash
cd /workspace
pokechamp/.venv/bin/python integration/laya_scenario/run.py --scenario <시나리오> --model <v4t|v5t|v6st|v6ht> --host 0.0.0.0
```

1. 터미널에 나온 주소(`http://localhost:8080/`)를 연다. VS Code에서 링크를 눌러 자동 포워딩해도 된다(포트 하나로 충분).
2. 이름을 정하고 아무 채팅창에 `/scenario`를 친다. 사용자가 p1(NHJ 팀), LayaBot이 p2로 앉는다.
3. 이전 턴 기록이 애니메이션으로 재생되면 **⏭ Skip to end**를 누른다.
4. 한 판이 끝나면 `/scenario`로 같은 국면을 다시 연다. 모델을 바꾸려면 Ctrl-C로 끄고 `--model`만 바꿔 다시 실행한다.

- 옵션: `--device cpu`(GPU 없이, 결정당 약 1초), `--gpu N`(기본 0), `--showdown-port`/`--client-port`(기본 8000/8080)
- 모델: `v4t` = EX-130(렌더러 v4, 실패 확정 표시), `v5t` = EX-136(렌더러 v5, 상대 아이템 상태·카운터), `v6st` = EX-141(렌더러 v6s, v5 + 같은 기술 연속 사용 표시 `streak`), `v6ht` = EX-142(렌더러 v6h, 2048토큰 안에서 4턴 이전까지 과거 기록, 봇이 `early_history`를 요청). 기준인 v1.1은 laya-play 패키지에 있다.
- Showdown은 실행할 때마다 고정 체크아웃을 복사한 `.artifacts/laya-scenario/showdown-runtime`에서 돈다(2026-10-30부터). Showdown이 채팅 플러그인 상태 파일을 다시 써도 `/workspace/pokemon-showdown`은 깨끗하게 남아, 배틀 실험과 동시에 써도 된다(EX-144 진행 중 확인).
- 기록: `/workspace/.artifacts/laya-scenario/games/<시각>-<모델>-<번호>/events.jsonl`(laya-play와 같은 형식: 입력, 확률, 보낸 명령)

## 시나리오

| 명령 | 원본 | 국면 | v1.1이 한 것 | 보는 점 |
|---|---|---|---|---|
| `--scenario b39t2` | 39번 2턴 (v1.1 승) | 봇 Ninetales-Alola(299/322, 오로라베일·눈 직후) 대 NHJ 가라르 야도킹(U-turn으로 등장) | Blizzard. 이후 7턴 연속 Blizzard를 쓰다가 베일·눈을 모두 소모했다 | 불리한 대면에서 교체(Gholdengo)하는지, 같은 기술을 반복하는지 |
| `--scenario b38t46` | 38번 46턴 (NHJ 승) | 봇 Gholdengo(299/315, 막 등장) 대 NHJ Zamazenta(방어 +2, Leftovers). NHJ 남은 포켓몬: Dragapult 52% 맹독, Corviknight 48% | Trick. 둘 다 Leftovers라 아무 효과가 없었다. 이후 Clodsire의 Steel 테라가 결정적 패인이었다 | 효과 없는 행동을 피하는지. 이어서 Clodsire로 받고 맹독으로 견제하는지 |
| `--scenario b34t15` | 34번 15턴 (NHJ 승) | 봇 Ting-Lu(467/514) 대 NHJ Gholdengo(Air Balloon, 특수공격 +2), 그래스필드 1턴 남음 | Whirlwind(Good as Gold로 무효)를 7턴 연속. 그동안 Gholdengo가 +6까지 올려 3마리를 잡았다 | 특성·아이템 때문에 무효인 기술(EQ·Whirlwind·Taunt)을 피하는지, 교체·스텔스록을 고르는지 |
| `--scenario b126t13` | 0829 126번 13턴 (NHJ 승) | 봇 Ting-Lu(510/514) 대 NHJ Corviknight(94%, Leftovers, 막 등장). NHJ 쪽 SR+Spikes 1층, 봇 쪽 SR. 봇 남은 포켓몬: Clefable 52%, Latios 88%, Slither Wing 100%, Ogerpon 100% | **v4t**: Ruination 7턴 연속. Body Press에 맞으며 Roost로 회복하는 상대를 못 잡고 쓰러졌다 | 회복 루프에 Ruination을 반복하지 않는지. Whirlwind(해저드 피해), Spikes 2층, Clefable 교체를 고르는지 |
| `--scenario b126t37` | 0829 126번 37턴 (NHJ 승) | 봇 Ogerpon(Grass 테라, 스피드 +1, 251/301) 대 NHJ Corviknight(67%, 아이템 없음, 지난 턴 교체로 등장). 봇 남은 포켓몬: Clefable 37% | **v4t**: Encore. 교체 직후라 반드시 실패한다. 이후 Knock Off 2번을 쓰고 Body Press·U-turn에 쓰러졌다 | 반드시 실패하는 Encore를 피하는지. 이 기술은 v4·v5 실패 표시 규칙에 없다 |

### 지금까지 본 첫 수 (확률은 행동 선택 확률이며 승률이 아니다)

| 시나리오 | v1.1(원래 경기) | v4t | v5t | v6st | v6ht |
|---|---|---|---|---|---|
| `b39t2` | Blizzard 0.25 (Gholdengo 교체 0.22) | Gholdengo 교체 0.35 | Gholdengo 교체 0.45 | — | — |
| `b38t46` | Trick 0.25 | Shadow Ball 0.26 (Trick 0.24) | Make It Rain | — | — |
| `b34t15` | Whirlwind 0.47 (EQ 0.03) | Stealth Rock 0.52 (Whirlwind 0.08) | Stealth Rock | — | — |
| `b126t13` | — | Ruination 0.31 (Spikes 0.31, Whirlwind 0.15) | Ruination 0.38 (Spikes 0.29, Clefable 교체 0.11, Whirlwind 0.08) | Spikes 0.43 (Ruination 0.30, Clefable 교체 0.13, Whirlwind 0.05) | Ruination 0.42 (Whirlwind 0.22, Spikes 0.11, Clefable 교체 0.11) |
| `b126t37` | — | Encore 0.32 (Knock Off 0.27, Clefable 교체 0.23) | Clefable 교체 0.35 (Knock Off 0.24, Encore 0.19, Ivy Cudgel 0.17) | Clefable 교체 0.35 (Knock Off 0.23, Encore 0.20, Ivy Cudgel 0.19) | Knock Off 0.48 (Encore 0.22, Clefable 교체 0.22) |

- v4t·v5t의 `b39t2` 수치, v4t의 `b38t46`·`b34t15` 수치는 시나리오 서버에서 실제로 둔 판에서 나왔다.
- v5t의 `b38t46`·`b34t15`는 NHJ-20261028 회귀 세트 채점(같은 입력, CPU)에서 고른 수다. 확률은 기록하지 않았다.
- `b126t13`·`b126t37`의 v6st 수치는 2026-10-30 시나리오 서버(CPU)에서 실제로 둔 판에서 나왔고, 봇 입력 `input_sha256`이 원본과 같았다. 두 국면 모두 첫 수 시점에는 반복 표시가 붙지 않는다(`b126t13`은 Ting-Lu가 Ruination을 쓰기 전, `b126t37`은 Ogerpon이 Ivy Cudgel을 한 번 쓴 뒤). 반복 표시는 같은 기술을 2턴 이상 쓴 뒤부터 보인다.
- v6ht 수치(2026-10-30, CPU)는 원래 경기 입력에 `early_history`(b126t13 76이벤트·0~8턴, b126t37 282이벤트)가 더해진 입력에서 나왔다. 이 필드를 빼면 `input_sha256`이 원본과 같다(`58ea3c79…`, `ad1816e6…`).
- `b126t13`·`b126t37`의 v4t 수치는 원래 0829 126번 경기(같은 입력)의 수치다. v5t 수치는 2026-10-29 시나리오 서버에서 실제로 둔 판(CPU)에서 나왔고, 봇 입력 `input_sha256`이 원본과 같았다(`58ea3c79…`, `ad1816e6…`).
- 2026-10-28 사용자가 직접 두어 본 소감: v4t·v5t 모두 꽤 만족스럽다.

## 한계

- NHJ 팀은 공개 정보로 재구성했다. 기술·아이템이 일부, 노력치는 전부 가정이다. 그래서 사용자 쪽 능력치·피해량은 원래 경기와 다를 수 있다. 봇은 상대 HP를 %로만 보므로 봇 입력에는 영향이 없다.
- `b38t46`, `b34t15`는 원래 로그와 시뮬레이터 상태를 직접 넣은 국면이다. 사용자 쪽 정확한 HP는 봇이 본 %에 맞는 가장 작은 값이고, PP는 로그의 기술 사용으로 계산했다.
- 고정되는 것은 시작 국면뿐이다. 그 뒤는 난수와 양쪽 선택에 따라 달라진다.
- 대전 방을 5분 넘게 떠나 있으면 사용자가 진다.

## 시나리오 추가·검증

- 새 국면은 `integration/laya_scenario/build_scenario.py`의 `SCENARIOS`(경기, 결정 ID, NHJ 팀 파일)와 `run.py`의 `SCENARIOS`에 한 줄씩 추가한다. 결정 ID는 원본 `events.jsonl`의 `input` 이벤트에서 찾는다.
  - 만들기: `python3 integration/laya_scenario/build_scenario.py <이름> <원본 묶음 디렉터리> integration/laya_scenario`(0828: `/workspace/data/NHJ-20261028/NHJ-20261028`, 0829: `/workspace/data/NHJ-20261029/NHJ-20261029`)
  - 검증: `python3 integration/laya_scenario/check_scenario.py <stem> <원본 묶음 디렉터리>` → `SCENARIO OK`
- 해저드는 스텔스록과 Spikes(층수)를 만들 수 있다. 봇 활성 포켓몬의 테라 상태도 만들 수 있다(126번 37턴).
- 활성 포켓몬에 대타출동·도발 같은 일시 효과가 걸린 국면, Sticky Web·Toxic Spikes가 있는 국면, 벤치에 테라한 봇 포켓몬이 있는 국면은 아직 만들 수 없다(생성기가 거부한다).
- 1턴만 지난 국면은 `b39t2`처럼 seed를 찾아 실제로 진행하는 방법(`seed_search.cjs`)도 있다.
