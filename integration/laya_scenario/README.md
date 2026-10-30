# laya 시나리오 대전: NHJ 경기의 고정 국면부터

NHJ-20261028(v1.1 상대)·NHJ-20261029(v4t 상대) 경기를 원래 국면에서 다시 시작해, 사람이 p1(NHJ 팀)으로 LayaBot v4t(EX-130) 또는 v5t(EX-136)를 상대한다.

| `--scenario` | 국면 | 만드는 방법 |
|---|---|---|
| `b39t2`(기본) | 39번 2턴. 1턴: NHJ Dragapult U-turn(Ninetales 299/322) → Slowking-Galar, 봇 Ninetales-Alola Aurora Veil, 눈 | 1턴이 원본과 같아지는 seed를 찾아 그대로 진행(`seed_search.cjs`) |
| `b38t46` | 38번 46턴. 봇 Gholdengo(299/315) 대 NHJ Zamazenta(방어 +2). 원래 v1.1은 여기서 Trick(둘 다 Leftovers) | 시작만 진행한 뒤 `>eval` 하나로 1~45턴 로그와 46턴 직전 상태를 넣는다(`build_scenario.py`) |
| `b34t15` | 34번 15턴. 봇 Ting-Lu(467/514) 대 NHJ Gholdengo(Air Balloon, 특수공격 +2), 그래스필드 1턴 남음. 원래 v1.1은 여기서 Whirlwind(Good as Gold로 무효)를 7턴 연속 시작 | `b38t46`과 같은 방법 |
| `b126t13` | NHJ-20261029 126번 13턴. 봇 Ting-Lu(510/514) 대 NHJ Corviknight(94%, Leftovers, 막 등장). NHJ 쪽 SR+Spikes 1층, 봇 쪽 SR. 원래 v4t는 여기서 Ruination을 7턴 연속 시작했고, 그동안 Body Press·Roost에 졌다 | `b38t46`과 같은 방법 |
| `b126t37` | 126번 37턴. 봇 Ogerpon(Grass 테라, Teal-Tera, 스피드 +1, 251/301) 대 NHJ Corviknight(67%, 아이템 없음, 지난 턴 교체로 등장). 원래 v4t는 여기서 Encore를 썼다(교체 직후라 반드시 실패) | `b38t46`과 같은 방법. 봇 활성 포켓몬의 테라는 시뮬레이터의 Terastallize를 기록 없이 다시 실행해 만든다 |

- 사람이 `/scenario`를 칠 때마다 같은 국면의 새 판이 만들어진다. 한 번에 한 판이다.
- `b38t46`, `b34t15`는 클라이언트가 이전 턴 기록을 애니메이션으로 재생하므로, 들어가면 **⏭ Skip to end**를 한 번 누른다.
- 봇의 판단 경로는 laya-play·EX-131/137과 같다(공식 클라이언트 스냅샷 → Metamon → 렌더러 v4/v5 → argmax).

## 실행

```bash
cd /workspace
pokechamp/.venv/bin/python integration/laya_scenario/run.py --scenario b34t15 --model v4t --host 0.0.0.0
# --scenario b39t2|b38t46|b34t15|b126t13|b126t37, --model v4t|v5t|v6st|v6ht
```

- 옵션: `--device cpu`(결정당 약 1초), `--gpu N`, `--showdown-port 8000`, `--client-port 8080`, `--bot-name LayaBot`
- 브라우저: `http://<서버>:8080/` → 이름 입력 → 아무 채팅창에 `/scenario`
- 웹 포트(8080)만 넘기면 된다. 클라이언트는 페이지와 같은 주소로 접속하고, 웹 서버가 `/showdown`(웹소켓 포함)을 Showdown 포트로 중계한다. VS Code 터미널 링크를 눌러 자동 포워딩된 경우도, 로컬 포트 번호가 바뀐 경우도 된다.
- 방을 5분 넘게 떠나 있으면 그 판은 사람이 진다. 다시 접속하면 같은 판으로 돌아간다.
- 기록: `.artifacts/laya-scenario/games/<시각>-<모델>-<번호>/events.jsonl`(laya-play와 같은 형식), 로그와 서빙 ready 파일은 `.artifacts/laya-scenario/logs/port-<Showdown 포트>/`

