# laya 학습 자료 재생성 가이드 (다른 서버용)

이 문서는 다른 서버의 코딩 에이전트가 laya 학습 자료(`laya-compact-imitation/<버전>`)를 다시 만들고, 새 렌더러로 새 버전을 만들 수 있게 환경을 구성하는 절차다. 2026-10-30 기준이며 이 저장소의 `research/model-training` 브랜치를 전제로 한다.

- 범위: EX-071 파싱 결과에서 출발하는 **렌더러 단계 이후**(정보 캐시 → 재파싱 저장소 → 렌더링 → 학습)다. 리플레이 수집·선별과 EX-071 파싱 자체(0~1단계)는 다루지 않는다.
- 이미 학습에 쓴 자료를 쓰기만 할 때는 `laya-training-data-20261030.zip`으로 충분하다. 이 문서는 자료를 **새로 만들** 때 필요하다.

## 1. 준비물

| 준비물 | 출처 | 비고 |
|---|---|---|
| 이 저장소 | `Hyung-Youn-Na/pokechamp_model_train`, 브랜치 `research/model-training` | 코드·고정 json(dex, 가정 세트, 테라 규칙)·계산기 lock |
| `laya-regen-inputs-20261030.zip` (513 MB, 풀면 3.7 GB, 파일 2,786개) | 연구 서버 `/workspace/exports/` | EX-071 파싱 결과, 중간 저장소, 환경 고정 파일. 아래 2절 |
| `laya-training-data-20261030.zip` (선택) | 연구 서버 `/workspace/exports/` | 기존 학습 자료. 재생성 결과 대조, 서빙의 렌더러 대조, 테라 지식 재생성(`v2-all` 필요)에 쓴다 |
| laya 0.4.13 | `https://github.com/NandhaKishorM/laya`, commit `6f0496f797dc7127265d62e1543a62de507d943c` | 공개 |
| 시작 모델(토크나이저) | Hugging Face `convaiinnovations/laya-typed-decisions`, revision `e929ae5cf69bc34259cd2f95c9e91145b818b1f0` | 공개. 렌더링의 길이 검사와 학습에 쓴다 |
| Metamon | `https://github.com/UT-Austin-RPL/metamon`, commit `0a00a759c9a4382a2877088d828302ec294a05a5` | 공개. 재파싱 저장소를 새로 만들 때만 |
| node | v24.18.0 (연구 서버 값) | 피해 계산기 |

## 2. 재생성 입력 zip의 구성

zip 안 `laya-regen-inputs-20261030/`의 `workspace/`와 `shared/`는 코드가 기대하는 위치를 그대로 따른다. `MANIFEST.json`에 파일별 sha256이 있다.

| zip 경로 | 놓을 위치 | 내용 |
|---|---|---|
| `workspace/.pokechamp-data/experiments/ex071-qwen-replay-imitation/prepared/` | `$ROOT/` 아래 같은 경로 | EX-071 결정 스냅샷(train 130,411 / validation 512 / test 1,024행), `manifest.json` |
| `workspace/.../preparation/{replays.jsonl, replay-exclusions.jsonl, historical-teams.json, recovered/}` | 같은 경로 | 리플레이 목록, 제외 목록, 복원된 리플레이 2,711개(재파싱 입력) |
| `shared/datasets/generated/laya-compact-features/{v2,v5}/` | `$SHARED/` 아래 같은 경로 | 정보 캐시. v5는 v5·v6 렌더러, v2는 v2 렌더러와 테라 지식의 입력 |
| `shared/datasets/generated/laya-item-state/v1/` | 같은 경로 | 상대 아이템 상태·상태 카운터(D-195) |
| `shared/datasets/generated/laya-early-history/v1/` | 같은 경로 | 4턴 창 밖 과거 기록(D-198) |
| `env/laya/` | 참고용 | `requirements.txt`(EP-207 고정판), `pip-list-ep207.txt`, `POKEMON_ENVIRONMENT.md`(재설치 명령) |
| `env/metamon/` | `$ROOT/.tools/metamon-imitation/` | `bootstrap.sh`, `requirements.lock`, `provenance.json` |
| `env/model/...checksums.sha256` | `$SHARED/models/laya-typed-decisions/e929ae5c/checksums.sha256` | 시작 모델 파일 검증용 |

빠진 것: 정보 캐시 v3·v4(`v3`/`v4` 렌더러 전용, `laya-imitation v3|v4 features`로 다시 만듦), EX-071 `preparation/`의 나머지(`records.jsonl` 등 2 GB, 0~1단계 전용), 원본 리플레이.

## 3. 경로 맞추기

