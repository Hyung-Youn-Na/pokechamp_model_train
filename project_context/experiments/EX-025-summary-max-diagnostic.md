# EX-025 — 요약 thinking low/max 진단

- Status: Invalidated — 전체 중단·진단 미완료
- 날짜: 2026-09-08
- 관련: [D-028](../decisions/D-028-summary-max-diagnostic.md),
  [EP-015](../exec-plans/active/EP-015-summary-max-diagnostic.md), C-017.

132응답을 모두 수집했으나 고정 입력에 없는 과거 HP를 평가 기준이 요구하는 오류를 발견해
전체 비교를 무효화했다. 조건별 오류율·보존율·재발·max−low 효과는 산출하지 않는다.
EP-015는 Blocked이며 low/max가 요약 오류를 줄였는지 결론내릴 수 없다.

## 실행 조건과 사전 검증

D-028의 첫 요약8·후속10·통합4 입력에 low/max 각3반복, 총132회를 새로 제출했다.
glm-5.3-flash, v1.1.2, temperature0, seed100, 출력131072, provider 기본 context,
timeout300초, 계정/모델10/10, 재시도0이다. 두 조건은 같은 SDK 호환 어댑터와
바이트 단위로 같은 system/user prompt를 사용하며 생성 응답의 후속 입력 재사용은0이다.

사전330/330검사(기존311 범위 포함), offline15/사후3, fake132 및 중단·선봉인·중복거부를
통과했다. Drought 공개 holder 누락은 최초 Cloud 전 pinned simulator와 과거 봉인 함수를
독립 대조해 수정·재검증했다. 기존125사실·통합46사실과14고정 메모리를 원문 대조·봉인했다.
그러나 이 검증은 아래의 **필수 사실 전체가 실제 전송 입력에 존재하는지**에 관한 결함을
검출하지 못했으므로, 사전 통과 기록을 유효 비교의 자격으로 유지하지 않는다.

[manifest](../../.pokechamp-data/summary-diagnostics/ex025/manifest.json),
[사전 검증 receipt](../../.pokechamp-data/summary-diagnostics/ex025/verification.json).

## 전체 중단 근거

통합 input21의 `history_78_fact02`는 상대 Latios의 공개 HP `100→51→26→13`을 요구한다.
최초100/100의 원문은 event10 line5다. 실제 전송된 원문은 event146–203이며,
이전 요약·통합용3요약은 `51→26→13`만 기록한다. 현재 관측은 기절 HP0이고,
`max_hp=100`·`level=100`이나 과거 event ID 목록은 최초 HP 관측을 제공하지 않는다.
이 입력의6개 실제 HTTP body가 같은 누락을 포함함을 대조했다.

원문 정답의 진실성과 고정 요약에 쓰인 주장들의 근거를 검증했지만, 각 요구 사실의 모든
구성요소가 실제 전송 입력에서 도출 가능한지에 대한 검증이 불충분했다. 없는 과거 값을
추측하지 않는 응답을 모델의 누락 오류로 셀 수 있으므로 이는 모델 결과가 아닌 입력·평가
기준 불일치다. 검토자가 조건별 지표를 열기 전에 전체 halt를 봉인했다.

[발견 증거](../../.pokechamp-data/summary-diagnostics/ex025/input-evaluation-discovery.json),
[halt](../../.pokechamp-data/summary-diagnostics/ex025/halt.json),
[최종 중단 보고서](../../.pokechamp-data/summary-diagnostics/ex025/closure.md).
이 실행에서 입력·기준·프롬프트·source 수정, 입력 제외, 재채점으로 유효 비교 복구,
추가 Cloud 호출을 하지 않았다.

## 분모·비용·보존

예정132·intent132·제출132·응답132, provider 실패0·미실행0·미확정0이다.
조건 비공개 검토 초안126/132(960개 사실 판정)을 보존하고 마지막6개 검토는 중단했다.
전체 무효이므로 유효 검토0, 유효 입력 대응0/22, 유효 원배틀 대응0/6이다.
물리적 응답 누락은0이며, 무효 초안126과 미검토6을 구분한다.

|조건|제출/응답|입력 tokens|출력 tokens|HTTP p50|HTTP p95|
|---|---:|---:|---:|---:|---:|
|low|66/66|1,948,794|88,007|8.199초|11.898초|
|max|66/66|1,948,794|565,887|39.123초|116.808초|

총4,551,482 tokens이며 usage 미확정0이다. 이는 provider가 보고한 사용량으로 금액이나
서버 내부 추론량의 직접 측정이 아니다. 실제 수집451.14초, 최초 제출부터 무효 보고까지
63.87분이다. 모든 응답은 HTTP200·반환 model glm-5.3-flash·done_reason stop이다.

[보존·정리 검증](../../.pokechamp-data/summary-diagnostics/ex025/preservation-cleanup.json)에서
기존21,793파일·130 source·1,524 사전 증거 불변, 실제 직렬화132/응답132,
SDK0.6 배포10파일 및 canonical submodule clean, worker132 종료·permit0·runtime lock 반환,
loopback8000/8100–8109 사용 가능, credential0600/18,615파일 유출0을 확인했다.
과거 EX-020~024 자료·halt·시계 및 EP-011/012/013 Blocked는 보존했다.

검토·대응 비교 완료 기준을 충족하지 못했으며, 중단 처리와 보존 완료는 진단 완료를 뜻하지
않는다. 운영 적용·IO 재개·실제 배틀은 수행하지 않았다.
[최종 봉인](../../.pokechamp-data/summary-diagnostics/ex025/closure-seal.json)에 상태 문서와 종료 보고를 연결한다.
