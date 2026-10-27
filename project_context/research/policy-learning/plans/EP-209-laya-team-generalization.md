# EP-209 — laya 모방 모델 새 팀 128경기 일반화 평가

- 상태: Completed
- 생성일: 2026-10-22
- 책임자: Claude Code
- 승인 근거·범위: 현재 사용자 지시와 승인된 계획 / [D-184](../decisions/D-184-laya-team-generalization.md)
- 관련 contract / decision / experiment: [C-055](../CONTRACTS.md#c-055-imitation), [EX-120](../experiments/EX-120-laya-team-generalization128.md), [EX-119](../experiments/EX-119-laya-compact-imitation-battle32.md), [EP-208](EP-208-laya-compact-imitation.md)
- 기준 연구선: `research/model-training`
- 실제 작업 branch, 시작 commit, 미커밋 변경: `research/model-training` `feda62f733c1b470364868262c789ec857ef67f5`. 기존 미커밋 변경은 보존하고 새 파일만 추가한다.
- 작업 checkout과 interpreter/launcher: `/workspace`, `pokechamp/.venv`(팀 선정, 배틀), laya venv(서빙). 실행기는 `scripts/laya-imitation general`이다.
- 새 산출물과 검증 출력 위치:
  - `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-120`
  - 뷰어 `/workspace/exports/battle_viewers/ex120/`
- 참조 원자료(읽기 전용):
  - `export/teams/gen9ou_reviewed108_teams.json`과 그 팀 파일
  - EX-071 `preparation/`, `schedule.json`
  - EX-089 manifest
  - EX-118 `checkpoints/selected`

## 목표와 맥락

EX-119의 0.78 점수가 처음 보는 팀 조합에서도 유지되는지 확인한다. 조건과 판정은 EX-120이 소유한다.

## 범위와 불변 조건

- **포함**:
  - `integration/laya_imitation/{teams.py, generalization.py}`
  - `cli.py`의 `general` 명령
  - `reporting.py`의 새 함수
  - 테스트, README, 문서 등록
- **보존**: EX-118/EX-119 산출물·봉인·코드 동작, 렌더러 v1, 기존 결과와 환경
- **GPU**: GPU0만 쓴다. 잠금과 UUID 확인을 거친다. 외부 프로세스 종료와 장치 reset은 금지한다.
- **포트**: 8107만 쓴다.
- **외부 호출**: 없다.

## 완료 기준

- [x] 팀 선정과 일정 생성 코드, 단위 검사
- [x] collection 생성과 감사: 32팀 합법, 서로 다른 조합, 제외 집합 교집합 0, 봉인. 결과를 보기 전에 완료한다.
- [x] mock 2경기(분모 밖)로 새 팀 경로 확인
- [x] 본 128경기, 경기별 감사, 보고, 봉인, 포트와 GPU 반환
- [x] [C-047](../../../CONTRACTS.md#c-047-viewer-export) 뷰어(`exports/battle_viewers/ex120`), 상위 목록, 오프라인 검사, [변경일지](../../../shared/viewers/CHANGELOG.md)
- [x] README, INDEX 흐름, STATUS, catalog build/check

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| 팀 선정 규칙과 결정성 | `tests/test_teams.py`, `test_generalization_summary.py` | - | 통과: 두 환경 각 20건(기존 11건 포함) |
| 오염 통제 | 제외 서명 교집합 감사 | EX-071 replays, historical-teams / collection `selection.json` | 통과: 4개 집합 교집합 0 |
| 배틀 경로 | mock 2경기, 감사 | EX-119 경로 / `EX-120/mock` | 통과: 2경기 정상, 감사 통과 |
| EX-119 불변 | EX-119와 EX-118 봉인 재검증, 수정한 뷰어 생성기로 EX-119 재내보내기 대조 | 각 `checksums.sha256` | 통과: 봉인 이상 없음. 재내보내기는 renderer-source 해시 외 동일 |

## 진행

- 2026-10-22 — 승인과 등록. 구현 전 상태다.
- 2026-10-22 — 구현과 실행.
  - `teams.py`, `generalization.py`를 추가하고 `viewer.export`에 선택 인자(실험 메타, 목록 열)를 더했다. 기본값은 EX-119 출력과 같다.
  - collection(32팀, 유형별 8, 교집합 0)을 결과 전에 봉인했다.
  - mock 2경기를 마쳤다.
  - 본 128경기는 모두 정상 종료했고 89승 0무 39패다.
  - 보고, 뷰어, 봉인을 마치고 GPU0과 포트 8107을 반환했다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 실험 결함 복구와 중단은 EX-120을 참조한다. 자동 재실행은 없다.

## 결과 및 증거

- [EX-120](../experiments/EX-120-laya-team-generalization128.md): 89승 0무 39패(0.695), 조합 클러스터 95% [0.617, 0.773]. 1차 판정은 "새 팀에서도 Abyssal보다 우세"다.
- 증거: [ep209 보고](../../../exec-plans/evidence/ep209/report.md), [뷰어 검사](../../../exec-plans/evidence/ep209/viewer-check.json), [리플레이 검사](../../../exec-plans/evidence/ep209/viewer-replay-check.json)
- 뷰어: `exports/battle_viewers/ex120/index.html`
