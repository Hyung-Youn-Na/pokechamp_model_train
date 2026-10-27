# EP-016 — 현재 입력·요약 구조 문서화

- 상태 (Status): Completed
- 생성일: 2026-09-08
- 완료일: 2026-09-09
- 책임자: Codex
- 승인 근거: 현재 사용자가 제공한 「현재 입력·요약 구조 문서화」 계획의 구현·검증 지시.
- 관련 contract: C-014/C-016/C-017
- 관련 decision: D-019/D-024/D-027/D-028
- 관련 experiment: EX-025 및 EX-025 사전 오프라인 자료(구조 설명용 evidence).

## 목표와 범위

연구자와 개발자가 현재 행동 입력·배틀 내 요약·실제 요청을 추적할 수 있는 한국어 본문
`docs/pokechamp-input-summary.md`와 영어 prompt 원문 부록
`docs/pokechamp-prompt-originals.md`를 작성한다. 프로젝트 색인·아키텍처·상태에 연결한다.
사용자의 상세 계획을 설계 근거로 사용하며 별도 설계 질문은 생략한다.

## 비목표와 불변 조건

코드·prompt·평가 기준·과거 실험 artifact·기존 worktree 변경은 보존한다. Cloud 호출,
실험 재개, 새 실험, 방법론 변경은 수행하지 않는다. EP-011/012/013/015의 `Blocked`는
유지한다. EX-025는 전체 무효이며 생성 응답 재사용 없는 독립 진단임을 밝힌다.
문서화만 검증하므로 runtime 회귀 추가·실배틀 재검증은 생략한다.

## 완료 기준

- [x] 흐름·A/B/C·필드 출처/소비·HP/결정 경계·요약 lifecycle을 코드에 대조한다.
- [x] IO-C01/IO-C05, EX-025 s15→s16→s17→s21의 실제 값 발췌와 봉인 원본을 연결한다.
- [x] prompt 원문 3종·버전·SHA-256 및 두 메시지 전송·thinking·검증 한계를 설명한다.
- [x] 운영 연쇄와 고정 메모리 진단·Latios 입력/평가 불일치를 구분한다.
- [x] 원문 바이트·JSON 발췌·로컬 링크·Mermaid를 검증하고 보호 파일 불변을 확인한다.
- [x] 검증 결과와 색인·STATUS를 갱신한 뒤 이 문서화 plan만 완료한다.

## 검증 및 진행

- 2026-09-08 — INDEX/CHARTER/관련 계약·Decision 및 겹치는 active plan 4개 확인.
- 2026-09-08 — 문서 변경 전 EX-025 closure seal의 문서 15개가 현재 바이트와 일치함을
  확인하고 [보존 기록](../../../exec-plans/evidence/ep016/preservation.json) 및
  [변경 전 문서 archive](../../../exec-plans/evidence/ep016/before-context.tar.gz)에 보존했다.
  이 archive는 legacy evidence이며 현재 authority가 아니다. 기존 source·자료·문서
  39,301개 파일의 변경 전 해시도 로컬 audit 경로에 기록했다.
- 2026-09-09 — 본문·부록 작성 및 대조 완료. 오프라인 IO-C05가 운영의 최근 10구간과
  달리 전체 prefix를 포함함을 명시했다. s17/s21의 context 차이는 고정 summaries 3개뿐이며,
  통합의 previous_summary는 둘 다 M142임을 실제 입력으로 확인했다.

## 차단 및 중단 조건

INDEX 공통 규칙을 따른다. 설명 중 발견한 구현·계약·evidence 차이는 문서에 기록하며
실험 조건이나 과거 자료를 수정하여 해소하지 않는다. 기존 실험 halt를 재개하지 않는다.

## 결과 및 증거

[한국어 본문](../../../../docs/pokechamp-input-summary.md)과
[영어 prompt 전문 부록](../../../../docs/pokechamp-prompt-originals.md)을 작성하고 INDEX 및
ARCHITECTURE에서 연결했다. STATUS에는 문서화 완료와 기존 실험 Blocked 유지 사실만 추가했다.
코드·prompt·평가 기준·과거 실험 artifact 및 기존 active plan 4개는 변경하지 않았다.

| 검사 | 결과 |
|---|---|
| builder/player/backend/validator 수기 코드 대조 | 필드 출처·소비, 10행동/3요약, 현재/과거 우선순위와 검사 한계를 본문에 연결 |
| prompt 원문 추출 | 3개 text 블록이 마지막 LF까지 원본 바이트 및 provenance SHA-256과 일치 |
| JSON 발췌 | 8개 블록이 지정 봉인 JSON의 부분값과 일치; 생략 범위·전체 파일 링크 명시 |
| EX-025 읽기 전용 대조 | 봉인 구성 파일 190개, 입력 22개, 기록된 실제 wire 요청 132개와 prompt/역할/think 일치 |
| 요약 예시 의존성 | M78→M142→M204 고정 메모리 참조, s17/s21 context, 구간별 event/주석 개수 대조 통과 |
| Mermaid | 격리된 mermaid 11.12.0 parser로 flowchart-v2 구문 통과; repo dependency 변경 없음 |
| 문서 링크·공백 | 최종 이동 후 로컬 링크와 공백·fence 검사, git diff --check 통과 |
| 이전 문서 보존 | EX-025가 참조한 15개 문서 archive의 모든 바이트·해시 일치 |
| 보호 범위 | 기존 39,301파일 중 승인된 현재 문서 4개만 변경; 나머지 39,297파일 및 runtime source 130개 불변 |

정확한 최종 검사 수·명령·해시는 [검증 기록](../../../exec-plans/evidence/ep016/verification.json)에 있다.
문서 링크 최초 검사에서 아직 생성 전인 verification.json을 발견해 기록 생성 후 재검사했다.
이번 검증은 설명·직렬화 evidence의 대조이며 runtime 회귀, 의미 재평가, Cloud 또는 실배틀
호출은 수행하지 않았다. 기존 EX-025의 전체 무효와 EP-011/012/013/015의 `Blocked`는 유지한다.
이 문서화 완료는 기존 실험 완료나 재개 승인이 아니다.