코드에 고정된 경로가 있다. 경로를 바꾸지 않고 **같은 경로를 만드는 쪽**을 권한다(심볼릭 링크로 충분).

| 고정 경로 | 정의 위치 | 기대하는 것 |
|---|---|---|
| `ROOT` = 저장소 루트 | `integration/laya_imitation/config.py` (`Path(__file__).parents[2]`) | 자동. 단, `scripts/laya-imitation`은 `/workspace`를 직접 쓴다 |
| `SHARED` = `/mnt/digicap/combined/hyna/backup/pokechamp-research` | 같은 파일 | 시작 모델, 생성 자료, 학습 실행 결과 |
| `/workspace/.tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python` | `scripts/laya-imitation` | laya env 인터프리터 |
| `$ROOT/.tools/metamon-imitation/{upstream,.venv}` | `item_state.py` (`METAMON`) | 재파싱 워커 |
| `$ROOT/.pokechamp-data/experiments/ex071-qwen-replay-imitation` | `config.py` (`EX071`) | EX-071 입력 |

```bash
# 예: 저장소를 /workspace에, 큰 자료를 /data/laya-shared에 둘 때
git clone -b research/model-training https://github.com/Hyung-Youn-Na/pokechamp_model_train.git /workspace
sudo mkdir -p /mnt/digicap/combined/hyna/backup
sudo ln -s /data/laya-shared /mnt/digicap/combined/hyna/backup/pokechamp-research
unzip laya-regen-inputs-20261030.zip -d /tmp/regen
cp -a /tmp/regen/laya-regen-inputs-20261030/workspace/. /workspace/
cp -a /tmp/regen/laya-regen-inputs-20261030/shared/. /mnt/digicap/combined/hyna/backup/pokechamp-research/
# MANIFEST.json의 sha256으로 전부 확인한다(아래 한 줄은 workspace/·shared/ 경로를 실제 위치로 바꿔 검사).
python3 - /tmp/regen/laya-regen-inputs-20261030 <<'EOF'
import hashlib, json, sys
from pathlib import Path
b = Path(sys.argv[1]); m = json.loads((b / 'MANIFEST.json').read_text())
base = {'workspace': Path(m['layout']['workspace']), 'shared': Path(m['layout']['shared'])}
bad = [k for k, h in m['files'].items() if k.split('/')[0] in base and
       hashlib.sha256((base[k.split('/')[0]] / k.split('/', 1)[1]).read_bytes()).hexdigest() != h]
print('mismatched', len(bad), bad[:5])
EOF
```

경로를 바꿔야 한다면 `config.py`의 `SHARED`와 `scripts/laya-imitation`의 인터프리터 경로를 함께 고치고, 그 변경을 별도 커밋으로 남긴다. 생성 자료의 `manifest.json`에는 만든 시점의 절대 경로가 기록되며, 코드는 경로가 아니라 sha256으로 입력을 대조한다.

## 4. 환경 구성

### 4.1 laya env (정보 캐시·렌더링·테라 지식·학습)

```bash
mkdir -p /workspace/.tools/laya-0.4.13
git clone https://github.com/NandhaKishorM/laya.git /workspace/.tools/laya-0.4.13/upstream
git -C /workspace/.tools/laya-0.4.13/upstream worktree add -b pokemon-training-env \
  ../worktrees/pokemon-training 6f0496f797dc7127265d62e1543a62de507d943c
cd /workspace/.tools/laya-0.4.13/worktrees/pokemon-training
uv venv --python 3.11 .venv --prompt laya-0413
uv pip install --python .venv/bin/python --index-url https://download.pytorch.org/whl/cu128 \
  --extra-index-url https://pypi.org/simple --index-strategy unsafe-best-match \
  -r <zip>/env/laya/requirements.txt -e .
cd /workspace && .tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python -c \
  "import laya, torch, transformers; print(laya.__file__, torch.__version__, transformers.__version__)"
```

- 기대값: laya가 worktree 안에서 import되고, torch `2.11.0+cu128`, transformers `5.0.0`.
- 자료 생성은 CPU만 쓴다. GPU는 학습·평가·서빙에만 필요하다.

### 4.2 시작 모델

```bash
M=/mnt/digicap/combined/hyna/backup/pokechamp-research/models/laya-typed-decisions/e929ae5c
/workspace/.tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/hf download convaiinnovations/laya-typed-decisions \
  --revision e929ae5cf69bc34259cd2f95c9e91145b818b1f0 --local-dir $M
cp <zip>/env/model/laya-typed-decisions-e929ae5c.checksums.sha256 $M/checksums.sha256
(cd $M && sha256sum -c checksums.sha256)
```

