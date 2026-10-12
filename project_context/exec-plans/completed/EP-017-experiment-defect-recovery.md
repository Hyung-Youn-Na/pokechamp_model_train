# EP-017 — 테스트·평가 결함 복구 절차 문서화

- 상태 (Status): Completed
- 생성일: 2026-09-09
- 완료일: 2026-09-09
- 책임자: Codex
- 승인 근거: 현재 사용자가 제공한 「테스트·평가 결함의 수정 및 복구 절차 문서화」 계획의 구현·검증 지시.
- 관련 contract: C-018 (이번 등록), 기존 C-014~C-017 보존
- 관련 decision: [D-029](../../decisions/D-029-experiment-defect-recovery.md)
- 관련 experiment: 새 실험 없음. 기존 EX-020~025는 보존 대상이다.

## 목표와 범위

새로 승인·등록하는 실험의 테스트·평가 도구 결함에 대해 발견 → 영향받는 작업 일시 중지 →
원인·영향 확인 → 수정·독립 검증 → 필요한 범위 재평가·재실행을 기본 절차로 문서화한다.
RESEARCH_DESIGN, CONTRACTS, INDEX, Decision/plan/experiment index 및 template, STATUS,
integration/pokechamp/README.md와 improved_io/README.md의 안내만 변경한다.
이 plan의 검증 기록·변경 전 문서와 해시 목록도 별도 보존한다.

## 비목표와 불변 조건

런타임 코드·API·CLI·파일 schema·prompt·실험별 평가 기준은 변경하지 않는다.
기존 원자료·봉인·보고서·halt·clock·개별 Decision/experiment/plan은 불변이다.
EP-011/012/013/015의 Blocked 및 기존 무효·미완료 판정을 유지한다.
실험 실행·재개·Cloud 호출·provider 재시도 확대는 승인 범위가 아니다.
같은 승인·예산 내 허용 복구의 재승인은 요구하지 않으며 상한 초기화도 허용하지 않는다.
이 plan은 비실험 문서 작업이므로 자체 재수집 허용은 해당 없음(Cloud·재수집 0)이다.

## 완료 기준

- [x] D-029/C-018과 공통 절차·5유형 판단표의 적용 시점·범위·기존 규정 관계를 명시한다.
- [x] 결함 기록, 독립 검증, 대응·연쇄 단위, 분모·버전 보존 및 예산·실행기 제한을 규정한다.
- [x] 매뉴얼·요약 진단·improved IO·INDEX·두 template의 등록 안내를 연결한다.
- [x] 8가지 사례와 전체 중단·재시도·재개 문구를 검토한다.
- [x] 링크·공백·변경 범위와 보호 파일을 검증하고 index/STATUS를 갱신한다.

## 검증

| 검사 | 방법 | 결과 |
|---|---|---|
| 상황 판단 | 단위 테스트·평가 코드·rubric·입력·연쇄 오염·영향 불명·예산 소진·기존 중단 8사례 수기 대입 | Passed — 아래 판단 기록 |
| 규정 범위 | 전체 중단·재시도·재개 검색 및 실행기의 halt/clock/report 거부 경로 읽기 전용 대조 | Passed — 새 기본 규칙과 당시 실험별 규칙 구분 |
| 문서 품질 | 로컬 Markdown 링크·anchor·fence·공백, git diff --check | Passed — 최종 수치는 검증 기록 참조 |
| 보존 | 변경 전 40,973파일 SHA-256과 비교 | Passed — 허용 문서 11개 변경, 40,962파일 불변 |

## 진행

- 2026-09-09 — INDEX/CHARTER/RESEARCH_DESIGN/CONTRACTS, 활성 EP-011/012/013/015와 관련 Decision을 확인했다.
  D-029·EP-017 중복 없음 확인 후 등록했다. 기존 실험을 확장하지 않는 별도 문서 작업이다.
- 2026-09-09 — 변경 전 40,973파일 해시와 허용 문서 11개 원본 archive를
  `.artifacts/pokechamp-documentation/ep017/`에 보존했다. 기존 미커밋 변경도 보존한다.
- 2026-09-09 — RESEARCH_DESIGN §11.1/C-018, 매뉴얼 5유형·8사례와 등록 항목을 작성했다.
  기준선 pilot의 재시도 설명을 해당 설정에 한정하고 improved IO의 현재 상태를 중단으로 명료화했다.
  초기 링크 274개/anchor 27개와 보호 범위 검사를 통과한 뒤 STATUS와 완료 index를 갱신했다.

