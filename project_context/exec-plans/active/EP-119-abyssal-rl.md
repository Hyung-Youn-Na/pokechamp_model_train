# EP-119 — Abyssal 우선 4GPU·24시간 학습

- 상태: Blocked — 학습·test 완료, 뷰어 전수 검증 시간 초과로 실험 미완료
- 생성일: 2026-10-03
- 책임자: Codex
- 승인: 현재 사용자 제공 계획 구현·검증·실행 지시 / D-116
- 관련: EX-073, C-057; INDEX/CHARTER, EP-108/103의 자원·기존 자료 보존 경계 확인.

## 목표·범위

사용자 계획에 따라 EX-071 출발 Abyssal 전용 정책을 GPU0–3에서 공동 학습하고 독립 평가한다.
조건 원문은 [EX-073](../../experiments/EX-073-abyssal-rl.md), runtime은 C-057이다.
새 integration/pokechamp/abyssal_rl 및 CLI·검사·제어 문서만 변경한다. EX-072 동결 구현/자료,
EX-066 재로딩 실패와 가중치를 보존하며 이전 실험을 재개하지 않는다.
독립 준비·분산 학습·수집 구현을 서브에이전트에 분리 위임하고 주 에이전트가 통합 검증한다.

## 완료 기준

- [x] protocol·runtime 등록, CPU 자료 준비·필수 검사
- [x] 4GPU 수치 대조·실제 SIGTERM 전체 worker 재개
- [x] 최소 학습 후보1개 dev·보정 판단·정상 test512경기
- [ ] 독립 감사·통계·봉인·C-047 오프라인 뷰어·자원 정리

## 중단·복구

INDEX 공통 기준·RD11.1/C-018을 적용한다. 재수집/대체/재질의0, 최초 GPU 검사부터24시간 유지.
분할 부족·OOM·길이 초과·비유한값·수치 gate 실패를 조건 완화로 통과시키지 않는다.
중단 처리 완료를 실험 완료로 표시하지 않는다.

## 진행

- 2026-10-03 — 등록. 원 체크포인트·BC와 RTX A6000 4장 존재 확인; GPU 연산/새 배틀0.

- CPU 최종121검사(학습/분산/런타임/단계/최종화63·오프라인 뷰어9·native 배틀49)와
  Chromium 의존성 검사를 통과했다. 이전 검사환경/과도한 discovery glob 오류는
  `versions/cpu-verifier-v1/`에 보존했고 GPU 연산/배틀 영향0이다. 합법416팀·가능17048슬롯·
  원 BC3072를 동결했다. [CPU receipt](../../../.pokechamp-data/experiments/ex073-abyssal-rl/verification/cpu.json).
- 4GPU 실제 수치 검증부터 최초24시간 실행에 진입한다. SIGTERM 전체 재시작·첫8경기
  감사·후속 학습/dev/보정/test는 각 선행 gate 통과 전에는 미실행이다.

- 첫 GPU preflight의 고정 경사 허용오차가 실패하여 전체 worker를 중지·정리했다.
  원본은 `versions/gpu-preflight-v1/`에 보존했으며 경기·update0이다.
  단일 GPU 반복에서도 같은 증상이 재현되어 [EP-120](../completed/EP-120-abyssal-preflight-recovery.md)의
  별도 복구 도구·독립 검증을 진행한다. 허용오차·최초 시계·실험 조건은 유지한다.

- EP-120 복구 도구 검증·봉인 후 최초 시계에서 재개했다. Production 4GPU 수치 gate를
  통과하여 초기 dev에 진입했다. 실제 학습 중 SIGTERM 재시작 검증은 아직 남아 있다.

- 초기 dev64경기는 모두 정상 종료(8승56패)했고 첫 학습 라운드 수집에 진입했다.
  초기 모델 후보와 각 경기의 audit evidence를 보존했다.

- 첫 학습 라운드64경기 모두 정상 종료·유효1809결정으로 gate를 통과했다. 채택1536결정의
  old-policy log probability/WDL 전수 재현 최대오차0을 확인했다. 첫 update 후 실제 SIGTERM으로
  전체 rank를 종료하고 동일 checkpoint·optimizer504상태·rank별 RNG·원 시계 복원을 검증했다.
  [재개 검사](../../../.pokechamp-data/experiments/ex073-abyssal-rl/verification/resume.json).

