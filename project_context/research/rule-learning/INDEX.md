# 규칙 이해 학습·적용

## 연구 질문·역할

규칙 QA 학습이 같은 과제의 정답률과 실제 행동 적용에 어떻게 연결되는가?

공통 규칙과 본 주제의 적용 범위를 함께 읽는다. 같은 폴더에 속한다는 사실만으로 실험의 직접 비교 가능성이나 효능 개선을 주장하지 않는다.

## 읽기 경로

[DESIGN.md](DESIGN.md) · [CONTRACTS.md](CONTRACTS.md) · [ARCHITECTURE.md](ARCHITECTURE.md)

[개별 기록과 원문 상태](RECORDS.md) · [전체 계획 상태](../../catalog/plans.md) · [방법별 탐색](../../catalog/by-method.md) · [기록 관계](../../catalog/relations.md)

## 연구 흐름과 해석 경계

### 자료 생성

[EP-169](plans/EP-169-showdown-ruleqa.md) · [Gen9 타입 전수 자료 EP192](plans/EP-192-gen9-type-matchup-dataset.md) · [System 1 표현 EP193](plans/EP-193-gen9-type-system1-data.md) · [상태이상 System 1 EP195](plans/EP-195-gen9-status-system1-data.md) · [우선도 System 1 EP196](plans/EP-196-gen9-priority-system1-data.md) · [날씨·영역 System 1 EP197](plans/EP-197-gen9-weather-terrain-system1-data.md) · [실제 리플레이 KO EP198](plans/EP-198-replay-ko-system1-data.md) · [조건부 KO EP199](plans/EP-199-conditional-ko-system1-data.md) · [Smogon 역할 EP200](plans/EP-200-smogon-role-system1-data.md) · [우선순위별 규칙 적용 EP201](plans/EP-201-gen9-mechanics-system1-data.md)

제어 장면에서 만든 규칙 QA 자료이며 세 표현을 독립 표본으로 합산하지 않는다.

### Tacit 학습과 후속 배틀

[EX-107](experiments/EX-107-tacit-ruleqa-lora.md) → [EX-108](experiments/EX-108-tacit-ruleqa-battle32.md)

QA 성적과 실제 배틀은 다른 과제다. EX-108에는 미학습 기반 배틀 대조가 없어 학습의 실전 개선 효과를 단정하지 않는다.

### JevK5 선택형 학습

[EX-113](experiments/EX-113-jevk5-ruleqa-lora.md) → [EP-184](plans/EP-184-jevk5-ruleqa-lora.md)

동일 자료 계열의 state_mc와 선택지 손실을 사용한다. 진행과 최종 판단은 원문에서 확인하며 Tacit와 동일 처치로 취급하지 않는다.

## 갱신

새 D·EP·EX는 이 폴더의 decisions/plans/experiments에 등록한다. 상태 변경으로 경로를 옮기지 않는다. 원문을 갱신한 뒤 등록부와 생성 색인을 갱신한다.
