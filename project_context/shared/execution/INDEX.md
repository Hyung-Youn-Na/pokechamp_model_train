# 공통 실행·운영 측정

## 연구 질문·역할

실행 환경·호출·동시성·재현과 실패 처리를 어떻게 관리하는가?

공통 규칙과 본 주제의 적용 범위를 함께 읽는다. 같은 폴더에 속한다는 사실만으로 실험의 직접 비교 가능성이나 효능 개선을 주장하지 않는다.

## 읽기 경로

[DESIGN.md](DESIGN.md) · [CONTRACTS.md](CONTRACTS.md) · [ARCHITECTURE.md](ARCHITECTURE.md)

[개별 기록과 원문 상태](RECORDS.md) · [전체 계획 상태](../../catalog/plans.md) · [방법별 탐색](../../catalog/by-method.md) · [기록 관계](../../catalog/relations.md)

## 연구 흐름과 해석 경계

### 기준선과 운영 측정

[EX-001](experiments/EX-001-pokechamp-baseline-pilot.md) → [EX-004](experiments/EX-004-model-concurrency-calibration.md) → [EX-016](experiments/EX-016-upstream-fallback.md)

동시성·지연·fallback과 실제 효능 비교를 구분한다.

### 환경·호출 기반

[EP-061](plans/EP-061-jev-client.md) → [EP-096](plans/EP-096-laya-training-environment.md) → [EP-097](plans/EP-097-eve-rlcd-environment.md) → [EP-098](plans/EP-098-rlcd-lite-environment.md) → [EP-178](plans/EP-178-openai-decisions-environment.md)

환경의 존재나 준비 완료를 새 실험 실행 권한으로 해석하지 않는다.

## 갱신

새 D·EP·EX는 이 폴더의 decisions/plans/experiments에 등록한다. 상태 변경으로 경로를 옮기지 않는다. 원문을 갱신한 뒤 등록부와 생성 색인을 갱신한다.
