# EP-197 — Gen9 날씨·영역 System 1 자료

- 상태: Completed
- 생성일: 2026-10-21
- 승인: 사용자 “다음은 날씨와 영역에 대한 system1 학습 데이터를 만들어줘”
- 연구선/checkout/commit: research/model-training /workspace feda62f733c1b470364868262c789ec857ef67f5; 기존변경 보존.
- 관련: EP193/195/196 직접선택CE, 기존범위·원자료·분할은보존.
- 소스: integration/weather_terrain_system1/, scripts/weather-terrain-system1-data; CPU Node/Python tokenizer.
- 원천: Showdown e64915c0eab066db1d3e732b1280386468dd7415 및실제built소스.
- 출력: /mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/gen9-weather-terrain-system1/v1
- 제공: /workspace/exports/gen9-weather-terrain-system1-v1 및ZIP, evidence/ep197.

## 범위

날씨는맑음/비/모래바람/눈과없음, 영역은Electric/Grassy/Misty/Psychic Terrain과없음으로해석한다.
9세대눈과이전세대우박을구분한다. 원시날씨/DeltaStream·다른세대·더블전체·Room류전체는범위밖.
날씨피해보정·SandRockSpD/SnowIceDef·모래타입면역을단일/복합171×테라20범위로검증한다.
Terrain기술강화/완화의공격자/방어자접지·반무적조건,Grass의특정지면기술과잔여회복,
지속시간/확장도구·교체/덮어쓰기·동시날씨/필드·대표특성/도구/기술예외를명시조건으로다룬다.
타입/테라및정의한유한그리드만전수이며모든상호작용을포함한다고주장하지않는다.

input.state/question→유효후보CE,정답/설명completion0. oracle/metadata/계산결과입력제외.
고정Dex/hook/제어Battle메서드와독립예상규칙을대조하고확률은표본1회로라벨링하지않는다.
실제종·세트OU합법성/자연경기표본으로해석하지않는다. 모두학습pool,별도test/성능주장0.
모델학습/forward/GPU/API/서빙변경0. 기존봉인보존. 비배틀자료작업으로EX/C047해당없음.

## 완료 기준

- [x] 날씨/필드그리드와대표예외의출처·조건·정답대조/분모확정
- [x] 눈/모래·Misty비강화·접지주체·우산·유지/소멸·최대HP회복경계 의미검토
- [x] 선택지유일정답·metadata입력불변·native비Thinking무절단token·저장대응
- [x] CPU선택CE검증·독립검토·사용안내/자료/manifest/ZIP·상태/색인완료

## 진행·중단

INDEX/CHARTER/매뉴얼·현재/중단색인·규칙학습계약·선행System1자료를확인했다.
기존Blocked작업을재개하지않으며실험시계/경기재수집해당없음.
정답/검증실패시내보내기를차단하고원인/교정을보존한다.

## 완료 결과

12178문항/22규칙군. 타입/테라별방어능력치6840·모래타입면역3420·날씨피해360·필드위력1440·그래스지면예외16·대표예외102.
전수oracle/선택지유일정답/metadata입력불변/native template/저장대응을통과했다. 입력205~309토큰, 답completion0.
CPU2~5후보CE의해석적값·gradient·후보순서·비후보배제·중복거부를검사했다.
독립에이전트가facts를분리구현하고core를검토했으며주에이전트가통합코드/22규칙대표를검토했다. 인간블라인드검토는아니다.
[최종보고](../../../exec-plans/evidence/ep197/report.md) · [사용안내](../../../../exports/gen9-weather-terrain-system1-v1/README.md).
모두학습pool·성능주장없음. 실제학습/모델forward/GPU/기존서빙변경0, 기존자료봉인보존.
