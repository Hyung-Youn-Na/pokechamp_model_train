# EP-217 — laya 직접 대결 평가 하네스와 벤치마크(GPU2)

- 상태: Active
- 생성일: 2026-10-26
- 책임자: Claude Code
- 승인 근거·범위: 현재 사용자 지시와 승인된 계획(GPU0·GPU2 활용 개선 방향) / [D-194](../decisions/D-194-laya-head-to-head-evaluation.md).
  - 계획 승인으로 GPU2 배틀을 별도 승인 없이 이어서 진행한다.
  - 오프라인 결과로 배틀을 거르지 않는다([D-191](../decisions/D-191-no-offline-battle-gate.md)).
- 관련 contract / decision / experiment: [EX-134](../experiments/EX-134-laya-head-to-head512.md), [EX-135](../experiments/EX-135-laya-head-to-head-v2tw-v4t.md), [EX-120](../experiments/EX-120-laya-team-generalization128.md), [D-193](../decisions/D-193-laya-outcome-weighted-imitation.md), [EP-213](EP-213-laya-effect-knowledge.md)(EX-127 export 마무리)
- 기준 연구선: `research/model-training`
- 실제 작업 branch, 시작 commit, 미커밋 변경: `research/model-training` `feda62f733c1b470364868262c789ec857ef67f5`. 기존 미커밋 변경은 보존한다.
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv(서빙), `pokechamp/.venv`(배틀), node.
  - 실행기는 `scripts/laya-imitation h2h {mock,prepare,execute,export} [--study EX-134|EX-135]`이다.
  - 연결 실행은 `scripts/laya-imitation-ep217`이다.
- 새 산출물과 검증 출력 위치:
  - `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-134`, `.../EX-135`
  - 연결 실행 로그 `.../runs/model-training/EP-217-chain.log`
  - 뷰어 `/workspace/exports/battle_viewers/ex134/`, `ex135/`
- 참조 원자료(읽기 전용):
  - EX-120 `collection/`
  - EX-118·121·124·126·128·130·132 selected 체크포인트
  - EX-120·125·127·129·131·133 결과(Abyssal 비교)

## 목표와 맥락

Abyssal 천장 때문에 구별되지 않는 laya 모델 차이를 laya 직접 대결로 구별할 수 있는지 측정한다. 이어서 새 후보(EX-132, EX-130)를 같은 기준으로 비교한다. 조건과 판정은 EX-134와 EX-135가 소유한다.

## 범위와 불변 조건

- **포함**:
  - `headtohead.py`, `tests/test_headtohead.py`
  - `battle.play_slot` 선택 인자, `browser_check.py` `h2h` 모드
  - 설정, CLI `h2h`, 실행기, 연결 실행 스크립트, 뷰어 확장(비교 진영 페이지)
  - 선행 정리: EX-127 export·문서화(EP-213 완료 처리)
- **보존**:
  - 기존 Abyssal 경로(`play_slot` 기본값)와 EX-118~133 Spec·Study·산출물·봉인
  - EX-071 공용 player·audit(`integration/pokechamp/imitation/`)는 수정하지 않는다.
- **자원**: GPU2와 포트 8108만 쓴다. GPU0·8107(EP-216)과 GPU1·8109(EP-215)는 쓰지 않는다. 외부 프로세스 종료와 장치 reset은 금지한다.
- **외부 호출**: 없다.

## 완료 기준

- [x] EX-127 export·뷰어·오프라인 검사, EP-213 완료 처리
- [x] 하네스, 단위 검사, mock(4경기, 두 진영 감사), 뷰어 사전 확인
- [ ] EX-134 prepare → 512경기 → 보고, 뷰어, 오프라인 검사, 봉인
- [ ] EX-135(EX-132·EX-130 봉인 뒤) 256경기 → 보고, 뷰어, 봉인, 자원 반환
- [ ] STATUS, catalog build/check, 뷰어 변경일지, 상위 목록

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| Abyssal 경로 보존 | `play_slot` 기본 인자 그대로, 기존 테스트 | `pytest integration/laya_imitation/tests` | 72 통과 |
| 일정 | 쌍마다 128슬롯 1회씩, 교환쌍 팀 교대, 거울 진영의 시드·팀 | `test_headtohead` | 통과 |
| 두 진영 기록·감사 | mock 4경기(v2+테라 대 v2+테라) | `EX-134/mock/` | 4/4 정상, 두 진영 감사 통과 |
| 뷰어 | mock 결과로 만든 임시 뷰어, 오프라인 1440·390 | [검사](../../../exec-plans/evidence/ep217/mock-viewer-check.json) | 두 진영 8탭, 오류 0 |
| 정적 검사 | ruff(E9,F63,F7,F82,F401,F811), compileall | — | 통과 |

## 진행

- 2026-10-26
  - 승인과 등록
  - EX-127 export(256/256 감사 통과, 뷰어 오프라인 검사 통과), EP-213 완료 처리
  - 하네스 구현과 단위 검사, mock 4경기(기준 34결정·비교 35결정, 교환쌍 각 1승 1패)

## 차단·중단

- [INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 결함 복구와 중단은 EX-134와 EX-135를 참조한다.
- 자동 재실행은 없다. 연결 실행 스크립트는 단계가 실패하면 그 자리에서 멈춘다.
- 경기마다 worker 프로세스가 `headtohead.py`를 새로 읽는다. 그래서 EX-134·EX-135 실행 중에는 이 파일과 `battle.py`를 바꾸지 않는다.

## 결과 및 증거

- 진행 중
