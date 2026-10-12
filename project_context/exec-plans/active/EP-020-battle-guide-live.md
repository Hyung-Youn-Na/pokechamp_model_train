# EP-020 — 필드 설명서 실제 Cloud 병렬 배틀

- 상태: Blocked — 구현·로컬 검증·중단 보고 완료, Cloud 기술 gate 실패로 실제 비교 미완료
- 생성일: 2026-09-09
- 책임자: Codex
- 승인: 현재 사용자 계획 전체, D-032. 유료 Cloud90·smoke8·compare32와 명시된 복구 포함.
- 관련: [D-032](../../decisions/D-032-battle-guide-live.md), C-018/C-020, [EX-027](../../experiments/EX-027-battle-guide-live.md).

## 목표·범위·불변 조건

A는 upstream IO·fallback, B는 교정 관측·고정 prior·계산기·필드 설명서 v1.1.0이다.
B 요약·통합·메모리 주입0. 모델 glm-5.3-flash/low/temperature0/seed100/출력131072/
provider 기본 context, 요청 timeout300초·경기 watchdog1200초·provider retry0을 유지한다.
`battle-guide-live-v1` 정책을 prepare에서 선택하고 manifest·study·execution·receipt·보고서에
봉인한다. 정책 부재는 D-030이다. 새 정책의 전체 비용·시간·행동 요청 상한은 없으며
요청/시간 상한은 명시적 null이다. 알려진 정책과 identity 일치 없이 null을 인정하지 않는다.
최초 Cloud 시각·요청·실패·미확정·token·경과 시간은 계속 누적한다.

로컬 회귀·운영15장면 의미/입력 도달성·사후피해3·필드완전성/전달·fake32(32/32,
실제 동시10, 격리오류0, 설명서 요청당1회, 요약0; native library thread1) 후
Cloud90(15장면×요청동시성1/10×3반복)을 수집한다. 출력/합법행동90/90, provider오류/
미확정0, HTTP overlap10, 병렬p95≤순차p95×2와 전체 원문/실제입력/계산 대조 검토를 요구한다.
설명 사실·진영·시점·계산 오류는 측정값이며 기술 gate와 분리한다. 오류가 남으면 의미
검증 통과로 표시하지 않는다. 출력·합법행동·입력/증거무결성·검토 완전성은 필수다.

smoke8은 b04 Abyssal/OneStep×양쪽×A/B, 실제 동시8·유효8/8·구성/IO오류0·요약0·격리
검증을 요구한다. 본 비교32는 Abyssal/OneStep×b01–b04×양쪽16대진에 A/B 대응,
EX-016 팀/게임 seed 고정·순서 seed20260908·배틀최대10/계정·모델요청최대10이다.
smoke 기반32판 시간 및50% 여유 추정은 보고용이며 남은 전체 시간으로 진입을 막지 않는다.
smoke는 본 비교에 합치지 않는다.

Cloud 기술 gate 실패는 후속 배틀을 차단한다. 실제 배틀 출력/provider/환경 오류·watchdog은
신규 배틀 제출 중지와 진행 자료 보존·정리를 요구한다. 합법 완료 설명 오류는 승패 제외
사유가 아니다. 모델 오답 재추첨·실험 중 prompt 변경은 금지한다.
D-029/C-018 영향입증·독립재현·수정·회귀 후 복구한다. 입력/처치/수집 재수집 최대1차,
영향 A/B 대응 양쪽·공유영향 전체를 포함하며 누적 gate180/smoke16/compare64를 유지한다.
이는 전체 행동 요청 상한과 별개다. 평가 구현 오류는 온전 응답을 대칭 재평가하고 rubric
교정은 공개된 별도 수정 분석이다. 원자료/halt/최초시계/누적사용량을 초기화하지 않는다.
기존 EX-026 및 모든 실험의 응답·판정·halt·시계·Blocked는 보존한다.

상대별 (승+0.5×무)/유효완료, 두 상대 동일가중 평균, 완료대응 B−A·누락과 예정/시도/
완료/실패/무효/미실행/미확정/복구를 분리 보고한다. B gate·배틀 설명 전수검토의 오류 종류/
근거/분모, A fallback·호출/token/HTTP지연/배치시간/동시성·정리를 보고한다.
전체 B 구성의 개발 대진 탐색적 비교이며 설명서 단독 효과나 L1–L5 전체 효능으로 귀속하지 않는다.

