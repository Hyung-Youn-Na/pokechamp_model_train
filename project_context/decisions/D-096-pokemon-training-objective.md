# D-096 — 세 RLCD 환경을 활용한 포켓몬 전용 학습 당면 목표 채택

- 상태: Accepted
- 날짜: 2026-09-28

## 맥락과 승인 근거

LAYA-RLCD·EVE-RLCD·RLCD-Lite의 독립 환경 구성을 EP-096–098에서 완료했다.
사용자는 “현재 구성한 3개의 jev 계열 학습 환경을 활용해 포켓몬 배틀에 최적화 학습을
진행하는 것을 당면 목표로 하도록 문서를 업데이트”하도록 명시적으로 지시했다.

## 결정

세 환경을 활용해 포켓몬 배틀에 특화된 행동 선택 모델을 학습하고 그 성능을 평가하는 것을
현재 우선하는 연구 목표로 채택한다. 상위 의도는 [CHARTER](../CHARTER.md#immediate-objective),
연구 질문·산출물·미정 설계·해석은 [연구 설계](../RESEARCH_DESIGN.md#pokemon-training-objective)가 소유한다.

L1-L5 장기 목표와 D-063의 입력 정보·이력·요약 연구 목표는 유지한다.
[D-063](D-063-intermediate-research-objectives.md)의 “현재 단계는 입력 정보 탐색”이라는
우선순위 표시는 이번 결정으로 대체한다. 기존 실험과 관측·입력 연구는 새 학습 설계의
참고 근거이며, 해당 연구의 완료나 데이터의 학습용 채택을 뜻하지 않는다.

## 근거와 영향

준비된 세 환경을 다음 연구의 학습 기반으로 사용하도록 목표와 현재 단계를 연결한다.
“JEV 계열”은 이 작업에서 구조화 결정/RLCD 학습을 위한 세 오픈소스 환경을 가리킨다.
TypeSafe JEV의 원본 가중치나 공식 학습 구현을 확보했다는 뜻이 아니다.

CHARTER·RESEARCH_DESIGN·STATUS와 탐색 색인을 동기화한다. 모델 초기값,
학습 데이터·분할·알고리즘·보상·연산 예산·평가 protocol은 후속 설계에서 정한다.
이번 범위는 목표 문서화다. 실제 학습·새 배틀·API 호출이나 과거 중단 실험 재개는 수행하지 않는다.
환경 설치 성공을 포켓몬 성능 향상으로 해석하지 않고 기존 결과·판정·Blocked를 보존한다.

## 증거

- 현재 대화의 명시적 사용자 지시.
- [LAYA 환경 구성](../exec-plans/completed/EP-096-laya-training-environment.md),
  [EVE 환경 구성](../exec-plans/completed/EP-097-eve-rlcd-environment.md),
  [RLCD-Lite 환경 구성](../exec-plans/completed/EP-098-rlcd-lite-environment.md).
- 문서 반영·검증: [EP-099](../exec-plans/completed/EP-099-pokemon-training-objective.md).