- round1은35개 완료 update 후 KL 한도로 정상 종료했고 round1 후보 dev64경기에 진입했다.
  초기 dev·round1 수집의 정상128경기 오프라인 뷰어 검증을 모두 통과했다.

- round1 후보 dev64경기도8승56패로 정상 완료했다. 초기 후보와 동률이며 원 tie-break를
  유지한다. 최소 학습 후보1개의 dev를 완료했고 round2 수집 중이다. 보정/test/최종화는 미실행이다.

- round2는192회·두 epoch 완료, round3/4는각38/34회 update 후 KL 한도로 종료했다.
  누적299update, 첫4라운드 정상256경기에서 train256팀 모두 등장한 것을 원자료로 확인했다.
  round4 dev는정상64경기4승60패로 완료했고 round5수집 중이다. 중간 dev최고는초기/round1
  동률이며 초기 후보의 동점 우선순위를 유지한다.

- round5–8은각8/29/29/54회 update 후 KL 한도로 종료했고 누적419update를 완료했다.
  round8 dev정상64경기5승59패, 현재후보[초기,1,4,8] 중 최고dev는초기/1동률이다.
  round9수집을 시작했으며 최종test는미실행이다.

- round9/10/11/12는각108/91/59/53회 update 후 KL 한도로 종료했다(누적730).
  round12 dev정상64경기8승56패로초기/round1과동률이며초기우선규칙을유지한다.
  최초시계약5시간경과, 최종test미실행이며후속라운드를계속한다.

- round13–16은 각각 47/31/29/54회 update 후 KL 한도로 종료했다(누적 891회).
  네 라운드 모두 채택 결정의 old-policy log probability/WDL 재현 최대오차는 0이다.
  round16 dev는 정상 64경기·4승 60패이며, 초기/round1/round12의 최고 dev 동률과 초기
  우선순위를 유지한다. 최초 시계 약 6시간 38분 경과 후 round17 수집에 진입했다.

- round17–20은 각각 45/89/34/45회 update 후 KL 한도로 종료했다(누적 1,104회).
  채택 결정의 old-policy log probability/WDL 재현 최대오차는 네 라운드 모두 0이다.
  round20 dev는 정상 64경기·4승 60패로 완료했다. 최고 dev 후보와 초기 우선순위는
  유지되며 최초 시계 약 8시간 5분 경과 후 round21 수집을 시작했다.

- round21–24는 각각 34/52/19/9회 update 후 KL 한도로 종료했다(누적 1,218회).
  네 라운드 모두 old-policy log probability/WDL 재현 최대오차는 0이다.
  round24 dev는 정상 64경기·10승 54패(15.625%)로 기존 최고 8승을 넘어 현재 최고 후보다.
  이는 중간 dev 결과이며 test 성능·개선 판정은 아직 미평가다. 최초 시계 약 9시간 19분
  경과 후 round25 수집을 시작했다.

- round25–28은 각각 26/25/11/80회 update 후 KL 한도로 종료했다(누적 1,360회).
  네 라운드 모두 old-policy log probability/WDL 재현 최대오차는 0이다.
  round28 dev는 정상 64경기·5승 59패이며 round24 후보가 현재 최고를 유지한다.
  최초 시계 약 10시간 37분 경과 후 round29 수집에 진입했다. 보정·test는 미실행이다.

- round29–32는 각각 16/32/17/24회 update 후 KL 한도로 종료했다(누적 1,449회).
  네 라운드 모두 old-policy log probability/WDL 재현 최대오차는 0이다.
  round32 dev는 정상 64경기·6승 58패이며 round24 후보가 현재 최고를 유지한다.
  최초 시계 약 11시간 47분 경과 후 round33 수집에 진입했다. 보정·test는 미실행이다.

- round33–36은 각각 42/53/29/20회 update 후 KL 한도로 종료했다(누적 1,593회).
  네 라운드 모두 old-policy log probability/WDL 재현 최대오차는 0이다.
  round36 dev는 정상 64경기·5승 59패이며 round24 후보가 현재 최고를 유지한다.
  최초 시계 약 13시간 6분 경과 후 round37 수집에 진입했다. 보정·test는 미실행이다.

- round37–40은 각각 60/40/29/11회 update 후 KL 한도로 종료했다(누적 1,733회).
  네 라운드 모두 old-policy log probability/WDL 재현 최대오차는 0이다.
  round40 dev는 정상 64경기·3승 61패이며 round24 후보가 현재 최고를 유지한다.
  최초 시계 약 14시간 26분 경과 후 round41 수집에 진입했다. 보정·test는 미실행이다.

