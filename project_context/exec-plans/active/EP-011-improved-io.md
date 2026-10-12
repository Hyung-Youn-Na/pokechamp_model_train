# EP-011 — IO 개선 및 병렬 3조건 비교

- 상태 (Status): Blocked
- 생성일: 2026-09-08
- 책임자: Codex
- 관련 contract: C-014
- 관련 decision: [D-019](../../decisions/D-019-improved-io.md)

## 목표와 범위

사용자가 승인한 A/B/C IO 구현과 오프라인·병렬 로컬·Cloud gate 및 조건부48판 비교를
수행한다. 정확한 조건·gate·예산·해석은 D-019와 연구 설계의 D-019 절을 따른다.
Parent integration 및 project_context만 변경하며 canonical submodule과 과거 원자료를 보존한다.
minimax 수리, 배틀 간 학습, 순차 배틀, 실패 보충은 제외한다.

## 완료 기준

- [ ] 관측/공개·추정 경계 및 원래 자기 세트 대조
- [ ] actor 소유 Node 계산기·lockfile·고정 prior·필수 범위 및 실패 검증
- [ ] fixed 런타임 자산·엄격한 행동 출력·배틀 내 요약 및 identity 검증
- [ ] 조건별 schedule/actor/resume/집계와 공유 permit·source seal
- [x] 15장면 오프라인 및 기존 회귀·정적 검사
- [x] fake 병렬12판 격리/취소/포트/무결성 검증
- [x] Cloud180회와 요약 fixture gate 또는 근거 있는 중단 기록
- [x] Cloud smoke12 및 조건부48판 또는 gate/예산 미실행 기록
- [x] 분모·대응·역할별 비용·배치 경과·정리 evidence 및 STATUS 갱신

## 진행 및 검증

2026-09-08: 기존 active plan 없음 확인. EX-016의 analysis/prompts_pvp에서 지정 자산과
15장면 acceptance_cases.json 발견. 원자료는 수정하지 않는다. 구현 전 D-019 등록.

## 중단 조건

상위 authority 충돌, 필수 입력 부재, gate 실패 시 해당 경계 이후 작업을 중단하고
원자료와 사유를 기록한다. Cloud 예산은 최초 Cloud 호출 이전에는 시작하지 않는다.

## 2026-09-08 검증 결과 및 차단

[EX-017](../../experiments/EX-017-improved-io-offline.md) 단계1에서 중단했다.
15개 원본 seal/발췌/결정시점 연결 및 구조 재생 완료. 별도 사후 정답 계산3건 중
Draco Meteor/면역2건은 관측과 일치했으나 Ruination이0피해로 나와 실제100→51%와 불일치한다.
계산 wrapper는 이제 해당 기술을 명시적으로 거부한다. 원본 및 불일치 당시 source는 보존했다.
새 benchmark는 봉인된 offline 통과 receipt와 source 일치 없이는 시작할 수 없다.

관측·계산·fixed 파서/backend·배틀 내 메모리·조건 schedule/actor/집계 연결은 구현했으나
전체 기술적 완료로 표시하지 않는다. 특히 runtime/요약 의미/병렬 격리의 실배틀 검증과
Cloud gate/예산 orchestration·역할별 최종 실측 보고는 미완료다. fake12/Cloud180/smoke12/48은
모두 미실행이며 Cloud 호출0이다. 단계1 실패를 숨기고 단계2로 진행하거나 순차 전환하지 않았다.

### 최종 확인

- `cd pokechamp && PYTHONPATH=/workspace .venv/bin/python -m pytest /workspace/integration/pokechamp/tests -q`:163 passed (최종31.98초). 기존 upstream 경로 회귀 포함.
- Changed-file Ruff E/F/I/W(line-length100), Node syntax, compileall 통과.
- offline/posthoc receipt checksum 및68개 당시 source archive hash 일치.
- canonical pokechamp/Showdown submodule clean,8100–8109 listener 없음, calculator 잔여 process 없음.
- project_context local link 검사 통과. 승률/HTTP overlap/배치 시간 실측은 배틀 미실행으로 없음.

[최종 검증 및 source seal](../../../.pokechamp-data/io-improvement/ep011-final/verification.json):
163 tests, credential 검사131파일/유출0, Cloud0 및 미완료 상태를 봉인했다.

## 2026-09-08 사용자 승인 후속: Ruination 패치

[D-020](../../decisions/D-020-project-owned-ruination-patch.md)의 프로젝트 소유 패치,
설치·런타임 identity 검사, 회귀와15장면/사후3건 재검증을 이번 bounded 범위로 추가한다.
EX-017과 당시 receipt/archive를 보존한다. 새 EX-018은 별도 출력 경로를 사용하며
새 불일치/미지원 효과 발견 시 중단한다. 의미 rubric, 병렬·Cloud·48판은 이번 완료 범위 밖이다.

