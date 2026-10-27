# 실행 계획 목록

<!-- generated: scripts/context-catalog build -->

원문 상태를 그대로 표시한다. 완료 상태는 효능 개선을 뜻하지 않는다.

<a id="running-plans"></a>

## 진행

| ID | 제목 | 상태 |
|---|---|---|
| [EP-215](../research/policy-learning/plans/EP-215-laya-renderer-v4.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) 학습과 배틀 비교(GPU1) | Active |
| [EP-216](../research/policy-learning/plans/EP-216-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방 학습과 배틀 비교(GPU0) | Active |
| [EP-217](../research/policy-learning/plans/EP-217-laya-head-to-head-evaluation.md) | laya 직접 대결 평가 하네스와 벤치마크(GPU2) | Active |
| [EP-218](../research/policy-learning/plans/EP-218-laya-renderer-v5-item-state.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) 학습과 배틀 비교(GPU0·GPU2) | Active |
| [EP-220](../research/policy-learning/plans/EP-220-laya-v2t-tera-decision-defence.md) | laya v2+테라 fix 입력 테라 합산 결정·테라 방어 문구 배틀(재학습 없음, GPU1) | Active |

<a id="blocked-plans"></a>

## Blocked 별도 관리

원래 판정과 현재 처리 필요 여부를 구분한다. [별도 색인](blocked.md)에서 이유·후속·근거를 확인한다.

| 관리 분류 | 계획 수 |
|---|---|
| [해결 대기](blocked.md#awaiting) | 0 |
| [후속 해결·종결](blocked.md#resolved) | 15 |
| [진행 종료](blocked.md#ended) | 2 |
| [확인 필요](blocked.md#review) | 19 |

<a id="paused-plans"></a>

## 일시 중지·기타 중단

| ID | 제목 | 상태 |
|---|---|---|
| [EP-126](../research/fixed-matchup-learning/plans/EP-126-fixed-matchup-day.md) | 하루 내 고정 대진 실험 | Paused — 사용자 요청 중지; 학습·test 미시작 |

<a id="completed-plans"></a>

## 완료

| ID | 제목 | 상태 |
|---|---|---|
| [EP-001](../shared/execution/plans/EP-001-pokechamp-reproducible-environment.md) | PokéChamp 재현 가능 연구 환경 구성 | Completed |
| [EP-002](../shared/viewers/plans/EP-002-pokechamp-battle-observability.md) | PokéChamp battle observability logging 및 정적 viewer | Completed |
| [EP-003](../shared/execution/plans/EP-003-default-untimed-showdown-battles.md) | PokéChamp Showdown battle timer 기본 비활성화 | Completed |
| [EP-004](../shared/execution/plans/EP-004-pokechamp-baseline-pilot.md) | PokéChamp 기준선 도구와 pilot | Completed |
| [EP-005](../shared/execution/plans/EP-005-remove-client-output-cap.md) | Cloud 출력 상한 최대화 | Completed |
| [EP-006](../shared/execution/plans/EP-006-repeat-benchmark-profiles.md) | 반복 benchmark 설정과 시간 재측정 | Completed |
| [EP-007](../shared/execution/plans/EP-007-model-concurrency.md) | 모델 동시성 측정과 병렬 배틀 | Completed |
| [EP-008](../shared/execution/plans/EP-008-parallel-thirty-two-repeat.md) | 병렬 32판 추가 실행 | Completed |
| [EP-009](../shared/execution/plans/EP-009-battle-identity-action-candidates.md) | 배틀 환경과 행동 출력 계약 수정 | Completed |
| [EP-010](../shared/execution/plans/EP-010-upstream-fallback.md) | 원본 fallback 병렬32판 | Completed |
| [EP-014](../shared/governance/plans/EP-014-agent-instruction-maintenance.md) | 승인·중단 지시와 현재 상태 정합화 | Completed |
| [EP-016](../research/input-and-memory/plans/EP-016-input-summary-documentation.md) | 현재 입력·요약 구조 문서화 | Completed |
| [EP-017](../shared/governance/plans/EP-017-experiment-defect-recovery.md) | 테스트·평가 결함 복구 절차 문서화 | Completed |
| [EP-019](../research/input-and-memory/plans/EP-019-battle-field-guide.md) | B 행동 입력 필드 설명서 | Completed |
| [EP-021](../research/input-and-memory/plans/EP-021-battle-guide-direct32.md) | 사전 검증 생략 32판과 오류 턴 표시 | Completed |
| [EP-022](../research/input-and-memory/plans/EP-022-calculator-entry-calcfix32.md) | 계산기 등장 특성 교정 및 동일32판 | Completed — 사용자 중단 대안 포함 완료; 성능 비교 미완료 |
| [EP-023](../research/input-and-memory/plans/EP-023-calculator-input-audit.md) | 계산기 입력 전체 조사와 결함 수정 | Completed |
| [EP-024](../research/input-and-memory/plans/EP-024-calculator-inputfix32.md) | 교정 입력·계산기 동일 조건 A/B32판 | Completed |
| [EP-025](../research/input-and-memory/plans/EP-025-calculator-move-names.md) | 계산기 기술명 정규화 버그 수정 | Completed |
| [EP-026](../research/input-and-memory/plans/EP-026-battle-guide-movefix32.md) | 수정 완료본 A/B32판 본 실험 | Completed — 승인된 중단 포함 작업 완료, 성능 비교 미완료 |
| [EP-027](../research/input-and-memory/plans/EP-027-external-memory-repeat32.md) | 외부 메모리 장애 후 동일 조건32판 재실험 | Completed |
| [EP-028](../research/input-and-memory/plans/EP-028-smogon-diagnostic-design.md) | Smogon 기반 원본 A 진단 평가 준비 | Completed — 평가 준비 구현·로컬 검증 완료, 대전 미실행 |
| [EP-029](../research/input-and-memory/plans/EP-029-a-diagnostic64.md) | Smogon 원본 A64 진단 실행 | Completed |
| [EP-031](../research/input-and-memory/plans/EP-031-protect-expiry.md) | Protect 만료 정규화 교정 | Completed |
| [EP-033](../shared/execution/plans/EP-033-cloud-concurrency-default8.md) | 전체 Cloud 기본 동시성 8 | Completed |
| [EP-034](../research/input-and-memory/plans/EP-034-b-prompt-optimization.md) | B 판단 정보 보존형 프롬프트 최적화 | Completed |
| [EP-036](../research/input-and-memory/plans/EP-036-delayed-target-slot.md) | 지연 기술 대상 슬롯 입력 교정 | Completed |
| [EP-037](../shared/viewers/plans/EP-037-viewer-turn-tabs.md) | Viewer 턴 탭과 LLM 응답 기본 표시 | Completed |
| [EP-038](../shared/governance/plans/EP-038-io-explanation-review-opt-in.md) | 기본 IO 테스트 설명 오류 기입 명시 선택 | Completed |
| [EP-039](../shared/governance/plans/EP-039-context-document-maintenance.md) | 현재 컨텍스트 문서 정리 | Completed |
| [EP-040](../research/lead-policy/plans/EP-040-llm-lead.md) | B2 LLM 선봉 선택 | Completed |
| [EP-042](../shared/execution/plans/EP-042-zai-provider.md) | Z.ai 배틀 공급자 연결 및 환경 구성 | Completed |
| [EP-043](../shared/execution/plans/EP-043-zai-connectivity-probe.md) | Z.ai 단일 연결 확인 | Completed |
| [EP-046](../research/input-and-memory/plans/EP-046-effect-reference.md) | 배틀·선봉 구조 설명과 상세 효과 사전 | Completed |
| [EP-047](../shared/execution/plans/EP-047-transport-retry.md) | 응답 대기600초·연결 오류 재시도 | Completed |
| [EP-049](../shared/execution/plans/EP-049-provider-retry-viewer.md) | 공급자 오류 재시도 확대·정상 경기 viewer | Completed |
| [EP-050](../research/lead-policy/plans/EP-050-lead-matchup-rules.md) | 선봉 전략·Dex 규칙 독립 개선 | Completed |
| [EP-051](../research/input-and-memory/plans/EP-051-court-change-input-audit.md) | Court Change 입력 교정·EX-042 전체 감사 | Completed |
| [EP-052](../research/input-and-memory/plans/EP-052-intermediate-research-objectives.md) | 입력 정보·메모리 설계 중간 연구 목표 문서화 | Completed |
| [EP-055](../research/input-and-memory/plans/EP-055-observation-tracker-comparison.md) | Abyssal 플레이어별 관측 추적 비교 | Completed |
| [EP-056](../research/input-and-memory/plans/EP-056-official-observation.md) | 공식 클라이언트 관측의 B/B2 운영 통합 | Completed |
| [EP-058](../research/input-and-memory/plans/EP-058-official-async.md) | 공식 관측 비동기 처리 교정 | Completed |
| [EP-059](../research/lead-policy/plans/EP-059-async-official-lead.md) | 비동기 교정본 공식 관측 선봉 본실험 | Completed |
| [EP-060](../shared/viewers/plans/EP-060-portable-viewer.md) | EX-046 다운로드용 단일 폴더 뷰어 | Completed |
| [EP-061](../shared/execution/plans/EP-061-jev-client.md) | JEV 환경 설정과 독립 호출 기반 | Completed |
| [EP-063](../research/model-evaluation/plans/EP-063-jev-probability-validation.md) | JEV 확률 합계 검사 제거 | Completed |
| [EP-065](../shared/execution/plans/EP-065-provider-judgment-policy.md) | 공급자 판단 오류의 전체 중단 제외 | Completed |
| [EP-066](../research/model-evaluation/plans/EP-066-jev-judgment-repeat.md) | 판단 오류 격리 적용·JEV 2경기 재실행 | Completed |
| [EP-067](../shared/viewers/plans/EP-067-viewer-export-location.md) | 정상 종료 실험 뷰어 내보내기 위치 | Completed |
| [EP-068](../shared/viewers/plans/EP-068-jev-replay-viewer.md) | EX-050 배틀 리플레이 통합 | Completed |
| [EP-069](../shared/viewers/plans/EP-069-researcher-viewer.md) | 실험자용 JEV 뷰어 가독성 | Completed |
| [EP-070](../research/input-and-memory/plans/EP-070-jev-lead-input.md) | JEV 선봉 입력 교정과 오프라인 회귀 | Completed |
| [EP-071](../research/input-and-memory/plans/EP-071-jev-v2-battle.md) | 교정 JEV 입력 v2 동일 조건2경기 | Completed |
| [EP-072](../shared/viewers/plans/EP-072-viewer-navigation-hp.md) | 뷰어 단축키·상대 HP 비율 표시 | Completed |
| [EP-073](../research/model-evaluation/plans/EP-073-jev-abyssal32.md) | JEV 대 Abyssal 32경기 본실험 | Completed |
| [EP-074](../research/input-and-memory/plans/EP-074-jev-v3-effects.md) | JEV v3 기본 지식·효과 사전 | Completed |
| [EP-076](../shared/execution/plans/EP-076-provider-retry-three.md) | provider 오류 재시도3회 고정 | Completed |
| [EP-078](../research/input-and-memory/plans/EP-078-jev-failed-input-probe.md) | 실패 입력 현재 응답 확인 | Completed |
| [EP-079](../shared/execution/plans/EP-079-jev-retry-backoff.md) | JEV 재시도 대기10·30·60초 | Completed |
| [EP-081](../research/input-and-memory/plans/EP-081-jev-pinned32.md) | jev-1.13.0 고정 직접32경기 | Completed |
| [EP-082](../research/input-and-memory/plans/EP-082-jev-damage-samples.md) | 기술별 피해량 범위 오프라인 프롬프트 샘플 | Completed |
| [EP-083](../shared/datasets/plans/EP-083-team-role-export.md) | 팀 풀 44종 역할 DB 내보내기 | Completed |
| [EP-084](../shared/datasets/plans/EP-084-role-export-readable.md) | 역할 DB 열람본 정리 | Completed |
| [EP-085](../shared/datasets/plans/EP-085-role-export-no-ev.md) | 열람본 노력치 정보 제거 | Completed |
| [EP-086](../shared/datasets/plans/EP-086-role-export-field-guide.md) | 역할 DB 열람본 필드 설명서 | Completed |
| [EP-087](../shared/datasets/plans/EP-087-role-evidence-restore.md) | 노력치 외 판단 조건 복원 | Completed |
| [EP-088](../shared/datasets/plans/EP-088-remove-empty-roles.md) | 빈 근거 역할 두 개 제거 | Completed |
| [EP-089](../shared/datasets/plans/EP-089-ex057-role-assessment.md) | EX-057 제출 팀 역할 대조 | Completed |
| [EP-090](../shared/datasets/plans/EP-090-team-pool-role-coverage.md) | 전체 저장 팀 역할 커버리지 검사 | Completed |
| [EP-091](../shared/datasets/plans/EP-091-team-corpus-role-expansion.md) | 전체 팀 데이터 기반 역할 DB 확장 | Completed |
| [EP-092](../shared/datasets/plans/EP-092-reviewed-species-team-list.md) | 검토 완료108종 팀 후보 목록 | Completed |
| [EP-093](../research/input-and-memory/plans/EP-093-jev-offline-input.md) | JEV 입력 표현 개선·오프라인 검증 | Completed |
| [EP-094](../research/input-and-memory/plans/EP-094-jev-improved32.md) | 개선 JEV 입력 동일32경기 | Completed |
| [EP-095](../research/input-and-memory/plans/EP-095-jev-compact32.md) | 자기 벤치 축약 동일32경기 | Completed |
| [EP-096](../shared/execution/plans/EP-096-laya-training-environment.md) | LAYA 전용 worktree 학습 환경 | Completed |
| [EP-097](../shared/execution/plans/EP-097-eve-rlcd-environment.md) | EVE-RLCD 전용 worktree 환경 | Completed |
| [EP-098](../shared/execution/plans/EP-098-rlcd-lite-environment.md) | RLCD-Lite 전용 worktree 환경 | Completed |
| [EP-099](../research/policy-learning/plans/EP-099-pokemon-training-objective.md) | 포켓몬 전용 모델 학습 당면 목표 문서화 | Completed |
| [EP-100](../shared/datasets/plans/EP-100-replay-rule-eligibility.md) | 현재 로컬 Gen9 OU 리플레이 규칙 적합성 분류 | Completed |
| [EP-101](../research/action-value/plans/EP-101-single-battle-branch-rollouts.md) | EX-058 한 경기 분기 데이터 추출기 | Completed |
| [EP-102](../research/action-value/plans/EP-102-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 첫 학습 검증 | Completed |
| [EP-104](../research/action-value/plans/EP-104-qwen-training-matchup.md) | Qwen 학습 원대진 실전 배틀 | Completed |
| [EP-105](../shared/viewers/plans/EP-105-viewer-action-names.md) | 뷰어 결정의 실제 기술·포켓몬 이름 표시 | Completed |
| [EP-106](../research/action-value/plans/EP-106-qwen-candidate-state.md) | EX-063 후보 상태 입력·결정별 지침·진단 | Completed |
| [EP-107](../research/action-value/plans/EP-107-joint-q-data.md) | Abyssal 80경기 공동 q 데이터 | Completed |
| [EP-109](../shared/governance/plans/EP-109-astra-subagent-guidance.md) | Astra 서브에이전트 활용 지침 | Completed |
| [EP-110](../research/action-value/plans/EP-110-abyssal-tera-joint-q.md) | Abyssal Tera 정책과 보완 공동 q 데이터 | Completed |
| [EP-111](../research/model-evaluation/plans/EP-111-kev-battle.md) | 학습된 Kev-4B 실시간 배틀 연결 | Completed |
| [EP-112](../research/model-evaluation/plans/EP-112-kev-test-battles.md) | EX-065 test20 대진의 Kev 본 테스트 | Completed |
| [EP-113](../research/model-evaluation/plans/EP-113-kev-continuation-question.md) | Kev 후속 정책 질문의 1경기 진단 | Completed |
| [EP-114](../research/policy-learning/plans/EP-114-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 구체화 | Completed |
| [EP-115](../research/policy-learning/plans/EP-115-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EP-116](../research/policy-learning/plans/EP-116-selfplay-rlcd.md) | 자기대국과 RLCD 확률 보정 | Completed |
| [EP-117](../research/policy-learning/plans/EP-117-selfplay-finalization-recovery.md) | EX-072 오프라인 뷰어 검증·최종화 복구 | Completed |
| [EP-118](../research/policy-learning/plans/EP-118-abyssal-first-objective.md) | Abyssal 우선 단기 목표 정비 | Completed |
| [EP-120](../research/policy-learning/plans/EP-120-abyssal-preflight-recovery.md) | EX-073 수치 사전검사 복구 도구 | Completed |
| [EP-121](../research/policy-learning/plans/EP-121-abyssal-rl-continue.md) | 57라운드 계승 추가12시간 | Completed |
| [EP-122](../research/policy-learning/plans/EP-122-abyssal-rl-next.md) | 82라운드 계승 추가12시간 | Completed |
| [EP-123](../research/input-and-memory/plans/EP-123-life-orb-input.md) | Life Orb 공개 입력 교정 | Completed |
| [EP-124](../research/fixed-matchup-learning/plans/EP-124-fixed-matchup-mcts.md) | 고정 대진 공개 상태 MCTS 구현 | Completed — 구현·CPU 개발 검증 완료, 실험 미실행 |
| [EP-128](../research/fixed-matchup-learning/plans/EP-128-fixed-matchup-no-time-limit.md) | EX-078 경과시간 상한 해제 | Completed |
| [EP-129](../research/fixed-matchup-learning/plans/EP-129-first-round-single-retry.md) | 실패1경기 재수집·1라운드 재개 | Completed |
| [EP-130](../research/fixed-matchup-learning/plans/EP-130-first-round-model-comparison.md) | 첫라운드 전후 동일 관측 비교 | Completed |
| [EP-131](../research/fixed-matchup-learning/plans/EP-131-fixed-matchup-stopping.md) | 종료조건 기반 추가 학습·독립 평가 | Completed |
| [EP-132](../research/fixed-matchup-learning/plans/EP-132-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 자기대국 학습 실행 | Completed |
| [EP-133](../research/action-value/plans/EP-133-joint-q-battle.md) | EX066 epoch3의 GPU0 실제 배틀 평가 | Completed |
| [EP-135](../shared/governance/plans/EP-135-research-branch-preservation.md) | 연구 브랜치 분리와 검증된 보존본 | Completed |
| [EP-136](../shared/governance/plans/EP-136-branch-research-manuals.md) | 분리된 연구선의 매뉴얼 정비 | Completed |
| [EP-137](../research/model-evaluation/plans/EP-137-jev27b-four-gpu-continuation.md) | JEV-27B 4GPU 잔여9경기 계승 | Completed |
| [EP-138](../research/model-evaluation/plans/EP-138-quyet-medium-two-stage.md) | Quyet-Medium 2단계 정책 동일32 평가 | Completed |
| [EP-139](../research/model-evaluation/plans/EP-139-jev9b-single-choice.md) | JEV-9B 단일 Choice 동일32 평가 | Completed |
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
| [EP-152](../research/planner-executor/plans/EP-152-planner-json-retry-sample.md) | GLM JSON 구문 재시도·샘플1경기 | Completed |
| [EP-153](../research/planner-executor/plans/EP-153-planner-unlimited-disk.md) | GLM·JEV 디스크 상한 해제 | Completed |
| [EP-156](../research/planner-executor/plans/EP-156-planner-format-temperature-zero.md) | GLM 형식 재시도·temperature0 실제1경기 | Completed |
| [EP-158](../research/planner-executor/plans/EP-158-planner-unlimited-time-max-output.md) | 시간 상한 없는 GLM 최대 출력 실제1경기 | Completed |
| [EP-159](../research/planner-executor/plans/EP-159-glm53-low-sample.md) | GLM-5.3 low 동일 대진 실제1경기 | Completed |
| [EP-160](../research/planner-executor/plans/EP-160-matchup-events.md) | 매치업 변화 기반 GLM 계획 갱신 | Completed |
| [EP-161](../research/planner-executor/plans/EP-161-matchup-events-high.md) | GLM high 매치업 사건 동일1경기 | Completed |
| [EP-162](../research/planner-executor/plans/EP-162-jev-omni-low.md) | Jev-Omni low 동일1경기 | Completed |
| [EP-164](../research/planner-executor/plans/EP-164-tacit-vllm-low.md) | Tacit vLLM 서버 새 평가 | Completed |
| [EP-165](../shared/datasets/plans/EP-165-showdown-sft-archive.md) | Pokémon Showdown SFT 원본 보관 | Completed |
| [EP-166](../shared/datasets/plans/EP-166-pokechamp-dataset-archive.md) | milkkarten/pokechamp 원본 보관 | Completed |
| [EP-167](../shared/datasets/plans/EP-167-dataset-manual.md) | 보관 데이터셋 매뉴얼 안내 | Completed |
| [EP-168](../shared/datasets/plans/EP-168-pretrain-data-archive.md) | pokechamp-pretrain-data 원본 보관 | Completed |
| [EP-169](../research/rule-learning/plans/EP-169-showdown-ruleqa.md) | Showdown 규칙 Q&A·State 데이터셋 v1 | Completed |
| [EP-170](../shared/datasets/plans/EP-170-pokemon-training-data-archive.md) | pokemon-training-data 원본 보관 | Completed |
| [EP-171](../shared/datasets/plans/EP-171-strategist-model-archive.md) | Pokémon Showdown Strategist 모델 보관·정보 확인 | Completed |
| [EP-172](../research/model-evaluation/plans/EP-172-strategist-first-battle.md) | Strategist 소형 모델 첫 배틀 | Completed |
| [EP-173](../research/rule-learning/plans/EP-173-tacit-ruleqa-lora.md) | Tacit 규칙 Q&A LoRA | Completed |
| [EP-174](../shared/datasets/plans/EP-174-smogon-ou-strategy-links.md) | Smogon OU 포켓몬·전략 링크 목록 | Completed |
| [EP-175](../shared/datasets/plans/EP-175-smogon-ou-strategy-data.md) | Smogon OU 전략 전수 수집 | Completed |
| [EP-176](../research/rule-learning/plans/EP-176-tacit-ruleqa-battle32.md) | 학습 Tacit 실전32 예약 | Completed |
| [EP-177](../shared/viewers/plans/EP-177-ex108-viewer-layout.md) | EX108 기존 뷰어 구성 복원 | Completed |
| [EP-178](../shared/execution/plans/EP-178-openai-decisions-environment.md) | OpenAI Decisions API 환경 | Completed |
| [EP-180](../research/model-evaluation/plans/EP-180-openai-decisions-retry32.md) | OpenAI 통신 재시도 새32경기 | Completed |
| [EP-181](../research/model-evaluation/plans/EP-181-jevk5-v6-battle32.md) | JevK5-9B v6 상세32경기 | Completed |
| [EP-182](../research/input-and-memory/plans/EP-182-candidate-matchup-summary.md) | 후보별 현재 대면 상성·효과 요약 | Completed |
| [EP-184](../research/rule-learning/plans/EP-184-jevk5-ruleqa-lora.md) | JevK5 규칙 선택형 추가 LoRA | Completed |
| [EP-185](../shared/governance/plans/EP-185-purpose-based-context.md) | 연구 목적 중심 컨텍스트 재구성 | Completed |
| [EP-186](../shared/governance/plans/EP-186-blocked-classification.md) | Blocked 계획 별도 분류 | Completed |
| [EP-187](../shared/viewers/plans/EP-187-battle-viewer-ui-standard.md) | 배틀 viewer UI 규격·변경 절차 고정 | Completed |
| [EP-188](../shared/viewers/plans/EP-188-ex112-viewer-ui-v1.md) | EX-112 viewer UI v1 재구성 | Completed |
| [EP-189](../shared/viewers/plans/EP-189-ex112-response-action-names.md) | EX-112 응답 탭의 실제 행동 이름 | Completed |
| [EP-190](../research/rule-learning/plans/EP-190-jevk5-vllm-serving-check.md) | JevK5 추가 LoRA vLLM 서빙 확인 | Completed |
| [EP-191](../research/rule-learning/plans/EP-191-jevk5-ruleqa-battle32.md) | 학습 JevK5 LoRA 실전32 실행 | Completed |
| [EP-192](../research/rule-learning/plans/EP-192-gen9-type-matchup-dataset.md) | Gen9 타입 상성 전수 학습 데이터 | Completed |
| [EP-193](../research/rule-learning/plans/EP-193-gen9-type-system1-data.md) | Gen9 타입 System 1 판별 학습자료 | Completed |
| [EP-194](../research/input-and-memory/plans/EP-194-ex112-input-structure-reference.md) | EX-112 입력 구조 참조 문서 | Completed |
| [EP-195](../research/rule-learning/plans/EP-195-gen9-status-system1-data.md) | Gen9 상태이상 System 1 학습자료 | Completed |
| [EP-196](../research/rule-learning/plans/EP-196-gen9-priority-system1-data.md) | Gen9 행동 우선도 System 1 자료 | Completed |
| [EP-197](../research/rule-learning/plans/EP-197-gen9-weather-terrain-system1-data.md) | Gen9 날씨·영역 System 1 자료 | Completed |
| [EP-198](../research/rule-learning/plans/EP-198-replay-ko-system1-data.md) | 실제 리플레이 KO 결과 예측 System 1 자료 | Completed |
| [EP-199](../research/rule-learning/plans/EP-199-conditional-ko-system1-data.md) | 조건부 확정 KO 판정 자료 | Completed |
| [EP-200](../research/rule-learning/plans/EP-200-smogon-role-system1-data.md) | Smogon 전략 기반 역할 System 1 자료 | Completed |
| [EP-201](../research/rule-learning/plans/EP-201-gen9-mechanics-system1-data.md) | 우선순위별 Gen9 규칙 적용 System 1 자료 | Completed |
| [EP-202](../research/input-and-memory/plans/EP-202-candidate-action-v7.md) | 후보 중심 v7와 GPT-6 Luna 32경기 | Completed |
| [EP-203](../research/rule-learning/plans/EP-203-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |
| [EP-204](../research/input-and-memory/plans/EP-204-human-input-structure-guides.md) | 사람이 읽는 입력 구조 상세 문서 폴더 | Completed |
| [EP-205](../research/input-and-memory/plans/EP-205-v7-survival-switch-cost.md) | v7 생존 판단과 교체 비용 지시문 개정 | Completed |
| [EP-207](../shared/execution/plans/EP-207-laya-0413-environment.md) | laya 0.4.13 독립 학습·추론 환경 | Completed |
| [EP-208](../research/policy-learning/plans/EP-208-laya-compact-imitation.md) | laya 압축 입력 모방 학습·배틀 에이전트 | Completed |
| [EP-209](../research/policy-learning/plans/EP-209-laya-team-generalization.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EP-210](../research/policy-learning/plans/EP-210-laya-renderer-v2.md) | laya 모듈형 렌더러 v2 학습과 v1·v2 비교 | Completed |
| [EP-211](../research/rule-learning/plans/EP-211-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Completed |
| [EP-212](../research/policy-learning/plans/EP-212-laya-tera-knowledge.md) | laya v2 테라 지식 데이터 학습과 배틀 비교(GPU1) | Completed |
| [EP-213](../research/policy-learning/plans/EP-213-laya-effect-knowledge.md) | laya v2+테라+효과 지식 데이터 학습과 배틀 비교(GPU2) | Completed |
| [EP-214](../research/policy-learning/plans/EP-214-laya-renderer-v3.md) | laya 렌더러 v3(상대 세트 추론) 학습과 배틀 비교(GPU0) | Completed |
| [EP-219](../research/policy-learning/plans/EP-219-laya-v2t-corrected-input-battle.md) | laya v2+테라 보정 입력 배틀(재학습 없음, GPU1) | Completed |

<a id="other-plans"></a>

## 기타

| ID | 제목 | 상태 |
|---|---|---|
