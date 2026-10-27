# EX-073 Abyssal 우선 학습

## 분리된 연구선에서 읽는 방법

현재 checkout의 작업·환경 선택은 [연구 매뉴얼](../../../project_context/RESEARCH_MANUAL.md), 실행 여부는
[STATUS](../../../project_context/STATUS.md#active-work)를 먼저 확인한다. 아래 실행 명령은 `/workspace`의 기존 환경을
기준으로 한 기술 참조다. L1–L5 worktree는 보존·설계용이며 실행용 환경이 구성되어 있지 않다.
D/EX가 지정된 조건·경로·재개 명령은 해당 실험의 범위로 읽고, 공통 규칙은 기존 적용 범위를
유지한다. 새 실험의 입력·출력·실행 범위는 등록된 작업에서 정한다.


승인 조건은 [EX-073](../../../project_context/research/policy-learning/experiments/EX-073-abyssal-rl.md),
실행 진행은 [EP-119](../../../project_context/research/policy-learning/plans/EP-119-abyssal-rl.md),
runtime은 [C-057](../../../project_context/research/policy-learning/CONTRACTS.md#c-057-abyssal-rl)이 소유한다.
EX-072 구현·동결 자료를 수정하지 않고 입력·모델·배틀 감사 기능을 재사용한다.

```bash
scripts/pokechamp-abyssal-rl prepare
scripts/pokechamp-abyssal-rl verify
scripts/pokechamp-abyssal-rl run
scripts/pokechamp-abyssal-rl status
scripts/pokechamp-abyssal-rl run --resume
```

`prepare`는 GPU 없이 새 합법 팀416개·전체 가능 슬롯·기존 동결 BC를 보존한다.
예약 dev129후보는 마지막 완료 라운드가 가변이기 때문이며 실제 평가는 최대34회다.
`verify`는 준비 무결성·분산 CPU·상태 전환·배틀·뷰어 검사를 수행하고 source에 묶인 receipt를
저장한다. source가 바뀌면 기존 receipt를 보존한 새 검증이 필요하다.
`run`은 GPU0–3와 포트를 모두 확보한 뒤 source/config/data를 동결하고 최초 시계를 시작한다.
실제 4GPU 수치 gate 전에 학습이나 배틀에 진입하지 않는다. 기존 점유 작업을 종료하지 않는다.

수집은 rank당 동결 복제본1·배틀2를 사용하며 단일 입력 추론은 직렬이다. 요청이 모두 종료한
동기 경계에서 학습한다. RL16/BC4 전체 손실을 실제 전역 표본 수로 나눈 뒤 FP32 gradient를
NCCL SUM한다. 구현 API 기준은 [PyTorch2.8 공식 분산 문서](https://docs.pytorch.org/docs/2.8/distributed.html)다.
단일 rank 오류/공유 배틀 결함은 모든 worker를 멈춘다. 완료 update1 뒤 실제 SIGTERM을 보내
전체 rank의 수신·새 PID·원 checkpoint/시계 복원을 검사한다.

`run --resume`은 원 source·자료·시계·GPU UUID와 마지막 원자 checkpoint만 허용한다.
원자 예약된 경기는 재실행하지 않는다. 공유 기술 결함은 C-018 증거 기반 복구를 먼저 해야 하며,
명령 자체가 source·조건 변경이나 시간 연장의 허가는 아니다. 숫자 gate 실패 후 허용오차를
확대하지 않는다. 실패 기록과 미완료는 최종 목표 미달과 구분한다.

산출물은 `.pokechamp-data/experiments/ex073-abyssal-rl/`의 prepared, snapshots,
checkpoints, games, verification, final과 `exports/battle_viewers/ex073/`다.
최종 모델은 evaluation-lock.json의 final snapshot, 재개 파일은 latest.json이 가리킨다.
