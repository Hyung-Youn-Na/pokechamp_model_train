# laya 시나리오 대전 목록

NHJ-20261028 사람 대전에서 v1.1(`laya-v2t-fix`)이 판단을 그르친 국면을 그대로 다시 열어, 같은 자리에서 다른 모델(v4t, v5t)이 어떻게 두는지 직접 상대하며 비교한다. 예외적인 상황에서 모델끼리 비교하는 용도다. 성적 판정이나 배틀 진행 여부를 정하는 기준으로는 쓰지 않는다.

- 코드: `/workspace/integration/laya_scenario/` (사용법·구현 상세는 그 안의 `README.md`)
- 원본 경기: `/workspace/data/NHJ-20261028/NHJ-20261028/battle-gen9ou-<번호>/`
- 국면마다 봇이 그 턴에 받는 모델 입력(`input_sha256`)이 원래 경기와 같은지 확인했다. 따라서 봇 입장에서는 원래 경기와 같은 자리다.

## 시작하는 법

```bash
cd /workspace
pokechamp/.venv/bin/python integration/laya_scenario/run.py --scenario <시나리오> --model <v4t|v5t> --host 0.0.0.0
```

1. 터미널에 나온 주소(`http://localhost:8080/`)를 연다. VS Code에서 링크를 눌러 자동 포워딩해도 된다(포트 하나로 충분).
2. 이름을 정하고 아무 채팅창에 `/scenario`를 친다. 사용자가 p1(NHJ 팀), LayaBot이 p2로 앉는다.
3. 이전 턴 기록이 애니메이션으로 재생되면 **⏭ Skip to end**를 누른다.
4. 한 판이 끝나면 `/scenario`로 같은 국면을 다시 연다. 모델을 바꾸려면 Ctrl-C로 끄고 `--model`만 바꿔 다시 실행한다.

- 옵션: `--device cpu`(GPU 없이, 결정당 약 1초), `--gpu N`(기본 0), `--showdown-port`/`--client-port`(기본 8000/8080)
- 모델: `v4t` = EX-130(렌더러 v4, 실패 확정 표시), `v5t` = EX-136(렌더러 v5, 상대 아이템 상태·카운터). 기준인 v1.1은 laya-play 패키지에 있다.
- 기록: `/workspace/.artifacts/laya-scenario/games/<시각>-<모델>-<번호>/events.jsonl`(laya-play와 같은 형식: 입력, 확률, 보낸 명령)

## 시나리오

| 명령 | 원본 | 국면 | v1.1이 한 것 | 보는 점 |
|---|---|---|---|---|
| `--scenario b39t2` | 39번 2턴 (v1.1 승) | 봇 Ninetales-Alola(299/322, 오로라베일·눈 직후) 대 NHJ 가라르 야도킹(U-turn으로 등장) | Blizzard. 이후 7턴 연속 Blizzard를 쓰다가 베일·눈을 모두 소모했다 | 불리한 대면에서 교체(Gholdengo)하는지, 같은 기술을 반복하는지 |
| `--scenario b38t46` | 38번 46턴 (NHJ 승) | 봇 Gholdengo(299/315, 막 등장) 대 NHJ Zamazenta(방어 +2, Leftovers). NHJ 남은 포켓몬: Dragapult 52% 맹독, Corviknight 48% | Trick. 둘 다 Leftovers라 아무 효과가 없었다. 이후 Clodsire의 Steel 테라가 결정적 패인이었다 | 효과 없는 행동을 피하는지. 이어서 Clodsire로 받고 맹독으로 견제하는지 |
| `--scenario b34t15` | 34번 15턴 (NHJ 승) | 봇 Ting-Lu(467/514) 대 NHJ Gholdengo(Air Balloon, 특수공격 +2), 그래스필드 1턴 남음 | Whirlwind(Good as Gold로 무효)를 7턴 연속. 그동안 Gholdengo가 +6까지 올려 3마리를 잡았다 | 특성·아이템 때문에 무효인 기술(EQ·Whirlwind·Taunt)을 피하는지, 교체·스텔스록을 고르는지 |

### 지금까지 본 첫 수 (확률은 행동 선택 확률이며 승률이 아니다)

| 시나리오 | v1.1(원래 경기) | v4t | v5t |
|---|---|---|---|
| `b39t2` | Blizzard 0.25 (Gholdengo 교체 0.22) | Gholdengo 교체 0.35 | Gholdengo 교체 0.45 |
| `b38t46` | Trick 0.25 | Shadow Ball 0.26 (Trick 0.24) | Make It Rain |
| `b34t15` | Whirlwind 0.47 (EQ 0.03) | Stealth Rock 0.52 (Whirlwind 0.08) | Stealth Rock |

- v4t·v5t의 `b39t2` 수치, v4t의 `b38t46`·`b34t15` 수치는 시나리오 서버에서 실제로 둔 판에서 나왔다.
- v5t의 `b38t46`·`b34t15`는 NHJ-20261028 회귀 세트 채점(같은 입력, CPU)에서 고른 수다. 확률은 기록하지 않았다.
- 2026-10-28 사용자가 직접 두어 본 소감: v4t·v5t 모두 꽤 만족스럽다.

## 한계

- NHJ 팀은 공개 정보로 재구성했다. 기술·아이템이 일부, 노력치는 전부 가정이다. 그래서 사용자 쪽 능력치·피해량은 원래 경기와 다를 수 있다. 봇은 상대 HP를 %로만 보므로 봇 입력에는 영향이 없다.
- `b38t46`, `b34t15`는 원래 로그와 시뮬레이터 상태를 직접 넣은 국면이다. 사용자 쪽 정확한 HP는 봇이 본 %에 맞는 가장 작은 값이고, PP는 로그의 기술 사용으로 계산했다.
- 고정되는 것은 시작 국면뿐이다. 그 뒤는 난수와 양쪽 선택에 따라 달라진다.
- 대전 방을 5분 넘게 떠나 있으면 사용자가 진다.

## 시나리오 추가·검증

- 새 국면은 `integration/laya_scenario/build_scenario.py`의 `SCENARIOS`(경기, 결정 ID, NHJ 팀 파일)와 `run.py`의 `SCENARIOS`에 한 줄씩 추가한다. 결정 ID는 원본 `events.jsonl`의 `input` 이벤트에서 찾는다.
  - 만들기: `python3 integration/laya_scenario/build_scenario.py <이름> /workspace/data/NHJ-20261028/NHJ-20261028 integration/laya_scenario`
  - 검증: `python3 integration/laya_scenario/check_scenario.py <stem> /workspace/data/NHJ-20261028/NHJ-20261028` → `SCENARIO OK`
- 활성 포켓몬에 대타출동·도발 같은 일시 효과가 걸린 국면, 스텔스록 외의 해저드가 있는 국면은 아직 만들 수 없다(생성기가 거부한다).
- 1턴만 지난 국면은 `b39t2`처럼 seed를 찾아 실제로 진행하는 방법(`seed_search.cjs`)도 있다.
