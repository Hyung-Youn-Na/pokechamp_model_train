# D-019 / D-022 / D-035 개선 IO

## 기본 IO 테스트의 설명 오류 기입

별도 사용자 지시가 없으면 기본 IO 알고리즘 테스트에 설명 오류 사후 검토·annotation 기입을
추가하지 않는다. 설명 정확성 평가를 명시적으로 요청한 경우에만 해당 범위에서 수행한다.
IO 기술 검사와 응답/reasoning 기록·표시는 유지하며, 미평가는 오류0이나 검토 통과를 뜻하지 않는다.
새 기본 테스트는 설명 미검토만으로 완료를 막지 않는다. 기존 오류 기록·viewer·Blocked 및
아래 과거 실험별 명시 gate는 보존한다. [규범 기본값](../../../project_context/RESEARCH_DESIGN.md#io-explanation-review).

현재 새 요약 없는 B 선택은 `battle-v1.2.0` / `calculator-input-v2`다. `lifecycle.py`의 전체 공개
prefix 이력, 단일 교대/테라 phase, 명시 hit/위력 branch, state/request/bundle 검증을 사용한다.
설치 파일을 바꾸지 않는 `mechanics-v2` overlay와 독립 검증은
[EX-030 보고서](../../../project_context/exec-plans/evidence/ep023/report.md)를 따른다.
과거 prompt/실험 정책 선택과 모든 기존 중단은 보존한다. 유료 재실험은 수행하지 않았다.

요약 경로의 최근 재실험은 [EX-024](../../../project_context/experiments/EX-024-low-summary-prompt-reexperiment.md)이며 현재 중단 상태다.
과거 중단 근거는 [EX-020](../../../project_context/experiments/EX-020-resume-io.md),
현재 실행 범위는 [EP-011](../../../project_context/exec-plans/active/EP-011-improved-io.md)를 따른다.
EX-020은 Cloud 요약의 사실 오류로 중단했다. 오프라인/로컬 통과는 Cloud 운용 자격이나
48판 비교 완료를 뜻하지 않는다. 과거 EX-017/018/019와 실패 receipt는 보존한다.

새 실험 등록 전 [테스트·평가 도구 결함 복구 절차](../README.md#defect-recovery)와
[실행기 지원 한계](../README.md#recovery-runtime-limits)를 확인한다. D-029는 기존 실험에
소급 적용하지 않으며 아래 재개·버전 전환 안내는 D-022/D-027의 당시 범위다.
EX-024의 전체 halt·시계·버전 한도와 EP-011 `Blocked`는 유지한다.

- `state.py`: 최신 자기 request·자기 세트와 상대 공개 정보/고정 prior를 분리한다.
  Pinned parser가 생략한 공개 기술과 자기 귀속 회복 특성은 수신 protocol에서 보완한다.
- `calculator.py`, `calculator/`: actor 소유 Node,0.11.0+ruination-v1, 설치·응답 identity 검증.
- `calculations.py`: 조건부 피해, 정확한 자기HP·랭크, 공개 활성 stat/기절 수를 전달한다.
  Future Sight 예약 피해와 양측 기절 후 미상 교체 대상을 즉시 피해와 구별한다.
- `player.py`, `backend.py`, `memory.py`: fixed 출력과 배틀 내10행동/3요약 cadence·identity.
- `offline.py`, `semantics.py`, `posthoc.py`: 기존15장면 구조·의미와 별도 사후3건 대조.
  `posthoc.py`만 검토용 상대 정답 세트를 읽는다. 사후 정보를 행동 입력으로 반환하지 않는다.
- `receipts.py`: source/archive/output/선행 receipt 검증, 최초 Cloud 시계와 영속 중단 기록.
- `study.py`, `cloud_gate.py`: fake12→Cloud 요청/별도 의미 검토→smoke12→예산 내48판.
  Cloud worker는 IPC 반환 전에 응답을 봉인하며 SIGINT/SIGTERM은 신규 작업을 막고 진행 중
  응답을 수집한다. `STOP` 파일로도 같은 요청 중지를 지정할 수 있다.
- `memory_fixture.py`: 실제 FixedPlayer·계산기 경로의 독립31행동 fixture(요약3·통합1).
  추가 배틀/승률 표본이 아니며 fake12의 격리·정리 검증을 보조한다.

설치와 회귀:

```sh
npm ci --prefix integration/pokechamp/improved_io/calculator --ignore-scripts
npm run patch:calc --prefix integration/pokechamp/improved_io/calculator
cd pokechamp
PYTHONPATH=/workspace .venv/bin/python -m pytest /workspace/integration/pokechamp/tests -q
```

오프라인은 `python -m integration.pokechamp.improved_io.offline --battle-root ... --evidence ...
--output ...`으로 새 디렉터리에 실행한다. 단계 실행기는 `python -m
integration.pokechamp.improved_io.study --help`를 따른다. `cloud_gate`의 구조·HTTP 통과만으로
다음 단계에 들어가지 않는다. 각 원응답의 사실·시점·identity 및 rubric 검토를 봉인한
`finish_cloud`가 필요하다. `halt.json`이 있는 연구는 새 디렉터리로 Cloud gate를 재질문하거나
예산을 초기화할 수 없다. 과거 gate를 수정하거나 중단 자료와 새 source 결과를 합치지 않는다.

프롬프트와 고정 prior의 출처는 `prompts/provenance.json`, `prior.json`에 보존한다.
프롬프트·전략·prior/패키지 버전은 EX-020에서 변경하지 않았다.

D-027은 원본 자산을 보존하고 `prompts/v1.1.0/`부터 최대3개 요약 지시 버전을 허용한다.
`study --summary-prompt-version v1.1.0`은 execution evidence와 실제 actor/Cloud의
같은 버전·해시를 고정한다. 필드가 없는 기존 실행은 v1.0.0이다.
`python -m integration.pokechamp.improved_io.review_gate prepare|collect|review|status|finish`
경로가 C요약8→별도요약48→행동180을 담당한다. `collect`는 검토할 응답을 봉인하고
반환한다. 원자료에 근거한 `review --audit` 통과 후 다시 collect하면 선행 요약을 재호출하지
않고 다음 경계를 실행한다. 독립 criteria의 모든 필수 사실 verdict와 응답 인용이 필요하다.
오류는 버전 halt, provider/환경/무결성 및 행동 오류는 전체 halt다. 최대3개 dispatch 기록이
하나의 최초 Cloud 시계를 해시로 고정한다. 기존 collect 경로로 이 gate를 대신하지 않는다.

## D-030 요약 없는 A/B 실행

`python -m integration.pokechamp.improved_io.battle_only`의 새 `io-battle-only-v1`은
A upstream과 B fixed 행동만 실행한다. 기존 A/B/C receipt와 요약 실험은 별도 보존한다.
B에는 요약 prompt 선택·품질 gate·요약 cadence가 없으며 역할/입력/actor archive를 검사한다.
모델/행동 prompt/prior/계산기 버전은 D-030에서 유지한다.

명령 순서는 `prepare --output PREP`, `fake32 --prepared PREP/result.json --previous PREP/result.json
--output LOCAL`, `register --prepared PREP/result.json --study-root STUDY`,
`collect --prepared PREP/result.json --previous LOCAL/result.json --study-root STUDY --output GATE`,
`review --study-root STUDY --output GATE --review REVIEW.json`, `smoke8`, `compare32`다.
배틀 명령에는 `--prepared`, `--previous`, `--output`, `--study-root`와 새 `--experiment-id`를 준다.
`--root`는 actor/benchmark data root이며 기본 `.pokechamp-data`다. 등록은 시계를 시작하지 않는다.

준비는 전체 공개 prefix로 현재 상태를 만들고 최근10결정 raw window만 행동 입력에 넣는다.
별도 원문·실제 입력 도달성 검사/평가 기준·15장면/사후3·prompt/prior/계산/source를 봉인한다.
Cloud gate는 B 행동90, 실제 요청 동시성1/10×3반복이며 기술 gate와 명시적 의미 검토가 모두
필요하다. 검토는 collection hash·각 response hash·facts/identity/timing/calculation/action_contract
boolean 및 구체적인 원문/실제 입력/계산 근거 문자열을 포함한다. 짧은 설명에 모든 사실 나열을
요구하거나 최적 행동을 정답으로 만들지 않는다.

Study의 요청 원장은 A 내부 추가 호출을 포함해 모든 HTTP 직전에 예약하며 응답은 worker가
검증/IPC 전에 선봉인한다. 실패·미확정은 차감하지 않는다. 최초4시간/신규3시간45분·4000호출,
배틀/계정/모델10 및 retry0이다. `report --study-root STUDY --output REPORT`는 gate/smoke/main과
복구의 분모를 분리한다. 배틀 B 설명은 `--review`로 원자료 해시/개별 claim 근거에 연결한다.
설명상 사실 오류가 있는 합법 완료는 승패 표본으로 유지한다. 자원 정리는 별도 검증한다.

`recover --study-root STUDY --prepared NEW_PREP/result.json --defect DEFECT.json`은 D-029의
독립 재현·관련 회귀·전후 source·영향 입증 기록을 검증한다. 평가/rubric 교정은 수집 없이
대칭 수정 분석 기록을 만들며 rubric은 사후 변경 공개가 필수다. 실제 수집 결함은 기존 c0 halt를
보존하고 최대1차 c1을 등록한다. `--cohort c1`은 같은 시계와 누적4000/180/16/64 상한을 쓴다.
재수집 목록은 영향 A/B 양쪽을 포함해야 한다. 수정 source에는 새 준비/로컬/Cloud 선행 gate가
필요하며 과거 gate의 source 불일치를 무시하지 않는다. 지원되는 단계 체인과 영향 범위 안에서만
실행하고, 과거 halt 삭제·receipt 덮어쓰기·원본 결과 수정으로 복구하지 않는다.

복구 record의 `impact`는 실제 무효화 단위이고 `recollect`는 c1 제출 단위다. Source 수정으로
온전했던 선행 gate를 다시 자격 검증해야 하면 `requalification`에 gate90/smoke8의 단위와
`requalification_reason`을 별도로 기록한다. 이는 이전 통과 gate에만 허용하며 모델 실패 gate나
본 비교를 단순 재자격으로 재수집할 수 없다. 무효와 선행 자격 교체를 분리하고 총180/16/64
상한을 적용한다. 이전 smoke의 합법 완료는 보존하되 본 비교나 반복 표본으로 합산하지 않는다.

평가 구현만 교정한 뒤 기존 gate의 미실행 요청을 이어 수집할 때는 `resume_unexecuted=true`와
기존 `collection`/`inputs` 참조를 포함한 evaluation record를 `recover`에 제공한다. `e1` 경로는
모든 기존 응답을 대칭 재평가하고, 원래15입력·prompt·prior·계산·rubric 동등성을 검사한다.
계산기 소요시간 차이는 동등성 검사에서만 제외하며 실제 wire에는 최초 봉인 값을 그대로 쓴다.
미확정이 있으면 이 경로는 거부된다. 기존 응답/trace/halt는 불변이고 원본 참조가 있는 새 판정만
생성한다. `collect --cohort e1`은 아직 제출하지 않은 ID만 수집하며 최초 시계/4000·단계 상한을
공유한다. 이미 받은 응답은 재호출하지 않으므로 유료 재수집 차수를 소비하지 않는다.
EX-026의 첫 응답에서 발견한 English 범위 대시의 ASCII 오거부가 이 평가 교정의 사례다.
구형 A/B/C의 ASCII 검증 동작은 보존하고 새 profile의 영문 문장 검사만 typographic 대시/따옴표를
허용한다. 원문 응답과 정확한 행동 JSON을 변환하거나 불법 후보를 허용하지 않는다.

## D-031 B 행동 필드 설명서

새 battle-only `prepare`는 `--battle-prompt-version v1.1.0`을 기본으로 선택한다.
`--battle-prompt-version v1.0.0`은 기존 `battle_fixed.txt` 원문이다. 버전이 없는 과거
설정도 v1.0.0으로 읽으며 A와 요약 실험의 선택은 유지한다.

`battle_prompts.py`는 단일 `prompts/battle-v1.1.0/fields.json`을 영문 설명서로 렌더링하고
기존 정책 뒤에 한 번 결합한다. 준비·worker·actor가 같은 함수를 사용하며 최종 backend도
system/user 실제 전달값을 대조한다. 설명되지 않은 JSON 경로·동적 키·중첩 request JSON과
자료형은 요청 전에 거부하며 입력을 제거하지 않는다. v1.1.0의 명시적 선택에는 identity가
필요하다. 설명서/원본 정책/완성 prompt hash를 manifest·execution·요청 trace에 연결한다.

준비의 `battle-prompt.json`은 전체 system 문자열·15입력별 문자/UTF-8 byte 크기를 봉인한다.
설명 범위와 pinned 근거는 [필드 설명서 구현 기록](../../../docs/pokechamp-battle-field-guide.md)을
참조한다. D-031은 로컬 구현·검증만 승인하며 EX-026의 halt/clock/Blocked를 재개하지 않는다.
