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
| OpenAI Decisions v6 배틀 | `/workspace/pokechamp/.venv/bin/python` | [EX110 실행/결과 안내](../integration/openai_decisions_battle/README.md) |
| 독립 OpenAI Decisions API | `/workspace/.tools/openai-decisions/.venv/bin/python` | [실행 안내](../integration/openai_decisions/README.md), 실 배틀 검증은 EX110 |
| PokéChamp actor, 공동 q 배틀/수집, Kev 제어 | `/workspace/pokechamp/.venv/bin/python` | [통합 환경](../integration/pokechamp/README.md) |
| 고정 대진, 모방 학습, 자기대국, Abyssal 계열, Qwen 행렬 탐색 | `/ref/kev/.venv/bin/python` | 각 `scripts/` wrapper와 아래 실행기 표 |
| 공동 q 학습, 기존 Qwen 가치 경로 | `/workspace/.tools/eve-rlcd/worktrees/pokemon-training/.venv-eve-rlcd/bin/python` | [EVE 환경](../.tools/eve-rlcd/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md) |
| LAYA-RLCD 참고 환경 | `/workspace/.tools/laya-rlcd/worktrees/pokemon-training/.venv-train` | [LAYA 환경](../.tools/laya-rlcd/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md) |
| RLCD-Lite 참고 환경 | `/workspace/.tools/rlcd-lite/worktrees/pokemon-training/.venv-rlcd-lite` | [RLCD-Lite 환경](../.tools/rlcd-lite/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md) |
| JEV-27B 로컬 모델 | `/workspace/.pokechamp-data/jev27b-runtime/.venv/bin/python` | [wrapper](../scripts/jev27b), [기존 EX-082](experiments/EX-082-jev27b-ex058-reproduction.md) |
| JEV-9B 로컬 모델 | `/workspace/.pokechamp-data/jev27b-runtime/.venv/bin/python` 재사용 | [wrapper](../scripts/jev9b), [EX-085](experiments/EX-085-jev9b-single-choice.md) |
| MiniCPM5-2B-Jev 로컬 모델 | `/workspace/.pokechamp-data/jev27b-runtime/.venv/bin/python` 재사용 | [실행기](../scripts/jev-eval), [EX-091](experiments/EX-091-minicpm5-2b-jev.md) |
| Tacit-9B Thinking | `/workspace/.pokechamp-data/tacit9b-runtime/.venv/bin/python` | [전용 안내](../integration/tacit9b/README.md) · EX-104 gate 필수 |
| Jev-Omni 텍스트 | `/workspace/.pokechamp-data/jev-omni-runtime/.venv/bin/python` | [전용 안내](../integration/jev_omni/README.md) · EX-103 gate 필수 |
| JEV-35B-NVFP4 | `/workspace/.pokechamp-data/jev35b-nvfp4-runtime/.venv/bin/python` | [전용 안내](../integration/jev35b_nvfp4/README.md) · EX-095 gate 필수 |
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

[D-147](decisions/D-147-planner-unlimited-disk.md)부터 새 `jev-planner` GLM/JEV 실행은
`evaluation.resources.disk_bytes: null`로 **디스크 용량 상한을 적용하지 않는다**.
디스크 사용량은 기록하며 용량 예산·사전 여유분·임시 복사본 합산 한도 때문에 실행을 막거나
중단하지 않는다. 실제 공간 부족/I/O 오류는 보고·처리한다. GPU/호스트 메모리·시간/호출 한도는
유지한다. 과거 실험/준비본의100GiB 조건·결과·봉인은 당시 기록으로 보존한다.

