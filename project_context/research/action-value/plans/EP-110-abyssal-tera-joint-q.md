# EP-110 — Abyssal Tera 정책과 보완 공동 q 데이터

- 상태: Completed
- 생성일: 2026-09-30
- 완료일: 2026-10-01 (KST)
- 책임자: Codex
- 승인: 현재 사용자 제공 계획 구현·검증·수집 지시 / D-107
- 관련: C-051/C-053, EX-067, EP-108(EX-066 보존)

## 목표와 범위

공격·방어를 고려한 `abyssal-tera-v1`을 parent integration에 구현하고 새80경기의
관측별 전체 후보32분기 학습 자료·감사·뷰어·백업 복사를 완료한다.
동결 정책·표본·자원·순서·복구·해석 원문은 [EX-067](../experiments/EX-067-abyssal-tera-joint-q.md)이다.
INDEX/CHARTER·STATUS·exec-plan 색인과 겹치는 EP-108/EP-103, RD11.1/C-018 및
EX-065 수집 근거를 확인했다. 과거 Blocked 실험은 재개하지 않는다.

기존 EX-066 learning 전체·data/serializer/storage·학습 실행기·봉인 입력/환경은 변경하지 않는다.
새 seed 설정은 별도 모듈에 둔다. upstream·AgenticSTS·현재 학습 입력/가중치는 보존한다.
정책·actor 연결·독립 검토는 분리 가능한 범위로 위임하고 공유 파일 통합과 최종 검증은 주 에이전트가 담당한다.

## 완료 기준

- [x] 정책/Actor/snapshot/재개·RNG/비공개 격리 및 의미 회귀 통과
- [x] 정책·설정·검증 기준 동결, train10 파일럿 전수 재현/root/입력/32완료·자발적 Tera gate
- [x] 나머지 train40/validation10, 그 뒤 test20 수집·전수 감사·실제 분모 보고
- [x] 원경기80 뷰어·관측별 후보 q·오프라인 열람 검증
- [x] 원자료/소스/비용/실패 봉인·학습 파일 백업 체크섬·로더 검증과 상태 갱신

## 검증과 진행

- 2026-09-30 — 승인 범위 등록, 구현 전. EX-066 실행 중이며 봉인 소스 목록을 확인했다.
  메모리 가용88GiB·작업 디스크 여유979GiB·백업 여유5.9TiB 확인. 실제 수집0.
- 정책·Actor/snapshot·EX067 seed/원장·CPU 실행기와 감사/뷰어/복사 구현을 연결했다.
  정책40검사와 분할/재시도/자원·입력 경계14검사가 통과했다. 원경기 수집은 아직0이며
  실제 분기 중단/재개 probe와 폴더 이동 후 오프라인 Chromium 검증을 준비한 뒤 동결한다.
  브라우저에서 발견한 file:// JSON 다운로드 문제는 수집 전 교정·독립 재검증한다.
- 소스 `96bfb374a404e9ea964f461685af4b1905efdc129c8f534d92a88f17e843d3df`와
  EX067/20260930 manifest를 동결했다. 필수 CPU147검사 통과(실패/오류/skip0),
  이동한 합성 뷰어의 실제 오프라인 Chromium·복사/다운로드 검증 통과.
  train10 원경기 파일럿과 전수 재현/root 검증을 시작했다. 감독 상태·로그는 별도 jobs에 보존한다.
  [CPU 검사](../../../../.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/verification/cpu-tests.json).
- 파일럿10 원경기·314관측의 전체 재현/root 복원·입력 생성을 완료했다.
  실제32분기를 worker1/16·역순으로 대조해 궤적/결과가 일치했고, 20단계 checkpoint에서
  소유 프로세스를 중단·재개한43단계 분기도 전체 궤적/결과가 일치했다. 검증 분기는 label에서 제외한다.
  동일 소스의 verification receipt로 파일럿 전체 후보32분기 수집에 진입한다.
- 파일럿90,720분기를 약1,198초에 완료(실패/재시도0)하고 전수 감사까지 통과했으나,
  보고서의 입력/공개 Tera 소모 대조에서 `t113171-s0-o0005` 불일치로 다음 단계 진입을 중지했다.
  독립 진단에서 공식 관측기의 기절 후 현재 Tera 표시 해제와 팀 소모 정보 누락을 확인했다.
  직접 영향은5경기·70관측/98진영쌍이며,65관측은 해당 사건도 최근3턴 이력 밖이다.
  원 소스·입력·분기·실패/STOP을 보존하고, 공개 prefix 기반 팀 소모2값과 현재 개체 플래그
  설명만 EX067 전용 입력 경계에서 교정한다. 정책/seed/분할/32회 기준과 EX-066 봉인은 불변이다.
  공통 입력 표현이 바뀌므로 파일럿10경기 전체를 `versions/public-tera-v2/`에서 같은 seed로
  1회 재수집한다. 직접 결함 범위5경기와 일관된 입력 버전을 위한 재수집10경기를 구분한다.
  원90,720분기는 최종 학습 자료에서 제외하되 최초 시계·비용/분모·증거를 유지한다.
  독립 원자료 대조·결함 재현/회귀·새 source/복구 receipt 검증 후에만 재수집한다.
- 독립314관측 대조에서 공개 소모값·입력 역변환 바이트 일치, unknown24,543값 보존,
  비공개 요청/세트·미래 RNG 교란 불변을 확인했다. 원103,753파일의 봉인과 정책/seed/최초 시계
  불변을 대조하고 `public-tera-v2` source `2835e527145afa19931a0c905fccb671680e71d3b6f8be713cbcfb357d75ca62`를
  동결했다. 첫 사전검사는175개 중174통과·기존 simulator 재현 검사1실패로 수집 전 중지했다.
  실패는 actor 로그의 시각 필드 대조이며 원로그/receipt를 보존하고 독립 재현으로 무영향 여부를 확인한다.
  [복구 receipt](../../../../.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2/recovery-receipt.json).