## 완료 기준

- [x] 정책 구현·과거 호환/무제한/검토/무결성/원장/복구 회귀
- [x] 최종 source 로컬15/3·필드/전달·fake32
- [ ] Cloud 기술90 gate 및 전수 검토
- [ ] smoke8/8·compare32/32 및16유효대응
- [x] 수집분18응답 전수 검토·미완료 분석·원자료 보존·정리·상태 갱신

## 진행·증거

2026-09-09: 관련 authority·겹치는 active EP-018/011 확인. 사용자 명시 승인으로 새 등록.
기존 자료는 ../evidence/ep020/preservation.json에 기록. 실행기 정책·복구 지원을 구현/검증한 뒤
Cloud 진입한다. 결함은 EX-027/defects와 이 plan에 원본/수정 identity·영향·재현·회귀를 연결한다.
미충족 완료 기준이 남으면 실제 도달 단계·원인을 기록하며 Completed로 옮기지 않는다.

2026-09-09: 정책 선택/identity·null 상한·clock/journal·복구·receipt·보고서 및 실제
worker의 무기한 batch deadline 경로 구현. 기존 관련58검사, 새 정책23검사 통과.
추가 무네트워크 worker 검사에서 테스트의 broker snapshot 키 오기를 교정했고 전체회귀에 포함했다.
운영15장면/도달성·사후3은 최종 prepare에서 통과. 기존46,757파일 보존 inventory와
13개 변경 source 비교 patch를 evidence/ep020에 기록했다. Cloud0.

최종412회귀(185.44초), Ruff E/F/I/W·compileall·Node13 및 운영15/도달성/사후3 통과.
같은 source145개의 fake32가 유효32/32·실제동시10·격리오류0·요약/통합0·포트정리 통과.
64 actor 봉인과 B400 실제 전달(설명서 각1회), A4850 fake 호출의 설명서0을 독립 검사했다.
[사전 검증](../../../.pokechamp-data/battle-guide-live/ex027-preflight/verification.json) 완료 후
Cloud90 c0 수집을 시작한다. 설명 오류는 전수 측정하며 기술 gate 실패 시 후속 배틀을 차단한다.

## 최종 결과 — 2026-09-09

Cloud18요청/18응답/미확정0,17출력유효·1형식실패에서중단했다. r1 IO-C03이설명과행동JSON을
같은행에출력해마지막별도줄JSON계약을위반했다. HTTP200/정상종료응답이며모델출력오류다.
기술gate미충족으로남은72응답·smoke8·본32미실행,유효대응0/16이며재수집/평가복구0이다.
전체시간·요청무제한정책을유지했고예산소진중단이아니다. 병렬Cloud/p95비율은미검증이다.

18/18원문·실제입력·계산/공개prefix검토를완료했다. 설명오류9/18(사실1·진영0·시점2·계산8,
차원중복포함)과별도출력1건이다. Semantic_review=failed이며설명오류를기술중단사유로쓰지않았다.
출력토큰절단이나입력/처치/수집결함은확인되지않았고18/18입력·prompt·원응답/원장일치를검증했다.
확정입력1,359,923/출력6,402tokens·수집97.61초·부분순차HTTP p50 5.141초/p95 8.830초다.

[최종보고서](../../../.pokechamp-data/battle-guide-live/ex027/final-report/report.md),
[전수검토](../../../.pokechamp-data/battle-guide-live/ex027/gate-review.json),
[종료검증](../../../.pokechamp-data/battle-guide-live/ex027/closure-verification.json):
기존46,756파일과5개기존Blocked불변·source145·64 actor봉인·216sidecar·credential1224파일유출0,
pinned submodule/포트/runtime lock/permit/소유worker정리통과. 최초시계·halt를보존했다.
최초정리검사호출은here-document를담은자기부모shell을worker로오인했다. 그로그를보존하고
동일검사파일의독립호출에서잔여worker0을확인했다. 실험입력·실행·평가에는영향이없다.

90기술gate·smoke8/8·본32/32·16유효대응이남아Completed로옮기지않는다. 전체B구성개발대진의
탐색비교는미완료이며설명서단독효과나L1–L5효능결론은없다.
