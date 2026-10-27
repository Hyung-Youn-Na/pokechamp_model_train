# EP-009 — 배틀 환경과 행동 출력 계약 수정

- Status: Completed
- 생성일: 2026-09-07
- 책임자: Codex
- 계약: C-010, C-011, C-012
- Decision: [D-017](../decisions/D-017-battle-identity-action-candidates.md)

## 목표와 범위

사용자 계획과 D-017의 식별/후보/환경 오류 수정, 오프라인 및 로컬 검증, 144회 Cloud 검증,
조건부8판→32판을 수행한다. Parent integration과 project_context 및 새 원자료만 변경한다.
Pinned source, 기존 실험/분모, 모델 설정, seed/팀, minimax depth 오류를 보존한다.

## 완료 기준

- [x] 정확한 식별·parser 격리·요청 후보 통합 구현 및 실패 원인 기록
- [x] 과거8판/응답4개와 경계 조건, 기존 일정/seal/admission/cancel 회귀 통과
- [x] b04 로컬8판 정상 완료 및 원자료 보존
- [x] 새24개 corpus seal, 1/10 각각3회144요청 검증 및 gate 판단
- [x] gate 통과 시 Cloud8판 및 조건부32판, 미달 시 원인 보존 및 후속 미실행
- [x] 비용/시간/fallback/integrity/정리와 상태 문서 갱신

## 중단 조건

상위 authority 충돌은 보고한다. 첫 출력 오류를 terminal 처리한다. 각 단계 기준 미달이면
후속 실험을 시작하지 않는다. Cloud부터4시간/신규3시간45분/정리15분과32판추정*1.5를 적용한다.

## 진행 상황

- 2026-09-07 — 상위 문서와 active 부재, EX-014 원인에 대응하는 pinned 구현 확인. 구현 전 등록.

- 2026-09-07 — 원본 nickname 오류8판 재현, 수정 후16 actor replay의 request/switch 팀6 및
  객체 동일성 통과. 과거 출력4개 계속 거부,24상태 모든 후보의 JSON→실제 BattleOrder 변환 통과.
  120 tests 통과. 로컬 b04팀6/12(Cloud역할 seeded Random)8/8유효·오류0·16 actor seals 통과.
  [EX-015](../experiments/EX-015-action-candidate-validation.md) 사전등록. Cloud 검증 준비 중.

## 결과 및 증거

D-017 구현과 계획된 단계 검증을 완료했다.122 tests/Ruff,원본 오류8판 재현 및 수정된
16 actor replay,과거 출력4개 거부,로컬8/8이 통과했다. Cloud144회 중140회 통과·출력 오류4건
(모두 금지된gigatonhammer),전송 오류0이다. 실제 HTTP겹침10,p95비율1.124배,129.97초였다.
출력 gate 미달로 Cloud8/32판을 시작하지 않고 이 bounded 작업을 종결한다. 실패 보충은 없다.
16 local actor/144 call seals,Cloud38개 source archive,기존EX-014 plan/64 actor seals,
credential 비노출,pinned submodule/포트/permit 정리와4시간 제한을 검증했다.

[EX-015](../experiments/EX-015-action-candidate-validation.md),
[상세 결과](../../../../.pokechamp-data/action-validation/identity-candidates-v1/report.md).
남은 한계는 모델의 후보 밖 선택이다. Minimax depth/fallback 수정과 추가 재실행은 범위 밖이다.