## 구성

| 파일 | 역할 |
|---|---|
| `nhj39_team.txt`, `nhj38_team.txt` | NHJ 팀 B 재구성(아래 가정). 두 판은 성별만 다르다 |
| `nhj34_team.txt` | NHJ 팀 A 재구성(34·35번 경기, 아래 가정) |
| `nhj126_team.txt` | NHJ-20261029 팀(팀 B와 같고 Corviknight 4번째 기술만 공개된 Defog) |
| `battle39_t2.json` | 두 팀, 팀 순서와 1턴 선택, 원래 1턴 로그(봇 시점), 봇 프리뷰 슬롯 |
| `seed_search.cjs` | 1턴 봇 시점 로그가 원본과 같아지는 PRNG seed를 찾아 입력 로그를 만든다 |
| `battle39_t2.inputlog.json` | 찾은 seed(`sodium,d1a5edd9…`)와 2턴 직전까지의 입력 로그 |
| `build_scenario.py` | `b38t46`, `b34t15`, `b126t13`, `b126t37`: 원래 봇 요청(봇 쪽 HP·PP·아이템·순서)과 봇 입력(NHJ 쪽 %·상태·랭크·아이템·테라 사용, 해저드(SR, Spikes 층수, 깐 순서대로), 필드·날씨와 남은 턴)으로 `<stem>.json`, `.inputlog.json`을 만든다. 봇 활성 포켓몬이 테라 상태면 다시 테라스탈하고, NHJ의 Regenerator 포켓몬은 보이지 않은 교체 회복(1/3씩)을 더한다. 활성 포켓몬의 휘발성 효과(대타출동, 도발 등)가 있는 국면, 벤치에 테라한 봇 포켓몬이 있는 국면은 만들지 않는다 |
| `replay_inputlog.cjs`, `check_scenario.py` | 입력 로그를 시뮬레이터에만 넣어 봇 요청·봇 수신 로그가 원본과 같은지, 사람에게 봇의 정확한 HP가 가지 않는지 확인한다: `python check_scenario.py battle34_t15 <NHJ-20261028 dir>` |
| `scenario_server.cjs` | 고정 Showdown(e64915c0e) 실행, `/scenario` 명령, 입력 로그 import, 봇 p2·사람 p1 좌석 배정 |
| `bot.py` | laya-play 봇에서 도전 수락만 뺀 것. 1턴 뒤에 앉으므로 원래 경기의 프리뷰 슬롯을 고정하고, 좌석 배정 때 오는 `|N|`과 빈 `|player|` 줄을 무시한다. 테라 이후에 앉는 경우(`b126t37`) 첫 요청의 테라 폼(Ogerpon-Teal-Tera)을 식별 어댑터가 묶을 수 있게 그 포켓몬에 요청 details를 먼저 넣는다 |
| `run.py` | 서버, 서빙(`scripts/laya-imitation serve`), 봇, 웹 클라이언트(laya-play `laya.html`, `.artifacts/laya-scenario/showdown-client`)를 함께 띄운다 |

## 확인한 것

