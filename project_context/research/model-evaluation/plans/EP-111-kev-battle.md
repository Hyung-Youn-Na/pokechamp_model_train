# EP-111 — 학습된 Kev-4B 실시간 배틀 연결

- 상태: Completed
- 완료일: 2026-10-01
- 생성일: 2026-09-30
- 책임자: Codex
- 승인 근거: 현재 사용자의 pokechamp r1 연결·validation 재현·1경기 smoke 의뢰
- 관련: [D-108](../decisions/D-108-kev-battle.md), [C-054](../CONTRACTS.md#c-054-kev-battle), [EX-068](../experiments/EX-068-kev-battle.md)

## 목표와 범위

Kev의 후보별 p(true)를 공식 관측 기반 JointInput에 연결하여 최대값 후보를 전송하고,
validation 입력 bytes·저장 예측·실전 전송을 검증한다. INDEX/CHARTER·STATUS·계획 색인과
겹치는 EP-103/108 및 C-051, 관련 RD/architecture/ADR을 확인했다. 기존 중단 실험과
EX-066 학습은 재개·변경하지 않는다. 독립 구현/검증을 서브에이전트에 분리 위임하고 통합한다.

`integration/pokechamp/kev*`, 관련 검사·CLI·문서·새 evidence만 변경한다. `/ref/kev`는
읽기 전용이며 test partition 열람·재학습·기존 q/배틀 자료의 학습 전용은 금지한다.
Kev 서버는 별도 사용자 실행 승인 또는 사용자가 준비한 서버를 필요로 한다. 승인 전에는
서버를 시작하지 않으며 CPU 준비·검증을 완료한다. GPU3 외 Kev 실행과 동시 GPU3 작업은 금지한다.
실험 설정·gate·분모·복구·Tera 조건은 EX-068이 소유한다.

## 완료 기준

- [x] 문자열 state·정확한 질문·순서·완전한 noul·동률·불량/오래된 응답 무전송 검사
- [x] validation private roots에서 live 생성 경로 재생, 저장 model_input과 bytes 일치
- [x] D-109 추가 승인 조건의 같은 입력 서버 예측과 development rows의 p[1]이 소수 넷째 자리까지 일치
- [x] 1경기 정상 종료·모든 결정 Kev 호출·fallback0·rqid/합법성/전송 전수 감사
- [x] C-047 뷰어·한국어 보고·봉인·소유 자원 정리·실행 방법과 상태 동기화

## 검증과 진행

- 2026-09-30 — 사용자 의뢰와 서버 실행의 별도 승인 경계를 등록했다. 구현 전.
- 검사/실행 결과는 `project_context/exec-plans/evidence/ep111/`와 EX-068 evidence에 보존한다.
- 2026-10-01 — live 생성기의 validation3관측/24후보 byte 재현 통과. 서버 실행0.
  팀 제출 검사에서 poke-env 텍스트 변환의 지역 폼 닉네임 변화가 발견되어 원 packed 팀을
  그대로 전송하고 모델용 own.text는 유지하도록 교정했다. 실제 경기/모델 요청에는 영향0.
  bb7185c의 기본 fused/merge 동작과 의뢰의 unmerged 설명 차이는 EX-068에 명시했다.
- 2026-10-01 — 통합169검사(실패/skip0), 이동 후 오프라인 브라우저 검사와 head/Base 캐시
  provenance를 검증했다. 새 team1/p2/seed·source444파일·3관측을 동결 준비했다.
  예측 재현/실제1경기/실전 뷰어는 서버 시작 별도 승인 전으로 미실행이다.
  [준비 보고](../../../exec-plans/evidence/ep111/report.md), [준비 receipt](../../../exec-plans/evidence/ep111/readiness.json).
- 2026-10-01 — 사용자가 “진행해주세요.”로 준비된 GPU3/bf16/T1/unmerged 서버 시작과
  예측 대조 통과 후1경기 smoke·감사·소유 서버 정리를 승인했다. 추가 승인 없이 같은 범위를
  이어가며 준비본과 최초 실행 증거를 보존한다. 실제 실행은 아래 별도 원장에 기록한다.
- 서버 시작 뒤 모델 요청 전, NVML의 PID와 컨테이너 PID를 직접 비교하던 준비 검사의
  환경 가정을 교정했다. 소유 HTTP socket·고정 CUDA3 설정·준비된 CUDA 모델·GPU3 단독
  프로세스로 연관성을 검증하고 두 PID/namespace/start_ticks/socket/UUID를 전후 고정한다.
  독립 검토·15검사와 원 입력/요청·모델/설정·팀/seed 불변을 확인했다. 원 준비본은 `ex068`,
  교정 준비본은 `ex068-v2`에 보존하며 기존 서버/첫 시계·실험 전체 요청/경기 상한은 유지한다.
  [교정 receipt](../../../exec-plans/evidence/ep111/process-identity-recovery.json). 모델 요청/배틀은 교정 시점0이다.
- 승인된 GPU3/bf16/T1/unmerged 서버의 첫 validation 응답이 development 기준과 달라
  배틀 진입을 중지했다. 입력/질문과 CPU 토큰열의 동일성, 실행 전후 모델/프로세스 불변을
  확인했다. 실제 요청1·배틀0이며 추가 요청 없이 소유 서버를 종료하고 GPU3 반환을 확인했다.
  원 준비/실패/교정 기록과 원 시작 시계를 보존했다. dev의 당시 merge/fused 옵션은 기록이
  없어 원인을 확정하지 않는다. 수락 검사 미충족으로 Blocked이며 Completed로 이동하지 않는다.
  [중단 보고](../../../exec-plans/evidence/ep111/report.md) · [종료 원장](../../../exec-plans/evidence/ep111/closure.json).
- 2026-10-01 — 사용자가 fused·merged 추가3관측 검증과 전부 일치 시1경기 제안에 다시
  “진행해주세요.”로 명시 승인했다(D-109). 원 실패/봉인을 유지하고 `ex068-v3`의 새 조건과
  별도 추가 요청 원장을 준비한다. 배틀 상한은 원1경기를 공유한다. 새 증거는
  `project_context/exec-plans/evidence/ep111-fused/`에 저장한다.
- v3의 변경 범위 CPU58검사(실패/skip0), 원3봉인·요청/모델/팀/seed 불변 대조와 source445파일
  동결을 완료했다. GPU3 bf16/T1/merged/fused 서버에서 선봉/일반/강제교체3관측·24후보가
  dev p와 소수 넷째 자리까지 일치했다(최대차이0). 전후 동일 프로세스/모델을 확인했고,
  전체 미사용1경기 smoke에 진입했다. 원1요청+추가3요청의 누적 validation4건을 유지한다.
  [추가 검사](../../../exec-plans/evidence/ep111-fused/tests-control-acceptance.log),
  [입력/조건 대조](../../../../.pokechamp-data/kev/ex068-v3/predecessor-comparison.json),
  [예측 gate](../../../../.pokechamp-data/kev/ex068-v3/probe.json).
- 2026-10-01 — 전체1경기 정상/유효 완료·57결정 모두 Kev 경유·fallback0을 확인했다.
  공식 재생 전수 감사와 독립 raw-event/transport 감사, 이동 후 오프라인 뷰어 검사까지
  통과했다. 첫 브라우저 검사 대기 경쟁은 실패를 보존하고 준비 대기만 보강하여 검증했다.
  소유 Kev/Showdown/worker 종료·GPU3 반환, 원3봉인·새 원자료/뷰어 봉인 보존과 현재 상태
  동기화를 완료했다. 원 unmerged 실패는 유지하며 D-109 조건에서 완료 기준을 충족했다.
  [최종 보고](../../../exec-plans/evidence/ep111-fused/report.md), [완료 검증](../../../exec-plans/evidence/ep111-fused/verification-final.json),
  [뷰어](../../../../exports/battle_viewers/ex068/index.html). 성능 효과는 미평가다.
- 완료 본문은 `completed/`로 이동한다. 원 `active/` 경로는 봉인된 첫 보고와 D-109의
  링크를 보존하는 호환 심볼릭 링크만 남기며 현재 실행 계획은 아니다.

## 중단·복구

INDEX 공통 기준과 EX-068을 따른다. 원 unmerged 예측 실패는 보존한다. D-109의 추가 승인
범위에서만 새 준비·3관측 대조를 수행하며 통과 전 배틀을 시작하지 않는다. 추가 불일치 시
의존 실행을 중단하고 소유 자원/증거를 정리한다. 미완료 수락 검사를 완료로 표시하지 않는다.
