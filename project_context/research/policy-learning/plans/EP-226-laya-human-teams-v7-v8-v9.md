# EP-226 — laya v7t·v8t·v9t 사람 팀 비교 배틀(GPU0·1·2)

- 상태: Stopped
- 생성일: 2026-11-02
- 책임자: Claude Code
- 승인 근거·범위: 사용자 지시(2026-11-02, "실제 팀 세팅으로 v7 v8 v9 비교, GPU 0·1·2 사용")와 [D-203](../decisions/D-203-laya-human-teams-v7-v8-v9.md)
- 관련 contract / decision / experiment: [EX-159](../experiments/EX-159-laya-human-teams-v7t-v8t-v9t.md), [EX-160](../experiments/EX-160-laya-human-teams-v8lt.md), [EX-145](../experiments/EX-145-laya-play-teams-v5t-v6st-v6ht-battle.md), [EX-153](../experiments/EX-153-laya-v7t-v8t-battle256.md), [EX-158](../experiments/EX-158-laya-v7t-v9t-battle256.md), [EP-224](EP-224-laya-engine-judge-v8.md), [EP-225](EP-225-laya-opponent-threat-v9.md)
- 기준 연구선: `research/model-training`
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv, `pokechamp/.venv`, node. 연결 실행 `scripts/laya-imitation-ep226 run`
- 새 산출물: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-159`(`collection/`, `mock/`, `shards/g0..g2/`), 로그 `.../runs/model-training/EP-226.log`, 뷰어 `/workspace/exports/battle_viewers/ex159/`
- 참조 원자료(읽기 전용): laya-play v1.8.0 `app/laya_play/teams*.json`, EX-149·EX-152·EX-157 체크포인트

## 목표와 맥락

EX-120 재구성 팀 대신 사람이 짠 완성 팀으로 v7t·v8t·v9t의 Abyssal 상대 성적을 같은 슬롯에서 비교한다(D-203).

## 범위와 불변 조건

- **포함**: `integration/laya_teamset/`, `scripts/laya-imitation-ep226`, 기록
- **보존**: laya_imitation·laya_threat·파서·기존 산출물을 바꾸지 않는다. 실행 중인 bash 스크립트는 고치지 않는다.
- **자원**: GPU0·8107, GPU1·8109, GPU2·8108만 쓴다(시작 시 네 GPU 모두 비어 있고 battle-window 표시 없음 확인, EP-224 레인 종료). 외부 프로세스 종료·장치 reset 금지.
- **배틀 표시**: prepare 직전 `.pokechamp-data/battle-window/EX-159`, export 뒤 삭제
- **외부 호출**: 없다.

## 완료 기준

- [x] D-203, EP-226, EX-159 등록, catalog build/check
- [x] collect: 123팀, 검증 탈락 0, 일정 봉인(모델당 492, 묶음당 164 기본 슬롯)
- [x] mock(CPU, v9t 초기 체크포인트 2경기)
- [ ] prepare → 세 묶음 동시 execute → combine → export·뷰어 확인 — execute 중 사용자 요청으로 중지(2026-11-03), combine·export 안 함
- [ ] 추가(2026-11-03): EX-160 v8lt 같은 일정(GPU3·8106) → EX-159 combine 뒤 비교·뷰어 — execute 중 함께 중지
- [x] 중단 결과를 EX 문서, STATUS, catalog에 기록

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 결과·한계 |
|---|---|---|
| 일정·분할 | `integration/laya_teamset/tests/test_schedule.py` | 통과: 기본 슬롯 4N, 쌍 단위 분할, 묶음 안 세 모델 연속 |
| 배틀 경로 | mock 2경기 | 2/2 completed·감사 통과(`EX-159/mock/result.json`) |

## 진행

- 2026-11-02 23:45Z — 사용자 지시로 시작. nvidia-smi: GPU0~3 비어 있음. EP-224 레인(gpu1·gpu1c 종료, ep224b gpu2는 15:43Z EX-154 mock 인자 오류로 멈춤)과 EP-225 레인 모두 종료, battle-window 표시 없음.
- 2026-11-02 — `integration/laya_teamset/` 작성, 단위 검사·ruff 통과. collect: 123팀(smogon 32, blim 62, trained 29), 유형 weather 21·offense 29·defense 6·balance 67, 학습 노출 서명 69, 원형 이웃 공유 종족 최대 4.
- 2026-11-02 23:48Z — `scripts/laya-imitation-ep226 run` 시작(로그 `runs/model-training/EP-226.log`, 묶음 로그 `EP-226-g0..g2.log`). mock 2/2 정상. 23:49Z battle-window 표시, prepare(묶음마다 492슬롯, 체크포인트 v7t `2b654e32…`, v8t `8b9fc653…`, v9t `e0e994be…`). 23:50Z 세 묶음 execute 동시 시작(GPU마다 서빙 3개, 약 6.5~7 GB).
- 2026-11-03 — 사용자 지시("GPU3에서 실행")로 v8lt를 EX-159 일정에 추가([EX-160](../experiments/EX-160-laya-human-teams-v8lt.md)). EX-159가 `laya_teamset` 해시를 동결했으므로 새 패키지 `integration/laya_teamset_v8l/`과 `scripts/laya-imitation-ep226b gpu3`로 둔다(로그 `runs/model-training/EP-226b-gpu3.log`).

- 2026-11-03 04:28Z — 사용자 직접 요청으로 GPU0~3 레인을 모두 중지했다("Abyssal 테스트는 딱히 의미 없는 것 같으니 GPU 0,1,2,3 테스트를 중지", 다음 개선 학습을 위해). `laya-imitation-ep226 run`·`ep226b gpu3` 프로세스 그룹과 그 서빙·Showdown·worker 그룹에 SIGTERM, 모두 종료 확인 뒤 GPU0~3 메모리 0 MiB. 중지 순간 두던 4슬롯의 Showdown worktree 등록을 제거하고 battle-window 표시 EX-159·EX-160을 지웠다. 중간 집계는 각 run의 `stopped.json`.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 자동 재실행은 없다. 실패한 단계에서 멈춘다. mock 실패만 배틀 전에 멈출 수 있다.

## 결과 및 증거

사용자 요청으로 중지, 판정 보류. 중간 결과(모델별 Abyssal 상대): v7t 332-40(0.892), v8t 326-48(0.872), v9t 333-41(0.890), v8lt 302-40(0.883). 같은 슬롯 차이는 모두 ±0.02 안이고 95% 구간이 0을 포함해 구별되지 않는다. 상세는 [EX-159](../experiments/EX-159-laya-human-teams-v7t-v8t-v9t.md#중단-결과)·[EX-160](../experiments/EX-160-laya-human-teams-v8lt.md#중단-결과), 증거 `runs/model-training/EX-159/stopped.json`·`EX-160/stopped.json`.