### 패치 범위 검증 결과

EX-018에서 추가 패치 회귀19건 및 전체181 tests(33.58초)가 통과했다. 새 npm 설치/재적용,
HP1·2·201·202, Protect/Wonder Guard/Mold Breaker, 강화/테라 불변, 패치 누락·버전·변조 및
응답 identity 불일치 종료/LLM 차단을 확인했다. Ruff E/F/I/W, Node syntax, compileall 통과.
최종15개 재생과 사후3건 대조가 통과하며 Ruination 피해186/잔여187/공개51%로 오류가 해소됐다.
패치 범위는 완료다. 상태 Blocked의 현재 이유는 의미 rubric 등 전체 offline gate 미완료이며
기존 계산 오류가 아니다. 병렬·Cloud·48판 및 EP-011 전체를 완료 처리하지 않는다.
결과와 source seal은 [EX-018](../../experiments/EX-018-ruination-offline-revalidation.md)에 연결한다.

## 2026-09-08 사용자 승인 후속: 특수 기술 진단

[D-021](../../decisions/D-021-special-move-diagnostics.md)에 따라 parent integration에
재실행 가능한 오프라인 도구를 추가한다. 현재 기술군과 고위험 기술의 선정/조건을 봉인하고
pinned Showdown의 메모리 내 테스트 Format으로 raw calculator 및 Python/Node wrapper를
대조한다. 불일치 독립 재현, 입력 표현 부족, 미검증 사유와 source identity를 EX-019에 보존한다.
계산기/운영 입력 수정·Cloud·서버 배틀·패키지 변경은 범위 밖이다. 전체 상태는 Blocked다.

### 특수 기술 진단 결과

[EX-019](../../experiments/EX-019-special-move-diagnostics.md)의343후보 중252기술에 대해
1,010 fixture×16난수를 실행했다. 일치685/수치 불일치73/입력 표현 부족234/명시적 미지원18,
범위 제외91 및 별도 미검증 범위64를 봉인했다. 수치 불일치73건은 독립 재현했고
명시적 타수의 raw 타격별 대조28건은 일치했다. 현재 팀61개 기술의 이번 수치 대조는
불일치가 없었지만5개 기술의 입력 표현 한계가 있다. 기본 prior의 Endeavor·Mirror Coat와
Pain Split 및 Nothing 문제를 우선 보고했다.

신규21개 포함 전체202 tests(47.34초), Ruff E/F/I/W·Node syntax·compileall 통과.
EX-018 기존 source와 현재 차이0이며 계산기·운영 입력을 수정하지 않았다. 개발 검증기 오류는
실패/무효 자료로 보존하고 최종776 source/build/입력파일과 출력 seal을 새 디렉터리에 보존한다.
진단·보고 범위는 완료지만 계산기 전체 통과가 아니며 offline_gate_passed=false다.
의미 rubric·병렬·Cloud·48판은 미실행으로 EP-011 상태 Blocked를 유지한다.

## 2026-09-08 D-022 재개

사용자 승인으로 [D-022](../../decisions/D-022-resume-io-experiment.md)와 EX-020에서
의미 검증·단계 gate·발생 오류 패치를 포함해 전체 경로를 재개한다. 기존 범위 제한은
과거 EX-018/019의 evidence에 유지한다. 진행은 새 source와 단계 receipt로 기록한다.

### EX-020 최종 결과 — Cloud 의미 gate 중단

Knock Off/Poison Heal 공개 정보, Future Sight 예약 효과, 양측 기절 교체 요청,
Quark Drive/Supreme Overlord 공개 활성 입력을 실제 재실행에서 발견해 독립 Showdown fixture로
재현·수정했다. 계산 수식·0.11.0+ruination-v1·프롬프트·전략은 유지했다.
최종214 tests(50.64초), Ruff/Node10파일/compileall,15장면 구조·의미 및 사후3건 통과.
fake 최종12/12, terminal 경기 오류0, 실제 동시배틀10, 별도31행동의 요약3/통합1을 검증했다.
이전 실패/수정 cohort는 보존·분리하며 실패 경기 보충을 하지 않았다.

