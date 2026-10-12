# EP-019 — B 행동 입력 필드 설명서

- 상태: Completed
- 생성일: 2026-09-09
- 책임자: Codex
- 승인: 현재 사용자 계획의 구현·로컬 검증 지시, D-031.
- 관련: C-019, D-030, D-031. EX-026은 보존 대상이며 재개하지 않는다.

## 목표·범위·불변 조건

단일 영문 필드 자산, 행동 v1.1.0, 공통 조립과 준비/실행/요청 hash 연결 및 fail-closed
경로 검사를 구현한다. 상태 JSON·합법 후보·출력 계약·A/요약 선택을 유지한다.
Parent integration과 프로젝트 문서를 변경하며 pinned source와 기존 자료를 보존한다.

## 완료 기준

- [x] 전체 필드와 선택적 분기·원문 request 중첩 경로 설명 및 음성 검사
- [x] pinned 코드/원문에 독립 대조한 효과·시점·HP·item·확률 의미
- [x] prepare/Cloud worker/actor 무네트워크 요청 동일성·설명서 1회·과거 선택/hash 거부
- [x] integration 회귀, 15장면 의미·도달성/사후3, 새 fake32
- [x] 문자/바이트 증가량·보존·자원 정리·계약/아키텍처/STATUS 갱신

## 중단·검증

비실험 구현 작업이므로 새 유료 실험 복구 규정은 해당 없음. Cloud/재수집 한도0,
실제 배틀 재개 없음. 기존 halt·receipt·시계·Blocked를 변경하지 않는다.
충돌과 승인 판단은 project_context/INDEX.md의 공통 절을 따른다.
검증과 발견 결함은 이 plan 및 ../evidence/ep019/에 기록한다.

## 진행

2026-09-09: 관련 계약·설계·EP-018/011 확인, 사용자 승인으로 등록. 기존 자료 hash를
[보존 목록](../evidence/ep019/preservation.json)에 기록. 구현 전 Cloud0.

2026-09-09: 단일 fields.json·공통 조립·준비 기본 v1.1.0/legacy v1.0.0·실행/요청 identity,
원문 request 재귀 검사 구현. 최초 전용16검사·기존 B/요약48검사 통과. 이후 전용18을 포함한
전체385회귀(190.95초)와15장면 원문/의미/도달성·사후3 통과. Worker의 사전 경로 오류를
봉인 응답에도 남기고 actor manifest에 identity를 연결하는 보완 후 전체 재검증 중이다.

독립 의미 검토에서 pinned Pokemon.types가 `(type_1, _type_2)`를 반환해 테라 후 원래
보조 타입을 남기는 한계를 실제 Gliscor parser로 재현했다(WATER/FLYING, tera_type=WATER,
별도 type_2 property=None). 입력·계산 코드는 변경하지 않고 설명서에 이 원본 한계를
명시한다. 초기 null 보조 타입 누락은 최초15장면 경로 검사에서 발견해 자산의 자료형을
수정했다. 실제 값·원자료를 삭제하거나 변형하지 않았다. Cloud0.

최종 설명서는361경로, 시스템72,980자/72,992 bytes(기존 대비64,751자/64,759 bytes)다.
테라 tuple 한계 회귀를 포함한386검사(171.96초), Ruff/compileall/Node, 새15장면/사후3이
통과했다. [최종 회귀](../evidence/ep019/regression-final.log),
[준비](../../../.pokechamp-data/battle-field-guide/ep019/prepare-complete/result.json).