### 4.3 피해 계산기 (정보 캐시)

```bash
cd /workspace/integration/pokechamp/improved_io/calculator
npm ci --no-audit --no-fund && node patch.cjs   # @smogon/calc 0.11.0 + ruination-v1 패치
```

`integration/laya_imitation/calc.cjs`가 버전(0.11.0)과 패치 해시를 확인하고, 다르면 실패한다.

### 4.4 Metamon 파서 venv (재파싱 저장소를 새로 만들 때만)

```bash
mkdir -p /workspace/.tools/metamon-imitation
cp <zip>/env/metamon/{bootstrap.sh,requirements.lock,provenance.json} /workspace/.tools/metamon-imitation/
bash /workspace/.tools/metamon-imitation/bootstrap.sh   # python3.11 필요, CPU 전용
```

## 5. 동작 확인: 기존 자료를 똑같이 다시 만들기

새 렌더러 작업 전에 같은 입력에서 기존 자료가 바이트 단위로 같게 나오는지 확인한다. 생성 함수는 출력 위치에 `manifest.json`이 있으면 실패하므로(봉인 자료 보호), 출력만 임시 위치로 돌린다. 연구 서버에서 2026-10-30에 아래 두 검사를 실행한 결과는 5.3절에 있다.

### 5.1 렌더링 (`v6h-all`)

```bash
cd /workspace
export PYTHONPATH=/workspace PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE=1 CUDA_VISIBLE_DEVICES=
.tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python - /tmp/v6h-check <<'EOF'
import hashlib, sys
from pathlib import Path
from integration.laya_imitation import data_v6
out, stored = Path(sys.argv[1]), data_v6.VARIANTS['v6h']['out']
data_v6.VARIANTS['v6h']['out'] = out   # 봉인 자료 대신 임시 위치에 만든다
data_v6.build('v6h')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for f in ('train.jsonl', 'validation.jsonl', 'test.jsonl', 'exclusions.jsonl'):
    print(f, 'same' if sha(out / f) == sha(stored / f) else 'DIFFERENT')
EOF
```

대조 대상(`stored`)은 학습 자료 zip의 `datasets/laya-compact-imitation/v6h-all/`을 `$SHARED/datasets/generated/laya-compact-imitation/v6h-all/`에 놓은 것이다.

### 5.2 재파싱 (`laya-early-history/v1`)

```bash
.tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python - /tmp/early-check <<'EOF'
import hashlib, sys
from pathlib import Path
from integration.laya_imitation import config as c, early_history
out = Path(sys.argv[1]); early_history.reparse(out)   # 워커는 Metamon venv에서 돈다
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for f in ('train.jsonl', 'validation.jsonl', 'test.jsonl'):
    print(f, 'same' if sha(out / f) == sha(c.EARLY_HISTORY / f) else 'DIFFERENT')
EOF
```

### 5.3 연구 서버 확인 결과 (2026-10-30)

이 저장소 커밋 `624ad9e`의 코드, 재생성 입력 zip과 같은 파일로 실행했다. 임시 위치에 만들고 봉인 자료와 sha256을 비교했다.

| 검사 | 결과 | 시간 |
|---|---|---|
| 5.1 `v6h-all` 렌더링 | `train.jsonl`, `validation.jsonl`, `test.jsonl`, `exclusions.jsonl` 모두 바이트 동일. 행 수 130,327 / 512 / 1,023, 초과 제외 85행 | 185초(32 프로세스, 다른 작업과 동시) |
| 5.2 `early-history` 재파싱 | 3개 split 모두 바이트 동일. 131,947행 기존 필드 전부 같음(Life Orb 공개 허용 7,462행은 원래와 같은 기준) | 204초(24 워커) |

- 두 검사 모두 `PYTHONPATH`에 `/workspace`만 두고 실행했다. pokechamp 환경은 자료 생성에 필요 없다.
- `build`가 끝에 출력하는 `counts_match_source`의 train·test `false`는 길이 초과로 뺀 행(84행, 1행) 때문이며 원래 자료와 같다.

### 5.4 테스트

```bash
cd /workspace && PYTHONPATH=/workspace .tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python -m pytest -q \
  integration/laya_imitation/tests/test_compact_v2.py integration/laya_imitation/tests/test_compact_v5.py \
  integration/laya_imitation/tests/test_compact_v6.py
```

## 6. 단계별 명령 (연구 서버에서 쓴 것)

모두 `scripts/laya-imitation <명령>`이다. 출력 위치는 `config.py`에 고정돼 있고, 이미 있으면 실패한다.

