# EX-027 — 필드 설명서 v1.1.0 실제 Cloud 병렬 배틀

- 상태: Stopped — Cloud 출력 계약 실패, 실제 비교 미완료
- 생성일: 2026-09-09
- 책임자: Codex
- 관련: [EP-020](../exec-plans/active/EP-020-battle-guide-live.md), [D-032](../decisions/D-032-battle-guide-live.md).

## 설계·승인·복구

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

## 환경·격리·증거

현재 worktree source hash·pinned submodule·모델/실행 설정을 준비 receipt로 봉인한다.
새 .pokechamp-data/battle-guide-live/ex027 study와 별도 actor store를 사용하며 과거 표본은 포함하지 않는다.
원장/clock·stage claim·cohort별 source identity와 복구1차 검증 전 Cloud를 시작하지 않는다.
별도 ../exec-plans/evidence/ep020/에 보존·회귀·종료 증거를 둔다.

## 결과

412회귀·운영15장면/사후3·fake32(32/32·실제동시10·B400전달·요약0)는통과했다.
Cloud90중18요청/18응답/미확정0에서마지막별도줄JSON계약위반1건으로중단했다.
출력유효17/18·provider오류0·HTTP200 18/18,재수집/평가복구0이다.
순차구간만실행되어HTTP overlap10/병렬p95비율은미검증이다. 수집97.61초,
부분순차HTTP p50 5.141초/p95 8.830초,확정입력1,359,923/출력6,402tokens다.

18응답원문·실제입력·계산근거전수검토에서설명오류9/18(50%)을확인했다.
차원중복포함사실1·진영0·시점2·계산8이며별도출력형식오류1건이중단원인이다.
사전rubric유지·입력/응답무결성18/18·설명서요청당1회·요약0을확인했다.

나머지gate72·smoke8·본32미실행,본비교A/B각예정16/시도0/유효0/실패0/무효0/미실행16,
대응0/16·누락16이다. 승률·상대별가중평균·B−A·smoke기반시간추정은산출하지않는다.
통화청구액은provider응답에없어미산출이다. 전체시간/요청상한때문에중단한것이아니다.

원자료·halt·최초시계·기존46,756보호파일·5개기존Blocked를보존했다. source145일치·
64 actor봉인·216sidecar·credential1224파일유출0·포트/runtime lock/permit/소유worker정리를확인했다.
EP-020은Blocked이며실제배틀비교/설명서단독효과/L1–L5효능결론은없다.

- [최종보고서](../../.pokechamp-data/battle-guide-live/ex027/final-report/report.md)
- [18응답전수검토](../../.pokechamp-data/battle-guide-live/ex027/gate-review.json)
- [실제입력/응답감사](../../.pokechamp-data/battle-guide-live/ex027/actual-input-response-audit.json)
- [종료검증](../../.pokechamp-data/battle-guide-live/ex027/closure-verification.json)
- [사전로컬검증](../../.pokechamp-data/battle-guide-live/ex027-preflight/verification.json)
