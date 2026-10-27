# EP-133 — EX066 epoch3의 GPU0 실제 배틀 평가

- 상태: Completed
- 생성일: 2026-10-08
- 책임자: Codex
- 승인: 현재 사용자 GPU0 요청·test20/기존 재현 기준/8시간 선택·계획 구현 지시 / D-129
- 관련: EX-081, C-052/C-062, RD11.1/11.2, C-018/C-046/C-047

## 목표·범위

EX066 epoch3 재현성 복구 후 GPU0에서 test20 대전·감사·뷰어·보고를 완료한다.
조건·시계·gate·분모·복구 원문은 [EX-081](../experiments/EX-081-joint-q-battle.md)이다.
INDEX/CHARTER·STATUS·색인과 겹치는 EP-108/103/119/132, 관련 RD/C/ARCHITECTURE를 확인했다.
기존 EX066의18개 봉인 source·가중치·입력/STOP과 다른 실험/공유 venv를 보존한다.
새 `integration/pokechamp/joint_q/battle_eval/`, 전용 CLI/검사와 문서에 구현한다.
추가 학습·원 오프라인 test·초기 모델 대전은 제외하고 GPU2·3의 별도 작업에 간섭하지 않는다.
Root AGENTS의 큰 작업 분리 지침에 따라 배틀 연결과 독립 감사/뷰어를 분리 위임한다.
주 에이전트가 모델/재현성·GPU0·통합 검증·공유 문서 갱신을 담당한다.

## 완료 기준

- [x] 새 protocol/runtime 등록·원본 보존·CPU 필수 검사
- [x] 두 프로세스 validation 전수 재현 통과·최종 서버 유지
- [x] test20 유효 완료·모든 입력/선택/전송 감사
- [x] 보고·명령/원자료 봉인·C-047 뷰어·이동 후 오프라인 전수 확인
- [x] 소유 자원/GPU0 반환·상태 갱신

## 검증·진행

- 2026-10-08 — 승인 범위 등록. 원18source·주요 checkpoint 해시·EVE 패키지 버전이
  봉인값과 같고 GPU0이 유휴임을 확인했다. 저장 validation 불일치는1관측·선택 변화0이다.
  새 GPU forward/배틀0이며 원인 판정은 아직 없다.

- 2026-10-08 — 새 서버/플레이어/실행기·독립 감사/뷰어를 분리 구현했다. GPU0 원경로의
  12forward(불일치 관측10·이웃2)에서 원 epoch3 q 최대차이0, 선택 변화0과
  checkpoint/Base/trainable/source 불변을 확인했다. 과거 실패 원인은 미확정이다.
  최초 시계09:41:13 KST를 기록했고 진단 서버를 정상 종료했다. 입력/수치 경로 변경0이다.
  새 배틀57·감사/뷰어54·제어12개 CPU 검사를 최종 통합 검증한 뒤 두 프로세스 전체 validation에 진입한다.

- 최종 native pytest123개가 모두 통과했고 skip/오류/실패0, 정적 F 검사도 통과했다.
  처음 unittest 모음은 pytest 함수 검사를 발견하지 못해12개만 실행했으며 원 receipt/log를
  보존하고 pytest로 전123개를 검증했다. 모델/배틀 수집 영향0이다.
  [최종 CPU](../../../exec-plans/evidence/ep133/cpu-final-v2.log) · [정적 검사](../../../exec-plans/evidence/ep133/static-final.log).
  모델/대진/639source와 서버 전용 source를 동결하고 전수 qualification을 시작했다.
  GPU0 첫 프로세스는170/320관측까지 원 q 최대차이0·입력/token/readout 일치를 확인했다.

- 2026-10-08 10:25 KST — 첫 qualification 프로세스가320관측/2991후보를 전부 완료했다.
  원 epoch3 q 최대차이0·선택 변화0, 입력/token/readout 일치, Base/LoRA/head/checkpoint/source
  불변 및 exit0을 확인했다. 원 GPU1 실패 원인은 미확정으로 보존한다.
  새 두 번째 프로세스를 GPU0에서 시작했으며 배틀은 아직0이다.
  [첫 전수 결과](../../../../.pokechamp-data/experiments/ex081-joint-q-battle/qualification/original-1791421547208867281/a/report.json).

- 2026-10-08 10:45 KST — 두 번째320관측/2991후보도 원 q 최대차이0로 완료했다.
  두 프로세스 사이 최대차이0이며 정확한 입력/token/readout과 모델/source identity를 대조했다.
  최종 서버를 그대로 유지하여 고정 test20의 첫 대진에 진입했다. 가중치/입력/수치 backend 변경0,
  원 GPU1 실패 원인은 미확정이다. [qualification](../../../../.pokechamp-data/experiments/ex081-joint-q-battle/qualification/passed.json).

