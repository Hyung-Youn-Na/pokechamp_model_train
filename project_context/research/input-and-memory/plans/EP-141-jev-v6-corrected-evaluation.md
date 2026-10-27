# EP-141 — 교정 v6의27B/9B 신규64평가

- 상태: Completed
- 생성일: 2026-10-13
- 완료일: 2026-10-14
- 책임자: Codex
- 승인: 사용자의 수정본 새64경기 명시 승인/재개 지시 / D-136
- 관련: [C-067](../CONTRACTS.md#c-067-jev-public-memory-v6),
  [EX-088](../experiments/EX-088-jev27b-v6-corrected.md),
  [EX-089](../experiments/EX-089-jev9b-v6-corrected.md)
- 연구선/branch/checkout: `research/model-training` / `/workspace`
- 시작 commit: `a4659bf298c7935714f9fbd25246db2d831c5926`; 기존 미커밋 변경·자료 보존

## 범위·보존

교정 완료된 v6로 새64경기를 실행하고 감사·3종 비교·뷰어·봉인·반환까지 수행한다.
실험 조건은 EX-088 공통protocol/EX-089 모델 차이를 따른다. EX-086/087/EP-140의
Blocked·원자료·당시 소스·사후교정·뷰어·봉인은 불변이며 기존 출력을 덮어쓰지 않는다.
INDEX/CHARTER·매뉴얼·STATUS/색인과 이전에 확인한 겹치는 active EP-013/062/064/075/077/080/134
및 새 중단EP-140의 보존 경계를 확인했다. 환경·가중치·후보/정책·설계 기준을 바꾸지 않는다.

실행기의 새ID/코호트 연결과 독립적인 공개이벤트 coverage 점검을 서브에이전트에 분리 위임한다.
파일 소유권·통합·핵심 수정 검토·실제GPU 실행·완료 판단은 주 에이전트가 담당한다.
이미 제공된 계획/교정 논의로 설계 토론을 대신하며 관련 행동 중심 검사와 리뷰를 수행한다.

## 완료 기준

- [x] 새 승인·ADR/EX/EP와 domain authority 연결
- [x] 새ID/순서·기준선/비교·출력/예산·원자료 보존 경계 연결 및 CPU 검증
- [x] 공유 결함의 실제 공개prefix CPU coverage 확인·두 모델 준비/길이 검증
- [x] 27B 단일 적재/8사전추론·신규32경기/16쌍
- [x] 9B 단일 적재/8사전추론·신규32경기/16쌍
- [x] 경기별 감사·종료 완전성/산술·3비교·전수내보내기/대표 오프라인검사
- [x] 모든 쓰기 종료 후 봉인·GPU/잠금/포트 반환·최종보고/문서 갱신

## 진행·증거

- 2026-10-13 — 사용자 승인으로 EX-088/089를 새로 등록했다. 실제 새GPU/경기0.
- 근거는 `project_context/exec-plans/evidence/ep141/`와 각EX 새run에 보존한다.
  기존 ep140은 봉인됐으므로 새 파일을 쓰지 않는다.
- 새 코호트/모델·formatter·선행평가/CPU재사용·프로토콜/사용량 연결86검사,
  새/기존ID 뷰어 내보내기3검사와8요청서버 검증 모의11검사를 통과했다.
  27B/9B 모델과4GPU 배치·한도를 유지하고 출력과 선행 관계만 새 코호트로 분리했다.
- EX-08532경기/EX-083 고유32경기의 공개prefix1,958관측을 원actor/cutoff에서 facts만
  CPU 재구성해 모두 통과했다. 실제sidestart39행/26경기를 포함한다. 실제 자료에 없는
  sideend/Transform 등은 합성검증과 구분하며 기존 성적 재감사·피해계산·GPU호출0이다.
  [coverage 보고](../../../exec-plans/evidence/ep141/public-prefix-coverage/report.md).
- 두 모델 최종prepare를 완료했다. 동결source CPU263통과/별도브라우저환경1skip,
  새코호트9B에는 같은source의27B CPUreceipt를 연결해 재사용했다.8사전입력의 최장은
  각17,271토큰·무절단이며 등록범위의 디스크는 약87.8GiB다. EX-088의 단일 본서버
  적재/8추론 검증을 시작했다. 본수집source는 고정한다.
- 2026-10-14 — EX-0888사전추론 통과: 반복선택 동일·확률 최대차이0·allocated동일/reserved비증가,
  실제4GPU배치/후보 연결/한도를 확인했다. 같은 서버로 신규32경기 수집에 진입했다.
- 사용자 후속 지시로 실시간 수동 조회/턴별 보고를 단계 알람으로 전환했다. 기존 자원 상한
  자동감시는 유지한다. 동결source 밖 `evidence/ep141/alarms/watch.py`의 별도 감지기가
  사전검증·수집 종료·오류·최종 종료와 프로세스 identity만 읽고, 현재 대화로 중복 없이 알린다.
  EX-088 최종 봉인·프로세스 종료·공유 무결성/자원 반환 조건이 만족되면 이미 승인된 EX-089를
  한 번 자동 시작한다. 알람 응답을 실행 gate로 삼지 않으며 수동 중복실행/재개를 금지한다.
  감지기는 원run/source를 쓰지 않고 자체 출력은 별도 알람 폴더에 둔다. 모델 호출 없이
  조건/중복/종료8검사와 현재 대화 전달 검사를 통과했고 두 prepared source의 불변을 확인했다.
  [설정/기동](../../../exec-plans/evidence/ep141/alarms/launch.json) · [전달 검사](../../../exec-plans/evidence/ep141/alarms/delivery-test.json).
- 사용자 요청으로 EX-088의 감사 완료 첫경기만 별도 미리보기로 내보낸다. 첫경기 audit의
  event_range와 events/outcome digest를 기준으로 완료된 기록만 복사하며 진행 중 원run이나
  동결source·최종뷰어 경로를 수정하지 않는다. 실제 파일은 예산에 포함된
  `evidence/ep141/preview-ex088-first/`에 두고 `exports/battle_viewers/ex088-sample-first`로 연결한다.
  저장입력/응답/명령·공개턴로그/cutoff를 대조하고 샘플1화면의 오프라인 열람을 확인한다.
  이 샘플은 사용자 요청에 따른 별도 열람본이며 본 실험의 최종 집계/검증을 대신하지 않는다.
- 첫경기 샘플 내보내기를 완료했다.25턴 승리·37결정/36모델호출/1자동 선택·공개331행이며,
  감사가 고정한417이벤트와 원문41파일·전결정/턴cutoff를 대조했다. 이동 후1대표화면에서
  요약·원문 복사/다운로드·결정전cutoff·턴 탐색을 확인하고 별도 사본/뷰어/근거를 봉인했다.
  진행 중 원run/동결source 수정·새모델호출0이며 알람 방식은 유지한다.
  [샘플](../../../../exports/battle_viewers/ex088-sample-first/index.html) ·
  [검증](../../../exec-plans/evidence/ep141/preview-ex088-first/completion.json).
- 추가 사용자 요청으로 요청 시점까지 감사 완료된 EX-088 경기들을 고정한 별도 미리보기를 만든다.
  경기별 audit의 event_range/digest와 완료 outcome을 재사용해 원문/전결정/턴cutoff를 대조하며
  현재 진행 경기는 포함하지 않는다. 기존 첫경기 샘플·동결source·최종뷰어 경로는 보존한다.
  파일은 예산에 포함된 `evidence/ep141/preview-ex088-completed-<완료수>/`에 저장하고
  `exports/battle_viewers/ex088-preview-<완료수>`로 연결한다. 샘플 시점/포함 분모를 명시하고
  원문 대조·오프라인 탐색 확인 후 해당 사본만 봉인한다. 본실험과 단계 알람을 변경하지 않는다.
- 완료 경기 미리보기는 2026-10-14 10:20 KST에 고정한15경기(6승0무9패)로 완료했다.
  저장454결정/436모델호출/18자동선택·공개4,419행과 원문500파일을 대조했다.
  각 경기 감사가 고정한1–5,104이벤트만 복사했고 원prefix 불변을 확인했다.
  이동 후 오프라인 목록·첫/마지막 경기2화면에서 요약/원문/결정전cutoff·턴 탐색을 확인했다.
  별도 사본/뷰어/검증 근거를 봉인했으며 추가 모델호출·진행 중run/source 변경0이다.
  [15경기 목록](../../../../exports/battle_viewers/ex088-preview-15/index.html) ·
  [검증](../../../exec-plans/evidence/ep141/preview-ex088-completed-15/completion.json).

- 단계 알람의 EX-088 완료 기록에서32경기/16쌍·최종 감사·전수내보내기·대표5화면
  오프라인 검증·봉인/반환 통과를 확인했다.15승17패이며 저장880결정·공개8,748행을 보존했다.
  수집849추론·사전8추론·단일서버 적재1회·중복0이며 종결 시점 소유GPU/잠금/포트를 반환했다.
  [전체 뷰어](../../../../exports/battle_viewers/ex088/index.html).
- 전용 감지기가 EX-088 종료 조건을 확인해 EX-089를1회 자동 시작했다. EX-089의
  entry-gates 기록에서CPU/길이 검증·서버 적재1회/사전8추론·반복 선택/확률 동일·메모리
  검증 통과를 확인했다. 최장17,271토큰이며 같은 서버로 본수집에 진입했다.
  실시간 수동 조회/대기·수동 중복실행 없이 단계 알람 방식을 유지한다.

## 중단·완료

INDEX 공통기준·RD11.1/C-018·RD11.2/C-046과 EX-088의 공유/모델 한정 중단 범위를 따른다.
본수집source 변경·재경기·보충·자동재개0이며 실제 목표 미달을 Completed로 바꾸지 않는다.

## 최종 종결

EX-088/089의 각32경기·16쌍과 모든 완료 기준을 충족했다. EX-089도6승26패·저장1,139결정/
공개11,036행·원문1,240파일·모델별5대표 오프라인 화면 검증을 완료했다.
두 실행은 실패/무효/미실행0이며 새 추론은 본수집1,950회+사전16회다.
원자료·완료 receipt의 연결과 공통 유효쌍 비교/산술의 독립 확인을 통과했다.

모든 run writer가 종료한 뒤 두run/collection/viewer의 전체 목록·봉인을 확인했고
동결source714파일은 현재 구현과도 일치했다. GPU0–3 각각0MiB·GPU프로세스0·잠금/포트
반환과 두 controller·알람 감지기 종료를 확인했다. 추가 경기·재개·모델호출0이다.
EX-086/087/EP-140의 기존 Blocked는 보존한다. 일반 성능 개선을 주장하지 않는다.

[최종 보고](../../../exec-plans/evidence/ep141/report.md) · [완료](../../../exec-plans/evidence/ep141/completion.json) ·
[3종 비교](../../../exec-plans/evidence/ep141/final-comparisons.json) ·
[봉인 검증](../../../exec-plans/evidence/ep141/final-integrity.json) · [반환](../../../exec-plans/evidence/ep141/closure.json).
완료 본문은 `completed/`로 옮기고 동결 실행기/기존 참조의 `active/` 경로는 호환 링크로 유지한다.