Cloud C 입력 요약에서 Ninetales349→64→0의 두 번 피격을 만피 OHKO라고 기술해 중단했다.
7응답 봉인, 추가 제출1응답 미봉인이다. 확정 token은 입력150,179/출력9,166이며 전체가 아니다.
SIGINT 때 부모 future 대기가 끊기는 보존 결함은 worker 선봉인·신호 후 수집·intent 기록으로
수정하고 로컬에서 재검증했다. 과거1건의 응답/token은 복원하거나0으로 대체하지 않았다.
최초 Cloud 시계와 halt는 유지하고 수정 후 Cloud 재호출은0이다. Cloud 행동180·별도요약48·
smoke12·비교48은 모두 미실행이다. 조건별 비교예정16/시도0/완료0/실패0/미실행16,
세 대비 각각16대응 누락이며 승률은 산출하지 않는다. EP-011은 완료 처리하지 않는다.

- [최종 보고서](../../../.pokechamp-data/io-improvement/ex020/report.md)
- [214회귀·source/출력·자원 검증](../../../.pokechamp-data/io-improvement/ex020/verification.json)
- [Cloud 사실 오류](../../../.pokechamp-data/io-improvement/ex020/cloud-gate-v1/semantic-failure.json)

EX-017/018 기존 receipt와 EX-019 출력8종 checksum,6개 로컬집단의132 actor seals를 검증했다.
Credential2,636파일 검사/유출0, 두 canonical submodule clean,8000/8100–8109 free,
소유 calculator/worker 잔여0이다. 최종 hygiene 검증기의8000 인자 오류는 별도 무효 기록으로
보존하고8100–8109 검증과8000 socket 검사를 분리해 통과했다.

## 2026-09-08 현재 사용자 승인 재개 — EX-023

사용자가 EX-017 계열 실험의 계속 진행과 오류 해결을 명시적으로 요청했다.
[D-026](../../decisions/D-026-continue-io-experiment.md)에 따라 기존 중단 자료를 보존하고
[EX-023](../../experiments/EX-023-continue-io.md)에서 상태 교정 후 전체 단계 경로를 재개한다.
EX-022 후속 로컬 교정을 적용하되 low/high 진단은 재실행하지 않는다. 기존 A/B/C와
gate·분모·4시간 상한을 유지한다. 새 실행에 필요한 source/identity/검증 결함을 수정하고
새 source로 로컬 검증부터 수행한다. EX-020 자체의 Blocked/halt/clock은 불변이다.

재개 전 실제 입력 검토에서 두 번째 이후 요약의 raw 구간을 줄인 뒤 전체 prefix 주석이
남는 Cloud 경로와, 구간 앞 턴/HP를 잃는 live 경로의 차이를 확인했다. 공통 builder가
공개 prefix로 턴·직전 HP를 계산하고 현재 구간의 주석만 전달하도록 교정했다.
첫 요약은 불변이며 프롬프트·전략·요약 주기를 바꾸지 않았다. 실험 ID도 CLI로 명시할 수 있다.
298회귀(85.09초),15장면 구조/의미 및 사후3건,18요약 입력(후속 경계10개)의 독립 원문 대조,
fake12/12와 실제 동시배틀10·31행동 요약3/통합1이 통과했다. Cloud 전 검증 receipt를 준비한다.

### EX-023 결과 — 요약 사실 오류 및 공개 아이템 입력 누락

Cloud C 입력 요약6제출/6봉인/미확정0,63.17초·입력170,508/출력7,227 tokens를 기록했다.
첫 검토에서 p2의 Spikes를 p1 교체의 위험으로 적고 turn1 행동을 없다고 한 오류를 확인했다.
원문과 현재 입력에는 올바른 진영/턴이 있으므로 이 오류를 입력 누락으로만 설명하지 않는다.
별도로 공개 Toxic Orb가 item=unknown_item으로 남아 있는 입력 모순을 봉인했다.
STOP·영속 halt 후 신규 제출을 차단했고 행동180/별도요약48/smoke12/비교48은 미실행이다.

중단 후 Toxic/Flame Orb 공개 발동·제거/교환/교체 수명을 독립 pinned Showdown3시나리오로
재현·수정했다. 외부 상태이상·다른 holder는 제외한다. 원문 독립 아이템 검사와 음성회귀,
전체300회귀(91.54초), 오프라인15/사후3·요약18입력·새 fake12/12가 통과했다.
당시6개 Cloud 입력/응답·시계/halt는 불변이며 Cloud 재호출은0이다. 후속 로컬 통과가
Cloud gate를 복구하지 않는다. 기존 low/프롬프트 조건의 요약 사실 gate는 미충족이다.

- [EX-023 보고서](../../../.pokechamp-data/io-improvement/ex023/report.md)
- [요약 사실 오류](../../../.pokechamp-data/io-improvement/ex023/cloud-gate-v1/semantic-failure.json)
- [입력 누락](../../../.pokechamp-data/io-improvement/ex023/cloud-gate-v1/input-failure.json)
- [수정 후 로컬12](../../../.pokechamp-data/io-improvement/ex023/fake12-poststop/result.json)

