# 기록 등록과 탐색

| 탐색 기준 | 생성 문서 |
|---|---|
| 실행 계획 상태 | [plans](plans.md) |
| Blocked 관리 분류·후속 근거 | [blocked](blocked.md) |
| 결정 | [decisions](decisions.md) |
| 실험 | [experiments](experiments.md) |
| 학습·추론·평가 방법 | [by-method](by-method.md) |
| 관련 모델 | [by-model](by-model.md) |
| 관련 자료 | [by-dataset](by-dataset.md) |
| 기준선·계승·교정·후속 평가 | [relations](relations.md) |

## 등록 절차

1. records.json에서 D/EP/EX별 최댓값 다음 ID를 선택한다. 원문 상태·승인·주제를 먼저 정한다.
2. templates의 형식을 사용해 해당 주제 decisions/plans/experiments에 원문을 만든다.
3. records.json의 records에 ID를 키로 등록한다. path는 project_context 기준 상대경로,
   topic은 topics의 기존 키, methods는 학습/추론/평가별 문자열 배열이다.
   models·datasets는 관련 모델/자료 배열이며 실제 처치와 기준선의 차이는 원문을 따른다.
   relations는 type·target을 가진 배열이다. references는 명시된 인용이며
   baseline/evaluates/continues/corrects/uses는 근거를 확인해 등록한다.
   legacy_paths는 이전 경로 호환용이며 새 기록에는 빈 배열을 사용한다.
4. `scripts/context-catalog build`로 생성하고 `scripts/context-catalog check`로 확인한다.
   `scripts/context-catalog resolve EX-113`으로 ID의 원문 위치를 찾는다.

제목·상태·날짜·결과를 등록부에 별도 복제하지 않는다. 상태는 원문의 첫 상태 필드에서 읽고,
인식 불가 상태는 오류로 보고한다. 기존 상태의 설명·미완료·무효 한정은 원형을 유지한다.
주제 RECORDS와 이 디렉터리의 생성 문서는 직접 편집하지 않는다.
새 주제가 필요하면 topics에 질문·제목을 등록하고 주제 INDEX를 작성한다.
분류 수정은 탐색 변경이며 연구 판정이나 실행 승인 변경이 아니다.

## Blocked 관리 분류

[D-171](../shared/governance/decisions/D-171-blocked-classification.md)에 따라
Blocked EP의 당시 판정은 보존하고 `blocked.json`에서 현재 관리 분류를 별도로 관리한다.
`awaiting`(해결 대기), `resolved`(후속 해결·종결), `ended`(진행 종료),
`review`(확인 필요)를 사용한다. Paused는 별도로 유지한다.

각 항목에는 category·reason·evidence(등록 ID 배열)·experiments(EX ID 배열)·followups를 적는다.
resolved는 실제 처리 범위를 확인한 최종 완료 기록을 resolved_by로 지정하고 evidence/followups에도 넣는다.
후속 Completed만으로 자동 판단하지 않으며 부분 복구·다른 과제·변경 조건의 한계를 reason에 쓴다.
ended는 해당 작업을 더 진행하지 않겠다는 명시적 종료 근거, awaiting은 장애와 현재 진행 필요의
근거가 필요하다. 불명확하면 review로 둔다. 이 분류는 실험 성공이나 실행·재개 승인으로 쓰지 않는다.

분류가 없는 새 Blocked는 생성 시 review에 나타난다. 알려진 항목의 분류를 갱신한 뒤
catalog build/check를 실행한다. 분류에 원래 EP/EX 상태·성적·조건을 복제하지 않는다.

## 실행기와 동결

`integration.project_context.registry.resolve_record(ID)`가 유일한 원문을 찾는다.
`record_relative(ID)`는 현재 원문의 project_context 상대경로를 반환하며
`prefix=True`는 저장소 상대경로를 반환한다. 알 수 없는 ID나 연결 문서는 원문으로 허용하지 않는다.
`freeze_document`는 실제 원문을 복사하고 분산 규범과 그 참조 기록을 protocol/context에 함께 보존한다.
이 사본은 실행 당시 문서 snapshot이며 이후 registry 변경으로 다시 해석하거나 갱신하지 않는다.
기존 run의 protocol·source·봉인은 원래 경로·바이트를 유지한다.
과거 코드가 이전 연결 문서를 직접 읽는 것을 지원된 새 동결 경로로 간주하지 않는다.

## 이전 위치

이전 경로는 원문으로 안내하며 authority가 없다. 기존 중앙 규범의 앵커도 이전 원문으로 연결한다.
완료 계획을 active/에서 찾던 기존 EP-132 경로 문제는 ID 조회로 해소한다.
이 경로 교정은 EX-080 재개나 과거 봉인의 변경을 승인하지 않는다.
