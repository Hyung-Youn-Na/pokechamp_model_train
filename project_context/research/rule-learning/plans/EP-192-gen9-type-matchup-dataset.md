# EP-192 — Gen9 타입 상성 전수 학습 데이터

- 상태: Completed
- 생성일: 2026-10-21
- 승인: 사용자 “gen9ou의 포켓몬 타입 경우의 수를 모두 포함하는 상성 계산 학습 데이터를 만들어줘.”
- 관련: D174, 공통 C007, 연구 설계의 평가/오염 경계. EP169 기존 자료와 분리한다.
- 연구선/checkout/시작commit: research/model-training /workspace feda62f733c1b470364868262c789ec857ef67f5, 기존 미커밋 변경 보존.
- 환경: 기존 Python3/Node, CPU 순차 생성·검증. GPU·모델추론·학습·외부 API 호출0.
- 새 소스: integration/type_matchup_dataset/, scripts/type-matchup-dataset
- 새 자료: /mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/gen9-type-matchup/v1/
- 열람 복사본: /workspace/exports/gen9-type-matchup-v1/ (JSONL/CSV/README/검증/manifest)
- 근거: /workspace/pokemon-showdown 고정commit e64915c0eab066db1d3e732b1280386468dd7415 및 실제 dist 소스, ep192 evidence.

## 범위

18 공격 타입 ×171 방어 조합(단일18+서로 다른 복합153)=3078 기본 문항.
확장은 19공격 타입 ×171기본방어 조합 ×20방어모드(미테라/일반18테라/스텔라)=64980 경우로 기본을 포함한다.
중복 합산하지 않고 기본3078과 확장61902로 분리한다. 스텔라 공격은 스텔라 테라버스트로 명시한다.
기존 포켓몬 종 목록이 아닌 이론적 타입 전수이며 OU에 실재하지 않는 조합도 포함한다.
특성·도구·날씨·필드·자속·특수기술 예외·추가3타입·무타입은 제외한 순수 타입 상성 배율이다.
일반 Tera는 방어타입을 대체, 스텔라는 기존방어타입 유지. 스텔라공격은 상대의 테라 여부로1/2배.

canonical 사실/정답/근거, messages SFT, 6개배율 선택형, CSV, 한국어 설명/예시/coverage·manifest를 생성한다.
학습용 영어 질문·짧은 계산 근거를 사용한다. 입력에는 주어진타입·테라조건만, 답/계산결과는 target·metadata에만 둔다.
전부 학습 pool이며 임의행분할/test 성능 주장을 만들지 않는다. 같은 상성의 표현변형은 semantic group으로 묶는다.
기존자료·잠긴 test·서빙모델을 변경하지 않는다. 새 배틀/평가 실험이 아니므로 EX 및 C047은 해당없음.

## 완료 기준

- [x] 결정적 생성기·전수커버리지/중복·유일정답·입력경계 검증
- [x] 독립 Showdown Dex/Pokemon 판독 전수대조와 면역/4배/0.25배/상쇄/테라·스텔라 경계 사례 검증
- [x] 기본/확장 SFT·선택형·CSV·설명·출처·분모·checksum 및 열람복사본 제공
- [x] 문서·색인·STATUS 갱신과 최종보고

## 진행·중단

INDEX/CHARTER/매뉴얼·진행/중단색인·EP169와 규칙학습 설계/계약을 확인했다.
현재 실행계획 없음; 이번 독립 타입 계산 데이터는 기존 Blocked 배틀·학습·관측 수집을 재개하지 않는다.
오류 시 학습용내보내기를 차단하고 새 CPU 자료를 수정·재검증한다. 실험시계/경기재수집은 해당없음.

## 결과 및 증거

기본3078·확장61902, 총64980상황/3080계산그룹을 생성했다. 전수 Showdown 대조와 타입순서반전,
Cartesian 누락/중복, 유일정답, 경계11사례, 저장SFT/선택형/CSV 원본대조를 통과했다.
독립 서브에이전트는 소스·oracle·실제검증결과의 범위/정확성/입력누출을 읽기검토했고 중대한 결함을 발견하지 않았다.
6개 기본정답군과 스텔라 미테라/일반/스텔라 사례를 추가 열람했다. 외부 인간 블라인드 검토는 아니다.
[보고](../../../exec-plans/evidence/ep192/report.md) · [배포 확인](../../../exec-plans/evidence/ep192/delivery.json) ·
[사용 안내](../../../../exports/gen9-type-matchup-v1/README.md) · [ZIP](../../../../exports/gen9-type-matchup-v1.zip).
학습/모델평가/배틀 실행은 하지 않았다. 기존모델·자료·봉인은 유지했다.
