# EP-215 — laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) 학습과 배틀 비교(GPU1)

- 상태: Active
- 생성일: 2026-10-26
- 책임자: Claude Code
- 승인 근거·범위: 현재 사용자 지시와 승인된 계획 / [D-192](../decisions/D-192-laya-renderer-v4-fail-out.md). 계획 승인으로 GPU 학습과 배틀을 별도 승인 없이 이어서 진행한다. 오프라인 결과로 배틀을 거르지 않는다([D-191](../decisions/D-191-no-offline-battle-gate.md)).
- 관련 contract / decision / experiment: [C-055](../CONTRACTS.md#c-055-imitation), [EX-130](../experiments/EX-130-laya-v4-tera-training.md), [EX-131](../experiments/EX-131-laya-v2t-v4t-battle256.md), [EX-124](../experiments/EX-124-laya-v2-tera-knowledge-training.md), [EX-122](../experiments/EX-122-laya-v1-v2-battle256.md)
- 기준 연구선: `research/model-training`
- 실제 작업 branch, 시작 commit, 미커밋 변경: `research/model-training` `feda62f733c1b470364868262c789ec857ef67f5`. 기존 미커밋 변경은 보존한다.
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv, `pokechamp/.venv`, node. 실행기는 `scripts/laya-imitation v4|compare5`, 연결 실행은 `scripts/laya-imitation-ep215`다.
- 새 산출물과 검증 출력 위치:
  - `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/laya-compact-features/v4`
  - `.../laya-compact-imitation/v4-all`
  - `.../runs/model-training/EX-130`, `.../runs/model-training/EX-131`, 연결 실행 로그 `.../runs/model-training/EP-215-chain.log`
  - 뷰어 `/workspace/exports/battle_viewers/ex131/`
- 참조 원자료(읽기 전용): EX-071 `prepared/`, 테라 지식 `v1`, EX-124 산출물, EX-120 `collection/`, EX-122 경기(검사 고정 사례)

## 목표와 맥락

확정 실패 표시와 교체 후보의 공격 피해를 입력에 넣었을 때 실패 반복이 줄고 배틀 성적이 나아지는지 측정한다. 조건과 판정은 EX-130과 EX-131이 소유한다.

## 범위와 불변 조건

- **포함**:
  - `features_v4.py`, `compact_v4.py`, `data_v4.py`, `evaluation_v4.py`, `tests/test_compact_v4.py`
  - 설정, 학습 Spec `EX130`, 서빙 `--render v4`, CLI `v4`·`compare5`, 비교 배틀 `EX131`, `failed_moves` 반복 지표, 실행기 경로
- **보존**:
  - v1~v3 렌더러와 자료(v4 모듈 없는 출력은 v2와 바이트 단위로 같다)
  - EX-118~129 산출물, 봉인, 동작. `effect_knowledge.py`와 규칙 파일은 수정하지 않는다.
- **자원**: GPU1과 포트 8109만 쓴다. 외부 프로세스 종료와 장치 reset은 금지한다.
- **외부 호출**: 없다.

## 완료 기준

- [x] v4 렌더러, 단위 검사(EX-122 실제 사례 포함), 사전 측정과 `out` 형식 동결
- [ ] v4 정보 캐시와 `v4-all` 자료 생성, 제외 비율 ≤ 0.005, parity, 봉인
- [ ] EX-130 학습(GPU1), 선택, 테라 지식 held-out, 잠긴 test, EX-124 쌍비교, 보고, 봉인
- [ ] EX-131 mock 후 256경기, 보고(반복 지표 포함), 뷰어, 봉인, 자원 반환
- [ ] POKEMON_EXPERIMENTS, STATUS, catalog build/check, 뷰어 변경일지

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| v2 출력 보존 | v4 모듈 없는 렌더가 v2와 같음(validation 40행) | `test_compact_v4` | 통과 |
| 실패 표시 규칙 | Spikes 3층만 표시, Tera Blast 테라 선택지 제외, `bounced` | `test_compact_v4` | 통과 |
| 실제 사례 | EX-122 m23·m27·m29 입력 | `test_compact_v4` | Spikes `fails`, Latios 103%, Kyurem 158%, Iron Treads 85% |
| 길이 | validation 512 실측 | 사전 측정 | 범위 형식 507/512 → 최댓값 형식 512/512 동결 |
| 전체 검사 | `pytest integration/laya_imitation/tests`, ruff, compileall | — | 60 통과, ruff·compileall 통과 |
| 오프라인·서빙 일치 | `v4 parity` 512행 | `EX-130/diagnostics/parity.json` | 예정 |

## 진행

- 2026-10-26 — 승인과 등록. 구현, 단위 검사, 사전 측정을 마쳤다. `out a-b%`가 5/512행에서 선택지 한도를 넘어 `out b%`로 동결했다(D-192).

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 결함 복구와 중단은 EX-130과 EX-131을 참조한다. 자동 재실행은 없다. 연결 실행 스크립트는 단계가 실패하면 그 자리에서 멈춘다.

## 결과 및 증거

- 진행 중
