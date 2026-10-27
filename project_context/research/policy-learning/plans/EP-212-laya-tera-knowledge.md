# EP-212 — laya v2 테라 지식 데이터 학습과 배틀 비교(GPU1)

- 상태: Completed
- 생성일: 2026-10-23
- 책임자: Claude Code
- 승인 근거·범위: 현재 사용자 지시와 승인된 계획 / [D-187](../decisions/D-187-laya-tera-knowledge.md)
- 관련 contract / decision / experiment: [C-055](../CONTRACTS.md#c-055-imitation), [EX-124](../experiments/EX-124-laya-v2-tera-knowledge-training.md), [EX-125](../experiments/EX-125-laya-v2-tera-battle256.md), [EX-121](../experiments/EX-121-laya-v2-all-training.md), [EP-210](EP-210-laya-renderer-v2.md)
- 기준 연구선: `research/model-training`
- 실제 작업 branch, 시작 commit, 미커밋 변경: `research/model-training` `feda62f733c1b470364868262c789ec857ef67f5`. 기존 미커밋 변경은 보존한다.
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv, `pokechamp/.venv`, node. 실행기는 `scripts/laya-imitation tera|compare2`다.
- 새 산출물과 검증 출력 위치:
  - `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/laya-tera-knowledge/v1`
  - `.../laya-compact-imitation/v2-all+tera`
  - `.../runs/model-training/EX-124`, `.../runs/model-training/EX-125`
  - 뷰어 `/workspace/exports/battle_viewers/ex125/`
- 참조 원자료(읽기 전용): v2 정보 캐시, `v2-all` 자료, EX-071 `prepared/`, EX-120 `collection/`, EX-121 산출물

## 목표와 맥락

테라 기본 지식 행을 더했을 때 테라 재현과 배틀 사용이 바뀌는지 측정한다. 조건과 판정은 EX-124와 EX-125가 소유한다.

## 범위와 불변 조건

- **포함**:
  - `tera_rules.md`, `tera_rules.json`, `tera_knowledge.py`, `evaluation_tera.py`
  - 자원(GPU, 포트) 인자화, 학습 Spec, 비교 배틀 인자화, 테스트, 문서
- **보존**:
  - v1, v2 렌더러와 자료, 정보 캐시
  - EX-118~122 산출물, 봉인, 동작
  - 다른 작업(EP-211, EX-123)의 자원
- **자원**: GPU1과 포트 8109만 쓴다. 외부 프로세스 종료와 장치 reset은 금지한다.
- **외부 호출**: 규칙 근거 웹 열람만 한다. 유료 API는 쓰지 않는다.

## 완료 기준

- [x] 규칙표(엔진 근거와 웹 교차 확인)
- [x] 지식 생성기와 단위 검사, 자료 생성, 감사, 봉인, `v2-all+tera` 결합(학습 시 결합)
- [x] EX-124 학습(GPU1), 선택, 지식 held-out, 잠긴 test, EX-121 쌍비교, 보고, 봉인
- [x] EX-125 mock 후 256경기, 테라 지표, 보고, 봉인, 자원 반환
- [x] 뷰어(C-047), 상위 목록, 오프라인 검사, 변경일지
- [x] README, ENVIRONMENT, INDEX, STATUS, catalog build/check

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| 규칙 정확성 | 규칙별 엔진 소스 위치와 단위 예시 | `tera_rules.md` / tests | 통과: 엔진 근거 9개 규칙, `test_tera_knowledge` 4건 |
| 지식 정답 검증 | 생성기 내부 재계산, 정답이 선택지 안에 있는지 | 자료 감사 | 통과: 모든 행의 정답이 선택지 안에 있음(생성 시 검사). 정답 분포 특성은 EX-124에 기록 |
| 기존 경로 회귀 | 기존 테스트, EX-118~122 봉인 | 각 봉인 | 테스트 34건 통과(두 환경). EX-122와 EX-125 mock 각 2경기 정상 |

## 진행

- 2026-10-23 — 승인과 등록. 규칙을 엔진 소스로 확인했다(구현 전).
- 2026-10-23 — 구현과 자료.
  - 규칙표, 지식 생성기, 테라 평가, GPU·포트 인자화, 비교 배틀 일반화(`comparison.Study`: EX-122 동작 유지)를 추가했다.
  - 테스트 34건이 통과했다.
  - 지식 자료: train 57,143, held-out 4,242, 초과 0. 봉인했다.
  - EX-124 사전검사 통과(loss 2.164 → 2.006, 재로딩 차이 0.0). GPU1 본학습을 시작했다(학습 행 187,154 = 모방 130,011 + 지식 57,143).
  - EX-122와 EX-125 mock(CPU, 8107과 8109)이 각 2경기 정상 종료하고 감사를 통과했다. v2 서빙의 실시간 피해 계산과 v2 뷰어 내보내기도 확인했다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 결함 복구와 중단은 EX-124와 EX-125를 참조한다. 자동 재실행은 없다.

## 결과 및 증거

- [EX-124](../experiments/EX-124-laya-v2-tera-knowledge-training.md): 지식 held-out 96.9%와 95.8%로 지식은 습득했다. 사람 테라 재현 차이는 +0.002 [-0.031, +0.033]이고, 전체 NLL 비열등 상한 +0.035 > +0.02 → "개선 없음".
- [EX-125](../experiments/EX-125-laya-v2-tera-battle256.md): v2+테라 111-0-17, v2 102-0-26. 차이 +0.070 [0.000, 0.141] → "구별되지 않음". 테라 사용은 16에서 22경기다.
- 증거: [뷰어 검사](../../../exec-plans/evidence/ep212/viewer-check.json), [리플레이 검사](../../../exec-plans/evidence/ep212/viewer-replay-check.json)
- 2026-10-23: 보고, 봉인, 뷰어(256경기, 11,380결정, 상위 목록)를 마치고 GPU1과 포트 8109를 반환했다.
