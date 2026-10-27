# EP-210 — laya 모듈형 렌더러 v2 학습과 v1·v2 비교

- 상태: Completed
- 생성일: 2026-10-22
- 책임자: Claude Code
- 승인 근거·범위: 현재 사용자 지시와 승인된 계획 / [D-185](../decisions/D-185-laya-modular-renderer-v2.md)
- 관련 contract / decision / experiment: [C-055](../CONTRACTS.md#c-055-imitation), [EX-121](../experiments/EX-121-laya-v2-all-training.md), [EX-122](../experiments/EX-122-laya-v1-v2-battle256.md), [EX-118](../experiments/EX-118-laya-compact-imitation-training.md), [EX-120](../experiments/EX-120-laya-team-generalization128.md)
- 기준 연구선: `research/model-training`
- 실제 작업 branch, 시작 commit, 미커밋 변경: `research/model-training` `feda62f733c1b470364868262c789ec857ef67f5`. 기존 미커밋 변경은 보존한다.
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv(자료, 학습, 서빙), `pokechamp/.venv`(배틀), node(계산기). 실행기는 `scripts/laya-imitation v2|compare`다.
- 새 산출물과 검증 출력 위치:
  - `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/laya-compact-features/v2`
  - `.../datasets/generated/laya-compact-imitation/v2-all`
  - `.../runs/model-training/EX-121`, `.../runs/model-training/EX-122`
  - 뷰어 `/workspace/exports/battle_viewers/ex122/`
- 참조 원자료(읽기 전용):
  - EX-071 `prepared/`, `preparation/corpus.jsonl`
  - EX-118 `checkpoints/selected`, `evaluation/test-selected.jsonl`
  - EX-120 `collection/`
  - 계산기 `integration/pokechamp/improved_io/calculator/`

## 목표와 맥락

v1 대비 4종 정보를 더한 v2 렌더러의 효과를 렌더러 외 조건을 고정한 채 측정하고, 이후 조합 실험의 기반을 만든다. 조건과 판정은 EX-121과 EX-122가 소유한다.

## 범위와 불변 조건

- **포함**:
  - `compact_v2.py`, `features.py`, `calc.cjs`, `dex_gen9_v2.json`, `data_v2.py`, `comparison.py`
  - 학습, 평가, 서빙의 판본 일반화
  - 테스트, 문서
- **보존**: v1(`compact.py`, `dex.py`, `dex_gen9.json`), v1 자료, EX-118/119/120 산출물과 봉인, 기존 테스트 통과
- **자원**: GPU0과 포트 8107만 쓴다. 외부 프로세스 종료와 장치 reset은 금지한다.
- **외부 호출**: 없다.

## 완료 기준

- [x] v2 렌더러, 정보 계산, 계산기 워커와 단위 검사(`features=∅` v1 동일 포함)
- [x] CPU 사전측정(validation 512): 길이, 제외율, 계산기 실패율 → `head_max_len`을 EX-121에 동결
- [x] 정보 캐시와 `v2-all` 자료 생성, 감사, 봉인, parity
- [x] EX-121 학습, 선택, 잠긴 test, v1 쌍비교, 보고, 봉인
- [x] EX-122 mock 이후 256경기, 감사, 보고, 봉인, 자원 반환
- [x] [C-047](../../../CONTRACTS.md#c-047-viewer-export) 뷰어, 상위 목록, 오프라인 검사, [변경일지](../../../shared/viewers/CHANGELOG.md)
- [x] README, ENVIRONMENT, INDEX, STATUS, catalog build/check

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| v1 상위호환 | `features=∅` 출력 대 v1 출력(자료 표본) | v1 자료 / tests | 통과: validation 40행 동일 |
| 모듈 규칙 | 고정 예시 단위 검사 | - | 통과: 두 환경 각 29건(기존 포함) |
| 계산기 정확도 | 이름 해석 누락 집계, 의미 점검(무효 0%, snow Weather Ball 대 Gliscor ×4) | 정보 캐시 manifest | 부분: 전 행 계산 실패 0, 미해석 이름 0. `improved_io` 계산 결과와의 독립 대조는 하지 않았다 |
| 오프라인·실시간 동일성 | 저장 자료 대 실시간 렌더 해시 | v2 자료 / parity | 통과: 512/512 일치(두 인터프리터) |
| v1 경로 회귀 | 기존 테스트, EX-118/119/120 봉인 | 각 봉인 | 통과: 테스트 44건(다른 세션 추가분 포함), EX-122 v1 경기가 EX-120과 128/128 동일 |

## 진행

- 2026-10-22 — 승인과 등록. 구현 전 상태다.
- 2026-10-22 — 구현과 자료.
  - v2 렌더러, 정보 계산, 계산기 워커, 자료, 비교 배틀 코드를 추가했다. 학습, 평가, 서빙, 뷰어에는 판본 인자를 더했고 v1 기본 동작은 유지했다.
  - 사전측정 1차는 선택지 초과 153/512였다. 축약 규칙을 바꾼 2차는 0/512였고 `head_max_len=512`로 동결했다(EX-121 기록).
  - 정보 캐시: 131,947행, 33초, 계산기 실패 0, 미해석 이름 0
  - `v2-all` 자료: 제외 0, 전체 최대 954, 질문·선택지 최대 473, 선택지 최대 48. parity 512/512 일치.
  - 운영 지연: 자료 생성 완료(13:50 UTC)를 기다리던 감시 명령이 자기 명령줄을 같은 프로세스로 오인해 끝나지 않았다. 학습 시작이 약 10시간 늦어졌다. 결과에는 영향이 없다. 이후 감시는 상태 파일 기준으로 바꿨다.
- 2026-10-22 — EX-121 사전검사 통과(loss 2.160 → 1.989, 재로딩 차이 0.0). 23:5x UTC에 본학습을 시작했다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 결함 복구와 중단은 EX-121과 EX-122를 참조한다. 자동 재실행은 없다.

## 결과 및 증거

- [EX-121](../experiments/EX-121-laya-v2-all-training.md): test NLL 1.4435(v1 1.4716), 차이 95% [-0.059, +0.003]으로 "구별되지 않음". ECE는 0.053에서 0.027로 줄었다.
- [EX-122](../experiments/EX-122-laya-v1-v2-battle256.md): v2 102-0-26, v1 89-0-39. 같은 슬롯 차이 +0.102 [0.023, 0.180]으로 "v2가 배틀 성적을 개선".
- 증거: [뷰어 검사](../../../exec-plans/evidence/ep210/viewer-check.json), [리플레이 검사](../../../exec-plans/evidence/ep210/viewer-replay-check.json)
- 진행: 2026-10-23 EX-121 평가, EX-122 실행, 보고, 뷰어를 완료하고 GPU0과 포트 8107을 반환했다.
