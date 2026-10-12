# EP-015 — 요약 thinking low/max 진단

- Status: Blocked — 입력·평가 기준 불일치로 전체 무효, 진단 미완료
- 생성일: 2026-09-08
- 책임자: Codex
- 승인: 현재 사용자가 제공한 계획의 전체 구현·사전검증·132 Cloud 호출·검토·보고.
- 관련: [D-028](../../decisions/D-028-summary-max-diagnostic.md), C-017,
  [EX-025](../../experiments/EX-025-summary-max-diagnostic.md).

## 범위와 불변 조건

Parent integration/project_context 및 새 EX-025 자료에 한정한다. D-028의22입력·low/max·v1.1.2·
132회·4시간을 따른다. canonical SDK/submodule·과거 원자료·halt/clock·EP-011 Blocked는 보존한다.
설계는 사용자가 상세히 제공했으므로 추가 설계 질문을 생략하고 behavior 검사·구현·검토를 수행한다.

## 완료 기준

- [x] max 직렬화 어댑터와 summary-max-v1 profile·역할·해시/설정 검증
- [ ] 125사실·22입력·고정 메모리 원문 검토와 최초 Cloud 전 봉인 — 봉인은 완료했으나 실제 입력의 필수 사실 도달성 검증 실패
- [x] 기존311회귀 범위와 추가검사·15장면/사후3·fake132 중단/선봉인/중복거부
- [ ] 132응답과 조건을 가린 근거 연결 검토·입력별 및 원배틀 가중 집계
- [ ] 비용·재발·해석 한계·분모·자원정리·상태 갱신
- [x] 전체 halt·132응답/126무효 초안 보존·중단 보고·자원정리·Blocked 상태 갱신

## 중단 조건

D-028/C-017 및 INDEX 공통 규칙을 따른다. 모델 오류는 수집 계속,
provider/환경/입력/평가/무결성 오류는 전체 중단하고 응답 보존·미완료 보고한다.

## 진행 및 검증

2026-09-08: 상위 계약/설계·겹치는 EP-011/012/013과 EX-024 상태를 확인하고 새 승인 범위를 등록했다.
이 등록 시점에는 Cloud 시계를 시작하지 않았다.

사전 준비: summary-max-v1의22입력/132일정 및14고정 메모리 준비를 dev01에서 확인했다.
기존125사실을8 actor 원문/각 경계request로 직접 검토했고, 통합4입력에는 별도 역사 요구를
포함한46사실을 작성했다(총171개 입력별 요구). 모델 입력에는 평가 기준을 추가하지 않는다.
고정 메모리는 원문에서 별도 작성한7제목 요약이며 각 문장에 원문행·prefix hash를 연결했다.

사전 입력 오류: one_step-b04-s0의 원문 event31 line5는 상대 Ninetales Drought를 공개하지만
정규화는 ability=null/known=false였다. 날씨의 [of] holder를 놓친 것으로, pinned simulator와
EX-024 봉인 함수를 독립 대조해 재현 후 parent state/별도 oracle을 수정했다. 실제 Cloud0이다.
이전 pytest 두 번은 root cwd에서 static data를 못 읽어 parser 단계에 실패했으므로
독립 재현으로 세지 않는다. cwd를 바로잡은 새 검사2/2는 통과했다.
[독립 재현](../../../.pokechamp-data/summary-diagnostics/ex025-preparation/drought-independent-reproduction.json).
이 사전 준비 시점에는 전체회귀·오프라인15/3·fake132와 최종source 재봉인이 남아 있었다.

최종 사전검증: 기존311 범위를 포함한330검사 통과, 오프라인15/사후3 통과, fake132수집·
가림검토 스키마/대응집계·provider 중단·응답 선봉인·중복 거부·시계 재사용 금지·강제 정리 통과.
최초 전체 회귀는 긴 임시 경로의 Unix socket8건과 legacy rubric 호환2건에 실패했다.
경로를 짧게 바꾸고 legacy 기본 동작을 복구한 최종회귀330/330을 자격으로 사용한다.
강제 취소 fake의 잔여 lease/응답은 미확정으로 보존한다; 이를0으로 만들지 않는다.

최종 manifest c34fdf6e3a0d20da0e2241a4662d2e28f8670256b37cfdc40f0f1a904e189390.
[검증 receipt](../../../.pokechamp-data/summary-diagnostics/ex025/verification.json)에 source/입력/
기준과 모든 검증 evidence를 연결한다. 과거21793파일 변경0, SDK0.6/canonical 두 submodule
clean, credential0600, 사전 Cloud0이었다.

수집·중단: 132/132응답을451.14초에 확보했으나 검토 초안126건을 봉인한 뒤 통합 input21의
평가 기준이 실제 입력에 없는 Latios 최초HP100/100을 요구함을 발견했다. 기준은
100→51→26→13 전체를 요구하지만 이전/통합 요약은51→26→13만 제공하고 원문window는
event146 이후여서 최초event10 line5가 없다. 사전 검증이 이 요구 사실의 입력 누락을
검출하지 못했다. D-028/C-017의 전체 중단 규칙으로 유효 검토0·효과추정 없음으로 처리했다.

예정/intent/제출/응답132, provider 실패/미실행/미확정0. 무효 검토 초안126(960사실판정),
미검토6, 유효 대응0/22입력·0/6원배틀이다. 기준 완화·입력 제외·재제출·source 수정은 없다.
비용·분모·중단·정리 보고는 완료했지만 유효 검토/재발/대응비교가 미완료여서 위 진단 완료
체크는 충족되지 않았다. 이 plan을 completed로 이동하지 않는다.

[중단 보고서](../../../.pokechamp-data/summary-diagnostics/ex025/closure.md),
[발견 증거](../../../.pokechamp-data/summary-diagnostics/ex025/input-evaluation-discovery.json),
[보존·정리 검증](../../../.pokechamp-data/summary-diagnostics/ex025/preservation-cleanup.json),
[최종 봉인](../../../.pokechamp-data/summary-diagnostics/ex025/closure-seal.json).
과거21,793파일·현재source130·사전증거1,524 불변과 worker/permit/port/credential/SDK/submodule을
확인했다. 최초 제출부터 무효 보고까지63.87분으로4시간 안이며, 과거 EP-011/012/013
Blocked와EX-020~024의 halt·시계는 그대로다.
