# EP-195 — Gen9 상태이상 System 1 학습자료

- 상태: Completed
- 생성일: 2026-10-21
- 승인: 사용자 상태이상 지식의 System 1 형식 학습데이터 생성 요청
- 연구선/checkout/commit: research/model-training /workspace feda62f733c1b470364868262c789ec857ef67f5; 기존 dirty변경 보존.
- 관련: D174/EP192의 Gen9 합성지식 경계, EP193의 직접선택CE, EP169 기존 상태QA와 중복가능성. 기존 분할/실행 승계0.
- 소스: integration/status_system1/, scripts/status-system1-data; 기존 Python CPU tokenizer/Node Showdown.
- 원천: pokemon-showdown e64915c0eab066db1d3e732b1280386468dd7415 및 실제dist; 읽기전용.
- 출력: /mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/gen9-status-system1/v1
- 제공: /workspace/exports/gen9-status-system1-v1 및ZIP, evidence/ep195.

## 범위·방법

화상/마비/일반독/맹독/잠듦/얼음, 별도 volatile인 혼란/풀죽음을 다룬다.
6상태×171단일/복합타입×20미테라/일반테라/스텔라 방어상태의20520 타입면역 경우를 전수포함한다.
추가 장면은 기존주요상태와중첩, 대표특성면역, 접지별 Electric/Misty Terrain,
지속피해·속도/행동실패확률·해제/회복·교체/일반테라의 상태유지와OU수면기술제약을 다룬다.
특성/종/기술 전조합을 모두 포괄한다는 주장은 하지 않는다. 상태별 세부지원범위/실제분모는 coverage에 기록한다.
입력은 명시조건과질문/후보만이며 설명/정답 completion 없이 후보logits CE를 적용하는 System1 자료다.
정답지도 판별학습용이며 실제학습/추론/속도·성능입증이 아니다. GPU/API/모델적재0.

정답은 독립 예상규칙과 고정 Showdown Dex/Pokemon/condition/ability/item hook 또는 rule table의 실제값을 대조한다.
확률/기간을 샘플1회결과로 라벨링하지 않는다. 제어hook/합성장면은 자연경기 표본/OU합법종세트로 해석하지 않는다.
Gen9OU Sleep Moves Clause와intrinsic수면을 구분하고 frostbite는 이포맷의상태로 추가하지 않는다.
입력에 oracle/라벨/근거/미래로그/계산결과를 합치지 않는다. 근거는 canonical/evidence에 별도 보존한다.
새 학습pool이며 test split/성능주장0. 원자료/기존모델·서빙·모든봉인은 보존한다.

## 완료 기준

- [x] 원천pin·완전타입커버리지·조건별oracle와기대정답 대조 및 실패0
- [x] 상태효과/확률/회복의 출처·예외 의미검토; 혼란33/100 등 실제engine값 명시
- [x] 동적후보 유일정답·metadata변조입력불변·native비Thinking token동치/무절단·저장원본대응
- [x] System1 choice/token JSONL·coverage·manifest·사용안내·ZIP/검증 및상태/색인완료

## 진행·중단

INDEX/CHARTER/매뉴얼/진행·중단색인·규칙학습계약·EP192/193을 확인했다.
기존Blocked평가·학습을 재개하지 않는다. 새정답불일치 시 해당자료 내보내기를 차단하고 교정근거를 보존한다.
정상배틀/효능실험이 아니므로 EX/C047·실험시계/재경기 해당없음이다.

## 결과·검증

22423문항/34규칙군을 생성했다. 타입면역20520경우는 전수, 그외영역은 명시된 제어문항이다.
전수oracle/후보유일정답/metadata입력불변/native template/저장행대응을 통과했다. 입력219~298토큰, 답completion0.
동적2~5후보 CE의 CPUgradient·후보순서불변·비후보제외·중복후보거부를 검사했다.
독립 에이전트가 효과/치료oracle facts.cjs를 분리구현하고 core.cjs를읽기검토했다. 주 에이전트가 통합코드/34대표문항을검토했다.
Magma Armor의별도면역hook과 기술PP준비를 생성전 gate에서교정했고 실패근거를보존했다.
[최종 보고](../../../exec-plans/evidence/ep195/report.md) · [교정](../../../exec-plans/evidence/ep195/corrections.md) ·
[사용안내](../../../../exports/gen9-status-system1-v1/README.md).
실제학습/모델forward·GPU·서빙변경0이다. 기존상태QA와개념중복가능성을유지하고 별도test/효능주장을만들지않았다.
