# EP-029 — Smogon 원본 A64 진단 실행

- 상태: Completed
- 생성일: 2026-09-11
- 책임자: Codex
- 승인: 현재 사용자 계획 전체, D-041.
- 관련: EX-035, EX-034, C-018.

## 목표·범위·불변 조건

원본 A의 EX-034 탐색4팀×anchor2×상대2×팀배정2×반복2의 고정64행을 실행한다.
탐색 S1/H1/R1/W1, 보류 S2/H2/R2/W2 제외. 팀 원문/순서/seed 불변.
A는 EX-033 upstream IO·prompt·파싱 재질의/fallback, glm-5.3-flash/low/temperature0/seed100/
출력131072/provider 기본 context를 유지한다. B 입력·요약·전략 해설·외부 메모리 추가0.
경기 watchdog을 기존1200초에서3600초로 변경한다. 요청 timeout300초 및 남은 수집시간 중 작은 값,
배틀/계정/모델 동시성10, 최초 유료 요청부터20700초 수집/21600초 총시간·8000요청이다.
전송 직전 원자 예약하며 실패/미확정/내부 재질의도 차감한다. 재시작으로 초기화하지 않는다.
slot1회/provider retry0/보충0/유료 재수집0/추가 모델 심사0. 로컬 검증+fake64 후 본64 첫10을
검사하고 공유 결함이 없으면 같은 시계/원장으로54를 진행한다. 별도 Cloud90/smoke8은 없다.
C-018 영향범위 중단, 불명확하면 잠재 전체 중단. 경기별 provider/timeout/watchdog/환경 실패는 격리한다.
수집 중 source/기준 불변, 온전한 자료의 평가 구현 교정은 별도 재평가만 허용한다.
모든 A 결정·무호출·fallback·실패 경기의 실제입력/원응답/선택/전송/공개prefix를 전수 검토한다.
EX-034 protocol v1의 판단/입력/출력·실행 분리, 정보시점 제한·미확정·기회/반대사례·후속가설 기준을 따른다.
정책×배정×과제 성적 및 예정/시도/유효완료/실패/무효/미실행, 사용량/시간/길이/검토율을 보고한다.
유효64/64만 수집 완료이며 미완료 시 실제 분모·사유와 수집분 검토·원자료 봉인·정리를 수행한다.
기존 실험/6개 Blocked/시계/봉인 불변. 전체 bitwise 재현은 주장하지 않는다.

## 완료 기준

- [x] 새 정책/외부 registry/명시64행/actor 전달 및 예산·시계 구현
- [x] A 동등성/경계/결함/관련 회귀와 실제 fake64 검증
- [x] 본64 실행, 첫10 검사 및 같은 원장54 진행
- [x] 수집분 전수 검토·성적/분모/실패/가설 보고
- [x] 원자료 봉인·자원 정리·기존 보존·색인 갱신

## 진행·증거

2026-09-11: authority·기존 active 확인, 구현 전 등록. 유료0. 기존 파일 inventory는 ../evidence/ep029/preservation.json.

구현 중간검증: 독립 a-diagnostic 경로·외부 registry/원문 archive·첫10 검사·원자 SQLite 예약 및
원문 intent/response 선봉인·20700/21600초 경계 구현. 새13검사 통과(원본 EX-033 backend
동일 입력/직렬화/파싱4종, 8000번째 동시예약·8001차단, 실패/미확정/재시작 시계 등).
최초 회귀5실패는 새 watchdog 연결에서 legacy fixture의 config 생략을 허용하지 못한 것으로 교정했다.
이후173통과/1실패/1error는 upstream 상대경로(cwd)와 검사 도중 source 변경의 fixture 충돌이었다.
원래 로그를 보존하고 올바른 pokechamp cwd·고정 source로 관련 회귀를 다시 실행한다. 유료0.

Fake v1: 유효64/64·A2031결정/2031전송·모의1838요청/1838응답·미확정0이다.
첫10 및 전체64의 팀 원문/실제 정규화·입력/옵션/원장·bundle 검사를 통과했다.
검사 결과는 `.pokechamp-data/a-diagnostic64/fake-v1/final-checks.json`에 봉인했다.
실행 중 시계 오류는 없었으나 별도 재현에서 JSON 공개와 sidecar 완료 사이의 읽기 경합을 확인했다.
`clock-race-before.json`은 FileNotFoundError, 교정 후 읽기 잠금은 봉인 완료까지 기다려 정확한 deadline을 반환한다.
예약 영속화 오류도 공유 integrity로 분류한다. 실제 actor PYTHONHASHSEED/네이티브 thread 환경을 bundle에 추가한다.
수집 중 source 수정은 없으며 fake v1 종료·봉인 뒤 수정했다. 수정본 로컬 검사 및 fake v2를 거쳐 유료 진입한다.

