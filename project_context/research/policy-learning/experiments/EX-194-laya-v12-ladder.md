# EX-194 — v12(EX-192) 공식 Showdown gen9ou 래더 대전(GPU 서빙, 2026-11-21 23:59 KST까지)

- 상태: Completed
- 생성일: 2026-11-21
- 책임자: Claude Code
- 관련 exec plan: [EP-237](../plans/EP-237-laya-observed-public-info-input.md)
- 관련 decision: [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-189](EX-189-laya-v11d-ladder-interim.md)(v11d), 같은 계정(nhy_test1629)·같은 팀의 v11rtc·v10rt 래더 기록
- 기준 연구선: `research/model-training`

## 질문 및 목적

사용자 지시(2026-11-21, "v12로 레더 대전도 오후 11:59 까지 진행해주세요"): v12 입력 모델이 사람 래더에서 어떻게 두는지 EX-193(foul-play 128경기)과 병행해 본다.

## 가설 또는 qualification 목표

- **판정 없음(보고 전용, D-191)**: 판 수, 승패, 레이팅 변화, 상대 평균 레이팅을 같은 팀 v11rtc 구간과 나란히 보고한다.

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 모델 | EX-192 selected(epoch 2), laya-play 서빙 이름 `laya-v12` |
| 입력 | laya-play 서빙(`app/integration/laya_v11/serve.py`)에 사용 통계 확장을 먼저 설치하고, 그 위에 `render_v12.install()`(v11 + v12)을 얹는다. v11rtc·v11d 래더 서빙과 같은 순서다. `app/integration/laya_v12/`는 저장소 `integration/laya_v12`의 observe·sets·render_v12와 세트 파일을 그대로 복사했다. EX-193 서빙에는 사용 통계 확장이 없다는 점이 다르다 |
| 팀 | `t95bfb45561`(EX-189 후반·EX-188과 같은 팀) |
| 정책·서빙 | argmax, guard 없음, **GPU 3** 서빙(CPU를 EX-193 foul-play 경기에 남김), laya-play `official.sh` 1판씩 반복 |
| 분량 | 시작부터 2026-11-21 23:59 KST(14:59Z)까지. 연속 3회 실패 시 중단 |

## 실행

- 실행기: `scripts/laya-ladder-ex194`(EX-189 스크립트에서 모델·팀·종료 시각만 바꿈). 로그: `exports/laya-play/runtime/logs/ladder-loop-ex194.log`.
- laya-play 로컬 변경: `app/integration/laya_v11/serve.py`(`laya-v12` 분기), `app/laya_play/bot.py`(`EARLY_HISTORY_MODELS`에 `laya-v12` 추가), `app/integration/laya_v12/` 복사.

## 결과

- 2026-11-21 20:59~23:59 KST 40판, 20승 20패. 레이팅 1330 → 1339(합 +9, 최고 1440). 상대 평균 레이팅 1371이다. 오류·연속 실패는 없었다. 23:59:47 KST에 루프가 멈췄고 서빙이 꺼졌으며 `runtime/serving.ready.json`도 되돌렸다.
- 10턴 이하에 끝난 6판은 모두 승이다(1·7·8·8·9·10턴). 상대가 기권했거나 접속을 끊은 것으로 보인다. 이 6판을 빼면 34판 14승 20패다.
- 같은 래더 봇 MissingNo.ZeroBot(레이팅 1578~1623)과 7번 만나 7패했다. 레이팅 1500 안팎에서 이 상대를 반복해 만나 내려왔다.
- 같은 계정 기록(laya-play `ladder/replays.md`): v11rtc 216판 108승 108패(상대 평균 1362, 합 -70), v11d 11판 5승 6패(합 -17), v10rt 222판 122승 100패(상대 평균 1261, 합 +296).

## 결론 및 후속 작업

- 40판 규모로는 v11rtc와 구별되지 않는다(승률 50%, 상대 평균 비슷). foul-play 상대 결과(EX-193)와 같은 방향이다.
