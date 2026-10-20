# 의사결정 색인 (Decision Index)

이 파일은 지속되는 architecture 및 design decision의 registry다. 실제 맥락, 결정, 근거, 영향,
evidence는 [`decisions/`](decisions/) 아래의 개별 ADR이 보존한다. 이 index는 changelog, task
list 또는 contract의 대체물이 아니다.

## Decision registry

| ID | Status | Date | Title |
|---|---|---|---|
| [D-169](decisions/D-169-jevk5-ruleqa-lora.md) | Accepted | 2026-10-20 | JevK5 규칙 선택형 LoRA |
| [D-168](decisions/D-168-openai-candidate-matchup-battle.md) | Accepted | 2026-10-20 | 후보별 요약 OpenAI 동일32경기 |
| [D-167](decisions/D-167-candidate-matchup-summary.md) | Accepted | 2026-10-20 | 후보별 현재 대면 적용결과 보강 |
| [D-166](decisions/D-166-jevk5-v6-battle32.md) | Accepted | 2026-10-20 | JevK5-9B v6 상세32경기 |
| [D-165](decisions/D-165-openai-decisions-retry32.md) | Accepted | 2026-10-20 | OpenAI 통신 재시도·시간무상한 새32경기 |
| [D-164](decisions/D-164-openai-decisions-v6-battle32.md) | Accepted | 2026-10-20 | OpenAI Decisions v6 상세32경기 |
| [D-163](decisions/D-163-openai-decisions-environment.md) | Accepted | 2026-10-20 | 독립 OpenAI Decisions API 환경 |
| [D-162](decisions/D-162-tacit-ruleqa-battle32.md) | Accepted | 2026-10-19 | 학습 Tacit 실전32 예약 |
| [D-161](decisions/D-161-tacit-ruleqa-lora.md) | Accepted | 2026-10-19 | Tacit 규칙 Q&A LoRA1회 |
| [D-160](decisions/D-160-strategist-first-battle.md) | Accepted | 2026-10-19 | Strategist 첫 배틀 탐색 평가 |
| [D-159](decisions/D-159-showdown-ruleqa.md) | Accepted | 2026-10-19 | 신규 Showdown 규칙 Q&A 데이터셋 |
| [D-158](decisions/D-158-tacit-vllm-low.md) | Accepted | 2026-10-16 | 기존 Tacit vLLM 서버 새 평가 |
| [D-157](decisions/D-157-tacit-thinking-low.md) | Accepted | 2026-10-16 | Tacit Thinking + GLM-5.3 Low 판단 비교 |
| [D-156](decisions/D-156-jev-omni-low.md) | Accepted | 2026-10-15 | Jev-Omni BF16·GLM low 동일1경기 |
| [D-155](decisions/D-155-matchup-events-high.md) | Accepted | 2026-10-15 | 매치업 사건 GLM high 동일1경기 |
| [D-154](decisions/D-154-matchup-events.md) | Accepted | 2026-10-15 | 매치업 변화 기반 계획 갱신 |
| [D-153](decisions/D-153-glm53-low-sample.md) | Accepted | 2026-10-15 | GLM-5.3 low 동일 대진 새1경기 |
| [D-152](decisions/D-152-planner-unlimited-time-max-output.md) | Accepted | 2026-10-15 | 경기/전체 시간 상한 해제·GLM 최대 출력 새1경기 |
| [D-151](decisions/D-151-planner-high-effort-sample.md) | Accepted | 2026-10-15 | GLM high 추론 강도 동일 대진1경기 |
| [D-150](decisions/D-150-planner-format-retries-temperature-zero.md) | Accepted | 2026-10-15 | GLM 형식 재시도·기본 temperature0 |
| [D-149](decisions/D-149-nvfp4-battle-with-probability-diagnostics.md) | Accepted | 2026-10-15 | 확률 변동을 진단으로 유지하며 NVFP4 실제1경기 |
| [D-148](decisions/D-148-jev35b-nvfp4-sample.md) | Accepted | 2026-10-15 | JEV-35B-NVFP4 GPU0 동일 대진 샘플 |
| [D-147](decisions/D-147-planner-unlimited-disk.md) | Accepted | 2026-10-15 | 새 GLM·JEV 실행의 디스크 용량 상한 해제 |
| [D-146](decisions/D-146-planner-json-retries.md) | Accepted | 2026-10-15 | GLM JSON 구문 최대5회 재시도·새1경기 |
| [D-145](decisions/D-145-goal-completion-sample.md) | Accepted | 2026-10-15 | 목표 충족 확인 수행 지시문·동일 대진 샘플1경기 |
| [D-144](decisions/D-144-planner-replay-viewer.md) | Accepted | 2026-10-15 | 향후 GLM·JEV 탭·리플레이 통합 표시 |
| [D-143](decisions/D-143-executor-goal-completion.md) | Accepted | 2026-10-15 | JEV 계획 목표 충족 확인·불필요한 반복 회피 |
| [D-142](decisions/D-142-planner-first-battle-sample.md) | Accepted | 2026-10-15 | EX-088 첫 대진·현재 GLM planner/JEV-9B 실제1경기 |
| [D-141](decisions/D-141-candidate-display-names.md) | Accepted | 2026-10-15 | Planner/JEV 후보의 포켓몬·기술 표시 이름 |
| [D-140](decisions/D-140-planner-role-resource-guide.md) | Accepted | 2026-10-15 | Planner 역할·양측 승리 경로·자원 관리 안내 |
| [D-139](decisions/D-139-jev-planner-environment.md) | Accepted | 2026-10-15 | GLM 전략 planner·JEV 수행·호출/프롬프트 독립 설정·로컬 검증 |
| [D-138](decisions/D-138-minicpm5-2b-jev.md) | Accepted | 2026-10-14 | MiniCPM5-2B-Jev·GPU0·디스크 무상한·EX-089 비교 |
| [D-137](decisions/D-137-jev9b-no-damage.md) | Accepted | 2026-10-14 | JEV-9B 피해 예측 제거·스피드 유지·EX-089 비교 |
| [D-136](decisions/D-136-jev-v6-corrected-evaluation.md) | Accepted | 2026-10-13 | 교정v6·별도27B/9B 신규64경기 재승인 |
| [D-135](decisions/D-135-jev-public-memory-v6.md) | Accepted | 2026-10-13 | 상대 공개 정보 v6·턴 로그·27B/9B 신규64평가 |
| [D-134](decisions/D-134-jev9b-single-choice.md) | Accepted | 2026-10-13 | JEV-9B 단일 Choice 동일32 평가 |
| [D-133](decisions/D-133-quyet-medium-two-stage.md) | Accepted | 2026-10-13 | Quyet-Medium 2단계 동일32 평가 |
| [D-132](decisions/D-132-jev27b-four-gpu-continuation.md) | Accepted | 2026-10-13 | EX-082 정상23 계승·4GPU 검증 후 잔여9경기 |
| [D-131](decisions/D-131-research-branch-preservation.md) | Accepted | 2026-10-12 | 연구 목적별 브랜치·고정 기준 태그·외부 자산 복사 검증 |
| [D-130](decisions/D-130-jev27b-ex058-reproduction.md) | Accepted | 2026-10-08 | JEV-27B 공개 가중치·GPU0/1·EX-058 동일32·경과시간 상한 없음 |
| [D-129](decisions/D-129-joint-q-battle.md) | Accepted | 2026-10-08 | EX066 epoch3·GPU0·재현 기준 복구 후 test20·8시간 |
| [D-128](decisions/D-128-qwen-fixed-shape-serving.md) | Accepted | 2026-10-07 | EX-080 고정 shape 서빙(32행·길이 버킷)·G3 비트 동일·G4 fp32 경로 검증 |
| [D-127](decisions/D-127-qwen-matrix-selfplay.md) | Accepted | 2026-10-07 | Qwen3.5-0.8B 행렬 탐색 자기대국·둔화 종료·GPU2·3·등록 유예 |
| [D-126](decisions/D-126-fixed-matchup-stopping.md) | Accepted | 2026-10-07 | 성능·정체·라운드 종료조건 추가 학습·독립 시험 |
| [D-125](decisions/D-125-first-round-single-retry.md) | Accepted | 2026-10-07 | 정상31 계승·시간초과1경기 재수집·첫라운드 재개 |
| [D-124](decisions/D-124-fixed-matchup-no-time-limit.md) | Accepted | 2026-10-07 | 현재1라운드 경기·단계·전체 경과시간 상한 해제 |
| [D-123](decisions/D-123-fixed-matchup-first-round.md) | Accepted | 2026-10-07 | 첫1라운드 체크포인트 진단 |
| [D-122](decisions/D-122-fixed-matchup-day.md) | Accepted | 2026-10-07 | 전체 예상24시간 이하 조건부 고정 대진 실행 |
| [D-121](decisions/D-121-fixed-matchup-fnt-recovery.md) | Accepted | 2026-10-07 | 기절 분류 교정·실패8측정1회 재시도·원12시간 및 단계 소비 계승 |
| [D-120](decisions/D-120-fixed-matchup-run.md) | Accepted | 2026-10-07 | 고정 대진 GPU 학습·실험 단일12시간 실행 |
| [D-119](decisions/D-119-fixed-matchup-mcts.md) | Accepted | 2026-10-07 | 고정 대진 공개 상태 MCTS·구현 범위·D-115 당면 순서 부분 대체 |
| [D-118](decisions/D-118-abyssal-rl-next.md) | Accepted | 2026-10-06 | 82라운드 계승·동일 설정 추가12시간1회·새 test |
| [D-117](decisions/D-117-abyssal-rl-continue.md) | Accepted | 2026-10-05 | 57라운드 계승·동일 설정12시간·새 test·표본 뷰어·단계 알람 |
| [D-116](decisions/D-116-abyssal-rl.md) | Accepted | 2026-10-03 | Abyssal 전용4GPU·24시간 학습·독립 평가 |
| [D-115](decisions/D-115-abyssal-first-objective.md) | Accepted | 2026-10-03 | Abyssal 효율적 승리 우선·D-112 당면 순서 부분 대체 |
| [D-114](decisions/D-114-selfplay-rlcd.md) | Accepted | 2026-10-02 | 단일 GPU 자기대국·선택 행동 WDL 보정·평가 |
| [D-113](decisions/D-113-qwen-replay-imitation.md) | Accepted | 2026-10-01 | Qwen4B 리플레이 모방 학습·첫40경기 평가 |
| [D-112](decisions/D-112-imitation-self-play-objectives.md) | Accepted | 2026-10-01 | Qwen 모방 학습·자기대국 목표; 당면 순서는 [D-115](decisions/D-115-abyssal-first-objective.md)로 부분 대체 |
| [D-111](decisions/D-111-kev-continuation-question.md) | Accepted | 2026-10-01 | Kev 후속 정책 질문·동일 첫 대진1경기 진단 |
| [D-110](decisions/D-110-kev-test-battles.md) | Accepted | 2026-10-01 | 기존 test20대진 Kev 본 실행·추가 사전검사 생략 |
| [D-109](decisions/D-109-kev-fused-validation.md) | Accepted | 2026-10-01 | Kev fused·merged 추가3관측 검증·통과 시1경기 |
| [D-108](decisions/D-108-kev-battle.md) | Accepted | 2026-09-30 | Kev-4B r1 실시간 배틀 연결·수락 검사 |
| [D-107](decisions/D-107-abyssal-tera-joint-q.md) | Accepted | 2026-09-30 | 자발적 Tera 정책·보완80경기 공동 q 수집 |
| [D-106](decisions/D-106-joint-q-idle-gpu.md) | Accepted | 2026-09-30 | GPU2 사용 중 유휴 GPU1 대체 승인 |
| [D-105](decisions/D-105-joint-q-gpu2.md) | Accepted | 2026-09-30 | 공동 q 학습·사전검사·평가 GPU2 지정 |
| [D-104](decisions/D-104-joint-q-training.md) | Accepted | 2026-09-30 | EX-065 기반 Base 공동 q 학습·독립 test 평가 |
| [D-103](decisions/D-103-joint-q-data.md) | Accepted | 2026-09-29 | Abyssal80경기 공동 q 수집·재개·입력/로더 |
| [D-102](decisions/D-102-qwen-candidate-state.md) | Accepted | 2026-09-29 | 후보 상태 입력·결정별 지침·별도 진단 |
| [D-101](decisions/D-101-viewer-action-names.md) | Accepted | 2026-09-29 | 뷰어의 실제 기술·교체/선봉 이름 표시 |
| [D-100](decisions/D-100-qwen-training-matchup.md) | Accepted | 2026-09-29 | Qwen 학습 원대진 1경기 실전 진단 |
| [D-099](decisions/D-099-qwen-local-battle.md) | Accepted | 2026-09-28 | Qwen 로컬 서빙·배틀 연결 |
| [D-098](decisions/D-098-qwen-action-value.md) | Accepted | 2026-09-28 | EX-060 기반 Qwen3.5-4B 첫 행동가치 학습 |
| [D-097](decisions/D-097-single-battle-branch-rollouts.md) | Accepted | 2026-09-28 | EX-058 한 경기 행동별 분기 데이터 |
| [D-096](decisions/D-096-pokemon-training-objective.md) | Accepted | 2026-09-28 | 세 RLCD 환경을 활용한 포켓몬 전용 학습 당면 목표 |
| [D-095](decisions/D-095-jev-compact32.md) | Accepted | 2026-09-23 | 자기 벤치 축약 동일32경기 |
| [D-094](decisions/D-094-jev-improved32.md) | Accepted | 2026-09-23 | 개선 입력 동일32경기 승인 |
| [D-093](decisions/D-093-speed-uncertainty.md) | Accepted | 2026-09-23 | 스피드 확률을 세트별 불확실성으로 대체 |
| [D-092](decisions/D-092-jev-offline-input.md) | Accepted | 2026-09-22 | JEV 별도 오프라인 입력 개선·축약 비교 |
| [D-091](decisions/D-091-reviewed-species-team-list.md) | Accepted | 2026-09-22 | 검토 완료108종으로 팀 후보 제한 |
| [D-090](decisions/D-090-team-corpus-role-expansion.md) | Accepted | 2026-09-22 | 전체 팀 데이터 기반 열람 역할 DB 확장 |
| [D-089](decisions/D-089-jev-pinned32.md) | Accepted | 2026-09-21 | jev-1.13.0 고정 직접32 |
| [D-088](decisions/D-088-jev-direct32.md) | Accepted | 2026-09-21 | EX-056 사전 검증 생략 동일32 |
| [D-087](decisions/D-087-jev-retry-backoff.md) | Accepted | 2026-09-21 | JEV 재시도 대기10·30·60초 |
| [D-086](decisions/D-086-jev-failed-input-probe.md) | Accepted | 2026-09-21 | 실패 입력 현재 응답 확인 |
| [D-085](decisions/D-085-jev-v3-retry32.md) | Accepted | 2026-09-21 | EX-054 동일 조건 재실험 |
| [D-084](decisions/D-084-provider-retry-three.md) | Accepted | 2026-09-21 | provider 오류 재시도3회 고정 |
| [D-083](decisions/D-083-jev-v3-abyssal32.md) | Accepted | 2026-09-21 | JEV v3 동일32·v2 전후 비교 |
| [D-082](decisions/D-082-jev-v3-effects.md) | Accepted | 2026-09-21 | JEV v3 기본 지식·효과 사전 |
| [D-081](decisions/D-081-jev-abyssal32.md) | Accepted | 2026-09-21 | JEV 대 Abyssal32경기 본실험 |
| [D-080](decisions/D-080-jev-v2-battle.md) | Accepted | 2026-09-21 | 교정 JEV 입력 실제2경기 테스트 |
| [D-079](decisions/D-079-jev-lead-input.md) | Accepted | 2026-09-21 | JEV 자기 선봉 입력·초기 PP 근거 교정 |
| [D-078](decisions/D-078-researcher-viewer.md) | Accepted | 2026-09-21 | 실험자 중심 입력·응답 뷰어 |
| [D-077](decisions/D-077-jev-replay-viewer.md) | Accepted | 2026-09-21 | 내보내기 뷰어 배틀 리플레이 포함 |
| [D-076](decisions/D-076-viewer-export-location.md) | Accepted | 2026-09-21 | 정상 종료 뷰어 exports/battle_viewers 제공 |
| [D-075](decisions/D-075-jev-judgment-repeat.md) | Accepted | 2026-09-21 | JEV 판단 오류 비중단 적용2경기 |
| [D-074](decisions/D-074-provider-judgment-policy.md) | Accepted | 2026-09-21 | 새 실험의 공급자 판단 오류 전체 중단 제외 |
| [D-073](decisions/D-073-jev-repeat.md) | Accepted | 2026-09-21 | JEV 수정본2경기 재실행 |
| [D-072](decisions/D-072-jev-probability-validation.md) | Accepted | 2026-09-21 | JEV 확률 합계 검사 제거 |
| [D-071](decisions/D-071-jev-battle.md) | Accepted | 2026-09-21 | JEV Choice 배틀 연결 |
| [D-070](decisions/D-070-jev-client.md) | Accepted | 2026-09-21 | JEV 독립 호출·D-007/054 환경 범위 확장 |
| [D-069](decisions/D-069-async-official-lead.md) | Accepted | 2026-09-17 | 비동기 교정본 공식 관측 본실험 |
| [D-068](decisions/D-068-official-async.md) | Accepted | 2026-09-17 | 공식 관측 비동기 완료 경계 교정 |
| [D-067](decisions/D-067-official-lead.md) | Accepted | 2026-09-17 | 공식 관측 B2 선봉 본실험 |
| [D-065](decisions/D-065-direct-corrected-lead.md) | 2026-09-16 | Accepted | 교정 선봉 재실행·사전 검사 생략 |
| [D-066](decisions/D-066-official-observation.md) | Accepted | 2026-09-17 | 공식 관측 B/B2 통합 |
| [D-064](decisions/D-064-corrected-lead.md) | Accepted | 2026-09-16 | 교정 B2 개선 선봉 비교 |
| [D-063](decisions/D-063-intermediate-research-objectives.md) | Accepted | 2026-09-16 | 입력 정보·이력·요약의 중간 연구 목표 채택 |
| [D-061](decisions/D-061-lead-matchup-rules.md) | Accepted | 2026-09-16 | 선봉 전략·Dex 규칙 독립 개선 |
| [D-062](decisions/D-062-court-change-input-audit.md) | Accepted | 2026-09-16 | Court Change 입력 교정·EX-042 전체 오프라인 감사 |
| [D-060](decisions/D-060-provider-retry-viewer.md) | Accepted | 2026-09-16 | 공급자 오류 재시도 확대·정상 경기 viewer |
| [D-059](decisions/D-059-distributed-lead.md) | Accepted | 2026-09-15 | 공급자4+4 분산 선봉 실험 |
| [D-058](decisions/D-058-transport-retry.md) | Accepted | 2026-09-15 | 새 응답 대기600초·연결 오류 재시도 |
| [D-057](decisions/D-057-effect-reference.md) | Accepted | 2026-09-15 | 배틀·선봉 구조와 상세 효과 사전 |
| [D-056](decisions/D-056-zai-concurrency4.md) | Accepted | 2026-09-15 | Z.ai 기본4·EX-041 독립 재실험 |
| [D-055](decisions/D-055-b2-lead-zai.md) | Accepted | 2026-09-15 | EX-040 Z.ai 선봉 정책32·첫429 중단 승인 |
| [D-054](decisions/D-054-zai-provider.md) | Accepted | 2026-09-14 | 새 배틀 Z.ai 선택·설정·기록 및 과거 Ollama 호환 |
| [D-053](decisions/D-053-b2-lead-comparison.md) | Accepted | 2026-09-14 | EX-039 실행·기술 gate·보고 승인, 금액 상한 제외 |
| [D-052](decisions/D-052-llm-lead.md) | Accepted | 2026-09-14 | B2 선봉 선택 구현·로컬 검증 |
| [D-051](decisions/D-051-context-document-maintenance.md) | Accepted | 2026-09-14 | 의미를 보존하는 컨텍스트 문서 정리 |
| [D-050](decisions/D-050-io-explanation-review-opt-in.md) | Accepted | 2026-09-14 | 기본 IO 테스트 설명 오류 검토·기입은 명시 요청 시 수행 |
| [D-049](decisions/D-049-viewer-turn-tabs.md) | Accepted | 2026-09-14 | 새 viewer 턴 탐색·LLM 응답/reasoning 기본 표시 |
| [D-048](decisions/D-048-delayed-target-slot.md) | Accepted | 2026-09-14 | 지연 기술 대상 슬롯 교정·오프라인 검증 |
| [D-047](decisions/D-047-ab-head-to-head32-b2.md) | Accepted | 2026-09-14 | B2 실제 전달 연결·직접대결 |
| [D-046](decisions/D-046-b-prompt-optimization.md) | Accepted | 2026-09-14 | B0–B3 별도 전달 표현·오프라인 검증 |
| [D-045](decisions/D-045-cloud-concurrency-default8.md) | Accepted | 2026-09-13 | 새 Cloud 기본 동시성·과거 설정 호환 |
| [D-044](decisions/D-044-ab-head-to-head32-protectfix.md) | Accepted | 2026-09-11 | Protect 수정본 직접대결 |
| [D-043](decisions/D-043-protect-expiry.md) | Accepted | 2026-09-11 | B Protect 만료 교정·오프라인 검증 |
| [D-042](decisions/D-042-ab-head-to-head32.md) | Accepted | 2026-09-11 | 원본 A/B 직접대결 |
| [D-041](decisions/D-041-a-diagnostic64.md) | Accepted | 2026-09-11 | 원본 A 진단 실행 |
| [D-040](decisions/D-040-smogon-diagnostic-design.md) | Accepted | 2026-09-11 | Smogon 기반 원본 A 진단 평가 준비 |
| [D-039](decisions/D-039-external-memory-repeat32.md) | Accepted | 2026-09-11 | 외부 RAM 급증의 사용자 보고 기록·동일 조건 새32판 승인 |
| [D-038](decisions/D-038-battle-guide-movefix32.md) | Accepted | 2026-09-11 | 수정 완료본 새32판·기준 검증 재사용·변경분 qualification |
| [D-037](decisions/D-037-calculator-move-names.md) | Accepted | 2026-09-10 | Weather Ball 및 동일 originalName 분기 정규화 버그 수정 |
| [D-036](decisions/D-036-calculator-inputfix32.md) | Accepted | 2026-09-10 | 교정 입력·계산기 동일 조건 새 A/B32판 |
| [D-035](decisions/D-035-calculator-input-audit.md) | Accepted | 2026-09-10 | 계산기 입력 전체 로컬 조사·수정·독립 검증 |
| [D-034](decisions/D-034-calculator-entry-calcfix32.md) | Accepted | 2026-09-10 | 계산기 등장특성 교정·동일32판 |
| [D-033](decisions/D-033-battle-guide-direct32.md) | Accepted | 2026-09-09 | 직접 비교·오류 복구/표시 |
| [D-032](decisions/D-032-battle-guide-live.md) | Accepted | 2026-09-09 | 필드 설명서 실제 Cloud 비교 |
| [D-031](decisions/D-031-battle-field-guide.md) | Accepted | 2026-09-09 | B 행동 필드 설명서·로컬 검증 |
| [D-030](decisions/D-030-io-battle-only.md) | Accepted | 2026-09-09 | 요약 없는 improved_io A/B 비교 |
| [D-029](decisions/D-029-experiment-defect-recovery.md) | 채택 (Accepted) | 2026-09-09 | 새 실험의 테스트·평가 결함 복구 절차 |
| [D-028](decisions/D-028-summary-max-diagnostic.md) | Accepted | 2026-09-08 | 요약 low/max 고정입력132호출 진단 |
| [D-027](decisions/D-027-low-summary-prompt-reexperiment.md) | Accepted | 2026-09-08 | low 요약 지시 최대3버전과 공유4시간 IO 재실험 |
| [D-026](decisions/D-026-continue-io-experiment.md) | Accepted | 2026-09-08 | 사용자 승인으로 상태 교정 후 IO 비교 재개 |
| [D-025](decisions/D-025-agent-instruction-boundaries.md) | 채택 (Accepted) | 2026-09-08 | 승인 근거와 작업 중단·완료 범위 명료화 |
| [D-024](decisions/D-024-state-summary-thinking.md) | Accepted | 2026-09-08 | 상태 처리 정비와 요약 low/high 72호출 진단 |
| [D-023](decisions/D-023-summary-harness-diagnostics.md) | Accepted | 2026-09-08 | EX-021 독립4조건 요약 harness 진단 및 모델 오류 수집 예외 |
| [D-022](decisions/D-022-resume-io-experiment.md) | Accepted | 2026-09-08 | 단계 재개와 발생 오류 중심 패치 |
| [D-021](decisions/D-021-special-move-diagnostics.md) | Accepted | 2026-09-08 | 현재 기술군과 고위험 기술의 검증·보고 전용 독립 진단 |
| [D-020](decisions/D-020-project-owned-ruination-patch.md) | Accepted | 2026-09-08 | 프로젝트 소유 ruination-v1 패치 및 별도 오프라인 재검증 |
| [D-019](decisions/D-019-improved-io.md) | Accepted | 2026-09-08 | IO 관측·계산·fixed 및 배틀 내 요약 탐색 비교 |
| [D-018](decisions/D-018-upstream-fallback.md) | Accepted | 2026-09-07 | 원본 출력 fallback 별도 조건 |
| [D-017](decisions/D-017-battle-identity-action-candidates.md) | Accepted | 2026-09-07 | 배틀 식별·행동 후보 통합과 단계 검증 |
| [D-016](decisions/D-016-model-concurrency.md) | Accepted | 2026-09-07 | 계정·모델 동시성 및 병렬 운영 측정 |
| [D-015](decisions/D-015-repeat-benchmark-profiles.md) | Accepted | 2026-09-06 | 반복 benchmark profile과 시간 재측정 |
| [D-014](decisions/D-014-increase-cloud-request-timeout.md) | Accepted | 2026-09-07 | Cloud 요청 timeout 조정 |
| [D-013](decisions/D-013-remove-client-output-cap.md) | Accepted | 2026-09-07 | 사용자 지시로 Cloud 출력 상한 최대화 |
| [D-012](decisions/D-012-adopt-pokechamp-baseline-pilot.md) | 채택 (Accepted) | 2026-09-06 | 기준선 도구와 pilot 채택 |
| [D-011](decisions/D-011-default-untimed-showdown-battles.md) | 채택 (Accepted) | 2026-09-04 | PokéChamp 실험의 Showdown battle timer 기본 비활성화 |
| [D-010](decisions/D-010-adopt-pokechamp-battle-observability.md) | 채택 (Accepted) | 2026-09-04 | PokéChamp battle full-fidelity observability 경계 채택 |
| [D-009](decisions/D-009-adapt-always-on-reasoning-output.md) | 채택 (Accepted) | 2026-09-04 | Always-on reasoning model의 compact action output 경계 채택 |
| [D-008](decisions/D-008-fail-closed-cloud-json-actions.md) | D-009로 대체됨 (Superseded) | 2026-09-04 | Ollama Cloud JSON action의 thinking 비활성화와 fail-closed 검증 |
| [D-007](decisions/D-007-adopt-pokechamp-dotenv-credential.md) | 채택 (Accepted) | 2026-09-04 | `.env` credential 정책을 포함한 PokéChamp 연구 환경 경계 채택 |
| [D-006](decisions/D-006-adopt-pokechamp-environment-boundary.md) | D-007로 대체됨 (Superseded) | 2026-09-04 | PokéChamp 연구 환경 및 외부 경계 채택 |
| [D-005](decisions/D-005-adopt-pokechamp-l1-l5-research-goal.md) | 채택 (Accepted) | 2026-09-04 | `pokechamp` 대상 L1-L5 적용 연구 목표 채택 |
| [D-004](decisions/D-004-split-accumulating-records.md) | 채택 (Accepted) | 2026-09-04 | 누적형 기록을 index와 개별 문서로 분리 |
| [D-003](decisions/D-003-korean-primary-documentation.md) | 채택 (Accepted) | 2026-09-04 | 한국어 우선 문서 정책 채택 |
| [D-002](decisions/D-002-reset-research-direction.md) | 채택 (Accepted) | 2026-09-04 | 연구 방향 reset 및 legacy plan 제외 |
| [D-001](decisions/D-001-persistent-project-context-control-plane.md) | 채택 (Accepted) | 2026-09-04 | Persistent project-context control plane 수립 |

