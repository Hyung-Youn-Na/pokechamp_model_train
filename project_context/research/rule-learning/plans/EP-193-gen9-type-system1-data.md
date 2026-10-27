# EP-193 — Gen9 타입 System 1 판별 학습자료

- 상태: Completed
- 생성일: 2026-10-21
- 승인: 사용자 “SFT가 아닌 system one 목적의 학습도 가능한 데이터도 구성해줘”
- 연구선/checkout/시작commit: research/model-training /workspace feda62f733c1b470364868262c789ec857ef67f5; 기존 미커밋 변경 보존.
- 관련: D174/EP192 원자료, C083의 선택지 CE 개념(기존 EX113 실행조건은 승계하지 않음), 공통 C007/RD 평가경계.
- 환경: 기존 vLLM runtime Python의 CPU tokenizer/PyTorch, 모델가중치 적재·GPU·추론·학습0.
- 소스: integration/type_system1/, scripts/type-system1-data
- 원자료(읽기 전용): datasets/generated/gen9-type-matchup/v1, EP192 봉인.
- 새 출력: /mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/gen9-type-system1/v1
- 제공: /workspace/exports/gen9-type-system1-v1 및 ZIP, evidence/ep193.

## 범위·계약

System 1을 설명/CoT 생성 없이 입력에서6개 타입배율을 직접 판별하는 학습으로 해석한다.
정답을 이용하는 supervised classification이며 생성형 assistant-token SFT나 비지도학습이 아니다.
EP192의64980행/3078기본/61902확장/3080의미그룹을 보존한다. 원래범위·정답·학습pool/no-test 경계 유지.
두 표현: (1) 57차원 원입력타입/테라 one/multi-hot→6클래스 분류; (2) JevK5 공식 비Thinking 입력→6선택지 logits CE.
입력은 원공격타입19·원방어타입18·테라상태20만 포함한다. 유효방어타입·배율·계산근거·ID·그룹·가중치·정답은 입력에 넣지 않는다.
선택형은 후보순서를 원자료에서 유지하고 input_ids/label_ids/target/expected를 CPU tokenizer로 준비한다.
assistant정답토큰/설명target을 붙이지 않는다. 학습시 마지막 입력위치의6후보 logits에만 CE를 적용한다.
기본/확장을 분리하고 의미그룹 반복역수 가중치를 metadata로 제공하되 실제 학습비중/선택은 후속계획에서 정한다.
기존 EX113 로더/완료모델·서빙·원자료·봉인 변경0. 새 모델학습·평가·배틀은 범위 밖으로 EX/C047 해당없음.

## 완료 기준

- [x] 원봉인/행대응·클래스/후보/벡터 전수검증·metadata변조시 입력불변
- [x] 공식 native 비Thinking template 동치·6문자단일token·무절단 길이 확인
- [x] 선택지/분류 CE 사용 예제 CPU 수치/gradient 검사, 기존학습기 자동호환으로 오인하지 않도록 경계 명시
- [x] JSONL/NPZ·manifest·설명·ZIP과 문서상태/색인 종결

## 진행

INDEX/CHARTER/매뉴얼/현재·중단색인/EP192·규칙학습DESIGN/CONTRACTS와 기존선택CE구현을 확인했다.
이번 자료변환은 기존 Blocked 실행을 재개하지 않는다. 실패시 새출력을 보존하고 내보내기를 차단한다.
실험시계/재경기 규칙은 해당없음이다.

## 결과

64980행의 두 판별학습 표현을 전수검증했다. 57차원/6클래스, JevK5 입력269~277토큰이며
6문자단일token·native template·metadata변조 입력불변·저장행대응이 모두 통과했다.
CPU 합성logits의 패딩/타겟gradient/후보순서불변/가중손실/빈입력거부7검사를 통과했다.
독립 서브에이전트가 소스의 후보매핑·누출·마지막위치 계산을 읽기검토했고 중대한 결함이 없었다.
[보고](../../../exec-plans/evidence/ep193/report.md) · [사용 안내](../../../../exports/gen9-type-system1-v1/README.md).
모델적재/실제학습·GPU/서빙변경은0이며 기존자료 봉인은 보존했다.
