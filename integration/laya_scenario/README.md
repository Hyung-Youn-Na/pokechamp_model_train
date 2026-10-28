# laya 시나리오 대전: battle-gen9ou-39 2턴부터

NHJ-20261028 39번 경기(laya-play v1.1 봇 승)를 1턴이 끝난 국면에서 다시 시작해, 사람이 p1(NHJ 팀)으로 LayaBot v4t(EX-130) 또는 v5t(EX-136)를 상대한다.

- 1턴: NHJ Dragapult 리드 → U-turn(Ninetales 299/322) → Slowking-Galar 등장, 봇 Ninetales-Alola 리드 → Aurora Veil, 눈 날씨.
- 사람이 `/scenario`를 칠 때마다 같은 2턴 국면의 새 판이 만들어진다. 한 번에 한 판이다.
- 봇의 판단 경로는 laya-play·EX-131/137과 같다(공식 클라이언트 스냅샷 → Metamon → 렌더러 v4/v5 → argmax).

## 실행

```bash
cd /workspace
pokechamp/.venv/bin/python integration/laya_scenario/run.py --model v4t --host 0.0.0.0   # 또는 --model v5t
```

- 옵션: `--device cpu`(결정당 약 1초), `--gpu N`, `--showdown-port 8000`, `--client-port 8080`, `--bot-name LayaBot`
- 브라우저: `http://<서버>:8080/` → 이름 입력 → 아무 채팅창에 `/scenario`
- 웹 포트(8080)만 넘기면 된다. 클라이언트는 페이지와 같은 주소로 접속하고, 웹 서버가 `/showdown`(웹소켓 포함)을 Showdown 포트로 중계한다. VS Code 터미널 링크를 눌러 자동 포워딩된 경우도, 로컬 포트 번호가 바뀐 경우도 된다.
- 방을 5분 넘게 떠나 있으면 그 판은 사람이 진다. 다시 접속하면 같은 판으로 돌아간다.
- 기록: `.artifacts/laya-scenario/games/<시각>-<모델>-<번호>/events.jsonl`(laya-play와 같은 형식), 로그와 서빙 ready 파일은 `.artifacts/laya-scenario/logs/port-<Showdown 포트>/`

## 구성

| 파일 | 역할 |
|---|---|
| `nhj39_team.txt` | NHJ 팀 재구성(아래 가정) |
| `battle39_t2.json` | 두 팀, 팀 순서와 1턴 선택, 원래 1턴 로그(봇 시점), 봇 프리뷰 슬롯 |
| `seed_search.cjs` | 1턴 봇 시점 로그가 원본과 같아지는 PRNG seed를 찾아 입력 로그를 만든다 |
| `battle39_t2.inputlog.json` | 찾은 seed(`sodium,d1a5edd9…`)와 2턴 직전까지의 입력 로그 |
| `scenario_server.cjs` | 고정 Showdown(e64915c0e) 실행, `/scenario` 명령, 입력 로그 import, 봇 p2·사람 p1 좌석 배정 |
| `bot.py` | laya-play 봇에서 도전 수락만 뺀 것. 1턴 뒤에 앉으므로 원래 경기의 프리뷰 슬롯을 고정하고, 좌석 배정 때 오는 `|N|`과 빈 `|player|` 줄을 무시한다 |
| `run.py` | 서버, 서빙(`scripts/laya-imitation serve`), 봇, 웹 클라이언트(laya-play `laya.html`, `.artifacts/laya-scenario/showdown-client`)를 함께 띄운다 |

## 확인한 것

- 시뮬레이터에서 봇 시점 로그가 2턴 시작까지 원본과 같다(차이는 아바타 표시뿐).
- 실제 서버에서 봇의 2턴 모델 입력 `input_sha256`이 원래 39번 경기 2턴 입력과 같다.
- 스크립트 사람으로 재접속, 8턴 진행, 기권까지 한 판이 정상 종료로 기록됐다.

## NHJ 팀 가정

36~39번 경기에서 공개된 기술·아이템·특성만 사실이다. 나머지는 흔한 OU 세트로 채웠다.

- 공개 4기술 전부: Lando-T, Zamazenta, Dragapult, Slowking-Galar. Ogerpon 4번째 기술(Play Rough), Corviknight 4번째 기술(Iron Defense)은 가정이다.
- Dragapult 아이템(Choice Specs), Ogerpon 외 테라 타입, 모든 노력치·성격은 가정이다.
- 1턴 U-turn 피해(23/322)는 이 노력치로 나오는 난수 범위 안이다. 봇은 사람 쪽 HP를 %로만 보므로 봇 입력은 원본과 같다.