- round41–44는 각각 33/19/18/25회 update 후 KL 한도로 종료했다(누적 1,828회).
  네 라운드 모두 old-policy log probability/WDL 재현 최대오차는 0이다.
  round44 dev는 정상 64경기·9승 55패이며 round24 후보가 현재 최고를 유지한다.
  최초 시계 약 15시간 37분 경과 후 round45 수집에 진입했다. 보정·test는 미실행이다.

- round45–48은 각각 25/31/17/25회 update 후 KL 한도로 종료했다(누적 1,926회).
  네 라운드 모두 old-policy log probability/WDL 재현 최대오차는 0이다.
  round48 dev는 정상 64경기·6승 58패이며 round24 후보가 현재 최고를 유지한다.
  최초 시계 약 16시간 49분 경과 후 round49 수집에 진입했다. 보정·test는 미실행이다.

- round49–52는 각각 29/14/25/21회 update 후 KL 한도로 종료했다(누적 2,015회).
  네 라운드 모두 old-policy log probability/WDL 재현 최대오차는 0이다.
  round52 dev는 정상 64경기·5승 59패이며 round24 후보가 현재 최고를 유지한다.
  최초 시계 약 17시간 59분 경과 후 round53 수집에 진입했다. 보정·test는 미실행이다.

- round53–56는 각각 33/39/30/24회 update 후 KL 한도로 종료했다(누적 2,141회).
  네 라운드 모두 old-policy log probability/WDL 재현 최대오차는 0이다.
  round56 dev는 정상 64경기·7승 57패이며 round24 후보가 현재 최고를 유지한다.
  최초 시계 약 19시간 19분 경과 후 round57 수집에 진입했다. 보정·test는 미실행이다.

- 2026-10-04 사용자 후속 지시 — 토큰 절약을 위해 대화형 반복 모니터링을 중단한다.
  학습·평가·자동 최종화 프로세스는 유지하며, 외부 일회성 종료 감지기가 실행 종료 또는
  최초 24시간 마감에 기존 대화로 후속 검증 요청을 전달한다. 실험 source·조건·시계는 변경하지 않는다.

## 종료 검증 — 2026-10-04

57라운드·2,164 update를 완료했다. 마지막 라운드는23 update/KL 종료이며 old-policy
log probability/WDL 재현 최대오차0, 마지막 dev는9승55패다. dev 선택은 round24를 유지했다.
보정64경기·보정 dev24경기를 마쳤고 half-Brier 0.0797936104→0.0775132911로 보정 head를
채택했다. 정책 불변 gate를 통과한 후 잠긴 test512경기를 모두 정상 완료했다.
최종 성능·분모·해석은 [EX-073 종료 결과](../../experiments/EX-073-abyssal-rl.md#final-results)를 따른다.

독립 감사는 정상5,336경기·158,876결정과 대응 통계를 재구성해 통과했다. 하지만 최종
이동 후 오프라인 뷰어 검사가 약8,600.84초 뒤 원24시간 한도로 TimeoutExpired가 됐다.
`all_normal_games_viewer_audit/finalization/sealed/viewer` 완료 gate는 미충족이다.
추가 실행 없이 원 실패·보고·내보내기를 보존하고 plan을 active/의 Blocked로 유지한다.
완료 기준을 완화하거나 예산을 연장하지 않았다.

worker는 최초 시계 약21시간에 정상 종료하고 GPU를 해제했다. 자동 최종화의 실패 기록·
내보내기 종료 처리는 절대 마감 후32.70초에 닫혔으며, 이를 시간 내 검증 성공으로 세지 않는다.
종료 알림 후 원 completed.json의 result SHA256 일치, 실행 프로세스 종료, GPU compute process0,
전용8100–8107/8030–8033 listener0 및 잔여 Chromium process0을 확인했다.

- [최종 보고](../../../.pokechamp-data/experiments/ex073-abyssal-rl/final/report.md)
- [종료 receipt](../../../.pokechamp-data/experiments/ex073-abyssal-rl/completed.json)
- [독립 감사](../../../.pokechamp-data/experiments/ex073-abyssal-rl/final/independent-audit.json)
- [검증 미완료 뷰어](../../../exports/battle_viewers/ex073/index.html)
