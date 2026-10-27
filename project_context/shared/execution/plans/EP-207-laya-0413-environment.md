# EP-207 — laya 0.4.13 독립 학습·추론 환경

- 상태: Completed
- 생성일: 2026-10-22
- 책임자: Claude Code
- 승인 근거: 현재 사용자 지시와 승인된 계획 / [D-183](../../../research/policy-learning/decisions/D-183-laya-compact-imitation.md)
- 관련 원문: [EP-208](../../../research/policy-learning/plans/EP-208-laya-compact-imitation.md), [EP-096](EP-096-laya-training-environment.md)
- 기준 연구선: `research/model-training`, `/workspace`, 시작 commit `feda62f733c1b470364868262c789ec857ef67f5`. 기존 미커밋 변경은 보존하고 손대지 않는다.

## 목표·범위

원본 laya 0.4.13으로 독립 환경을 구성한다. 공개 체크포인트의 고정 revision을 GPU0에서 로딩하고 최소 추론까지 검증한다.

| 항목 | 내용 |
|---|---|
| source | `/workspace/.tools/laya-0.4.13/upstream`. `/ref/laya`의 `6f0496f7`("release: 0.4.13")을 clone하고 고정한다. |
| worktree | `/workspace/.tools/laya-0.4.13/worktrees/pokemon-training`, branch `pokemon-training-env` |
| venv | worktree 아래 `.venv` (Python 3.11, uv). Torch는 EP-096과 같은 `2.11.0+cu128`. upstream은 editable 설치. |
| 모델 | `convaiinnovations/laya-typed-decisions` revision `e929ae5cf69bc34259cd2f95c9e91145b818b1f0`. 저장 위치는 `/mnt/digicap/combined/hyna/backup/pokechamp-research/models/laya-typed-decisions/e929ae5c/`이며 파일별 SHA-256을 기록한다. |

- **변경하지 않는 것**: 기존 `.tools/laya-rlcd`(laya 0.3.4)와 다른 환경, driver.
- **금지**: 자동 package fallback, 배틀, 학습.
- **GPU**: GPU0 잠금(`/workspace/.pokechamp-data/locks/gpu0.lock`)과 UUID 확인 후에만 쓴다.

## 완료 기준

- [x] 고정 source, 별도 branch와 worktree
- [x] 독립 환경 설치, 패키지 목록, `pip check`
- [x] upstream CI 게이트(`ruff …`, `compileall`)와 plain 스위트(`tests/test_router.py`, `test_criteria.py`, `test_hooks.py`, `test_hooks_api.py`)
- [x] GPU0 텐서 연산·역전파·동기화
- [x] 공개 모델 revision과 hash, GPU0 로딩, 최소 추론
- [x] 한국어 재진입 안내(`docs/POKEMON_ENVIRONMENT.md`), `ENVIRONMENT.md`와 `ARCHITECTURE.md` 행, 증거 `exec-plans/evidence/ep207/`

## 검증·중단

- 증거는 `../../../exec-plans/evidence/ep207/`에 둔다.
- 설치, GPU, 모델 실패는 원인을 기록한다. 버전이나 드라이버를 바꿔 우회하지 않는다.
- 비실험 환경 준비이므로 실험 시계, 재수집, 배틀 뷰어는 해당 없다.

## 진행

- 2026-10-22 — 승인 범위 등록. GPU0 유휴(0 MiB, 프로세스 없음)와 HF revision을 확인했다. 설치는 아직 하지 않았다.
- 2026-10-22 — 설치, pip check, CI 게이트, plain 4스위트(1,984건 통과), GPU0 연산·역전파, 모델 해시·로딩·최소 추론을 완료했다. [검증 보고](../../../exec-plans/evidence/ep207/report.md), [환경 안내](../../../../.tools/laya-0.4.13/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md). 시작 체크포인트의 `choice:11+` 온도 범위 밖 경고를 기록했다. 학습과 배틀은 0회이며 포켓몬 성능은 아직 평가하지 않았다.