새 출력의 기준 위치는 [공통 출력 안내](RESEARCH_WORKFLOW.md#outputs)의
`runs/model-training/<새 실험 ID>`다. 출력 폴더만 바꿔 기존 EX의 동결 조건을 새 실험으로
사용하지 않는다. 아래 표는 현재 CLI 지원 범위이며 각 명령의 protocol·입력·준비 상태를 함께 확인한다.

| 실행기 | 출력 선택 | 읽기·실행 경계와 상세 안내 |
|---|---|---|
| `openai-decisions-matchup-battle` | EX112 고정 경로 | mock은 API0 두경기, prepare/execute/status/export. [안내](../integration/openai_decisions_matchup_battle/README.md) |
| `candidate-matchup` | `--output` | 저장 v6에 후보별 요약 추가·OpenAI 요청 준비만 수행(API0). 기존출력 덮어쓰기 거부. [안내](../integration/candidate_matchup/README.md) |
| `jevk5-battle` | EX111 고정 경로 | capture는 외부정체성, mock은 모의2경기, gates는6추론, prepare/execute는 새32 동결/실행, status는 저장조회. [안내](../integration/jevk5_battle/README.md) |
| `jev-planner` | prepare의 `--output`, run의 `--directory`, export의 `--output` | preview/prepare는 모델 무호출. run의 mock/live 명시, live는 새EX·일정·호출/자원 한도 필요. EX-092/094 실제1경기 완료·EX-093 JSON 오류 실패 보존. 새 설정은 GLM temperature0·응답 형식 재생성 최대5회. [안내](../integration/jev_planner/README.md) |
| `tacit-ruleqa-battle` | EX108 고정 경로 | schedule은 EX107 검증 후 GPU1 단독32경기1회·후처리. status는 저장기록 조회. [안내](../integration/tacit_ruleqa_battle/README.md) |
| `jevk5-ruleqa-train` | EX113 고정 경로 | prepare→preflight→train→calibrate→evaluate→export, status 저장조회. [안내](../integration/jevk5_ruleqa_training/README.md) |
| `pokechamp-ruleqa-train` | `--output` | prepare는 CPU, preflight/train/evaluate/export는 GPU1·2·3. status는 저장 기록 조회. [학습 안내](../integration/pokechamp/rule_qa_training/README.md) · [EX-107](experiments/EX-107-tacit-ruleqa-lora.md) |
| `pokechamp-fixed-matchup` | `--directory` | `status`는 저장 JSON 열람. `prepare`·`verify`·`finalize`는 쓰기가 가능하다. [기술 안내](../integration/pokechamp/fixed_matchup/README.md) |
| `pokechamp-imitation`, `pokechamp-selfplay` | `--output` | `status`는 저장 JSON 열람. [모방 학습](../integration/pokechamp/imitation/README.md), [자기대국](../integration/pokechamp/selfplay/README.md) |
| `pokechamp-abyssal-rl`, `pokechamp-abyssal-rl-continue`, `pokechamp-abyssal-rl-next` | `--output` | `status`는 저장 JSON 열람. [첫 실행](../integration/pokechamp/abyssal_rl/README.md), [계승](../integration/pokechamp/abyssal_rl_continue/README.md), [추가 주기](../integration/pokechamp/abyssal_rl_next/README.md) |
| `pokechamp-joint-q` | `--out`, 입력 `--data` | 각 단계가 출력/lock·진입 기록을 쓴다. reload 검증은 GPU를 쓴다. [학습 안내](../integration/pokechamp/joint_q/learning/README.md) |
| `pokechamp-joint-q-battle`, `pokechamp-joint-q-tera` | `--directory` | battle의 `status`는 저장 JSON 열람. [배틀](../integration/pokechamp/joint_q/battle_eval/README.md), [자료 안내](../integration/pokechamp/joint_q/README.md) |
| `qwen-mcts` | `--directory` | `prepare`는 CPU 모델 로딩/출력 생성, `run`은 GPU 서버를 시작한다. EP132 경로 한계는 아래 절 참조. [기술 안내](../integration/qwen_mcts/README.md) |
| `pokechamp-qwen` | probe/battle/state-study/study-run의 `--output` | `start`는 `--output`을 받아도 서버 출력은 고정이다. `status`는 HTTP 확인이다. [구현](../integration/pokechamp/qwen_control.py) |
| `pokechamp-kev`, `pokechamp-kev-main`, `pokechamp-kev-continuation` | `--output` | 기존 EX 전용 경로이며 viewer export 목적지는 고정인 경우가 있다. `kev status`는 HTTP·GPU 상태를 확인한다. [Kev 안내](../integration/pokechamp/KEV.md) |
| `pokechamp-env` | 범용 출력 인자 없음 | qualification 출력은 `.artifacts/pokechamp` 고정. research 기록은 별도 `POKECHAMP_DATA_ROOT`를 쓴다. [통합 안내](../integration/pokechamp/README.md) |
| `quyet` | EX-084 보존 루트 고정 | download·prepare·execute는 쓰기/모델 실행. status는 저장 JSON 조회. [안내](../integration/quyet/README.md) |
| `jev9b` | EX-085 보존 루트 고정 | download·prepare·execute는 쓰기/모델 실행. status는 저장 JSON 조회. [안내](../integration/jev9b/README.md) |
| `strategist-eval` | EX-106 보존 루트 고정 | download·prepare·execute·status·export. GPU0 전용·실행 재개 금지. [안내](../integration/strategist_eval/README.md) |
| `jev-eval` | `--experiment EX-091` MiniCPM GPU0 단독 평가; EX-086–090 보존 | download는 EX-091 공식 파일 검증, prepare는 CPU 전수 대조/토큰화, execute는 단일 서버 검증·새32경기/감사/비교/뷰어·봉인, status는 저장 JSON 조회. reexport는 완료 EX-088/089의 별도 Damage-calc 판본이다. [안내](../integration/jev_eval/README.md) |
| `jev27b` | continue의 `--parent`, `--directory` | EX-083 계승은 새 출력 루트를 명시한다. execute/download/lengths는 기존 고정 경로다. [안내](../integration/jev27b/README.md) · [wrapper](../scripts/jev27b) |

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

<a id="archived-datasets"></a>

### 6.1 보관한 Pokémon Showdown 데이터셋

추가 JSONL 보관본은 [6.2절 pokechamp-pretrain-data](#pretrain-dataset)와
[6.3절 pokemon-training-data](#pokemon-training-dataset)를 참조한다.

두 자료는 **경기 전체 리플레이**와 **리플레이에서 가공한 턴별 SFT 대화**라는 관계다.
SFT의 원자료 출처는 작성자 README의 설명이며, 원경기별 대응이나 원자료 test와의 중복은
확인하지 않았다. 아래는 보관한 고정 revision 기준 안내다. 다운로드·파일 검증의 상세 원문은
[EP-165](exec-plans/completed/EP-165-showdown-sft-archive.md)·
[EP-166](exec-plans/completed/EP-166-pokechamp-dataset-archive.md) 및 각 manifest에 둔다.

보관 루트: `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/`.

| 항목 | `milkkarten/pokechamp` | `stevenkhan/pokemon-showdown-battle-sft` |
|---|---|---|
| 한 행의 단위 | 경기 1개의 Showdown 이벤트 로그 | 특정 턴의 상태·행동 추천 대화 1개 |
| 분할·행 수 | train 1,916,868 / test 213,356; 총 2,130,224 | train 500,057; 별도 test 없음 |
| Parquet 구성 | `data/train-*.parquet` 37개, `data/test-*.parquet` 5개 | `data/train-*.parquet` 2개 |
| 전체 원본 구성·용량 | 45개, 5,566,414,178 bytes (약 5.57 GB) | 4개, 537,045,320 bytes (약 537 MB) |
| 보관 폴더 | [milkkarten/pokechamp](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp/) | [stevenkhan/pokemon-showdown-battle-sft](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/stevenkhan/pokemon-showdown-battle-sft/) |
| 원문 | [README](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp/README.md) | [README](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/stevenkhan/pokemon-showdown-battle-sft/README.md) |
| 출처·revision·검증 | [manifest.json](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp/manifest.json) | [manifest.json](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/stevenkhan/pokemon-showdown-battle-sft/manifest.json) |
| 원문 라이선스 표기 | 보관 README에 선언 없음 | `apache-2.0` 선언 |

용량은 원본 파일 합계이며 보관용 `manifest.json`과 CLI의 `.cache/huggingface/`는 제외한다.
두 폴더 모두 원본 README·.gitattributes와 data 구조를 유지하며, pokechamp에는
`resource/method.png`도 포함된다. 고정 revision은 다음과 같다.

- `milkkarten/pokechamp`: `b5820ff5d0c8d5e5cec692d55f756b6e5a66a203`
- `stevenkhan/pokemon-showdown-battle-sft`: `8acf5b03d84cc3cad9a52906f237c4db199bd59a`

**경기 로그 구조.** pokechamp의 컬럼은 모두 문자열이다.

| 필드 | 의미 |
|---|---|
| `text` | `|turn|`, `|move|`, `|switch|`, `|-damage|`, `|win|` 등 시간순 경기 이벤트 |
| `month_year` | 월·연도, 예: `May2024` |
| `gamemode` | 세대·경기 형식, 예: `gen9nu` |
| `elo` | 레이팅 구간 문자열, 예: `1000-1199` |
| `battle_id` | 경기 식별자 |

작성자는 Gen 1–9, 37개 이상 형식, 여러 레이팅 구간과 2024–2025년 자료를 설명한다.
이는 작성자 설명이며 실제 분포의 전수 집계 결과는 아니다. 경기 ID와 메타데이터를 이용해
원경기를 추적·필터링할 수 있다. 턴별 학습 입력에는 이벤트 파싱과 의사결정 시점의 관측 재구성이
필요하며, 공개 리플레이에 드러나지 않은 정보는 이 schema만으로 확정할 수 없다.

**SFT 구조.** 최상위 컬럼은 `messages` 하나이며,
`list<struct<role: string, content: string>>` 형태다. 모든 행에 다음 메시지가 각 1개씩 있다.

| role | content의 역할 |
|---|---|
| `system` | 배틀 전략가 역할·응답 지침 |
| `user` | 턴·형식, 현재 포켓몬·HP·상태, 공개 기술·특성, 벤치·상대 공개 정보·필드 등의 상태 요약 |
| `assistant` | `Action: Use ...` 또는 `Action: Switch to ...`와 설명 |

작성자는 pokechamp에서 ELO 1400 이상·승자가 있는 경기·의미 있는 턴 3개 이상을 필터링하고
승자 측 행동을 추출했다고 설명한다. Gen 9 비중 약75%라는 설명과 필터 충족 여부는
독립적으로 재검증하지 않았다. 전략 설명은 가공 과정에서 생성된 것으로, 원 플레이어의
사고 기록이나 모든 행동의 최적성을 입증하는 자료가 아니다. 원경기 ID·날짜·레이팅의 별도
컬럼이 없어 원자료와의 대응·중복 확인에는 추가 작업이 필요하다.

**확인한 범위.** 두 자료 모두 원격 파일 목록·크기·파일 정체성 대조를 통과했다.
SFT는 전체500,057행의 메시지 구조를 검사했다. pokechamp는42개 Parquet의 schema와
footer 행 수를 확인하고 파일마다 첫32행을 읽었다. 내용의 전략적 정확성, 상태와 행동의
시점 정합성, 학습 적합성이나 두 자료 간 평가 오염 여부를 검증한 것은 아니다.
데이터 사용 조건·분할·오염 통제는 위6절의 학습 설계와 해당 EX에서 정한다.

<a id="pretrain-dataset"></a>

### 6.2 보관한 pokechamp-pretrain-data

[`milkkarten/pokechamp-pretrain-data`](https://huggingface.co/datasets/milkkarten/pokechamp-pretrain-data)의
고정 revision `be424eb903daf07deb57a579f48be319c02d6224`를
[EP-168](exec-plans/completed/EP-168-pretrain-data-archive.md)에서 보관했다.
위6.1절의 두 Parquet 자료와 별도 폴더에 둔 JSONL 자료다.

- 보관 경로: `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp-pretrain-data/`
- [폴더](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp-pretrain-data/) · [manifest.json](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp-pretrain-data/manifest.json) · [원본 통계](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp-pretrain-data/stage_1a_stats.json)
- 원본3개 파일: `.gitattributes`, `stage_1a.jsonl`, `stage_1a_stats.json`.
- 원본 합계 **63,051,202,721 bytes (약63.05 GB)**. CLI metadata와 보관 manifest는 제외한다.
- JSONL **121,960,458행**이며 원본 stats의 `total_samples`와 일치한다.
- 이 revision에는 README·라이선스 선언·train/test 분할 설명이 없다.

첫32행 JSON 표본의 필드와 자료형은 다음과 같다. 필드 설명은 표본 내용에 근거하며,
전체 데이터의 의미·분포를 확정한 결과는 아니다.

| 필드 | 표본 자료형 | 표본에서 확인한 내용 |
|---|---|---|
| `prompt` | string | 경기 형식·턴·현재 포켓몬·HP·기술·상대 정보 등을 담은 입력 |
| `response` | string | 행동 문자열; 빈 문자열인 표본도 있음 |
| `opponent_action` | string | 상대 행동 문자열 |
| `reward` | float | 보상 수치; 계산 규칙은 원본에 별도 설명 없음 |
| `done` | bool | 종료 여부를 나타내는 필드 |
| `turn` | int | 턴 번호 |
| `format` | string | 경기 형식, 예: `gen1ou` |

원격3파일의 목록·크기·해시 대조, JSONL 전체 물리 행 수 집계와 stats 대조,
첫32행의 JSON 디코딩·동일 구조 확인을 완료했다. 모든 행의 JSON 구문·전략적 정확성·
상태와 행동의 시점 정합성·다른 자료와의 중복은 검증하지 않았다.
학습 사용 조건·분할·오염 통제는 위6절의 설계/EX 안내를 따른다.

<a id="pokemon-training-dataset"></a>

### 6.3 보관한 pokemon-training-data

[`milkkarten/pokemon-training-data`](https://huggingface.co/datasets/milkkarten/pokemon-training-data)의
고정 revision `4bdd862f098852498ed0c696a2bbc4d64e43801e`를
[EP-170](exec-plans/completed/EP-170-pokemon-training-data-archive.md)에서 원구조로 보관했다.

- 보관 경로: `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokemon-training-data/`
- [폴더](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokemon-training-data/) · [manifest.json](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokemon-training-data/manifest.json)
- 원본4파일 합계 **131,243,573,620 bytes (약131.24 GB)**. CLI metadata와 보관 manifest는 제외한다.
- README·라이선스 선언·dataset card·정답 행 수 통계·train/test 분할 설명은 없다.

| JSONL 상대 경로 | 원본 bytes | 실측 물리 행 수 | 첫32행 표본 필드 |
|---|---:|---:|---|
| `stage1a/stage_1a.jsonl` | 129,097,783,886 | 123,740,223 | prompt, response, opponent_action, reward, done, turn, format |
| `stage2a/stage_2a_reasoning.jsonl` | 1,547,316,444 | 500,000 | stage1a와 같은7필드 + outcome, reasoning, response_with_reasoning |
| `stage2b/counterfactual_actions.jsonl` | 598,470,628 | 1,000,000 | format, game_id, turn, prompt, response, action_idx, rating, source |

나머지 원본은 `.gitattributes`(2,662 bytes)다. JSONL 합계125,240,223행을 직접 집계했으며,
원격4파일의 목록·크기·해시 대조를 통과했다. 파일별 첫32행은 Python json으로 디코딩했다.
**stage2b 첫32행 모두 `rating: NaN`을 포함**한다. Python json 기본 모드는 허용하지만
표준 JSON 상수는 아니므로 엄격한 parser는 거부할 수 있다. 원본 bytes는 수정하지 않았고
manifest에 표본 검사 결과와 `passed_with_source_format_note` 상태를 남겼다.
전체 행의 JSON 구문·내용·보상 의미는 검증하지 않았다.

6.2절의 `pokechamp-pretrain-data`와 파일명이 일부 같아도 동일 파일로 취급하지 않는다.
이 보관본의 stage1a는 크기·행 수가 다르며 두 자료의 포함 관계·중복은 확인하지 않았다.
학습 사용 조건·분할·오염 통제는 위6절의 설계/EX 안내를 따른다.

<a id="generated-ruleqa"></a>

### 6.4 생성한 Showdown 규칙 Q&A v1

[EP-169](exec-plans/completed/EP-169-showdown-ruleqa.md)에서 새 CPU Gen9 장면으로 만든 영어 규칙 자료다.
기존 replay/EX 입력은 학습에 넣지 않았다. 총5,760문항이며 train4,608 / validation576 / test576이다.
기반1,920상황의 짧은 QA·전체 State QA·전체 State 선택형은 파생 표현이다. 두 export를 독립 표본으로 합산하지 않는다.

- [보관 폴더](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/showdown-ruleqa/v1/)
- [manifest](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/showdown-ruleqa/v1/manifest.json) · [한국어 검토 보고](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/showdown-ruleqa/v1/report.txt)
- [SFT messages](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/showdown-ruleqa/v1/exports/messages/) · [선택형](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/showdown-ruleqa/v1/exports/multiple_choice/)
- [입력/target 구분과 사용 예시](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/showdown-ruleqa/v1/README.txt) · [재생성 CLI](../integration/pokechamp/rule_qa/README.md)

State는 jev-ruleqa-state-v1이며 v6 관측·수치·후보를 보존하고 혼란 상태 설명만 별도 교정했다.
추천세트 피해 범위는 조건부 값이다. evidence/의 내부 세트·oracle·실패본을 모델 입력으로 사용하지 않는다.
전수 기계 검사와96상황 의미 검토, 두 tokenizer 무절단 검사를 통과했다. 자기1–2마리/상대1마리의
제어 장면이며 자연6대6 경기나 미지 템플릿의 독립 평가를 대신하지 않는다. EP169에서는 학습·모델 추론을 하지 않았다.
후속 [EX107](experiments/EX-107-tacit-ruleqa-lora.md)의 규칙QA 학습·오프라인 평가를 완료했고 실제 배틀은 별도 [EX108](experiments/EX-108-tacit-ruleqa-battle32.md)의32경기 탐색으로 완료했다.

<a id="archived-strategist-model"></a>

### 6.5 보관한 Pokémon Showdown Strategist 모델

`stevenkhan/pokemon-showdown-strategist`의 고정 revision
`f2726381423690cbe48f581c8027ce8b01012dae`를 [EP-171](exec-plans/completed/EP-171-strategist-model-archive.md)에서 보관했다.
[정보·검증 보고](exec-plans/evidence/ep171/report.md)에서 모델 카드와 실제 설정의 차이를 확인한다.

- 경로: `/mnt/digicap/combined/hyna/backup/pokechamp-research/models/stevenkhan/pokemon-showdown-strategist/`
- [폴더](/mnt/digicap/combined/hyna/backup/pokechamp-research/models/stevenkhan/pokemon-showdown-strategist/) · [manifest](/mnt/digicap/combined/hyna/backup/pokechamp-research/models/stevenkhan/pokemon-showdown-strategist/manifest.json)
- 원본11파일·92,248,228 bytes. `Qwen/Qwen3-0.6B`용 **LoRA 어댑터**이며 기반 가중치는 포함되지 않는다.
- 실제 어댑터 rank32/alpha16/dropout0.05, 28층·7모듈, FP32 tensor392개·20,185,088 parameter.
- 저장 학습 args는 max_length512·학습률0.0002·1epoch 설정이다. 공개 학습 스크립트의 모델/rank/길이와 달라 실제 사용 데이터 수·학습 완료·성능은 확정하지 않는다.
- 원격 파일 크기·해시 및 safetensors 헤더·rank/구조 검증 완료. 어댑터 README의 라이선스 표기는 불명확하다.
- 모델 실행·GPU·추론·학습·배틀은 수행하지 않았다. 기반 모델 결합과 실행기 연결은 별도 작업이다.

### 6.6 Smogon Gen9 OU 전략 수집본

[EP-175](exec-plans/completed/EP-175-smogon-ou-strategy-data.md)의 새 자료는
사용자 지정 `/workspace/data/smogon-dex/strategies/gen9ou-20261019/`에 있다.
[사용 안내](../data/smogon-dex/strategies/gen9ou-20261019/README.txt) ·
[manifest](../data/smogon-dex/strategies/gen9ou-20261019/manifest.json) ·
[검증 보고](exec-plans/evidence/ep175/report.md).

EP-174의110링크를 모두 보존하고 공유 폼 관계와 원문 빈 설명, 오래된 분석을 구분한다.
포켓몬별 전체 JSON/JSONL과 중복 없는 세트/전략 JSONL·Parquet, 원 HTML/JSON을 제공한다.
기존 raw/normalized의8월 보관본과 별도이며 학습 데이터 포함이나 새 평가 조건을 승인하지 않는다.

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
