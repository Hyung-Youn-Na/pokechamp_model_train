# 자기대국·선택 행동 승무패 확률 보정

## 분리된 연구선에서 읽는 방법

현재 checkout의 작업·환경 선택은 [연구 매뉴얼](../../../project_context/RESEARCH_MANUAL.md), 실행 여부는
[STATUS](../../../project_context/STATUS.md#active-work)를 먼저 확인한다. 아래 실행 명령은 `/workspace`의 기존 환경을
기준으로 한 기술 참조다. L1–L5 worktree는 보존·설계용이며 실행용 환경이 구성되어 있지 않다.
D/EX가 지정된 조건·경로·재개 명령은 해당 실험의 범위로 읽고, 공통 규칙은 기존 적용 범위를
유지한다. 새 실험의 입력·출력·실행 범위는 등록된 작업에서 정한다.


[EX-072](../../../project_context/experiments/EX-072-selfplay-rlcd.md)의 별도 실행 경로다.
승인·연구 조건은 D-114/EX-072, 입력/실행 경계는 C-056, 현재 진행은 EP-116이 소유한다.
기존 EX-071 imitation 및 EX-066/GPU1 실행은 변경하지 않는다.

`prepare`는 전 원 replay 구성·역사 평가팀을 제외하고 신규 합법92팀, 최대584경기와
EX-071 train 전용 BC 자료를 동결한다. `model`은 같은 backbone forward에서 정책/WDL을
구분하며, `trainer`는 PPO·선택 WDL half-Brier·BC와 head 전용 보정을 담당한다.
`player`는 기존 공식 입력·전송 경계를 재사용하고, `serving`은 한 GPU에서 동결 snapshot을
직렬로 교체한다. `battle`은 실제 전송·RNG·후보·terminal을 대조하며 실패를 학습에서 제외한다.
`runner`는 고정 단계/기한을 실행하고 `execution`은 완료 step checkpoint·SIGTERM 재개·
GPU UUID·5분 상태 기록을 관리한다. `reporting`/`viewer`는 고정 가중 평가와 이동 가능한
오프라인 입력·선택·턴별 공개 로그 재생을 제공한다.

```bash
scripts/pokechamp-selfplay prepare
scripts/pokechamp-selfplay verify
scripts/pokechamp-selfplay run
scripts/pokechamp-selfplay status
# 이미 등록된 동일 실행의 원 시계·checkpoint에서만 재개:
scripts/pokechamp-selfplay run --resume
```

위 명령은 완료 실험의 재실행 승인이나 상한 연장이 아니다. `run`은 기록된 CPU 검사 통과,
자료/소스 동결과 유휴 GPU3→2→0 lock을 요구하며 첫 GPU preflight부터24시간이다.
훈련 중 계획된1회 SIGTERM은 완료 step 저장 후 실제 worker 프로세스를 종료/재시작한다.
그 밖의 중단은 자동 재시도하지 않는다. 각 대국 폴더는 사용된 슬롯이며 미완료도 재경기하지 않는다.
단계별 경기를 직접 재수집하거나 수동으로 gate/clock/latest를 바꿔 재개하면 안 된다.

기본 산출물은 `.pokechamp-data/experiments/ex072-selfplay-rlcd/`다.
`prepared/`는 팀·일정·BC 출처, `games/`는 모든 시도와 learner 결정,
`snapshots/`는 초기/각 라운드/보정 전후/최종 가중치, `checkpoints/`는 optimizer·RNG·cursor·
원 시계 및 동결 snapshot 참조, `verification/`은 CPU/GPU·재개·불변 검사다.
최종 결과는 `final/report.md`, 뷰어는 `exports/battle_viewers/ex072/index.html`이다.
수집 buffer는 immutable 경기별 JSONL로 남고 checkpoint의 cursor·snapshot·단계와 함께 복원한다.

행동 선택 확률은 승리 확률이 아니다. 승무패 오차는 실제 선택한 행동에만 평가하며,
결합 방식의 개선을 WDL 보조 손실만의 인과 효과로 해석하지 않는다.