- 초 경계 독립 재현에서 기존 fixture의 actor 로그 시각 정규화 누락을 확인했다.
  시각 이외 전체 응답/snapshot과 운영 boundary fingerprint 차이는0이며 소스/원실패 증거는 불변이다.
  같은 동결 소스의 필수175검사를 다시 실행하여 실패/오류/skip0을 확인한 뒤 파일럿 재수집에 진입했다.
  [독립 시각 진단](../../../../.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2/verification/simulator-clock-diagnostic-v1/diagnosis.json) ·
  [최종 CPU 검사](../../../../.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2/verification/cpu-tests.json).
- 복구본 파일럿10경기·314관측·2,835후보·90,720분기를1,269.83초에 완료했다.
  수집 오류/재시도0, 입력 격리/토큰/전수 감사와 새 소스의 worker1/16·역순/중단재개 대조를 통과했다.
  원경기의 자발적 Tera는 p1 9/10·p2 5/10이며 양측 사용 이후 관측과 분기 후속 사용을 확인했다.
  원본/교정본90,720분기의 결과·seed·궤적·시작/종료 경계 차이0으로 파일럿 gate를 통과했다.
  나머지 train40/validation10 원경기 수집을 시작하며 test는 rest gate 전 미진입이다.
  [파일럿 gate](../../../../.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2/pilot-gate.json) ·
  [전수 대응 대조](../../../../.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2/verification/paired-pilot-v1-v2.json).
- train50/validation10의60경기·1,904관측·15,783후보·505,056분기를 완료했다.
  추가414,336분기 수집5,711.73초, 수집 오류/재시도0, 불완전 관측/분할 간 중복 충돌0이다.
  전체 재현/root·입력 격리/토큰/전수 감사와 보고/rest gate를 통과해 정책/설정 변경 없이
  test20 원경기 수집에 진입했다. 이 단계의 집계 원문은 별도 cohort 증거로 보존했다.
  [rest gate](../../../../.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2/rest-gate.json) ·
  [60경기 보고](../../../../.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2/rest/report.md).
- test20의179,776분기를2,571.75초에 완료했다. 전체80경기·2,543관측·21,401후보·684,832분기의
  전수 감사와 토큰 검사를 통과했다. 불완전 관측/분할 간 충돌0, 같은 split 의미 중복71관측,
  최대28,445토큰·절단0이다. 최종 보고·80경기 뷰어/오프라인 검증·봉인/백업 확인을 진행한다.
  원 파일럿103,753파일도 전수 재해시하여 보존 봉인과 일치하고 원 STOP이 유지됨을 확인했다.
  [최종 감사](../../../../.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2/audit.json) ·
  [원본 보존 검증](../../../exec-plans/evidence/ep110/parent-v1-preservation.json).
- 2026-10-01 (KST) — test gate·최종 보고·뷰어·봉인/복사 검증을 완료했다.
  폴더 이동 후 네트워크 차단 Chromium에서80경기/공개 리플레이·2,543관측·21,401후보를 전수 대조했다.
  실제 표시 입력/행동 이름/q/WDL·방향키 탐색·복사/다운로드가 일치하고 JavaScript/CSP 오류0이다.
  원자료705,092파일·논리4,984,062,306bytes를 봉인했다. 백업25파일·333,053,044bytes의
  크기/체크섬·관측/후보 ID·공개 로더가 원본과 일치한다. 뷰어 논리 용량은750,174,356bytes다.
  기존 EX-066 봉인 소스/입력/설치 환경 불변을 재확인했으며 해당 학습 프로세스는 계속 실행 중이다.
  EX-067 소유 수집/검증 프로세스는0, 감독의34단계 완료·실제 종료코드0이다. 상태 파일의
  역사적 `exit_code: 1`과 실패 로그 경로는 최초 사전검사 실패 필드로 보존됐으며 마지막 종료 상태가 아니다.
  최초 실험 시계부터 감독 종료까지18,706.30초이며 원 파일럿/복구/검증 비용을 초기화하지 않았다.
  [완료 검증](../../../exec-plans/evidence/ep110/completion.json) ·
  [브라우저 검증](../../../../.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2/final/browser-verification.json) ·
  [복사/로더 검증](../../../../.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2/final/copy-verification.json).

## 중단과 복구

[INDEX](../../../INDEX.md#workflow)·RD11.1/C-018과 EX-067의 복구 절을 적용한다.
동일 seed/checkpoint 최대3시도, 기술 결함은 영향 경기와 의존 전체 분기의 별도 버전1회 재수집만 허용한다.
누적 시간 상한은 없고 최초 시계·실패·원본을 유지한다. 복구 실행기 검증 전 우회 재개하지 않는다.

## 결과와 증거

80경기·모든 후보32분기의 수집·감사·뷰어·봉인·학습 자료 복사/검증을 완료했다.
원/교정 버전과 실제 유효 분모를 구분하며 새 q는 `abyssal-tera-v1` 후속 정책에 조건부다.
현재 학습에 병합하지 않았고 모델 성능 향상은 평가하지 않았다.

- [최종 보고](../../../../.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2/final/report.md)
- [80경기 뷰어](../../../../exports/battle_viewers/ex067/index.html)
- 학습 자료: `/mnt/digicap/combined/hyna/backup/pokechamp/ex067-abyssal-tera-joint-q/`
- [원자료 봉인](../../../../.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2/final/source-seal.json)
