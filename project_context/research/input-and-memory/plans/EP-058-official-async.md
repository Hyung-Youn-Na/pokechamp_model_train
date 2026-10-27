# EP-058 — 공식 관측 비동기 처리 교정

- 상태: Completed
- 생성일: 2026-09-17
- 책임자: Codex
- 승인: 현재 사용자의 계획 구현 지시, [D-068](../decisions/D-068-official-async.md)
- 계약: [C-043](../CONTRACTS.md#c-043-official-observation), INDEX workflow, RD11.1/C-018

## 목표·범위

공식 타이머 양보 후 지정 행까지 종료 처리를 기다리고 오류에는 입력 생성을 차단한다.
EP-030/032/035/041/044/045/048/053/054/057의 중단·원자료·수집 source는 보존한다.
공식 upstream/build/schema/prompt/계산 의미는 유지하고 연결 source만 새 해시로 구분한다.
Python 동기 API와 요청 전체30초 제한, Node 직렬 명령·실패 부분 상태 폐기·실패 계측을 유지한다.

## 완료 기준·검증

- [x] 실제 EX-045 두 실패 결정3의 통제 지연 재현 및 정상/지연·증분/전체 상태·정규화·계산·B2 동등성
- [x] 반복/마지막 행 양보·request 순서·슬롯·동일 턴 교체·battle 격리·16actor 동시 재생
- [x] 영구 정지·타이머 예외·Node 종료·연속 명령·처리 중 종료·기존 경계 회귀
- [x] 최종 source 관련 검사·전체 integration·EP-056 100경계 및 EX-045 12시도 생성 관측 전수 재생
- [x] 실제 coordinator/worker/공식 관측/계산기 무유료8경기 동시 실행·공급자별 HTTP4·16actor·정리
- [x] 한국어 보고·지연/메모리/분모/한계·코드/검증/viewer 봉인·과거 보존·상태 갱신

## 로컬 실행 조건·중단

EX-045 후속 첫8행의 팀/seed를 별도 로컬 identity에서 한 번씩 실행한다. HTTP만 모의화한다.
cloud에서는 로컬 모드를 거부하며 본실험 첫4 gate 우회로 노출하지 않는다.
경기당1200초·전체1800초(마지막60초 강제 정리), 자동 재경기/유료 호출/과거 재개0.
성능 비교 실험이 아닌 기술 검증이다. RD11.1/C-018의 증거 보존·영향 조사 적용,
검증 실패는 보존하고 완료로 판정하지 않는다. 로컬 경기 재수집 허용0.

## 진행·증거

- 2026-09-17 관련 원문·겹치는 active plan 확인 후 구현 전 등록. 증거: ../evidence/ep058/.

- 실제320ms 지연 최초 검사에서 scene stub interruptionCount=NaN이 공식 타이머 동일성 검사를 실패시켜 영구 정지를 유발함을 추가 확인. 연결부에서 실제 BattleScene과 같은 카운터1로 초기화한다. upstream/build/시계는 변경하지 않는다. 최초 실패 로그 async-v1 보존.
- 관련54검사 통과. 정상/지연/전체 재생의 두 실제 실패 결정3에서 공식 상태·정규화·계산 요청/결과·B2 문자열 일치, 구 source의 결정3 오류 재현. 실제 player의 timeout/타이머 예외는 관측·계산·HTTP 이전 차단. 동일 턴 교체·연속 실패 명령 폐쇄도 별도 검증했다.
- 진단 JS가 직렬화 전 snapshot 객체 참조를 모아 이전 결정 표시가 뒤 상태로 변하는 검증 harness 결함을 확인했다. 운영 JSON 전송처럼 즉시 직렬화하도록 진단만 교정하고 새 source-final.json(295파일)로 고정했다. 첫 전체 검사는320통과 시 중단, 진행 중 보존 감사도 중단 보존했다. 이를 최종 source 통과로 재사용하지 않고 최종 전체 integration/정상·지연 전수 감사를 새 경로에서 수행 중이다.
- 최종 source의 EP-056 정상100경계 통과. EX-045 생성 관측 전수와 지연 재생 및 전체 integration은 진행 중이며 로컬8경기 아직 미시작·유료 호출0이다.

## 최종 결과 — 2026-09-17

최종295source에서 전체 고유1,344검사(전체1,340 + 설정 누락으로 건너뛴 기존4의 별도 실행),
EP-056 100/EX-045 330생성 관측의 정상·지연 재생,402개 배틀 계산/B2 동등성을 통과했다.
실제 실패2결정의 과거 오류 재현·새6연결 기록, 실패 시 player 호출0·16tracker 동시성도 확인했다.

로컬8/8경기가 각1시도로 정상 종료(255–320초)했고,421관측·413모의 HTTP를 전수 감사했다.
실측 최대8경기·16actor/관측 Node·공급자 HTTP4+4,744.16초에 실행/감사/자원 정리 완료.
새 identity ep058-local-eight 및 모의 HTTP만 사용했으며 본 gate 생성/유료 호출/재경기0이다.
원자료를 읽는 독립 요약의 viewer 키 조회 오류는 실제 bundle 경로로 교정하고 원본 로그를
보존했다. 경기·판정 기준 변경이나 재실행은 없었다.

과거45,997파일·EX-045 수집291source·upstream/build 보존, 소유 프로세스/포트/worktree/
socket/permit·runtime lock 반환을 확인했다. 한국어 보고·독립 로컬8분모 viewer·desktop/mobile
브라우저 검증을 마치고5,275개 산출물을 봉인했다. 추가 실행·감시는 없다.

[최종 보고](../../../exec-plans/evidence/ep058/report.md) · [검증 viewer](../../../exec-plans/evidence/ep058/index.html) ·
[완료 기준](../../../exec-plans/evidence/ep058/final-verification.json) · [봉인](../../../exec-plans/evidence/ep058/final-manifest.json).
이번 수정 작업은 Completed이며 EX-045 비교 미완료·EP-057 Blocked와 원자료/중단 판정은 유지한다.
