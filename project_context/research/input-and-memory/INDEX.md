# 입력·관측·메모리

## 연구 질문·역할

관측 정보와 전달 표현·이력·계산 근거가 행동 선택에 어떻게 연결되는가?

공통 규칙과 본 주제의 적용 범위를 함께 읽는다. 같은 폴더에 속한다는 사실만으로 실험의 직접 비교 가능성이나 효능 개선을 주장하지 않는다.

## 읽기 경로

[DESIGN.md](DESIGN.md) · [CONTRACTS.md](CONTRACTS.md) · [ARCHITECTURE.md](ARCHITECTURE.md)

[사람용 입력 구조 설명서 모음](input-structures/README.md)

[EX-112 입력 필드 구조](input-structures/EX112_INPUT_STRUCTURE.md): v6 전체 상태·후보별 상성 요약·실제 API 포장 형식의 버전별 참조.

[개별 기록과 원문 상태](RECORDS.md) · [전체 계획 상태](../../catalog/plans.md) · [방법별 탐색](../../catalog/by-method.md) · [기록 관계](../../catalog/relations.md)

## 연구 흐름과 해석 경계

### 초기 IO·요약·계산 진단

[EX-017](experiments/EX-017-improved-io-offline.md) → [EX-025](experiments/EX-025-summary-max-diagnostic.md) → [EX-038](experiments/EX-038-ab-head-to-head32-b2.md)

입력 의미·요약·계산 결함과 전달 표현의 변경을 구분한다. 중단/무효 분모는 각 실험에서 보존한다.

### JEV 입력과 공개 정보

[EX-051](experiments/EX-051-jev-v2-battle.md) → [EX-058](experiments/EX-058-jev-improved32.md) → [EX-086](experiments/EX-086-jev27b-public-memory-v6.md) → [EX-088](experiments/EX-088-jev27b-v6-corrected.md) → [EX-089](experiments/EX-089-jev9b-v6-corrected.md)

v6의 중단 원실행과 교정된 신규 평가를 구분한다. 모델 패키지 변경과 입력 효과를 분리해서 읽는다.

### 정보 제거와 후보별 적용결과

[EX-090](experiments/EX-090-jev9b-no-damage.md) → [EX-110](../model-evaluation/experiments/EX-110-openai-decisions-retry32.md) → [EX-112](experiments/EX-112-openai-candidate-matchup-battle.md)

피해 예측 제거는 EX-089와, 후보별 요약은 EX-110과 연결한다. EX-112의 분모 미달과 탐색 비교 한계를 유지한다.

## 갱신

새 D·EP·EX는 이 폴더의 decisions/plans/experiments에 등록한다. 상태 변경으로 경로를 옮기지 않는다. 원문을 갱신한 뒤 등록부와 생성 색인을 갱신한다.

[후보 중심 v7 구조·예시](input-structures/EX115_INPUT_STRUCTURE.md): D-179/EX-115의 기술 후보 직접 설명·피해 분기 재배치와 정보 보존 gate.
