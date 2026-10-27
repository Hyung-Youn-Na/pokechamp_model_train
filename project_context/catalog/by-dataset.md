# 관련 자료별 탐색

<!-- generated: scripts/context-catalog build -->

탐색 분류는 처치의 동일성·실제 실행·직접 비교 가능성을 보증하지 않는다. 관련 모델·자료에는 기준선과 참조도 포함하며 실제 조건은 원문을 확인한다.

| 분류 | 기록 수 |
|---|---|
| [EX-089 fixed32](#ex-089-fixed32) | 3 |
| [Smogon](#smogon) | 22 |
| [conditional-ko-system1-v1](#conditional-ko-system1-v1) | 2 |
| [gen9-mechanics-system1-v1](#gen9-mechanics-system1-v1) | 2 |
| [gen9-priority-system1-v1](#gen9-priority-system1-v1) | 1 |
| [gen9-status-system1-v1](#gen9-status-system1-v1) | 1 |
| [gen9-type-matchup-v1](#gen9-type-matchup-v1) | 3 |
| [gen9-type-system1-v1](#gen9-type-system1-v1) | 1 |
| [gen9-weather-terrain-system1-v1](#gen9-weather-terrain-system1-v1) | 1 |
| [joint-q](#joint-q) | 16 |
| [laya-compact-imitation](#laya-compact-imitation) | 24 |
| [laya-effect-knowledge](#laya-effect-knowledge) | 3 |
| [laya-outcome-weights](#laya-outcome-weights) | 3 |
| [laya-tera-knowledge](#laya-tera-knowledge) | 15 |
| [milkkarten/pokechamp](#milkkartenpokechamp) | 2 |
| [replay](#replay) | 9 |
| [replay-ko-system1-v1](#replay-ko-system1-v1) | 4 |
| [showdown-ruleqa-v1](#showdown-ruleqa-v1) | 14 |
| [smogon-gen9ou-20261019](#smogon-gen9ou-20261019) | 2 |
| [smogon-role-system1-v1](#smogon-role-system1-v1) | 2 |
| [system1-full](#system1-full) | 3 |

## EX-089 fixed32

| ID | 제목 | 상태 |
|---|---|---|
| [D-186](../research/rule-learning/decisions/D-186-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Accepted |
| [EP-211](../research/rule-learning/plans/EP-211-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Completed |
| [EX-123](../research/rule-learning/experiments/EX-123-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Completed |

## Smogon

| ID | 제목 | 상태 |
|---|---|---|
| [D-017](../shared/execution/decisions/D-017-battle-identity-action-candidates.md) | 배틀 식별과 요청별 행동 후보 통합 | Accepted |
| [D-019](../research/input-and-memory/decisions/D-019-improved-io.md) | IO 관측·계산·고정 정책 및 배틀 내 요약 비교 | Accepted |
| [D-020](../research/input-and-memory/decisions/D-020-project-owned-ruination-patch.md) | 프로젝트 소유 Ruination 계산 패치 | Accepted |
| [D-021](../research/input-and-memory/decisions/D-021-special-move-diagnostics.md) | 특수 기술 피해의 독립 오프라인 진단 | Accepted |
| [D-034](../research/input-and-memory/decisions/D-034-calculator-entry-calcfix32.md) | 계산기 등장 특성 교정 및 동일32판 | Accepted |
| [D-040](../research/input-and-memory/decisions/D-040-smogon-diagnostic-design.md) | Smogon 기반 원본 A 진단 평가 준비 | Accepted — 평가 준비 범위 |
| [D-041](../research/input-and-memory/decisions/D-041-a-diagnostic64.md) | Smogon 원본 A64 진단 실행 | Accepted |
| [D-061](../research/lead-policy/decisions/D-061-lead-matchup-rules.md) | 선봉 전략과 규칙 입력의 독립 개선 | Accepted |
| [D-107](../research/action-value/decisions/D-107-abyssal-tera-joint-q.md) | Abyssal Tera 보완 학습 데이터 | Accepted |
| [D-112](../research/policy-learning/decisions/D-112-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 채택 | Accepted |
| [D-154](../research/planner-executor/decisions/D-154-matchup-events.md) | 매치업 변화 기반 계획 갱신 | Accepted |
| [EP-022](../research/input-and-memory/plans/EP-022-calculator-entry-calcfix32.md) | 계산기 등장 특성 교정 및 동일32판 | Completed — 사용자 중단 대안 포함 완료; 성능 비교 미완료 |
| [EP-028](../research/input-and-memory/plans/EP-028-smogon-diagnostic-design.md) | Smogon 기반 원본 A 진단 평가 준비 | Completed — 평가 준비 구현·로컬 검증 완료, 대전 미실행 |
| [EP-029](../research/input-and-memory/plans/EP-029-a-diagnostic64.md) | Smogon 원본 A64 진단 실행 | Completed |
| [EP-082](../research/input-and-memory/plans/EP-082-jev-damage-samples.md) | 기술별 피해량 범위 오프라인 프롬프트 샘플 | Completed |
| [EP-174](../shared/datasets/plans/EP-174-smogon-ou-strategy-links.md) | Smogon OU 포켓몬·전략 링크 목록 | Completed |
| [EP-175](../shared/datasets/plans/EP-175-smogon-ou-strategy-data.md) | Smogon OU 전략 전수 수집 | Completed |
| [EX-017](../research/input-and-memory/experiments/EX-017-improved-io-offline.md) | 개선 IO 오프라인 검증 | Stopped |
| [EX-029](../research/input-and-memory/experiments/EX-029-calculator-entry-calcfix32.md) | 계산기 교정 동일 조건 A/B32판 | Completed — 승인된 중단 포함 작업 완료; 32판 성능 비교 미완료 |
| [EX-030](../research/input-and-memory/experiments/EX-030-calculator-input-audit.md) | 계산기 입력 전체 로컬 진단 | Completed |
| [EX-034](../research/input-and-memory/experiments/EX-034-smogon-diagnostic-design.md) | Smogon 기반 원본 A 운용 한계 진단 설계 | Prepared — 팀·대진·검토·자원 명세 검증 완료, 대전 미실행 |
| [EX-035](../research/input-and-memory/experiments/EX-035-a-diagnostic64.md) | Smogon 원본 A64 진단 실험 | Completed — 유효64/64·A50승14패·1902결정 전수검토·보고·보존/정리 완료 |

## conditional-ko-system1-v1

| ID | 제목 | 상태 |
|---|---|---|
| [D-176](../research/rule-learning/decisions/D-176-conditional-ko-system1-data.md) | 조건부 KO와 관측 KO의 분리 | Accepted |
| [EP-199](../research/rule-learning/plans/EP-199-conditional-ko-system1-data.md) | 조건부 확정 KO 판정 자료 | Completed |

## gen9-mechanics-system1-v1

| ID | 제목 | 상태 |
|---|---|---|
| [D-178](../research/rule-learning/decisions/D-178-gen9-mechanics-system1-data.md) | 우선순위별 규칙 적용과 정보 충분성 자료 | Accepted |
| [EP-201](../research/rule-learning/plans/EP-201-gen9-mechanics-system1-data.md) | 우선순위별 Gen9 규칙 적용 System 1 자료 | Completed |

## gen9-priority-system1-v1

| ID | 제목 | 상태 |
|---|---|---|
| [EP-196](../research/rule-learning/plans/EP-196-gen9-priority-system1-data.md) | Gen9 행동 우선도 System 1 자료 | Completed |

## gen9-status-system1-v1

| ID | 제목 | 상태 |
|---|---|---|
| [EP-195](../research/rule-learning/plans/EP-195-gen9-status-system1-data.md) | Gen9 상태이상 System 1 학습자료 | Completed |

## gen9-type-matchup-v1

| ID | 제목 | 상태 |
|---|---|---|
| [D-174](../research/rule-learning/decisions/D-174-gen9-type-matchup-dataset.md) | Gen9 타입 상성 전수 자료 | Accepted |
| [EP-192](../research/rule-learning/plans/EP-192-gen9-type-matchup-dataset.md) | Gen9 타입 상성 전수 학습 데이터 | Completed |
| [EP-193](../research/rule-learning/plans/EP-193-gen9-type-system1-data.md) | Gen9 타입 System 1 판별 학습자료 | Completed |

## gen9-type-system1-v1

| ID | 제목 | 상태 |
|---|---|---|
| [EP-193](../research/rule-learning/plans/EP-193-gen9-type-system1-data.md) | Gen9 타입 System 1 판별 학습자료 | Completed |

## gen9-weather-terrain-system1-v1

| ID | 제목 | 상태 |
|---|---|---|
| [EP-197](../research/rule-learning/plans/EP-197-gen9-weather-terrain-system1-data.md) | Gen9 날씨·영역 System 1 자료 | Completed |

## joint-q

| ID | 제목 | 상태 |
|---|---|---|
| [D-103](../research/action-value/decisions/D-103-joint-q-data.md) | 다경기 공동 q 데이터 | Accepted |
| [D-104](../research/action-value/decisions/D-104-joint-q-training.md) | EX-065 기반 Base 공동 q 학습 | Accepted |
| [D-105](../research/action-value/decisions/D-105-joint-q-gpu2.md) | 공동 q 학습의 GPU2 지정 | Accepted |
| [D-106](../research/action-value/decisions/D-106-joint-q-idle-gpu.md) | 공동 q 학습의 유휴 GPU 대체 | Accepted |
| [D-107](../research/action-value/decisions/D-107-abyssal-tera-joint-q.md) | Abyssal Tera 보완 학습 데이터 | Accepted |
| [D-110](../research/model-evaluation/decisions/D-110-kev-test-battles.md) | 기존 test 대진의 Kev 본 배틀 | Accepted |
| [D-129](../research/action-value/decisions/D-129-joint-q-battle.md) | EX066 epoch3의 GPU0 배틀 평가 | Accepted |
| [EP-107](../research/action-value/plans/EP-107-joint-q-data.md) | Abyssal 80경기 공동 q 데이터 | Completed |
| [EP-108](../research/action-value/plans/EP-108-joint-q-training.md) | EX-065 기반 Base 공동 q 학습 | Blocked |
| [EP-110](../research/action-value/plans/EP-110-abyssal-tera-joint-q.md) | Abyssal Tera 정책과 보완 공동 q 데이터 | Completed |
| [EP-112](../research/model-evaluation/plans/EP-112-kev-test-battles.md) | EX-065 test20 대진의 Kev 본 테스트 | Completed |
| [EX-065](../research/action-value/experiments/EX-065-joint-q-data.md) | Abyssal 80경기 기반 공동 q 학습 데이터 | Completed |
| [EX-066](../research/action-value/experiments/EX-066-joint-q-training.md) | Qwen3.5-4B-Base 공동 q 학습·독립 평가 | Blocked — 새 프로세스 재로딩 gate 실패 |
| [EX-067](../research/action-value/experiments/EX-067-abyssal-tera-joint-q.md) | Abyssal Tera 보완 공동 q 데이터 | Completed |
| [EX-068](../research/model-evaluation/experiments/EX-068-kev-battle.md) | Kev-4B pokechamp r1 연결 smoke | Completed — D-109 조건의 연결 수락 검사 완료. 원 unmerged gate 실패는 보존. |
| [EX-069](../research/model-evaluation/experiments/EX-069-kev-test-battles.md) | EX-065 test20 고정 대진의 Kev 본 테스트 | Completed |

## laya-compact-imitation

| ID | 제목 | 상태 |
|---|---|---|
| [D-183](../research/policy-learning/decisions/D-183-laya-compact-imitation.md) | laya 압축 입력 모방 학습과 표준 배틀 평가 | Accepted |
| [D-185](../research/policy-learning/decisions/D-185-laya-modular-renderer-v2.md) | laya 모듈형 렌더러 v2(기술 변형·속도·교체·피해량) | Accepted |
| [D-187](../research/policy-learning/decisions/D-187-laya-tera-knowledge.md) | laya v2에 테라 기본 지식 데이터 추가(GPU1) | Accepted |
| [D-188](../research/policy-learning/decisions/D-188-laya-effect-knowledge.md) | laya v2+테라에 기술·도구·특성 효과 지식 데이터 추가(GPU2) | Accepted |
| [D-189](../research/policy-learning/decisions/D-189-laya-renderer-v3-opponent-sets.md) | laya 렌더러 v3(상대 세트 추론)와 래더 대비 학습(GPU0) | Accepted |
| [D-190](../research/policy-learning/decisions/D-190-laya-ex129-gate-override.md) | EX-128 진행 조건 미충족에도 EX-129 배틀 실행(사용자 결정) | Accepted |
| [D-191](../research/policy-learning/decisions/D-191-no-offline-battle-gate.md) | 오프라인 test 평가로 배틀 평가를 거르지 않는다 | Accepted |
| [D-192](../research/policy-learning/decisions/D-192-laya-renderer-v4-fail-out.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해)와 GPU1 학습·배틀 | Accepted |
| [D-193](../research/policy-learning/decisions/D-193-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방(GPU0 학습·배틀) | Accepted |
| [D-195](../research/policy-learning/decisions/D-195-laya-item-state-renderer-v5.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터)와 학습·배틀 | Accepted |
| [EP-208](../research/policy-learning/plans/EP-208-laya-compact-imitation.md) | laya 압축 입력 모방 학습·배틀 에이전트 | Completed |
| [EP-210](../research/policy-learning/plans/EP-210-laya-renderer-v2.md) | laya 모듈형 렌더러 v2 학습과 v1·v2 비교 | Completed |
| [EP-214](../research/policy-learning/plans/EP-214-laya-renderer-v3.md) | laya 렌더러 v3(상대 세트 추론) 학습과 배틀 비교(GPU0) | Completed |
| [EP-215](../research/policy-learning/plans/EP-215-laya-renderer-v4.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) 학습과 배틀 비교(GPU1) | Active |
| [EP-216](../research/policy-learning/plans/EP-216-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방 학습과 배틀 비교(GPU0) | Active |
| [EP-218](../research/policy-learning/plans/EP-218-laya-renderer-v5-item-state.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) 학습과 배틀 비교(GPU0·GPU2) | Active |
| [EX-118](../research/policy-learning/experiments/EX-118-laya-compact-imitation-training.md) | laya 압축 입력 리플레이 모방 학습 | Completed |
| [EX-121](../research/policy-learning/experiments/EX-121-laya-v2-all-training.md) | laya 모듈형 렌더러 v2(4종 전부) 학습과 v1 쌍비교 | Completed |
| [EX-124](../research/policy-learning/experiments/EX-124-laya-v2-tera-knowledge-training.md) | laya v2 + 테라 기본 지식 데이터 학습(GPU1) | Completed |
| [EX-126](../research/policy-learning/experiments/EX-126-laya-v2-tera-effect-training.md) | laya v2 + 테라 + 효과 지식 데이터 학습(GPU2) | Completed |
| [EX-128](../research/policy-learning/experiments/EX-128-laya-v3-tera-training.md) | laya 렌더러 v3(상대 세트 추론) + 테라 지식 학습(GPU0) | Completed |
| [EX-130](../research/policy-learning/experiments/EX-130-laya-v4-tera-training.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) + 테라 지식 학습(GPU1) | Running |
| [EX-132](../research/policy-learning/experiments/EX-132-laya-v2t-outcome-weighted-training.md) | laya v2+테라 승패 가중 모방 학습(GPU0) | Running |
| [EX-136](../research/policy-learning/experiments/EX-136-laya-v5-tera-training.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) + 테라 지식 학습(GPU0) | Planned |

## laya-effect-knowledge

| ID | 제목 | 상태 |
|---|---|---|
| [D-188](../research/policy-learning/decisions/D-188-laya-effect-knowledge.md) | laya v2+테라에 기술·도구·특성 효과 지식 데이터 추가(GPU2) | Accepted |
| [EP-213](../research/policy-learning/plans/EP-213-laya-effect-knowledge.md) | laya v2+테라+효과 지식 데이터 학습과 배틀 비교(GPU2) | Completed |
| [EX-126](../research/policy-learning/experiments/EX-126-laya-v2-tera-effect-training.md) | laya v2 + 테라 + 효과 지식 데이터 학습(GPU2) | Completed |

## laya-outcome-weights

| ID | 제목 | 상태 |
|---|---|---|
| [D-193](../research/policy-learning/decisions/D-193-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방(GPU0 학습·배틀) | Accepted |
| [EP-216](../research/policy-learning/plans/EP-216-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방 학습과 배틀 비교(GPU0) | Active |
| [EX-132](../research/policy-learning/experiments/EX-132-laya-v2t-outcome-weighted-training.md) | laya v2+테라 승패 가중 모방 학습(GPU0) | Running |

## laya-tera-knowledge

| ID | 제목 | 상태 |
|---|---|---|
| [D-187](../research/policy-learning/decisions/D-187-laya-tera-knowledge.md) | laya v2에 테라 기본 지식 데이터 추가(GPU1) | Accepted |
| [D-188](../research/policy-learning/decisions/D-188-laya-effect-knowledge.md) | laya v2+테라에 기술·도구·특성 효과 지식 데이터 추가(GPU2) | Accepted |
| [D-189](../research/policy-learning/decisions/D-189-laya-renderer-v3-opponent-sets.md) | laya 렌더러 v3(상대 세트 추론)와 래더 대비 학습(GPU0) | Accepted |
| [D-190](../research/policy-learning/decisions/D-190-laya-ex129-gate-override.md) | EX-128 진행 조건 미충족에도 EX-129 배틀 실행(사용자 결정) | Accepted |
| [D-191](../research/policy-learning/decisions/D-191-no-offline-battle-gate.md) | 오프라인 test 평가로 배틀 평가를 거르지 않는다 | Accepted |
| [D-192](../research/policy-learning/decisions/D-192-laya-renderer-v4-fail-out.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해)와 GPU1 학습·배틀 | Accepted |
| [D-193](../research/policy-learning/decisions/D-193-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방(GPU0 학습·배틀) | Accepted |
| [D-195](../research/policy-learning/decisions/D-195-laya-item-state-renderer-v5.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터)와 학습·배틀 | Accepted |
| [EP-212](../research/policy-learning/plans/EP-212-laya-tera-knowledge.md) | laya v2 테라 지식 데이터 학습과 배틀 비교(GPU1) | Completed |
| [EX-124](../research/policy-learning/experiments/EX-124-laya-v2-tera-knowledge-training.md) | laya v2 + 테라 기본 지식 데이터 학습(GPU1) | Completed |
| [EX-126](../research/policy-learning/experiments/EX-126-laya-v2-tera-effect-training.md) | laya v2 + 테라 + 효과 지식 데이터 학습(GPU2) | Completed |
| [EX-128](../research/policy-learning/experiments/EX-128-laya-v3-tera-training.md) | laya 렌더러 v3(상대 세트 추론) + 테라 지식 학습(GPU0) | Completed |
| [EX-130](../research/policy-learning/experiments/EX-130-laya-v4-tera-training.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) + 테라 지식 학습(GPU1) | Running |
| [EX-132](../research/policy-learning/experiments/EX-132-laya-v2t-outcome-weighted-training.md) | laya v2+테라 승패 가중 모방 학습(GPU0) | Running |
| [EX-136](../research/policy-learning/experiments/EX-136-laya-v5-tera-training.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) + 테라 지식 학습(GPU0) | Planned |

## milkkarten/pokechamp

| ID | 제목 | 상태 |
|---|---|---|
| [D-175](../research/rule-learning/decisions/D-175-replay-ko-system1-data.md) | 실제 리플레이의 관측 KO 결과 학습자료 | Accepted |
| [EP-198](../research/rule-learning/plans/EP-198-replay-ko-system1-data.md) | 실제 리플레이 KO 결과 예측 System 1 자료 | Completed |

## replay

| ID | 제목 | 상태 |
|---|---|---|
| [D-112](../research/policy-learning/decisions/D-112-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 채택 | Accepted |
| [D-113](../research/policy-learning/decisions/D-113-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Accepted |
| [EP-100](../shared/datasets/plans/EP-100-replay-rule-eligibility.md) | 현재 로컬 Gen9 OU 리플레이 규칙 적합성 분류 | Completed |
| [EP-114](../research/policy-learning/plans/EP-114-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 구체화 | Completed |
| [EP-115](../research/policy-learning/plans/EP-115-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EP-132](../research/fixed-matchup-learning/plans/EP-132-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 자기대국 학습 실행 | Completed |
| [EP-177](../shared/viewers/plans/EP-177-ex108-viewer-layout.md) | EX108 기존 뷰어 구성 복원 | Completed |
| [EX-071](../research/policy-learning/experiments/EX-071-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EX-072](../research/policy-learning/experiments/EX-072-selfplay-rlcd.md) | 자기대국과 RLCD 확률 보정: 단일 GPU 24시간 | Completed — 실험 완료, 성능 개선 미입증 |

## replay-ko-system1-v1

| ID | 제목 | 상태 |
|---|---|---|
| [D-175](../research/rule-learning/decisions/D-175-replay-ko-system1-data.md) | 실제 리플레이의 관측 KO 결과 학습자료 | Accepted |
| [D-176](../research/rule-learning/decisions/D-176-conditional-ko-system1-data.md) | 조건부 KO와 관측 KO의 분리 | Accepted |
| [EP-198](../research/rule-learning/plans/EP-198-replay-ko-system1-data.md) | 실제 리플레이 KO 결과 예측 System 1 자료 | Completed |
| [EP-199](../research/rule-learning/plans/EP-199-conditional-ko-system1-data.md) | 조건부 확정 KO 판정 자료 | Completed |

## showdown-ruleqa-v1

| ID | 제목 | 상태 |
|---|---|---|
| [D-159](../research/rule-learning/decisions/D-159-showdown-ruleqa.md) | Showdown 규칙 Q&A 데이터셋 v1 | Accepted |
| [D-161](../research/rule-learning/decisions/D-161-tacit-ruleqa-lora.md) | Tacit 규칙 Q&A LoRA 1회 | Accepted |
| [D-169](../research/rule-learning/decisions/D-169-jevk5-ruleqa-lora.md) | JevK5 규칙 선택형 추가 LoRA | Accepted |
| [D-173](../research/rule-learning/decisions/D-173-jevk5-ruleqa-battle32.md) | 학습 JevK5 규칙 LoRA 실전32 | Accepted |
| [EP-169](../research/rule-learning/plans/EP-169-showdown-ruleqa.md) | Showdown 규칙 Q&A·State 데이터셋 v1 | Completed |
| [EP-170](../shared/datasets/plans/EP-170-pokemon-training-data-archive.md) | pokemon-training-data 원본 보관 | Completed |
| [EP-173](../research/rule-learning/plans/EP-173-tacit-ruleqa-lora.md) | Tacit 규칙 Q&A LoRA | Completed |
| [EP-184](../research/rule-learning/plans/EP-184-jevk5-ruleqa-lora.md) | JevK5 규칙 선택형 추가 LoRA | Completed |
| [EP-190](../research/rule-learning/plans/EP-190-jevk5-vllm-serving-check.md) | JevK5 추가 LoRA vLLM 서빙 확인 | Completed |
| [EP-191](../research/rule-learning/plans/EP-191-jevk5-ruleqa-battle32.md) | 학습 JevK5 LoRA 실전32 실행 | Completed |
| [EX-107](../research/rule-learning/experiments/EX-107-tacit-ruleqa-lora.md) | Tacit-9B 규칙 Q&A LoRA | Completed |
| [EX-108](../research/rule-learning/experiments/EX-108-tacit-ruleqa-battle32.md) | 학습 Tacit 규칙 Q&A 어댑터 실전32 | Completed |
| [EX-113](../research/rule-learning/experiments/EX-113-jevk5-ruleqa-lora.md) | JevK5-9B 규칙 선택형 추가 LoRA | Completed |
| [EX-114](../research/rule-learning/experiments/EX-114-jevk5-ruleqa-battle32.md) | 학습 JevK5 선택형 LoRA 실전32 | Completed |

## smogon-gen9ou-20261019

| ID | 제목 | 상태 |
|---|---|---|
| [D-177](../research/rule-learning/decisions/D-177-smogon-role-system1-data.md) | Smogon 분석의 역할 근거 학습 | Accepted |
| [EP-200](../research/rule-learning/plans/EP-200-smogon-role-system1-data.md) | Smogon 전략 기반 역할 System 1 자료 | Completed |

## smogon-role-system1-v1

| ID | 제목 | 상태 |
|---|---|---|
| [D-177](../research/rule-learning/decisions/D-177-smogon-role-system1-data.md) | Smogon 분석의 역할 근거 학습 | Accepted |
| [EP-200](../research/rule-learning/plans/EP-200-smogon-role-system1-data.md) | Smogon 전략 기반 역할 System 1 자료 | Completed |

## system1-full

| ID | 제목 | 상태 |
|---|---|---|
| [D-180](../research/rule-learning/decisions/D-180-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Accepted |
| [EP-203](../research/rule-learning/plans/EP-203-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |
| [EX-116](../research/rule-learning/experiments/EX-116-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |
