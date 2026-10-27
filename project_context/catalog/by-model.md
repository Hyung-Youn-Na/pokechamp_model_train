# 관련 모델별 탐색

<!-- generated: scripts/context-catalog build -->

탐색 분류는 처치의 동일성·실제 실행·직접 비교 가능성을 보증하지 않는다. 관련 모델·자료에는 기준선과 참조도 포함하며 실제 조건은 원문을 확인한다.

| 분류 | 기록 수 |
|---|---|
| [Abyssal](#abyssal) | 3 |
| [GLM](#glm) | 127 |
| [JEV](#jev) | 138 |
| [JevK5](#jevk5) | 30 |
| [Kev](#kev) | 14 |
| [MiniCPM](#minicpm) | 4 |
| [OpenAI Decisions](#openai-decisions) | 23 |
| [Quyet](#quyet) | 3 |
| [Qwen](#qwen) | 39 |
| [Strategist](#strategist) | 4 |
| [Tacit](#tacit) | 12 |
| [laya](#laya) | 49 |

## Abyssal

| ID | 제목 | 상태 |
|---|---|---|
| [D-173](../research/rule-learning/decisions/D-173-jevk5-ruleqa-battle32.md) | 학습 JevK5 규칙 LoRA 실전32 | Accepted |
| [EP-191](../research/rule-learning/plans/EP-191-jevk5-ruleqa-battle32.md) | 학습 JevK5 LoRA 실전32 실행 | Completed |
| [EX-114](../research/rule-learning/experiments/EX-114-jevk5-ruleqa-battle32.md) | 학습 JevK5 선택형 LoRA 실전32 | Completed |

## GLM

| ID | 제목 | 상태 |
|---|---|---|
| [D-006](../shared/execution/decisions/D-006-adopt-pokechamp-environment-boundary.md) | PokéChamp 연구 환경 및 외부 경계 채택 | [`D-007`](../shared/execution/decisions/D-007-adopt-pokechamp-dotenv-credential.md)로 대체됨 (Superseded) |
| [D-007](../shared/execution/decisions/D-007-adopt-pokechamp-dotenv-credential.md) | PokéChamp `.env` credential 정책을 포함한 연구 환경 경계 채택 | 채택 (Accepted) |
| [D-008](../shared/execution/decisions/D-008-fail-closed-cloud-json-actions.md) | Ollama Cloud JSON action의 thinking 비활성화와 fail-closed 검증 | [`D-009`](../shared/execution/decisions/D-009-adapt-always-on-reasoning-output.md)로 대체됨 (Superseded) |
| [D-009](../shared/execution/decisions/D-009-adapt-always-on-reasoning-output.md) | Always-on reasoning model의 compact action output 경계 채택 | 채택 (Accepted) |
| [D-012](../shared/execution/decisions/D-012-adopt-pokechamp-baseline-pilot.md) | PokéChamp 기준선 pilot 채택 | Accepted |
| [D-013](../shared/execution/decisions/D-013-remove-client-output-cap.md) | 사용자 지시에 따른 LLM 출력 상한 최대화 | Accepted |
| [D-016](../shared/execution/decisions/D-016-model-concurrency.md) | 계정·모델 요청 제한과 병렬 운영 측정 | Accepted |
| [D-023](../research/input-and-memory/decisions/D-023-summary-harness-diagnostics.md) | 요약 오류의 harness 기여도 진단 | Accepted |
| [D-024](../research/input-and-memory/decisions/D-024-state-summary-thinking.md) | 상태 처리 정비와 요약 thinking 비교 | Accepted |
| [D-027](../research/input-and-memory/decisions/D-027-low-summary-prompt-reexperiment.md) | low 요약 지시 개선과 IO 재실험 | Accepted |
| [D-028](../research/input-and-memory/decisions/D-028-summary-max-diagnostic.md) | 요약 thinking low/max 독립 진단 | Accepted |
| [D-030](../research/input-and-memory/decisions/D-030-io-battle-only.md) | 요약을 제외한 improved_io A/B 비교 | Accepted |
| [D-032](../research/input-and-memory/decisions/D-032-battle-guide-live.md) | 필드 설명서 v1.1.0 실제 Cloud 병렬 배틀 | Accepted |
| [D-033](../research/input-and-memory/decisions/D-033-battle-guide-direct32.md) | 사전 검증 생략 32판과 오류 턴 표시 | Accepted |
| [D-034](../research/input-and-memory/decisions/D-034-calculator-entry-calcfix32.md) | 계산기 등장 특성 교정 및 동일32판 | Accepted |
| [D-036](../research/input-and-memory/decisions/D-036-calculator-inputfix32.md) | 교정 입력·계산기 동일32판 | Accepted |
| [D-038](../research/input-and-memory/decisions/D-038-battle-guide-movefix32.md) | 수정 완료본 A/B32판 새 실행 | Accepted |
| [D-039](../research/input-and-memory/decisions/D-039-external-memory-repeat32.md) | 외부 메모리 장애 기록 및 동일 조건 재실험 | Accepted |
| [D-041](../research/input-and-memory/decisions/D-041-a-diagnostic64.md) | Smogon 원본 A64 진단 실행 | Accepted |
| [D-042](../research/input-and-memory/decisions/D-042-ab-head-to-head32.md) | 원본 A 대 변경 구성 B 직접 대결32경기 | Accepted |
| [D-044](../research/input-and-memory/decisions/D-044-ab-head-to-head32-protectfix.md) | Protect 수정본 직접32 연속 실행 | Accepted |
| [D-047](../research/input-and-memory/decisions/D-047-ab-head-to-head32-b2.md) | B2 직접대결32 실행 | Accepted |
| [D-054](../shared/execution/decisions/D-054-zai-provider.md) | Z.ai 배틀 공급자 선택 | Accepted |
| [D-055](../research/lead-policy/decisions/D-055-b2-lead-zai.md) | EX-040 Z.ai B2 선봉 정책 재비교 | Accepted |
| [D-139](../research/planner-executor/decisions/D-139-jev-planner-environment.md) | GLM planner–JEV 수행 모델 실험 환경 | Accepted |
| [D-142](../research/planner-executor/decisions/D-142-planner-first-battle-sample.md) | EX-088 첫 대진의 planner–JEV 샘플 실행 | Accepted |
| [D-143](../research/planner-executor/decisions/D-143-executor-goal-completion.md) | JEV의 계획 목표 충족 여부 확인 | Accepted |
| [D-144](../shared/viewers/decisions/D-144-planner-replay-viewer.md) | 향후 GLM·JEV 탭·리플레이 통합 표시 | Accepted |
| [D-145](../research/planner-executor/decisions/D-145-goal-completion-sample.md) | 바뀐 수행 프롬프트의 실제 샘플1경기 | Accepted |
| [D-146](../research/planner-executor/decisions/D-146-planner-json-retries.md) | GLM JSON 구문 오류 최대5회 재시도·새 샘플 | Accepted |
| [D-147](../research/planner-executor/decisions/D-147-planner-unlimited-disk.md) | GLM·JEV 향후 실행의 디스크 용량 상한 해제 | Accepted |
| [D-148](../research/planner-executor/decisions/D-148-jev35b-nvfp4-sample.md) | JEV-35B-NVFP4 단일 GPU 동일 대진 샘플 | Accepted |
| [D-150](../research/planner-executor/decisions/D-150-planner-format-retries-temperature-zero.md) | GLM 응답 형식 재시도·기본 temperature0 | Accepted |
| [D-151](../research/planner-executor/decisions/D-151-planner-high-effort-sample.md) | GLM high 추론 강도 동일 대진 샘플 | Accepted |
| [D-152](../research/planner-executor/decisions/D-152-planner-unlimited-time-max-output.md) | 경기/전체 시간 상한 해제·GLM 최대 출력 새1경기 | Accepted |
| [D-153](../research/planner-executor/decisions/D-153-glm53-low-sample.md) | GLM-5.3 low 동일 대진 새1경기 | Accepted |
| [D-155](../research/planner-executor/decisions/D-155-matchup-events-high.md) | 매치업 사건 GLM high 동일 대진 | Accepted |
| [D-156](../research/planner-executor/decisions/D-156-jev-omni-low.md) | Jev-Omni + GLM-5.3 low 동일 대진 | Accepted |
| [D-157](../research/planner-executor/decisions/D-157-tacit-thinking-low.md) | Tacit-9B Thinking + GLM-5.3 Low 판단 비교 | Accepted |
| [EP-001](../shared/execution/plans/EP-001-pokechamp-reproducible-environment.md) | PokéChamp 재현 가능 연구 환경 구성 | Completed |
| [EP-007](../shared/execution/plans/EP-007-model-concurrency.md) | 모델 동시성 측정과 병렬 배틀 | Completed |
| [EP-008](../shared/execution/plans/EP-008-parallel-thirty-two-repeat.md) | 병렬 32판 추가 실행 | Completed |
| [EP-010](../shared/execution/plans/EP-010-upstream-fallback.md) | 원본 fallback 병렬32판 | Completed |
| [EP-020](../research/input-and-memory/plans/EP-020-battle-guide-live.md) | 필드 설명서 실제 Cloud 병렬 배틀 | Blocked — 구현·로컬 검증·중단 보고 완료, Cloud 기술 gate 실패로 실제 비교 미완료 |
| [EP-021](../research/input-and-memory/plans/EP-021-battle-guide-direct32.md) | 사전 검증 생략 32판과 오류 턴 표시 | Completed |
| [EP-022](../research/input-and-memory/plans/EP-022-calculator-entry-calcfix32.md) | 계산기 등장 특성 교정 및 동일32판 | Completed — 사용자 중단 대안 포함 완료; 성능 비교 미완료 |
| [EP-024](../research/input-and-memory/plans/EP-024-calculator-inputfix32.md) | 교정 입력·계산기 동일 조건 A/B32판 | Completed |
| [EP-026](../research/input-and-memory/plans/EP-026-battle-guide-movefix32.md) | 수정 완료본 A/B32판 본 실험 | Completed — 승인된 중단 포함 작업 완료, 성능 비교 미완료 |
| [EP-027](../research/input-and-memory/plans/EP-027-external-memory-repeat32.md) | 외부 메모리 장애 후 동일 조건32판 재실험 | Completed |
| [EP-029](../research/input-and-memory/plans/EP-029-a-diagnostic64.md) | Smogon 원본 A64 진단 실행 | Completed |
| [EP-030](../research/input-and-memory/plans/EP-030-ab-head-to-head32.md) | 원본 A 대 변경 구성 B 직접 대결32경기 | Blocked — 계산 결함 중단, 직접비교 미완료 |
| [EP-032](../research/input-and-memory/plans/EP-032-ab-head-to-head32-protectfix.md) | Protect 수정본 A/B 직접대결32 | Blocked |
| [EP-035](../research/input-and-memory/plans/EP-035-ab-head-to-head32-b2.md) | B2 적용 A/B 직접대결32 | Blocked |
| [EP-042](../shared/execution/plans/EP-042-zai-provider.md) | Z.ai 배틀 공급자 연결 및 환경 구성 | Completed |
| [EP-043](../shared/execution/plans/EP-043-zai-connectivity-probe.md) | Z.ai 단일 연결 확인 | Completed |
| [EP-073](../research/model-evaluation/plans/EP-073-jev-abyssal32.md) | JEV 대 Abyssal 32경기 본실험 | Completed |
| [EP-145](../research/planner-executor/plans/EP-145-jev-planner-environment.md) | GLM planner–JEV 실험 설정 환경 | Completed |
| [EP-148](../research/planner-executor/plans/EP-148-planner-first-battle-sample.md) | GLM planner–JEV 첫 실제 샘플 | Completed |
| [EP-149](../research/planner-executor/plans/EP-149-executor-goal-completion.md) | JEV 계획 목표 충족 확인 지시 | Completed |
| [EP-150](../shared/viewers/plans/EP-150-planner-replay-viewer.md) | GLM·JEV 탭·리플레이 통합 뷰어 | Completed |
| [EP-151](../research/planner-executor/plans/EP-151-planner-goal-completion-sample.md) | 변경 수행 프롬프트 샘플1경기 | Blocked |
| [EP-152](../research/planner-executor/plans/EP-152-planner-json-retry-sample.md) | GLM JSON 구문 재시도·샘플1경기 | Completed |
| [EP-153](../research/planner-executor/plans/EP-153-planner-unlimited-disk.md) | GLM·JEV 디스크 상한 해제 | Completed |
| [EP-154](../research/planner-executor/plans/EP-154-jev35b-nvfp4-sample.md) | JEV-35B-NVFP4 동일 대진 샘플 | Blocked |
| [EP-155](../research/planner-executor/plans/EP-155-nvfp4-battle-probability-diagnostics.md) | 확률 변동 진단을 유지하는 NVFP4 실제1경기 | Blocked |
| [EP-156](../research/planner-executor/plans/EP-156-planner-format-temperature-zero.md) | GLM 형식 재시도·temperature0 실제1경기 | Completed |
| [EP-157](../research/planner-executor/plans/EP-157-planner-high-effort-sample.md) | GLM high 추론 강도 실제1경기 | Blocked |
| [EP-158](../research/planner-executor/plans/EP-158-planner-unlimited-time-max-output.md) | 시간 상한 없는 GLM 최대 출력 실제1경기 | Completed |
| [EP-159](../research/planner-executor/plans/EP-159-glm53-low-sample.md) | GLM-5.3 low 동일 대진 실제1경기 | Completed |
| [EP-160](../research/planner-executor/plans/EP-160-matchup-events.md) | 매치업 변화 기반 GLM 계획 갱신 | Completed |
| [EP-161](../research/planner-executor/plans/EP-161-matchup-events-high.md) | GLM high 매치업 사건 동일1경기 | Completed |
| [EP-163](../research/planner-executor/plans/EP-163-tacit-thinking-low.md) | Tacit Thinking low 판단 비교 | Blocked |
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
| [EX-016](../shared/execution/experiments/EX-016-upstream-fallback.md) | 원본 fallback 병렬32판 | Completed |
| [EX-018](../research/input-and-memory/experiments/EX-018-ruination-offline-revalidation.md) | Ruination 패치 후 오프라인 재검증 | Completed |
| [EX-021](../research/input-and-memory/experiments/EX-021-summary-harness-diagnostics.md) | 요약 오류의 harness 기여도 비교 | Blocked (invalidated / 진단 미완료) |
| [EX-022](../research/input-and-memory/experiments/EX-022-state-summary-thinking.md) | 상태 처리 정비 후 요약 thinking 비교 | Blocked / invalidated / 진단 미완료 |
| [EX-023](../research/input-and-memory/experiments/EX-023-continue-io.md) | 상태 교정 후 개선 IO 실험 재개 | Blocked |
| [EX-025](../research/input-and-memory/experiments/EX-025-summary-max-diagnostic.md) | 요약 thinking low/max 진단 | Invalidated — 전체 중단·진단 미완료 |
| [EX-027](../research/input-and-memory/experiments/EX-027-battle-guide-live.md) | 필드 설명서 v1.1.0 실제 Cloud 병렬 배틀 | Stopped — Cloud 출력 계약 실패, 실제 비교 미완료 |
| [EX-028](../research/input-and-memory/experiments/EX-028-battle-guide-direct32.md) | 사전 검증 생략 32판 비교 | Completed — 32 slot 처리 완료, 16쌍 비교 미완료 |
| [EX-029](../research/input-and-memory/experiments/EX-029-calculator-entry-calcfix32.md) | 계산기 교정 동일 조건 A/B32판 | Completed — 승인된 중단 포함 작업 완료; 32판 성능 비교 미완료 |
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
| [EX-045](../research/lead-policy/experiments/EX-045-official-lead.md) | 공식 관측 B2 기반 LLM 선봉 정책 본실험 | Incomplete |
| [EX-052](../research/model-evaluation/experiments/EX-052-jev-abyssal32.md) | JEV 대 Abyssal 32경기 | Completed |
| [EX-053](../research/input-and-memory/experiments/EX-053-jev-v3-abyssal32.md) | JEV 대 Abyssal 32경기 | Incomplete |
| [EX-054](../research/input-and-memory/experiments/EX-054-jev-v3-retry32.md) | 재시도3회 적용 JEV v3 동일32경기 | Incomplete |
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
| [EX-108](../research/rule-learning/experiments/EX-108-tacit-ruleqa-battle32.md) | 학습 Tacit 규칙 Q&A 어댑터 실전32 | Completed |

## JEV

| ID | 제목 | 상태 |
|---|---|---|
| [D-007](../shared/execution/decisions/D-007-adopt-pokechamp-dotenv-credential.md) | PokéChamp `.env` credential 정책을 포함한 연구 환경 경계 채택 | 채택 (Accepted) |
| [D-054](../shared/execution/decisions/D-054-zai-provider.md) | Z.ai 배틀 공급자 선택 | Accepted |
| [D-070](../shared/execution/decisions/D-070-jev-client.md) | JEV 환경 설정과 독립 호출 기반 | Accepted |
| [D-071](../research/model-evaluation/decisions/D-071-jev-battle.md) | JEV Choice 배틀 연결 | Accepted |
| [D-072](../research/model-evaluation/decisions/D-072-jev-probability-validation.md) | JEV 확률 합계 검사 제거 | Accepted |
| [D-073](../research/model-evaluation/decisions/D-073-jev-repeat.md) | JEV 수정본2경기 재실행 | Accepted |
| [D-075](../research/model-evaluation/decisions/D-075-jev-judgment-repeat.md) | 판단 오류 비중단 적용 JEV 재실행 | Accepted |
| [D-077](../shared/viewers/decisions/D-077-jev-replay-viewer.md) | 내보내기 뷰어에 배틀 리플레이 포함 | Accepted |
| [D-079](../research/input-and-memory/decisions/D-079-jev-lead-input.md) | JEV 자기 선봉 입력 근거 교정 | Accepted |
| [D-080](../research/input-and-memory/decisions/D-080-jev-v2-battle.md) | 교정 JEV 입력 실제2경기 테스트 | Accepted |
| [D-081](../research/model-evaluation/decisions/D-081-jev-abyssal32.md) | JEV 대 Abyssal 32경기 본실험 | Accepted |
| [D-082](../research/input-and-memory/decisions/D-082-jev-v3-effects.md) | JEV v3 기본 지식·효과 사전 | Accepted |
| [D-083](../research/input-and-memory/decisions/D-083-jev-v3-abyssal32.md) | JEV v3 동일32경기와 v2 전후 비교 | Accepted |
| [D-084](../shared/execution/decisions/D-084-provider-retry-three.md) | provider 오류 재시도3회 고정 | Accepted |
| [D-085](../research/input-and-memory/decisions/D-085-jev-v3-retry32.md) | EX-054 동일 조건 재실험 | Accepted |
| [D-086](../research/input-and-memory/decisions/D-086-jev-failed-input-probe.md) | 실패 입력의 현재 응답 확인 | Accepted |
| [D-087](../shared/execution/decisions/D-087-jev-retry-backoff.md) | JEV 재시도 대기 확대 | Accepted |
| [D-088](../research/input-and-memory/decisions/D-088-jev-direct32.md) | EX-056 사전 검증 생략 동일32경기 | Accepted |
| [D-089](../research/input-and-memory/decisions/D-089-jev-pinned32.md) | jev-1.13.0 고정 새 본실험 | Accepted |
| [D-092](../research/input-and-memory/decisions/D-092-jev-offline-input.md) | JEV 오프라인 입력 표현 개선 | Accepted |
| [D-094](../research/input-and-memory/decisions/D-094-jev-improved32.md) | 개선 JEV 입력 동일32경기 | Accepted |
| [D-095](../research/input-and-memory/decisions/D-095-jev-compact32.md) | 자기 벤치 축약 동일32경기 | Accepted |
| [D-096](../research/policy-learning/decisions/D-096-pokemon-training-objective.md) | 세 RLCD 환경을 활용한 포켓몬 전용 학습 당면 목표 채택 | Accepted |
| [D-097](../research/action-value/decisions/D-097-single-battle-branch-rollouts.md) | EX-058 한 경기 행동별 분기 데이터 | Accepted |
| [D-101](../shared/viewers/decisions/D-101-viewer-action-names.md) | 뷰어 결정의 실제 행동 이름 | Accepted |
| [D-130](../research/model-evaluation/decisions/D-130-jev27b-ex058-reproduction.md) | JEV-27B 공개 가중치로 개선 입력 동일32 평가 | Accepted |
| [D-134](../research/model-evaluation/decisions/D-134-jev9b-single-choice.md) | JEV-9B 단일 Choice 동일32경기 | Accepted |
| [D-135](../research/input-and-memory/decisions/D-135-jev-public-memory-v6.md) | 상대 공개 정보 v6와 JEV 재평가 | Accepted |
| [D-136](../research/input-and-memory/decisions/D-136-jev-v6-corrected-evaluation.md) | 교정된 v6의 새64경기 평가 승인 | Accepted |
| [D-137](../research/input-and-memory/decisions/D-137-jev9b-no-damage.md) | JEV-9B 피해 예측 제거 평가 | Accepted |
| [D-138](../research/model-evaluation/decisions/D-138-minicpm5-2b-jev.md) | MiniCPM5-2B-Jev 계산기 포함 평가 | Accepted |
| [D-139](../research/planner-executor/decisions/D-139-jev-planner-environment.md) | GLM planner–JEV 수행 모델 실험 환경 | Accepted |
| [D-140](../research/planner-executor/decisions/D-140-planner-role-resource-guide.md) | Planner 역할·승리 경로·자원 관리 안내 | Accepted |
| [D-141](../research/input-and-memory/decisions/D-141-candidate-display-names.md) | Planner/JEV 후보 표시 이름 | Accepted |
| [D-142](../research/planner-executor/decisions/D-142-planner-first-battle-sample.md) | EX-088 첫 대진의 planner–JEV 샘플 실행 | Accepted |
| [D-143](../research/planner-executor/decisions/D-143-executor-goal-completion.md) | JEV의 계획 목표 충족 여부 확인 | Accepted |
| [D-144](../shared/viewers/decisions/D-144-planner-replay-viewer.md) | 향후 GLM·JEV 탭·리플레이 통합 표시 | Accepted |
| [D-146](../research/planner-executor/decisions/D-146-planner-json-retries.md) | GLM JSON 구문 오류 최대5회 재시도·새 샘플 | Accepted |
| [D-147](../research/planner-executor/decisions/D-147-planner-unlimited-disk.md) | GLM·JEV 향후 실행의 디스크 용량 상한 해제 | Accepted |
| [D-148](../research/planner-executor/decisions/D-148-jev35b-nvfp4-sample.md) | JEV-35B-NVFP4 단일 GPU 동일 대진 샘플 | Accepted |
| [D-150](../research/planner-executor/decisions/D-150-planner-format-retries-temperature-zero.md) | GLM 응답 형식 재시도·기본 temperature0 | Accepted |
| [D-151](../research/planner-executor/decisions/D-151-planner-high-effort-sample.md) | GLM high 추론 강도 동일 대진 샘플 | Accepted |
| [D-153](../research/planner-executor/decisions/D-153-glm53-low-sample.md) | GLM-5.3 low 동일 대진 새1경기 | Accepted |
| [D-156](../research/planner-executor/decisions/D-156-jev-omni-low.md) | Jev-Omni + GLM-5.3 low 동일 대진 | Accepted |
| [D-160](../research/model-evaluation/decisions/D-160-strategist-first-battle.md) | Strategist 첫 배틀 탐색 평가 | Accepted |
| [EP-061](../shared/execution/plans/EP-061-jev-client.md) | JEV 환경 설정과 독립 호출 기반 | Completed |
| [EP-062](../research/model-evaluation/plans/EP-062-jev-battle.md) | JEV 전용 배틀 입력과 2경기 테스트 | Blocked |
| [EP-063](../research/model-evaluation/plans/EP-063-jev-probability-validation.md) | JEV 확률 합계 검사 제거 | Completed |
| [EP-064](../research/model-evaluation/plans/EP-064-jev-repeat.md) | JEV 수정본2경기 재실행 | Blocked |
| [EP-065](../shared/execution/plans/EP-065-provider-judgment-policy.md) | 공급자 판단 오류의 전체 중단 제외 | Completed |
| [EP-066](../research/model-evaluation/plans/EP-066-jev-judgment-repeat.md) | 판단 오류 격리 적용·JEV 2경기 재실행 | Completed |
| [EP-069](../shared/viewers/plans/EP-069-researcher-viewer.md) | 실험자용 JEV 뷰어 가독성 | Completed |
| [EP-070](../research/input-and-memory/plans/EP-070-jev-lead-input.md) | JEV 선봉 입력 교정과 오프라인 회귀 | Completed |
| [EP-071](../research/input-and-memory/plans/EP-071-jev-v2-battle.md) | 교정 JEV 입력 v2 동일 조건2경기 | Completed |
| [EP-072](../shared/viewers/plans/EP-072-viewer-navigation-hp.md) | 뷰어 단축키·상대 HP 비율 표시 | Completed |
| [EP-073](../research/model-evaluation/plans/EP-073-jev-abyssal32.md) | JEV 대 Abyssal 32경기 본실험 | Completed |
| [EP-074](../research/input-and-memory/plans/EP-074-jev-v3-effects.md) | JEV v3 기본 지식·효과 사전 | Completed |
| [EP-075](../research/input-and-memory/plans/EP-075-jev-v3-abyssal32.md) | JEV v3 동일32경기와 v2 전후 비교 | Blocked |
| [EP-076](../shared/execution/plans/EP-076-provider-retry-three.md) | provider 오류 재시도3회 고정 | Completed |
| [EP-077](../research/input-and-memory/plans/EP-077-jev-v3-retry32.md) | EX-054 재시도3회 동일32경기 | Blocked |
| [EP-078](../research/input-and-memory/plans/EP-078-jev-failed-input-probe.md) | 실패 입력 현재 응답 확인 | Completed |
| [EP-079](../shared/execution/plans/EP-079-jev-retry-backoff.md) | JEV 재시도 대기10·30·60초 | Completed |
| [EP-080](../research/input-and-memory/plans/EP-080-jev-direct32.md) | EX-056 사전 검증 생략 동일32경기 | Blocked |
| [EP-081](../research/input-and-memory/plans/EP-081-jev-pinned32.md) | jev-1.13.0 고정 직접32경기 | Completed |
| [EP-082](../research/input-and-memory/plans/EP-082-jev-damage-samples.md) | 기술별 피해량 범위 오프라인 프롬프트 샘플 | Completed |
| [EP-086](../shared/datasets/plans/EP-086-role-export-field-guide.md) | 역할 DB 열람본 필드 설명서 | Completed |
| [EP-089](../shared/datasets/plans/EP-089-ex057-role-assessment.md) | EX-057 제출 팀 역할 대조 | Completed |
| [EP-093](../research/input-and-memory/plans/EP-093-jev-offline-input.md) | JEV 입력 표현 개선·오프라인 검증 | Completed |
| [EP-094](../research/input-and-memory/plans/EP-094-jev-improved32.md) | 개선 JEV 입력 동일32경기 | Completed |
| [EP-095](../research/input-and-memory/plans/EP-095-jev-compact32.md) | 자기 벤치 축약 동일32경기 | Completed |
| [EP-102](../research/action-value/plans/EP-102-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 첫 학습 검증 | Completed |
| [EP-103](../research/action-value/plans/EP-103-qwen-local-battle.md) | Qwen 로컬 서빙과 PokéChamp 연결 | Blocked |
| [EP-104](../research/action-value/plans/EP-104-qwen-training-matchup.md) | Qwen 학습 원대진 실전 배틀 | Completed |
| [EP-105](../shared/viewers/plans/EP-105-viewer-action-names.md) | 뷰어 결정의 실제 기술·포켓몬 이름 표시 | Completed |
| [EP-134](../research/model-evaluation/plans/EP-134-jev27b-ex058-reproduction.md) | JEV-27B 개선 입력 동일32 재현 | Blocked |
| [EP-137](../research/model-evaluation/plans/EP-137-jev27b-four-gpu-continuation.md) | JEV-27B 4GPU 잔여9경기 계승 | Completed |
| [EP-138](../research/model-evaluation/plans/EP-138-quyet-medium-two-stage.md) | Quyet-Medium 2단계 정책 동일32 평가 | Completed |
| [EP-139](../research/model-evaluation/plans/EP-139-jev9b-single-choice.md) | JEV-9B 단일 Choice 동일32 평가 | Completed |
| [EP-140](../research/input-and-memory/plans/EP-140-jev-public-memory-v6.md) | 공개 정보 v6·턴 로그 뷰어·JEV 27B/9B 재평가 | Blocked |
| [EP-141](../research/input-and-memory/plans/EP-141-jev-v6-corrected-evaluation.md) | 교정 v6의27B/9B 신규64평가 | Completed |
| [EP-142](../shared/viewers/plans/EP-142-jev-damage-viewer.md) | EX-088·089 Damage-calc 시나리오 탭 | Completed |
| [EP-143](../research/input-and-memory/plans/EP-143-jev9b-no-damage.md) | JEV-9B 피해 예측 제거와 EX-089 비교 | Completed |
| [EP-144](../research/model-evaluation/plans/EP-144-minicpm5-2b-jev.md) | MiniCPM5-2B-Jev 계산기 포함 배틀 평가 | Completed |
| [EP-145](../research/planner-executor/plans/EP-145-jev-planner-environment.md) | GLM planner–JEV 실험 설정 환경 | Completed |
| [EP-146](../research/planner-executor/plans/EP-146-planner-role-resource-guide.md) | Planner 역할·승리 경로·자원 안내 | Completed |
| [EP-147](../research/input-and-memory/plans/EP-147-candidate-display-names.md) | 후보 표시 이름 추가 | Completed |
| [EP-148](../research/planner-executor/plans/EP-148-planner-first-battle-sample.md) | GLM planner–JEV 첫 실제 샘플 | Completed |
| [EP-149](../research/planner-executor/plans/EP-149-executor-goal-completion.md) | JEV 계획 목표 충족 확인 지시 | Completed |
| [EP-150](../shared/viewers/plans/EP-150-planner-replay-viewer.md) | GLM·JEV 탭·리플레이 통합 뷰어 | Completed |
| [EP-151](../research/planner-executor/plans/EP-151-planner-goal-completion-sample.md) | 변경 수행 프롬프트 샘플1경기 | Blocked |
| [EP-152](../research/planner-executor/plans/EP-152-planner-json-retry-sample.md) | GLM JSON 구문 재시도·샘플1경기 | Completed |
| [EP-153](../research/planner-executor/plans/EP-153-planner-unlimited-disk.md) | GLM·JEV 디스크 상한 해제 | Completed |
| [EP-154](../research/planner-executor/plans/EP-154-jev35b-nvfp4-sample.md) | JEV-35B-NVFP4 동일 대진 샘플 | Blocked |
| [EP-162](../research/planner-executor/plans/EP-162-jev-omni-low.md) | Jev-Omni low 동일1경기 | Completed |
| [EP-169](../research/rule-learning/plans/EP-169-showdown-ruleqa.md) | Showdown 규칙 Q&A·State 데이터셋 v1 | Completed |
| [EP-172](../research/model-evaluation/plans/EP-172-strategist-first-battle.md) | Strategist 소형 모델 첫 배틀 | Completed |
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
| [EX-062](../research/action-value/experiments/EX-062-qwen-local-battle.md) | Qwen 최종 LoRA 로컬 배틀 연결 검증 | Blocked |
| [EX-063](../research/action-value/experiments/EX-063-qwen-training-matchup.md) | Qwen 학습 원대진 배틀 진단 | Completed |
| [EX-064](../research/action-value/experiments/EX-064-qwen-candidate-state.md) | Qwen 후보 상태 입력 3조건 개발 진단 | Completed |
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
| [EX-109](../research/model-evaluation/experiments/EX-109-openai-decisions-v6-battle32.md) | OpenAI Decisions v6 상세32경기 | Stopped |
| [EX-111](../research/model-evaluation/experiments/EX-111-jevk5-v6-battle32.md) | JevK5-9B v6 상세32경기 | Completed |
| [EX-112](../research/input-and-memory/experiments/EX-112-openai-candidate-matchup-battle.md) | 후보별 현재 대면 요약 gpt-6-luna 32경기 | Stopped |

## JevK5

| ID | 제목 | 상태 |
|---|---|---|
| [D-166](../research/model-evaluation/decisions/D-166-jevk5-v6-battle32.md) | JevK5-9B v6 상세32경기 | Accepted |
| [D-169](../research/rule-learning/decisions/D-169-jevk5-ruleqa-lora.md) | JevK5 규칙 선택형 추가 LoRA | Accepted |
| [D-173](../research/rule-learning/decisions/D-173-jevk5-ruleqa-battle32.md) | 학습 JevK5 규칙 LoRA 실전32 | Accepted |
| [D-175](../research/rule-learning/decisions/D-175-replay-ko-system1-data.md) | 실제 리플레이의 관측 KO 결과 학습자료 | Accepted |
| [D-176](../research/rule-learning/decisions/D-176-conditional-ko-system1-data.md) | 조건부 KO와 관측 KO의 분리 | Accepted |
| [D-177](../research/rule-learning/decisions/D-177-smogon-role-system1-data.md) | Smogon 분석의 역할 근거 학습 | Accepted |
| [D-178](../research/rule-learning/decisions/D-178-gen9-mechanics-system1-data.md) | 우선순위별 규칙 적용과 정보 충분성 자료 | Accepted |
| [D-180](../research/rule-learning/decisions/D-180-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Accepted |
| [D-186](../research/rule-learning/decisions/D-186-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Accepted |
| [EP-181](../research/model-evaluation/plans/EP-181-jevk5-v6-battle32.md) | JevK5-9B v6 상세32경기 | Completed |
| [EP-182](../research/input-and-memory/plans/EP-182-candidate-matchup-summary.md) | 후보별 현재 대면 상성·효과 요약 | Completed |
| [EP-183](../research/input-and-memory/plans/EP-183-openai-candidate-matchup-battle.md) | 후보별 상성 요약 OpenAI 32경기 | Blocked |
| [EP-184](../research/rule-learning/plans/EP-184-jevk5-ruleqa-lora.md) | JevK5 규칙 선택형 추가 LoRA | Completed |
| [EP-190](../research/rule-learning/plans/EP-190-jevk5-vllm-serving-check.md) | JevK5 추가 LoRA vLLM 서빙 확인 | Completed |
| [EP-191](../research/rule-learning/plans/EP-191-jevk5-ruleqa-battle32.md) | 학습 JevK5 LoRA 실전32 실행 | Completed |
| [EP-193](../research/rule-learning/plans/EP-193-gen9-type-system1-data.md) | Gen9 타입 System 1 판별 학습자료 | Completed |
| [EP-195](../research/rule-learning/plans/EP-195-gen9-status-system1-data.md) | Gen9 상태이상 System 1 학습자료 | Completed |
| [EP-196](../research/rule-learning/plans/EP-196-gen9-priority-system1-data.md) | Gen9 행동 우선도 System 1 자료 | Completed |
| [EP-197](../research/rule-learning/plans/EP-197-gen9-weather-terrain-system1-data.md) | Gen9 날씨·영역 System 1 자료 | Completed |
| [EP-198](../research/rule-learning/plans/EP-198-replay-ko-system1-data.md) | 실제 리플레이 KO 결과 예측 System 1 자료 | Completed |
| [EP-199](../research/rule-learning/plans/EP-199-conditional-ko-system1-data.md) | 조건부 확정 KO 판정 자료 | Completed |
| [EP-200](../research/rule-learning/plans/EP-200-smogon-role-system1-data.md) | Smogon 전략 기반 역할 System 1 자료 | Completed |
| [EP-201](../research/rule-learning/plans/EP-201-gen9-mechanics-system1-data.md) | 우선순위별 Gen9 규칙 적용 System 1 자료 | Completed |
| [EP-203](../research/rule-learning/plans/EP-203-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |
| [EP-211](../research/rule-learning/plans/EP-211-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Completed |
| [EX-111](../research/model-evaluation/experiments/EX-111-jevk5-v6-battle32.md) | JevK5-9B v6 상세32경기 | Completed |
| [EX-113](../research/rule-learning/experiments/EX-113-jevk5-ruleqa-lora.md) | JevK5-9B 규칙 선택형 추가 LoRA | Completed |
| [EX-114](../research/rule-learning/experiments/EX-114-jevk5-ruleqa-battle32.md) | 학습 JevK5 선택형 LoRA 실전32 | Completed |
| [EX-116](../research/rule-learning/experiments/EX-116-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |
| [EX-123](../research/rule-learning/experiments/EX-123-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Completed |

## Kev

| ID | 제목 | 상태 |
|---|---|---|
| [D-108](../research/model-evaluation/decisions/D-108-kev-battle.md) | pokechamp r1 Kev-4B 연결 검증 | Accepted |
| [D-109](../research/model-evaluation/decisions/D-109-kev-fused-validation.md) | Kev fused·merged 서빙의 추가 수락 검사 | Accepted |
| [D-110](../research/model-evaluation/decisions/D-110-kev-test-battles.md) | 기존 test 대진의 Kev 본 배틀 | Accepted |
| [D-111](../research/model-evaluation/decisions/D-111-kev-continuation-question.md) | Kev 후속 정책 질문의 1경기 진단 | Accepted |
| [D-112](../research/policy-learning/decisions/D-112-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 채택 | Accepted |
| [D-113](../research/policy-learning/decisions/D-113-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Accepted |
| [EP-111](../research/model-evaluation/plans/EP-111-kev-battle.md) | 학습된 Kev-4B 실시간 배틀 연결 | Completed |
| [EP-112](../research/model-evaluation/plans/EP-112-kev-test-battles.md) | EX-065 test20 대진의 Kev 본 테스트 | Completed |
| [EP-113](../research/model-evaluation/plans/EP-113-kev-continuation-question.md) | Kev 후속 정책 질문의 1경기 진단 | Completed |
| [EX-068](../research/model-evaluation/experiments/EX-068-kev-battle.md) | Kev-4B pokechamp r1 연결 smoke | Completed — D-109 조건의 연결 수락 검사 완료. 원 unmerged gate 실패는 보존. |
| [EX-069](../research/model-evaluation/experiments/EX-069-kev-test-battles.md) | EX-065 test20 고정 대진의 Kev 본 테스트 | Completed |
| [EX-070](../research/model-evaluation/experiments/EX-070-kev-continuation-question.md) | Kev 후속 정책 질문의 1경기 진단 | Completed |
| [EX-071](../research/policy-learning/experiments/EX-071-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EX-080](../research/fixed-matchup-learning/experiments/EX-080-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Completed — 시도 3 학습(round40 둔화 종료)·선택(round36)·잠긴 test·감사/뷰어/봉인·정리 완료; 주효능 미입증 (시도 1·2는 도구 결함으로 학습 전 중단·보존) |

## MiniCPM

| ID | 제목 | 상태 |
|---|---|---|
| [D-138](../research/model-evaluation/decisions/D-138-minicpm5-2b-jev.md) | MiniCPM5-2B-Jev 계산기 포함 평가 | Accepted |
| [D-139](../research/planner-executor/decisions/D-139-jev-planner-environment.md) | GLM planner–JEV 수행 모델 실험 환경 | Accepted |
| [EP-144](../research/model-evaluation/plans/EP-144-minicpm5-2b-jev.md) | MiniCPM5-2B-Jev 계산기 포함 배틀 평가 | Completed |
| [EX-091](../research/model-evaluation/experiments/EX-091-minicpm5-2b-jev.md) | MiniCPM5-2B-Jev 계산기 포함 신규32경기 | Completed |

## OpenAI Decisions

| ID | 제목 | 상태 |
|---|---|---|
| [D-025](../shared/governance/decisions/D-025-agent-instruction-boundaries.md) | 승인 근거와 작업 중단·완료 범위 명료화 | 채택 (Accepted) |
| [D-163](../shared/execution/decisions/D-163-openai-decisions-environment.md) | 독립 OpenAI Decisions API 환경 | Accepted |
| [D-164](../research/model-evaluation/decisions/D-164-openai-decisions-v6-battle32.md) | OpenAI Decisions v6 상세32경기 | Accepted |
| [D-165](../research/model-evaluation/decisions/D-165-openai-decisions-retry32.md) | OpenAI 통신 재시도와 새32경기 | Accepted |
| [D-166](../research/model-evaluation/decisions/D-166-jevk5-v6-battle32.md) | JevK5-9B v6 상세32경기 | Accepted |
| [D-168](../research/input-and-memory/decisions/D-168-openai-candidate-matchup-battle.md) | 후보별 상성 요약 OpenAI 동일32경기 | Accepted |
| [D-179](../research/input-and-memory/decisions/D-179-candidate-action-v7.md) | 후보 중심 v7와 응답 복구 탐색 실험 | Accepted |
| [D-182](../research/input-and-memory/decisions/D-182-v7-survival-battle32.md) | 생존·교체 비용 v7 GPT-6 Luna 32경기 | Accepted |
| [EP-014](../shared/governance/plans/EP-014-agent-instruction-maintenance.md) | 승인·중단 지시와 현재 상태 정합화 | Completed |
| [EP-109](../shared/governance/plans/EP-109-astra-subagent-guidance.md) | Astra 서브에이전트 활용 지침 | Completed |
| [EP-178](../shared/execution/plans/EP-178-openai-decisions-environment.md) | OpenAI Decisions API 환경 | Completed |
| [EP-179](../research/model-evaluation/plans/EP-179-openai-decisions-v6-battle32.md) | OpenAI Decisions v6 상세32경기 | Blocked |
| [EP-180](../research/model-evaluation/plans/EP-180-openai-decisions-retry32.md) | OpenAI 통신 재시도 새32경기 | Completed |
| [EP-182](../research/input-and-memory/plans/EP-182-candidate-matchup-summary.md) | 후보별 현재 대면 상성·효과 요약 | Completed |
| [EP-183](../research/input-and-memory/plans/EP-183-openai-candidate-matchup-battle.md) | 후보별 상성 요약 OpenAI 32경기 | Blocked |
| [EP-202](../research/input-and-memory/plans/EP-202-candidate-action-v7.md) | 후보 중심 v7와 GPT-6 Luna 32경기 | Completed |
| [EP-204](../research/input-and-memory/plans/EP-204-human-input-structure-guides.md) | 사람이 읽는 입력 구조 상세 문서 폴더 | Completed |
| [EP-206](../research/input-and-memory/plans/EP-206-v7-survival-battle32.md) | 개정 v7 GPT-6 Luna 32경기 시작·수집 | Blocked |
| [EX-109](../research/model-evaluation/experiments/EX-109-openai-decisions-v6-battle32.md) | OpenAI Decisions v6 상세32경기 | Stopped |
| [EX-110](../research/model-evaluation/experiments/EX-110-openai-decisions-retry32.md) | OpenAI Decisions 통신 재시도 새32경기 | Completed |
| [EX-112](../research/input-and-memory/experiments/EX-112-openai-candidate-matchup-battle.md) | 후보별 현재 대면 요약 gpt-6-luna 32경기 | Stopped |
| [EX-115](../research/input-and-memory/experiments/EX-115-candidate-action-v7.md) | 후보 중심 v7 GPT-6 Luna 32경기 | Completed |
| [EX-117](../research/input-and-memory/experiments/EX-117-v7-survival-battle32.md) | 생존·교체 비용 v7 GPT-6 Luna 32경기 | Stopped |

## Quyet

| ID | 제목 | 상태 |
|---|---|---|
| [D-133](../research/model-evaluation/decisions/D-133-quyet-medium-two-stage.md) | Quyet-Medium 2단계 정책 동일32경기 | Accepted |
| [EP-138](../research/model-evaluation/plans/EP-138-quyet-medium-two-stage.md) | Quyet-Medium 2단계 정책 동일32 평가 | Completed |
| [EX-084](../research/model-evaluation/experiments/EX-084-quyet-medium-two-stage.md) | Quyet-Medium 2단계 정책의 EX-083 동일32경기 평가 | Completed |

## Qwen

| ID | 제목 | 상태 |
|---|---|---|
| [D-098](../research/action-value/decisions/D-098-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 첫 행동가치 학습 | Accepted |
| [D-099](../research/action-value/decisions/D-099-qwen-local-battle.md) | Qwen 행동가치 로컬 서빙·배틀 연결 | Accepted |
| [D-100](../research/action-value/decisions/D-100-qwen-training-matchup.md) | Qwen 학습 원대진 실전 진단 | Accepted |
| [D-101](../shared/viewers/decisions/D-101-viewer-action-names.md) | 뷰어 결정의 실제 행동 이름 | Accepted |
| [D-102](../research/action-value/decisions/D-102-qwen-candidate-state.md) | EX-063 후보 실행 후 상태 평가 개선 | Accepted |
| [D-104](../research/action-value/decisions/D-104-joint-q-training.md) | EX-065 기반 Base 공동 q 학습 | Accepted |
| [D-112](../research/policy-learning/decisions/D-112-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 채택 | Accepted |
| [D-113](../research/policy-learning/decisions/D-113-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Accepted |
| [D-119](../research/fixed-matchup-learning/decisions/D-119-fixed-matchup-mcts.md) | 고정 대진 공개 상태 MCTS 정책 학습 | Accepted |
| [D-120](../research/fixed-matchup-learning/decisions/D-120-fixed-matchup-run.md) | 고정 대진 GPU 학습·실험 실행 | Accepted |
| [D-127](../research/fixed-matchup-learning/decisions/D-127-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Accepted |
| [D-131](../shared/governance/decisions/D-131-research-branch-preservation.md) | 연구 목적별 브랜치 분리와 실험 자산 보존 | Accepted |
| [D-160](../research/model-evaluation/decisions/D-160-strategist-first-battle.md) | Strategist 첫 배틀 탐색 평가 | Accepted |
| [EP-098](../shared/execution/plans/EP-098-rlcd-lite-environment.md) | RLCD-Lite 전용 worktree 환경 | Completed |
| [EP-102](../research/action-value/plans/EP-102-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 첫 학습 검증 | Completed |
| [EP-103](../research/action-value/plans/EP-103-qwen-local-battle.md) | Qwen 로컬 서빙과 PokéChamp 연결 | Blocked |
| [EP-104](../research/action-value/plans/EP-104-qwen-training-matchup.md) | Qwen 학습 원대진 실전 배틀 | Completed |
| [EP-105](../shared/viewers/plans/EP-105-viewer-action-names.md) | 뷰어 결정의 실제 기술·포켓몬 이름 표시 | Completed |
| [EP-106](../research/action-value/plans/EP-106-qwen-candidate-state.md) | EX-063 후보 상태 입력·결정별 지침·진단 | Completed |
| [EP-114](../research/policy-learning/plans/EP-114-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 구체화 | Completed |
| [EP-115](../research/policy-learning/plans/EP-115-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EP-132](../research/fixed-matchup-learning/plans/EP-132-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 자기대국 학습 실행 | Completed |
| [EP-135](../shared/governance/plans/EP-135-research-branch-preservation.md) | 연구 브랜치 분리와 검증된 보존본 | Completed |
| [EP-171](../shared/datasets/plans/EP-171-strategist-model-archive.md) | Pokémon Showdown Strategist 모델 보관·정보 확인 | Completed |
| [EP-173](../research/rule-learning/plans/EP-173-tacit-ruleqa-lora.md) | Tacit 규칙 Q&A LoRA | Completed |
| [EX-061](../research/action-value/experiments/EX-061-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 행동가치 개발 실험 | Completed |
| [EX-062](../research/action-value/experiments/EX-062-qwen-local-battle.md) | Qwen 최종 LoRA 로컬 배틀 연결 검증 | Blocked |
| [EX-063](../research/action-value/experiments/EX-063-qwen-training-matchup.md) | Qwen 학습 원대진 배틀 진단 | Completed |
| [EX-064](../research/action-value/experiments/EX-064-qwen-candidate-state.md) | Qwen 후보 상태 입력 3조건 개발 진단 | Completed |
| [EX-066](../research/action-value/experiments/EX-066-joint-q-training.md) | Qwen3.5-4B-Base 공동 q 학습·독립 평가 | Blocked — 새 프로세스 재로딩 gate 실패 |
| [EX-068](../research/model-evaluation/experiments/EX-068-kev-battle.md) | Kev-4B pokechamp r1 연결 smoke | Completed — D-109 조건의 연결 수락 검사 완료. 원 unmerged gate 실패는 보존. |
| [EX-071](../research/policy-learning/experiments/EX-071-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EX-076](../research/fixed-matchup-learning/experiments/EX-076-fixed-matchup-mcts.md) | 고정 A/B 공개 상태 MCTS 정책 학습 | Incomplete — 교정 후 기술 검증/측정 통과, 평가 예산 gate 초과로 학습/test 보류 |
| [EX-077](../research/fixed-matchup-learning/experiments/EX-077-fixed-matchup-day.md) | 하루 내 고정 대진 공개 상태 학습 | Incomplete — 사용자 요청 중지; 학습/test 미시작 |
| [EX-080](../research/fixed-matchup-learning/experiments/EX-080-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Completed — 시도 3 학습(round40 둔화 종료)·선택(round36)·잠긴 test·감사/뷰어/봉인·정리 완료; 주효능 미입증 (시도 1·2는 도구 결함으로 학습 전 중단·보존) |
| [EX-081](../research/action-value/experiments/EX-081-joint-q-battle.md) | EX066 epoch3 재현성 복구·GPU0 실제 test20 | Completed |
| [EX-082](../research/model-evaluation/experiments/EX-082-jev27b-ex058-reproduction.md) | JEV-27B로 EX-058 개선 입력 동일32 평가 | Blocked |
| [EX-106](../research/model-evaluation/experiments/EX-106-strategist-first-battle.md) | Strategist 소형 모델 첫 배틀 | Completed |
| [EX-111](../research/model-evaluation/experiments/EX-111-jevk5-v6-battle32.md) | JevK5-9B v6 상세32경기 | Completed |

## Strategist

| ID | 제목 | 상태 |
|---|---|---|
| [D-160](../research/model-evaluation/decisions/D-160-strategist-first-battle.md) | Strategist 첫 배틀 탐색 평가 | Accepted |
| [EP-171](../shared/datasets/plans/EP-171-strategist-model-archive.md) | Pokémon Showdown Strategist 모델 보관·정보 확인 | Completed |
| [EP-172](../research/model-evaluation/plans/EP-172-strategist-first-battle.md) | Strategist 소형 모델 첫 배틀 | Completed |
| [EX-106](../research/model-evaluation/experiments/EX-106-strategist-first-battle.md) | Strategist 소형 모델 첫 배틀 | Completed |

## Tacit

| ID | 제목 | 상태 |
|---|---|---|
| [D-157](../research/planner-executor/decisions/D-157-tacit-thinking-low.md) | Tacit-9B Thinking + GLM-5.3 Low 판단 비교 | Accepted |
| [D-158](../research/planner-executor/decisions/D-158-tacit-vllm-low.md) | 기존 Tacit vLLM 서버로 새 평가 | Accepted |
| [D-161](../research/rule-learning/decisions/D-161-tacit-ruleqa-lora.md) | Tacit 규칙 Q&A LoRA 1회 | Accepted |
| [D-162](../research/rule-learning/decisions/D-162-tacit-ruleqa-battle32.md) | 학습 Tacit의 실전32 예약 | Accepted |
| [EP-163](../research/planner-executor/plans/EP-163-tacit-thinking-low.md) | Tacit Thinking low 판단 비교 | Blocked |
| [EP-164](../research/planner-executor/plans/EP-164-tacit-vllm-low.md) | Tacit vLLM 서버 새 평가 | Completed |
| [EP-173](../research/rule-learning/plans/EP-173-tacit-ruleqa-lora.md) | Tacit 규칙 Q&A LoRA | Completed |
| [EP-176](../research/rule-learning/plans/EP-176-tacit-ruleqa-battle32.md) | 학습 Tacit 실전32 예약 | Completed |
| [EX-104](../research/planner-executor/experiments/EX-104-tacit-thinking-low.md) | Tacit-9B Thinking + GLM-5.3 Low 판단 비교 | Blocked |
| [EX-105](../research/planner-executor/experiments/EX-105-tacit-vllm-low.md) | Tacit vLLM Thinking + GLM-5.3 Low | Completed |
| [EX-107](../research/rule-learning/experiments/EX-107-tacit-ruleqa-lora.md) | Tacit-9B 규칙 Q&A LoRA | Completed |
| [EX-108](../research/rule-learning/experiments/EX-108-tacit-ruleqa-battle32.md) | 학습 Tacit 규칙 Q&A 어댑터 실전32 | Completed |

## laya

| ID | 제목 | 상태 |
|---|---|---|
| [D-183](../research/policy-learning/decisions/D-183-laya-compact-imitation.md) | laya 압축 입력 모방 학습과 표준 배틀 평가 | Accepted |
| [D-184](../research/policy-learning/decisions/D-184-laya-team-generalization.md) | laya 모방 모델의 새 팀 일반화 평가 | Accepted |
| [D-185](../research/policy-learning/decisions/D-185-laya-modular-renderer-v2.md) | laya 모듈형 렌더러 v2(기술 변형·속도·교체·피해량) | Accepted |
| [D-187](../research/policy-learning/decisions/D-187-laya-tera-knowledge.md) | laya v2에 테라 기본 지식 데이터 추가(GPU1) | Accepted |
| [D-188](../research/policy-learning/decisions/D-188-laya-effect-knowledge.md) | laya v2+테라에 기술·도구·특성 효과 지식 데이터 추가(GPU2) | Accepted |
| [D-189](../research/policy-learning/decisions/D-189-laya-renderer-v3-opponent-sets.md) | laya 렌더러 v3(상대 세트 추론)와 래더 대비 학습(GPU0) | Accepted |
| [D-190](../research/policy-learning/decisions/D-190-laya-ex129-gate-override.md) | EX-128 진행 조건 미충족에도 EX-129 배틀 실행(사용자 결정) | Accepted |
| [D-191](../research/policy-learning/decisions/D-191-no-offline-battle-gate.md) | 오프라인 test 평가로 배틀 평가를 거르지 않는다 | Accepted |
| [D-192](../research/policy-learning/decisions/D-192-laya-renderer-v4-fail-out.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해)와 GPU1 학습·배틀 | Accepted |
| [D-193](../research/policy-learning/decisions/D-193-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방(GPU0 학습·배틀) | Accepted |
| [D-194](../research/policy-learning/decisions/D-194-laya-head-to-head-evaluation.md) | laya 직접 대결 평가(GPU2, EX-120 일정) | Accepted |
| [D-195](../research/policy-learning/decisions/D-195-laya-item-state-renderer-v5.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터)와 학습·배틀 | Accepted |
| [D-196](../research/policy-learning/decisions/D-196-laya-v2t-corrected-input-battle.md) | laya v2+테라(EX-124)를 재학습 없이 D-195 보정 입력으로 배틀(GPU1) | Accepted |
| [D-197](../research/policy-learning/decisions/D-197-laya-v2t-tera-decision-defence.md) | laya v2+테라(EX-124) fix 입력에서 테라 합산 결정과 테라 방어 문구 배틀(재학습 없음, GPU1) | Accepted |
| [EP-207](../shared/execution/plans/EP-207-laya-0413-environment.md) | laya 0.4.13 독립 학습·추론 환경 | Completed |
| [EP-208](../research/policy-learning/plans/EP-208-laya-compact-imitation.md) | laya 압축 입력 모방 학습·배틀 에이전트 | Completed |
| [EP-209](../research/policy-learning/plans/EP-209-laya-team-generalization.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EP-210](../research/policy-learning/plans/EP-210-laya-renderer-v2.md) | laya 모듈형 렌더러 v2 학습과 v1·v2 비교 | Completed |
| [EP-212](../research/policy-learning/plans/EP-212-laya-tera-knowledge.md) | laya v2 테라 지식 데이터 학습과 배틀 비교(GPU1) | Completed |
| [EP-213](../research/policy-learning/plans/EP-213-laya-effect-knowledge.md) | laya v2+테라+효과 지식 데이터 학습과 배틀 비교(GPU2) | Completed |
| [EP-214](../research/policy-learning/plans/EP-214-laya-renderer-v3.md) | laya 렌더러 v3(상대 세트 추론) 학습과 배틀 비교(GPU0) | Completed |
| [EP-215](../research/policy-learning/plans/EP-215-laya-renderer-v4.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) 학습과 배틀 비교(GPU1) | Active |
| [EP-216](../research/policy-learning/plans/EP-216-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방 학습과 배틀 비교(GPU0) | Active |
| [EP-217](../research/policy-learning/plans/EP-217-laya-head-to-head-evaluation.md) | laya 직접 대결 평가 하네스와 벤치마크(GPU2) | Active |
| [EP-218](../research/policy-learning/plans/EP-218-laya-renderer-v5-item-state.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) 학습과 배틀 비교(GPU0·GPU2) | Active |
| [EP-219](../research/policy-learning/plans/EP-219-laya-v2t-corrected-input-battle.md) | laya v2+테라 보정 입력 배틀(재학습 없음, GPU1) | Completed |
| [EP-220](../research/policy-learning/plans/EP-220-laya-v2t-tera-decision-defence.md) | laya v2+테라 fix 입력 테라 합산 결정·테라 방어 문구 배틀(재학습 없음, GPU1) | Active |
| [EX-118](../research/policy-learning/experiments/EX-118-laya-compact-imitation-training.md) | laya 압축 입력 리플레이 모방 학습 | Completed |
| [EX-119](../research/policy-learning/experiments/EX-119-laya-compact-imitation-battle32.md) | laya 압축 입력 모방 모델 EX-089 표준 32경기 | Completed |
| [EX-120](../research/policy-learning/experiments/EX-120-laya-team-generalization128.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EX-121](../research/policy-learning/experiments/EX-121-laya-v2-all-training.md) | laya 모듈형 렌더러 v2(4종 전부) 학습과 v1 쌍비교 | Completed |
| [EX-122](../research/policy-learning/experiments/EX-122-laya-v1-v2-battle256.md) | laya v1·v2 같은 실행 256경기 비교 (EX-120 일정) | Completed |
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
