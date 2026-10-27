# EP-208 — laya 압축 입력 모방 학습·배틀 에이전트

- 상태: Completed
- 생성일: 2026-10-22
- 책임자: Claude Code
- 승인 근거·범위: 현재 사용자 지시와 승인된 계획 / [D-183](../decisions/D-183-laya-compact-imitation.md)
- 관련 contract / decision / experiment: [C-055](../CONTRACTS.md#c-055-imitation), [EX-118](../experiments/EX-118-laya-compact-imitation-training.md), [EX-119](../experiments/EX-119-laya-compact-imitation-battle32.md), [EP-207](../../../shared/execution/plans/EP-207-laya-0413-environment.md)
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit·미커밋 변경: `research/model-training`, `feda62f733c1b470364868262c789ec857ef67f5`. 기존 미커밋 변경은 보존하며 새 파일만 추가한다.
- 작업 checkout·interpreter/launcher: `/workspace`
  - 학습과 서빙: `.tools/laya-0.4.13/worktrees/pokemon-training/.venv`
  - 자료 변환과 배틀: `pokechamp/.venv`
  - 실행기: `scripts/laya-imitation`
- 새 산출물·검증 출력 위치: `/mnt/digicap/combined/hyna/backup/pokechamp-research/`
  - `datasets/generated/laya-compact-imitation/v1`
  - `runs/model-training/EX-118`
  - `runs/model-training/EX-119`
  - 뷰어는 `/workspace/exports/battle_viewers/ex119/`
- 참조 원자료(읽기 전용):
  - `.pokechamp-data/experiments/ex071-qwen-replay-imitation/prepared/`
  - EX-089 `collection/manifest.json`

## 목표와 맥락

EX-071 스냅샷을 laya용 1,024토큰 이하 텍스트로 압축한다. laya 0.4.13으로 사람 선택을 학습하고, 선택 모델을 EX-089 표준 32경기에서 평가한다. 조건과 판정은 EX-118과 EX-119가 소유한다.

## 범위와 불변 조건

- **포함**: `integration/laya_imitation/`(렌더러, 자료, 학습, 서빙, 배틀, 뷰어, 보고, 테스트), `scripts/laya-imitation`, 설명자료, 문서 등록
- **보존**:
  - C-055 입력 경계(금지 필드와 미래 정보 차단)
  - EX-071의 분할과 고정 표본
  - EX-089 일정과 봉인
  - 기존 결과와 환경
- **GPU**: GPU0만 쓴다. 잠금과 UUID 확인을 거치며, 외부 프로세스 종료와 장치 reset은 금지한다.
- **포트**: 8107만 쓴다. `port8107.lock`을 잡는다.
- **외부 호출**: 공개 모델 다운로드 외에 유료 API 호출은 없다.

## 완료 기준

- [x] EP-207 환경 완료
- [x] 압축 렌더러와 단위 검사. 오프라인과 실배틀 입력이 같은지 확인한다.
- [x] 자료 v1 생성과 감사: 길이 ≤1,024, EX-089 팀 겹침 0, 봉인
- [x] EX-118 학습, validation 선택, 잠긴 test 평가, 보고, 봉인, GPU0 반환
- [x] EX-119 mock 배틀 2경기 이후 본 32경기, 경기 감사, 보고, 봉인, 포트와 GPU 반환
- [x] 정상 종료한 배틀은 [C-047](../../../CONTRACTS.md#c-047-viewer-export)에 따라 `exports/battle_viewers/ex119`에 뷰어, 목록, 출처를 제공하고 오프라인 열람을 검증한다.
- [x] EX-119의 UI 규격, 생성기 판본, 소스, 확장 선언을 연결한다. [매뉴얼](../../../RESEARCH_MANUAL.md#battle-viewer-workflow)에 따라 실행 전 지원을 확인한다.
- [x] 실제 내보내기의 UI 확인표와 [변경일지](../../../shared/viewers/CHANGELOG.md) 항목
- [x] Codex용 README, ENVIRONMENT 실행기 표, 연구 INDEX 흐름, catalog build/check

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| 입력 경계와 결정성 | `integration/laya_imitation/tests`, 두 인터프리터 렌더 해시 대조 | EX-071 schema / [사전 검사](../../../exec-plans/evidence/ep208/pre-run-checks.json) | 통과: laya 환경 9건, pokechamp 환경 8건, 1,536행 해시 일치 |
| 자료 무결성과 오염 | 전수 감사, EX-089 팀 서명 대조 | EX-071 replay-exclusions / 자료 `validation.json`·`contamination.json` | 통과: 130,411/512/1,024행, 제외 0, 겹침 경기 22건 모두 EX-071 제외분 |
| 학습 재현성 | 저장 후 재로딩한 예측 일치 | EX-118 `preflight/`, `evaluation/` | 통과: 저장 후 재로딩 logit 차이 0.0, 잠긴 test 모델별 1회 |
| 배틀 경로 | mock 2경기, 경기별 audit, 뷰어 이동·오프라인 | EX-119 `mock/` / [사전 검사](../../../exec-plans/evidence/ep208/pre-run-checks.json) | 통과: 2경기 정상 종료, 감사 통과, 89결정 뷰어 |

## 진행

- 2026-10-22 — 승인과 등록.
  - EX-089의 네 팀 서명이 EX-071 train(1,938경기), validation(187), test(219) 어디에도 없음을 확인했다. 해당 22경기는 EX-071 replay-exclusions에 포함되어 있다.
  - 구현 전 상태다.
- 2026-10-22 — 구현과 사전 검증.
  - 자료 v1(`/mnt/.../datasets/generated/laya-compact-imitation/v1`)을 생성하고 봉인했다. 전체 최대 808토큰, 질문·선택지 최대 326토큰이다. 실측 결과에 따라 실행 전에 `head_max_len`을 256에서 384로 바꾸고 EX-118 원문에 반영했다.
  - EX-118 사전검사 v1은 비교 기준이 RoPE 버퍼까지 반올림한 검사 도구 결함으로 실패했다. 원본은 `EX-118/diagnostics/preflight-v1`에 보존했다. 수정 후 재검사에서 재로딩 차이 0.0으로 통과했다.
  - EX-119 mock v1은 예산 확인 조건이 공개 체크포인트를 EX-118 체크포인트로 오인해 서빙이 시작되지 않았다(경기 0). 원본은 `EX-119/diagnostics/mock-v1`에 보존했다. 수정 후 mock 2경기가 정상 종료하고 감사를 통과했다.
  - 뷰어 생성기 `laya-imitation-researcher-v1`의 실행 전 지원을 확인했다([변경일지](../../../shared/viewers/CHANGELOG.md#ex119-laya-v1)).
  - EX-118 본학습을 GPU0에서 시작했다.
- 2026-10-22 — 학습과 배틀 완료.
  - EX-118: 5.51시간, epoch 2 선택. 잠긴 test NLL 1.4716, 일치율 46.78%(초기 2.1311, 20.12%). 봉인했다.
  - EX-119: 32/32 정상, 25승 0무 7패, 전 경기 감사 통과. 보고, 뷰어, 봉인을 마쳤다.
  - 뷰어를 상위 목록에 연결하고 폴더 이동 오프라인 검사와 리플레이 이동 검사를 통과했다.
  - GPU0 잠금과 포트 8107을 반환했다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 실험 결함 복구와 중단은 EX-118과 EX-119의 해당 절을 참조한다. 자동 재실행은 없다.

## 결과 및 증거

- 학습: [EX-118](../experiments/EX-118-laya-compact-imitation-training.md). 잠긴 test에서 선택 모델 NLL 1.4716, 일치율 46.78%. 참고로 EX-071 Qwen 4B는 1.7168, 31.25%.
- 배틀: [EX-119](../experiments/EX-119-laya-compact-imitation-battle32.md). 25승 0무 7패, 쌍 bootstrap 95% [0.6562, 0.9062].
- 증거: [ep208 보고](../../../exec-plans/evidence/ep208/report.md), [뷰어 검사](../../../exec-plans/evidence/ep208/viewer-final-check.json), [리플레이 검사](../../../exec-plans/evidence/ep208/viewer-replay-check.json)
- 뷰어: `exports/battle_viewers/ex119/index.html`
