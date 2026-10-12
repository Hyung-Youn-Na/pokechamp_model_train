# EX-036 — 원본 A 대 변경 구성 B 직접 대결32경기

- 상태: Stopped — 계산 결함 중단, 직접비교 미완료
- 날짜: 2026-09-11
- 관련: D-042, EP-030

## 사전등록

2026-09-11 현재 사용자가 제공한 직접 대결32경기 계획의 구현·검증·유료 실행을 승인 근거로 삼는다.
EX-033 A 원본 입력/프롬프트/IO 파싱 재질의/fallback과 B 개선 입력/계산기/calculator-input-v2/
battle-v1.2.0/mechanics-v2/출력복구를 유지한다. 최근 진단 오류를 수정하지 않는다.
공통 glm-5.3-flash/low/temperature0/model seed100/출력131072/provider 기본 context,
요약·외부 메모리·추가 모델 심사0이다.
b01 팀1/2, b02 팀6/2, b03 팀2/6, b04 팀6/12 각각 새 seed4×배정반전2=8경기다.
16대응쌍에서 팀 위치·게임 seed·진영별 actor seed를 고정하고 A/B만 교환한다.
master seed20260911와 EX036의 SHA-256으로 seed와 쌍/쌍내 순서를 생성·봉인한다.
b02/b03은 동일 팀 조합의 방향 반전이다. 각 조건은32경기에 참여한다.
독립 ab-head-to-head32-v1 정책과 ab-head-to-head prepare/run/report CLI, actor_conditions를 추가한다.
EX-035 원자 예약·시계·격리·수집을 확장해 양쪽 모든 요청을 공통 원장에 기록한다.
actor별 관측/입력/계산은 별도 process와 bundle로 격리한다. 상대 숨김정보/계산 공유0이다.
최초 유료 요청부터20700초 수집,21600초까지 보존·정리,공통8000요청(실패/미확정/A 재질의 포함).
watchdog3600초,HTTP min(300초,잔여 수집시간),배틀/계정/모델 동시성 각10이다.
실행 identity에 원장/시계를 결합하여 재시작/새 폴더 초기화 금지,slot1회/provider retry0/보충0/재수집0.
로컬 검증+실제 worker fake32 후 본 실험 첫10경기의 설정/실제입력/원장/격리/증거를 검사하고
통과하면 동일 시계로22경기를 진행한다. 별도 유료 smoke/gate0이다.
출력 오류는 기존 구성별 복구,provider/timeout/경기별 환경 실패는 해당경기 실패이며 상대 승리0이다.
공유 입력/계산/설정/무결성/permit 결함은 영향범위 중단,불명확하면 잠재 전체 중단한다.
C-018/RESEARCH_DESIGN §11.1 보존·영향조사 적용,수집중 source/기준 고정·유료 재수집0이다.
주지표 B의 A상대 승률과(B승+0.5무)/유효경기, A·블록·팀배정별 결과를 함께 보고한다.
양쪽 유효 대응쌍은 두 경기 B점수 평균,불완전쌍은 개별 결과 보존/대응분모 제외/누락표시한다.
예정/시도/유효완료/실패/무효/미실행,A/B별 요청/token/지연/fallback/경기길이를 보고한다.
양쪽 모든 결정을 실제입력/전체원응답/선택출처/전송/결정직전 공개prefix에 연결하여 전수검토한다.
사실·규칙 오류/입력문제/출력·실행실패/전략미확정을 분리하고 승패로 오류·원인을 판정하지 않는다.
유효32/32·완료쌍16/16만 직접비교 완료다. 중단 시 실제분모/미완료 사유와 수집분 검토/보존/정리까지 한다.
32상태·양쪽viewer·전수검토·직접대결보고서·원자료봉인·보존/정리가 산출물이다.
EX-033 두 전체 구성의 직접대결이며 프롬프트 단독이나 L1–L5 효능으로 해석하지 않는다.
기존 실험/봉인/6개 Blocked는 보존한다.

## 실행 진입

전체668회귀(293.66초),정적 검사,EX-033 입력/처치 대조·팀/hash/seed/경계 검증 통과.
실제 worker fake32는32/32·16/16대응,1961결정·1860요청/응답·미확정0,최대배틀10·474소유프로세스 정리 통과.
source180개를 고정하고 verification.json의 fake32 증거를 봉인한 뒤 본32 실행을 시작한다.
경로: `.pokechamp-data/ab-head-to-head32/ex036`, 양측 bundle은 `.pokechamp-data/experiments/ex036-cloud`.

## 결과·중단·검토

첫10경기 중 B의 turn25 입력 계산에서 `unsupported active effects: ['PROTECT']`가 발생했다.
turn24 Protect가 Gigaton Hammer를 막아 발생한 `-activate`를 상속 parser가 효과로 저장하고,
다음 턴에 제거하지 않은 상태를 유지한 B 계산기가 거절했다. provider 호출 전 실패이며
EX-033 처치를 변경하거나 유료 재수집하지 않았다. 잠재 공유 결함으로 진행·후속경기를 전체 중단했다.

예정32·시도10·유효1·실패9(원인1+동료취소8)·무효0·미실행22·완료대응0/16이다.
완료 `b02-r4-s0`은19턴 A승/B패다. 해당 효과와 수집 무결성 문제는 완료경기에서 확인되지 않아
개별 결과를 보존한다. A승률1/1·B승률0/1·paired B mean null이며 성능 우열을 결론내리지 않는다.

529요청(A260/B269)·529응답·미확정0, 입력37,559,074/출력129,466 token이다.
첫 유료 요청부터 batch 종료까지20.94분,배틀/계정/모델 최대 동시성10이었다.
553판단과529응답의 전체 원문·reasoning을 검토하고 actor별 실제 입력·직전 공개prefix·선택·wire에 연결했다.
540개 선택이 전송과 일치했다. B 출력복구33,양쪽 fallback0,취소로 미전송된 응답10개는 모델 실패와 분리했다.

양측20bundle·source180·기존99,459파일(기존데이터99,453+기존Blocked6) 불변 검증,
142관측process 종료·포트/작업트리/runtime lock/permit 반환·submodule clean을 확인했다.
중단 보고·정리는 완료했지만 유효32/32·완료대응16/16 미충족으로 EP-030은 Blocked다.

- [직접대결 최종 보고서·32상태·양쪽 viewer](../exec-plans/evidence/ep030/final-report.md)
- [원인·영향 분석](../exec-plans/evidence/ep030/failure-analysis.json)
- [553판단 검토 연결](../../.pokechamp-data/ab-head-to-head32/ex036/review.json)
- [사용량·지연 분모 보정](../exec-plans/evidence/ep030/condition-metrics.json)
- [보존·정리](../exec-plans/evidence/ep030/preservation-cleanup.json)
- [최종 봉인 목록](../exec-plans/evidence/ep030/final-manifest.json)
