# EX-116 전체 System One 학습

원본 JevK5-9B의 새 LoRA, 130149문항 전체 3epoch. 규범은 등록 EX-116이다.
기존 EX-113/자료/서빙은 보존한다. 환경은 `/ref/kev/.venv`, 출력은
`<BACKUP_ROOT>/pokechamp-research/runs/model-training/EX-116`이다.

- `scripts/jevk5-system1-train prepare-training`: 원자료 봉인·native token 전수검사와 메모리맵.
- `prepare-evaluation --rules <검증된 새규칙 JSONL>`: 별도 리플레이/규칙 평가와 진단자료 준비.
- `freeze`: CPU/의미 검토 후 데이터·소스·설정·protocol 동결. 기존 동결 덮어쓰기 거부.
- `preflight`: GPU 1·2·3, microbatch 8→4→2→1의 최초 통과값 동결. 실제 업데이트는 폐기한다.
- `all`: 사전검사(미완료일 때), 학습, 선택/test, 학습자료 진단, 내보내기/별도 재로딩을 순서대로 수행한다.
- `train --resume <완전checkpoint>`: 동일 소스·설정·자료이며 저장 이후 업데이트가 없는 frontier만 재개한다.
- `status`: 저장된 기록만 읽는다. `--help`는 인자 안내만 제공한다.

학습 중 조건변경·실패단계 자동 재실행·test 재생성은 없다. GPU 메모리/소유 host RSS는 controller가 감시하며 소유 process group만 정리한다.
가중 CE 분모는 실제 전역96(마지막69)문항의 가중치 합이다. 각 rank 누적분자에 world_size를 곱해 DDP 평균 후 전역 gradient와 일치시킨다.
마지막 실제 입력 위치만 판독하고 후보 외 logits를 제외한다. 토큰은 int32 mmap, offset/label/target/weight는 NumPy mmap이다.

사전 배치 동등성: 단독 대비 확률 최대절대차≤0.002·argmax 동일, dropout 비활성 gradient 상대L2≤0.02. 이 검사는 BF16 배치 연산차를 허용하는 수치 기준이다.
저장/복원 후 동일 업데이트의 LoRA 최대차≤1e-7. 최종 별도프로세스는 원평가와 같은 배치 형상을 유지하여 선택동일/확률차≤1e-5를 확인한다.

검증: `python -m unittest discover -s integration/jevk5_system1_training/tests` 및
`python -m torch.distributed.run --standalone --nproc_per_node=3 -m integration.jevk5_system1_training.tests.ddp_check`.

선택 기준은 독립규칙7영역 macro정확도→macroNLL→이른epoch이며 리플레이/타입/역할 진단을 선택에 섞지 않는다.
관측 KO는 확정KO가 아니며, 역할 미확인은 역할 불가가 아니다. 모든 평가 T=1. 실제배틀 승률은 평가하지 않는다.

현재 v2는 결정적 Torch/cuDNN 연산과 `CUBLAS_WORKSPACE_CONFIG=:4096:8`을 사용한다. 최초통과microbatch는1이며전역96은그대로다. v1 사전시도와 평가보기교정 이전 자료는 EX116/preparation-v1에 보존했다. 아직 본학습·test·최종내보내기 결과가 없으면 완료로 해석하지 않는다.
