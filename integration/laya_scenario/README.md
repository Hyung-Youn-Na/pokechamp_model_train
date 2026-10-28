# laya 시나리오 대전: NHJ-20261028 경기의 고정 국면부터

NHJ-20261028 경기를 원래 국면에서 다시 시작해, 사람이 p1(NHJ 팀)으로 LayaBot v4t(EX-130) 또는 v5t(EX-136)를 상대한다.

| `--scenario` | 국면 | 만드는 방법 |
|---|---|---|
| `b39t2`(기본) | 39번 2턴. 1턴: NHJ Dragapult U-turn(Ninetales 299/322) → Slowking-Galar, 봇 Ninetales-Alola Aurora Veil, 눈 | 1턴이 원본과 같아지는 seed를 찾아 그대로 진행(`seed_search.cjs`) |
| `b38t46` | 38번 46턴. 봇 Gholdengo(299/315) 대 NHJ Zamazenta(방어 +2). 원래 v1.1은 여기서 Trick(둘 다 Leftovers) | 시작만 진행한 뒤 `>eval` 하나로 1~45턴 로그와 46턴 직전 상태를 넣는다(`build_b38t46.py`) |

- 사람이 `/scenario`를 칠 때마다 같은 국면의 새 판이 만들어진다. 한 번에 한 판이다.
- `b38t46`은 클라이언트가 45턴 기록을 애니메이션으로 재생하므로, 들어가면 **⏭ Skip to end**를 한 번 누른다.
- 봇의 판단 경로는 laya-play·EX-131/137과 같다(공식 클라이언트 스냅샷 → Metamon → 렌더러 v4/v5 → argmax).

## 실행

```bash
cd /workspace
pokechamp/.venv/bin/python integration/laya_scenario/run.py --scenario b38t46 --model v4t --host 0.0.0.0
# --scenario b39t2|b38t46, --model v4t|v5t
```

- 옵션: `--device cpu`(결정당 약 1초), `--gpu N`, `--showdown-port 8000`, `--client-port 8080`, `--bot-name LayaBot`
- 브라우저: `http://<서버>:8080/` → 이름 입력 → 아무 채팅창에 `/scenario`
- 웹 포트(8080)만 넘기면 된다. 클라이언트는 페이지와 같은 주소로 접속하고, 웹 서버가 `/showdown`(웹소켓 포함)을 Showdown 포트로 중계한다. VS Code 터미널 링크를 눌러 자동 포워딩된 경우도, 로컬 포트 번호가 바뀐 경우도 된다.
- 방을 5분 넘게 떠나 있으면 그 판은 사람이 진다. 다시 접속하면 같은 판으로 돌아간다.
- 기록: `.artifacts/laya-scenario/games/<시각>-<모델>-<번호>/events.jsonl`(laya-play와 같은 형식), 로그와 서빙 ready 파일은 `.artifacts/laya-scenario/logs/port-<Showdown 포트>/`

## 구성

| 파일 | 역할 |
|---|---|
| `nhj39_team.txt`, `nhj38_team.txt` | NHJ 팀 재구성(아래 가정). 두 판은 성별만 다르다 |
| `battle39_t2.json` | 두 팀, 팀 순서와 1턴 선택, 원래 1턴 로그(봇 시점), 봇 프리뷰 슬롯 |
| `seed_search.cjs` | 1턴 봇 시점 로그가 원본과 같아지는 PRNG seed를 찾아 입력 로그를 만든다 |
| `battle39_t2.inputlog.json` | 찾은 seed(`sodium,d1a5edd9…`)와 2턴 직전까지의 입력 로그 |
| `build_b38t46.py` | 38번 46턴: 원래 봇 46턴 요청(봇 쪽 HP·PP·아이템·순서)과 봇 입력(NHJ 쪽 %·상태·랭크·테라 사용·스텔스록)으로 `battle38_t46.json`, `.inputlog.json`을 만든다 |
| `replay_inputlog.cjs` | 입력 로그를 시뮬레이터에 넣고 한쪽이 받는 로그와 마지막 요청을 출력한다(검증용) |
| `scenario_server.cjs` | 고정 Showdown(e64915c0e) 실행, `/scenario` 명령, 입력 로그 import, 봇 p2·사람 p1 좌석 배정 |
| `bot.py` | laya-play 봇에서 도전 수락만 뺀 것. 1턴 뒤에 앉으므로 원래 경기의 프리뷰 슬롯을 고정하고, 좌석 배정 때 오는 `|N|`과 빈 `|player|` 줄을 무시한다 |
| `run.py` | 서버, 서빙(`scripts/laya-imitation serve`), 봇, 웹 클라이언트(laya-play `laya.html`, `.artifacts/laya-scenario/showdown-client`)를 함께 띄운다 |

## 확인한 것

- `b39t2`: 시뮬레이터에서 봇 시점 로그가 2턴 시작까지 원본과 같다(차이는 아바타 표시뿐). 실제 서버에서 봇의 2턴 모델 입력 `input_sha256`이 원래 39번 경기 2턴 입력과 같다. 스크립트 사람으로 재접속, 8턴 진행, 기권까지 한 판이 정상 종료로 기록됐다.
- `b38t46`: 시뮬레이터가 만든 봇 46턴 요청이 원래 요청과 같고(rqid 제외), 봇이 받는 1~46턴 로그가 원본과 줄 단위로 같다. 사람 쪽에는 봇의 정확한 HP가 보이지 않는다(`|split|p2`). 실제 서버에서 봇의 46턴 모델 입력 `input_sha256`이 원래 38번 경기 46턴 입력(`35fd240c…`)과 같다.
- `b38t46`의 NHJ 쪽 내부 값 중 HP는 봇이 본 %에 맞는 가장 작은 값, PP는 로그의 기술 사용(봇 Kyurem의 Pressure 포함)으로 정했다. 랭크·상태·아이템·테라 사용·Dauntless Shield 사용·Zamazenta의 직전 기술(Iron Defense)은 원본을 따른다.

## NHJ 팀 가정

36~39번 경기에서 공개된 기술·아이템·특성만 사실이다. 나머지는 흔한 OU 세트로 채웠다.

- 공개 4기술 전부: Lando-T, Zamazenta, Dragapult, Slowking-Galar. Ogerpon 4번째 기술(Play Rough), Corviknight 4번째 기술(Iron Defense)은 가정이다.
- Dragapult 아이템(Choice Specs), Ogerpon 외 테라 타입, 모든 노력치·성격은 가정이다.
- 1턴 U-turn 피해(23/322)는 이 노력치로 나오는 난수 범위 안이다. 봇은 사람 쪽 HP를 %로만 보므로 봇 입력은 원본과 같다.
