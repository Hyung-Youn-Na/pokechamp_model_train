# EP-205 — v7 생존 판단과 교체 비용 지시문 개정

- 상태: Completed
- 완료일: 2026-10-21
- 생성일: 2026-10-21
- 책임자: Codex
- 승인: 사용자 제공 계획의 구현·검증 지시 / D-181
- 관련: D-179, EP-202/204, EX-115, C-006/067/081/082 및 주제 candidate-action-v1 계약
- 기준·실제 연구선: research/model-training; checkout /workspace
- 시작 commit: feda62f733c1b470364868262c789ec857ef67f5; 기존 다수 미커밋 변경 보존
- 환경: /workspace/pokechamp/.venv/bin/python; catalog는 scripts/context-catalog
- 새 출력: project_context/exec-plans/evidence/ep205
- 읽기 전용 근거: EX-115 최종 보고·manifest·동결 source 및 EX-112 저장 입력

## 목표·범위

사용자 지정 영어 두 문단을 상세 스피드 설명 뒤에 한 번만 넣고 기존 일반 문장을 제거한다.
prompt.txt·개발 README·EX115 상세 문서의 동결 참조·D/EP·주제 설계 연결·catalog만 갱신한다.
입력 필드·계산·후보·정책·기존 실험 자료는 유지하며 API·배틀 실행은0이다.
INDEX/CHARTER/매뉴얼/STATUS/계획색인·공통 RD/계약·주제 설계/계약/구성,
관련 EP202/204와 중단 EP140/179/183, 병행 EP203의 범위·보존 조건을 확인했다.
EP203 학습과 과거 중단 실험은 이번 범위 밖이다.

## 완료 기준

- [x] 지정 문구·배치·중복/의미 검토 및 개발/동결 참조 구분
- [x] 기존 선봉·일반 행동·강제 교체 입력의 API 요청 지시문 전달과 나머지 정보 보존
- [x] 문자·UTF-8 바이트·기존 프롬프트 해시 식별·catalog build/check 기록

## 검증·중단

저장 대표3종에서 실제 변환/요청 생성 함수를 오프라인 실행해 instructions 이외 동치를 확인한다.
기존 roundtrip 검사를 실행한다. 검증 실패는 원인을 기록하고 해당 범위만 교정한다.
비배틀 지시문 개정이므로 실험 시계·재수집·뷰어 내보내기는 해당 없음.
효능 개선은 평가하지 않는다. EX115의 수집 당시 gate·결과·봉인을 변경하지 않는다.

## 진행

- 2026-10-21 — 사용자 승인 범위 등록, 구현 전.

## 결과·증거

지정 영어 두 문단을 상세 스피드 문단 바로 뒤에 한 번 배치하고 일반 문장 하나만 제거했다.
역변환 대조로 그 외 지시문 전체가 동일함을 확인했다. 기존 우선도·피해 조건·교체 상태 변화는
유지되며 새 문단은 그 규칙을 참조해 생존과 행동 기회비용 판단을 연결한다.
강제 교체에는 잔류 대안이 없고 피벗에는 행동 시점까지 생존이 필요하다는 구분을 검토했다.
개발 README·주제 DESIGN을 갱신하고 EX115 상세 설명의 지시문 링크를 수집 당시 동결본으로 바꿨다.

- 선봉·일반 행동·강제 교체 각1개: 변환/복원·후보 명령 순서·API 요청의 instructions 외 전체 동치·
  모의 HTTP 실제 본문 대조 통과. 일반 행동에는 일반/테라 후보가 함께 포함된다.
- 기존 `test_core.py -k roundtrip_and_wire`: 3 passed, 13 deselected.
- 지시문: 10,126 → 10,953자(+827), UTF-8 10,126 → 10,959바이트(+833).
  대표 요청별 전달 텍스트도 각각833바이트 증가했다. 토큰은 측정하지 않았다.
- 개정 전 SHA-256: `ca467ea2a507dfbff21df2fbcc93f262d732816b83d0b92c43f06a7a23a042b4`
- 개정 후 SHA-256: `6a4bd45bb2e4d89a58a8daff959b3e29fb2691fffd6b575b9d00397ae01f1e64`
- EX115 동결 prompt와 개정 전 바이트 일치를 확인했다. 원자료·동결본·결과에 쓰기 없음.
- catalog build/check 결과는 [검사 기록](../../../exec-plans/evidence/ep205/catalog.txt)에 보존한다.

[오프라인 검증 결과](../../../exec-plans/evidence/ep205/verification.json) ·
[재현 스크립트](../../../exec-plans/evidence/ep205/verify.py) ·
[개정 전 지시문](../../../exec-plans/evidence/ep205/prompt-before.txt).
재현: `PYTHONPATH=/workspace PYTHONDONTWRITEBYTECODE=1 pokechamp/.venv/bin/python project_context/exec-plans/evidence/ep205/verify.py`.
API·배틀0이며 성능 개선은 평가하지 않았다. 기존 EX115의 총량 감소 gate를 재검증하거나
새 지시문에 승계하지 않았다. 미충족 완료 기준 없음. 병행 학습 상태가 바뀌지 않아 STATUS는 유지한다.
