# EX-189 — v11d(EX-183) 공식 Showdown gen9ou 래더 중간 대전(GPU 서빙, 2026-11-20 23:00 KST까지)

- 상태: Stopped
- 생성일: 2026-11-20
- 책임자: Claude Code
- 관련 exec plan: [EP-236](../plans/EP-236-laya-v11rtc-foulplay-distill-rl.md)
- 관련 decision: [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: 같은 계정(nhy_test1629)·같은 팀의 v11rtc·v10rt 래더 기록(팀별로 나눠 보고)
- 기준 연구선: `research/model-training`

## 질문 및 목적

사용자 지시(2026-11-20, "오늘 오후 11시까지 레더 대전을 진행하고 싶은데 추후 강화학습에 문제가 없도록 해줘")로, 증류 모델 v11d가 사람 래더에서 어떻게 두는지 EX-185와 병행해 본다. EX-188(최종 후보 래더)을 대신하지 않는다.

## 가설 또는 qualification 목표

- **판정 없음(보고 전용, D-191)**: 판 수, 승패, 레이팅 변화, 상대 평균 레이팅을 같은 팀 v11rtc 구간과 나란히 보고한다.
- 병행 조건: EX-185(foul-play 시간 기반 탐색)의 결정 시간 p50이 래더 시작 전과 달라지면(±10%) 래더를 멈춘다.

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 모델 | v11d = EX-183 selected(`model.safetensors` sha256 `a45b13…`), laya-play 서빙 이름 `laya-v11d`(v11 입력, v11rtc와 같은 경로) |
| 팀 | 13:56~14:40 KST `t9ff547d715`(전날 사용자가 고른 blimAI 팀, v11rtc 76판) 8판. 14:40 KST부터 사용자 지시로 `t95bfb45561`(래더 기록 최다·레이팅 기대 대비 초과 승 최고, v11rtc 60판·v10rt 52판, EX-188과 같은 팀) |
| 정책·서빙 | argmax, guard 없음, **GPU 3** 서빙(CPU를 foul-play 경기에 남김), laya-play `official.sh` 1판씩 반복 |
| 분량 | 시작부터 2026-11-20 23:00 KST(14:00Z)까지. 연속 3회 실패 시 중단 |
| 강화학습과의 관계 | 래더는 학습 자료를 만들지 않는다. EX-186 수집(CPU, 로컬 포트 8100~8103)과 포트·계정이 겹치지 않는다. EX-186 갱신(GPU 0~3)은 GPU 3을 서빙(수 GB)과 나눠 쓴다(GPU당 48 GB, 학습 최대 약 30 GB). 23:00 KST에 서빙을 끈다 |

## 실행

- 실행기: `scripts/laya-ladder-ex189`(laya-play `official.sh` 루프, 로그 `exports/laya-play/runtime/logs/ladder-loop-20261120.log`).
- laya-play 로컬 변경: `app/integration/laya_v11/serve.py`·`app/laya_play/bot.py`에 `laya-v11d` 이름을 더했다(입력·정책은 v11rtc와 같음).

## 결과

- 2026-11-20 15:03 KST 사용자 지시("현재 레더 대전은 중지해줘. 보니까 이상한 판단을 많이하네")로 새 판을 멈추고 진행 중인 판을 끝까지 둔 뒤 서빙을 껐다. 모두 11판 5승 6패(`t9ff547d715` 8판, `t95bfb45561` 3판; 팀별 레이팅 정리는 보고 때).
- 마지막 판 66턴(Raging Bolt 51%, Dragon Pulse 고정 대 Dragonite 16%)의 Dondozo 교체: 같은 입력에서 v11rtc도 교체(0.49)였고 v11d는 교체 0.44, Dragon Pulse 일반 0.22 + 테라 0.34 = 0.56. 일반·테라로 나뉜 확률 때문에 argmax가 교체가 됐다. 입력은 상대 선공 확률 0.63과 지진 68~80%로 `duel ... lose`를 보였다. 관측 순서를 속도 추정에 쓰지 않는 점은 [EP-237](../plans/EP-237-laya-observed-public-info-input.md)로 예약했다.

## 결론 및 후속 작업

아직 없다.
