# EX-024 — low 요약 지시 개선 후 IO 재실험

- Status: Blocked
- 날짜: 2026-09-08
- 관련: [D-027](../decisions/D-027-low-summary-prompt-reexperiment.md),
  [EP-011](../exec-plans/active/EP-011-improved-io.md)

## 사전 protocol

D-027의 범위·모든 단계·통과 기준·시계·중단 규칙을 적용한다.
A=upstream IO, B=개선 IO, C=B+배틀 내 요약이며 EX-016 개발 b01–b04/기존15장면을 쓴다.
source/프롬프트 버전별 별도 집단으로 보존하며 비교48판은 조건당16, 동일 block/진영의
유효 완료 대응만 비교한다. smoke는 비교 분모에서 제외한다.
출력은 `.pokechamp-data/io-improvement/ex024/`, 최초 Cloud 전에 독립 평가 기준을 봉인한다.
v1.1.0부터 최대3조합, 모든 역할 low와 기존 모델/샘플링/동시성 설정을 유지한다.
총4시간/신규작업3시간45분을 버전 수정과 재검증을 포함해 공유한다.
요약 오류는 버전 중단, 행동 출력/provider/환경/무결성 오류는 전체 중단이다.
과거 EX-020/021/022/023의 봉인 자료·중단 기록·시계를 보존한다.

## 진행

사용자 승인 계획 등록 후 버전 선택 및 호출 간 검토 게이트를 구현하고 사전 검증을 수행했다.
설계 토의/계획은 사용자가 제공한 명시적 계획으로 충족한다. 동작 중심 회귀와 직접 코드
검토를 수행하고 별도 agent 위임은 사용하지 않는다.

### v1.1.0 사전 검증

311회귀(88.01초), Ruff/compileall/Node12, 오프라인15·사후3, 원문 독립18입력·
후속10경계, 로컬 병렬12/12·실제 동시10·격리/포트 및31행동의3요약/1통합이 통과했다.
원본에서 독립 작성한18경계/125필수 사실을 Cloud 전에 봉인했다. 기존 아이템 교정 후
EX-023과 입력18개가 동일하다. 가짜236호출의 단계/검토/재개/중복제출 거부도 통과했다.

- [사전 검증](../../.pokechamp-data/io-improvement/ex024/verification-precloud-v1.json)
- [기준](../../.pokechamp-data/io-improvement/ex024/criteria-v1.json)
- [일정·source·프롬프트 봉인](../../.pokechamp-data/io-improvement/ex024/cloud-v1/manifest.json)

v1.1.0 첫 C요약 수집부터 EX-024 전체 버전이 최초 제출 시계를 공유했다.

### v1.1.0 중단과 v1.1.1 재검증

첫 C요약5제출/5응답/미확정0, 형식오류3(정확한 actor_id 줄에 설명 추가)으로 버전을
봉인했다. 원문 대조에서 Spikes 영향 진영·Encore 종료 시점·기절 후 교체 턴 및 벤치의
과거 boost/Choice lock 재도입 오류도 확인했다. 전체 필수 사실 검토는 완료하지 않았으며
[실패 검토](../../.pokechamp-data/io-improvement/ex024/cloud-v1/failure-review.json)에
확정 오류 근거와 검토 한계를 기록했다. 입력153,895/출력5,854 tokens, 수집23.58초다.
나머지 C요약3/별도요약48/행동180/smoke12/비교48은 이 버전에서 미실행이다.

관측 오류에 따라 v1.1.1에서 identity 줄·전 절의 영향 진영·기절 후 교체의 실제 턴·
현재 관측과 과거 제한의 구별을 강화했다. 평가 기준125개는 불변이며 같은 시계를 공유한다.
새 source의 사전 검증부터 다시 수행했다.

### v1.1.1 중단과 v1.1.2 재검증

v1.1.1도5제출/5응답/미확정0에서 summary 태그 누락1건으로 버전 중단됐다.
[실패 검토](../../.pokechamp-data/io-improvement/ex024/cloud-v2/failure-review.json)에서
가설 절의 Spikes 진영 역전과 미공개 팀 자리 수 오류를 추가 확인했다. 입력155,075/
출력6,493 tokens, 실제수집25.19초다. 전체 의미·누락 검토 완료율은 산출하지 않는다.
팀 수 오류의 원문 행 참조1개는 [별도 참조 정정](../../.pokechamp-data/io-improvement/ex024/cloud-v2/failure-review-evidence-correction.json)에 보존했고 판정·사전기준은 변경하지 않았다.