- `b39t2`: 시뮬레이터에서 봇 시점 로그가 2턴 시작까지 원본과 같다(차이는 아바타 표시뿐). 실제 서버에서 봇의 2턴 모델 입력 `input_sha256`이 원래 39번 경기 2턴 입력과 같다. 스크립트 사람으로 재접속, 8턴 진행, 기권까지 한 판이 정상 종료로 기록됐다.
- `b38t46`: 시뮬레이터가 만든 봇 46턴 요청이 원래 요청과 같고(rqid 제외), 봇이 받는 1~46턴 로그가 원본과 줄 단위로 같다. 사람 쪽에는 봇의 정확한 HP가 보이지 않는다(`|split|p2`). 실제 서버에서 봇의 46턴 모델 입력 `input_sha256`이 원래 38번 경기 46턴 입력(`35fd240c…`)과 같다.
- `b34t15`: 같은 검사를 통과했고, 실제 서버에서 봇의 15턴 모델 입력 `input_sha256`이 원본(`302c60a7…`)과 같다. 시뮬레이터 안에서 그래스필드 1턴, Gholdengo 특수공격 +2·Air Balloon·직전 기술 Nasty Plot을 확인했다.
- `b126t13`, `b126t37`(2026-10-29): `check_scenario.py ... /workspace/data/NHJ-20261029/NHJ-20261029`에서 `SCENARIO OK`. 시뮬레이터 안에서 NHJ 쪽 SR+Spikes 1층(원본처럼 SR 피해가 먼저), 봇 쪽 SR, Ogerpon-Teal-Tera·Grass 테라·스피드 +1·Embody Aspect 상태, Corviknight의 직전 기술 없음을 확인했고, 37턴에 Encore를 넣으면 원본처럼 실패한다. 13턴의 NHJ Slowking은 Regenerator로 394/394(원본 20턴 재등장 100%와 일치)다. 실제 서버(v5t, CPU)에서 봇 입력 `input_sha256`이 원본과 같다(13턴 `58ea3c79…`, 37턴 `ad1816e6…`).
- `b38t46`, `b34t15`의 NHJ 쪽 내부 값 중 HP는 봇이 본 %에 맞는 가장 작은 값(한 번도 안 나온 포켓몬은 최대), PP는 로그의 기술 사용(봇 쪽 Pressure 포함)으로 정했다. 랭크·상태·아이템·테라 사용·Dauntless Shield 사용·직전 기술은 원본을 따른다.

## NHJ 팀 가정

NHJ-20261029 팀(`nhj126_team.txt`)은 팀 B와 종이 같아 팀 B를 그대로 쓰고, 이 세션에서 공개된 Corviknight Defog(124·125번)만 바꿨다. 126번에서 공개된 것(Landorus Rocky Helmet·SR·U-turn, Zamazenta 4기술·Leftovers, Corviknight Body Press·Roost·U-turn·Leftovers, Slowking Sludge Bomb·Future Sight·Slack Off·Heavy-Duty Boots, Ogerpon Ivy Cudgel)은 팀 B와 어긋나지 않는다. 126번에 한 번도 나오지 않은 Dragapult는 팀 B 가정(Choice Specs) 그대로다.

팀 A(34번)는 34·35번에서 공개된 것만 사실이다: Kingambit(4기술, Leftovers, Supreme Overlord), Rillaboom(4기술, Grassy Surge), Gholdengo(Nasty Plot·Make It Rain·Shadow Ball, Air Balloon, Good as Gold), Great Tusk(Rapid Spin·Stealth Rock), Dragapult(Draco Meteor·Shadow Ball). 나머지 기술·아이템(공개되지 않은 아이템은 드러나지 않는 것으로 골랐다)·테라·노력치와 한 번도 나오지 않은 Primarina 전체는 가정이다.

팀 B(38·39번)는 36~39번 경기에서 공개된 기술·아이템·특성만 사실이다. 나머지는 흔한 OU 세트로 채웠다.

- 공개 4기술 전부: Lando-T, Zamazenta, Dragapult, Slowking-Galar. Ogerpon 4번째 기술(Play Rough), Corviknight 4번째 기술(Iron Defense)은 가정이다.
- Dragapult 아이템(Choice Specs), Ogerpon 외 테라 타입, 모든 노력치·성격은 가정이다.
- 1턴 U-turn 피해(23/322)는 이 노력치로 나오는 난수 범위 안이다. 봇은 사람 쪽 HP를 %로만 보므로 봇 입력은 원본과 같다.
