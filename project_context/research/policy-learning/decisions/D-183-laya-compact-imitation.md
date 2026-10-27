# D-183 — laya 압축 입력 모방 학습과 표준 배틀 평가

- 상태: Accepted
- 날짜: 2026-10-22

## 맥락

- **사용자 지시**: 사용자가 GPU0을 이 작업에 배정하고 다음을 명시적으로 지시했다.
  - 현재 배틀 프롬프트를 압축한다.
  - laya에 맞게 학습한다.
  - 배틀 에이전트를 구현하는 실험을 한다.
  - 결과물은 공용 저장소 `/mnt/digicap/combined/hyna/backup/pokechamp-research/`에 남긴다.
  - Codex 에이전트용 설명자료를 둔다.
- **사용자 선택**: 입력은 EX-071 리플레이 모방 스냅샷의 압축, 라벨은 EX-071 사람 선택, 평가는 EX-089 표준 32경기다.
- **확인된 사실**:
  - laya 공개 체크포인트의 학습 길이는 512 또는 1,024토큰이다.
  - EX-071 스냅샷은 laya 토크나이저 기준 중앙값 3,304, 최대 4,024토큰이다(validation 512건).
  - v6 상태는 평균 11,940토큰이다(EX-109 입력 331건).
  - EX-089 일정의 네 팀은 EX-071 train/validation/test 어디에도 없다. EX-071이 기존 평가팀 제외로 이미 뺀 22경기에 해당한다.

## 결정

1. EX-071 `ImitationInput` 경계를 그대로 거친 스냅샷을 1,024토큰 이하의 결정적 텍스트로 렌더링한다.
2. laya 0.4.13(`/ref/laya` `6f0496f7`)을 `laya-typed-decisions`(revision `e929ae5c`)에서 이어서 학습한다. 학습은 EX-071 학습 분할의 사람 선택에 대한 soft CE다.
3. 학습과 선택은 [EX-118](../experiments/EX-118-laya-compact-imitation-training.md), 배틀 평가는 [EX-119](../experiments/EX-119-laya-compact-imitation-battle32.md), 실행은 [EP-208](../plans/EP-208-laya-compact-imitation.md), 환경은 [EP-207](../../../shared/execution/plans/EP-207-laya-0413-environment.md)이 소유한다.

## 거절한 대안

- **v6 JEV 프롬프트 압축**: v6로 렌더링할 수 있는 라벨은 joint-q EX-065/067뿐이다(학습 약 3,200관측, 내 팀 하나로 고정). 사용자가 선택하지 않았다.
- **2단계(모방 후 joint-q)**: 범위가 크다. 1단계 결과를 보고 별도 결정한다.
- **EX-071 고정 40경기 평가**: 사용자가 표준 EX-089 일정을 선택했다.

## 근거

- **학습·실전 입력 일치**: `schema.py`가 오프라인 복원과 실배틀에 같은 직렬화를 제공한다. 압축 렌더러를 그 위에 두면 학습과 실전 입력이 같다.
- **표준 비교 가능**: EX-089 일정은 기존 모델들의 표준 비교 대진이다. 학습 자료와 겹치지 않는다는 사실도 확인했다.
- **CHARTER 준수**: 학습 지표와 배틀 성능을 분리해 보고한다.

## 영향

- 새 환경, 렌더러, 자료, 학습, 서빙, 배틀 코드를 `integration/laya_imitation/`과 `.tools/laya-0.4.13/`에 추가한다. 기존 실험의 원자료, 봉인, 환경은 변경하지 않는다.
- GPU0만 사용한다. EP-203/EX-116(GPU1~3)과 자원이 겹치지 않는다.
- 배틀 결과는 같은 일정의 기존 결과(EX-089, EX-110, EX-111)와 함께 표시하되, 같은 실행 안의 기준선이 아닌 상속 근거로만 해석한다.

## 증거

- 현재 대화의 사용자 지시와 선택
- [EX-071](../experiments/EX-071-qwen-replay-imitation.md), [C-055](../CONTRACTS.md#c-055-imitation)
- [EX-089](../../input-and-memory/experiments/EX-089-jev9b-v6-corrected.md)
