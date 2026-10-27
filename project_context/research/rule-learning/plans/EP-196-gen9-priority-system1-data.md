# EP-196 — Gen9 행동 우선도 System 1 자료

- 상태: Completed
- 생성일: 2026-10-21
- 승인: 사용자 “그 다음은 행동 우선도에 관한 system1 학습 데이터를 생성해주세요.”
- 연구선/checkout/commit: research/model-training /workspace feda62f733c1b470364868262c789ec857ef67f5; 기존변경 보존.
- 관련: EP193/195 선택형 CE 자료·공통 연구/출처/입력분리 규범. 기존 학습·평가·자료분할은 승계하지 않는다.
- 소스: integration/priority_system1/, scripts/priority-system1-data; CPU Python tokenizer/Node.
- 원천: Showdown e64915c0eab066db1d3e732b1280386468dd7415 실제 built Gen9 규칙과 source pin.
- 출력: /mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/gen9-priority-system1/v1
- 제공: /workspace/exports/gen9-priority-system1-v1 및ZIP, evidence/ep196.

## 범위

기술의 정수 우선도와 같은 우선도 안의 행동순서, 효과의 성공/차단을 분리한다.
Gen9 표준기술 목록의 기본우선도, 대표 특성(Prankster/GaleWings/Triage)의 우선도변경,
수치우선도×명시실효스피드×TrickRoom의 두행동 비교, 먼저/나중행동효과의 같은구간 제한,
우선도공격 차단·Switch/Tera 및 대표조건을 다룬다. 같은스피드는 확정승자가 아니라 tie로 라벨링한다.
수치스피드는50/100/200/400 범위로 고정해 극단적 engine wrap 경계를 포함하지 않는다.
대전모드/종/세트 합법성·전특성/전아이템/전턴 상호작용 전수라고 주장하지 않는다.
표준기술 roster의 추출조건과 행수, 실제제어사례 분모는 coverage에 기록한다.

System1용 input.state/question→문항별유효후보 CE. 정답/설명completion0, oracle/라벨/메타데이터 입력제외.
모두학습pool이며 test성능/모델사고방식/속도향상 주장0. 실제학습/모델forward/GPU/API/서빙변경0.
기존봉인 유지, 새경로쓰기만 수행한다. 정상배틀평가 아니므로 EX/C047 해당없음.

## 검증·완료

- [x] 고정Dex목록/정수우선도·확인가능기준사례와 조건별실제hooks/정렬메서드 대조
- [x] 순서비교의좌우교환·tie·TrickRoom/정수구간보존·고정범위완전성과오류0
- [x] 동적선택지유일정답·metadata입력불변·native비Thinking무절단token·저장대응
- [x] CPU CE검사·독립의미검토·JSONL/coverage/manifest/안내/ZIP·상태/색인완료

## 진행·중단

INDEX/CHARTER/매뉴얼·진행/중단색인·규칙학습계약과EP193/195를 확인했다.
선행자료를전용데이터로재개하지않고기존모델/학습기/Blocked평가도재개하지않는다.
오류시새내보내기를차단하고교정근거보존. 실험시계/경기재수집은해당없음.

## 완료 결과

10160문항/15규칙군. 기본우선도685·특성변경2740·우선도/스피드/TrickRoom비교3872·같은구간순서효과2816·대표예외47.
전수원천/후보유일정답/metadata입력불변/native template/저장대응을통과했고 입력205~365토큰, 답completion0이다.
분리facts구현·core독립검토·주에이전트통합/15규칙대표읽기를수행했다. QuickClaw의기술우선도0/행동정렬0.1을실제메서드로구분했다.
CPU2~11후보손실을해석적CE/gradient/후보순서/비후보배제에대조했다. 첫11후보검사임계값교정근거는보존했다.
[최종보고](../../../exec-plans/evidence/ep196/report.md) · [사용안내](../../../../exports/gen9-priority-system1-v1/README.md).
전체는학습pool이며 실제모델/학습/GPU/서빙변경0. 기존자료봉인은유지했다.
