# 모델 학습 연구 매뉴얼

이 매뉴얼은 `research/model-training`에서 모델 학습·정책 개선·독립 평가를 준비하는
작업 순서를 안내한다. 현재 연구 주제·조건은 [CHARTER](CHARTER.md)와
[연구 설계](RESEARCH_DESIGN.md#branch-research-objective), 진행 중인 작업은
[STATUS](STATUS.md#active-work)에서 확인한다. 매뉴얼의 명령 예시는 새 실험 실행 지시가 아니다.
승인·중단·완료 기준의 원문은 [INDEX](INDEX.md#workflow)와 개별 EP/EX에 유지한다.

<a id="start"></a>

## 1. 작업 위치 확인

현재 연구 주기의 주 개발 checkout과 기존 실행 환경은 `/workspace`다.
먼저 실제 checkout·브랜치·변경분·submodule pin을 확인한다.

```bash
cd /workspace
GIT_OPTIONAL_LOCKS=0 git rev-parse --show-toplevel
GIT_OPTIONAL_LOCKS=0 git branch --show-current
GIT_OPTIONAL_LOCKS=0 git status --short --branch
GIT_OPTIONAL_LOCKS=0 git submodule status
```

기준 연구선은 `research/model-training`이다. 작업 브랜치가 따로 있으면 그 이름과 기준 연구선을
함께 기록한다. 현재 학습 원격은 `model-train`이며, 원격 역할과 L1–L5 checkout은
[Git·작업 위치 안내](RESEARCH_WORKFLOW.md#remotes)를 따른다.
Git clone에는 코드·문서·작은 고정 입력이 포함된다. 외부 모델·자료·환경은
[보존/복원 안내](RESEARCH_WORKFLOW.md#preservation)에서 연결하므로 다른 머신의 clone을
현재 연구 주기의 실행 환경과 같은 상태로 간주하지 않는다.

## 2. 연구 질문과 작업 등록

1. [현재 목표](CHARTER.md)와 [학습 설계](RESEARCH_DESIGN.md#pokemon-training-objective),
   관련 EX의 최종 결과·한계를 읽어 이번 질문이 무엇인지 정한다.
2. [plan 색인](exec-plans/INDEX.md)의 현재 실행 작업과 범위가 겹치는 중단 보존 plan을 확인한다.
   기존 사용자 승인과 동일 범위이면 [INDEX 절차](INDEX.md#workflow)에 따라 재사용한다.
3. [EP 템플릿](exec-plans/TEMPLATE.md)으로 작업 범위·변경 대상·검증·완료 기준을 기록한다.
   지속되는 설계·계약 변경이 있을 때는 [Decision 템플릿](decisions/TEMPLATE.md)을 사용한다.
4. 실제 실험은 [EX 템플릿](experiments/TEMPLATE.md)에 질문·모델/revision·데이터/분할·처치·
   기준선·독립 평가·자원/예산·중단/복구 조건과 출력 위치를 기록한다. 세부 원문을 EP에 중복하지 않는다.
5. 등록된 조건과 해당 실행기의 실제 동작이 맞는지 확인한 뒤 승인된 단계를 수행한다.

새 기록에는 연구선, 실제 branch/commit·미커밋 변경, checkout, interpreter/launcher,
새 출력 경로와 원자료/보존본을 구분해 적는다. 기존 ID는 재사용하지 않는다.
다른 연구선의 자료는 ID와 함께 branch·commit·EX/manifest를 인용해 출처를 식별한다.
이 문서는 기존 연구 질문·평가 기준·예산을 새로 정하지 않는다.

<a id="environment"></a>

## 3. 기존 환경 선택

아래는 현재 연구 주기의 원경로다. 실제 사용할 실행기와 그 wrapper가 지정하는 interpreter를
함께 확인한다. 환경 안내의 오래된 설치·학습 예시를 새 실행 순서로 사용하지 않는다.

| 용도·실행기 | 기존 interpreter 또는 환경 | 설명 원문 |
|---|---|---|
| PokéChamp actor, 공동 q 배틀/수집, Kev 제어 | `/workspace/pokechamp/.venv/bin/python` | [통합 환경](../integration/pokechamp/README.md) |
| 고정 대진, 모방 학습, 자기대국, Abyssal 계열, Qwen 행렬 탐색 | `/ref/kev/.venv/bin/python` | 각 `scripts/` wrapper와 아래 실행기 표 |
| 공동 q 학습, 기존 Qwen 가치 경로 | `/workspace/.tools/eve-rlcd/worktrees/pokemon-training/.venv-eve-rlcd/bin/python` | [EVE 환경](../.tools/eve-rlcd/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md) |
| LAYA-RLCD 참고 환경 | `/workspace/.tools/laya-rlcd/worktrees/pokemon-training/.venv-train` | [LAYA 환경](../.tools/laya-rlcd/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md) |
| RLCD-Lite 참고 환경 | `/workspace/.tools/rlcd-lite/worktrees/pokemon-training/.venv-rlcd-lite` | [RLCD-Lite 환경](../.tools/rlcd-lite/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md) |
| JEV-27B 로컬 모델 | `/workspace/.pokechamp-data/jev27b-runtime/.venv/bin/python` | [wrapper](../scripts/jev27b), [기존 EX-082](experiments/EX-082-jev27b-ex058-reproduction.md) |
| 기존 오프라인 브라우저 검사 | `/tmp/ep037/tools/bin/python` | 해당 실행기의 검증/최종화 코드 |

파일·경로 존재만 확인할 때는 다음처럼 조회한다. 이 결과는 모델 로딩·학습·실험 gate 통과를
뜻하지 않는다. 필요한 검증의 범위는 해당 작업의 변경과 미해결 우려에 맞춰 정한다.

```bash
test -x /workspace/pokechamp/.venv/bin/python
test -x /ref/kev/.venv/bin/python
readlink -f /ref/kev/.venv/bin/python
sed -n '1,12p' /ref/kev/.venv/pyvenv.cfg
```

자격증명은 원래 위치에서 관리하며 문서·로그·Git에 값을 넣지 않는다. `.env` 처리 규범은
[통합 환경 안내](../integration/pokechamp/README.md)를 따른다. 환경의 이동·재설치·의존성 변경은
해당 변경을 다루는 작업 범위에서 검증한다. 복사본의 가상환경을 새 위치에서 바로 실행 가능한
환경으로 취급하지 않는다.

<a id="outputs"></a>

## 4. 실행기와 새 출력 경로

새 출력의 기준 위치는 [공통 출력 안내](RESEARCH_WORKFLOW.md#outputs)의
`runs/model-training/<새 실험 ID>`다. 출력 폴더만 바꿔 기존 EX의 동결 조건을 새 실험으로
사용하지 않는다. 아래 표는 현재 CLI 지원 범위이며 각 명령의 protocol·입력·준비 상태를 함께 확인한다.

| 실행기 | 출력 선택 | 읽기·실행 경계와 상세 안내 |
|---|---|---|
| `pokechamp-fixed-matchup` | `--directory` | `status`는 저장 JSON 열람. `prepare`·`verify`·`finalize`는 쓰기가 가능하다. [기술 안내](../integration/pokechamp/fixed_matchup/README.md) |
| `pokechamp-imitation`, `pokechamp-selfplay` | `--output` | `status`는 저장 JSON 열람. [모방 학습](../integration/pokechamp/imitation/README.md), [자기대국](../integration/pokechamp/selfplay/README.md) |
| `pokechamp-abyssal-rl`, `pokechamp-abyssal-rl-continue`, `pokechamp-abyssal-rl-next` | `--output` | `status`는 저장 JSON 열람. [첫 실행](../integration/pokechamp/abyssal_rl/README.md), [계승](../integration/pokechamp/abyssal_rl_continue/README.md), [추가 주기](../integration/pokechamp/abyssal_rl_next/README.md) |
| `pokechamp-joint-q` | `--out`, 입력 `--data` | 각 단계가 출력/lock·진입 기록을 쓴다. reload 검증은 GPU를 쓴다. [학습 안내](../integration/pokechamp/joint_q/learning/README.md) |
| `pokechamp-joint-q-battle`, `pokechamp-joint-q-tera` | `--directory` | battle의 `status`는 저장 JSON 열람. [배틀](../integration/pokechamp/joint_q/battle_eval/README.md), [자료 안내](../integration/pokechamp/joint_q/README.md) |
| `qwen-mcts` | `--directory` | `prepare`는 CPU 모델 로딩/출력 생성, `run`은 GPU 서버를 시작한다. EP132 경로 한계는 아래 절 참조. [기술 안내](../integration/qwen_mcts/README.md) |
| `pokechamp-qwen` | probe/battle/state-study/study-run의 `--output` | `start`는 `--output`을 받아도 서버 출력은 고정이다. `status`는 HTTP 확인이다. [구현](../integration/pokechamp/qwen_control.py) |
| `pokechamp-kev`, `pokechamp-kev-main`, `pokechamp-kev-continuation` | `--output` | 기존 EX 전용 경로이며 viewer export 목적지는 고정인 경우가 있다. `kev status`는 HTTP·GPU 상태를 확인한다. [Kev 안내](../integration/pokechamp/KEV.md) |
| `pokechamp-env` | 범용 출력 인자 없음 | qualification 출력은 `.artifacts/pokechamp` 고정. research 기록은 별도 `POKECHAMP_DATA_ROOT`를 쓴다. [통합 안내](../integration/pokechamp/README.md) |
| `jev27b` | 단계별로 다름 | execute/download/lengths는 고정 경로. 범용 `--output` 지원으로 취급하지 않는다. [wrapper](../scripts/jev27b) |

이미 준비된 승인 실행의 상태를 읽는 예시다. `EX-NEW`를 실제 기록의 ID로 바꾼다.

```bash
cd /workspace
POKECHAMP_RUN_DIR='/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-NEW'
PYTHONDONTWRITEBYTECODE=1 scripts/pokechamp-fixed-matchup status --directory "$POKECHAMP_RUN_DIR"
```

<a id="command-boundaries"></a>

## 5. 확인 명령과 실행 명령 구분

`status`, `verify`, `--help`라는 이름만으로 부작용을 판단하지 않는다. 현재 소스에서 확인한
아래 경우는 단순 문서/파일 조회와 다르다.

- `scripts/jev27b execute --help`는 인자를 해석하지 않고 `execute()`에 진입한다.
- EVE의 `run-pokemon-value.sh --help`는 고정 EX-061 학습·재로딩을 실행한다.
- Metamon의 `bootstrap.sh --help`는 설치를 수행한다.
- `pokechamp-env server status`도 manifest를 쓰며, Qwen/Kev의 `status`는 서버 조회를 수행한다.
- 환경의 `check_training_env.py`는 GPU 연산·모델 추론·결과 쓰기를 포함한다.

wrapper의 빈 `CUDA_VISIBLE_DEVICES`는 controller 설정일 수 있으며 하위 `run`의 GPU 실행을
금지하는 일반 장치가 아니다. 처음 보는 wrapper는 소스를 읽어 인자 처리와 호출 대상을 확인한다.
새 작업의 실행·검증 범위는 [INDEX](INDEX.md#workflow)와 해당 EP/EX를 따른다.

## 6. 자료·평가·종결

기존 실행의 보고서 → manifest → 원자료 순으로 읽는다. `.pokechamp-data/experiments`,
`export/teams`, `exports/pokemon-role-data`, replay corpus에는 학습 입력뿐 아니라 평가/참조
자료도 있으므로 새 데이터 포함 범위는 [학습 설계](RESEARCH_DESIGN.md#pokemon-training-objective)와
해당 EX의 분할·오염 통제에 맞춘다. 학습 손실이나 같은 학습 자료의 재평가만으로 독립 성능
개선을 주장하지 않는다.

결과는 해당 EX에 실제 분모·실패/중단·불확실성과 함께 기록하고 EP의 완료 기준을 대조한다.
보고·봉인·소유 자원 정리와 [C-047](CONTRACTS.md#c-047-viewer-export)의 배틀 viewer 요건은
해당 실행에 적용한다. 새 run 출력 경로와 `/workspace/exports/battle_viewers/`는 역할이 다르다.
기존 snapshot·봉인·Blocked/Paused를 새 작업 결과로 덮어쓰지 않는다.

## 7. 다른 연구선과 보존본

L1–L5 이식의 source·설계는 별도 checkout의 매뉴얼을 따른다. 그 worktree의 evidence·exports와
일부 `.tools/.../docs`는 보존본으로 연결된 읽기용 링크다. 연구선 간 코드를 옮길 때는 변경 범위와
출처 commit을 확인하고 필요한 변경을 명시적으로 반영한다. 작업 전체나 legacy TODO를 자동 계승하지 않는다.

복원 절차와 EP-135 기준 기록은 [보존 안내](RESEARCH_WORKFLOW.md#preservation) 및
[복원 절차](RESEARCH_WORKFLOW.md#restore)를 따른다. `snapshot/pre-split`과 당시 bundle/receipt는
분리 완료 시점의 기록이며 이후 README·매뉴얼 커밋을 가리키도록 갱신하지 않는다.

현재 `integration/qwen_mcts/prepare.py`의 EP132 active/completed 경로 불일치는
[알려진 한계](RESEARCH_WORKFLOW.md#limitations)에 남아 있다. 준비 명령을 확인용으로 실행하거나
문서 경로 오류를 이유로 봉인 검사를 우회하지 않는다.