Fake v2도 유효64/64·모의1838응답·미확정0·전체64 기술검사 통과였다.
그 뒤 종료된 자료를 보존하고 실패 보고 경로를 보강했다. 전송 전 취소의 본래 범위,
원장 없는 전송 거부와 실제 HTTP 누락의 구별, 강제 종료 actor의 부분 로그·미확정 원장 연결,
원본 정책으로 복구한 출력 오류의 자연종료 분모 유지, 첫10 무결성 실패의 영향분모 기록을 검사했다.
새 Cloud 요청은 원래 EX-035 study-link/plan hash에도 결합하여 새 폴더로 시계를 초기화하지 못한다.
관련233사례 범위에서231개 통과 후, cwd를 요구하는 upstream fixture를 포함한 최종54개
(진단34+원본fallback20)를 올바른 cwd에서 통과했다. 원래 cwd 실패 로그도 보존했다.
Ruff/compile/Node syntax 통과. 최종 source177개로 fake v3를 실행 중이며 유료0이다.

최종 fake v3: 유효64/64·A2031결정/2031전송·모의1838응답·미확정0.
전체64의 원문/정규화 팀·seed/thread·원본 실제 입력·원장·bundle 검사 통과, 미연결 요청/부분 원장/파손 로그0.
관측 소유 프로세스878개 종료, 포트8100–8109·임시 worktree·runtime lock 정리 확인.
승인 진입 근거는 `../evidence/ep029/verification.json`, 기술검사는
`.pokechamp-data/a-diagnostic64/fake-v3/final-checks.json`이다.
동일 source177개와 고정64행을 `.pokechamp-data/a-diagnostic64/ex035`에 준비·봉인했다.
plan SHA256 `5237eb87c37cc1fc3c0c07e627d2b32a76f43d18313136b043031e62b20c74be`.
본64 실행을 시작했으며 첫10 기술검사 뒤 같은 시계/원장으로54를 자동 진행한다.
실행 로그/소유 프로세스 관측은 `../evidence/ep029/cloud64.log`, `cloud64-runtime.jsonl`이다.

본64 첫10 기술검사 통과: `ex035/first10-check.json` passed=true, errors=[], admission_denied=0.
동일 시계/원장으로 나머지54 수집을 자동 진행 중이다. 전략 전수검토는 별도
`../evidence/ep029/reviews/`의 순차 annotation과 시점 제한 view receipt에 누적하며 승패를 보지 않는다.

본64 수집 종료: 유효64/64·A1902결정, 유료1811요청 모두응답·미확정0.
전체64 입력/팀/원장 기술검사와 source177개 불변을 확인했다. 관측869소유프로세스 종료,
포트/작업트리/실행 잠금 해제, 계정/모델 최대10·활성permit0이다.
[수집 검증](../../../exec-plans/evidence/ep029/cloud-collection-verification.json). 전수검토와 최종 분석은 미완료다.

2026-09-11 최종 완료: A1902결정/1811호출/97무호출을 모두 검토했다. 최초 전략 판정은
경기별로 이전 결정을 확정한 뒤 다음 prefix를 열었고1902개 ID·시점 영수증 예외0이다.
초기 판정과 수정 이력을 보존한 뒤 공통 분류·과제 기회·실행 연결을 보충했다.
성적50승14패/64(78.125%), Abyssal·OneStep각25승7패, A_new26승6패/A_anchor24승8패다.
사실·규칙 오류664결정과608사건 묶음은 설명/전제 수준이며 최적 선택·패배 원인과 구분했다.
입력 노출 문제·출력 후보 연결 오류6회/3결정·반대 사례·후속 가설9개를 별도 보고했다.
보류팀 실행·추가 유료 심사·재수집0이다.

최종 무결성 검증:128 actor bundle·177 source·1811요청·1902전송,
기존68081 inventory 중 승인된 control-plane6개 외68075불변/누락0·기존6개 Blocked불변,
소유869프로세스 종료·포트/작업트리/잠금 해제·활성permit0.
최초 유료 예약부터 정리18.14분으로 원래 시계/한도를 지켰다.
현재 상태와 experiment/exec-plan index를 완료로 갱신했다.
[최종 보고서](../../../exec-plans/evidence/ep029/report.md), [전수검토](../../../exec-plans/evidence/ep029/reviews.html),
[최종 검증](../../../exec-plans/evidence/ep029/final-verification.json).