개별 ADR의 본문과 status가 해당 결정의 source of truth다. 이 표는 탐색용 summary이며 ADR의
내용을 대신하지 않는다. 표와 ADR이 충돌하면 임의로 해석하지 말고 불일치를 보고한 뒤 함께
정정한다.

## 상태값 (Status Values)

- **제안 (Proposed)** — 검토 중이며 authoritative하지 않다.
- **채택 (Accepted)** — 승인되어 유효하다. 후속 decision이 대체할 때까지 유지된다.
- **대체됨 (Superseded)** — 이름이 명시된 후속 decision으로 대체되었다. History를 위해
  보존한다.
- **거절 (Rejected)** — 검토했으나 채택하지 않았다. 실수로 반복하지 않도록 보존한다.

실제 지원 전환 기간이 있을 때만 **사용 중단 예정 (Deprecated)**을 사용하고 제거 gate를
명시한다. 날짜나 implemented code만으로 decision이 Accepted였다고 판단하지 않는다.

## Decision을 기록할 때

작업이 주요 component boundary, 외부에 보이는 contract, persistent schema, authority/write
rule, experiment methodology, security/licensing constraint 또는 미래 작업이 모르고 되돌릴 수
있는 invariant를 변경할 때 decision을 기록한다. 일상적인 implementation 선택은 exec plan이나
code review에 둔다.

