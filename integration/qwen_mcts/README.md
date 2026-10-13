# qwen_mcts — EX-080 Qwen3.5-0.8B 행렬 탐색 자기대국

## 분리된 연구선에서 읽는 방법

현재 checkout의 작업·환경 선택은 [연구 매뉴얼](../../project_context/RESEARCH_MANUAL.md), 실행 여부는
[STATUS](../../project_context/STATUS.md#active-work)를 먼저 확인한다. 아래 실행 명령은 `/workspace`의 기존 환경을
기준으로 한 기술 참조다. L1–L5 worktree는 보존·설계용이며 실행용 환경이 구성되어 있지 않다.
D/EX가 지정된 조건·경로·재개 명령은 해당 실험의 범위로 읽고, 공통 규칙은 기존 적용 범위를
유지한다. 새 실험의 입력·출력·실행 범위는 등록된 작업에서 정한다.


조건 원문은 [EX-080](../../project_context/experiments/EX-080-qwen-matrix-selfplay.md),
결정은 [D-127](../../project_context/decisions/D-127-qwen-matrix-selfplay.md),
당시 실행·완료 기록은 [EP-132](../../project_context/exec-plans/completed/EP-132-qwen-matrix-selfplay.md)를 따른다.

## EX-080 명령 (기술 참조)

`prepare.py`가 EP-132를 `active/`에서 찾지만 문서는 `completed/`에 있는 알려진 경로
불일치가 남아 있다. prepare는 그 문서를 읽기 전에 출력·초기 모델을 만들 수 있으므로
단순 확인용으로 실행하지 않는다. [현재 한계](../../project_context/RESEARCH_WORKFLOW.md#limitations)를 따른다.

```bash
scripts/qwen-mcts prepare --directory .pokechamp-data/experiments/ex080-qwen-matrix-selfplay-attempt3   # CPU, identity 동결
scripts/qwen-mcts verify  --directory ...                                                    # live source/env 대조
scripts/qwen-mcts run     --directory ...                                                    # GPU2·3 서버 기동, 단계별 재개
/ref/kev/.venv/bin/python -m pytest integration/qwen_mcts/tests -q -p no:cacheprovider       # CPU 검사
```

`run`의 단계는 다음 순서로 진행한다. 끝난 단계는 기록 파일(`gates.json`, `settings.json`, `smoke.json`,
`rounds/*/commit.json`, `train-stop.json`, `selection.json`, `test.json`)이 있으면 건너뛴다.
예약했지만 끝나지 않은 경기는 incomplete로 기록하고 다시 하지 않는다.

1. GPU 게이트 G0~G8
2. 처리량 측정
3. smoke 8경기
4. 학습 루프
5. 선택
6. 잠긴 test

단계 사건은 `<run>/events.jsonl`에 남는다.

## 구조

| 파일 | 역할 |
|---|---|
| `render.cjs`, `sim.cjs` | 검증된 공개 JSON만 읽는 `fixed-matchup-qwen-text-v1` 렌더러. real/search 역할로 분리된 Showdown 워커(`expand`: 결정당 모든 joint 자식) |
| `tokens.py` | 정적 접두, 자식 행, 루트 행의 토큰 배치와 구분 토큰 |
| `solver.py` | 사전 정책을 magnet으로 둔 MMD 정규화 균형(float64) |
| `network.py` | Qwen3.5 text backbone, 태그별 LoRA 어댑터, 포인터·가치 head, 정적 캐시 복제 경로, Kev 공유 접두 경로 |
| `server.py` | GPU별 장수명 프로세스(lock 보유, 배치 추론, GPU2 학습) |
| `pool.py`, `game.py`, `search.py` | torch 없는 CPU 워커, 실제 경기 루프, 행렬 탐색 |
| `schedule.py`, `replay.py`, `trainer.py`, `evaluation.py` | seed namespace, 학습 행, 학습 라운드, 점수·둔화 종료·BT 선택·bootstrap |
| `prepare.py`, `gates.py`, `run.py` | identity, GPU 게이트, 컨트롤러 |
| `vendor/` + `VENDOR.json` | `integration/pokechamp` 복사본과 원본·사본 해시(EX-079 해시 범위 보호) |

## EX-080 동결 당시 경계

- **당시 보호 범위:** `integration/pokechamp/**`, Showdown dist, `pokechamp/poke_env`, RD·CONTRACTS·CHARTER, 공유 venv.
  EX-080 준비 당시 EX-079의 해시 범위를 보호하기 위한 경계다. 현재 진행 여부는 위 STATUS와 해당 EP를 따른다.
- **이 실행의 live 재검증 범위:** 이 패키지(`tests/`·`finalize/` 제외), Showdown dist, poke_env, Kev 고정 파일,
  모델 snapshot, 팀 목록, 래퍼. 문서는 `<run>/docs/` 사본만 보존한다.
- **GPU:** 물리 GPU2·3만 쓰며, 각 서버가 `.pokechamp-data/locks/gpu{2,3}.lock`을 잡는다.