v1.1.1 사전 회귀 최초3건은 fake12와 공용 runtime lock 경합으로 거부됐다. 실패 로그를
보존한 뒤 배틀 종료 후 같은 source로 전체311회귀(88.12초)가 통과했다. prepare 종료 전
collect의 조기 진입1회도 manifest 부재로 제출 전에 거부됐으며 실패 로그를 보존했다.
두 거부는 Cloud 중복 제출/실패 보충이 아니며 제출 intent가 생기지 않았다.

마지막 허용 v1.1.2는 출력의 전체 태그 틀·가설에서의 근거 없는 위험 예측·roster 집계를
명시했다. 새 source의 사전 검증을 다시 수행했으며125필수사실/최초시계는 불변이다.

### v1.1.2 중단 및 최종 결과

311회귀(90.52초), 오프라인15·사후3·독립 요약18입력/후속10경계,
새 로컬12/12·실제 동시10·31행동3요약/1통합 및 source/identity 검증을 통과했다.
세 source의 회귀는 각각311개가 통과했고 새 로컬 배틀은 버전별12/12다.

첫 C요약5제출/5응답 모두 형식을 통과했지만, turn9에 Cinderace로 교체한 뒤에도
과거 Kyurem의 Choice lock을 현재 상태로 재도입했다. 원본 event72:2의 과거 요청과
event77:4의 교체, event78:2의 최신 요청을 근거로
[실패 검토](../../.pokechamp-data/io-improvement/ex024/cloud-v3/failure-review.json)를
봉인하고 해당 버전을 `summary_semantics`로 중단했다. 최대3개 유료 source/프롬프트
조합을 소진하여 [전체 halt](../../.pokechamp-data/io-improvement/ex024/halt.json)를
`version_limit`으로 기록했다. 이후 Cloud 제출은 없다.

| 버전 | C요약 예정/제출/응답/미실행 | 형식 오류 | 확인된 무효 응답* | 입력/출력 tokens | 실제 수집 초 |
|---|---|---|---|---|---|
| v1.1.0 | 8/5/5/3 | 3 | 5 | 153,895/5,854 | 23.58 |
| v1.1.1 | 8/5/5/3 | 1 | 2 | 155,075/6,493 | 25.19 |
| v1.1.2 | 8/5/5/3 | 0 | 1 | 158,015/6,192 | 44.70 |

*형식·확정 사실 오류의 응답 단위 합집합이다. 나머지를 의미 검토 통과로 간주하지 않는다.
전체 의미 오류율·필수 사실 보존율은 미산출이며 모든 응답의 미검토 상태를 보존했다.
추가 Cloud 채점·재질문·실패 보충은0이다. 버전별 별도요약48/행동180/smoke12/비교48은
전부 미실행이다. A/B/C 각각 예정16/시도0/유효완료0/실패경기0/미실행16,
B-A/C-A/C-B 각각 유효대응0/누락16이며 승률·효과·행동HTTP overlap/p95는 미산출이다.

최초 제출은2026-09-08 07:50:56.795583 UTC, 전체 halt까지19.89분이다.
실제 수집 batch 합93.47초와 명시적 의미 검토 대기57.29초를 분리 기록했다.
형식 오류로 중단한 첫 두 wave는 후속 검토 대기에 들어가지 않았다. 공유 시간에는
프롬프트 수정·원문 검토·재검증도 포함했고 시계를 초기화하지 않았다. 금액 단가 자료가
없어 실제 token만 보고하며 전체 모델 설정은 사전 protocol과 같다.

### 보존·정리와 완료 판단

[종료 검증](../../.pokechamp-data/io-improvement/ex024/verification-final.json):
과거9,499파일 불변, JSON139 seals·로컬72 actor seals, Cloud15 intent/15응답 일치·미확정0,
세 버전의 halt 재진입 거부·동일 시계, source 고정, canonical submodule clean,
8000/8100–8109 해제·잔여 계산기0 및 credential1,853파일/유출0을 확인했다.
종료된 로그만 해시하고 개발 중 잠금 경합·조기 진입·참조 정정도 원형 보존했다.
공통 clock/halt의 `decision=D-022`는 기존 유틸리티 필드이며 이번 승인은 D-027 manifest에
연결한다. 기존 실험의 raw/halt/clock을 변경하거나 개선 결과를 소급하지 않았다.

- [통합 보고서](../../.pokechamp-data/io-improvement/ex024/report.md)
- [기계 판독 집계](../../.pokechamp-data/io-improvement/ex024/report.json)
- [v1.1.2 사전 검증](../../.pokechamp-data/io-improvement/ex024/verification-precloud-v3.json)

구현·사전 검증·중단 처리는 수행했지만 요약 gate와48판 검토·대응 분석을 완료하지 못했다.
EP-011은 `Blocked`로 유지하며 `Completed`로 옮기지 않는다. 이 개발 자료의 탐색적 gate
실패에서 L1-L5 효능·프롬프트 우월성·모델 일반 한계 결론을 내리지 않는다.