| 단계 | 명령 | 입력 → 출력 | 연구 서버 CPU 시간 |
|---|---|---|---|
| 아이템 상태 재파싱 | `v5 reparse` | EX-071 + `recovered/` → `laya-item-state/v1` | 147초 |
| 정보 캐시 v5 | `v5 features` | EX-071 + item-state → `laya-compact-features/v5` | 75초 |
| v5 렌더링 | `v5 data` / `v5 parity` | 위 둘 → `laya-compact-imitation/v5-all` | 수 분 |
| 과거 기록 재파싱 | `v6 reparse` | EX-071 + `recovered/` → `laya-early-history/v1` | 198초 |
| v6 렌더링 | `v6 data --variant v6s|v6h` / `v6 parity --variant ...` | features v5 + item-state (+ early-history) → `v6s-all`/`v6h-all` | 223초(v6h) |
| v2 정보 캐시·렌더링 | `v2 features`, `v2 data` | EX-071 → `laya-compact-features/v2`, `v2-all` | 33초 + 5분 |
| 테라 지식 | `tera data` | features v2 + `v2-all` + `tera_rules.json` → `laya-tera-knowledge/v1` | 59초 |
| 학습 | `v6 train --variant v6h` 등 | 자료 + 시작 모델 → `$SHARED/runs/model-training/EX-142` | GPU, 수 시간 |

`parity`는 서빙에서 쓰는 실시간 렌더러로 validation 행을 다시 만들어 저장된 자료와 같은지 본다. 결과는 해당 학습 실행 폴더의 `diagnostics/parity.json`에 쓴다.

## 7. 새 렌더러 버전 추가하기

v6(D-198, 커밋 `f36fc09`)이 가장 최근 예다. 그 커밋의 파일 목록을 그대로 따라 하면 된다.

1. **렌더러** `integration/laya_imitation/compact_vN.py`: 이전 버전 렌더러를 감싸 모듈을 더한다(`MODULES`, `render`, `version`). 텍스트 형식은 테스트 케이스(`tests/dNNN_cases.json`, `tests/test_compact_vN.py`)로 고정한다.
2. **자료 생성** `data_vN.py`: `VARIANTS`(모듈, 토큰 한도, 출력, 학습 실행 위치), `_rows`(EX-071 + 저장소를 행 순서대로 합침), `measure`, `build`, `parity`, `GENERATOR`(자료에 복사할 생성 코드 목록). 분할·행 순서·라벨은 EX-071과 같게 유지하고, 길이 초과 행만 `exclusions.jsonl`로 뺀다.
3. **새 정보가 파서에 없을 때**: `integration/pokechamp/imitation/{schema,replay,metamon_bridge}.py`에 opt-in 필드를 더하고(기본값에서는 기존 출력이 바뀌지 않게), `early_history.py`처럼 재파싱 저장소 모듈을 만든다. 재파싱은 기존 스냅샷 필드가 전 행 같다는 `parity.json`을 남기고, 다르면 실패한다.
4. **경로·명령** `config.py`(새 자료·저장소·학습 실행 경로), `cli.py`(새 하위 명령과 단계).
5. **학습** `training.py`의 `Spec`(자료, 출력, head 512, 테라 지식 `extra_train`, `max_exclusion_rate=0.005`, 토큰 한도). 학습 설정은 기존 실험과 같게 두고 렌더러만 바꾼다.
6. **서빙·평가** `serving.py`(모델 이름, `VN_RENDER_FILES`, `_dataset`, 렌더러 함수: 서빙은 자료의 `generator-source/`와 현재 코드가 같은지 확인한다), `policy.py`(토큰 한도), `evaluation_vN.py`.
7. 자료를 만든 뒤 `parity`와 5절 같은 재생성 대조를 통과시키고, 기록(D·EP·EX)을 남긴다.

## 8. 지켜야 할 것

- 봉인된 자료(`checksums.sha256`이 있는 폴더)와 EX-071 파일을 고치거나 덮어쓰지 않는다. 바꿀 일이 있으면 새 버전 폴더를 만든다.
- 각 자료의 `manifest.json`은 입력 저장소의 manifest sha256(`source_manifest_sha256` 등)을 기록하고, 생성·학습 코드는 이 값을 대조한다. 입력 파일을 다시 쓰면 이후 단계가 모두 실패한다.
- 정보 캐시는 고정 계산기(0.11.0 + 패치)와 고정 dex json에 의존한다. 계산기나 dex를 바꾸면 새 정보 캐시 버전이다.
- 라벨은 사람의 선택이며 승률이 아니다. 상대 미공개 정보는 가정 세트(`assumed_sets_v2.json`)로 채운다.
