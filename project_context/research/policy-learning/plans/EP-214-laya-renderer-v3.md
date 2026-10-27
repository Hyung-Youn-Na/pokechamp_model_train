# EP-214 — laya 렌더러 v3(상대 세트 추론) 학습과 배틀 비교(GPU0)

- 상태: Completed
- 생성일: 2026-10-25
- 책임자: Claude Code
- 승인 근거·범위: 현재 사용자 지시와 승인된 계획 / [D-189](../decisions/D-189-laya-renderer-v3-opponent-sets.md). GPU 학습과 배틀은 별도 승인 없이 이어서 진행한다(사용자 지시). EX-129는 EX-128의 사전 등록 진행 조건을 충족할 때만 시작한다. EX-128이 미충족이었고, 사용자 결정으로 [D-190](../decisions/D-190-laya-ex129-gate-override.md)에 이탈을 기록한 뒤 실행한다.
- 관련 contract / decision / experiment: [C-055](../CONTRACTS.md#c-055-imitation), [EX-128](../experiments/EX-128-laya-v3-tera-training.md), [EX-129](../experiments/EX-129-laya-v2t-v3t-battle256.md), [EX-124](../experiments/EX-124-laya-v2-tera-knowledge-training.md), [EP-212](EP-212-laya-tera-knowledge.md)
- 기준 연구선: `research/model-training`
- 실제 작업 branch, 시작 commit, 미커밋 변경: `research/model-training` `feda62f733c1b470364868262c789ec857ef67f5`. 기존 미커밋 변경은 보존한다.
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv, `pokechamp/.venv`, node. 실행기는 `scripts/laya-imitation v3|compare4`다.
- 새 산출물과 검증 출력 위치:
  - `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/laya-compact-features/v3`
  - `.../laya-compact-imitation/v3-all`
  - `.../runs/model-training/EX-128`, `.../runs/model-training/EX-129`
  - 뷰어 `/workspace/exports/battle_viewers/ex129/`
- 참조 원자료(읽기 전용): EX-071 `prepared/`, 테라 지식 `v1`, EX-124 산출물, EX-120 `collection/`, usage stats 처리본(`exports/pokemon-role-data/…/gen9ou-1695.json`)

## 목표와 맥락

래더 대비로 상대 세트 추론 정보를 입력에 넣었을 때 사람 교체 판단 재현이 나아지는지, Abyssal 상대 성적이 퇴보하지 않는지 측정한다. 조건과 판정은 EX-128과 EX-129가 소유한다.

## 범위와 불변 조건

- **포함**:
  - `features_v3.py`, `compact_v3.py`, `usage_sets_v3.json`, `data_v3.py`, `evaluation_v3.py`, `tests/test_compact_v3.py`
  - 설정, 학습 Spec `EX128`, 서빙 `--render v3`, CLI `v3`·`compare4`, 비교 배틀 `EX129`(비열등 `margin`), 실행기 경로
- **보존**:
  - v1, v2 렌더러와 자료, 정보 캐시(v2 출력은 v3 모듈 없이 바이트 단위로 같다)
  - EX-118~127 산출물, 봉인, 동작
  - EX-127(GPU2·8108)의 자원
- **자원**: GPU0과 포트 8107만 쓴다. 외부 프로세스 종료와 장치 reset은 금지한다.
- **외부 호출**: 없다. usage stats는 이미 받아 둔 처리본을 고정해 쓴다.

## 완료 기준

- [x] v3 렌더러, 세트 추론, 단위 검사, 사전 측정(validation 512 초과 0)
- [x] v3 정보 캐시와 `v3-all` 자료 생성, 제외 비율 ≤ 0.005, parity, 봉인
- [x] EX-128 학습(GPU0), 선택, 테라 지식 held-out, 잠긴 test, EX-124 쌍비교, 보고, 봉인
- [x] EX-129 진행 조건 판정(미충족, D-190 이탈 실행). mock 후 256경기, 보고, 뷰어 생성, 봉인, 자원 반환. 뷰어 오프라인 브라우저 검사·상위 목록·변경일지는 미실행
- [ ] POKEMON_EXPERIMENTS, STATUS, catalog build/check

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| v2 출력 보존 | v3 모듈 없는 렌더가 v2와 같음(validation 40행) | `test_compact_v3` | 통과 |
| 세트 추론 규칙 | 공개 정보 확정, 남은 칸, 종족 없음·별칭, 먼저 행동 확률, 교체 `hit` | `test_compact_v3` 9건 | 통과(전체 53건) |
| 길이 | validation 512 실측 | 사전 측정 | 초과 0, 전체 최대 984, head 453, 선택지 46 |
| 오프라인·서빙 일치 | `v3 parity` 512행 | `EX-128/diagnostics/parity.json` | 512/512 일치 |

## 진행

- 2026-10-25 — 승인과 등록. 구현과 단위 검사를 마쳤다. 사전 측정에서 교체 선택지 위협 문구가 48토큰을 넘어(109/512) `hit` 대체 방식으로 줄였다(D-189).

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 결함 복구와 중단은 EX-128과 EX-129를 참조한다. 자동 재실행은 없다. 연결 실행 스크립트는 단계가 실패하면 그 자리에서 멈춘다.

## 결과 및 증거

- EX-128: test NLL 1.4391(EX-124 1.4506), 교체 행 −0.034 [−0.085, +0.016], 전체 −0.012 [−0.043, +0.0200]. 진행 조건 미충족.
- EX-129: v3t 104-24 대 v2t 111-17, 차이 −0.055 [−0.125, +0.008] → 퇴보를 배제하지 못함. v3t Spikes 실패 53/95.
- 후속: [EP-215](EP-215-laya-renderer-v4.md)