첫 fake32는 높은 시스템 부하가 관측된 동안 B 계산기 시작 timeout30으로 중단(10시도/0유효,
22미시작)했다. 프롬프트 조립 전 startup 오류이며20 actor 봉인을 보존했다. 취소된 채
websocket 연결에 남은 소유 fake actor 하나는 command/process group 확인 후 SIGINT로
정리하여 최종 recorder 봉인을 확보했다. 같은 계산기 동시 시작10개는 별도 검사에서
143–170ms에 모두 성공했다. 원인이 부하라는 해석은 추정이며 확정된 단일 원인으로 삼지 않는다.
[독립 시작 검사](../evidence/ep019/calculator-startup.json),
[실패 보존·새 로컬 실행 설정](../evidence/ep019/local-retry.json).
소스/프롬프트/timeout/실제 배틀 동시성10은 유지하고 native library thread만1로 제한한
새32 전체 로컬 fixture를 별도 ID로 실행 중이다. 실패 표본을 새 결과에 합치지 않으며
EX-026 재개·Cloud 호출은0이다.

스레드 제한 후 새32배틀은32/32 유효·실제 동시10·요약0으로 완료됐지만 최종
`study.battle_checks`에 남은 v1.0.0 고정 문자열 비교가400개 정상 B요청을 거부했다.
실제400개 전달 문자열·선택 identity는 v1.1.0과 일치한다. 기존 실패 receipt를 보존하고
선택 버전으로 비교하도록 검사기를 교정했다. 원자료 재평가에서32/32·오류0을 별도로
[봉인](../evidence/ep019/evaluation-recheck.json)했으며 과거 판정을 덮어쓰지 않았다.
v1.0.0 metadata 부재 호환 및 v1.1.0 누락/변조 거부 회귀2건을 추가했다.
최종388회귀·새 준비 및 최종 source로 별도fake32 전체를 검증한다.

## 최종 결과 — 2026-09-09

구현·로컬 검증·보존·정리를 완료했다. 최종143 source의388회귀(171.99초), Ruff E/F/I/W,
compileall·Node 검사, 운영15장면의 의미·실제 입력 도달성·사후 피해3건이 통과했다.
일반 행동/강제 교체/테라/변화기/미상 상대 교체/지연 효과 및 원 request 선택 분기와
설명 제거·신규 중첩 필드·형식/해시/과거 선택 회귀를 포함한다.

최종 새fake32는32/32 유효·실제 동시10·64 actor 봉인·B16 actor의400행동 전송 모두
공통 v1.1.0 문자열·identity와 일치했다. 각 system에 설명서1회, 사용자 context/후보/요약부재를
검증했다. A-condition32 actor bundle에는 새 설명서0이며 B 요약/통합/archive0이다.
별도31행동 fixture도 같은 전달·메모리부재 검사를 통과했다. CPU native thread1의 로컬
실행 조건은 별도 기록했으며 배틀 동시성과 timeout은 완화하지 않았다.
첫 startup 실패10시도와 검사기 교정 전32완료 자료/실패 receipt/별도 재평가는 보존했다.
최종 통과 분모에 앞선 집단을 합치지 않는다.

시스템72,980자/72,992 UTF-8 bytes, 기존 대비64,751자/64,759 bytes 증가이며 user JSON은
유지했다. 모델 token/latency/오류 감소는 미측정이다. 원래44,000파일 hash·기존5개 Blocked
plan·EX-026 응답/halt/시계 불변, 최종 source143 일치, credential2,948파일 검사/유출0,
canonical submodule clean/pinned, 포트8000/8100–8109 free와 소유 runtime 잔여0을 확인했다.

- [최종 준비](../../../.pokechamp-data/battle-field-guide/ep019/prepare-validated/result.json)
- [최종fake32](../../../.pokechamp-data/battle-field-guide/ep019/fake32-validated/result.json)
- [종료 검증](../evidence/ep019/verification.json), [회귀 로그](../evidence/ep019/regression-final.log)
- [361경로 inventory](../evidence/ep019/field-inventory.json), [렌더링 영문 설명서](../evidence/ep019/field-guide.txt)
- [한국어 구현·의미 근거](../../../docs/pokechamp-battle-field-guide.md)

D-031 승인 범위의 완료다. Cloud 호출0·EX-026 미재개이며 EP-018 및 기존 요약 실험의
Blocked를 유지한다. 새 실험의 유료 gate 통과·모델 오류 감소·배틀 효능은 주장하지 않는다.
