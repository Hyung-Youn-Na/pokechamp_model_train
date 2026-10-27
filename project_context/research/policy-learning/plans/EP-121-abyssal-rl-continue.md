# EP-121 — 57라운드 계승 추가12시간

- 상태: Completed
- 생성일: 2026-10-05
- 책임자: Codex
- 승인: 현재 사용자 제공 EX-074 계획의 구현·검증·실행 지시 / [D-117](../decisions/D-117-abyssal-rl-continue.md)
- 관련: EX-074 / [C-058](../CONTRACTS.md#c-058-abyssal-rl-continue); INDEX/CHARTER·EP-119/108/103 보존 경계 확인.

## 목표·범위

사용자 EX-074 계획을 구현하고 CPU 검증 뒤 지정57라운드 checkpoint에서 추가 학습·평가한다.
새 integration/pokechamp/abyssal_rl_continue·CLI·검사·제어 문서만 변경한다.
EX-073 동결 source/artifact·시간 초과 미완료 및 다른 Blocked 실험은 보존한다.
독립 준비·복원과 최종화·알람을 서브에이전트에 분리 위임하고 주 에이전트가 통합·검증한다.
조건 원문은 [EX-074](../experiments/EX-074-abyssal-rl-continue.md)다.

## 완료 기준·검증

- [x] 부모 CPU 출처/가중치/optimizer504/4rank RNG·새 split·슬롯·필수 CPU 검사
- [x] 원4GPU 수치 gate·실제 SIGTERM 전체rank 재개
- [x] 추가 후보 dev·보정 판단·정상 test512·독립 감사
- [x] 전 경기 뷰어 내보내기·단계별 최대12경기 확인·봉인·소유 자원 정리
- [x] 영속 중복 방지 단계 알람·최종 보고/문서 갱신

## 중단·복구

INDEX 공통 기준·RD11.1/C-018·RD11.2/C-046 적용. 재시도·대체·재질의0.
첫 GPU 검사부터12시간/48GPU시간. 예산 연장·허용오차 확대·임의 표본 제거0.
팀 부족은 실행 전 중단. 실시간 대화형 감시·브라우저 전수/점진 전수 검사는 금지한다.

## 진행

- 2026-10-05 — 사용자 계획 등록. CPU 준비·구현 중, 신규 GPU/배틀0.

## 구현·검증 경계

prepare/verify/run/status/finalize와 EX-074 내부 `run --resume`를 구현한다.
parent checkpoint 경로·해시·원 identity, 누적2,164/추가 update와 local1/global58 구분을
manifest·보고에 보존한다. 초기 복원은 buffer 재사용 없이 진행하며 필수 수치 기준을 완화하지 않는다.
시간·슬롯·선택·보정·평가·알람·표본 검증 전문은 EX-074를 따른다.
알람 receipt 확인은 사건당1회이며 종료 알람에서 최종 문서와 보고서·뷰어 링크를 갱신한다.
최종화 미완료를 학습 효과·통계적 개선 판정과 분리하며 과거 EX-073의 판정을 바꾸지 않는다.

- 2026-10-05 — D-117/EX-074/C-058 및 RD·STATUS·ARCHITECTURE·색인 연결 등록.
  구현·CPU/GPU 검증·실험 완료는 아직 판정하지 않는다.

- CPU 준비 완료: train256/dev32·BC3072를 유지하고 신규 합법 test128, 가능17048슬롯을 동결했다.
  지정 부모 checkpoint의 round57 정확 일치·optimizer504/누적2164step·4rank RNG 출처 검사를 통과했다.
  기존 abyssal_rl source/CLI를 EX-073 recovery 동결 해시와 대조해 보존을 확인했다.
  [준비 manifest](../../../../.pokechamp-data/experiments/ex074-abyssal-rl-continue/prepared/manifest.json),
  [부모 검사](../../../../.pokechamp-data/experiments/ex074-abyssal-rl-continue/prepared/parent.json),
  [원 source 보존](../../../exec-plans/evidence/ep121/ex073-source-preservation.json).
- 새 실행기는 부모 복원 후 새 buffer·local update0으로 시작하며 누적2164를 별도 기록한다.
  EX-074 내부 resume·완료 학습 checkpoint 별도 보존·실제 SIGTERM 복원 검증을 구현했다.
  전수/점진 브라우저 실행을 제거하고 단계별 최대12경기 검사 및 영속 단계 알람을 구현했다.
  초기 개발 회귀의 새 seed 기대값1건을 교정했으며 GPU 실행·동결 자료 영향은 없다.
  통합 CPU admission 검증 전이며 실제4GPU/SIGTERM·배틀·최종화는 아직 미실행이다.

- CPU admission179검사(학습/분산/복원/알람114·뷰어16·native 배틀49) 및 Chromium 의존성 검사를 통과했다.
  [동결 source 연결 CPU receipt](../../../../.pokechamp-data/experiments/ex074-abyssal-rl-continue/verification/cpu.json).
  GPU0–3 유휴를 확인했으며 자동 실행·별도 단계 알람을 시작한다. 실제4GPU gate·SIGTERM·학습/평가
  완료를 이 CPU 결과로 대신하지 않는다. 이후 대화형 반복 모니터링은 하지 않는다.

- 별도 실행 프로세스와 모델 비호출 단계 감지기를 시작했다.
  [시작 receipt](../../../../.pokechamp-data/experiments/ex074-abyssal-rl-continue/launch.json).
  현재 대화 identity를 사용하며 알람 claim/전달 상태를 영속 기록한다. 정상 전환은 응답을 기다리지 않는다.
  자동 실행은 수치 검사·실제 SIGTERM 재개를 먼저 통과해야 하며 이후 상태는 단계 receipt로 확인한다.


## 실행 전 동결 경계 중단·복구

첫 시작의 source 동결 중 에이전트가 EP-121 시작 기록을 갱신하여 hash 계산과 복사 사이에
문서가 바뀌었다. 동결 gate가 이를 거부했다. manifest 작성·GPU worker 시작·학습·배틀은0이다.
부분 source·원 CPU receipt·실행/알람 로그를 `versions/startup-freeze-v1/`에 보존했다.
[중단 receipt](../../../../.pokechamp-data/experiments/ex074-abyssal-rl-continue/versions/startup-freeze-v1/receipt.json).
원 clock·자원 identity·부모·자료·조건은 유지하고 문서 갱신을 동결 전에 끝낸다.
CPU에서 문서 hash/copy 경계 변경을 주입해 같은 실패를 재현하고, 변경 없는 재진입의 같은
clock 보존을 검사한다. 알람은 비정상 사건과 이후 최종화 사건을 분리하되 완료/마감만 합치도록
수정했다. 이미 전달한 시작 실패 알람은 원 ledger를 보존하고 abnormal로 분류하여 재전송하지 않는다.
새 CPU 검증 뒤 같은12시간·48GPU시간 안에서 실행을 시작하며 자동 예산 연장은 없다.

- 재검증183검사(학습/분산/복원/알람/동결 경계118·뷰어16·native 배틀49)와 브라우저 의존성 검사가 통과했다.
  원12시간 시계/마감·부모·팀·슬롯·손실·수치 기준을 그대로 유지하며 재진입한다.
  이미 전달한 이전 supervisor의 시작 실패는 `abnormal-startup-freeze-v1` 사건으로 영속 보존한다.
  새 supervisor의 비정상 종료는 별도 사건이고, 같은 supervisor/감지기 재시작은 중복 전송하지 않는다.
  source 동결 중에는 문서·코드를 변경하지 않는다. 이후 운영은 자동 단계 알람에 맡긴다.


## 완료 검증 — 2026-10-06

추가25라운드·510update, dev9후보·보정 판단·잠긴 정상test512를 완료했다.
최종 선택은 추가round20(전체77)·보정 전 head다. 사전 기준상57라운드 출발 대비 개선은
확인했으나 성능 목표는 미달이다. 상세 분모·구간·자원·해석은
[EX-074 종료 결과](../experiments/EX-074-abyssal-rl-continue.md#final-results)를 따른다.

4GPU 출력 최대차이0, 경사1.1175870895385742e-8, update1.728767529129982e-8로 고정 기준을
통과했다. 실제 첫 update 뒤 SIGTERM 전체rank 재시작과 가중치·optimizer504·각 RNG 정확 복원을
확인했다. 독립 감사2776경기·83757결정, 독립 통계, 전 경기 export·표본12경기 오프라인 확인,
원자료/모델/학습 계승 checkpoint·봉인·자원 정리를 완료했다. 브라우저 전수 검증 생략은 유지한다.
완료 receipt의 result SHA256을 대조했고 실행/알람 프로세스 종료·GPU compute process0·
전용 port listener0을 확인했다. 원 시계 약9시간12분에 종료했으며 미충족 완료 기준은 없다.
시작 실패·당시 알람·원본은 보존하고 EX-073 판정은 변경하지 않았다.

- [종료 확인](../../../exec-plans/evidence/ep121/closure.json)
- [최종 보고](../../../../.pokechamp-data/experiments/ex074-abyssal-rl-continue/final/report.md)
- [뷰어](../../../../exports/battle_viewers/ex074/index.html)
