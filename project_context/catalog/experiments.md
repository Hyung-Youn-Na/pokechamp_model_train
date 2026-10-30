# 실험 목록

<!-- generated: scripts/context-catalog build -->

원문 상태를 그대로 표시한다. 완료 상태는 효능 개선을 뜻하지 않는다.

| ID | 제목 | 상태 |
|---|---|---|
| [EX-001](../shared/execution/experiments/EX-001-pokechamp-baseline-pilot.md) | PokéChamp 기준선 pilot | Stopped |
| [EX-002](../shared/execution/experiments/EX-002-pokechamp-baseline-pilot.md) | 중단 처리 검증 후 PokéChamp 기준선 pilot | Completed |
| [EX-003](../shared/execution/experiments/EX-003-core-smoke-timing.md) | 128K·300초 핵심 8판 시간 재측정 | Completed |
| [EX-004](../shared/execution/experiments/EX-004-model-concurrency-calibration.md) | 모델별 요청 동시성 측정 | Completed |
| [EX-005](../shared/execution/experiments/EX-005-sequential-eight.md) | 동일 수정 source의 순차 8판 (배틀1/요청1) | NotRun |
| [EX-006](../shared/execution/experiments/EX-006-parallel-eight.md) | 동일 수정 source의 병렬 8판 (배틀 min(C*,8)/모델 요청 C*) | Stopped |
| [EX-007](../shared/execution/experiments/EX-007-parallel-thirty-two.md) | C* 배틀/모델 요청의 조건부 32판 | NotRun |
| [EX-008](../shared/execution/experiments/EX-008-parallel-eight-revised.md) | 수정된 coordinator의 병렬 8판 | Completed |
| [EX-009](../shared/execution/experiments/EX-009-sequential-eight-revised.md) | 수정coordinator 순차8판 | Stopped |
| [EX-010](../shared/execution/experiments/EX-010-parallel-thirty-two-revised.md) | 수정coordinator 조건부32판 | NotRun |
| [EX-011](../shared/execution/experiments/EX-011-parallel-eight-final.md) | 포트 정리를 보완한 병렬 8판 | Completed |
| [EX-012](../shared/execution/experiments/EX-012-sequential-eight-final.md) | 포트 정리를 보완한 순차 8판 | Completed |
| [EX-013](../shared/execution/experiments/EX-013-parallel-thirty-two-final.md) | 선택 조건의 32판 | Completed |
| [EX-014](../shared/execution/experiments/EX-014-parallel-thirty-two-repeat.md) | 동일 조건의 병렬 32판 반복 | Completed |
| [EX-015](../shared/execution/experiments/EX-015-action-candidate-validation.md) | 식별 수정과 요청 후보 조건 검증 | Completed |
| [EX-016](../shared/execution/experiments/EX-016-upstream-fallback.md) | 원본 fallback 병렬32판 | Completed |
| [EX-017](../research/input-and-memory/experiments/EX-017-improved-io-offline.md) | 개선 IO 오프라인 검증 | Stopped |
| [EX-018](../research/input-and-memory/experiments/EX-018-ruination-offline-revalidation.md) | Ruination 패치 후 오프라인 재검증 | Completed |
| [EX-019](../research/input-and-memory/experiments/EX-019-special-move-diagnostics.md) | 특수 기술 피해 계산 진단 | Completed — 진단·보고 범위만 완료, 계산기 전체 통과 아님 |
| [EX-020](../research/input-and-memory/experiments/EX-020-resume-io.md) | 개선 IO 재실험 | Blocked |
| [EX-021](../research/input-and-memory/experiments/EX-021-summary-harness-diagnostics.md) | 요약 오류의 harness 기여도 비교 | Blocked (invalidated / 진단 미완료) |
| [EX-022](../research/input-and-memory/experiments/EX-022-state-summary-thinking.md) | 상태 처리 정비 후 요약 thinking 비교 | Blocked / invalidated / 진단 미완료 |
| [EX-023](../research/input-and-memory/experiments/EX-023-continue-io.md) | 상태 교정 후 개선 IO 실험 재개 | Blocked |
| [EX-024](../research/input-and-memory/experiments/EX-024-low-summary-prompt-reexperiment.md) | low 요약 지시 개선 후 IO 재실험 | Blocked |
| [EX-025](../research/input-and-memory/experiments/EX-025-summary-max-diagnostic.md) | 요약 thinking low/max 진단 | Invalidated — 전체 중단·진단 미완료 |
| [EX-026](../research/input-and-memory/experiments/EX-026-io-battle-only.md) | 요약 없는 improved_io A/B 비교 | Blocked — Cloud 출력·의미 gate 실패, A/B 비교 미완료 |
| [EX-027](../research/input-and-memory/experiments/EX-027-battle-guide-live.md) | 필드 설명서 v1.1.0 실제 Cloud 병렬 배틀 | Stopped — Cloud 출력 계약 실패, 실제 비교 미완료 |
| [EX-028](../research/input-and-memory/experiments/EX-028-battle-guide-direct32.md) | 사전 검증 생략 32판 비교 | Completed — 32 slot 처리 완료, 16쌍 비교 미완료 |
| [EX-029](../research/input-and-memory/experiments/EX-029-calculator-entry-calcfix32.md) | 계산기 교정 동일 조건 A/B32판 | Completed — 승인된 중단 포함 작업 완료; 32판 성능 비교 미완료 |
| [EX-030](../research/input-and-memory/experiments/EX-030-calculator-input-audit.md) | 계산기 입력 전체 로컬 진단 | Completed |
| [EX-031](../research/input-and-memory/experiments/EX-031-calculator-inputfix32.md) | 교정 입력·계산기 동일 조건 A/B32판 | Completed — 중단 포함 작업 완료, 성능 비교 미완료 |
| [EX-032](../research/input-and-memory/experiments/EX-032-battle-guide-movefix32.md) | 수정 완료본 A/B32판 | Completed — 승인된 중단 포함 작업 완료, 성능 비교 미완료 |
| [EX-033](../research/input-and-memory/experiments/EX-033-external-memory-repeat32.md) | 외부 메모리 장애 후 동일 조건32판 | Completed |
| [EX-034](../research/input-and-memory/experiments/EX-034-smogon-diagnostic-design.md) | Smogon 기반 원본 A 운용 한계 진단 설계 | Prepared — 팀·대진·검토·자원 명세 검증 완료, 대전 미실행 |
| [EX-035](../research/input-and-memory/experiments/EX-035-a-diagnostic64.md) | Smogon 원본 A64 진단 실험 | Completed — 유효64/64·A50승14패·1902결정 전수검토·보고·보존/정리 완료 |
| [EX-036](../research/input-and-memory/experiments/EX-036-ab-head-to-head32.md) | 원본 A 대 변경 구성 B 직접 대결32경기 | Stopped — 계산 결함 중단, 직접비교 미완료 |
| [EX-037](../research/input-and-memory/experiments/EX-037-ab-head-to-head32-protectfix.md) | Protect 수정본 A/B 직접대결32 | Blocked / 비교 미완료 |
| [EX-038](../research/input-and-memory/experiments/EX-038-ab-head-to-head32-b2.md) | 원본 A 대 B2 직접대결32 | Blocked |
| [EX-039](../research/lead-policy/experiments/EX-039-b2-lead-proposal.md) | B2 seeded_random 대 llm_lead 선봉 정책 대응 비교 | Stopped / 비교 미완료 — 사용자 지시로 실행·감시 종료, 미실행12경기 보존 |
| [EX-040](../research/lead-policy/experiments/EX-040-b2-lead-zai.md) | Z.ai B2 seeded_random 대 llm_lead32 | Stopped / 첫 HTTP429 중단·비교 미완료 |
| [EX-041](../research/lead-policy/experiments/EX-041-b2-lead-zai4.md) | Z.ai B2 seeded_random 대 llm_lead32 | Incomplete / 수집·보고·보존·정리 완료, 비교 미완료 |
| [EX-042](../research/lead-policy/experiments/EX-042-distributed-lead.md) | Ollama Cloud·Z.ai 분산 B2 선봉 정책 비교 | Incomplete |
| [EX-043](../research/lead-policy/experiments/EX-043-corrected-lead.md) | 교정된 B2 개선 선봉 대 무작위 선봉 | Incomplete |
| [EX-044](../research/lead-policy/experiments/EX-044-direct-corrected-lead.md) | 교정 선봉 비교 직접 본실험 | Incomplete |
| [EX-045](../research/lead-policy/experiments/EX-045-official-lead.md) | 공식 관측 B2 기반 LLM 선봉 정책 본실험 | Incomplete |
| [EX-046](../research/lead-policy/experiments/EX-046-async-official-lead.md) | 비동기 교정본 공식 관측 B2 선봉 본실험 | Completed |
| [EX-047](../research/model-evaluation/experiments/EX-047-jev-battle.md) | JEV Choice 소규모 배틀 진단 | Incomplete |
| [EX-048](../research/model-evaluation/experiments/EX-048-jev-repeat.md) | JEV 합계 검사 수정본2경기 | Incomplete |
| [EX-049](../research/model-evaluation/experiments/EX-049-jev-judgment-repeat.md) | JEV 판단 오류 비중단 적용2경기 | Incomplete |
| [EX-050](../research/model-evaluation/experiments/EX-050-jev-judgment-recovery.md) | JEV 준비 경로 교정2경기 | Completed |
| [EX-051](../research/input-and-memory/experiments/EX-051-jev-v2-battle.md) | JEV 교정 입력 v2 동일 조건2경기 | Completed |
| [EX-052](../research/model-evaluation/experiments/EX-052-jev-abyssal32.md) | JEV 대 Abyssal 32경기 | Completed |
| [EX-053](../research/input-and-memory/experiments/EX-053-jev-v3-abyssal32.md) | JEV 대 Abyssal 32경기 | Incomplete |
| [EX-054](../research/input-and-memory/experiments/EX-054-jev-v3-retry32.md) | 재시도3회 적용 JEV v3 동일32경기 | Incomplete |
| [EX-055](../research/input-and-memory/experiments/EX-055-jev-failed-input-probe.md) | EX-054 실패 입력의 현재 응답 확인 | Completed |
| [EX-056](../research/input-and-memory/experiments/EX-056-jev-direct32.md) | 사전 검증 없이 동일 조건32경기 재실험 | Incomplete |
| [EX-057](../research/input-and-memory/experiments/EX-057-jev-pinned32.md) | jev-1.13.0 고정 직접32경기 | Completed |
| [EX-058](../research/input-and-memory/experiments/EX-058-jev-improved32.md) | 개선 JEV 입력 동일32경기 | Completed |
| [EX-059](../research/input-and-memory/experiments/EX-059-jev-compact32.md) | 자기 벤치 축약 JEV 입력 동일32경기 | Completed |
| [EX-060](../research/action-value/experiments/EX-060-single-battle-branch-rollouts.md) | EX-058 battle-19 분기 데이터 추출 | Completed |
| [EX-061](../research/action-value/experiments/EX-061-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 행동가치 개발 실험 | Completed |
| [EX-062](../research/action-value/experiments/EX-062-qwen-local-battle.md) | Qwen 최종 LoRA 로컬 배틀 연결 검증 | Blocked |
| [EX-063](../research/action-value/experiments/EX-063-qwen-training-matchup.md) | Qwen 학습 원대진 배틀 진단 | Completed |
| [EX-064](../research/action-value/experiments/EX-064-qwen-candidate-state.md) | Qwen 후보 상태 입력 3조건 개발 진단 | Completed |
| [EX-065](../research/action-value/experiments/EX-065-joint-q-data.md) | Abyssal 80경기 기반 공동 q 학습 데이터 | Completed |
| [EX-066](../research/action-value/experiments/EX-066-joint-q-training.md) | Qwen3.5-4B-Base 공동 q 학습·독립 평가 | Blocked — 새 프로세스 재로딩 gate 실패 |
| [EX-067](../research/action-value/experiments/EX-067-abyssal-tera-joint-q.md) | Abyssal Tera 보완 공동 q 데이터 | Completed |
| [EX-068](../research/model-evaluation/experiments/EX-068-kev-battle.md) | Kev-4B pokechamp r1 연결 smoke | Completed — D-109 조건의 연결 수락 검사 완료. 원 unmerged gate 실패는 보존. |
| [EX-069](../research/model-evaluation/experiments/EX-069-kev-test-battles.md) | EX-065 test20 고정 대진의 Kev 본 테스트 | Completed |
| [EX-070](../research/model-evaluation/experiments/EX-070-kev-continuation-question.md) | Kev 후속 정책 질문의 1경기 진단 | Completed |
| [EX-071](../research/policy-learning/experiments/EX-071-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EX-072](../research/policy-learning/experiments/EX-072-selfplay-rlcd.md) | 자기대국과 RLCD 확률 보정: 단일 GPU 24시간 | Completed — 실험 완료, 성능 개선 미입증 |
| [EX-073](../research/policy-learning/experiments/EX-073-abyssal-rl.md) | Abyssal 우선 정책 학습: 4GPU·24시간 | Incomplete — 학습·test·독립 감사 완료, 최종 뷰어 검증 시간 초과 |
| [EX-074](../research/policy-learning/experiments/EX-074-abyssal-rl-continue.md) | 57라운드 계승·동일 설정 추가12시간 학습 | Completed — 실험 완료·57라운드 출발 대비 통계적 개선·성능 목표 미달 |
| [EX-075](../research/policy-learning/experiments/EX-075-abyssal-rl-next.md) | 82라운드 계승·동일 설정 추가12시간 1회 | Completed — 필수 검증·평가·뷰어·봉인·정리 완료; 개선 미입증·목표 미달 |
| [EX-076](../research/fixed-matchup-learning/experiments/EX-076-fixed-matchup-mcts.md) | 고정 A/B 공개 상태 MCTS 정책 학습 | Incomplete — 교정 후 기술 검증/측정 통과, 평가 예산 gate 초과로 학습/test 보류 |
| [EX-077](../research/fixed-matchup-learning/experiments/EX-077-fixed-matchup-day.md) | 하루 내 고정 대진 공개 상태 학습 | Incomplete — 사용자 요청 중지; 학습/test 미시작 |
| [EX-078](../research/fixed-matchup-learning/experiments/EX-078-fixed-matchup-first-round.md) | 첫1라운드 학습 체크포인트 | Completed — D-125 복구·첫라운드 진단 완료; 원실행 Incomplete 보존 |
| [EX-079](../research/fixed-matchup-learning/experiments/EX-079-fixed-matchup-stopping.md) | 종료조건 기반 고정 대진 추가 학습 | Completed — 추가학습·시험·감사/뷰어·정리 완료; 주효능 기준 미달 |
| [EX-080](../research/fixed-matchup-learning/experiments/EX-080-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Completed — 시도 3 학습(round40 둔화 종료)·선택(round36)·잠긴 test·감사/뷰어/봉인·정리 완료; 주효능 미입증 (시도 1·2는 도구 결함으로 학습 전 중단·보존) |
| [EX-081](../research/action-value/experiments/EX-081-joint-q-battle.md) | EX066 epoch3 재현성 복구·GPU0 실제 test20 | Completed |
| [EX-082](../research/model-evaluation/experiments/EX-082-jev27b-ex058-reproduction.md) | JEV-27B로 EX-058 개선 입력 동일32 평가 | Blocked |
| [EX-083](../research/model-evaluation/experiments/EX-083-jev27b-four-gpu-continuation.md) | JEV-27B 4GPU 잔여9경기 계승 평가 | Completed |
| [EX-084](../research/model-evaluation/experiments/EX-084-quyet-medium-two-stage.md) | Quyet-Medium 2단계 정책의 EX-083 동일32경기 평가 | Completed |
| [EX-085](../research/model-evaluation/experiments/EX-085-jev9b-single-choice.md) | JEV-9B의 EX-083 설정 기반 동일32경기 평가 | Completed |
| [EX-086](../research/input-and-memory/experiments/EX-086-jev27b-public-memory-v6.md) | JEV-27B 공개 정보 v6 신규32경기 | Blocked |
| [EX-087](../research/input-and-memory/experiments/EX-087-jev9b-public-memory-v6.md) | JEV-9B 공개 정보 v6 신규32경기 | Blocked |
| [EX-088](../research/input-and-memory/experiments/EX-088-jev27b-v6-corrected.md) | 교정 v6 JEV-27B 신규32경기 | Completed |
| [EX-089](../research/input-and-memory/experiments/EX-089-jev9b-v6-corrected.md) | 교정 v6 JEV-9B 신규32경기 | Completed |
| [EX-090](../research/input-and-memory/experiments/EX-090-jev9b-no-damage.md) | JEV-9B 피해 예측 제거 신규32경기 | Completed |
| [EX-091](../research/model-evaluation/experiments/EX-091-minicpm5-2b-jev.md) | MiniCPM5-2B-Jev 계산기 포함 신규32경기 | Completed |
| [EX-092](../research/planner-executor/experiments/EX-092-planner-first-battle-sample.md) | EX-088 첫 대진의 GLM planner–JEV 샘플 | Completed |
| [EX-093](../research/planner-executor/experiments/EX-093-planner-goal-completion-sample.md) | 목표 충족 확인 지시문 적용 샘플1경기 | Blocked |
| [EX-094](../research/planner-executor/experiments/EX-094-planner-json-retry-sample.md) | GLM JSON 구문 재시도 적용 샘플 | Completed |
| [EX-095](../research/planner-executor/experiments/EX-095-jev35b-nvfp4-sample.md) | JEV-35B-NVFP4 EX-094 동일 대진 샘플 | Blocked |
| [EX-096](../research/planner-executor/experiments/EX-096-nvfp4-battle-probability-diagnostics.md) | 확률 변동 진단을 유지하는 NVFP4 실제 샘플1경기 | Blocked |
| [EX-097](../research/planner-executor/experiments/EX-097-planner-format-temperature-zero.md) | GLM 형식 재시도·temperature0 NVFP4 샘플1경기 | Completed |
| [EX-098](../research/planner-executor/experiments/EX-098-planner-high-effort-sample.md) | GLM high 추론 강도 NVFP4 동일 대진1경기 | Blocked |
| [EX-099](../research/planner-executor/experiments/EX-099-planner-unlimited-time-max-output.md) | 시간 상한 없는 GLM 최대 출력 NVFP4 샘플1경기 | Completed |
| [EX-100](../research/planner-executor/experiments/EX-100-glm53-low-sample.md) | GLM-5.3 low 동일 대진 NVFP4 샘플1경기 | Completed |
| [EX-101](../research/planner-executor/experiments/EX-101-matchup-events.md) | 매치업 변화 기반 GLM 계획 갱신 | Completed |
| [EX-102](../research/planner-executor/experiments/EX-102-matchup-events-high.md) | 매치업 사건 기반 GLM high 동일 대진 | Completed |
| [EX-103](../research/planner-executor/experiments/EX-103-jev-omni-low.md) | Jev-Omni + GLM-5.3 low 동일 대진 | Completed |
| [EX-104](../research/planner-executor/experiments/EX-104-tacit-thinking-low.md) | Tacit-9B Thinking + GLM-5.3 Low 판단 비교 | Blocked |
| [EX-105](../research/planner-executor/experiments/EX-105-tacit-vllm-low.md) | Tacit vLLM Thinking + GLM-5.3 Low | Completed |
| [EX-106](../research/model-evaluation/experiments/EX-106-strategist-first-battle.md) | Strategist 소형 모델 첫 배틀 | Completed |
| [EX-107](../research/rule-learning/experiments/EX-107-tacit-ruleqa-lora.md) | Tacit-9B 규칙 Q&A LoRA | Completed |
| [EX-108](../research/rule-learning/experiments/EX-108-tacit-ruleqa-battle32.md) | 학습 Tacit 규칙 Q&A 어댑터 실전32 | Completed |
| [EX-109](../research/model-evaluation/experiments/EX-109-openai-decisions-v6-battle32.md) | OpenAI Decisions v6 상세32경기 | Stopped |
| [EX-110](../research/model-evaluation/experiments/EX-110-openai-decisions-retry32.md) | OpenAI Decisions 통신 재시도 새32경기 | Completed |
| [EX-111](../research/model-evaluation/experiments/EX-111-jevk5-v6-battle32.md) | JevK5-9B v6 상세32경기 | Completed |
| [EX-112](../research/input-and-memory/experiments/EX-112-openai-candidate-matchup-battle.md) | 후보별 현재 대면 요약 gpt-6-luna 32경기 | Stopped |
| [EX-113](../research/rule-learning/experiments/EX-113-jevk5-ruleqa-lora.md) | JevK5-9B 규칙 선택형 추가 LoRA | Completed |
| [EX-114](../research/rule-learning/experiments/EX-114-jevk5-ruleqa-battle32.md) | 학습 JevK5 선택형 LoRA 실전32 | Completed |
| [EX-115](../research/input-and-memory/experiments/EX-115-candidate-action-v7.md) | 후보 중심 v7 GPT-6 Luna 32경기 | Completed |
| [EX-116](../research/rule-learning/experiments/EX-116-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |
| [EX-117](../research/input-and-memory/experiments/EX-117-v7-survival-battle32.md) | 생존·교체 비용 v7 GPT-6 Luna 32경기 | Stopped |
| [EX-118](../research/policy-learning/experiments/EX-118-laya-compact-imitation-training.md) | laya 압축 입력 리플레이 모방 학습 | Completed |
| [EX-119](../research/policy-learning/experiments/EX-119-laya-compact-imitation-battle32.md) | laya 압축 입력 모방 모델 EX-089 표준 32경기 | Completed |
| [EX-120](../research/policy-learning/experiments/EX-120-laya-team-generalization128.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EX-121](../research/policy-learning/experiments/EX-121-laya-v2-all-training.md) | laya 모듈형 렌더러 v2(4종 전부) 학습과 v1 쌍비교 | Completed |
| [EX-122](../research/policy-learning/experiments/EX-122-laya-v1-v2-battle256.md) | laya v1·v2 같은 실행 256경기 비교 (EX-120 일정) | Completed |
| [EX-123](../research/rule-learning/experiments/EX-123-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Completed |
| [EX-124](../research/policy-learning/experiments/EX-124-laya-v2-tera-knowledge-training.md) | laya v2 + 테라 기본 지식 데이터 학습(GPU1) | Completed |
| [EX-125](../research/policy-learning/experiments/EX-125-laya-v2-tera-battle256.md) | laya v2와 v2+테라 지식 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-126](../research/policy-learning/experiments/EX-126-laya-v2-tera-effect-training.md) | laya v2 + 테라 + 효과 지식 데이터 학습(GPU2) | Completed |
| [EX-127](../research/policy-learning/experiments/EX-127-laya-v2t-v2te-battle256.md) | laya v2+테라와 v2+테라+효과 지식 같은 실행 256경기(GPU2, EX-120 일정) | Completed |
| [EX-128](../research/policy-learning/experiments/EX-128-laya-v3-tera-training.md) | laya 렌더러 v3(상대 세트 추론) + 테라 지식 학습(GPU0) | Completed |
| [EX-129](../research/policy-learning/experiments/EX-129-laya-v2t-v3t-battle256.md) | laya v2+테라와 v3+테라 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-130](../research/policy-learning/experiments/EX-130-laya-v4-tera-training.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) + 테라 지식 학습(GPU1) | Running |
| [EX-131](../research/policy-learning/experiments/EX-131-laya-v2t-v4t-battle256.md) | laya v2+테라와 v4+테라 같은 실행 256경기(GPU1, EX-120 일정) | Planned |
| [EX-132](../research/policy-learning/experiments/EX-132-laya-v2t-outcome-weighted-training.md) | laya v2+테라 승패 가중 모방 학습(GPU0) | Running |
| [EX-133](../research/policy-learning/experiments/EX-133-laya-v2t-v2tw-battle256.md) | laya v2+테라와 v2+테라 승패 가중 모방 같은 실행 256경기(GPU0, EX-120 일정) | Planned |
| [EX-134](../research/policy-learning/experiments/EX-134-laya-head-to-head512.md) | laya v2+테라 대 v2·v1·v2+테라+효과·v3+테라 직접 대결 512경기(GPU2, EX-120 일정) | Running |
| [EX-135](../research/policy-learning/experiments/EX-135-laya-head-to-head-v2tw-v4t.md) | laya v2+테라 대 승패 가중·v4+테라 직접 대결 256경기(GPU2, EX-120 일정) | Planned |
| [EX-136](../research/policy-learning/experiments/EX-136-laya-v5-tera-training.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) + 테라 지식 학습(GPU0) | Planned |
| [EX-137](../research/policy-learning/experiments/EX-137-laya-v4t-v5t-battle256.md) | laya v4+테라와 v5+테라 같은 실행 256경기(GPU0, EX-120 일정) | Planned |
| [EX-138](../research/policy-learning/experiments/EX-138-laya-head-to-head-v5t.md) | laya v5+테라 대 v2+테라·v4+테라 직접 대결 256경기(GPU2, EX-120 일정) | Planned |
| [EX-139](../research/policy-learning/experiments/EX-139-laya-v2t-corrected-input-battle256.md) | laya v2+테라(EX-124) 보정 입력 fix·info 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-140](../research/policy-learning/experiments/EX-140-laya-v2t-tera-decision-defence384.md) | laya v2+테라(EX-124) fix 입력 테라 합산 결정(k=1·3)과 테라 방어 문구 384경기(GPU1, EX-120 일정) | Running |
| [EX-141](../research/policy-learning/experiments/EX-141-laya-v6s-streaks-training.md) | laya 렌더러 v6s(같은 기술 반복 표시) + 테라 지식 학습(GPU0) | Completed |
| [EX-142](../research/policy-learning/experiments/EX-142-laya-v6h-long-history-training.md) | laya 렌더러 v6h(긴 과거 기록, 2048토큰) + 테라 지식 학습(GPU1) | Completed |
| [EX-143](../research/policy-learning/experiments/EX-143-laya-v5t-v6st-battle256.md) | laya v5+테라와 v6st (반복 표시) 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-144](../research/policy-learning/experiments/EX-144-laya-v5t-v6ht-battle256.md) | laya v5+테라와 v6ht (긴 기록 2048토큰) 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-145](../research/policy-learning/experiments/EX-145-laya-play-teams-v5t-v6st-v6ht-battle.md) | laya-play 완성 팀 74개로 v5t·v6st·v6ht 대 Abyssal(GPU2) | Planned |