조건별 비교예정16/시도0/유효완료0/실패경기0/미실행16,세 대비16쌍 누락이다.
승률·조건 차이·행동HTTP overlap/p95비율은 산출하지 않는다. EP-011은 미완료다.

[종료 검증](../../../.pokechamp-data/io-improvement/ex023/verification-final.json):
48 actor seals·기존10,022파일 불변·Cloud6 intent/응답 일치·halt 재진입 거부·
Ruff/compileall/Node12·포트/계산기/credential 정리 통과. 사전 보조 receipt의 자기 stdout
로그1개 해시 불일치는 원형을 보존하고 별도 감사에 기록했다. 다른 첨부/source/단계 seal은
일치하며 최종 receipt에서는 작성 중 로그를 해시 목록에 넣지 않았다.

## 2026-09-08 D-027 승인 확장 — EX-024

현재 사용자 계획에 따라 [D-027](../../decisions/D-027-low-summary-prompt-reexperiment.md)의
최대3프롬프트 버전·공유4시간 재실험을 실행한다. 원본 프롬프트/과거 자료를 보존하며
요약·통합 지시와 버전/검토 게이트를 구현한다. 단계는 사전300+회귀·15/3/18·로컬12 →
C요약8 → 별도요약48 → 행동180 → smoke12 → 예산 내 비교48이다.
의미 검토 전 응답의 후속 재사용을 금지한다. 모든 기준과 최종48판 검토/분석/정리가
완료되지 않으면 Completed로 옮기지 않는다.

EX-024 v1.1.0은311회귀/15·3·18/로컬12를 통과하고125필수 사실을 사전 봉인했다.
요약 연쇄의 의미 검토 게이트를 적용하여 첫 Cloud 수집을 시작했다.

### EX-024 최종 결과 — 세 요약 버전 중단, 비교 미실행

원본 자산을 보존하며 v1.1.0/1.1.1/1.1.2와 실행별 선택·실제 wire/actor 해시 검증을
구현했다. C요약8→별도요약48→행동180의 선행 검토·응답 선봉인·재호출 없는 대기/재개,
버전별/전체 halt·중복 제출 거부·3개 source/프롬프트 조합과 동일 시계를 적용했다.
추가11개 포함 각 source의311회귀와 오프라인15·사후3·독립18입력/후속10경계,
새 로컬 병렬12/12가 통과했다. 원본 독립125필수 사실과 기존7제목/10행동·3요약 주기는
유지했다. 최종 source의311회귀는90.52초이며 Ruff/Node12/compileall도 통과했다.

세 버전이 각각 첫5개 C요약 응답에서 중단됐다. v1.1.0은 identity 줄 형식 및 진영/턴/
과거 상태 복원 오류, v1.1.1은 summary 태그 누락·가설 진영/팀 수 오류를 확인했다.
v1.1.2는 형식5/5 통과했지만 교체 후 과거 Kyurem Choice lock을 현재로 복원하는 오류가
남았다. 모두 실패 근거를 봉인했고 최대3조합 소진으로 전체 `version_limit` halt를 기록했다.
Cloud15제출/15응답/미확정0, 입력466,985/출력18,539 tokens, 실제 batch 합93.47초다.
첫 제출부터 halt까지19.89분으로 시간 예산이 아니라 버전 한도와 요약 gate 실패로 중단했다.

각 버전 C요약 나머지3/별도요약48/행동180/smoke12/비교48은 미실행이다.
조건별 예정16/시도0/완료0/실패경기0/미실행16, 세 대비 각각16쌍 누락이다.
미검토 응답을 통과로 처리하거나 버전 간 성공을 합치지 않으며 추가 Cloud 채점은 없다.
상단의 중단 기록 완료 체크는 D-027의 전체 gate·48판 검토·분석 완료를 대신하지 않는다.
요약 사실 gate와 비교 완료 요건이 남아 EP-011은 `Blocked`다.

- [EX-024 상세 및 실패 근거](../../experiments/EX-024-low-summary-prompt-reexperiment.md)
- [분모·역할별 token/HTTP·검토 대기 보고](../../../.pokechamp-data/io-improvement/ex024/report.md)
- [종료 검증](../../../.pokechamp-data/io-improvement/ex024/verification-final.json):
  과거9,499파일/72 actor seals·Cloud15응답 보존,139 JSON seals·재진입 거부·단일 시계,
  canonical submodule/포트/계산기/credential 검증 통과.
