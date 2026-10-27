# 결정 목록

<!-- generated: scripts/context-catalog build -->

원문 상태를 그대로 표시한다. 완료 상태는 효능 개선을 뜻하지 않는다.

| ID | 제목 | 상태 |
|---|---|---|
| [D-001](../shared/governance/decisions/D-001-persistent-project-context-control-plane.md) | Persistent project-context control plane 수립 | 채택 (Accepted) |
| [D-002](../shared/governance/decisions/D-002-reset-research-direction.md) | 연구 방향 reset 및 legacy plan 제외 | 채택 (Accepted) |
| [D-003](../shared/governance/decisions/D-003-korean-primary-documentation.md) | 한국어 우선 문서 정책 채택 | 채택 (Accepted) |
| [D-004](../shared/governance/decisions/D-004-split-accumulating-records.md) | 누적형 기록을 index와 개별 문서로 분리 | 채택 (Accepted) |
| [D-005](../research/l1-l5-port/decisions/D-005-adopt-pokechamp-l1-l5-research-goal.md) | `pokechamp` 대상 L1-L5 적용 연구 목표 채택 | 채택 (Accepted) |
| [D-006](../shared/execution/decisions/D-006-adopt-pokechamp-environment-boundary.md) | PokéChamp 연구 환경 및 외부 경계 채택 | [`D-007`](../shared/execution/decisions/D-007-adopt-pokechamp-dotenv-credential.md)로 대체됨 (Superseded) |
| [D-007](../shared/execution/decisions/D-007-adopt-pokechamp-dotenv-credential.md) | PokéChamp `.env` credential 정책을 포함한 연구 환경 경계 채택 | 채택 (Accepted) |
| [D-008](../shared/execution/decisions/D-008-fail-closed-cloud-json-actions.md) | Ollama Cloud JSON action의 thinking 비활성화와 fail-closed 검증 | [`D-009`](../shared/execution/decisions/D-009-adapt-always-on-reasoning-output.md)로 대체됨 (Superseded) |
| [D-009](../shared/execution/decisions/D-009-adapt-always-on-reasoning-output.md) | Always-on reasoning model의 compact action output 경계 채택 | 채택 (Accepted) |
| [D-010](../shared/viewers/decisions/D-010-adopt-pokechamp-battle-observability.md) | PokéChamp battle full-fidelity observability 경계 채택 | 채택 (Accepted) |
| [D-011](../shared/execution/decisions/D-011-default-untimed-showdown-battles.md) | PokéChamp 실험의 Showdown battle timer 기본 비활성화 | 채택 (Accepted) |
| [D-012](../shared/execution/decisions/D-012-adopt-pokechamp-baseline-pilot.md) | PokéChamp 기준선 pilot 채택 | Accepted |
| [D-013](../shared/execution/decisions/D-013-remove-client-output-cap.md) | 사용자 지시에 따른 LLM 출력 상한 최대화 | Accepted |
| [D-014](../shared/execution/decisions/D-014-increase-cloud-request-timeout.md) | Cloud 요청 timeout 300초 | Accepted |
| [D-015](../shared/execution/decisions/D-015-repeat-benchmark-profiles.md) | 반복 연구용 8판·32판 benchmark 설정 | Accepted |
| [D-016](../shared/execution/decisions/D-016-model-concurrency.md) | 계정·모델 요청 제한과 병렬 운영 측정 | Accepted |
| [D-017](../shared/execution/decisions/D-017-battle-identity-action-candidates.md) | 배틀 식별과 요청별 행동 후보 통합 | Accepted |
| [D-018](../shared/execution/decisions/D-018-upstream-fallback.md) | 원본 행동 생성과 출력 fallback 조건 | Accepted |
| [D-019](../research/input-and-memory/decisions/D-019-improved-io.md) | IO 관측·계산·고정 정책 및 배틀 내 요약 비교 | Accepted |
| [D-020](../research/input-and-memory/decisions/D-020-project-owned-ruination-patch.md) | 프로젝트 소유 Ruination 계산 패치 | Accepted |
| [D-021](../research/input-and-memory/decisions/D-021-special-move-diagnostics.md) | 특수 기술 피해의 독립 오프라인 진단 | Accepted |
| [D-022](../research/input-and-memory/decisions/D-022-resume-io-experiment.md) | EX-017 재실험 및 발생 오류 중심 패치 | Accepted |
| [D-023](../research/input-and-memory/decisions/D-023-summary-harness-diagnostics.md) | 요약 오류의 harness 기여도 진단 | Accepted |
| [D-024](../research/input-and-memory/decisions/D-024-state-summary-thinking.md) | 상태 처리 정비와 요약 thinking 비교 | Accepted |
| [D-025](../shared/governance/decisions/D-025-agent-instruction-boundaries.md) | 승인 근거와 작업 중단·완료 범위 명료화 | 채택 (Accepted) |
| [D-026](../research/input-and-memory/decisions/D-026-continue-io-experiment.md) | EX-017 계열 IO 실험의 사용자 승인 재개 | Accepted |
| [D-027](../research/input-and-memory/decisions/D-027-low-summary-prompt-reexperiment.md) | low 요약 지시 개선과 IO 재실험 | Accepted |
| [D-028](../research/input-and-memory/decisions/D-028-summary-max-diagnostic.md) | 요약 thinking low/max 독립 진단 | Accepted |
| [D-029](../shared/governance/decisions/D-029-experiment-defect-recovery.md) | 새 실험의 테스트·평가 결함 복구 절차 | 채택 (Accepted) |
| [D-030](../research/input-and-memory/decisions/D-030-io-battle-only.md) | 요약을 제외한 improved_io A/B 비교 | Accepted |
| [D-031](../research/input-and-memory/decisions/D-031-battle-field-guide.md) | B 행동 입력 필드 설명서 | Accepted |
| [D-032](../research/input-and-memory/decisions/D-032-battle-guide-live.md) | 필드 설명서 v1.1.0 실제 Cloud 병렬 배틀 | Accepted |
| [D-033](../research/input-and-memory/decisions/D-033-battle-guide-direct32.md) | 사전 검증 생략 32판과 오류 턴 표시 | Accepted |
| [D-034](../research/input-and-memory/decisions/D-034-calculator-entry-calcfix32.md) | 계산기 등장 특성 교정 및 동일32판 | Accepted |
| [D-035](../research/input-and-memory/decisions/D-035-calculator-input-audit.md) | 계산기 입력 전체 조사와 결함 수정 | Accepted |
| [D-036](../research/input-and-memory/decisions/D-036-calculator-inputfix32.md) | 교정 입력·계산기 동일32판 | Accepted |
| [D-037](../research/input-and-memory/decisions/D-037-calculator-move-names.md) | 계산기 기술명 정규화 | Accepted |
| [D-038](../research/input-and-memory/decisions/D-038-battle-guide-movefix32.md) | 수정 완료본 A/B32판 새 실행 | Accepted |
| [D-039](../research/input-and-memory/decisions/D-039-external-memory-repeat32.md) | 외부 메모리 장애 기록 및 동일 조건 재실험 | Accepted |
| [D-040](../research/input-and-memory/decisions/D-040-smogon-diagnostic-design.md) | Smogon 기반 원본 A 진단 평가 준비 | Accepted — 평가 준비 범위 |
| [D-041](../research/input-and-memory/decisions/D-041-a-diagnostic64.md) | Smogon 원본 A64 진단 실행 | Accepted |
| [D-042](../research/input-and-memory/decisions/D-042-ab-head-to-head32.md) | 원본 A 대 변경 구성 B 직접 대결32경기 | Accepted |
| [D-043](../research/input-and-memory/decisions/D-043-protect-expiry.md) | Protect 만료 정규화 교정 | Accepted |
| [D-044](../research/input-and-memory/decisions/D-044-ab-head-to-head32-protectfix.md) | Protect 수정본 직접32 연속 실행 | Accepted |
| [D-045](../shared/execution/decisions/D-045-cloud-concurrency-default8.md) | 전체 Cloud 기본 동시성 8 | Accepted |
| [D-046](../research/input-and-memory/decisions/D-046-b-prompt-optimization.md) | B 판단 정보 보존형 전달 표현 | Accepted |
| [D-047](../research/input-and-memory/decisions/D-047-ab-head-to-head32-b2.md) | B2 직접대결32 실행 | Accepted |
| [D-048](../research/input-and-memory/decisions/D-048-delayed-target-slot.md) | 지연 기술 대상 슬롯 교정 | Accepted |
| [D-049](../shared/viewers/decisions/D-049-viewer-turn-tabs.md) | Viewer 턴 탭과 LLM 응답 기본 표시 | Accepted |
| [D-050](../shared/governance/decisions/D-050-io-explanation-review-opt-in.md) | 기본 IO 테스트 설명 오류 기입은 명시 요청 시 수행 | Accepted |
| [D-051](../shared/governance/decisions/D-051-context-document-maintenance.md) | 의미를 보존하는 컨텍스트 문서 정리 | Accepted |
| [D-052](../research/lead-policy/decisions/D-052-llm-lead.md) | B2의 별도 LLM 선봉 정책 | Accepted |
| [D-053](../research/lead-policy/decisions/D-053-b2-lead-comparison.md) | EX-039 선봉 정책 비교 실행 승인 | Accepted |
| [D-054](../shared/execution/decisions/D-054-zai-provider.md) | Z.ai 배틀 공급자 선택 | Accepted |
| [D-055](../research/lead-policy/decisions/D-055-b2-lead-zai.md) | EX-040 Z.ai B2 선봉 정책 재비교 | Accepted |
| [D-056](../research/lead-policy/decisions/D-056-zai-concurrency4.md) | Z.ai 기본 동시성4 및 EX-041 | Accepted |
| [D-057](../research/input-and-memory/decisions/D-057-effect-reference.md) | 구조 설명과 요청별 상세 효과 사전 | Accepted |
| [D-058](../shared/execution/decisions/D-058-transport-retry.md) | 응답 대기600초·연결 오류 재시도 | Accepted |
| [D-059](../research/lead-policy/decisions/D-059-distributed-lead.md) | Ollama Cloud·Z.ai 동시성4+4 분산 선봉 실험 | Accepted |
| [D-060](../shared/execution/decisions/D-060-provider-retry-viewer.md) | 공급자 오류 재시도 확대·정상 경기 viewer | Accepted |
| [D-061](../research/lead-policy/decisions/D-061-lead-matchup-rules.md) | 선봉 전략과 규칙 입력의 독립 개선 | Accepted |
| [D-062](../research/input-and-memory/decisions/D-062-court-change-input-audit.md) | Court Change 입력 교정과 EX-042 전수 오프라인 감사 | Accepted |
| [D-063](../research/input-and-memory/decisions/D-063-intermediate-research-objectives.md) | 입력 정보·이력·요약의 중간 연구 목표 채택 | Accepted |
| [D-064](../research/lead-policy/decisions/D-064-corrected-lead.md) | 교정 B2 개선 선봉 비교 | Accepted |
| [D-065](../research/lead-policy/decisions/D-065-direct-corrected-lead.md) | 교정 선봉 비교 재실행·사전 검사 생략 | Accepted |
| [D-066](../research/input-and-memory/decisions/D-066-official-observation.md) | 공식 클라이언트 관측 소스 채택 | Accepted |
| [D-067](../research/lead-policy/decisions/D-067-official-lead.md) | 공식 관측 B2 선봉 정책 본실험 | Accepted |
| [D-068](../research/input-and-memory/decisions/D-068-official-async.md) | 공식 관측 비동기 완료 경계 교정 | Accepted |
| [D-069](../research/lead-policy/decisions/D-069-async-official-lead.md) | 비동기 교정본 공식 관측 선봉 본실험 | Accepted |
| [D-070](../shared/execution/decisions/D-070-jev-client.md) | JEV 환경 설정과 독립 호출 기반 | Accepted |
| [D-071](../research/model-evaluation/decisions/D-071-jev-battle.md) | JEV Choice 배틀 연결 | Accepted |
| [D-072](../research/model-evaluation/decisions/D-072-jev-probability-validation.md) | JEV 확률 합계 검사 제거 | Accepted |
| [D-073](../research/model-evaluation/decisions/D-073-jev-repeat.md) | JEV 수정본2경기 재실행 | Accepted |
| [D-074](../shared/execution/decisions/D-074-provider-judgment-policy.md) | 공급자 판단 오류의 전체 실험 중단 제외 | Accepted |
| [D-075](../research/model-evaluation/decisions/D-075-jev-judgment-repeat.md) | 판단 오류 비중단 적용 JEV 재실행 | Accepted |
| [D-076](../shared/viewers/decisions/D-076-viewer-export-location.md) | 정상 종료 실험 뷰어의 고정 내보내기 경로 | Accepted |
| [D-077](../shared/viewers/decisions/D-077-jev-replay-viewer.md) | 내보내기 뷰어에 배틀 리플레이 포함 | Accepted |
| [D-078](../shared/viewers/decisions/D-078-researcher-viewer.md) | 실험자 중심 입력·응답 뷰어 | Accepted |
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
| [D-090](../shared/datasets/decisions/D-090-team-corpus-role-expansion.md) | 팀 데이터 기반 열람 역할 DB 확장 | Accepted |
| [D-091](../shared/datasets/decisions/D-091-reviewed-species-team-list.md) | 검토 완료108종으로 팀 후보 제한 | Accepted |
| [D-092](../research/input-and-memory/decisions/D-092-jev-offline-input.md) | JEV 오프라인 입력 표현 개선 | Accepted |
| [D-093](../research/input-and-memory/decisions/D-093-speed-uncertainty.md) | 스피드 확률 대신 세트별 불확실성 | Accepted |
| [D-094](../research/input-and-memory/decisions/D-094-jev-improved32.md) | 개선 JEV 입력 동일32경기 | Accepted |
| [D-095](../research/input-and-memory/decisions/D-095-jev-compact32.md) | 자기 벤치 축약 동일32경기 | Accepted |
| [D-096](../research/policy-learning/decisions/D-096-pokemon-training-objective.md) | 세 RLCD 환경을 활용한 포켓몬 전용 학습 당면 목표 채택 | Accepted |
| [D-097](../research/action-value/decisions/D-097-single-battle-branch-rollouts.md) | EX-058 한 경기 행동별 분기 데이터 | Accepted |
| [D-098](../research/action-value/decisions/D-098-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 첫 행동가치 학습 | Accepted |
| [D-099](../research/action-value/decisions/D-099-qwen-local-battle.md) | Qwen 행동가치 로컬 서빙·배틀 연결 | Accepted |
| [D-100](../research/action-value/decisions/D-100-qwen-training-matchup.md) | Qwen 학습 원대진 실전 진단 | Accepted |
| [D-101](../shared/viewers/decisions/D-101-viewer-action-names.md) | 뷰어 결정의 실제 행동 이름 | Accepted |
| [D-102](../research/action-value/decisions/D-102-qwen-candidate-state.md) | EX-063 후보 실행 후 상태 평가 개선 | Accepted |
| [D-103](../research/action-value/decisions/D-103-joint-q-data.md) | 다경기 공동 q 데이터 | Accepted |
| [D-104](../research/action-value/decisions/D-104-joint-q-training.md) | EX-065 기반 Base 공동 q 학습 | Accepted |
| [D-105](../research/action-value/decisions/D-105-joint-q-gpu2.md) | 공동 q 학습의 GPU2 지정 | Accepted |
| [D-106](../research/action-value/decisions/D-106-joint-q-idle-gpu.md) | 공동 q 학습의 유휴 GPU 대체 | Accepted |
| [D-107](../research/action-value/decisions/D-107-abyssal-tera-joint-q.md) | Abyssal Tera 보완 학습 데이터 | Accepted |
| [D-108](../research/model-evaluation/decisions/D-108-kev-battle.md) | pokechamp r1 Kev-4B 연결 검증 | Accepted |
| [D-109](../research/model-evaluation/decisions/D-109-kev-fused-validation.md) | Kev fused·merged 서빙의 추가 수락 검사 | Accepted |
| [D-110](../research/model-evaluation/decisions/D-110-kev-test-battles.md) | 기존 test 대진의 Kev 본 배틀 | Accepted |
| [D-111](../research/model-evaluation/decisions/D-111-kev-continuation-question.md) | Kev 후속 정책 질문의 1경기 진단 | Accepted |
| [D-112](../research/policy-learning/decisions/D-112-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 채택 | Accepted |
| [D-113](../research/policy-learning/decisions/D-113-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Accepted |
| [D-114](../research/policy-learning/decisions/D-114-selfplay-rlcd.md) | 단일 GPU 자기대국과 선택 행동 확률 보정 | Accepted |
| [D-115](../research/policy-learning/decisions/D-115-abyssal-first-objective.md) | Abyssal 상대 효율적 승리를 당면 단기 목표로 채택 | Accepted |
| [D-116](../research/policy-learning/decisions/D-116-abyssal-rl.md) | Abyssal 전용 4GPU·24시간 학습 승인 | Accepted |
| [D-117](../research/policy-learning/decisions/D-117-abyssal-rl-continue.md) | 57라운드 계승·동일 설정 추가12시간 승인 | Accepted |
| [D-118](../research/policy-learning/decisions/D-118-abyssal-rl-next.md) | 82라운드 계승·추가12시간 1회 승인 | Accepted |
| [D-119](../research/fixed-matchup-learning/decisions/D-119-fixed-matchup-mcts.md) | 고정 대진 공개 상태 MCTS 정책 학습 | Accepted |
| [D-120](../research/fixed-matchup-learning/decisions/D-120-fixed-matchup-run.md) | 고정 대진 GPU 학습·실험 실행 | Accepted |
| [D-121](../research/fixed-matchup-learning/decisions/D-121-fixed-matchup-fnt-recovery.md) | 기절 상태 교정 후 원 예산 재개 | Accepted |
| [D-122](../research/fixed-matchup-learning/decisions/D-122-fixed-matchup-day.md) | 하루 내 예상 시 고정 대진 실행 | Accepted |
| [D-123](../research/fixed-matchup-learning/decisions/D-123-fixed-matchup-first-round.md) | 첫1라운드 체크포인트 진단 | Accepted |
| [D-124](../research/fixed-matchup-learning/decisions/D-124-fixed-matchup-no-time-limit.md) | 현재1라운드 실험의 경과시간 상한 해제 | Accepted |
| [D-125](../research/fixed-matchup-learning/decisions/D-125-first-round-single-retry.md) | 실패1경기 재수집·첫라운드 재개 | Accepted |
| [D-126](../research/fixed-matchup-learning/decisions/D-126-fixed-matchup-stopping.md) | 성능·정체·학습량 종료조건을 갖춘 추가 학습 | Accepted |
| [D-127](../research/fixed-matchup-learning/decisions/D-127-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Accepted |
| [D-128](../research/fixed-matchup-learning/decisions/D-128-qwen-fixed-shape-serving.md) | EX-080 고정 shape 서빙과 G3·G4 게이트 재정의 | Accepted |
| [D-129](../research/action-value/decisions/D-129-joint-q-battle.md) | EX066 epoch3의 GPU0 배틀 평가 | Accepted |
| [D-130](../research/model-evaluation/decisions/D-130-jev27b-ex058-reproduction.md) | JEV-27B 공개 가중치로 개선 입력 동일32 평가 | Accepted |
| [D-131](../shared/governance/decisions/D-131-research-branch-preservation.md) | 연구 목적별 브랜치 분리와 실험 자산 보존 | Accepted |
| [D-132](../research/model-evaluation/decisions/D-132-jev27b-four-gpu-continuation.md) | EX-082 정상23경기 계승·4GPU 잔여9경기 | Accepted |
| [D-133](../research/model-evaluation/decisions/D-133-quyet-medium-two-stage.md) | Quyet-Medium 2단계 정책 동일32경기 | Accepted |
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
| [D-145](../research/planner-executor/decisions/D-145-goal-completion-sample.md) | 바뀐 수행 프롬프트의 실제 샘플1경기 | Accepted |
| [D-146](../research/planner-executor/decisions/D-146-planner-json-retries.md) | GLM JSON 구문 오류 최대5회 재시도·새 샘플 | Accepted |
| [D-147](../research/planner-executor/decisions/D-147-planner-unlimited-disk.md) | GLM·JEV 향후 실행의 디스크 용량 상한 해제 | Accepted |
| [D-148](../research/planner-executor/decisions/D-148-jev35b-nvfp4-sample.md) | JEV-35B-NVFP4 단일 GPU 동일 대진 샘플 | Accepted |
| [D-149](../research/planner-executor/decisions/D-149-nvfp4-battle-with-probability-diagnostics.md) | 확률 변동을 기록하며 NVFP4 실제1경기 진행 | Accepted |
| [D-150](../research/planner-executor/decisions/D-150-planner-format-retries-temperature-zero.md) | GLM 응답 형식 재시도·기본 temperature0 | Accepted |
| [D-151](../research/planner-executor/decisions/D-151-planner-high-effort-sample.md) | GLM high 추론 강도 동일 대진 샘플 | Accepted |
| [D-152](../research/planner-executor/decisions/D-152-planner-unlimited-time-max-output.md) | 경기/전체 시간 상한 해제·GLM 최대 출력 새1경기 | Accepted |
| [D-153](../research/planner-executor/decisions/D-153-glm53-low-sample.md) | GLM-5.3 low 동일 대진 새1경기 | Accepted |
| [D-154](../research/planner-executor/decisions/D-154-matchup-events.md) | 매치업 변화 기반 계획 갱신 | Accepted |
| [D-155](../research/planner-executor/decisions/D-155-matchup-events-high.md) | 매치업 사건 GLM high 동일 대진 | Accepted |
| [D-156](../research/planner-executor/decisions/D-156-jev-omni-low.md) | Jev-Omni + GLM-5.3 low 동일 대진 | Accepted |
| [D-157](../research/planner-executor/decisions/D-157-tacit-thinking-low.md) | Tacit-9B Thinking + GLM-5.3 Low 판단 비교 | Accepted |
| [D-158](../research/planner-executor/decisions/D-158-tacit-vllm-low.md) | 기존 Tacit vLLM 서버로 새 평가 | Accepted |
| [D-159](../research/rule-learning/decisions/D-159-showdown-ruleqa.md) | Showdown 규칙 Q&A 데이터셋 v1 | Accepted |
| [D-160](../research/model-evaluation/decisions/D-160-strategist-first-battle.md) | Strategist 첫 배틀 탐색 평가 | Accepted |
| [D-161](../research/rule-learning/decisions/D-161-tacit-ruleqa-lora.md) | Tacit 규칙 Q&A LoRA 1회 | Accepted |
| [D-162](../research/rule-learning/decisions/D-162-tacit-ruleqa-battle32.md) | 학습 Tacit의 실전32 예약 | Accepted |
| [D-163](../shared/execution/decisions/D-163-openai-decisions-environment.md) | 독립 OpenAI Decisions API 환경 | Accepted |
| [D-164](../research/model-evaluation/decisions/D-164-openai-decisions-v6-battle32.md) | OpenAI Decisions v6 상세32경기 | Accepted |
| [D-165](../research/model-evaluation/decisions/D-165-openai-decisions-retry32.md) | OpenAI 통신 재시도와 새32경기 | Accepted |
| [D-166](../research/model-evaluation/decisions/D-166-jevk5-v6-battle32.md) | JevK5-9B v6 상세32경기 | Accepted |
| [D-167](../research/input-and-memory/decisions/D-167-candidate-matchup-summary.md) | 후보별 현재 상대 적용결과 보강 | Accepted |
| [D-168](../research/input-and-memory/decisions/D-168-openai-candidate-matchup-battle.md) | 후보별 상성 요약 OpenAI 동일32경기 | Accepted |
| [D-169](../research/rule-learning/decisions/D-169-jevk5-ruleqa-lora.md) | JevK5 규칙 선택형 추가 LoRA | Accepted |
| [D-170](../shared/governance/decisions/D-170-purpose-based-context.md) | 연구 목적별 문서 배치와 분산 규범 원문 | Accepted |
| [D-171](../shared/governance/decisions/D-171-blocked-classification.md) | Blocked 계획의 별도 관리 분류 | Accepted |
| [D-172](../shared/viewers/decisions/D-172-battle-viewer-ui-standard.md) | 배틀 viewer UI 규격과 변경 기록 | Accepted |
| [D-173](../research/rule-learning/decisions/D-173-jevk5-ruleqa-battle32.md) | 학습 JevK5 규칙 LoRA 실전32 | Accepted |
| [D-174](../research/rule-learning/decisions/D-174-gen9-type-matchup-dataset.md) | Gen9 타입 상성 전수 자료 | Accepted |
| [D-175](../research/rule-learning/decisions/D-175-replay-ko-system1-data.md) | 실제 리플레이의 관측 KO 결과 학습자료 | Accepted |
| [D-176](../research/rule-learning/decisions/D-176-conditional-ko-system1-data.md) | 조건부 KO와 관측 KO의 분리 | Accepted |
| [D-177](../research/rule-learning/decisions/D-177-smogon-role-system1-data.md) | Smogon 분석의 역할 근거 학습 | Accepted |
| [D-178](../research/rule-learning/decisions/D-178-gen9-mechanics-system1-data.md) | 우선순위별 규칙 적용과 정보 충분성 자료 | Accepted |
| [D-179](../research/input-and-memory/decisions/D-179-candidate-action-v7.md) | 후보 중심 v7와 응답 복구 탐색 실험 | Accepted |
| [D-180](../research/rule-learning/decisions/D-180-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Accepted |
| [D-181](../research/input-and-memory/decisions/D-181-v7-survival-switch-cost.md) | v7 생존 판단과 교체 기회비용 지침 | Accepted |
| [D-182](../research/input-and-memory/decisions/D-182-v7-survival-battle32.md) | 생존·교체 비용 v7 GPT-6 Luna 32경기 | Accepted |
| [D-183](../research/policy-learning/decisions/D-183-laya-compact-imitation.md) | laya 압축 입력 모방 학습과 표준 배틀 평가 | Accepted |
| [D-184](../research/policy-learning/decisions/D-184-laya-team-generalization.md) | laya 모방 모델의 새 팀 일반화 평가 | Accepted |
| [D-185](../research/policy-learning/decisions/D-185-laya-modular-renderer-v2.md) | laya 모듈형 렌더러 v2(기술 변형·속도·교체·피해량) | Accepted |
| [D-186](../research/rule-learning/decisions/D-186-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Accepted |
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
