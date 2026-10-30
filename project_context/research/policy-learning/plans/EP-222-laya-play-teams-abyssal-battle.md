# EP-222 — laya-play 완성 팀으로 v5t·v6st·v6ht 대 Abyssal 비교(GPU2)

- 상태: Active
- 생성일: 2026-10-30
- 책임자: Claude Code
- 승인 근거·범위: 사용자 지시(2026-10-30, laya-play 봇 완성 팀으로 Abyssal 테스트)와 [D-199](../decisions/D-199-laya-play-teams-abyssal-battle.md). 구현, mock, 배틀을 별도 승인 없이 이어서 진행한다.
- 관련 contract / decision / experiment: [EX-145](../experiments/EX-145-laya-play-teams-v5t-v6st-v6ht-battle.md), [EX-143](../experiments/EX-143-laya-v5t-v6st-battle256.md), [EX-144](../experiments/EX-144-laya-v5t-v6ht-battle256.md), [EP-221](EP-221-laya-past-turn-input-v6.md)
- 기준 연구선: `research/model-training`
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv, `pokechamp/.venv`, node. 실행기 `scripts/laya-imitation teamset {collect,mock,prepare,execute,export}`
- 새 산출물과 검증 출력 위치:
  - `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-145`(일정 `collection/` 포함)
  - 뷰어 `/workspace/exports/battle_viewers/ex145/`
- 참조 원자료(읽기 전용): laya-play v1.6.0 팀 파일, EX-136·EX-141·EX-142 selected 체크포인트, v5·v6s·v6h 자료 manifest

## 목표와 맥락

EX-120 재구성 팀 대신 사람이 짠 완성 팀으로 두었을 때, v6st·v6ht가 v5t와 어떻게 다른지 Abyssal 상대로 측정한다. 조건과 판정은 EX-145가 소유한다.

## 범위와 불변 조건

- **포함**: `teamset_battle.py`, `config.py`의 EX-145 경로, `cli.py`의 `teamset` 명령
- **보존**: EX-120 collection과 EX-118~144 산출물·봉인·동작은 그대로 둔다. `comparison.py`·`battle.py`·렌더러는 수정하지 않고 가져다 쓴다.
- **자원**: GPU2·포트 8108만 쓴다. GPU0·GPU1·GPU3은 쓰지 않는다. 외부 프로세스 종료와 장치 reset은 금지한다.
- **외부 호출**: 없다.

## 완료 기준

- [x] 팀 수집·검증·일정 생성과 봉인(`EX-145/collection`): 74팀 모두 검증 통과(smogon 11, blim 63), 유형 weather 12·offense 20·defense 4·balance 38, 학습 노출 서명 24, 원형 이웃 공유 종족 최대 4
- [x] mock(기반 체크포인트 v6ht-initial, CPU, 2경기): 2/2 정상·감사 통과
- [ ] EX-145 prepare·execute(888슬롯)·export, 보고, 뷰어, 봉인
- [ ] POKEMON_EXPERIMENTS, STATUS, catalog build/check

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| 팀 합법성 | 고정 로컬 Showdown 검증기 재검증 | `EX-145/collection/selection.json` | 76팀 중 74팀 채택(서명 중복 2), 거부 0 |
| 일정 구조 | 조합 74 × 시드 2 × 교환 | `EX-145/collection/manifest.json` | 기본 296슬롯, 세 모델 888슬롯 |
| 실전 입력 | mock 2경기 | `EX-145/mock` | 2/2 정상·감사 통과 |

## 진행

- 2026-10-30 — 계획 등록. 수집·mock 완료 뒤 연결 실행 `scripts/laya-imitation-ep222` 시작(06:25 UTC, 로그 `runs/model-training/EP-222-chain.log`).

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 자동 재실행은 없다. 배틀 실행 중에는 worker가 import하는 코드를 수정하지 않는다.

## 결과 및 증거

- 진행 전
