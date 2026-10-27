# EP-218 — laya 렌더러 v5(상대 아이템 상태·상태 카운터) 학습과 배틀 비교(GPU0·GPU2)

- 상태: Active
- 생성일: 2026-10-27
- 책임자: Claude Code
- 승인 근거·범위: 사용자 지시(2026-10-27)와 [D-195](../decisions/D-195-laya-item-state-renderer-v5.md). 사용자가 계획을 승인하면 구현, GPU 학습, 배틀을 별도 승인 없이 이어서 진행한다. 오프라인 결과로 배틀을 거르지 않는다([D-191](../decisions/D-191-no-offline-battle-gate.md)).
- 관련 contract / decision / experiment: [C-055](../CONTRACTS.md#c-055-imitation), [EX-136](../experiments/EX-136-laya-v5-tera-training.md), [EX-137](../experiments/EX-137-laya-v4t-v5t-battle256.md), [EX-138](../experiments/EX-138-laya-head-to-head-v5t.md), [EX-130](../experiments/EX-130-laya-v4-tera-training.md), [EX-124](../experiments/EX-124-laya-v2-tera-knowledge-training.md)
- 기준 연구선: `research/model-training`
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv, `pokechamp/.venv`, node. 실행기 `scripts/laya-imitation v5|compare7|h2h3`, 연결 실행 `scripts/laya-imitation-ep218`
- 새 산출물과 검증 출력 위치:
  - `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/laya-item-state/v1`
  - `.../laya-compact-features/v5`, `.../laya-compact-imitation/v5-all`
  - `.../runs/model-training/EX-136`, `EX-137`, `EX-138`, 연결 실행 로그 `.../runs/model-training/EP-218-chain.log`
  - 뷰어 `/workspace/exports/battle_viewers/ex137/`, `ex138/`
- 참조 원자료(읽기 전용): EX-071 `prepared/`·`preparation/replays.jsonl`·원본 리플레이, 테라 지식 `v1`, EX-124·EX-130 산출물, EX-120 `collection/`, EX-125·EX-131 경기, 사람 대전 `/workspace/data/NHJ-20261027`

## 목표와 맥락

상대 아이템의 미공개·들고 있음·제거(Knock Off, 풍선 터짐, 소모)를 입력에서 구분하고, 상태 카운터(잠듦 턴·Rest, 맹독 카운터, 날씨·필드·벽의 지난 턴)를 표시했을 때, 사람 선택 재현과 배틀 성적이 어떻게 달라지는지 측정한다. 조건과 판정은 EX-136~138이 소유한다.

## 범위와 불변 조건

- **포함**:
  - 파서 선택 필드 `item_state`, `status_counter`, `status_source`, `weather_turn`(`replay.py`, `schema.py`)
  - `item_state.py`(재파싱과 전수 비교), `features_v5.py`, `compact_v5.py`, `data_v5.py`, `evaluation_v5.py`, `tests/test_compact_v5.py`
  - 설정, 학습 Spec `EX136`, 서빙 `--render v5`, CLI `v5`·`compare7`·`h2h3`, 비교 배틀 `EX137`, 직접 대결 `EX138`, 실행기 경로
- **보존**:
  - v1~v4 렌더러 출력은 새 선택 필드가 있어도 바이트 단위로 같다. EX-071 `prepared` 등 기존 자료와 EX-118~135 산출물·봉인·동작은 그대로 둔다.
  - `effect_knowledge.py`와 규칙 파일은 수정하지 않는다. 사람 라벨과 분할은 바꾸지 않는다.
- **자원**:
  - GPU0·포트 8107: 자료, 학습, EX-137
  - GPU2·포트 8108: EX-138(EX-136 봉인 뒤)
  - GPU1·GPU3은 쓰지 않는다. 외부 프로세스 종료와 장치 reset은 금지한다.
- **외부 호출**: 없다.

## 완료 기준

- [x] 파서 새 선택 필드, 단위 검사:
  - Knock Off·풍선·소모·Trick 사례
  - 잠듦(일반·Rest, Sleep Talk 시도 포함)·맹독 카운터·교체 초기화·날씨 시작 턴
  - 사람 대전 23번 T10 이후 `removed/popped`
  - v1~v4 출력 불변
- [x] EX-071 재파싱
  - 새 선택 필드 이외 필드 전수 일치
  - `laya-item-state/v1` 생성·봉인
  - 제거·카운터 행 수 확정
- [x] v5 렌더러(`items`, `counters`)와 단위 검사
  - 23번 T13 Earth Power 피해가 0%가 아님
  - 25번 T10 Earthquake `x0`
  - 미공개 Gholdengo `balloon?`
  - EX-131 Sleep Talk 실패 사례의 `slp t<n> rest` 표시
  - 형식 동결
- [x] v5 정보 캐시, `v5-all` 자료(제외 ≤ 0.005), parity, 봉인
- [ ] EX-136 학습(GPU0), 선택, 지식 held-out, 잠긴 test, EX-130·EX-124 쌍비교, 사람 대전 국면 재추론, 보고, 봉인
- [ ] EX-137 mock 후 256경기(GPU0·8107), 보고, 뷰어, 봉인
- [ ] EX-138 mock 후 256경기(GPU2·8108), 보고, 뷰어, 봉인, 자원 반환
- [ ] POKEMON_EXPERIMENTS, STATUS, catalog build/check, 뷰어 변경일지

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| 파서 의미 보존 | EX-071 전 행 재파싱, 새 선택 필드 이외 스냅샷 필드 비교 | EX-071 `prepared` / `laya-item-state/v1/parity.json` | 131,947/131,947 일치. 그중 7,462행은 상대 `item` None→`lifeorb` 차이만 있다(EX-071 동결 뒤 `replay.py`에 추가된 Life Orb 반동 공개 규칙, D-195와 무관) |
| v1~v4 출력 불변 | 새 선택 필드를 넣은 입력으로 v1·v4 렌더(validation 40), 사람 대전 132결정에서 v5 모듈 없는 렌더 = v4 | `test_compact_v5` | 통과 |
| 아이템 상태·카운터 규칙 | 합성 protocol 사례, 사람 대전 23·25·26번, EX-131 m01-s2-a | `test_imitation_replay` `OptionalPublicStateTests` 3건, `test_compact_v5` 9건 | 통과 |
| 길이 | validation 512 실측 | `EX-136/diagnostics/measure` | 512/512 들어감(전체 최대 945, head 470, 선택지 48). 형식 동결 |
| 전체 검사 | `pytest integration/laya_imitation/tests`, `integration/pokechamp/tests/test_imitation_*`, ruff, compileall | — | laya_imitation 81 통과. pokechamp imitation 112 통과, 실패 2·오류 9는 수정 전 파일에서도 같다(`peft` 없음, transformers 버전 불일치 환경 문제). ruff·compileall 통과 |
| 오프라인·서빙 일치 | `v5 parity` 512행 | `EX-136/diagnostics/parity.json` | 512/512 일치 |
| 실전 파서 | 사람 대전 4경기·EX-131 m01-s2-a events를 `serialize_state`로 재생, EX-137 mock 2경기 | `d195_cases.json`, `EX-137/mock` | 기존 필드 132/132·156/156 일치. mock 2/2 정상·감사 통과, 실전 입력 32/32에 새 필드 있음, 서빙 렌더 v5 |

## 진행

- 2026-10-27 — 계획 등록. 사용자가 상태 카운터 포함(선택지 A)을 고르고 진행을 승인했다.
- 2026-10-27 — 구현 중 같은 부류의 누락을 하나 더 확인해 `item_state`에 넣었다. `[from] item: X`로 효과가 공개된 아이템(Leftovers 등)도 기존 `item` 필드에서는 미공개였다(D-195 결함 1b).
- 2026-10-27 — 재파싱 완료(146초, 2,344 리플레이). train 상대 활성 아이템: 들고 있음 33,547행(그중 기존 필드에서 가려졌던 29,933행), 제거 25,983행(Knock Off 14,392, 풍선 2,653, 소모 8,778, 기타 160).
- 2026-10-27 — v5 자료 생성(정보 캐시 75초), 제외 85행(0.064%), parity 512/512. EX-137 mock 통과. 연결 실행 `scripts/laya-imitation-ep218`을 시작했다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 결함 복구와 중단은 EX-136~138을 참조한다. 자동 재실행은 없다. 연결 실행 스크립트는 단계가 실패하면 그 자리에서 멈춘다. 배틀 실행 중에는 worker가 import하는 코드를 수정하지 않는다.

## 결과 및 증거

- 진행 전
