# EX-023 — 상태 교정 후 개선 IO 실험 재개

- Status: Blocked
- 날짜: 2026-09-08
- 관련: [D-026](../decisions/D-026-continue-io-experiment.md),
  [EP-011](../exec-plans/active/EP-011-improved-io.md)

## 실행 전 protocol

질문은 D-019의 A=upstream IO, B=개선 IO, C=B+배틀 내 요약의 운영 성적·오류·자원 차이다.
EX-016 개발 b01–b04 및 기존15장면을 사용한다. D-022 단계와 평가를 그대로 적용한다.
오프라인15/사후3 → fake12 → Cloud 행동180, 별도 요약48 및 C 입력 요약 별도 분모 →
smoke12 → 조건당16/전체48판이다. 같은 block의 완료 대응만 비교하며 미완료를 숨기지 않는다.
모델 glm-5.3-flash, low, temperature0, seed100, 출력131072, provider 기본 context,
배틀/계정/모델10/10/10, retry_transient=0, 일정 seed20260908을 유지한다.
Smoke는 비교 분모에서 제외하고 원자료/조건/source를 분리한다.

출력 위치는 `.pokechamp-data/io-improvement/ex023/`이다. 기존 실패 자료와 합치지 않는다.
최초 Cloud 제출부터4시간,3시간45분에 신규 작업 중지, 남은15분 보존·정리다.
패치와 재검증에도 동일 시계를 사용한다. Cloud 출력·사실·시점·identity 오류0,
HTTP 겹침10과 p95비율≤2, smoke12/12와 실제 동시배틀10이 필요하다.
입력/계산 오류만 독립 재현 후 새 source로 재검증하며 모델 오류 gate는 완화하지 않는다.
작은 점수 차이는 탐색적 관측이며 효능·우월성 확증이 아니다.

## 진행

후속 요약의 원문 구간과 주석 구간 불일치, live 구간 앞 턴/HP 소실을 공통 builder로
교정했다. 기존 첫 요약·프롬프트·전략은 유지한다. 회귀298개(85.09초),15장면 구조/의미와
사후3건,18요약 입력/후속10경계의 독립 원문 대조가 통과했다. fake12/12 및 실제
동시배틀10·격리/정리·31행동의 요약3/통합1을 통과했다.

초기 로컬 실행의 evidence 인자에 rubric을 넣은 오류는 원문 발췌 파일 io_evidence.json으로
교정했다. 잘못된 명령은 replay/Cloud 전에 실패했으며 로그를 보존했다. 신규 회귀의
수기 원문 행 번호5를6으로 적은 실패도 교정하여 전체298통과와 구별한다.

- [오프라인](../../.pokechamp-data/io-improvement/ex023/offline-v1/result.json)
- [독립 요약 입력 대조](../../.pokechamp-data/io-improvement/ex023/summary-preflight-v1.json)
- [로컬 병렬12](../../.pokechamp-data/io-improvement/ex023/fake12-v1/result.json)

## Cloud 결과와 중단 후 수정

C 입력 요약6제출/6봉인/미확정0,63.17초다. 형식/전송 실패는0이지만 첫 요약에서
p2 측 Spikes를 p1 교체에 영향을 주는 것으로 기술하고 turn1의 실제 행동을 없다고 했다.
현재 입력과 원문에는 올바른 진영·턴이 제공되어 있다. 별도로 event24의 Toxic Orb 공개
발동이 item=unknown_item으로 남는 입력 누락을 확인했다. 두 실패는 독립 근거로 보존한다.
입력170,508/출력7,227/합177,735 tokens가 확정됐으며 전체 의미 오류율은 미산출이다.
기존 기준에 따라 STOP/halt 후 신규 제출을 중지하고 진행 중 응답을 보존했다.

중단 후 Toxic/Flame Orb의 공개 자기 귀속 발동 및 제거·교환·교체 이후 수명을 수정했다.
Pinned Showdown3시나리오와 외부 귀속 음성 검사, 독립 원문 oracle의 과거 입력 거부,
전체300회귀(91.54초), 오프라인15/사후3·요약18입력·별도 fake12/12가 통과했다.
Fixture 개발 중 돌아오는 교체 번호를1로 지정한 오류는 active가 index1로 이동하는 원본
규칙에 따라2로 고쳤다. 실패/통과 로그를 보존한다. 당시6개 Cloud 입력·응답은 불변이다.

Cloud 행동180/별도요약48/smoke12/비교48은 모두 미실행이다. A/B/C 각각 예정16/시도0/
완료0/실패경기0/미실행16이며 세 대비 각각16대응이 누락됐다. 승률·효과·행동 지연비는
산출하지 않는다. 새 source의 Cloud 재호출은0이며 고정 low 조건 요약 gate가 미충족이다.
EP-011 전체를 완료로 처리하지 않는다.

- [상세 보고서·분모·비용](../../.pokechamp-data/io-improvement/ex023/report.md)
- [Cloud 사실 오류](../../.pokechamp-data/io-improvement/ex023/cloud-gate-v1/semantic-failure.json)
- [공개 아이템 누락](../../.pokechamp-data/io-improvement/ex023/cloud-gate-v1/input-failure.json)
- [수정 후 로컬12](../../.pokechamp-data/io-improvement/ex023/fake12-poststop/result.json)

## 종료 검증과 기록 한계

[최종 검증](../../.pokechamp-data/io-improvement/ex023/verification-final.json)에서 두 로컬
집단48 actor seals, 기존10,022파일 불변, Cloud6 intent/응답 일치, halt 재진입 거부,
Ruff/compileall/Node12 및 포트·소유 계산기·credential 정리를 확인했다.

사전 보조 receipt가 자기 stdout 로그를 아직 비어 있을 때 해시한 뒤 출력을 작성하여
해당 로그1개의 참조 해시가 달라졌다. 원래 receipt를 수정하지 않았으며 다른 모든 첨부
파일·source/단계 seal은 일치했다. [별도 감사](../../.pokechamp-data/io-improvement/ex023/verification-precloud-audit.json)에
기록/현재 해시와 원인을 보존했다. 최종 receipt는 작성 중 로그를 참조 목록에서 제외하고
종료된 증거만 봉인한다. 이 교정은 Cloud 자격 복구가 아니다.
