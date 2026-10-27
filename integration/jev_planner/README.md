# GLM planner–JEV 실험 설정 환경

호출 시점과 프롬프트를 독립적으로 변경하는 전략 planner 실험 도구다.
기본 조합은 Z.ai `glm-5.3-flash`와 `autotrust/JEV-9B`, 계산기 포함 교정 v6 입력이다.
`planner.model`에 `glm-5.3`도 명시 선택할 수 있다. 추론 강도와 생성 옵션은 설정대로 전송하며
모델 사용 불가 시 자동 대체하지 않는다. 기존 기본 모델은 유지한다.
JEV-27B와 MiniCPM5-2B-Jev도 기존 고정 revision·formatter·자원 프로필로 선택한다.
계획은 전략 조언이며 최종 합법 행동은 JEV가 고른다.

이번 EP-145 검증은 CPU·모의 모델·로컬 Showdown 연결이다. 실제 API/GPU 성공이나 승률 효과를
검증한 결과가 아니다. 규범은 [D-139](../../project_context/research/planner-executor/decisions/D-139-jev-planner-environment.md)와
[C-070](../../project_context/research/planner-executor/CONTRACTS.md#c-070-jev-planner)이다.

후속 [EX-092](../../project_context/research/planner-executor/experiments/EX-092-planner-first-battle-sample.md)에서는
현재 역할guide·표시이름의 GLM/JEV-9B 실제1경기를55턴 승리로 정상종료하고 감사/뷰어·자원반환을
완료했다. [실제 샘플 뷰어](../../exports/battle_viewers/ex092/index.html).
단일 사례이며 다른 조합의 실행 성공이나 일반 성능 향상의 검증은 아니다.

## 바로 사용하기

모든 명령은 `/workspace`에서 실행한다. `preview/prepare`는 자격증명·모델 적재·API 호출이 없다.

```bash
scripts/jev-planner preview --config integration/jev_planner/examples/default.json --output /tmp/planner-preview.json
scripts/jev-planner prepare --config integration/jev_planner/examples/matrix.json --output .artifacts/jev-planner/demo-01 --mode mock
scripts/jev-planner run --directory .artifacts/jev-planner/demo-01 --mode mock
scripts/jev-planner compare --directories .artifacts/jev-planner/demo-01 --output .artifacts/jev-planner/demo-01-comparison.json
scripts/jev-planner export --directory .artifacts/jev-planner/demo-01 --output exports/battle_viewers/jev-planner-demo-01
```

`matrix.json`은 planner 없음1개와 나머지5정책×2프롬프트의 **11조건**을 만든다.
이 예제는 합성 저장 궤적을 재생한다. 실제 경기를 다른 정책으로 다시 진행한 성적이 아니다.
`default.json`은 기본 조합1조건이다. 기존 출력은 덮어쓰거나 이어서 실행하지 않으므로
반복할 때 `demo-02`처럼 새 경로를 쓴다. 비교·export 출력은 봉인된 run 폴더 밖에 둔다.

실제 로컬 Showdown에 모의 선택을 전송하려면 `examples/battle-mock.json`을 같은 명령에 사용한다.
아주 짧은 기술 검사용 두 팀으로 off/기본 정책 각각 진영교환2경기, 총4경기를 실행한다.
API/GPU 호출은 없으며 대전 성적은 연결 검증 결과로만 표시한다.

## 두 실험 축 바꾸기

설정 파일의 상대경로는 **그 설정 파일의 디렉터리**를 기준으로 해석한다.
다른 디렉터리로 복사하면 prompt·fixture·schedule 경로도 함께 맞추거나 절대경로를 사용한다.

```json
{
  "name": "strategy-test",
  "executor": {"model": "jev9b", "input_version": "jev-choice-v6", "candidate_display": "names-v1"},
  "trigger": {
    "policy": "events_or_periodic",
    "interval_turns": 3,
    "events": ["faint", "tera", "forced_switch"]
  },
  "prompts": {
    "planner": "../prompts/strategy-compact.txt",
    "executor": "../prompts/executor-guidance.txt",
    "guide": "../prompts/role-resource-guide-v1.txt"
  },
  "evaluation": {"kind": "trace", "fixture": "../fixtures/demo.json"}
}
```

| policy | 동작 |
|---|---|
| `off` | 선택한 입력 표현으로 JEV만 사용. 빈 planner 필드도 추가하지 않음 |
| `initial_only` | 최초 다후보 결정에서 한 번 |
| `every_decision` | 모든 다후보 선봉·일반턴·강제교체 결정 |
| `periodic` | 최초 및 마지막 성공 계획과 현재 턴 차이가 N 이상 |
| `events` | 최초 및 지정 사건이 새로 관측됨 |
| `events_or_periodic` | 사건 또는 주기, 겹치면 한 번 |

명시적 `trigger.events`에 `active_change`(양측 switch/drag/replace)와
`form_change`(출전 대상 detailschange/-formechange/-transform)를 추가할 수 있다.
벤치 폼 변화는 제외하며 공개행 좌표로 검출해 교체 후 원래 조합으로 돌아오는 사건도 보존한다.
기본 events 목록은 기존 세 사건을 유지한다. `events` 정책에서는 주기값을 사용하지 않는다.

기본 N=3이다. 선봉은0턴이고 사건으로 계획을 갱신해도 N의 기준이 바뀐다.
기절·실제 Tera는 공개 로그 사건이고 강제교체는 자기 요청 사건이다.
단일 후보는 두 모델 모두 무호출이며 사건은 다음 다후보 결정까지 보존한다.
같은 턴의 서로 다른 rqid는 별도 결정이다. 같은 요청 재전송은 모델·행동 전송을 중복하지 않는다.
경기마다 재사용되는 실제 Showdown 방 번호는 고유 슬롯별 논리 경기 ID와 분리한다.

`prompts/strategy-compact.txt`는 간결한 우선순위, `strategy-conditional.txt`는 관측 가능한
조건에 따른 전략 변경을 강조한다. 같은 관측·출력 형식을 사용한다.
`prompts/role-resource-guide-v1.txt`는 양측 역할/승리 경로·보존/소모·교환·자원·전환을 다루는
새 기본 공통 안내다. `prompts.guide` 경로를 바꿔 독립적으로 편집·동결할 수 있다.
상대의 역할 가능성을 확정된 실제 세트로 취급하지 않으며 계산값은 전략 가능성의 보조 근거다.
자세한 구조와 참고 문헌은 [거시 전략 안내](../../docs/pokechamp-planner-macro-strategy.md)에 있다.
`executor-guidance.txt`는 기존 JEV 지시문 뒤에 붙는 연결 지침이다.
새 기본 지침은 목표의 현재 충족 여부를 확인하고, 충족 조건이 유지되는 동안 불필요한 반복을
피하며, 유효한 미완료 목표를 진전시키도록 한다. 조건 변화 시 재평가하고 위협·보존 우선순위를
유지한다. 이미 준비된 실행은 당시 동결 지시문을 사용한다.
이 파일도 바꿀 수 있지만 그 변경은 planner 프롬프트만의 비교와 구분된다.

새 기본 `executor.candidate_display=names-v1`은 후보 객체에 `display_name`을 추가한다.
예: `Lokix — U-turn`, `Lokix — U-turn · Terastallize`, `Switch to Pecharunt`, `Lead: Lokix`.
Planner와 JEV는 같은 표시 후보를 읽고 뷰어는 실제 전달된 표시명을 보여준다.
현재 명시 slot 참조로 이름을 찾으며 `move_2` 같은 ID·slot·move_ref·후보 순서·실행 명령은 유지한다.
표시명으로 명령을 해석하지 않으며 이름 근거가 없으면 Unknown을 표시한다.
`original` 또는 이 필드가 없는 과거 동결 설정은 원 입력을 유지한다.
planner on/off에도 같은 표현 조건을 적용하며, 표시 추가 전후는 입력 표현의 별도 실험 조건이다.

Planner 입력은 현재 v6 state·후보, 이전 계획, 마지막 계획 이후 현재 cutoff까지의 공개 사건이다.
새 system은 planner 지시문과 동결된 guide 원문을 합친다. guide 필드가 없는 과거 준비 설정만
당시 v6의 첫 행동 선택 문단을 제외한 관측·계산 안내 조립을 유지한다.
이전 계획의 reasoning은 다음 planner/JEV 입력에 넣지 않는다.
Planner 출력 형식은 다음과 같고, 빈 목록은 허용한다.

```json
{
  "objective": "Short strategic objective",
  "priorities": ["Current priority"],
  "preserve": [],
  "threats": [],
  "tera_policy": "When to preserve or spend Tera",
  "contingencies": [{"if": "Observable condition", "then": "Strategic response"}]
}
```

형식 위반·빈/잘린 응답은 재질의나 임의 보정 없이 해당 경기만 실패한다.
유효한 형식의 나쁜 전략은 기록하고 계속한다. 후보·명령은 계획 때문에 추가·삭제·재정렬하지 않는다.
계획 생성 턴·경과 턴을 JEV에 전달하며 현재 관측이 이전 계획보다 우선한다.

`matrix.triggers`와 `matrix.planner_prompts` 목록을 조합하면 코드를 수정하지 않고 비교 조건을 만든다.
각 planner_prompts 항목에 `guide` 경로도 지정할 수 있다. 같은 front prompt라도 guide가 다르면
별도 조건이며, 둘의 본문을 합쳐 planner 프롬프트 차이로 센다. 예시는 다음과 같다.

```json
"planner_prompts": [
  {"name": "roles-v1", "path": "../prompts/strategy-compact.txt", "guide": "../prompts/role-resource-guide-v1.txt"},
  {"name": "custom", "path": "../prompts/strategy-compact.txt", "guide": "./my-guide.txt"}
]
```

단일 축 효과를 보려면 다른 축·모델·관측·일정·생성 옵션을 고정한다.
비교기는 여러 축 변경·실행 종류/모델/일정 차이를 표시하고 그런 조건에 대응 효과를 붙이지 않는다.

## 저장 관측과 실제 실행

trace fixture는 `schema_version: jev-planner-fixture-v1`과 `cases` 배열이다. 각 사례는
`battle`, `actor`, `rqid`, `payload`, `commands`, `prefix`, `boundary`를 포함한다.
`payload`는 v6 입력, `prefix`는 해당 actor가 실제 수신한 protocol과 event_seq,
`boundary`는 `protocol_event_seq/line_index`다. 비공개 요청·채팅은 planner 공개 사건에서 제외하며
미해소 split·잘못된 actor·관측/턴 불일치는 거부한다. `preview --case 2`로 특정 입력을 볼 수 있다.
호출 타이밍과 실제 적용된 계획 이력은 모의 run 뷰어에서 확인한다.

모델 선택 값은 `jev9b`, `jev27b`, `minicpm5-jev`, `jev35b-nvfp4`다.
D-148/EX-095의 새 NVFP4 경로·전용환경·공식 서버·8회 gate는 [전용 안내](../jev35b_nvfp4/README.md)를 따른다. 양자화·학습·가중치 다운로드·임의 GPU 배치는
이 도구의 설정 축이 아니다. 기존 모델 환경·가중치 경로가 필요하다.
실제 전송 입력 전체의32768토큰 한도를 지키며 초과 입력을 자동으로 자르지 않는다.
대표 요청 JSON 배열은 기존 모델 환경으로 CPU 길이를 확인할 수 있다.

```bash
CUDA_VISIBLE_DEVICES='' PYTHONPATH=/workspace .pokechamp-data/jev27b-runtime/.venv/bin/python -B -m integration.jev_planner.tokens --model jev9b --requests /absolute/path/requests.json
```

`live`는 후속 승인·등록할 새 EX에서만 실행한다. 저장 trace를 live로 표시하는 것은 거부한다.
필수 설정은 다음과 같다.

- `evaluation.kind=battle`, `schedule` JSON 경로, `experiment_record`의 등록된 새 EX 문서 경로.
- 일정 파일의 `schedule` 행은 `slot_id`, **그룹 ID인** `paired_slot_id`, `jev_actor`,
  두 `teams` 키, `battle_seed`, 두 `actor_seeds`를 가진다. `teams`는 키→`showdown_team` 객체다.
  모의 일정 파일은 형식 예제이며 실제 평가 모집단으로 자동 채택하지 않는다.
- `evaluation.limits`의 `planner_http_attempts`, `executor_calls`, `games`, `battle_seconds`,
  `total_seconds`를 모두 명시한다. 호출·전체 시계·경기 한도는 조건 행렬 전체에서 공유한다.
- `evaluation.resources`는 선택한 모델의 기존 고정 `gpu_indices`, `allocator_bytes`,
  `gpu_bytes`, `host_bytes`, `disk_bytes`와 일치해야 한다. 두 JEV는GPU0–3,
  MiniCPM은GPU0; allocator40GiB/GPU44GiB/host32GiB, 새 planner 실행의 disk_bytes는 세 모델 모두null(용량 상한 없음)이다.
- `showdown_port`는8100–8109(기본8109), `server_port` 기본18845다. 사용 중 자원을 빼앗지 않는다.

Z.ai는 기존 process 환경과 private `.env`의 `ZAI_API_KEY/ZAI_BASE_URL`을 사용한다.
키를 JSON 설정·프롬프트에 넣지 않는다. 생성 기본값은 enabled/low·temperature0·top_p0.95·
max_tokens8192이며 `planner`에서 바꾼다. 연결/timeout/5xx/429는 기존1/2/4초 최대3재시도,
최종429·공유 기술 결함·상한 도달은 신규 수집을 중단한다. JEV 로컬 재전송은 같은 요청 ID와
본문을 유지하고 영속 원장으로 중복 추론을 막는다.

## 기록·비교·완료

준비본은 config·prompt 원문과 코드 snapshot을 보존한다. 원 prompt 파일을 수정해도 이미 준비한
실행의 본문은 바뀌지 않는다. 실행 코드가 달라졌다면 새 출력으로 prepare한다.
결정별 실제 planner 메시지/응답/reasoning, 적용된 계획, JEV 입력/응답/선택과 명령,
호출 이유·계획 나이·HTTP 시도·usage·지연을 저장한다. 누락 usage는 미확인이며0으로 보정하지 않는다.

사용할 수 없는 모델 응답은 경기별 실패, 기술 오류는 의존 수집 중단으로 구분한다.
시도한 경기·실패·미실행 분모를 남기며 예산/프로세스 중단 뒤 자동 재개하지 않는다.
정상·실패 종료 기록이 끝난 run을 봉인하고 비교와 export는 그 자료만 읽는다.
원문과 결과를 확인하는 HTML/JS는 오프라인으로 열 수 있으며 폴더를 옮겨도 동작한다.
실제 배틀 연구의 완료에는 새 EX에 정한 검증·해석과 C-047의 정해진 뷰어 경로/목록 등록을 적용한다.


## 탭·리플레이 통합 화면

D-144/EP-150부터 새 `export --directory <봉인 run> --output <새 폴더>`의 경기 화면은
GLM 계획을 기본으로 JEV 요청·응답, 상태·후보, 턴 로그, Damage-calc, 기술 기록의7탭을 제공한다.
계획의6필드와 생성/경과턴·호출 사유, 선택 행동·일반/강제교체·호출/재사용 상태를 확인한다.
재사용 계획의 생성 결정으로 이동하거나 그 결정의 GLM 요청/응답/reasoning을 열어 복사·다운로드한다.

경기·턴·결정 선택과 이전/다음 버튼을 사용한다. 폼·탭 밖 좌우 방향키는 이전/다음 결정,
탭 안 좌우/Home/End는 탭을 탐색한다. 턴·결정을 선택하면 리플레이를 일시정지하고 해당 턴
시작으로 이동한다. 같은턴 일반/강제교체도 같은 위치이며 각 정보는 실제 결정 기록이다.
리플레이 재생/수동이동과 탭 전환은 정보 선택을 유지한다. `선택한 턴으로 이동`으로 다시 맞춘다.
결정 없는 턴도 공개 사건을 볼 수 있다. `선택한 결정 전까지`는 원래 수신 행 cutoff를 적용한다.

넓은 화면은 정보 왼쪽·스크롤 중 유지되는 리플레이 오른쪽, 좁은 화면은 세로 배치다.
애니메이션은 공식 Showdown 외부 자산을 사용하며 로딩 실패 시 로컬 공개 로그가 표시된다.
정보 탭·원문·피해 계산은 네트워크 없이 동작한다. 큰 결정 원문과 피해 시나리오는 상대경로의
로컬 JS로 지연 적재하므로 HTML만 복사하지 말고 내보낸 폴더 전체를 이동한다.
Damage-calc는 방향/기술/테라/가정 세트 필터·50개 단위 탐색·시나리오 상세/다운로드를 제공한다.
미제공·미계산·0피해를 구별하며 observation 감사 해시와 표시명/계획 추가 전 입력을 검증한다.
계산을 다시 실행하지 않는다. `provenance.json`에 원자료/복사본·renderer·고정 로그 parser 출처를 남긴다.
기존 EX-088/092 뷰어·원자료·봉인은 변경하지 않는다.


## GLM 출력 재시도 (과거 구문 전용 정책)

D-146 당시 설정의 `planner.json_retries`는0–5(기본5)다. GLM content의 JSON 구문 오류에
같은 관측·메시지·옵션으로 최초+추가5회(최대6회) 생성한다. 유효 응답이면 즉시 멈추며
JSON은 정상이지만 계획 필드가 잘못된 경우·중복키·응답 envelope 오류는 재시도하지 않는다.
HTTP 전송 재시도는 각 생성 안에서 기존1/2/4초 최대3회 정책을 유지한다. 모든 물리HTTP를
전체 호출·시간 한도 안에서 센다. 사용불가 응답을 임의 교정하거나 이전 계획으로 대체하지 않는다.
과거 동결 설정에서 필드가 없으면0으로 읽는다. 새 준비본에서만 기본값이 적용된다.
`planner_output_attempt`/`planner_json_retry` 원문과 usage·생성차수/누적HTTP를 보존하고
GLM/기술 탭에서 확인한다. 최종 유효 계획만 JEV에 전달한다.


## 디스크 사용량 정책

D-147부터 새 GLM/JEV 설정의 `evaluation.resources.disk_bytes`는 `null`이다.
디스크 사용량 때문에 prepare/run을 거부하거나100GiB 초과로 중단하지 않는다.
사용량/출력 경로·실제 공간 부족과 파일 I/O 오류는 계속 기록·처리한다. 별도의 여유 공간
예산이나 임시복사 상한을 수동으로 추가하지 않는다.
`model_spec().runtime_name`은 디스크 상한 없는 `planner-*` 자원 profile,
`model_runtime_name`은 기존 배치·수치를 유지하는 모델 적재 profile이다.
부모·모델 서버·추가 ResourceMonitor 모두 자원용 runtime_name을 사용한다.
예전 실행의100GiB 설정·봉인·실험 전용 profile은 보존하며 새 준비 설정은null을 명시한다.

D-150부터 새 기본 `temperature=0`, `retry_scope=response_format`이다. 모든 출력 형식 오류
(스키마·추가/누락 필드·중복키/비유한값·빈/잘린 응답·성공HTTP envelope 포함)를 같은 메시지와
옵션으로 최초+최대5회 재생성한다. `json_retries`는 형식/구문 전체의 단일 추가생성 상한이다.
전략 판단은 재시도하지 않으며 통신 재시도는 기존 정책을 유지한다. 과거 동결 설정의
`retry_scope` 부재는 `json_syntax`, 명시 temperature는 원값을 유지한다.
`planner_format_retry`와 기존 `planner_json_retry`를 구별해 원문/usage/오류/HTTP 예산을 기록한다.

출력 생성 차수의 저장 필드 `json_attempt`/`json_attempts`는 호환성을 위해 이름을 유지한다.
전체 형식 정책에서는 구문 외 형식 오류로 재생성한 차수도 포함하며 `retry_scope`,
`format_valid`/`format_error`와 두 retry 이벤트로 실제 사유를 구별한다.

D-152부터 `evaluation.limits.battle_seconds`와 `total_seconds`는 명시적 `null`을 지원한다.
이 경우 경기/전체 경과시간으로 종료하지 않으며, 양쪽 actor의 deadline과 상대 watchdog에
동일하게 적용한다. config와 request에는 `null`을 저장하고 내부 비교에만 무한대를 사용한다.
경과시간은 계속 기록한다. 기존 유한 기본값과 GLM/JEV 호출·메모리 한도, 개별 HTTP timeout/
재시도·사용자 취소·자식/서버 실패 감시는 유지한다. EX-099는 `max_tokens=131072`와 함께
명시하며 공용 기본 출력8192/시간 한도는 바꾸지 않는다.
