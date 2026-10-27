# EX-021 — 요약 오류의 harness 기여도 비교

- Status: Blocked (invalidated / 진단 미완료)
- 날짜: 2026-09-08
- 관련: [D-023](../decisions/D-023-summary-harness-diagnostics.md),
  [EP-012](../plans/EP-012-summary-harness-diagnostics.md)

## 실행 전 protocol

동일 모델·장면에서 의미 명확화와 반복 request 축소의 기여를 분리한다.
H0=EX-020 봉인 코드 원본, H1=의미 주석, H2=가역 request 변경분, H3=둘 모두다.
모든 조건의 원본 정보·전략·summary system prompt를 유지한다. 모델 glm-5.3-flash,
temperature0, seed100, thinking low, 출력131072, provider 기본 context를 고정한다.
첫10행동 후 이전 요약 없는 첫 경계만 사용한다. EX-016 io 관점의 기존4장면
(Abyssal b01-s1/b04-s1, OneStep b03-s0/b04-s0)과 추가8장면
(Abyssal b01-s0/b02-s1/b03-s1/b04-s0, OneStep b01-s0/b02-s0/b02-s1/b03-s1)을
분리한다. 추가 장면은 EX-020 요약 준비 경기 전체를 제외하되 같은 개발 자료임을 명시한다.
12장면×4조건×3반복=144호출; 순서 seed20260908로 장면을 섞고 조건 위치를 균형 교대한다.
반복 seed는 동일하며 장면을 독립 단위로 삼는다. 요청/모델 permit10/10, retry_transient=0.
첫 Cloud 제출부터1시간,45분에 신규 제출 중지하고15분간 보존·정리한다. 재시작으로
시계를 초기화하지 않고 미확정 응답/token을0으로 대체하지 않는다.

의미 주석은 원본을 유지하면서 상태 숫자의 의미, 실제 protocol 내부 턴, 원본 행 참조,
관측 HP 전후·정밀도·피격/기절 연결만 추가한다. 패킷 끝의 턴으로 앞선 행동을 덮어쓰지 않는다.
피해 예측·미래·상대 비공개 정보·평가 정답 문구를 입력하지 않는다.
request는 첫 값과 변경/삭제 연산으로 원래 JSON 값 전체를 복원하며 비요청 protocol 순서를 보존한다.
H1/H3의 의미 주석은 동일하다. 정답은 변환과 분리하여 원본 이벤트에서 작성·봉인한다.

주지표는 중요 사실 오류·필수 사실 누락·출력 형식 위반 중 하나 이상인 요약 비율이다.
HP·생존·피격 횟수·actor identity·효과 시점·공개 상태를 필수 평가하고, 전체 사실 주장 오류,
근거 없는 단정·내부 모순·필수 사실 보존율도 기록한다. 최적 행동은 채점하지 않는다.
조건명을 가린 응답을 원자료/사전 rubric에 대조하며 추가 Cloud 채점은 없다.
장면별3반복을 먼저 집계하고 H0↔H1/H2↔H3, H0↔H2/H1↔H3, H0↔H3와 결합 차이를
대응 비교한다. 기존4/추가8을 따로 보고하며 오류 감소와 누락 증가를 함께 확인한다.
조건별 실제 token·HTTP 지연·배치 경과, 예정/제출/응답/실패/미실행/미확정·대응 누락을 보존한다.
오류 문장→원본 근거→조건별 재현 횟수→오류·누락 변화→해석 한계 순으로 보고한다.
144호출과 근거 연결 검토 완료가 진단 완료다. 중단하면 미완료 분모를 명시한다.
차이가 없거나 오류가 남았다는 이유로 모델 한계를 확정하지 않는다.

## 실제 결과

사전238회귀·정적검사·fake144 통과 후144/144 Cloud 응답을166.6126초에 수집했다.
예정/제출/확보144, provider 실패/미실행/미확정0. 실행기 output_contract1이며 전체 수기
형식 오류율은 미확정이다. 독립 worker/permit10/10으로 수집했고 실제 배틀·Cloud 채점은 없다.

기존4장면 중3장면의36응답 검토 초안 후 나머지 장면에서 입력 변환 오류를 확인했다.
weather 숫자는 pinned parser가 upkeep마다 갱신한 마지막 이벤트 턴인데 H1/H3가
activation_turn으로 표시했다. scene1은 실제8턴/값10, scene3은 실제3턴/값9다.
H3 응답 R016도 “activation turn 9 per annotation”이라고 인용했다. 직접 영향은
기존2장면×H1/H3×3=12응답(4입력)이며 모델 오류 재현율 측정치가 아니다.
수기 평가 기준도 scene3의 Drought 시작을 다음 턴4로 잘못 적었다.
scene1 기준의 “Value8” 문구 또한 현재 raw10과 혼동할 수 있어 후속 로컬 기준에서 명확히 했다.

입력 변환 오류의 전체 중단 규칙을 적용해 모든 효과 추정을 무효화했다.
검토 초안36/144는 무효로 보존,108/144는 검토 중단, 유효 검토0/144다.
기존4/추가8의 각 대응 비교 유효 쌍0/4·0/8. 주지표·오류/누락 변화·결합 효과는 미확정이며
모델 한계·harness 효과를 결론 내리지 않는다. 조건별 실제 token·HTTP 지연·배치 경과는
아래 보고서에 보존했다. 사후 조건/장면 제외로 결과를 구제하지 않는다.

중단 후 로컬 변환·수기 기준·회귀와 무효 보고서 guard를 수정했지만 봉인된 당시 source,
48입력,122사실 기준,144일정/응답,사전 receipt는 불변이다. 재호출·보충은 없다.
EX-020 halt/receipt/clock과 EP-011 Blocked를 유지한다. 진단은 미완료이며 별도 결정 없이
새 실행이나 운영 적용을 하지 않는다.

## 증거

- [입력·일정 manifest](../../../../.pokechamp-data/summary-diagnostics/ex021/manifest.json)
- [사전 검증 receipt](../../../../.pokechamp-data/summary-diagnostics/ex021/verification.json): 당시 통과 기록, 현재 자격은 halt로 철회
- [144응답 collection](../../../../.pokechamp-data/summary-diagnostics/ex021/collection.json)
- [입력 오류 근거](../../../../.pokechamp-data/summary-diagnostics/ex021/input-transform-failure.json)
- [halt](../../../../.pokechamp-data/summary-diagnostics/ex021/halt.json)
- [무효 검토 초안](../../../../.pokechamp-data/summary-diagnostics/ex021/review-partial-invalid.json)
- [중단 보고서](../../../../.pokechamp-data/summary-diagnostics/ex021/report.md)
- [machine-readable 분모·비용](../../../../.pokechamp-data/summary-diagnostics/ex021/report.json)


종료 검증: 기존214+추가30=244 tests(69.71초), Ruff E/F/I/W, compileall, Node10파일 통과.
사전238통과 기록과 별도로 중단 후 source/재현/검증을
[종료 검증 receipt](../../../../.pokechamp-data/summary-diagnostics/ex021/closure-verification.json)에
연결한다. 이 receipt는 도구 교정·증거 보존 검증이며 EX-021 비교 자격을 복구하지 않는다.
