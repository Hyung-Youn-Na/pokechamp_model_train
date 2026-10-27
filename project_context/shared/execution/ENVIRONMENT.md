# 실행 환경·명령 경계

<a id="environment"></a>

## 3. 기존 환경 선택

아래는 현재 연구 주기의 원경로다. 실제 사용할 실행기와 그 wrapper가 지정하는 interpreter를
함께 확인한다. 환경 안내의 오래된 설치·학습 예시를 새 실행 순서로 사용하지 않는다.

| 용도·실행기 | 기존 interpreter 또는 환경 | 설명 원문 |
|---|---|---|
| OpenAI Decisions v6 배틀 | `/workspace/pokechamp/.venv/bin/python` | [EX110 실행/결과 안내](../../../integration/openai_decisions_battle/README.md) |
| 독립 OpenAI Decisions API | `/workspace/.tools/openai-decisions/.venv/bin/python` | [실행 안내](../../../integration/openai_decisions/README.md), 실 배틀 검증은 EX110 |
| PokéChamp actor, 공동 q 배틀/수집, Kev 제어 | `/workspace/pokechamp/.venv/bin/python` | [통합 환경](../../../integration/pokechamp/README.md) |
| 고정 대진, 모방 학습, 자기대국, Abyssal 계열, Qwen 행렬 탐색 | `/ref/kev/.venv/bin/python` | 각 `scripts/` wrapper와 아래 실행기 표 |
| 공동 q 학습, 기존 Qwen 가치 경로 | `/workspace/.tools/eve-rlcd/worktrees/pokemon-training/.venv-eve-rlcd/bin/python` | [EVE 환경](../../../.tools/eve-rlcd/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md) |
| laya 0.4.13 학습·서빙 (EX-118/119) | `/workspace/.tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python` | [laya 0.4.13 환경](../../../.tools/laya-0.4.13/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md) · [EP-207](plans/EP-207-laya-0413-environment.md) |
| LAYA-RLCD 참고 환경 | `/workspace/.tools/laya-rlcd/worktrees/pokemon-training/.venv-train` | [LAYA 환경](../../../.tools/laya-rlcd/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md) |
| RLCD-Lite 참고 환경 | `/workspace/.tools/rlcd-lite/worktrees/pokemon-training/.venv-rlcd-lite` | [RLCD-Lite 환경](../../../.tools/rlcd-lite/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md) |
| JEV-27B 로컬 모델 | `/workspace/.pokechamp-data/jev27b-runtime/.venv/bin/python` | [wrapper](../../../scripts/jev27b), [기존 EX-082](../../research/model-evaluation/experiments/EX-082-jev27b-ex058-reproduction.md) |
| JEV-9B 로컬 모델 | `/workspace/.pokechamp-data/jev27b-runtime/.venv/bin/python` 재사용 | [wrapper](../../../scripts/jev9b), [EX-085](../../research/model-evaluation/experiments/EX-085-jev9b-single-choice.md) |
| MiniCPM5-2B-Jev 로컬 모델 | `/workspace/.pokechamp-data/jev27b-runtime/.venv/bin/python` 재사용 | [실행기](../../../scripts/jev-eval), [EX-091](../../research/model-evaluation/experiments/EX-091-minicpm5-2b-jev.md) |
| Tacit-9B Thinking | `/workspace/.pokechamp-data/tacit9b-runtime/.venv/bin/python` | [전용 안내](../../../integration/tacit9b/README.md) · EX-104 gate 필수 |
| Jev-Omni 텍스트 | `/workspace/.pokechamp-data/jev-omni-runtime/.venv/bin/python` | [전용 안내](../../../integration/jev_omni/README.md) · EX-103 gate 필수 |
| JEV-35B-NVFP4 | `/workspace/.pokechamp-data/jev35b-nvfp4-runtime/.venv/bin/python` | [전용 안내](../../../integration/jev35b_nvfp4/README.md) · EX-095 gate 필수 |
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
[통합 환경 안내](../../../integration/pokechamp/README.md)를 따른다. 환경의 이동·재설치·의존성 변경은
해당 변경을 다루는 작업 범위에서 검증한다. 복사본의 가상환경을 새 위치에서 바로 실행 가능한
환경으로 취급하지 않는다.