Accepted decision은 아직 유효한 Charter나 Contract를 override할 수 없다. Evidence가
higher-authority 변경을 요구한다면 decision에 근거를 남기고, 필요한 승인을 받은 명시적
higher-authority 수정도 함께 반영해야 한다. 그 전까지 충돌은 unresolved 상태다.

새 항목은 [`decisions/TEMPLATE.md`](decisions/TEMPLATE.md)를 사용한다. Stable하고 단조 증가하는
ID를 부여하고 `decisions/D-XXX-short-title.md`에 저장한 뒤 위 registry 표 안에 한 행을 추가한다. 규칙 전문·예산·실행 결과를 색인에 복사하지 않는다.
대체 관계는 관련된 두 ADR과 registry에 모두 link한다. 대안이나 근거를 만들어내지 말고 기록이
없으면 `기록 없음 (None recorded)`이라고 쓴다.

## Legacy 자료

Repository에는 날짜가 있는 다수의 spec, plan과
[보관된 technical-decision 요약](../AgenticSTS/docs/archive/detailed-technical-decisions.md)이
있다. 이들은 유용한 evidence지만 일괄 import하거나 소급하여 Accepted status를 부여하지
않았다. Repository만으로 승인 상태와 현재성을 일관되게 확정할 수 없기 때문이다.
