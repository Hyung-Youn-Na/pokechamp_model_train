# EP-233 — foul-play 대 laya v11rt·v11rtc, EX-174 Blim 일정 128경기씩(CPU)

- 상태: Stopped
- 생성일: 2026-11-18
- 책임자: Claude Code
- 승인 근거·범위: 사용자 지시(2026-11-18 대화, "v11 학습이 완료됐으면 해당 버전과도 foul-play 테스트"). 조건은 [D-211](../decisions/D-211-laya-foulplay-opponent.md)·[D-212](../decisions/D-212-laya-foulplay-blim-teams.md)과 [EX-174](../experiments/EX-174-laya-v10rt-vs-foulplay-blim128.md)를 그대로 쓴다. mock → prepare → execute → export까지 중간 확인 없이 진행한다. 외부 호출 없음.
- 관련 contract / decision / experiment: [C-047](../../../CONTRACTS.md#c-047-viewer-export), [D-211](../decisions/D-211-laya-foulplay-opponent.md), [D-212](../decisions/D-212-laya-foulplay-blim-teams.md), [EP-232](EP-232-laya-foulplay-v10rt.md), [EP-231](EP-231-laya-ladder-postmortem-v11.md), [EX-174](../experiments/EX-174-laya-v10rt-vs-foulplay-blim128.md), [EX-175](../experiments/EX-175-laya-v11rt-vs-foulplay-blim128.md), [EX-176](../experiments/EX-176-laya-v11rtc-vs-foulplay-blim128.md), [EX-171](../experiments/EX-171-laya-v11rt-training.md), [EX-172](../experiments/EX-172-laya-v11rtc-training.md)
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit·미커밋 변경: `research/model-training`, `a4e5964`, EP-231·EP-232의 미커밋 변경이 있다.
- 작업 checkout과 interpreter/launcher: `/workspace`. EP-232와 같다(오케스트레이터 laya venv, laya 워커 `pokechamp/.venv`, foul-play `/workspace/.tools/foul-play/.venv`).
- 새 산출물: `runs/model-training/EX-175/`, `EX-176/`, 뷰어 `/workspace/exports/battle_viewers/ex175/`·`ex176/`, `integration/foulplay/serve_v11.py`
- 참조 원자료(읽기 전용): EX-174 `collection`·`result.json`(봉인), EX-171·EX-172 `checkpoints/selected`, foul-play 사본·추론 자료(EP-232 봉인)

## 목표와 맥락

v11rt(입력 수정만)와 v11rtc(입력 수정 + 정책 교정)를 포화되지 않은 상대 foul-play에 붙여, EX-174의 v10rt(0.331)와 같은 슬롯으로 비교한다. 잠긴 test로는 v11rt와 v10rt가 구별되지 않았다(EX-171).

## 범위와 불변 조건

- **포함**: `integration/foulplay/`(`battle.py`의 `STUDIES` 확장, `serve_v11.py`), `scripts/foulplay-ep232`의 대상 추가, 기록.
- **v11 서빙**: `laya_v10.serve_v10` + `render_v11.install()`. EX-174의 v10rt 서빙과 맞추려고 **usage extension과 guard는 쓰지 않는다**(argmax). 두 실행의 차이는 모델과 입력뿐이다. 서빙 렌더러가 `v11-ladder` 생성기 사본과 같은지 prepare에서 확인한다.
- **보존**: `laya_imitation`·`laya_ladder`·`laya_v10`·`laya_v11`·`pokechamp/imitation` 파일, EX-174 등 기존 산출물·봉인. EX-171·EX-172 실행 디렉터리는 읽기만 한다(봉인되어 있지 않으므로 체크포인트 해시를 manifest에 동결하고 서빙 시작 때 대조한다).
- **자원**: CPU만. EX-175 포트 8100~8103, EX-176 8104~8107. GPU와 EP-231 프로세스는 건드리지 않는다. 실행당 mem-guard 25 GB, 시작 전 `free -g` 확인.
- **순서**: EX-175는 바로, EX-176은 EX-172가 `completed`가 된 뒤 시작한다. 두 실행이 겹치면 CPU를 나눠 쓴다(128코어, 실행당 foul-play 16 + 서빙 8 스레드).

## 완료 기준

- [x] EP-233, EX-175, EX-176 등록, catalog build/check
- [x] 단위 검사 통과, EX-174 일정과 같음(모델 표기만 다름) 확인, v11 렌더 일치 확인
- [ ] EX-175 mock 2/2 → prepare → execute → export, 뷰어 확인 — mock·prepare 완료, execute 60/128에서 사용자 지시로 중지
- [ ] EX-176 mock 2/2 → prepare → execute → export, 뷰어 확인 — mock·prepare 완료, execute 52/128에서 사용자 지시로 중지
- [x] 결과를 EX-175·176, STATUS, catalog에 기록

## 절차

1. `scripts/mem-guard 25 … -- scripts/foulplay-ep232 run EX-175`
2. EX-172 완료 확인 뒤 `scripts/foulplay-ep232 run EX-176`
3. 결과 기록, 사용자 보고

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)과 EP-232와 같다. 자동 재실행 없음.

## 진행

- 2026-11-18 — 등록. 실행기 확장(`STUDIES`의 EX-175·176, v11 서빙). 일정은 EX-174 manifest와 128행 모두 같고 모델 표기만 다르다. v11 서빙 렌더러는 `v11-ladder` 생성기 사본과 같다. 단위 검사 4개 통과.

- 2026-11-18 — EX-175 mock 1승 1패(09:09 KST), EX-176 mock 1승 1패(09:21 KST), 각각 execute 시작. EX-172는 09:14 KST에 완료됐다. 10:52 KST(01:52Z)에 사용자 지시("드라마틱한 성능 개선은 안 되는 것 같다, 조기 종료")로 두 실행을 중지했다. 연결 실행 프로세스 트리를 PID 목록으로 종료했고, foul-play가 결정마다 새로 띄우는 작업 프로세스가 남아 경로 패턴으로 한 번 더 정리했다. laya-play 래더 루프·v11 서빙은 건드리지 않았다. battle-window 표시 파일은 지웠다.

## 결과 및 증거

- [EX-175](../experiments/EX-175-laya-v11rt-vs-foulplay-blim128.md): v11rt 15/0/44(정상 59), 0.254 [0.143, 0.370], EX-174 v10rt 대비 같은 슬롯 −0.051 [−0.211, +0.105].
- [EX-176](../experiments/EX-176-laya-v11rtc-vs-foulplay-blim128.md): v11rtc 12/0/39(정상 51), 0.235 [0.125, 0.364], 같은 슬롯 −0.059 [−0.239, +0.122].
- 둘 다 판정 보류(정상 120 미만). 집계 `runs/model-training/EX-17{5,6}/partial-summary.json`.
