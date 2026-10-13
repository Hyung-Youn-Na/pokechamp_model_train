# 연구선 작업·출력·복원 안내

현재 checkout에서 시작할 순서는 [브랜치별 연구 매뉴얼](RESEARCH_MANUAL.md)을 따른다.
이 문서는 두 연구선의 공통 경로·Git 연결·보존 시점·복원 방법을 안내하며, 실험 규범은
[INDEX](INDEX.md#workflow)와 해당 RD/CONTRACTS/EP/EX에 유지한다.

[D-131](decisions/D-131-research-branch-preservation.md)에 따라 연구 목적과 실행 위치를
분리한다. 원본 소스·실험·환경은 삭제하거나 이동하지 않는다. 분리 검증의 원문은
[EP-135](exec-plans/completed/EP-135-research-branch-preservation.md)다.

<a id="checkouts"></a>

## 브랜치와 작업 위치

| Git 이름 | 역할 | 위치 |
|---|---|---|
| `main` | 기존 기준 `e93a7b166b0c4b8721bd802d1e9d6731eecbffcf` 유지 | 주 개발 checkout으로 사용하지 않음 |
| `research/model-training` | 포켓몬 모델 학습·정책 개선·독립 평가 | `/workspace`, 기존 환경 유지 |
| `research/l1-l5-port` | AgenticSTS L1–L5 이식 연구 보존·후속 설계 | `/mnt/digicap/combined/hyna/backup/pokechamp-research/worktrees/l1-l5-port` |
| `snapshot/pre-split` | 두 연구선의 공통 소스 기준 커밋 | 보존 태그, 이후 이동하지 않음 |

브랜치들은 같은 실행 코드·submodule pin에서 출발한다. 프롬프트·JEV·학습·AgenticSTS
구성은 유지한다. 별도 L1–L5 worktree는 실제 Git checkout이며 `/workspace` 코드로 향하는
symlink가 아니다. 이 worktree에 실행용 가상환경·자격증명·GPU lock을 구성하지 않는다.
현재 실행 여부는 각 checkout의 [STATUS](STATUS.md#active-work)와 [plan 색인](exec-plans/INDEX.md)을
확인한다. 기존 Blocked/Paused plan과 EX의 당시 판정·동결 protocol은 유지하며, 연구선 분리는
재개 또는 실험 완료를 뜻하지 않는다.

<a id="remotes"></a>

## Git 원격과 작업 기록

2026-10-12 사용자의 후속 push 지시로 학습 브랜치를 게시했다. EP-135 당시의 “push 없음”은
그 분리 작업의 완료 기록이며 이후 승인된 push 이력을 소급해 덮어쓰지 않는다.

| 원격 | 대상 | 현재 역할 |
|---|---|---|
| `origin` | `https://github.com/AlayaLab/AgenticSTS.git` | 상속된 upstream; 로컬 `main`의 기존 연결 |
| `model-train` | `https://github.com/Hyung-Youn-Na/pokechamp_model_train.git` | `research/model-training`의 게시·추적 원격 |

연결 상태는 `git status --short --branch`와 `git branch -vv`로 확인한다. Git 원격 설정은
worktree들이 공유하지만 현재 L1–L5 브랜치는 별도 원격을 추적하지 않는다. 다른 branch·tag의
게시 범위는 원격 이름만으로 확대하지 않고 사용자 지시를 따른다.

새 [EP](exec-plans/TEMPLATE.md)·[EX](experiments/TEMPLATE.md)는 기준 연구선과 실제 branch,
commit/미커밋 변경, checkout·interpreter, 새 출력 위치, 원자료·보존 manifest를 구분해 기록한다.
기존 ID와 기록은 유지하고 새로운 번호 체계를 만들지 않는다. 같은 ID가 다른 연구선에 보일 때는
출처 branch·commit을 함께 확인하여 동일 실행이나 별도 실험이라고 임의로 판단하지 않는다.

<a id="preservation"></a>

## 보존 위치와 manifest

보존 루트는 `/mnt/digicap/combined/hyna/backup/pokechamp-research`다. 기존
`/mnt/digicap/combined/hyna/backup/pokechamp` 학습 자료 경로도 그대로 유지한다.

| 상대 위치 | 내용 |
|---|---|
| `snapshots/pre-split/fs/` | 원래 절대경로의 `/`를 제외한 구조로 보존한 소스·실험·모델·환경 사본 |
| `manifests/asset-roots.json` | 보존 roots, 외부 blob·환경·자격증명 제외 및 공개 fixture 예외 |
| `manifests/inventory.jsonl` | 복사 전 파일 종류·크기·mode·시각·원경로·symlink 대상 |
| `manifests/assets.jsonl` | 파일별 원경로↔보존 경로, 원본/사본 SHA-256, 복사 결과 |
| `manifests/exclusions.json` | 자격증명, Git 별도 보존, 파일로 복구할 수 없는 runtime endpoint의 명시적 제외 |
| `manifests/copy-verification.json` | 전수 파일 복사·해시 대조와 원본 목록/metadata 불변 검사 |
| `manifests/repositories.json`, `manifests/additional-repositories.json` | 별도 소스 저장소·worktree와 bundle/변경 기록의 전체 목록 |
| `manifests/git-receipt.json` | EP-135 완료 시점의 브랜치·태그·submodule·자산 manifest 해시·bundle/검증 연결 |
| `repositories/` | 주/별도 저장소 bundle, worktree별 index·staged/unstaged diff·미추적 파일 목록 |
| `repositories/workspace-final.bundle` | EP-135 완료 시점의 두 연구 브랜치·보존 태그·main을 포함한 bundle |
| `validation/` | CPU 전후 회귀, 보존 도구 표본, 링크·환경·Git·표본 복원 결과 |
| `runs/model-training/` | 이후 새로 승인된 학습 실험의 출력 위치 |

`snapshot/pre-split`, 위 snapshot·bundle·receipt는 분리 시점의 고정 보존 기록이다.
이후 README·매뉴얼·코드 커밋이나 원격 HEAD를 가리키도록 태그를 옮기거나 과거 receipt를
갱신하지 않는다. 후속 작업의 검증·게시 기록은 해당 EP 또는 별도 receipt에 남긴다.

예를 들어 `/workspace/.pokechamp-data/...`의 사본은
`snapshots/pre-split/fs/workspace/.pokechamp-data/...`다. `/ref`, `/tmp`, 모델 캐시,
외부 interpreter와 기존 학습 데이터도 같은 원경로 대응 규칙을 따른다.
모델 snapshot의 symlink뿐 아니라 실제 blob까지 보존한다. symlink 문자열과 기존 실험의
절대경로·봉인은 수정하지 않는다. 따라서 사본의 절대 symlink는 원위치를 참조할 수 있으며,
독립 복구 시에는 manifest의 원경로를 재구성해야 한다.

자산 manifest는 Git 커밋을 내포하지 않는다. 최종 Git 이름과 manifest SHA-256을 연결하는
receipt는 외부에 따로 둬 커밋 해시의 순환 참조를 피한다. 과거 봉인 오류가 있다면 당시 파일과
오류를 보존하며, 이번 바이트 복사 검증을 과거 실험의 유효성 재판정으로 해석하지 않는다.

Git에는 기존 추적 파일과 명시적으로 선택한 소스·테스트·설정·문서·작은 고정 입력을 둔다.
대형 exports·과거 evidence·replay corpus·환경·모델은 외부 사본으로 연결한다.
L1–L5 worktree의 무시된 evidence/exports/data와 `.tools/.../docs` 링크는 보존 자료 열람용이다.
그 링크를 통한 편집·출력 쓰기는 사본을 바꿀 수 있으므로 새 작업의 쓰기 경로로 사용하지 않는다.
환경 안내가 보이는 것은 실행용 가상환경이 설치되어 있다는 뜻이 아니다.
Git bundle만으로 대형 자산까지 복구되는 것은 아니다.

다음 외부 항목은 실행 코드가 읽는 고정 입력·참조 패키지도 포함한다. 출력물이라는 이유로
폐기하지 않으며 L1–L5 worktree에서도 보존용 링크로 원래 상대경로를 열람한다.

| 원래 상대경로 | 보존 대상 |
|---|---|
| `export/teams/` | 검토된 팀·종 목록 등 입력 파일 |
| `export/docs/` | 팀 pool RoleDB 등 고정 참조 |
| `exports/pokemon-role-data/` | 코드가 사용하는 역할 데이터 패키지 |
| `data/showdown-replays/` | 기존 replay corpus와 provenance |

각 경로의 사본은 `snapshots/pre-split/fs/workspace/` 아래 같은 상대경로다. 이 연결은 과거
평가 자료를 새로운 학습에 자동 편입하거나 사용 범위를 확대하는 승인이 아니다.

<a id="outputs"></a>

## 새 학습 출력

새 EX/plan에서 모델·데이터·분할·평가·예산·중단 조건을 확정한 뒤, 해당 실행기가 지원하는
명시적 출력 인자로 다음 경로를 선택한다. 이 경로 안내는 새 실험 실행 지시가 아니다.
명령별 지원 인자·쓰기/서버 호출 경계는 현재 checkout의 [연구 매뉴얼](RESEARCH_MANUAL.md)을 따른다.

```bash
# EX-NEW는 승인된 새 실험 ID로 바꾼다.
POKECHAMP_RUN_DIR='/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-NEW'
```

`scripts/pokechamp-fixed-matchup`의 경로 인자는 `--directory`다. 예를 들어 이미 준비된
승인 실행의 상태 열람 문법은 다음과 같다.

```bash
cd /workspace
PYTHONDONTWRITEBYTECODE=1 scripts/pokechamp-fixed-matchup status --directory "$POKECHAMP_RUN_DIR"
```

출력 폴더 이름만 바꿔 동결된 과거 protocol을 새 실험으로 재사용하지 않는다. 기존 실행기의
고정 출력 상수는 유지한다. 출력 위치를 선택할 수 없는 과거 실행기는 새 실험에 자동 재사용하지
않고, 후속 승인 범위에서 별도 경로 지원을 정한다. 정상 배틀 완료 시
[C-047](CONTRACTS.md#c-047-viewer-export)의 `/workspace/exports/battle_viewers/` 내보내기
요건도 유지한다. 새 run 경로는 그 완료 요건을 대체하지 않는다.

<a id="restore"></a>

## 복구 절차

아래는 별도 복구 작업을 위한 안내이며 현재 `/workspace`에 덮어쓰는 명령이 아니다.

1. 복원하려는 시점을 먼저 구분한다. EP-135 분리 상태를 복원할 때는
   `manifests/git-receipt.json`의 Git SHA와 파일 해시를 확인하고 당시 bundle을 검증한다.
   원래 `main`, 두 브랜치, 고정 태그, submodule pin을 receipt와 대조한다. 이후 학습 브랜치
   코드가 필요하면 승인된 원격/작업 기록의 commit을 별도로 확인하며 과거 receipt의 SHA를
   최신 HEAD의 값으로 바꾸지 않는다.
2. 충돌하지 않는 빈 경로에 `repositories/workspace-final.bundle`을 clone한다.
   `research/model-training` 또는 `research/l1-l5-port`를 checkout한다. submodule은
   `repositories/workspace__pokechamp/source.bundle`과
   `repositories/workspace__pokemon-showdown/source.bundle`의 지정 pin으로 복구한다.
   원래 remote URL은 `.gitmodules`에 보존되어 있으며 복구를 위해 원격 push할 필요가 없다.
3. `assets.jsonl`에서 필요한 자산의 `destination`과 `source`를 찾고 크기·SHA-256·mode·
   symlink 문자열을 대조한다. 다른 위치에서 조사할 때는 `snapshots/pre-split/fs/`를 읽는다.
   기존 실험을 원경로로 복구할 때에는 해당 `source` 경로가 비었는지 먼저 확인한 뒤 복사한다.
   기존 원본·봉인을 수정하거나 snapshot 내부 절대경로를 일괄 치환하지 않는다.
4. `repositories.json`과 `additional-repositories.json`의 전체 저장소 목록을 확인한다.
   `.tools`, `/ref/kev`, `.artifacts/ep055/client` 등은 해당 `state.json`의 커밋과 bundle로 복구하고,
   원래 worktree 경로를 재구성한다. staged/unstaged patch를 같은 커밋에 대조·적용하고
   `untracked.z`에 기록된 미추적 소스를 대응 snapshot에서 복사한다. 의존성 lock·설치 metadata와
   editable source·interpreter 경로도 복구한다. root `.git`를 통째 복사하지 않으므로 worktree의
   Git 연결은 원경로에 맞춰 다시 만든다.
   특히 공식 관측 build는 `.artifacts/ep055/client`의 Git HEAD도 읽으므로 파일 사본만으로
   해당 저장소의 Git identity가 복원됐다고 간주하지 않는다.
5. 가상환경은 바이트 보존본이다. shebang·editable `.pth`·interpreter symlink가 절대경로를
   포함하므로 새 위치에서 바로 실행 가능하다고 간주하지 않는다. 원경로와 OS/라이브러리
   조건을 확인하고, 이번 CPU 회귀와 환경 출처 검사를 복구 대상에 맞게 다시 수행한다.
   설치·upgrade나 실제 GPU/배틀 검증은 이 안내만으로 자동 수행하지 않는다.
6. 자격증명은 보존 패키지에 없다. 기존 `.env`와 Hugging Face 인증 파일은 원위치에 유지한다.
   공유·Git 추적·환경 복제에 포함하지 않는다. 복구 과정에서도 소유자의 별도 설정을 사용한다.

<a id="limitations"></a>

## 알려진 후속 항목

`integration/qwen_mcts/prepare.py`는 EP-132 문서를 `exec-plans/active/`에서 찾지만 실제
문서는 `completed/`에 있다. 이번에는 원 코드와 알려진 불일치를 보존한다. 코드 삭제·공통화,
이 경로 수정, 환경 재설치, 과거 실험 재개는 별도 후속 범위다.
