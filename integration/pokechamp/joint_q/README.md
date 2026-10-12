# EX-065 공동 q 데이터

고정 자기 팀 p2, reviewed108 상대20팀, 신규 Abyssal80경기(50/10/20)의 모든 관측·합법 후보를
32회씩 평가한다. 모델 호출·본학습·GPU·외부 API는 사용하지 않는다. 실행 조건은
[EX-065](../../../project_context/experiments/EX-065-joint-q-data.md), 진행은 EP-107이다.
사용자 후속 지시로 이번 뷰어는 생성하지 않는다.

## 실행

프로젝트 루트에서 다음 환경을 사용한다. 데이터 루트 기본값은
`.pokechamp-data/experiments/ex065-joint-q`다. 원경기80개의 실제 seed는 prepare가 저장하며
동일6종 그룹·개발 상대5종 중복·원문 해시·로컬 합법성 실패는 수집 전에 거부한다.

```bash
export PYTHONPATH=/workspace:/workspace/pokechamp
export PYTHONHASHSEED=20260929
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
PY=/workspace/pokechamp/.venv/bin/python
$PY -m integration.pokechamp.joint_q prepare
$PY -m integration.pokechamp.joint_q freeze
$PY -m integration.pokechamp.joint_q capture --cohort pilot
$PY -m integration.pokechamp.joint_q inputs --cohort pilot
$PY -m integration.pokechamp.joint_q register --cohort pilot
$PY -m integration.pokechamp.joint_q benchmark
$PY -m integration.pokechamp.joint_q collect --workers 32
$PY -m integration.pokechamp.joint_q export
$PY -m integration.pokechamp.joint_q tokens
$PY -m integration.pokechamp.joint_q audit
$PY -m integration.pokechamp.joint_q pilot-gate
```

필수 검증 원문과 source_id가 일치하는 verification.json 및 16/32/48 동일 실제 작업
benchmark·원장 완성·입력/토큰 감사 없이는 pilot-gate가 실패한다. 이후 같은 순서의
capture/inputs/register에서 `--cohort rest` (train40+validation10), 그다음 `--cohort test`
(test20)를 사용한다. worker는 gate 기록값을 적용한다. test를 설정/프롬프트 선택에 사용하지 않는다.

`collect`는 완료 작업을 다시 집계하지 않고 SQLite WAL 원장·원자적 결과 파일을 대조하여
미완료 작업만 이어간다. 복구 시 같은 논리 ID/seed와 마지막 완전한 결정 경계 checkpoint를
사용하며 기술 시도는 최대3회다. `STOP` 파일은 신규 실행과 진행 중 작업을 결정 경계에서
멈춘다. 오류를 해결/검증한 뒤 같은 버전의 기술 중단을 재개하려면 STOP을 제거하고 collect를
다시 호출한다. source/seed/root 손상·공유 의미 결함은 STOP을 지워 우회할 수 없다.
무결성 수정에는 새 소스 버전과 영향 관측 전체 후보×32 재수집 근거가 필요하다.
원경기 재현 실패를 다른 시드 경기로 대체하지 않는다.

## 저장 레코드와 모델 입력

- `manifest.json`: 자기/상대 원문·실제 제출 세트·분류 근거·그룹·split·80개 seed·정책 조건.
- `frozen-collection.json`, `frozen/`: 코드·정적 데이터·계산기·공식 관측·simulator의 보존 복사본/해시.
- `games/`: 원경기 전체 선택/공개 로그, 재현·모든 root 복원/다음 결정 경계 검증.
- `inputs.jsonl`: 관측 ID/split·모델 전용 JSON·명시 후보 순서·serializer 버전.
- `targets.jsonl`: 같은 ID의 독립 q 벡터·W/D/L/n·완성 여부·타깃 버전.
- `candidate-records.jsonl`: EX-061 형태의 input_ref·평가 후보·[q,1-q]·원집계.
- `rollouts.sqlite`: 논리 작업, 시도, 오류·재개 이벤트와 원자 결과 파일 해시.
- `private/`: simulator/actor snapshot·실제 상대세트/queue·계산 감사·시도 trace/checkpoint.
- `incomplete.jsonl`, `duplicates.json`, `tokens.jsonl`, `audit.json`: 미완료·중복 격리·길이·감사.

저장 레코드 전체를 프롬프트로 전달하지 않는다. `serializer.generate(official, prefix, own_team, …)`가
공식 actor cutoff·공개 이력·자기 팀만 받아 `JointInput`을 만든다. 동일 함수가 향후 실시간
입력 경계다. renderer는 이 타입만 받으며 `TrainingRecord`·타깃·원선택·seed·private를 거부한다.
CPU tokenizer는 Qwen3.5-4B의 기존 고정 로컬 tokenizer만 로드한다. 길이는 무절단이며
16384 초과를 별도 보고한다. 그 한도가 향후 미정 모델의 길이 계약을 결정하지 않는다.

```python
from integration.pokechamp.joint_q.data import load, collate, masked_mse, masked_argmax
from integration.pokechamp.joint_q.serializer import render

records = list(load('/workspace/.pokechamp-data/experiments/ex065-joint-q', split='train'))
batch = collate(records[:8])
prompts = [render(value) for value in batch['inputs']]
# prediction[B,Amax]는 향후 모델이 제공한다.
# loss = masked_mse(prediction, batch['q_targets'], batch['action_mask'])
# indices = masked_argmax(prediction, batch['action_mask'])
# chosen_ids = [ids[i] for ids, i in zip(batch['action_ids'], indices.tolist())]
```

손실은 관측별 유효 후보 MSE를 구한 뒤 관측 평균이다. padding은 손실/선택에서 제외하고,
동률은 주어진 후보 순서의 첫 ID다. 순서 변경은 `record.reordered(action_ids)`로 입력과 타깃을
함께 ID 정렬한다. 후보 하나라도 유효32회가 없으면 관측 전체를 loader에서 제외한다.

EX-064 계산기는 당시 동결 모델 결과 이후의 사후 보정본 `2349ed21…`을 사용한다.
공동 입력은 후보 결과 열 배열/후보 참조를 펼친다. 미지원·빈 unknown 테라 이득은 unknown이며
다른 후보의 결과로 안전 판정을 만들지 않는다. EX-060 추가300턴 제한은 제거하고 pinned
Showdown의1000턴 자동 무승부를 정상 결과로 인정한다. 정확한 정규 bigerror 경고만 허용한다.
q는 숨은 실제 상태와 양측 Abyssal 후속 조건부 값이다. 관측 수는 독립 상황 다양성이나
모델 성능 향상을 입증하지 않는다.

수집 준비의 정정은 이전 봉인·실패와 연결한다. `active-source.json`이 현재 source label을,
`frozen-<label>.json`이 각 버전의 파일 해시를 가리킨다. 최초 nonterminal winner 생략 교정과
Keldeo-Resolute의 canonical species 별칭 바인딩은 분기 수집 전에 적용했다. 팀 성향의 기술명
정규화 정정은 `team-styles-v2.json`에 원/정정 분류를 나란히 보존하며 팀·그룹·seed는 불변이다.
개발 중 만들어진 input-records의 fingerprint는 export 시 현재 의미 정규화로 재산출하며
모델 입력 bytes는 바꾸지 않는다. 실제 원자료 버전/유효성은 감사 보고를 따른다.
