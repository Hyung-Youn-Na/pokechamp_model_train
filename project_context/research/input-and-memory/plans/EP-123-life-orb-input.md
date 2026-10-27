# EP-123 — Life Orb 공개 입력 교정

- 상태: Completed
- 생성일: 2026-10-07
- 책임자: Codex
- 승인: 사용자 Life Orb 입력 버그 수정 요청
- 계약: [C-055](../../policy-learning/CONTRACTS.md#c-055-imitation)

## 목표·범위

공개 반동 `-damage ... [from] item: Life Orb`의 보유자를 공개 도구 목록에 반영한다.
공유 offline/live serializer·회귀 검사만 변경한다. 일반 도구 공개 처리 확대·학습/재평가 제외.
INDEX/CHARTER·EP-119/108/103 보존 경계를 확인했다. 기존 실험 source·원자료·가중치·판정 보존.

## 완료 기준

- [x] 공개 전 unknown, 반동 후 lifeorb, 최근4턴 이력 밖에서도 유지
- [x] 도구 제거·교체 이후 현재 도구 상태 보존, 다른 미공개 포켓몬 정보 비노출
- [x] 관련 CPU 회귀 검사·문서 완료

## 중단·검증

비실험 CPU 교정이므로 새 GPU/배틀·재수집·실험 시계 없음. INDEX 공통 기준 적용.
실제 EX-075 입력 하나를 읽기 전용 재구성하여 교정 차이를 확인한다.

## 진행

- 2026-10-07 — 등록. 원인은 공개 목록이 -item/-enditem만 처리하고 반동 공개를 누락한 것.

## 결과·증거

- Life Orb 반동 공개만 public_item에 등록한다. 현재 값·제거·재획득은 기존 parser가 소유한다.
- [CPU 회귀](../../../exec-plans/evidence/ep123/tests.log): 27검사·15subtest 통과.
  최초 검사는 Trick 선행 이벤트 없는 fixture 오류1건으로 실패했고 fixture만 교정했다.
  [실패 원문](../../../exec-plans/evidence/ep123/tests-fixture-error.log)을 보존한다.
- [실제 EX-075 재구성](../../../exec-plans/evidence/ep123/ex075-reconstruction.json): 동일 공개 prefix에서
  상대 첫 슬롯 item만 null→lifeorb, 나머지 입력 동일·schema 유효·원본 SHA 불변.
- 공개 전/일반 피해 미노출, 공개 후4턴 이력 밖 유지, 타 슬롯 미노출,
  제거 후 null·재획득 후 새 도구 반영을 실제 CPU parser 경로로 검증했다.
- 과거 입력·학습 모델·보고서·동결 source는 수정하지 않았다. 과거 전체 영향 범위와 성능 효과는
  미측정이며 이번 교정은 향후 새 입력 생성에 적용한다. 다른 도구의 공개 경로 확대는 범위 밖이다.