## 차단 및 중단 조건

[INDEX](../../INDEX.md)의 승인·확인 질문·중단·완료를 따른다. 문서와 구현의 차이는
지원 한계로 명시하고, 기존 실험의 판정이나 halt를 수정해 해소하지 않는다.
문서화 완료는 실험 재개·기존 plan 완료·복구 기능 구현 완료를 뜻하지 않는다.

## 결과 및 증거

[공통 절차](../../RESEARCH_DESIGN.md#defect-recovery), [C-018](../../CONTRACTS.md#c-018-recovery),
[매뉴얼·8사례](../../../integration/pokechamp/README.md#defect-recovery)에 규정과 운영 안내를 연결했다.
기존 D-017 이후 연구 설계 절 및 C-001~C-017 원문은 바이트 단위로 유지했다.
기존 활성 plan 4개·index 행, experiment record 26개, 원자료 40,477파일, halt/clock 180파일,
integration/scripts의 허용 README 외 129파일은 불변이다. Canonical submodule 두 곳도 clean이다.

| 사례 | 규정 대입 검토 결과 |
|---|---|
| 단위 테스트/cwd | 의존 단계 보류 → 실제 수집 비영향 근거와 재현/회귀 통과로 결과 유지 가능. 수집 오류와 구분됨 |
| 평가 코드 | 모든 영향 조건·응답의 분석 보류 → 사전 기준을 바꾸지 않는 동일 재평가. 선택 재채점 금지와 일치 |
| rubric | 원문·실제 입력 도달성 확인 → 사후 변경 공개·별도 수정 분석. 기존 통과 판정으로 소급하지 않음 |
| 실제 입력 | 영향 실행·의존 결과 무효 → 필요한 조건 쌍/block 재수집. rubric 완화만으로 복구 불가 |
| 연쇄 오염 | 공유 store·후속 요약/행동 포함 중지 → 검증된 오염 전 경계에서 대응 단위까지 재수집. 마지막 응답만 교체 불가 |
| 영향 불명 | 공유 source의 잠재 영향 전체 중지 → 경계 입증 불가 시 비교 전체 무효. 선택 보존 불가 |
| 예산 소진 | 수정 검증 성공이어도 신규 수집 보류 → 상한 초기화 없이 미완료 보고. 추가 승인 범위만 구체화 |
| 기존 EX-025 | D-028/C-017 전체 무효·132응답/126무효 초안/6미검토·EP-015 Blocked 유지. D-029 적용으로 재개 불가 |

수기 검토는 절차의 일관성 확인이며 새 실험이나 과거 응답의 의미 재평가가 아니다.
정책 검색은 `rg -n '전체.*중단|재시도|재개|halt|retry|resume' project_context integration/pokechamp -g '*.md'`
기반으로 수행했다. 종결 기록 추가 전 66문서/297줄을 찾았으며 현행 규범·매뉴얼과 겹치는 active
plan을 대조하고, 기존 Decision/실험/완료 plan의 당시 규칙은 보존했다. 진단 runner/report/maximum_report,
IO receipts/review_gate의 실제 거부 경로를 읽어 매뉴얼의 미지원 경로를 확인했다.

- [최종 검증 기록](../evidence/ep017/verification.json)
- [변경 전 문서 보존 기록](../evidence/ep017/preservation.json) 및 [원본 archive](../evidence/ep017/before-docs.tar.gz)
- [검증 스크립트](../../../.artifacts/pokechamp-documentation/ep017/verify.py),
  [변경 전 해시 목록](../../../.artifacts/pokechamp-documentation/ep017/before.json),
  [문서 diff](../../../.artifacts/pokechamp-documentation/ep017/documentation.diff),
  [정책 검색 기록](../../../.artifacts/pokechamp-documentation/ep017/policy-search.txt)

검증 기록의 로컬 audit 링크는 이 workspace에 보존된 자료를 필요로 한다. Runtime 회귀·실배틀·
Cloud 호출은 문서 작업 범위 밖이므로 실행하지 않았다. API·CLI·파일 schema 변경, 복구 기능 구현,
실험 재개 또는 기존 plan 완료를 뜻하지 않는다. EP-017의 문서 정비만 완료했다.