<a id="outputs"></a>

## 4. 실행기와 새 출력 경로

[D-147](../../research/planner-executor/decisions/D-147-planner-unlimited-disk.md)부터 새 `jev-planner` GLM/JEV 실행은
`evaluation.resources.disk_bytes: null`로 **디스크 용량 상한을 적용하지 않는다**.
디스크 사용량은 기록하며 용량 예산·사전 여유분·임시 복사본 합산 한도 때문에 실행을 막거나
중단하지 않는다. 실제 공간 부족/I/O 오류는 보고·처리한다. GPU/호스트 메모리·시간/호출 한도는
유지한다. 과거 실험/준비본의100GiB 조건·결과·봉인은 당시 기록으로 보존한다.

새 출력의 기준 위치는 [공통 출력 안내](../../RESEARCH_WORKFLOW.md#outputs)의
`runs/model-training/<새 실험 ID>`다. 출력 폴더만 바꿔 기존 EX의 동결 조건을 새 실험으로
사용하지 않는다. 아래 표는 현재 CLI 지원 범위이며 각 명령의 protocol·입력·준비 상태를 함께 확인한다.

| 실행기 | 출력 선택 | 읽기·실행 경계와 상세 안내 |
|---|---|---|
| `laya-imitation` | 고정 경로(EX-118/EX-119, 데이터셋 v1) | data는 CPU 변환·감사, train/evaluate는 GPU0 단독, battle은 mock/prepare/execute/export(포트8107·GPU0), status는 저장 JSON 조회. [안내](../../../integration/laya_imitation/README.md) |
| `openai-decisions-matchup-battle` | EX112 고정 경로 | mock은 API0 두경기, prepare/execute/status/export. [안내](../../../integration/openai_decisions_matchup_battle/README.md) |
| `candidate-matchup` | `--output` | 저장 v6에 후보별 요약 추가·OpenAI 요청 준비만 수행(API0). 기존출력 덮어쓰기 거부. [안내](../../../integration/candidate_matchup/README.md) |
| `jevk5-battle` | EX111 고정 경로 | capture는 외부정체성, mock은 모의2경기, gates는6추론, prepare/execute는 새32 동결/실행, status는 저장조회. [안내](../../../integration/jevk5_battle/README.md) |
| `jev-planner` | prepare의 `--output`, run의 `--directory`, export의 `--output` | preview/prepare는 모델 무호출. run의 mock/live 명시, live는 새EX·일정·호출/자원 한도 필요. EX-092/094 실제1경기 완료·EX-093 JSON 오류 실패 보존. 새 설정은 GLM temperature0·응답 형식 재생성 최대5회. [안내](../../../integration/jev_planner/README.md) |
| `tacit-ruleqa-battle` | EX108 고정 경로 | schedule은 EX107 검증 후 GPU1 단독32경기1회·후처리. status는 저장기록 조회. [안내](../../../integration/tacit_ruleqa_battle/README.md) |
| `jevk5-ruleqa-train` | EX113 고정 경로 | prepare→preflight→train→calibrate→evaluate→export, status 저장조회. [안내](../../../integration/jevk5_ruleqa_training/README.md) |
| `pokechamp-ruleqa-train` | `--output` | prepare는 CPU, preflight/train/evaluate/export는 GPU1·2·3. status는 저장 기록 조회. [학습 안내](../../../integration/pokechamp/rule_qa_training/README.md) · [EX-107](../../research/rule-learning/experiments/EX-107-tacit-ruleqa-lora.md) |
| `pokechamp-fixed-matchup` | `--directory` | `status`는 저장 JSON 열람. `prepare`·`verify`·`finalize`는 쓰기가 가능하다. [기술 안내](../../../integration/pokechamp/fixed_matchup/README.md) |
| `pokechamp-imitation`, `pokechamp-selfplay` | `--output` | `status`는 저장 JSON 열람. [모방 학습](../../../integration/pokechamp/imitation/README.md), [자기대국](../../../integration/pokechamp/selfplay/README.md) |
| `pokechamp-abyssal-rl`, `pokechamp-abyssal-rl-continue`, `pokechamp-abyssal-rl-next` | `--output` | `status`는 저장 JSON 열람. [첫 실행](../../../integration/pokechamp/abyssal_rl/README.md), [계승](../../../integration/pokechamp/abyssal_rl_continue/README.md), [추가 주기](../../../integration/pokechamp/abyssal_rl_next/README.md) |
| `pokechamp-joint-q` | `--out`, 입력 `--data` | 각 단계가 출력/lock·진입 기록을 쓴다. reload 검증은 GPU를 쓴다. [학습 안내](../../../integration/pokechamp/joint_q/learning/README.md) |
| `pokechamp-joint-q-battle`, `pokechamp-joint-q-tera` | `--directory` | battle의 `status`는 저장 JSON 열람. [배틀](../../../integration/pokechamp/joint_q/battle_eval/README.md), [자료 안내](../../../integration/pokechamp/joint_q/README.md) |
| `qwen-mcts` | `--directory` | `prepare`는 CPU 모델 로딩/출력 생성, `run`은 GPU 서버를 시작한다. EP132 경로 한계는 아래 절 참조. [기술 안내](../../../integration/qwen_mcts/README.md) |
| `pokechamp-qwen` | probe/battle/state-study/study-run의 `--output` | `start`는 `--output`을 받아도 서버 출력은 고정이다. `status`는 HTTP 확인이다. [구현](../../../integration/pokechamp/qwen_control.py) |
| `pokechamp-kev`, `pokechamp-kev-main`, `pokechamp-kev-continuation` | `--output` | 기존 EX 전용 경로이며 viewer export 목적지는 고정인 경우가 있다. `kev status`는 HTTP·GPU 상태를 확인한다. [Kev 안내](../../../integration/pokechamp/KEV.md) |
| `pokechamp-env` | 범용 출력 인자 없음 | qualification 출력은 `.artifacts/pokechamp` 고정. research 기록은 별도 `POKECHAMP_DATA_ROOT`를 쓴다. [통합 안내](../../../integration/pokechamp/README.md) |
| `quyet` | EX-084 보존 루트 고정 | download·prepare·execute는 쓰기/모델 실행. status는 저장 JSON 조회. [안내](../../../integration/quyet/README.md) |
| `jev9b` | EX-085 보존 루트 고정 | download·prepare·execute는 쓰기/모델 실행. status는 저장 JSON 조회. [안내](../../../integration/jev9b/README.md) |
| `strategist-eval` | EX-106 보존 루트 고정 | download·prepare·execute·status·export. GPU0 전용·실행 재개 금지. [안내](../../../integration/strategist_eval/README.md) |
| `jev-eval` | `--experiment EX-091` MiniCPM GPU0 단독 평가; EX-086–090 보존 | download는 EX-091 공식 파일 검증, prepare는 CPU 전수 대조/토큰화, execute는 단일 서버 검증·새32경기/감사/비교/뷰어·봉인, status는 저장 JSON 조회. reexport는 완료 EX-088/089의 별도 Damage-calc 판본이다. [안내](../../../integration/jev_eval/README.md) |
| `jev27b` | continue의 `--parent`, `--directory` | EX-083 계승은 새 출력 루트를 명시한다. execute/download/lengths는 기존 고정 경로다. [안내](../../../integration/jev27b/README.md) · [wrapper](../../../scripts/jev27b) |

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
새 작업의 실행·검증 범위는 [INDEX](../../INDEX.md#workflow)와 해당 EP/EX를 따른다.