- 2026-10-08 12:03 KST — test20 전부 정상/유효 완료,0승0무20패·실패/무효0이다.
  970결정의 per-game 감사와 최종 모델/Base/checkpoint/source 불변·exit0·GPU0 반환을 확인했다.
  별도 전체 원문 감사도 통과했으며 첫 보고/뷰어를 생성했다.
- 최종 비교에서 EX065 v5의 `games`가 원 실험 `games`로 향하는 보존 심볼릭 링크임을
  범용 디렉터리 containment가 거부하여 역사 기준선20쌍이 누락됐다. 새 대전·입력·q·전송·
  승패/모델 무결성에는 영향0이다. RD11.1/C-018의 저장 자료 평가 구현 교정으로 처리한다.
  최초 `final/` 보고·receipt와 `exports/battle_viewers/ex081/` 봉인본은 원 경로에 보존하고,
  `corrections/baseline-v2/`와 별도 `ex081-baseline-v2` 뷰어로 교정한다. 원 시계와8시간을 유지한다.
  원 manifest/버전 seal·실제 terminal·원 대진 seed를 독립 계산한20쌍은 모델0승/기준선11승,
  점수차−0.55·5팀20000 bootstrap95%[-0.70,-0.40]이다. 코드 교정은 같은 원 실험 lineage와
  버전 seal 검증을 만족하는 역사 capture 경로에만 적용하고 일반 경로 검사는 유지한다.
  [결함/원본 해시](../../../exec-plans/evidence/ep133/baseline-defect.json) · [독립 계산](../../../exec-plans/evidence/ep133/baseline-independent.json).

## 중단·복구

INDEX 공통 기준과 EX081의 새 실행 규칙을 따른다. 사전 도구 교정·validation 검증은 같은
8시간 안에서 허용하고 배틀 재수집0이다. 필수 gate 실패로 의존 배틀을 시작하지 않는다.
실패·부분 결과·첫 시계·원본을 보존하며 중단 처리의 완료를20경기 완료로 해석하지 않는다.

## 결과 및 증거

20경기 모두 정상/유효 완료,0승0무20패·실패/무효/미실행0이다.970결정·6629후보와
실제 전송970건을 전수 감사했다. 두 새 프로세스 각320관측/2991후보의 원 예측 및 상호 q
최대차이는0이다. GPU0 원경로 재qualification 통과이며 과거 GPU1 불일치 원인은 미확정이다.

역사 경로 교정18검사가 통과했고 동일 원자료에서20쌍을 정정했다. 기준선은11승9패,
점수차−55%p·5팀 bootstrap95%[-70,-40]%p로 독립 계산과 일치한다. 이는 역사 구성 비교이며
학습 단독 효과나 일반 Gen9 OU 효능을 확증하지 않는다. 원 보고/뷰어·원자료와
원 EX066 실패/가중치를 보존했고 재수집·추가 모델 호출0이다.

최초 브라우저 검사는 링크 이동 직후 초기화 전 option 개수0을 읽었다. 독립20페이지에서
화면 준비 후 정확한 개수와 오류0을 확인했다. 원 실패/검사 source를 보존하고 예상 DOM 준비를
기다리는 검사만 교정했다. 지연 초기화 포함4검사와 정적 검사가 통과했으며 뷰어/데이터 변경0이다.
실제 이동·오프라인 브라우저에서20경기·970결정·6629후보·선택/전송970건 전부 확인했다.

모델/Base/checkpoint/source 불변·소유 프로세스/포트/lock 정리·GPU0 점유0을 확인했다.
원자료5368파일의 SHA256 봉인과 전수 대조를 완료했고 첫 GPU 시계부터 약3시간25분으로8시간 안에 종료했다.
실행 전123검사, 기준선 정정18검사, 브라우저 검사 교정4검사를 해당 source에 연결한다.

- [최종 완료·봉인](../../../exec-plans/evidence/ep133/completion.json)
- [정정 보고](../../../../.pokechamp-data/experiments/ex081-joint-q-battle/corrections/baseline-v2/final/report.md)
- [원본 보존·정정 receipt](../../../../.pokechamp-data/experiments/ex081-joint-q-battle/corrections/baseline-v2/final/receipt.json)
- [이동 후 오프라인 전수 검증](../../../../.pokechamp-data/experiments/ex081-joint-q-battle/corrections/viewer-check-v3/viewer-offline.json)
- [최종20경기 뷰어](../../../../exports/battle_viewers/ex081-baseline-v2/index.html)

최초 `final/`과 `exports/battle_viewers/ex081/`는 기준선 누락 당시의 봉인본으로 유지한다.
현재 최종 분석/열람은 위 정정본을 사용한다. 추가 학습·EX066 오프라인 test 실행은 하지 않았다.
