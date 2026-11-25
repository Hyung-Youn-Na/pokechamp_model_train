# 방법별 탐색

<!-- generated: scripts/context-catalog build -->

탐색 분류는 처치의 동일성·실제 실행·직접 비교 가능성을 보증하지 않는다. 관련 모델·자료에는 기준선과 참조도 포함하며 실제 조건은 원문을 확인한다.

| 분류 | 기록 수 |
|---|---|
| [입력 / 렌더러](#입력--렌더러) | 5 |
| [입력·표현 / 렌더러](#입력표현--렌더러) | 9 |
| [자료 / MCTS](#자료--mcts) | 1 |
| [자료 / 렌더러](#자료--렌더러) | 1 |
| [자료 / 리플레이 복원](#자료--리플레이-복원) | 5 |
| [자료 / 상대 모델](#자료--상대-모델) | 1 |
| [진단 / 입력](#진단--입력) | 1 |
| [추론 / Choice](#추론--choice) | 25 |
| [추론 / MCTS](#추론--mcts) | 7 |
| [추론 / laya](#추론--laya) | 70 |
| [추론 / vLLM LoRA 선택지 판독](#추론--vllm-lora-선택지-판독) | 3 |
| [추론 / 선봉](#추론--선봉) | 1 |
| [추론 / 요약](#추론--요약) | 97 |
| [추론 / 입력 표현](#추론--입력-표현) | 8 |
| [추론 / 전략 planner](#추론--전략-planner) | 30 |
| [추론 / 행렬 탐색](#추론--행렬-탐색) | 1 |
| [탐색 / MCTS](#탐색--mcts) | 35 |
| [평가 / System1](#평가--system1) | 3 |
| [평가 / foul-play](#평가--foul-play) | 1 |
| [평가 / 고정 대진](#평가--고정-대진) | 132 |
| [평가 / 고정대진32경기](#평가--고정대진32경기) | 2 |
| [평가 / 독립 선택형](#평가--독립-선택형) | 56 |
| [평가 / 래더](#평가--래더) | 12 |
| [평가 / 배틀](#평가--배틀) | 103 |
| [평가 / 배틀32](#평가--배틀32) | 1 |
| [평가 / 서빙 기술 검증](#평가--서빙-기술-검증) | 1 |
| [평가 / 오프라인 QA](#평가--오프라인-qa) | 5 |
| [평가 / 오프라인 진단](#평가--오프라인-진단) | 1 |
| [평가 / 정보 제거](#평가--정보-제거) | 9 |
| [학습 / LoRA](#학습--lora) | 20 |
| [학습 / RLCD](#학습--rlcd) | 7 |
| [학습 / SFT](#학습--sft) | 4 |
| [학습 / System1](#학습--system1) | 3 |
| [학습 / laya](#학습--laya) | 66 |
| [학습 / soft-CE](#학습--soft-ce) | 52 |
| [학습 / 가치망](#학습--가치망) | 3 |
| [학습 / 가치함수](#학습--가치함수) | 7 |
| [학습 / 강화학습](#학습--강화학습) | 3 |
| [학습 / 공동 q](#학습--공동-q) | 1 |
| [학습 / 규칙 데이터 생성](#학습--규칙-데이터-생성) | 3 |
| [학습 / 리플레이 결과 지도](#학습--리플레이-결과-지도) | 2 |
| [학습 / 모방](#학습--모방) | 56 |
| [학습 / 모방 학습](#학습--모방-학습) | 7 |
| [학습 / 본문 근거 역할 주석](#학습--본문-근거-역할-주석) | 2 |
| [학습 / 분류 데이터 생성](#학습--분류-데이터-생성) | 1 |
| [학습 / 상대 모델](#학습--상대-모델) | 3 |
| [학습 / 선택지 교차엔트로피](#학습--선택지-교차엔트로피) | 13 |
| [학습 / 자기대국](#학습--자기대국) | 18 |
| [학습 / 정책 강화학습](#학습--정책-강화학습) | 3 |
| [학습 / 조건부 KO 판정](#학습--조건부-ko-판정) | 2 |
| [학습 / 증류](#학습--증류) | 11 |
| [학습 / 증류·재정렬](#학습--증류재정렬) | 5 |
| [학습 / 학습 데이터 생성](#학습--학습-데이터-생성) | 2 |
| [학습 / 합성 규칙 자료](#학습--합성-규칙-자료) | 2 |
| [학습 / 행동가치](#학습--행동가치) | 10 |

## 입력 / 렌더러

| ID | 제목 | 상태 |
|---|---|---|
| [D-218](../research/policy-learning/decisions/D-218-laya-v13-input-bugfixes.md) | laya 렌더러 v13 입력 결함 수정(폼 스펙·테라 방어 재계산·선공 Roost 지면화·Ivy Cudgel 타입) | Accepted |
| [EP-237](../research/policy-learning/plans/EP-237-laya-observed-public-info-input.md) | laya 입력에 foul-play의 경기 중 추론 전부 반영(렌더러 v12) | Active |
| [EP-240](../research/policy-learning/plans/EP-240-laya-v13-input-bugfixes.md) | laya 렌더러 v13 입력 결함 수정(폼 스펙·테라 방어·선공 Roost·Ivy Cudgel)과 검증 | Completed |
| [EP-241](../research/policy-learning/plans/EP-241-laya-v13-zeroshot-vs-foulplay.md) | laya v13 입력 교정(무재학습 EX-200) 대 foul-play Blim 128경기(시간 제한 없음) | Completed |
| [EX-205](../research/policy-learning/experiments/EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md) | laya v13 입력 교정(무재학습 EX-200) argmax 대 foul-play, Blim 128경기, 시간 제한 없음(CPU) | Completed |

## 입력·표현 / 렌더러

| ID | 제목 | 상태 |
|---|---|---|
| [D-220](../research/policy-learning/decisions/D-220-laya-recovery-matchup-2bv2-and-v14.md) | 상대 회복·흡수 기반 대면 불리 대응: 2-B v2 탐색 개선(CPU 서빙) 및 v14 입력·재학습 병행 | Accepted |
| [D-221](../research/policy-learning/decisions/D-221-laya-main-waya-mcts50k-vphi-v2.md) | Laya 메인 합의형 블런더 가드(방식 A), MCTS 50k 심화, 상성·도구·특성·기술 반영 가치망 V_phi v2 및 렌더러 무효 대면 보완 | Accepted |
| [D-222](../research/policy-learning/decisions/D-222-laya-way-c1-v14-walled-teacher50k.md) | 방식 C-1: v14+walled_duel 입력 및 Hard-Example MCTS 50k + EX-216 V_phi v2 교사 증류 학습 | Accepted |
| [EP-244](../research/policy-learning/plans/EP-244-laya-search-2bv2-and-v14-training.md) | 상대 회복·흡수 대면 대응: 2-B v2 탐색 개선(CPU 서빙) 및 v14 입력·MCTS-5k Q 재학습 병행 (GPU 0·1 전용) | Paused |
| [EP-245](../research/policy-learning/plans/EP-245-laya-main-blunder-veto-mcts50k-vphi-v2.md) | Laya 메인 합의형 블런더 가드(방식 A): 상성·도구·특성·기술 반영 V_phi v2 보강 및 MCTS 50k 결합 (GPU 0·1 전용) | Completed |
| [EP-246](../research/policy-learning/plans/EP-246-laya-way-c1-v14-walled-teacher50k-distill.md) | 방식 C-1: v14+walled_duel 입력 및 Hard-Example MCTS 50k + EX-216 V_phi v2 교사 증류 학습 (GPU 0·1 전용) | Paused |
| [EX-213](../research/policy-learning/experiments/EX-213-laya-v14-data-and-mcts5k-training.md) | v14 회복·흡수 인지 입력 렌더러 데이터 생성 및 MCTS-5k Q 단일 모델 DDP 학습(GPU 0·1) | Stopped |
| [EX-216](../research/policy-learning/experiments/EX-216-laya-state-value-v2-matchup-train.md) | 상성·도구·특성·기술 기계적 매치업 피처 반영 상태가치망 V_phi v2 학습 및 검증 (GPU 0) | Completed |
| [EX-218](../research/policy-learning/experiments/EX-218-laya-way-c1-v14-walled-teacher50k-train.md) | 방식 C-1: v14+walled_duel 데이터·Hard-Example MCTS 50k + EX-216 V_phi v2 교사 타깃 생성 및 DDP 학습 (GPU 0·1) | Stopped |

## 자료 / MCTS

| ID | 제목 | 상태 |
|---|---|---|
| [EX-182](../research/policy-learning/experiments/EX-182-laya-distill-teacher-labels.md) | 사람 학습 국면의 foul-play 탐색 교사 라벨(CPU) | Completed |

## 자료 / 렌더러

| ID | 제목 | 상태 |
|---|---|---|
| [EX-191](../research/policy-learning/experiments/EX-191-laya-v12-data.md) | laya v12 학습 자료(렌더러 v12로 v11 행 재렌더) | Completed |

## 자료 / 리플레이 복원

| ID | 제목 | 상태 |
|---|---|---|
| [D-213](../research/policy-learning/decisions/D-213-laya-fp1-foulplay-input.md) | laya 입력을 foul-play 추적·poke-engine 계산으로 전부 바꾼 렌더러 fp1과 처음부터 전체 학습 | Accepted |
| [EP-234](../research/policy-learning/plans/EP-234-laya-fp1-foulplay-input.md) | laya fp1 렌더러(foul-play 기반 입력) 자료·처음부터 전체 학습·foul-play 배틀 | Active |
| [EX-166](../research/policy-learning/experiments/EX-166-laya-ladder-r1500-data.md) | 최근 래더(레이팅 1500 이상) 리플레이의 v10 학습 자료(CPU) | Completed |
| [EX-170](../research/policy-learning/experiments/EX-170-laya-v11-data.md) | laya 렌더러 v11 학습 자료(판정 재생성·재렌더, 가중·교정 행, CPU) | Running |
| [EX-177](../research/policy-learning/experiments/EX-177-laya-fp1-data.md) | laya fp1 학습 자료(foul-play 추적·표본·poke-engine 재렌더, CPU) | Completed |

## 자료 / 상대 모델

| ID | 제목 | 상태 |
|---|---|---|
| [EX-195](../research/policy-learning/experiments/EX-195-laya-foe-prediction-data.md) | laya 상대 행동 예측 자료와 새 모방 행(v12, CPU) | Completed |

## 진단 / 입력

| ID | 제목 | 상태 |
|---|---|---|
| [EX-190](../research/policy-learning/experiments/EX-190-laya-obsinfo-frequency.md) | foul-play 경기 중 추론이 laya v11 입력을 바꾸는 빈도(EX-184·185 결정, 학습 없음) | Completed |

## 추론 / Choice

| ID | 제목 | 상태 |
|---|---|---|
| [D-028](../research/input-and-memory/decisions/D-028-summary-max-diagnostic.md) | 요약 thinking low/max 독립 진단 | Accepted |
| [D-071](../research/model-evaluation/decisions/D-071-jev-battle.md) | JEV Choice 배틀 연결 | Accepted |
| [D-113](../research/policy-learning/decisions/D-113-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Accepted |
| [D-134](../research/model-evaluation/decisions/D-134-jev9b-single-choice.md) | JEV-9B 단일 Choice 동일32경기 | Accepted |
| [D-160](../research/model-evaluation/decisions/D-160-strategist-first-battle.md) | Strategist 첫 배틀 탐색 평가 | Accepted |
| [EP-011](../research/input-and-memory/plans/EP-011-improved-io.md) | IO 개선 및 병렬 3조건 비교 | Blocked |
| [EP-062](../research/model-evaluation/plans/EP-062-jev-battle.md) | JEV 전용 배틀 입력과 2경기 테스트 | Blocked |
| [EP-115](../research/policy-learning/plans/EP-115-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EP-139](../research/model-evaluation/plans/EP-139-jev9b-single-choice.md) | JEV-9B 단일 Choice 동일32 평가 | Completed |
| [EP-149](../research/planner-executor/plans/EP-149-executor-goal-completion.md) | JEV 계획 목표 충족 확인 지시 | Completed |
| [EP-179](../research/model-evaluation/plans/EP-179-openai-decisions-v6-battle32.md) | OpenAI Decisions v6 상세32경기 | Blocked |
| [EX-024](../research/input-and-memory/experiments/EX-024-low-summary-prompt-reexperiment.md) | low 요약 지시 개선 후 IO 재실험 | Blocked |
| [EX-047](../research/model-evaluation/experiments/EX-047-jev-battle.md) | JEV Choice 소규모 배틀 진단 | Incomplete |
| [EX-051](../research/input-and-memory/experiments/EX-051-jev-v2-battle.md) | JEV 교정 입력 v2 동일 조건2경기 | Completed |
| [EX-071](../research/policy-learning/experiments/EX-071-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EX-082](../research/model-evaluation/experiments/EX-082-jev27b-ex058-reproduction.md) | JEV-27B로 EX-058 개선 입력 동일32 평가 | Blocked |
| [EX-083](../research/model-evaluation/experiments/EX-083-jev27b-four-gpu-continuation.md) | JEV-27B 4GPU 잔여9경기 계승 평가 | Completed |
| [EX-084](../research/model-evaluation/experiments/EX-084-quyet-medium-two-stage.md) | Quyet-Medium 2단계 정책의 EX-083 동일32경기 평가 | Completed |
| [EX-085](../research/model-evaluation/experiments/EX-085-jev9b-single-choice.md) | JEV-9B의 EX-083 설정 기반 동일32경기 평가 | Completed |
| [EX-086](../research/input-and-memory/experiments/EX-086-jev27b-public-memory-v6.md) | JEV-27B 공개 정보 v6 신규32경기 | Blocked |
| [EX-087](../research/input-and-memory/experiments/EX-087-jev9b-public-memory-v6.md) | JEV-9B 공개 정보 v6 신규32경기 | Blocked |
| [EX-088](../research/input-and-memory/experiments/EX-088-jev27b-v6-corrected.md) | 교정 v6 JEV-27B 신규32경기 | Completed |
| [EX-090](../research/input-and-memory/experiments/EX-090-jev9b-no-damage.md) | JEV-9B 피해 예측 제거 신규32경기 | Completed |
| [EX-091](../research/model-evaluation/experiments/EX-091-minicpm5-2b-jev.md) | MiniCPM5-2B-Jev 계산기 포함 신규32경기 | Completed |
| [EX-095](../research/planner-executor/experiments/EX-095-jev35b-nvfp4-sample.md) | JEV-35B-NVFP4 EX-094 동일 대진 샘플 | Blocked |

## 추론 / MCTS

| ID | 제목 | 상태 |
|---|---|---|
| [D-119](../research/fixed-matchup-learning/decisions/D-119-fixed-matchup-mcts.md) | 고정 대진 공개 상태 MCTS 정책 학습 | Accepted |
| [EP-124](../research/fixed-matchup-learning/plans/EP-124-fixed-matchup-mcts.md) | 고정 대진 공개 상태 MCTS 구현 | Completed — 구현·CPU 개발 검증 완료, 실험 미실행 |
| [EP-130](../research/fixed-matchup-learning/plans/EP-130-first-round-model-comparison.md) | 첫라운드 전후 동일 관측 비교 | Completed |
| [EP-235](../research/policy-learning/plans/EP-235-laya-v10rt-search-regret.md) | laya v10rt 결정과 foul-play 탐색의 대조 진단(EX-174 기록, CPU) | Completed |
| [EX-076](../research/fixed-matchup-learning/experiments/EX-076-fixed-matchup-mcts.md) | 고정 A/B 공개 상태 MCTS 정책 학습 | Incomplete — 교정 후 기술 검증/측정 통과, 평가 예산 gate 초과로 학습/test 보류 |
| [EX-079](../research/fixed-matchup-learning/experiments/EX-079-fixed-matchup-stopping.md) | 종료조건 기반 고정 대진 추가 학습 | Completed — 추가학습·시험·감사/뷰어·정리 완료; 주효능 기준 미달 |
| [EX-181](../research/policy-learning/experiments/EX-181-laya-v10rt-foulplay-search-regret.md) | EX-174 v10rt 결정 대 foul-play 탐색(같은 자리·같은 설정) 불일치·값 차이 진단(CPU) | Completed |

## 추론 / laya

| ID | 제목 | 상태 |
|---|---|---|
| [D-184](../research/policy-learning/decisions/D-184-laya-team-generalization.md) | laya 모방 모델의 새 팀 일반화 평가 | Accepted |
| [D-194](../research/policy-learning/decisions/D-194-laya-head-to-head-evaluation.md) | laya 직접 대결 평가(GPU2, EX-120 일정) | Accepted |
| [D-196](../research/policy-learning/decisions/D-196-laya-v2t-corrected-input-battle.md) | laya v2+테라(EX-124)를 재학습 없이 D-195 보정 입력으로 배틀(GPU1) | Accepted |
| [D-197](../research/policy-learning/decisions/D-197-laya-v2t-tera-decision-defence.md) | laya v2+테라(EX-124) fix 입력에서 테라 합산 결정과 테라 방어 문구 배틀(재학습 없음, GPU1) | Accepted |
| [D-199](../research/policy-learning/decisions/D-199-laya-play-teams-abyssal-battle.md) | laya-play 완성 팀(Smogon 샘플·Blim)으로 v5t·v6st·v6ht 대 Abyssal 비교 | Accepted |
| [D-200](../research/policy-learning/decisions/D-200-laya-loop-break-opponent-sets.md) | laya 손해 루프 탈출(학습 가중·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험 | Accepted |
| [D-201](../research/policy-learning/decisions/D-201-laya-engine-judge-v8.md) | laya 실패 표시를 고정 Showdown 엔진 판정기로 바꾼 렌더러 v8 | Accepted |
| [D-202](../research/policy-learning/decisions/D-202-laya-opponent-threat-v9.md) | laya 상대 가정 세트 노력치 보정과 최악 피해 표시(렌더러 v9) | Accepted |
| [D-203](../research/policy-learning/decisions/D-203-laya-human-teams-v7-v8-v9.md) | laya v7t·v8t·v9t를 사람이 짠 완성 팀으로 Abyssal과 비교(GPU0·1·2) | Accepted |
| [D-204](../research/policy-learning/decisions/D-204-laya-renderer-v10-all-info.md) | laya 렌더러 v10: 지금까지의 정보 전부 + lock + 전략 정보, 2,048토큰 | Accepted |
| [D-205](../research/policy-learning/decisions/D-205-laya-switch-read-and-mixing.md) | laya 교체 읽기 상대(정직함 측정)와 교체 갈림길 섞기(재학습 없음) | Accepted |
| [D-206](../research/policy-learning/decisions/D-206-laya-opponent-model-search.md) | laya 상대 모델 + 한 턴 탐색(세트 표본 추정), 재학습 없음 | Accepted |
| [D-211](../research/policy-learning/decisions/D-211-laya-foulplay-opponent.md) | foul-play(탐색 봇)를 laya의 고정 상대로 도입하고 v10rt와 EX-120 일정으로 대전 | Accepted |
| [D-212](../research/policy-learning/decisions/D-212-laya-foulplay-blim-teams.md) | foul-play 대전을 Blim 팀 일정으로 바꾸고 EX-173을 중지 | Accepted |
| [EP-209](../research/policy-learning/plans/EP-209-laya-team-generalization.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EP-217](../research/policy-learning/plans/EP-217-laya-head-to-head-evaluation.md) | laya 직접 대결 평가 하네스와 벤치마크(GPU2) | Completed |
| [EP-219](../research/policy-learning/plans/EP-219-laya-v2t-corrected-input-battle.md) | laya v2+테라 보정 입력 배틀(재학습 없음, GPU1) | Completed |
| [EP-220](../research/policy-learning/plans/EP-220-laya-v2t-tera-decision-defence.md) | laya v2+테라 fix 입력 테라 합산 결정·테라 방어 문구 배틀(재학습 없음, GPU1) | Completed |
| [EP-222](../research/policy-learning/plans/EP-222-laya-play-teams-abyssal-battle.md) | laya-play 완성 팀으로 v5t·v6st·v6ht 대 Abyssal 비교(GPU2) | Completed |
| [EP-223](../research/policy-learning/plans/EP-223-laya-loop-break-opponent-sets.md) | laya 손해 루프 탈출(가중 학습·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험(GPU0~3) | Completed |
| [EP-224](../research/policy-learning/plans/EP-224-laya-engine-judge-v8.md) | laya 엔진 판정기(고정 Showdown 실패 판정)와 렌더러 v8 학습·배틀(GPU1·GPU2) | Completed |
| [EP-225](../research/policy-learning/plans/EP-225-laya-opponent-threat-v9.md) | laya 상대 노력치 보정·최악 피해 표시 렌더러 v9 학습·배틀(GPU3) | Completed |
| [EP-226](../research/policy-learning/plans/EP-226-laya-human-teams-v7-v8-v9.md) | laya v7t·v8t·v9t 사람 팀 비교 배틀(GPU0·1·2) | Stopped |
| [EP-227](../research/policy-learning/plans/EP-227-laya-renderer-v10.md) | laya 렌더러 v10(정보 전부 + lock + 전략, 2,048토큰) 학습과 Abyssal 배틀 | Completed |
| [EP-228](../research/policy-learning/plans/EP-228-laya-switch-read-and-mixing.md) | laya 교체 읽기 상대(정직함 측정)와 v8lt 교체 갈림길 섞기 배틀(재학습 없음, GPU1~3) | Completed |
| [EP-229](../research/policy-learning/plans/EP-229-laya-opponent-model-search.md) | laya 상대 모델 + 한 턴 탐색(세트 표본 추정) | Active |
| [EP-230](../research/policy-learning/plans/EP-230-laya-ladder-r1500-v10.md) | 최근 래더(레이팅 1500 이상) 리플레이 자료와 v10 학습(GPU 4장 DDP), Abyssal 배틀 | Completed |
| [EP-231](../research/policy-learning/plans/EP-231-laya-ladder-postmortem-v11.md) | laya v10rt 공식 래더 패배 원인 추가 분석과 재학습 v11(v11rt·v11rtc) | Active |
| [EP-232](../research/policy-learning/plans/EP-232-laya-foulplay-v10rt.md) | foul-play(탐색 봇) 대 laya v10rt 128경기(CPU; EX-173 EX-120 팀 → 중지, EX-174 Blim 팀) | Completed |
| [EP-233](../research/policy-learning/plans/EP-233-laya-foulplay-v11.md) | foul-play 대 laya v11rt·v11rtc, EX-174 Blim 일정 128경기씩(CPU) | Stopped |
| [EP-235](../research/policy-learning/plans/EP-235-laya-v10rt-search-regret.md) | laya v10rt 결정과 foul-play 탐색의 대조 진단(EX-174 기록, CPU) | Completed |
| [EX-119](../research/policy-learning/experiments/EX-119-laya-compact-imitation-battle32.md) | laya 압축 입력 모방 모델 EX-089 표준 32경기 | Completed |
| [EX-120](../research/policy-learning/experiments/EX-120-laya-team-generalization128.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EX-122](../research/policy-learning/experiments/EX-122-laya-v1-v2-battle256.md) | laya v1·v2 같은 실행 256경기 비교 (EX-120 일정) | Completed |
| [EX-125](../research/policy-learning/experiments/EX-125-laya-v2-tera-battle256.md) | laya v2와 v2+테라 지식 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-127](../research/policy-learning/experiments/EX-127-laya-v2t-v2te-battle256.md) | laya v2+테라와 v2+테라+효과 지식 같은 실행 256경기(GPU2, EX-120 일정) | Completed |
| [EX-129](../research/policy-learning/experiments/EX-129-laya-v2t-v3t-battle256.md) | laya v2+테라와 v3+테라 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-131](../research/policy-learning/experiments/EX-131-laya-v2t-v4t-battle256.md) | laya v2+테라와 v4+테라 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-133](../research/policy-learning/experiments/EX-133-laya-v2t-v2tw-battle256.md) | laya v2+테라와 v2+테라 승패 가중 모방 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-134](../research/policy-learning/experiments/EX-134-laya-head-to-head512.md) | laya v2+테라 대 v2·v1·v2+테라+효과·v3+테라 직접 대결 512경기(GPU2, EX-120 일정) | Completed |
| [EX-135](../research/policy-learning/experiments/EX-135-laya-head-to-head-v2tw-v4t.md) | laya v2+테라 대 승패 가중·v4+테라 직접 대결 256경기(GPU2, EX-120 일정) | Completed |
| [EX-137](../research/policy-learning/experiments/EX-137-laya-v4t-v5t-battle256.md) | laya v4+테라와 v5+테라 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-138](../research/policy-learning/experiments/EX-138-laya-head-to-head-v5t.md) | laya v5+테라 대 v2+테라·v4+테라 직접 대결 256경기(GPU2, EX-120 일정) | Completed |
| [EX-139](../research/policy-learning/experiments/EX-139-laya-v2t-corrected-input-battle256.md) | laya v2+테라(EX-124) 보정 입력 fix·info 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-140](../research/policy-learning/experiments/EX-140-laya-v2t-tera-decision-defence384.md) | laya v2+테라(EX-124) fix 입력 테라 합산 결정(k=1·3)과 테라 방어 문구 384경기(GPU1, EX-120 일정) | Completed |
| [EX-143](../research/policy-learning/experiments/EX-143-laya-v5t-v6st-battle256.md) | laya v5+테라와 v6st (반복 표시) 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-144](../research/policy-learning/experiments/EX-144-laya-v5t-v6ht-battle256.md) | laya v5+테라와 v6ht (긴 기록 2048토큰) 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-145](../research/policy-learning/experiments/EX-145-laya-play-teams-v5t-v6st-v6ht-battle.md) | laya-play 완성 팀 74개로 v5t·v6st·v6ht 대 Abyssal(GPU2) | Completed |
| [EX-147](../research/policy-learning/experiments/EX-147-laya-v6st-v6slt-battle256.md) | laya v6st 대 v6slt(루프 탈출 가중) 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-148](../research/policy-learning/experiments/EX-148-laya-loop-decision-rule.md) | laya 루프 결정 규칙(재학습 없음): v6st·v6ht 정체 루프 기술 제외, EX-120 일정 대 Abyssal | Completed |
| [EX-150](../research/policy-learning/experiments/EX-150-laya-v6st-v7t-battle256.md) | laya v6st 대 v7t(상대 세트 추정) 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-153](../research/policy-learning/experiments/EX-153-laya-v7t-v8t-battle256.md) | laya v7t 대 v8t(엔진 실패 표시) 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-154](../research/policy-learning/experiments/EX-154-laya-head-to-head-v8t-v7t.md) | laya v8t 대 v7t 직접 대결 128경기(GPU2, EX-120 일정) | Stopped |
| [EX-156](../research/policy-learning/experiments/EX-156-laya-v8t-v8lt-battle256.md) | laya v8t 대 v8lt(`likely fails` 표시) 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-158](../research/policy-learning/experiments/EX-158-laya-v7t-v9t-battle256.md) | laya v7t 대 v9t(상대 위협 표시) 같은 실행 256경기(GPU3, EX-120 일정) | Completed |
| [EX-159](../research/policy-learning/experiments/EX-159-laya-human-teams-v7t-v8t-v9t.md) | laya v7t·v8t·v9t 사람이 짠 완성 팀 123개 대 Abyssal(GPU0·1·2) | Stopped |
| [EX-160](../research/policy-learning/experiments/EX-160-laya-human-teams-v8lt.md) | laya v8lt 사람이 짠 완성 팀 123개 대 Abyssal(EX-159 일정, GPU3) | Stopped |
| [EX-162](../research/policy-learning/experiments/EX-162-laya-v7t-v10t-battle256.md) | laya v7t 대 v10t(정보 전부 + lock + 전략) 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-163](../research/policy-learning/experiments/EX-163-laya-v8lt-vs-switch-reader.md) | laya v8lt argmax 대 교체 읽기 상대(abyssal-read), EX-120 일정 128경기(GPU1) | Completed |
| [EX-164](../research/policy-learning/experiments/EX-164-laya-v8lt-switch-mixing.md) | laya v8lt 교체 갈림길 섞기(재학습 없음): 대 Abyssal·대 교체 읽기 상대, 각 128경기(GPU2·GPU3) | Completed |
| [EX-165](../research/policy-learning/experiments/EX-165-laya-opponent-prediction-scenes.md) | laya 상대 시점 예측(세트 표본) 장면 검증: 사람 test 4경기, v8lt(CPU) | Completed |
| [EX-168](../research/policy-learning/experiments/EX-168-laya-v10t-v10rt-battle256.md) | laya v10t 대 v10rt(최근 래더 자료 추가) 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-169](../research/policy-learning/experiments/EX-169-laya-v10rt-ladder-loss-analysis.md) | laya v10rt 공식 래더 83판 패배 원인 추가 분석(CPU, 추론만 GPU) | Completed |
| [EX-173](../research/policy-learning/experiments/EX-173-laya-v10rt-vs-foulplay128.md) | laya v10rt 대 foul-play(MCTS 3초 × 병렬 4), EX-120 일정 128경기(CPU) | Stopped |
| [EX-174](../research/policy-learning/experiments/EX-174-laya-v10rt-vs-foulplay-blim128.md) | laya v10rt 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기(CPU) | Completed |
| [EX-175](../research/policy-learning/experiments/EX-175-laya-v11rt-vs-foulplay-blim128.md) | laya v11rt 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기(CPU) | Stopped |
| [EX-176](../research/policy-learning/experiments/EX-176-laya-v11rtc-vs-foulplay-blim128.md) | laya v11rtc 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기(CPU) | Stopped |
| [EX-179](../research/policy-learning/experiments/EX-179-laya-fp1-vs-foulplay-blim128.md) | laya fp1 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기 | Planned |
| [EX-180](../research/policy-learning/experiments/EX-180-laya-fp1e2-vs-foulplay-blim128.md) | laya fp1 epoch-2 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기(CPU) | Running |
| [EX-181](../research/policy-learning/experiments/EX-181-laya-v10rt-foulplay-search-regret.md) | EX-174 v10rt 결정 대 foul-play 탐색(같은 자리·같은 설정) 불일치·값 차이 진단(CPU) | Completed |

## 추론 / vLLM LoRA 선택지 판독

| ID | 제목 | 상태 |
|---|---|---|
| [EP-190](../research/rule-learning/plans/EP-190-jevk5-vllm-serving-check.md) | JevK5 추가 LoRA vLLM 서빙 확인 | Completed |
| [EP-191](../research/rule-learning/plans/EP-191-jevk5-ruleqa-battle32.md) | 학습 JevK5 LoRA 실전32 실행 | Completed |
| [EX-114](../research/rule-learning/experiments/EX-114-jevk5-ruleqa-battle32.md) | 학습 JevK5 선택형 LoRA 실전32 | Completed |

## 추론 / 선봉

| ID | 제목 | 상태 |
|---|---|---|
| [EP-242](../research/policy-learning/plans/EP-242-laya-lead-matchup-2b.md) | laya 2b 선봉 선택 모듈(`lead_policy.py`, 상대 선봉 추정 × 6×6 매치업 기대값 + 모델 사전확률 재가중) 구현 | Completed |

## 추론 / 요약

| ID | 제목 | 상태 |
|---|---|---|
| [D-004](../shared/governance/decisions/D-004-split-accumulating-records.md) | 누적형 기록을 index와 개별 문서로 분리 | 채택 (Accepted) |
| [D-019](../research/input-and-memory/decisions/D-019-improved-io.md) | IO 관측·계산·고정 정책 및 배틀 내 요약 비교 | Accepted |
| [D-022](../research/input-and-memory/decisions/D-022-resume-io-experiment.md) | EX-017 재실험 및 발생 오류 중심 패치 | Accepted |
| [D-023](../research/input-and-memory/decisions/D-023-summary-harness-diagnostics.md) | 요약 오류의 harness 기여도 진단 | Accepted |
| [D-024](../research/input-and-memory/decisions/D-024-state-summary-thinking.md) | 상태 처리 정비와 요약 thinking 비교 | Accepted |
| [D-025](../shared/governance/decisions/D-025-agent-instruction-boundaries.md) | 승인 근거와 작업 중단·완료 범위 명료화 | 채택 (Accepted) |
| [D-026](../research/input-and-memory/decisions/D-026-continue-io-experiment.md) | EX-017 계열 IO 실험의 사용자 승인 재개 | Accepted |
| [D-027](../research/input-and-memory/decisions/D-027-low-summary-prompt-reexperiment.md) | low 요약 지시 개선과 IO 재실험 | Accepted |
| [D-028](../research/input-and-memory/decisions/D-028-summary-max-diagnostic.md) | 요약 thinking low/max 독립 진단 | Accepted |
| [D-030](../research/input-and-memory/decisions/D-030-io-battle-only.md) | 요약을 제외한 improved_io A/B 비교 | Accepted |
| [D-031](../research/input-and-memory/decisions/D-031-battle-field-guide.md) | B 행동 입력 필드 설명서 | Accepted |
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
| [D-063](../research/input-and-memory/decisions/D-063-intermediate-research-objectives.md) | 입력 정보·이력·요약의 중간 연구 목표 채택 | Accepted |
| [D-071](../research/model-evaluation/decisions/D-071-jev-battle.md) | JEV Choice 배틀 연결 | Accepted |
| [D-094](../research/input-and-memory/decisions/D-094-jev-improved32.md) | 개선 JEV 입력 동일32경기 | Accepted |
| [D-096](../research/policy-learning/decisions/D-096-pokemon-training-objective.md) | 세 RLCD 환경을 활용한 포켓몬 전용 학습 당면 목표 채택 | Accepted |
| [D-167](../research/input-and-memory/decisions/D-167-candidate-matchup-summary.md) | 후보별 현재 상대 적용결과 보강 | Accepted |
| [D-168](../research/input-and-memory/decisions/D-168-openai-candidate-matchup-battle.md) | 후보별 상성 요약 OpenAI 동일32경기 | Accepted |
| [EP-011](../research/input-and-memory/plans/EP-011-improved-io.md) | IO 개선 및 병렬 3조건 비교 | Blocked |
| [EP-012](../research/input-and-memory/plans/EP-012-summary-harness-diagnostics.md) | 요약 harness 기여도 진단 | Blocked |
| [EP-013](../research/input-and-memory/plans/EP-013-state-summary-thinking.md) | 상태 처리 정비와 요약 thinking 비교 | Blocked |
| [EP-014](../shared/governance/plans/EP-014-agent-instruction-maintenance.md) | 승인·중단 지시와 현재 상태 정합화 | Completed |
| [EP-015](../research/input-and-memory/plans/EP-015-summary-max-diagnostic.md) | 요약 thinking low/max 진단 | Blocked — 입력·평가 기준 불일치로 전체 무효, 진단 미완료 |
| [EP-016](../research/input-and-memory/plans/EP-016-input-summary-documentation.md) | 현재 입력·요약 구조 문서화 | Completed |
| [EP-017](../shared/governance/plans/EP-017-experiment-defect-recovery.md) | 테스트·평가 결함 복구 절차 문서화 | Completed |
| [EP-018](../research/input-and-memory/plans/EP-018-io-battle-only.md) | 요약 없는 improved_io A/B 비교 | Blocked — 구현·검증·중단 보고 완료, Cloud gate 미충족으로 비교 미완료 |
| [EP-019](../research/input-and-memory/plans/EP-019-battle-field-guide.md) | B 행동 입력 필드 설명서 | Completed |
| [EP-020](../research/input-and-memory/plans/EP-020-battle-guide-live.md) | 필드 설명서 실제 Cloud 병렬 배틀 | Blocked — 구현·로컬 검증·중단 보고 완료, Cloud 기술 gate 실패로 실제 비교 미완료 |
| [EP-021](../research/input-and-memory/plans/EP-021-battle-guide-direct32.md) | 사전 검증 생략 32판과 오류 턴 표시 | Completed |
| [EP-022](../research/input-and-memory/plans/EP-022-calculator-entry-calcfix32.md) | 계산기 등장 특성 교정 및 동일32판 | Completed — 사용자 중단 대안 포함 완료; 성능 비교 미완료 |
| [EP-024](../research/input-and-memory/plans/EP-024-calculator-inputfix32.md) | 교정 입력·계산기 동일 조건 A/B32판 | Completed |
| [EP-026](../research/input-and-memory/plans/EP-026-battle-guide-movefix32.md) | 수정 완료본 A/B32판 본 실험 | Completed — 승인된 중단 포함 작업 완료, 성능 비교 미완료 |
| [EP-027](../research/input-and-memory/plans/EP-027-external-memory-repeat32.md) | 외부 메모리 장애 후 동일 조건32판 재실험 | Completed |
| [EP-028](../research/input-and-memory/plans/EP-028-smogon-diagnostic-design.md) | Smogon 기반 원본 A 진단 평가 준비 | Completed — 평가 준비 구현·로컬 검증 완료, 대전 미실행 |
| [EP-029](../research/input-and-memory/plans/EP-029-a-diagnostic64.md) | Smogon 원본 A64 진단 실행 | Completed |
| [EP-030](../research/input-and-memory/plans/EP-030-ab-head-to-head32.md) | 원본 A 대 변경 구성 B 직접 대결32경기 | Blocked — 계산 결함 중단, 직접비교 미완료 |
| [EP-032](../research/input-and-memory/plans/EP-032-ab-head-to-head32-protectfix.md) | Protect 수정본 A/B 직접대결32 | Blocked |
| [EP-034](../research/input-and-memory/plans/EP-034-b-prompt-optimization.md) | B 판단 정보 보존형 프롬프트 최적화 | Completed |
| [EP-035](../research/input-and-memory/plans/EP-035-ab-head-to-head32-b2.md) | B2 적용 A/B 직접대결32 | Blocked |
| [EP-038](../shared/governance/plans/EP-038-io-explanation-review-opt-in.md) | 기본 IO 테스트 설명 오류 기입 명시 선택 | Completed |
| [EP-052](../research/input-and-memory/plans/EP-052-intermediate-research-objectives.md) | 입력 정보·메모리 설계 중간 연구 목표 문서화 | Completed |
| [EP-058](../research/input-and-memory/plans/EP-058-official-async.md) | 공식 관측 비동기 처리 교정 | Completed |
| [EP-069](../shared/viewers/plans/EP-069-researcher-viewer.md) | 실험자용 JEV 뷰어 가독성 | Completed |
| [EP-072](../shared/viewers/plans/EP-072-viewer-navigation-hp.md) | 뷰어 단축키·상대 HP 비율 표시 | Completed |
| [EP-105](../shared/viewers/plans/EP-105-viewer-action-names.md) | 뷰어 결정의 실제 기술·포켓몬 이름 표시 | Completed |
| [EP-140](../research/input-and-memory/plans/EP-140-jev-public-memory-v6.md) | 공개 정보 v6·턴 로그 뷰어·JEV 27B/9B 재평가 | Blocked |
| [EP-141](../research/input-and-memory/plans/EP-141-jev-v6-corrected-evaluation.md) | 교정 v6의27B/9B 신규64평가 | Completed |
| [EP-142](../shared/viewers/plans/EP-142-jev-damage-viewer.md) | EX-088·089 Damage-calc 시나리오 탭 | Completed |
| [EP-169](../research/rule-learning/plans/EP-169-showdown-ruleqa.md) | Showdown 규칙 Q&A·State 데이터셋 v1 | Completed |
| [EP-182](../research/input-and-memory/plans/EP-182-candidate-matchup-summary.md) | 후보별 현재 대면 상성·효과 요약 | Completed |
| [EP-183](../research/input-and-memory/plans/EP-183-openai-candidate-matchup-battle.md) | 후보별 상성 요약 OpenAI 32경기 | Blocked |
| [EX-017](../research/input-and-memory/experiments/EX-017-improved-io-offline.md) | 개선 IO 오프라인 검증 | Stopped |
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
| [EX-047](../research/model-evaluation/experiments/EX-047-jev-battle.md) | JEV Choice 소규모 배틀 진단 | Incomplete |
| [EX-051](../research/input-and-memory/experiments/EX-051-jev-v2-battle.md) | JEV 교정 입력 v2 동일 조건2경기 | Completed |
| [EX-052](../research/model-evaluation/experiments/EX-052-jev-abyssal32.md) | JEV 대 Abyssal 32경기 | Completed |
| [EX-053](../research/input-and-memory/experiments/EX-053-jev-v3-abyssal32.md) | JEV 대 Abyssal 32경기 | Incomplete |
| [EX-054](../research/input-and-memory/experiments/EX-054-jev-v3-retry32.md) | 재시도3회 적용 JEV v3 동일32경기 | Incomplete |
| [EX-058](../research/input-and-memory/experiments/EX-058-jev-improved32.md) | 개선 JEV 입력 동일32경기 | Completed |
| [EX-059](../research/input-and-memory/experiments/EX-059-jev-compact32.md) | 자기 벤치 축약 JEV 입력 동일32경기 | Completed |
| [EX-060](../research/action-value/experiments/EX-060-single-battle-branch-rollouts.md) | EX-058 battle-19 분기 데이터 추출 | Completed |
| [EX-086](../research/input-and-memory/experiments/EX-086-jev27b-public-memory-v6.md) | JEV-27B 공개 정보 v6 신규32경기 | Blocked |
| [EX-109](../research/model-evaluation/experiments/EX-109-openai-decisions-v6-battle32.md) | OpenAI Decisions v6 상세32경기 | Stopped |
| [EX-111](../research/model-evaluation/experiments/EX-111-jevk5-v6-battle32.md) | JevK5-9B v6 상세32경기 | Completed |
| [EX-112](../research/input-and-memory/experiments/EX-112-openai-candidate-matchup-battle.md) | 후보별 현재 대면 요약 gpt-6-luna 32경기 | Stopped |

## 추론 / 입력 표현

| ID | 제목 | 상태 |
|---|---|---|
| [D-179](../research/input-and-memory/decisions/D-179-candidate-action-v7.md) | 후보 중심 v7와 응답 복구 탐색 실험 | Accepted |
| [D-181](../research/input-and-memory/decisions/D-181-v7-survival-switch-cost.md) | v7 생존 판단과 교체 기회비용 지침 | Accepted |
| [D-182](../research/input-and-memory/decisions/D-182-v7-survival-battle32.md) | 생존·교체 비용 v7 GPT-6 Luna 32경기 | Accepted |
| [EP-202](../research/input-and-memory/plans/EP-202-candidate-action-v7.md) | 후보 중심 v7와 GPT-6 Luna 32경기 | Completed |
| [EP-205](../research/input-and-memory/plans/EP-205-v7-survival-switch-cost.md) | v7 생존 판단과 교체 비용 지시문 개정 | Completed |
| [EP-206](../research/input-and-memory/plans/EP-206-v7-survival-battle32.md) | 개정 v7 GPT-6 Luna 32경기 시작·수집 | Blocked |
| [EX-115](../research/input-and-memory/experiments/EX-115-candidate-action-v7.md) | 후보 중심 v7 GPT-6 Luna 32경기 | Completed |
| [EX-117](../research/input-and-memory/experiments/EX-117-v7-survival-battle32.md) | 생존·교체 비용 v7 GPT-6 Luna 32경기 | Stopped |

## 추론 / 전략 planner

| ID | 제목 | 상태 |
|---|---|---|
| [D-139](../research/planner-executor/decisions/D-139-jev-planner-environment.md) | GLM planner–JEV 수행 모델 실험 환경 | Accepted |
| [D-140](../research/planner-executor/decisions/D-140-planner-role-resource-guide.md) | Planner 역할·승리 경로·자원 관리 안내 | Accepted |
| [D-142](../research/planner-executor/decisions/D-142-planner-first-battle-sample.md) | EX-088 첫 대진의 planner–JEV 샘플 실행 | Accepted |
| [D-143](../research/planner-executor/decisions/D-143-executor-goal-completion.md) | JEV의 계획 목표 충족 여부 확인 | Accepted |
| [D-145](../research/planner-executor/decisions/D-145-goal-completion-sample.md) | 바뀐 수행 프롬프트의 실제 샘플1경기 | Accepted |
| [D-146](../research/planner-executor/decisions/D-146-planner-json-retries.md) | GLM JSON 구문 오류 최대5회 재시도·새 샘플 | Accepted |
| [D-147](../research/planner-executor/decisions/D-147-planner-unlimited-disk.md) | GLM·JEV 향후 실행의 디스크 용량 상한 해제 | Accepted |
| [D-150](../research/planner-executor/decisions/D-150-planner-format-retries-temperature-zero.md) | GLM 응답 형식 재시도·기본 temperature0 | Accepted |
| [D-151](../research/planner-executor/decisions/D-151-planner-high-effort-sample.md) | GLM high 추론 강도 동일 대진 샘플 | Accepted |
| [D-152](../research/planner-executor/decisions/D-152-planner-unlimited-time-max-output.md) | 경기/전체 시간 상한 해제·GLM 최대 출력 새1경기 | Accepted |
| [D-153](../research/planner-executor/decisions/D-153-glm53-low-sample.md) | GLM-5.3 low 동일 대진 새1경기 | Accepted |
| [D-155](../research/planner-executor/decisions/D-155-matchup-events-high.md) | 매치업 사건 GLM high 동일 대진 | Accepted |
| [EP-145](../research/planner-executor/plans/EP-145-jev-planner-environment.md) | GLM planner–JEV 실험 설정 환경 | Completed |
| [EP-146](../research/planner-executor/plans/EP-146-planner-role-resource-guide.md) | Planner 역할·승리 경로·자원 안내 | Completed |
| [EP-148](../research/planner-executor/plans/EP-148-planner-first-battle-sample.md) | GLM planner–JEV 첫 실제 샘플 | Completed |
| [EP-149](../research/planner-executor/plans/EP-149-executor-goal-completion.md) | JEV 계획 목표 충족 확인 지시 | Completed |
| [EP-151](../research/planner-executor/plans/EP-151-planner-goal-completion-sample.md) | 변경 수행 프롬프트 샘플1경기 | Blocked |
| [EP-152](../research/planner-executor/plans/EP-152-planner-json-retry-sample.md) | GLM JSON 구문 재시도·샘플1경기 | Completed |
| [EP-153](../research/planner-executor/plans/EP-153-planner-unlimited-disk.md) | GLM·JEV 디스크 상한 해제 | Completed |
| [EP-156](../research/planner-executor/plans/EP-156-planner-format-temperature-zero.md) | GLM 형식 재시도·temperature0 실제1경기 | Completed |
| [EP-157](../research/planner-executor/plans/EP-157-planner-high-effort-sample.md) | GLM high 추론 강도 실제1경기 | Blocked |
| [EP-158](../research/planner-executor/plans/EP-158-planner-unlimited-time-max-output.md) | 시간 상한 없는 GLM 최대 출력 실제1경기 | Completed |
| [EX-092](../research/planner-executor/experiments/EX-092-planner-first-battle-sample.md) | EX-088 첫 대진의 GLM planner–JEV 샘플 | Completed |
| [EX-093](../research/planner-executor/experiments/EX-093-planner-goal-completion-sample.md) | 목표 충족 확인 지시문 적용 샘플1경기 | Blocked |
| [EX-094](../research/planner-executor/experiments/EX-094-planner-json-retry-sample.md) | GLM JSON 구문 재시도 적용 샘플 | Completed |
| [EX-097](../research/planner-executor/experiments/EX-097-planner-format-temperature-zero.md) | GLM 형식 재시도·temperature0 NVFP4 샘플1경기 | Completed |
| [EX-098](../research/planner-executor/experiments/EX-098-planner-high-effort-sample.md) | GLM high 추론 강도 NVFP4 동일 대진1경기 | Blocked |
| [EX-099](../research/planner-executor/experiments/EX-099-planner-unlimited-time-max-output.md) | 시간 상한 없는 GLM 최대 출력 NVFP4 샘플1경기 | Completed |
| [EX-100](../research/planner-executor/experiments/EX-100-glm53-low-sample.md) | GLM-5.3 low 동일 대진 NVFP4 샘플1경기 | Completed |
| [EX-102](../research/planner-executor/experiments/EX-102-matchup-events-high.md) | 매치업 사건 기반 GLM high 동일 대진 | Completed |

## 추론 / 행렬 탐색

| ID | 제목 | 상태 |
|---|---|---|
| [EX-080](../research/fixed-matchup-learning/experiments/EX-080-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Completed — 시도 3 학습(round40 둔화 종료)·선택(round36)·잠긴 test·감사/뷰어/봉인·정리 완료; 주효능 미입증 (시도 1·2는 도구 결함으로 학습 전 중단·보존) |

## 탐색 / MCTS

| ID | 제목 | 상태 |
|---|---|---|
| [D-219](../research/policy-learning/decisions/D-219-laya-multiturn-search-and-value.md) | 1턴 시야·정적 가치 편향 극복을 위한 다중턴 탐색(2-A)·신경망 상태가치(2-B)·경량 MCTS-Q 재정렬 학습(1-B) (GPU 0·1 전용) | Accepted |
| [D-220](../research/policy-learning/decisions/D-220-laya-recovery-matchup-2bv2-and-v14.md) | 상대 회복·흡수 기반 대면 불리 대응: 2-B v2 탐색 개선(CPU 서빙) 및 v14 입력·재학습 병행 | Accepted |
| [D-221](../research/policy-learning/decisions/D-221-laya-main-waya-mcts50k-vphi-v2.md) | Laya 메인 합의형 블런더 가드(방식 A), MCTS 50k 심화, 상성·도구·특성·기술 반영 가치망 V_phi v2 및 렌더러 무효 대면 보완 | Accepted |
| [D-222](../research/policy-learning/decisions/D-222-laya-way-c1-v14-walled-teacher50k.md) | 방식 C-1: v14+walled_duel 입력 및 Hard-Example MCTS 50k + EX-216 V_phi v2 교사 증류 학습 | Accepted |
| [D-223](../research/policy-learning/decisions/D-223-vphi-v3-future-horizon-and-multiturn-search.md) | 미래 영향력 반영 상태가치망 V_phi v3 및 다수 턴 2-ply 탐색 · Way A v2 가드레일 | Accepted |
| [D-224](../research/policy-learning/decisions/D-224-batch-b-waya-v2-ladder-wayc1-clean-wayb.md) | 배치 B 병행 실행: EX-223 방식 A v2 공식 래더(EX-224) + 정화 교사 방식 C-1(EX-225) → 프롬프트 도구 주입 방식 B(EX-226) DDP 자동 연쇄 | Accepted |
| [D-225](../research/policy-learning/decisions/D-225-ep249-ex226-wayb-ex225-c1clean-blim128-ladder.md) | EP-249: EX-226(방식 B) · EX-225(방식 C-1 정화판) Blim 128 병렬 배틀 평가 및 EX-226 공식 래더 병행 | Accepted |
| [D-226](../research/policy-learning/decisions/D-226-ep250-ex226-wayb-offense-ladder.md) | EP-250: EX-226 방식 B Offense 전용 공식 Showdown 래더 대전 (13:30 KST까지) | Accepted |
| [EP-243](../research/policy-learning/plans/EP-243-laya-multiturn-search-value-distill.md) | 다중턴 온라인 탐색(2-A)·신경망 상태가치(2-B)·경량 MCTS-Q 재정렬 학습(1-B) (GPU 0·1 전용) | Active |
| [EP-244](../research/policy-learning/plans/EP-244-laya-search-2bv2-and-v14-training.md) | 상대 회복·흡수 대면 대응: 2-B v2 탐색 개선(CPU 서빙) 및 v14 입력·MCTS-5k Q 재학습 병행 (GPU 0·1 전용) | Paused |
| [EP-245](../research/policy-learning/plans/EP-245-laya-main-blunder-veto-mcts50k-vphi-v2.md) | Laya 메인 합의형 블런더 가드(방식 A): 상성·도구·특성·기술 반영 V_phi v2 보강 및 MCTS 50k 결합 (GPU 0·1 전용) | Completed |
| [EP-246](../research/policy-learning/plans/EP-246-laya-way-c1-v14-walled-teacher50k-distill.md) | 방식 C-1: v14+walled_duel 입력 및 Hard-Example MCTS 50k + EX-216 V_phi v2 교사 증류 학습 (GPU 0·1 전용) | Paused |
| [EP-247](../research/policy-learning/plans/EP-247-vphi-v3-future-horizon-and-multiturn-search.md) | 미래 영향력 반영 가치함수 V_phi v3 및 2-ply 다수 턴 탐색 · Way A v2 검증 (GPU 0·1 전용) | Completed |
| [EP-248](../research/policy-learning/plans/EP-248-batch-b-waya-v2-ladder-wayc1-clean-wayb.md) | 배치 B: EX-223 방식 A v2 공식 래더 병행 + 정화 방식 C-1 → 방식 B GPU 0·1 DDP 자동 연쇄 | Completed |
| [EP-249](../research/policy-learning/plans/EP-249-ex226-wayb-and-ex225-c1clean-blim128-and-ladder.md) | EX-226(방식 B) · EX-225(방식 C-1 정화판) Blim 128 병렬 배틀 평가 및 EX-226 공식 래더 병행 | Completed |
| [EP-250](../research/policy-learning/plans/EP-250-ex226-wayb-offense-ladder.md) | EX-226 방식 B Offense 전용 공식 Showdown gen9ou 래더 (13:30 KST까지) | Active |
| [EX-206](../research/policy-learning/experiments/EX-206-laya-search-2a-vs-foulplay-unlimited.md) | 2-A 온라인 다중턴 탐색(EX-200 + v13 + GPU 0 서빙 + MCTS 5k 사전확률 융합) 대 foul-play, Blim 128경기(시간 제한 없음) | Completed |
| [EX-208](../research/policy-learning/experiments/EX-208-laya-search-2b-vs-foulplay-unlimited.md) | 2-B 온라인 다중턴 탐색 + 신경망 상태가치 V_phi 결합 대 foul-play, Blim 128경기(시간 제한 없음) | Completed |
| [EX-209](../research/policy-learning/experiments/EX-209-laya-mcts5k-q-rerank-1b-train.md) | 1-B 오프라인 경량 MCTS-5k 루트 Q 후보 재정렬 타깃 생성 및 v13 단일 모델 학습(GPU 0·1) | Completed |
| [EX-211](../research/policy-learning/experiments/EX-211-laya-search2b-ladder.md) | 2-B 온라인 다중턴 탐색 + 상태가치 V_phi(EX-208) 공식 Showdown gen9ou 래더 대전(GPU 1 서빙, 2026-11-24 13:00 KST까지) | Stopped |
| [EX-212](../research/policy-learning/experiments/EX-212-laya-search-2bv2-vs-foulplay-unlimited.md) | 2-B v2 탐색 개선(foe PP 파싱 수정·스케일 정규화·duel lose 완화·Taunt 흡수 보정, CPU 서빙) 대 foul-play, Blim 128경기 | Stopped |
| [EX-214](../research/policy-learning/experiments/EX-214-laya-v14-search2bv2-vs-foulplay-unlimited.md) | v14 학습 모델(EX-213) + 2-B v2 온라인 탐색 결합 대 foul-play, Blim 128경기 | Planned |
| [EX-215](../research/policy-learning/experiments/EX-215-laya-search2bv2-ladder.md) | 2-B v2 탐색 개선(EX-212 동일 설정, CPU 서빙) 공식 Showdown gen9ou 래더 대전(2026-11-24 13:00 KST까지) | Stopped |
| [EX-217](../research/policy-learning/experiments/EX-217-laya-main-waya-mcts50k-vphiv2-vs-foulplay.md) | 방식 A(Laya 메인 합의형 블런더 가드 + MCTS 50k + V_phi v2 + 렌더러 무효 대면 수정) 대 foul-play, Blim 128경기 | Completed |
| [EX-218](../research/policy-learning/experiments/EX-218-laya-way-c1-v14-walled-teacher50k-train.md) | 방식 C-1: v14+walled_duel 데이터·Hard-Example MCTS 50k + EX-216 V_phi v2 교사 타깃 생성 및 DDP 학습 (GPU 0·1) | Stopped |
| [EX-220](../research/policy-learning/experiments/EX-220-laya-waya-mcts50k-ladder.md) | EX-217 방식 A(Laya 메인 + MCTS 50k + EX-216 V_phi v2 + walled_duel, CPU 서빙) 공식 Showdown gen9ou 래더 대전 (EX-218 학습 완료까지) | Stopped |
| [EX-222](../research/policy-learning/experiments/EX-222-multiturn-2ply-waya-v2-ab.md) | 다수 턴 2-ply Top-K 탐색기 + Way A v2 가드레일 오프라인 A/B 진단 | Completed |
| [EX-223](../research/policy-learning/experiments/EX-223-laya-waya-v2-vphiv3-2ply-vs-foulplay.md) | 방식 A v2(미래인지 V_phi v3 + 2-ply Top-K + MCTS 50k + 회복/Protect 가드레일) 대 foul-play, Blim 128경기 | Completed |
| [EX-224](../research/policy-learning/experiments/EX-224-laya-waya-v2-vphiv3-2ply-ladder.md) | EX-223 방식 A v2(V_phi v3 + 2-ply + MCTS 50k + 회복/Protect 가드레일, CPU 서빙) 공식 Showdown gen9ou 래더 대전 | Stopped |
| [EX-225](../research/policy-learning/experiments/EX-225-laya-way-c1-clean-vphiv3-2ply-train.md) | 방식 C-1 오염 제거판: EX-221 V_phi v3 + 2-ply 정화 교사 증류 학습 (GPU 0·1 DDP) | Completed |
| [EX-226](../research/policy-learning/experiments/EX-226-laya-way-b-tool-inject-train.md) | 방식 B: calc-duel-free + MCTS50k/V_phi v3 5단계 matchup & eval 프롬프트 주입 + 35% Tool Dropout + 인간 앵커 보존 학습 (GPU 0·1 DDP) | Completed |
| [EX-227](../research/policy-learning/experiments/EX-227-laya-ex226-wayb-vs-foulplay-blim128.md) | EX-226 방식 B(calc-duel-free + 5단계 matchup & eval 프롬프트 주입, Laya 단독 최종결정) 대 foul-play Blim 128 (GPU 0) | Completed |
| [EX-229](../research/policy-learning/experiments/EX-229-laya-ex225-waya-v2-noduel-vs-foulplay-blim128.md) | EX-225 방식 C-1 정화판 + Way A v2(calc-duel-free + MCTS 50k + V_phi v3 2-ply) 대 foul-play Blim 128 (GPU 1) | Completed |
| [EX-230](../research/policy-learning/experiments/EX-230-laya-ex226-wayb-ladder.md) | EX-226 방식 B(calc-duel-free + 5단계 matchup & eval 프롬프트 주입, CPU 서빙) 공식 Showdown gen9ou 래더 대전 | Completed |
| [EX-231](../research/policy-learning/experiments/EX-231-laya-ex226-wayb-offense-ladder.md) | EX-226 방식 B Offense 전용(4팀 순환, GPU 0 서빙) 공식 Showdown gen9ou 래더 대전 | Running |

## 평가 / System1

| ID | 제목 | 상태 |
|---|---|---|
| [D-186](../research/rule-learning/decisions/D-186-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Accepted |
| [EP-211](../research/rule-learning/plans/EP-211-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Completed |
| [EX-123](../research/rule-learning/experiments/EX-123-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Completed |

## 평가 / foul-play

| ID | 제목 | 상태 |
|---|---|---|
| [EX-223](../research/policy-learning/experiments/EX-223-laya-waya-v2-vphiv3-2ply-vs-foulplay.md) | 방식 A v2(미래인지 V_phi v3 + 2-ply Top-K + MCTS 50k + 회복/Protect 가드레일) 대 foul-play, Blim 128경기 | Completed |

## 평가 / 고정 대진

| ID | 제목 | 상태 |
|---|---|---|
| [D-034](../research/input-and-memory/decisions/D-034-calculator-entry-calcfix32.md) | 계산기 등장 특성 교정 및 동일32판 | Accepted |
| [D-036](../research/input-and-memory/decisions/D-036-calculator-inputfix32.md) | 교정 입력·계산기 동일32판 | Accepted |
| [D-083](../research/input-and-memory/decisions/D-083-jev-v3-abyssal32.md) | JEV v3 동일32경기와 v2 전후 비교 | Accepted |
| [D-088](../research/input-and-memory/decisions/D-088-jev-direct32.md) | EX-056 사전 검증 생략 동일32경기 | Accepted |
| [D-094](../research/input-and-memory/decisions/D-094-jev-improved32.md) | 개선 JEV 입력 동일32경기 | Accepted |
| [D-095](../research/input-and-memory/decisions/D-095-jev-compact32.md) | 자기 벤치 축약 동일32경기 | Accepted |
| [D-110](../research/model-evaluation/decisions/D-110-kev-test-battles.md) | 기존 test 대진의 Kev 본 배틀 | Accepted |
| [D-115](../research/policy-learning/decisions/D-115-abyssal-first-objective.md) | Abyssal 상대 효율적 승리를 당면 단기 목표로 채택 | Accepted |
| [D-119](../research/fixed-matchup-learning/decisions/D-119-fixed-matchup-mcts.md) | 고정 대진 공개 상태 MCTS 정책 학습 | Accepted |
| [D-120](../research/fixed-matchup-learning/decisions/D-120-fixed-matchup-run.md) | 고정 대진 GPU 학습·실험 실행 | Accepted |
| [D-122](../research/fixed-matchup-learning/decisions/D-122-fixed-matchup-day.md) | 하루 내 예상 시 고정 대진 실행 | Accepted |
| [D-127](../research/fixed-matchup-learning/decisions/D-127-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Accepted |
| [D-130](../research/model-evaluation/decisions/D-130-jev27b-ex058-reproduction.md) | JEV-27B 공개 가중치로 개선 입력 동일32 평가 | Accepted |
| [D-133](../research/model-evaluation/decisions/D-133-quyet-medium-two-stage.md) | Quyet-Medium 2단계 정책 동일32경기 | Accepted |
| [D-134](../research/model-evaluation/decisions/D-134-jev9b-single-choice.md) | JEV-9B 단일 Choice 동일32경기 | Accepted |
| [D-137](../research/input-and-memory/decisions/D-137-jev9b-no-damage.md) | JEV-9B 피해 예측 제거 평가 | Accepted |
| [D-138](../research/model-evaluation/decisions/D-138-minicpm5-2b-jev.md) | MiniCPM5-2B-Jev 계산기 포함 평가 | Accepted |
| [D-168](../research/input-and-memory/decisions/D-168-openai-candidate-matchup-battle.md) | 후보별 상성 요약 OpenAI 동일32경기 | Accepted |
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
| [D-198](../research/policy-learning/decisions/D-198-laya-past-turn-input-v6.md) | laya 과거 턴 입력 두 가지(v6s 반복 표시·v6h 긴 기록 2048토큰) 동시 학습과 배틀 | Accepted |
| [D-199](../research/policy-learning/decisions/D-199-laya-play-teams-abyssal-battle.md) | laya-play 완성 팀(Smogon 샘플·Blim)으로 v5t·v6st·v6ht 대 Abyssal 비교 | Accepted |
| [D-200](../research/policy-learning/decisions/D-200-laya-loop-break-opponent-sets.md) | laya 손해 루프 탈출(학습 가중·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험 | Accepted |
| [D-201](../research/policy-learning/decisions/D-201-laya-engine-judge-v8.md) | laya 실패 표시를 고정 Showdown 엔진 판정기로 바꾼 렌더러 v8 | Accepted |
| [D-202](../research/policy-learning/decisions/D-202-laya-opponent-threat-v9.md) | laya 상대 가정 세트 노력치 보정과 최악 피해 표시(렌더러 v9) | Accepted |
| [D-203](../research/policy-learning/decisions/D-203-laya-human-teams-v7-v8-v9.md) | laya v7t·v8t·v9t를 사람이 짠 완성 팀으로 Abyssal과 비교(GPU0·1·2) | Accepted |
| [D-204](../research/policy-learning/decisions/D-204-laya-renderer-v10-all-info.md) | laya 렌더러 v10: 지금까지의 정보 전부 + lock + 전략 정보, 2,048토큰 | Accepted |
| [D-205](../research/policy-learning/decisions/D-205-laya-switch-read-and-mixing.md) | laya 교체 읽기 상대(정직함 측정)와 교체 갈림길 섞기(재학습 없음) | Accepted |
| [D-225](../research/policy-learning/decisions/D-225-ep249-ex226-wayb-ex225-c1clean-blim128-ladder.md) | EP-249: EX-226(방식 B) · EX-225(방식 C-1 정화판) Blim 128 병렬 배틀 평가 및 EX-226 공식 래더 병행 | Accepted |
| [EP-022](../research/input-and-memory/plans/EP-022-calculator-entry-calcfix32.md) | 계산기 등장 특성 교정 및 동일32판 | Completed — 사용자 중단 대안 포함 완료; 성능 비교 미완료 |
| [EP-027](../research/input-and-memory/plans/EP-027-external-memory-repeat32.md) | 외부 메모리 장애 후 동일 조건32판 재실험 | Completed |
| [EP-075](../research/input-and-memory/plans/EP-075-jev-v3-abyssal32.md) | JEV v3 동일32경기와 v2 전후 비교 | Blocked |
| [EP-077](../research/input-and-memory/plans/EP-077-jev-v3-retry32.md) | EX-054 재시도3회 동일32경기 | Blocked |
| [EP-080](../research/input-and-memory/plans/EP-080-jev-direct32.md) | EX-056 사전 검증 생략 동일32경기 | Blocked |
| [EP-094](../research/input-and-memory/plans/EP-094-jev-improved32.md) | 개선 JEV 입력 동일32경기 | Completed |
| [EP-095](../research/input-and-memory/plans/EP-095-jev-compact32.md) | 자기 벤치 축약 동일32경기 | Completed |
| [EP-115](../research/policy-learning/plans/EP-115-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EP-124](../research/fixed-matchup-learning/plans/EP-124-fixed-matchup-mcts.md) | 고정 대진 공개 상태 MCTS 구현 | Completed — 구현·CPU 개발 검증 완료, 실험 미실행 |
| [EP-126](../research/fixed-matchup-learning/plans/EP-126-fixed-matchup-day.md) | 하루 내 고정 대진 실험 | Paused — 사용자 요청 중지; 학습·test 미시작 |
| [EP-130](../research/fixed-matchup-learning/plans/EP-130-first-round-model-comparison.md) | 첫라운드 전후 동일 관측 비교 | Completed |
| [EP-131](../research/fixed-matchup-learning/plans/EP-131-fixed-matchup-stopping.md) | 종료조건 기반 추가 학습·독립 평가 | Completed |
| [EP-132](../research/fixed-matchup-learning/plans/EP-132-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 자기대국 학습 실행 | Completed |
| [EP-134](../research/model-evaluation/plans/EP-134-jev27b-ex058-reproduction.md) | JEV-27B 개선 입력 동일32 재현 | Blocked |
| [EP-136](../shared/governance/plans/EP-136-branch-research-manuals.md) | 분리된 연구선의 매뉴얼 정비 | Completed |
| [EP-138](../research/model-evaluation/plans/EP-138-quyet-medium-two-stage.md) | Quyet-Medium 2단계 정책 동일32 평가 | Completed |
| [EP-139](../research/model-evaluation/plans/EP-139-jev9b-single-choice.md) | JEV-9B 단일 Choice 동일32 평가 | Completed |
| [EP-209](../research/policy-learning/plans/EP-209-laya-team-generalization.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EP-210](../research/policy-learning/plans/EP-210-laya-renderer-v2.md) | laya 모듈형 렌더러 v2 학습과 v1·v2 비교 | Completed |
| [EP-212](../research/policy-learning/plans/EP-212-laya-tera-knowledge.md) | laya v2 테라 지식 데이터 학습과 배틀 비교(GPU1) | Completed |
| [EP-213](../research/policy-learning/plans/EP-213-laya-effect-knowledge.md) | laya v2+테라+효과 지식 데이터 학습과 배틀 비교(GPU2) | Completed |
| [EP-214](../research/policy-learning/plans/EP-214-laya-renderer-v3.md) | laya 렌더러 v3(상대 세트 추론) 학습과 배틀 비교(GPU0) | Completed |
| [EP-215](../research/policy-learning/plans/EP-215-laya-renderer-v4.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) 학습과 배틀 비교(GPU1) | Completed |
| [EP-216](../research/policy-learning/plans/EP-216-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방 학습과 배틀 비교(GPU0) | Completed |
| [EP-217](../research/policy-learning/plans/EP-217-laya-head-to-head-evaluation.md) | laya 직접 대결 평가 하네스와 벤치마크(GPU2) | Completed |
| [EP-218](../research/policy-learning/plans/EP-218-laya-renderer-v5-item-state.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) 학습과 배틀 비교(GPU0·GPU2) | Completed |
| [EP-219](../research/policy-learning/plans/EP-219-laya-v2t-corrected-input-battle.md) | laya v2+테라 보정 입력 배틀(재학습 없음, GPU1) | Completed |
| [EP-220](../research/policy-learning/plans/EP-220-laya-v2t-tera-decision-defence.md) | laya v2+테라 fix 입력 테라 합산 결정·테라 방어 문구 배틀(재학습 없음, GPU1) | Completed |
| [EP-221](../research/policy-learning/plans/EP-221-laya-past-turn-input-v6.md) | laya 과거 턴 입력 v6s·v6h 동시 학습과 배틀 비교(GPU0·GPU1) | Completed |
| [EP-222](../research/policy-learning/plans/EP-222-laya-play-teams-abyssal-battle.md) | laya-play 완성 팀으로 v5t·v6st·v6ht 대 Abyssal 비교(GPU2) | Completed |
| [EP-223](../research/policy-learning/plans/EP-223-laya-loop-break-opponent-sets.md) | laya 손해 루프 탈출(가중 학습·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험(GPU0~3) | Completed |
| [EP-224](../research/policy-learning/plans/EP-224-laya-engine-judge-v8.md) | laya 엔진 판정기(고정 Showdown 실패 판정)와 렌더러 v8 학습·배틀(GPU1·GPU2) | Completed |
| [EP-225](../research/policy-learning/plans/EP-225-laya-opponent-threat-v9.md) | laya 상대 노력치 보정·최악 피해 표시 렌더러 v9 학습·배틀(GPU3) | Completed |
| [EP-226](../research/policy-learning/plans/EP-226-laya-human-teams-v7-v8-v9.md) | laya v7t·v8t·v9t 사람 팀 비교 배틀(GPU0·1·2) | Stopped |
| [EP-227](../research/policy-learning/plans/EP-227-laya-renderer-v10.md) | laya 렌더러 v10(정보 전부 + lock + 전략, 2,048토큰) 학습과 Abyssal 배틀 | Completed |
| [EP-228](../research/policy-learning/plans/EP-228-laya-switch-read-and-mixing.md) | laya 교체 읽기 상대(정직함 측정)와 v8lt 교체 갈림길 섞기 배틀(재학습 없음, GPU1~3) | Completed |
| [EP-230](../research/policy-learning/plans/EP-230-laya-ladder-r1500-v10.md) | 최근 래더(레이팅 1500 이상) 리플레이 자료와 v10 학습(GPU 4장 DDP), Abyssal 배틀 | Completed |
| [EP-249](../research/policy-learning/plans/EP-249-ex226-wayb-and-ex225-c1clean-blim128-and-ladder.md) | EX-226(방식 B) · EX-225(방식 C-1 정화판) Blim 128 병렬 배틀 평가 및 EX-226 공식 래더 병행 | Completed |
| [EX-033](../research/input-and-memory/experiments/EX-033-external-memory-repeat32.md) | 외부 메모리 장애 후 동일 조건32판 | Completed |
| [EX-046](../research/lead-policy/experiments/EX-046-async-official-lead.md) | 비동기 교정본 공식 관측 B2 선봉 본실험 | Completed |
| [EX-054](../research/input-and-memory/experiments/EX-054-jev-v3-retry32.md) | 재시도3회 적용 JEV v3 동일32경기 | Incomplete |
| [EX-056](../research/input-and-memory/experiments/EX-056-jev-direct32.md) | 사전 검증 없이 동일 조건32경기 재실험 | Incomplete |
| [EX-058](../research/input-and-memory/experiments/EX-058-jev-improved32.md) | 개선 JEV 입력 동일32경기 | Completed |
| [EX-059](../research/input-and-memory/experiments/EX-059-jev-compact32.md) | 자기 벤치 축약 JEV 입력 동일32경기 | Completed |
| [EX-069](../research/model-evaluation/experiments/EX-069-kev-test-battles.md) | EX-065 test20 고정 대진의 Kev 본 테스트 | Completed |
| [EX-077](../research/fixed-matchup-learning/experiments/EX-077-fixed-matchup-day.md) | 하루 내 고정 대진 공개 상태 학습 | Incomplete — 사용자 요청 중지; 학습/test 미시작 |
| [EX-079](../research/fixed-matchup-learning/experiments/EX-079-fixed-matchup-stopping.md) | 종료조건 기반 고정 대진 추가 학습 | Completed — 추가학습·시험·감사/뷰어·정리 완료; 주효능 기준 미달 |
| [EX-080](../research/fixed-matchup-learning/experiments/EX-080-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Completed — 시도 3 학습(round40 둔화 종료)·선택(round36)·잠긴 test·감사/뷰어/봉인·정리 완료; 주효능 미입증 (시도 1·2는 도구 결함으로 학습 전 중단·보존) |
| [EX-082](../research/model-evaluation/experiments/EX-082-jev27b-ex058-reproduction.md) | JEV-27B로 EX-058 개선 입력 동일32 평가 | Blocked |
| [EX-083](../research/model-evaluation/experiments/EX-083-jev27b-four-gpu-continuation.md) | JEV-27B 4GPU 잔여9경기 계승 평가 | Completed |
| [EX-084](../research/model-evaluation/experiments/EX-084-quyet-medium-two-stage.md) | Quyet-Medium 2단계 정책의 EX-083 동일32경기 평가 | Completed |
| [EX-085](../research/model-evaluation/experiments/EX-085-jev9b-single-choice.md) | JEV-9B의 EX-083 설정 기반 동일32경기 평가 | Completed |
| [EX-086](../research/input-and-memory/experiments/EX-086-jev27b-public-memory-v6.md) | JEV-27B 공개 정보 v6 신규32경기 | Blocked |
| [EX-088](../research/input-and-memory/experiments/EX-088-jev27b-v6-corrected.md) | 교정 v6 JEV-27B 신규32경기 | Completed |
| [EX-089](../research/input-and-memory/experiments/EX-089-jev9b-v6-corrected.md) | 교정 v6 JEV-9B 신규32경기 | Completed |
| [EX-090](../research/input-and-memory/experiments/EX-090-jev9b-no-damage.md) | JEV-9B 피해 예측 제거 신규32경기 | Completed |
| [EX-091](../research/model-evaluation/experiments/EX-091-minicpm5-2b-jev.md) | MiniCPM5-2B-Jev 계산기 포함 신규32경기 | Completed |
| [EX-109](../research/model-evaluation/experiments/EX-109-openai-decisions-v6-battle32.md) | OpenAI Decisions v6 상세32경기 | Stopped |
| [EX-110](../research/model-evaluation/experiments/EX-110-openai-decisions-retry32.md) | OpenAI Decisions 통신 재시도 새32경기 | Completed |
| [EX-111](../research/model-evaluation/experiments/EX-111-jevk5-v6-battle32.md) | JevK5-9B v6 상세32경기 | Completed |
| [EX-120](../research/policy-learning/experiments/EX-120-laya-team-generalization128.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EX-122](../research/policy-learning/experiments/EX-122-laya-v1-v2-battle256.md) | laya v1·v2 같은 실행 256경기 비교 (EX-120 일정) | Completed |
| [EX-125](../research/policy-learning/experiments/EX-125-laya-v2-tera-battle256.md) | laya v2와 v2+테라 지식 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-127](../research/policy-learning/experiments/EX-127-laya-v2t-v2te-battle256.md) | laya v2+테라와 v2+테라+효과 지식 같은 실행 256경기(GPU2, EX-120 일정) | Completed |
| [EX-129](../research/policy-learning/experiments/EX-129-laya-v2t-v3t-battle256.md) | laya v2+테라와 v3+테라 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-131](../research/policy-learning/experiments/EX-131-laya-v2t-v4t-battle256.md) | laya v2+테라와 v4+테라 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-133](../research/policy-learning/experiments/EX-133-laya-v2t-v2tw-battle256.md) | laya v2+테라와 v2+테라 승패 가중 모방 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-134](../research/policy-learning/experiments/EX-134-laya-head-to-head512.md) | laya v2+테라 대 v2·v1·v2+테라+효과·v3+테라 직접 대결 512경기(GPU2, EX-120 일정) | Completed |
| [EX-135](../research/policy-learning/experiments/EX-135-laya-head-to-head-v2tw-v4t.md) | laya v2+테라 대 승패 가중·v4+테라 직접 대결 256경기(GPU2, EX-120 일정) | Completed |
| [EX-137](../research/policy-learning/experiments/EX-137-laya-v4t-v5t-battle256.md) | laya v4+테라와 v5+테라 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-138](../research/policy-learning/experiments/EX-138-laya-head-to-head-v5t.md) | laya v5+테라 대 v2+테라·v4+테라 직접 대결 256경기(GPU2, EX-120 일정) | Completed |
| [EX-139](../research/policy-learning/experiments/EX-139-laya-v2t-corrected-input-battle256.md) | laya v2+테라(EX-124) 보정 입력 fix·info 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-140](../research/policy-learning/experiments/EX-140-laya-v2t-tera-decision-defence384.md) | laya v2+테라(EX-124) fix 입력 테라 합산 결정(k=1·3)과 테라 방어 문구 384경기(GPU1, EX-120 일정) | Completed |
| [EX-143](../research/policy-learning/experiments/EX-143-laya-v5t-v6st-battle256.md) | laya v5+테라와 v6st (반복 표시) 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-144](../research/policy-learning/experiments/EX-144-laya-v5t-v6ht-battle256.md) | laya v5+테라와 v6ht (긴 기록 2048토큰) 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-145](../research/policy-learning/experiments/EX-145-laya-play-teams-v5t-v6st-v6ht-battle.md) | laya-play 완성 팀 74개로 v5t·v6st·v6ht 대 Abyssal(GPU2) | Completed |
| [EX-147](../research/policy-learning/experiments/EX-147-laya-v6st-v6slt-battle256.md) | laya v6st 대 v6slt(루프 탈출 가중) 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-148](../research/policy-learning/experiments/EX-148-laya-loop-decision-rule.md) | laya 루프 결정 규칙(재학습 없음): v6st·v6ht 정체 루프 기술 제외, EX-120 일정 대 Abyssal | Completed |
| [EX-150](../research/policy-learning/experiments/EX-150-laya-v6st-v7t-battle256.md) | laya v6st 대 v7t(상대 세트 추정) 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-153](../research/policy-learning/experiments/EX-153-laya-v7t-v8t-battle256.md) | laya v7t 대 v8t(엔진 실패 표시) 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-154](../research/policy-learning/experiments/EX-154-laya-head-to-head-v8t-v7t.md) | laya v8t 대 v7t 직접 대결 128경기(GPU2, EX-120 일정) | Stopped |
| [EX-156](../research/policy-learning/experiments/EX-156-laya-v8t-v8lt-battle256.md) | laya v8t 대 v8lt(`likely fails` 표시) 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-158](../research/policy-learning/experiments/EX-158-laya-v7t-v9t-battle256.md) | laya v7t 대 v9t(상대 위협 표시) 같은 실행 256경기(GPU3, EX-120 일정) | Completed |
| [EX-159](../research/policy-learning/experiments/EX-159-laya-human-teams-v7t-v8t-v9t.md) | laya v7t·v8t·v9t 사람이 짠 완성 팀 123개 대 Abyssal(GPU0·1·2) | Stopped |
| [EX-160](../research/policy-learning/experiments/EX-160-laya-human-teams-v8lt.md) | laya v8lt 사람이 짠 완성 팀 123개 대 Abyssal(EX-159 일정, GPU3) | Stopped |
| [EX-162](../research/policy-learning/experiments/EX-162-laya-v7t-v10t-battle256.md) | laya v7t 대 v10t(정보 전부 + lock + 전략) 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-163](../research/policy-learning/experiments/EX-163-laya-v8lt-vs-switch-reader.md) | laya v8lt argmax 대 교체 읽기 상대(abyssal-read), EX-120 일정 128경기(GPU1) | Completed |
| [EX-164](../research/policy-learning/experiments/EX-164-laya-v8lt-switch-mixing.md) | laya v8lt 교체 갈림길 섞기(재학습 없음): 대 Abyssal·대 교체 읽기 상대, 각 128경기(GPU2·GPU3) | Completed |
| [EX-168](../research/policy-learning/experiments/EX-168-laya-v10t-v10rt-battle256.md) | laya v10t 대 v10rt(최근 래더 자료 추가) 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-227](../research/policy-learning/experiments/EX-227-laya-ex226-wayb-vs-foulplay-blim128.md) | EX-226 방식 B(calc-duel-free + 5단계 matchup & eval 프롬프트 주입, Laya 단독 최종결정) 대 foul-play Blim 128 (GPU 0) | Completed |
| [EX-228](../research/policy-learning/experiments/EX-228-laya-ex225-c1clean-standalone-vs-foulplay-blim128.md) | EX-225 방식 C-1 정화판 단독 무탐색(v14+walled_duel) 대 foul-play Blim 128 (GPU 1) | Completed |
| [EX-229](../research/policy-learning/experiments/EX-229-laya-ex225-waya-v2-noduel-vs-foulplay-blim128.md) | EX-225 방식 C-1 정화판 + Way A v2(calc-duel-free + MCTS 50k + V_phi v3 2-ply) 대 foul-play Blim 128 (GPU 1) | Completed |

## 평가 / 고정대진32경기

| ID | 제목 | 상태 |
|---|---|---|
| [EP-191](../research/rule-learning/plans/EP-191-jevk5-ruleqa-battle32.md) | 학습 JevK5 LoRA 실전32 실행 | Completed |
| [EX-114](../research/rule-learning/experiments/EX-114-jevk5-ruleqa-battle32.md) | 학습 JevK5 선택형 LoRA 실전32 | Completed |

## 평가 / 독립 선택형

| ID | 제목 | 상태 |
|---|---|---|
| [D-180](../research/rule-learning/decisions/D-180-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Accepted |
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
| [D-198](../research/policy-learning/decisions/D-198-laya-past-turn-input-v6.md) | laya 과거 턴 입력 두 가지(v6s 반복 표시·v6h 긴 기록 2048토큰) 동시 학습과 배틀 | Accepted |
| [D-200](../research/policy-learning/decisions/D-200-laya-loop-break-opponent-sets.md) | laya 손해 루프 탈출(학습 가중·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험 | Accepted |
| [D-201](../research/policy-learning/decisions/D-201-laya-engine-judge-v8.md) | laya 실패 표시를 고정 Showdown 엔진 판정기로 바꾼 렌더러 v8 | Accepted |
| [D-202](../research/policy-learning/decisions/D-202-laya-opponent-threat-v9.md) | laya 상대 가정 세트 노력치 보정과 최악 피해 표시(렌더러 v9) | Accepted |
| [D-204](../research/policy-learning/decisions/D-204-laya-renderer-v10-all-info.md) | laya 렌더러 v10: 지금까지의 정보 전부 + lock + 전략 정보, 2,048토큰 | Accepted |
| [D-209](../research/policy-learning/decisions/D-209-laya-ladder-postmortem-v11.md) | laya v10rt 공식 래더 패배 원인 추가 분석과 재학습 v11(입력 수정·정책 교정) 설계 | Accepted |
| [EP-203](../research/rule-learning/plans/EP-203-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |
| [EP-208](../research/policy-learning/plans/EP-208-laya-compact-imitation.md) | laya 압축 입력 모방 학습·배틀 에이전트 | Completed |
| [EP-210](../research/policy-learning/plans/EP-210-laya-renderer-v2.md) | laya 모듈형 렌더러 v2 학습과 v1·v2 비교 | Completed |
| [EP-212](../research/policy-learning/plans/EP-212-laya-tera-knowledge.md) | laya v2 테라 지식 데이터 학습과 배틀 비교(GPU1) | Completed |
| [EP-213](../research/policy-learning/plans/EP-213-laya-effect-knowledge.md) | laya v2+테라+효과 지식 데이터 학습과 배틀 비교(GPU2) | Completed |
| [EP-214](../research/policy-learning/plans/EP-214-laya-renderer-v3.md) | laya 렌더러 v3(상대 세트 추론) 학습과 배틀 비교(GPU0) | Completed |
| [EP-215](../research/policy-learning/plans/EP-215-laya-renderer-v4.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) 학습과 배틀 비교(GPU1) | Completed |
| [EP-216](../research/policy-learning/plans/EP-216-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방 학습과 배틀 비교(GPU0) | Completed |
| [EP-218](../research/policy-learning/plans/EP-218-laya-renderer-v5-item-state.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) 학습과 배틀 비교(GPU0·GPU2) | Completed |
| [EP-221](../research/policy-learning/plans/EP-221-laya-past-turn-input-v6.md) | laya 과거 턴 입력 v6s·v6h 동시 학습과 배틀 비교(GPU0·GPU1) | Completed |
| [EP-223](../research/policy-learning/plans/EP-223-laya-loop-break-opponent-sets.md) | laya 손해 루프 탈출(가중 학습·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험(GPU0~3) | Completed |
| [EP-224](../research/policy-learning/plans/EP-224-laya-engine-judge-v8.md) | laya 엔진 판정기(고정 Showdown 실패 판정)와 렌더러 v8 학습·배틀(GPU1·GPU2) | Completed |
| [EP-225](../research/policy-learning/plans/EP-225-laya-opponent-threat-v9.md) | laya 상대 노력치 보정·최악 피해 표시 렌더러 v9 학습·배틀(GPU3) | Completed |
| [EP-227](../research/policy-learning/plans/EP-227-laya-renderer-v10.md) | laya 렌더러 v10(정보 전부 + lock + 전략, 2,048토큰) 학습과 Abyssal 배틀 | Completed |
| [EP-230](../research/policy-learning/plans/EP-230-laya-ladder-r1500-v10.md) | 최근 래더(레이팅 1500 이상) 리플레이 자료와 v10 학습(GPU 4장 DDP), Abyssal 배틀 | Completed |
| [EP-231](../research/policy-learning/plans/EP-231-laya-ladder-postmortem-v11.md) | laya v10rt 공식 래더 패배 원인 추가 분석과 재학습 v11(v11rt·v11rtc) | Active |
| [EX-116](../research/rule-learning/experiments/EX-116-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |
| [EX-118](../research/policy-learning/experiments/EX-118-laya-compact-imitation-training.md) | laya 압축 입력 리플레이 모방 학습 | Completed |
| [EX-121](../research/policy-learning/experiments/EX-121-laya-v2-all-training.md) | laya 모듈형 렌더러 v2(4종 전부) 학습과 v1 쌍비교 | Completed |
| [EX-124](../research/policy-learning/experiments/EX-124-laya-v2-tera-knowledge-training.md) | laya v2 + 테라 기본 지식 데이터 학습(GPU1) | Completed |
| [EX-126](../research/policy-learning/experiments/EX-126-laya-v2-tera-effect-training.md) | laya v2 + 테라 + 효과 지식 데이터 학습(GPU2) | Completed |
| [EX-128](../research/policy-learning/experiments/EX-128-laya-v3-tera-training.md) | laya 렌더러 v3(상대 세트 추론) + 테라 지식 학습(GPU0) | Completed |
| [EX-130](../research/policy-learning/experiments/EX-130-laya-v4-tera-training.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) + 테라 지식 학습(GPU1) | Completed |
| [EX-132](../research/policy-learning/experiments/EX-132-laya-v2t-outcome-weighted-training.md) | laya v2+테라 승패 가중 모방 학습(GPU0) | Completed |
| [EX-136](../research/policy-learning/experiments/EX-136-laya-v5-tera-training.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) + 테라 지식 학습(GPU0) | Completed |
| [EX-141](../research/policy-learning/experiments/EX-141-laya-v6s-streaks-training.md) | laya 렌더러 v6s(같은 기술 반복 표시) + 테라 지식 학습(GPU0) | Completed |
| [EX-142](../research/policy-learning/experiments/EX-142-laya-v6h-long-history-training.md) | laya 렌더러 v6h(긴 과거 기록, 2048토큰) + 테라 지식 학습(GPU1) | Completed |
| [EX-146](../research/policy-learning/experiments/EX-146-laya-v6sl-loop-weighted-training.md) | laya v6s + 루프 탈출 행 가중 학습(v6sl, GPU1) | Completed |
| [EX-149](../research/policy-learning/experiments/EX-149-laya-v7-opponent-sets-training.md) | laya 렌더러 v7(v6s + 상대 세트 추정 `oppset2`, Protean 실패 표시 보정) 학습(GPU0) | Completed |
| [EX-151](../research/policy-learning/experiments/EX-151-laya-engine-judge-validation.md) | laya 엔진 판정기 구축과 실전·사람 리플레이 검증 | Completed |
| [EX-152](../research/policy-learning/experiments/EX-152-laya-v8-engine-fails-training.md) | laya 렌더러 v8(v7 + 엔진 판정기 실패 표시) 학습(GPU1) | Completed |
| [EX-155](../research/policy-learning/experiments/EX-155-laya-v8l-likely-fails-training.md) | laya 렌더러 v8l(v8 + `likely fails` 표시) 학습(GPU2) | Completed |
| [EX-157](../research/policy-learning/experiments/EX-157-laya-v9-opponent-threat-training.md) | laya 렌더러 v9(v7 + 상대 노력치 보정·최악 피해 표시) 학습(GPU3) | Completed |
| [EX-161](../research/policy-learning/experiments/EX-161-laya-v10-all-info-training.md) | laya 렌더러 v10(정보 전부 + lock + 전략, 2,048토큰) 학습(GPU0) | Completed |
| [EX-167](../research/policy-learning/experiments/EX-167-laya-v10-ladder-training.md) | laya v10 + 최근 래더 자료 학습(GPU 4장 DDP, 약 24시간) | Completed |
| [EX-169](../research/policy-learning/experiments/EX-169-laya-v10rt-ladder-loss-analysis.md) | laya v10rt 공식 래더 83판 패배 원인 추가 분석(CPU, 추론만 GPU) | Completed |
| [EX-171](../research/policy-learning/experiments/EX-171-laya-v11rt-training.md) | laya v11rt 학습(v10rt + 입력 수정, 1 epoch) | Completed |
| [EX-172](../research/policy-learning/experiments/EX-172-laya-v11rtc-training.md) | laya v11rtc 학습(v10rt + 입력 수정 + 정책 교정, 1 epoch) | Completed |
| [EX-178](../research/policy-learning/experiments/EX-178-laya-fp1-training.md) | laya fp1 처음부터 전체 학습(GPU 4장 DDP, 약 24시간) | Completed |

## 평가 / 래더

| ID | 제목 | 상태 |
|---|---|---|
| [D-224](../research/policy-learning/decisions/D-224-batch-b-waya-v2-ladder-wayc1-clean-wayb.md) | 배치 B 병행 실행: EX-223 방식 A v2 공식 래더(EX-224) + 정화 교사 방식 C-1(EX-225) → 프롬프트 도구 주입 방식 B(EX-226) DDP 자동 연쇄 | Accepted |
| [D-225](../research/policy-learning/decisions/D-225-ep249-ex226-wayb-ex225-c1clean-blim128-ladder.md) | EP-249: EX-226(방식 B) · EX-225(방식 C-1 정화판) Blim 128 병렬 배틀 평가 및 EX-226 공식 래더 병행 | Accepted |
| [D-226](../research/policy-learning/decisions/D-226-ep250-ex226-wayb-offense-ladder.md) | EP-250: EX-226 방식 B Offense 전용 공식 Showdown 래더 대전 (13:30 KST까지) | Accepted |
| [EP-248](../research/policy-learning/plans/EP-248-batch-b-waya-v2-ladder-wayc1-clean-wayb.md) | 배치 B: EX-223 방식 A v2 공식 래더 병행 + 정화 방식 C-1 → 방식 B GPU 0·1 DDP 자동 연쇄 | Completed |
| [EP-249](../research/policy-learning/plans/EP-249-ex226-wayb-and-ex225-c1clean-blim128-and-ladder.md) | EX-226(방식 B) · EX-225(방식 C-1 정화판) Blim 128 병렬 배틀 평가 및 EX-226 공식 래더 병행 | Completed |
| [EP-250](../research/policy-learning/plans/EP-250-ex226-wayb-offense-ladder.md) | EX-226 방식 B Offense 전용 공식 Showdown gen9ou 래더 (13:30 KST까지) | Active |
| [EX-211](../research/policy-learning/experiments/EX-211-laya-search2b-ladder.md) | 2-B 온라인 다중턴 탐색 + 상태가치 V_phi(EX-208) 공식 Showdown gen9ou 래더 대전(GPU 1 서빙, 2026-11-24 13:00 KST까지) | Stopped |
| [EX-215](../research/policy-learning/experiments/EX-215-laya-search2bv2-ladder.md) | 2-B v2 탐색 개선(EX-212 동일 설정, CPU 서빙) 공식 Showdown gen9ou 래더 대전(2026-11-24 13:00 KST까지) | Stopped |
| [EX-220](../research/policy-learning/experiments/EX-220-laya-waya-mcts50k-ladder.md) | EX-217 방식 A(Laya 메인 + MCTS 50k + EX-216 V_phi v2 + walled_duel, CPU 서빙) 공식 Showdown gen9ou 래더 대전 (EX-218 학습 완료까지) | Stopped |
| [EX-224](../research/policy-learning/experiments/EX-224-laya-waya-v2-vphiv3-2ply-ladder.md) | EX-223 방식 A v2(V_phi v3 + 2-ply + MCTS 50k + 회복/Protect 가드레일, CPU 서빙) 공식 Showdown gen9ou 래더 대전 | Stopped |
| [EX-230](../research/policy-learning/experiments/EX-230-laya-ex226-wayb-ladder.md) | EX-226 방식 B(calc-duel-free + 5단계 matchup & eval 프롬프트 주입, CPU 서빙) 공식 Showdown gen9ou 래더 대전 | Completed |
| [EX-231](../research/policy-learning/experiments/EX-231-laya-ex226-wayb-offense-ladder.md) | EX-226 방식 B Offense 전용(4팀 순환, GPU 0 서빙) 공식 Showdown gen9ou 래더 대전 | Running |

## 평가 / 배틀

| ID | 제목 | 상태 |
|---|---|---|
| [D-179](../research/input-and-memory/decisions/D-179-candidate-action-v7.md) | 후보 중심 v7와 응답 복구 탐색 실험 | Accepted |
| [D-182](../research/input-and-memory/decisions/D-182-v7-survival-battle32.md) | 생존·교체 비용 v7 GPT-6 Luna 32경기 | Accepted |
| [D-184](../research/policy-learning/decisions/D-184-laya-team-generalization.md) | laya 모방 모델의 새 팀 일반화 평가 | Accepted |
| [D-186](../research/rule-learning/decisions/D-186-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Accepted |
| [D-194](../research/policy-learning/decisions/D-194-laya-head-to-head-evaluation.md) | laya 직접 대결 평가(GPU2, EX-120 일정) | Accepted |
| [D-196](../research/policy-learning/decisions/D-196-laya-v2t-corrected-input-battle.md) | laya v2+테라(EX-124)를 재학습 없이 D-195 보정 입력으로 배틀(GPU1) | Accepted |
| [D-197](../research/policy-learning/decisions/D-197-laya-v2t-tera-decision-defence.md) | laya v2+테라(EX-124) fix 입력에서 테라 합산 결정과 테라 방어 문구 배틀(재학습 없음, GPU1) | Accepted |
| [D-199](../research/policy-learning/decisions/D-199-laya-play-teams-abyssal-battle.md) | laya-play 완성 팀(Smogon 샘플·Blim)으로 v5t·v6st·v6ht 대 Abyssal 비교 | Accepted |
| [D-200](../research/policy-learning/decisions/D-200-laya-loop-break-opponent-sets.md) | laya 손해 루프 탈출(학습 가중·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험 | Accepted |
| [D-201](../research/policy-learning/decisions/D-201-laya-engine-judge-v8.md) | laya 실패 표시를 고정 Showdown 엔진 판정기로 바꾼 렌더러 v8 | Accepted |
| [D-202](../research/policy-learning/decisions/D-202-laya-opponent-threat-v9.md) | laya 상대 가정 세트 노력치 보정과 최악 피해 표시(렌더러 v9) | Accepted |
| [D-203](../research/policy-learning/decisions/D-203-laya-human-teams-v7-v8-v9.md) | laya v7t·v8t·v9t를 사람이 짠 완성 팀으로 Abyssal과 비교(GPU0·1·2) | Accepted |
| [D-204](../research/policy-learning/decisions/D-204-laya-renderer-v10-all-info.md) | laya 렌더러 v10: 지금까지의 정보 전부 + lock + 전략 정보, 2,048토큰 | Accepted |
| [D-205](../research/policy-learning/decisions/D-205-laya-switch-read-and-mixing.md) | laya 교체 읽기 상대(정직함 측정)와 교체 갈림길 섞기(재학습 없음) | Accepted |
| [D-206](../research/policy-learning/decisions/D-206-laya-opponent-model-search.md) | laya 상대 모델 + 한 턴 탐색(세트 표본 추정), 재학습 없음 | Accepted |
| [D-208](../research/policy-learning/decisions/D-208-laya-ladder-r1500-v10.md) | 최근 래더(레이팅 1500 이상) 리플레이를 더한 v10 학습(GPU 4장 DDP, 24시간) | Accepted |
| [D-209](../research/policy-learning/decisions/D-209-laya-ladder-postmortem-v11.md) | laya v10rt 공식 래더 패배 원인 추가 분석과 재학습 v11(입력 수정·정책 교정) 설계 | Accepted |
| [D-211](../research/policy-learning/decisions/D-211-laya-foulplay-opponent.md) | foul-play(탐색 봇)를 laya의 고정 상대로 도입하고 v10rt와 EX-120 일정으로 대전 | Accepted |
| [D-212](../research/policy-learning/decisions/D-212-laya-foulplay-blim-teams.md) | foul-play 대전을 Blim 팀 일정으로 바꾸고 EX-173을 중지 | Accepted |
| [D-213](../research/policy-learning/decisions/D-213-laya-fp1-foulplay-input.md) | laya 입력을 foul-play 추적·poke-engine 계산으로 전부 바꾼 렌더러 fp1과 처음부터 전체 학습 | Accepted |
| [D-214](../research/policy-learning/decisions/D-214-laya-foulplay-primary-ladder-final.md) | laya 정책 개선의 개발 목표를 foul-play 상대 점수로, 최종 실험을 공식 래더 대전으로 둔다 | Accepted |
| [EP-202](../research/input-and-memory/plans/EP-202-candidate-action-v7.md) | 후보 중심 v7와 GPT-6 Luna 32경기 | Completed |
| [EP-206](../research/input-and-memory/plans/EP-206-v7-survival-battle32.md) | 개정 v7 GPT-6 Luna 32경기 시작·수집 | Blocked |
| [EP-209](../research/policy-learning/plans/EP-209-laya-team-generalization.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EP-211](../research/rule-learning/plans/EP-211-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Completed |
| [EP-217](../research/policy-learning/plans/EP-217-laya-head-to-head-evaluation.md) | laya 직접 대결 평가 하네스와 벤치마크(GPU2) | Completed |
| [EP-219](../research/policy-learning/plans/EP-219-laya-v2t-corrected-input-battle.md) | laya v2+테라 보정 입력 배틀(재학습 없음, GPU1) | Completed |
| [EP-220](../research/policy-learning/plans/EP-220-laya-v2t-tera-decision-defence.md) | laya v2+테라 fix 입력 테라 합산 결정·테라 방어 문구 배틀(재학습 없음, GPU1) | Completed |
| [EP-222](../research/policy-learning/plans/EP-222-laya-play-teams-abyssal-battle.md) | laya-play 완성 팀으로 v5t·v6st·v6ht 대 Abyssal 비교(GPU2) | Completed |
| [EP-223](../research/policy-learning/plans/EP-223-laya-loop-break-opponent-sets.md) | laya 손해 루프 탈출(가중 학습·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험(GPU0~3) | Completed |
| [EP-224](../research/policy-learning/plans/EP-224-laya-engine-judge-v8.md) | laya 엔진 판정기(고정 Showdown 실패 판정)와 렌더러 v8 학습·배틀(GPU1·GPU2) | Completed |
| [EP-225](../research/policy-learning/plans/EP-225-laya-opponent-threat-v9.md) | laya 상대 노력치 보정·최악 피해 표시 렌더러 v9 학습·배틀(GPU3) | Completed |
| [EP-226](../research/policy-learning/plans/EP-226-laya-human-teams-v7-v8-v9.md) | laya v7t·v8t·v9t 사람 팀 비교 배틀(GPU0·1·2) | Stopped |
| [EP-227](../research/policy-learning/plans/EP-227-laya-renderer-v10.md) | laya 렌더러 v10(정보 전부 + lock + 전략, 2,048토큰) 학습과 Abyssal 배틀 | Completed |
| [EP-228](../research/policy-learning/plans/EP-228-laya-switch-read-and-mixing.md) | laya 교체 읽기 상대(정직함 측정)와 v8lt 교체 갈림길 섞기 배틀(재학습 없음, GPU1~3) | Completed |
| [EP-229](../research/policy-learning/plans/EP-229-laya-opponent-model-search.md) | laya 상대 모델 + 한 턴 탐색(세트 표본 추정) | Active |
| [EP-230](../research/policy-learning/plans/EP-230-laya-ladder-r1500-v10.md) | 최근 래더(레이팅 1500 이상) 리플레이 자료와 v10 학습(GPU 4장 DDP), Abyssal 배틀 | Completed |
| [EP-232](../research/policy-learning/plans/EP-232-laya-foulplay-v10rt.md) | foul-play(탐색 봇) 대 laya v10rt 128경기(CPU; EX-173 EX-120 팀 → 중지, EX-174 Blim 팀) | Completed |
| [EP-233](../research/policy-learning/plans/EP-233-laya-foulplay-v11.md) | foul-play 대 laya v11rt·v11rtc, EX-174 Blim 일정 128경기씩(CPU) | Stopped |
| [EP-234](../research/policy-learning/plans/EP-234-laya-fp1-foulplay-input.md) | laya fp1 렌더러(foul-play 기반 입력) 자료·처음부터 전체 학습·foul-play 배틀 | Active |
| [EP-236](../research/policy-learning/plans/EP-236-laya-v11rtc-foulplay-distill-rl.md) | v11rtc에 foul-play 탐색 증류 → foul-play 상대 강화학습 → foul-play·공식 래더 평가 | Paused |
| [EP-241](../research/policy-learning/plans/EP-241-laya-v13-zeroshot-vs-foulplay.md) | laya v13 입력 교정(무재학습 EX-200) 대 foul-play Blim 128경기(시간 제한 없음) | Completed |
| [EP-243](../research/policy-learning/plans/EP-243-laya-multiturn-search-value-distill.md) | 다중턴 온라인 탐색(2-A)·신경망 상태가치(2-B)·경량 MCTS-Q 재정렬 학습(1-B) (GPU 0·1 전용) | Active |
| [EX-115](../research/input-and-memory/experiments/EX-115-candidate-action-v7.md) | 후보 중심 v7 GPT-6 Luna 32경기 | Completed |
| [EX-117](../research/input-and-memory/experiments/EX-117-v7-survival-battle32.md) | 생존·교체 비용 v7 GPT-6 Luna 32경기 | Stopped |
| [EX-120](../research/policy-learning/experiments/EX-120-laya-team-generalization128.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EX-122](../research/policy-learning/experiments/EX-122-laya-v1-v2-battle256.md) | laya v1·v2 같은 실행 256경기 비교 (EX-120 일정) | Completed |
| [EX-123](../research/rule-learning/experiments/EX-123-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Completed |
| [EX-125](../research/policy-learning/experiments/EX-125-laya-v2-tera-battle256.md) | laya v2와 v2+테라 지식 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-127](../research/policy-learning/experiments/EX-127-laya-v2t-v2te-battle256.md) | laya v2+테라와 v2+테라+효과 지식 같은 실행 256경기(GPU2, EX-120 일정) | Completed |
| [EX-129](../research/policy-learning/experiments/EX-129-laya-v2t-v3t-battle256.md) | laya v2+테라와 v3+테라 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-131](../research/policy-learning/experiments/EX-131-laya-v2t-v4t-battle256.md) | laya v2+테라와 v4+테라 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-133](../research/policy-learning/experiments/EX-133-laya-v2t-v2tw-battle256.md) | laya v2+테라와 v2+테라 승패 가중 모방 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-134](../research/policy-learning/experiments/EX-134-laya-head-to-head512.md) | laya v2+테라 대 v2·v1·v2+테라+효과·v3+테라 직접 대결 512경기(GPU2, EX-120 일정) | Completed |
| [EX-135](../research/policy-learning/experiments/EX-135-laya-head-to-head-v2tw-v4t.md) | laya v2+테라 대 승패 가중·v4+테라 직접 대결 256경기(GPU2, EX-120 일정) | Completed |
| [EX-137](../research/policy-learning/experiments/EX-137-laya-v4t-v5t-battle256.md) | laya v4+테라와 v5+테라 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-138](../research/policy-learning/experiments/EX-138-laya-head-to-head-v5t.md) | laya v5+테라 대 v2+테라·v4+테라 직접 대결 256경기(GPU2, EX-120 일정) | Completed |
| [EX-139](../research/policy-learning/experiments/EX-139-laya-v2t-corrected-input-battle256.md) | laya v2+테라(EX-124) 보정 입력 fix·info 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-140](../research/policy-learning/experiments/EX-140-laya-v2t-tera-decision-defence384.md) | laya v2+테라(EX-124) fix 입력 테라 합산 결정(k=1·3)과 테라 방어 문구 384경기(GPU1, EX-120 일정) | Completed |
| [EX-143](../research/policy-learning/experiments/EX-143-laya-v5t-v6st-battle256.md) | laya v5+테라와 v6st (반복 표시) 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-144](../research/policy-learning/experiments/EX-144-laya-v5t-v6ht-battle256.md) | laya v5+테라와 v6ht (긴 기록 2048토큰) 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-145](../research/policy-learning/experiments/EX-145-laya-play-teams-v5t-v6st-v6ht-battle.md) | laya-play 완성 팀 74개로 v5t·v6st·v6ht 대 Abyssal(GPU2) | Completed |
| [EX-147](../research/policy-learning/experiments/EX-147-laya-v6st-v6slt-battle256.md) | laya v6st 대 v6slt(루프 탈출 가중) 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-148](../research/policy-learning/experiments/EX-148-laya-loop-decision-rule.md) | laya 루프 결정 규칙(재학습 없음): v6st·v6ht 정체 루프 기술 제외, EX-120 일정 대 Abyssal | Completed |
| [EX-150](../research/policy-learning/experiments/EX-150-laya-v6st-v7t-battle256.md) | laya v6st 대 v7t(상대 세트 추정) 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-151](../research/policy-learning/experiments/EX-151-laya-engine-judge-validation.md) | laya 엔진 판정기 구축과 실전·사람 리플레이 검증 | Completed |
| [EX-153](../research/policy-learning/experiments/EX-153-laya-v7t-v8t-battle256.md) | laya v7t 대 v8t(엔진 실패 표시) 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-154](../research/policy-learning/experiments/EX-154-laya-head-to-head-v8t-v7t.md) | laya v8t 대 v7t 직접 대결 128경기(GPU2, EX-120 일정) | Stopped |
| [EX-156](../research/policy-learning/experiments/EX-156-laya-v8t-v8lt-battle256.md) | laya v8t 대 v8lt(`likely fails` 표시) 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-158](../research/policy-learning/experiments/EX-158-laya-v7t-v9t-battle256.md) | laya v7t 대 v9t(상대 위협 표시) 같은 실행 256경기(GPU3, EX-120 일정) | Completed |
| [EX-159](../research/policy-learning/experiments/EX-159-laya-human-teams-v7t-v8t-v9t.md) | laya v7t·v8t·v9t 사람이 짠 완성 팀 123개 대 Abyssal(GPU0·1·2) | Stopped |
| [EX-160](../research/policy-learning/experiments/EX-160-laya-human-teams-v8lt.md) | laya v8lt 사람이 짠 완성 팀 123개 대 Abyssal(EX-159 일정, GPU3) | Stopped |
| [EX-162](../research/policy-learning/experiments/EX-162-laya-v7t-v10t-battle256.md) | laya v7t 대 v10t(정보 전부 + lock + 전략) 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-163](../research/policy-learning/experiments/EX-163-laya-v8lt-vs-switch-reader.md) | laya v8lt argmax 대 교체 읽기 상대(abyssal-read), EX-120 일정 128경기(GPU1) | Completed |
| [EX-164](../research/policy-learning/experiments/EX-164-laya-v8lt-switch-mixing.md) | laya v8lt 교체 갈림길 섞기(재학습 없음): 대 Abyssal·대 교체 읽기 상대, 각 128경기(GPU2·GPU3) | Completed |
| [EX-168](../research/policy-learning/experiments/EX-168-laya-v10t-v10rt-battle256.md) | laya v10t 대 v10rt(최근 래더 자료 추가) 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-173](../research/policy-learning/experiments/EX-173-laya-v10rt-vs-foulplay128.md) | laya v10rt 대 foul-play(MCTS 3초 × 병렬 4), EX-120 일정 128경기(CPU) | Stopped |
| [EX-174](../research/policy-learning/experiments/EX-174-laya-v10rt-vs-foulplay-blim128.md) | laya v10rt 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기(CPU) | Completed |
| [EX-175](../research/policy-learning/experiments/EX-175-laya-v11rt-vs-foulplay-blim128.md) | laya v11rt 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기(CPU) | Stopped |
| [EX-176](../research/policy-learning/experiments/EX-176-laya-v11rtc-vs-foulplay-blim128.md) | laya v11rtc 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기(CPU) | Stopped |
| [EX-179](../research/policy-learning/experiments/EX-179-laya-fp1-vs-foulplay-blim128.md) | laya fp1 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기 | Planned |
| [EX-180](../research/policy-learning/experiments/EX-180-laya-fp1e2-vs-foulplay-blim128.md) | laya fp1 epoch-2 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기(CPU) | Running |
| [EX-184](../research/policy-learning/experiments/EX-184-laya-v11rtc-vs-foulplay-blim128.md) | v11rtc 대 foul-play, Blim 팀 64개 128경기(CPU, 기준 완료본) | Planned |
| [EX-185](../research/policy-learning/experiments/EX-185-laya-distill-vs-foulplay-blim128.md) | 증류 모델(EX-183) 대 foul-play, Blim 팀 64개 128경기(CPU) | Stopped |
| [EX-187](../research/policy-learning/experiments/EX-187-laya-distill-rl-vs-foulplay-blim128.md) | 강화학습 모델(EX-186) 대 foul-play, Blim 팀 64개 128경기(CPU) | Paused |
| [EX-188](../research/policy-learning/experiments/EX-188-laya-distill-ladder-final.md) | EP-236 최종 후보의 공식 Showdown gen9ou 래더 대전 | Paused |
| [EX-189](../research/policy-learning/experiments/EX-189-laya-v11d-ladder-interim.md) | v11d(EX-183) 공식 Showdown gen9ou 래더 중간 대전(GPU 서빙, 2026-11-20 23:00 KST까지) | Stopped |
| [EX-193](../research/policy-learning/experiments/EX-193-laya-v12-vs-foulplay-blim128.md) | laya v12(EX-192) 대 foul-play, Blim 팀 64개 128경기(CPU) | Completed |
| [EX-194](../research/policy-learning/experiments/EX-194-laya-v12-ladder.md) | v12(EX-192) 공식 Showdown gen9ou 래더 대전(GPU 서빙, 2026-11-21 23:59 KST까지) | Completed |
| [EX-197](../research/policy-learning/experiments/EX-197-laya-one-turn-read-vs-foulplay.md) | laya 한 턴 읽기 선택 대 foul-play, Blim 128경기(CPU) | Completed |
| [EX-198](../research/policy-learning/experiments/EX-198-laya-v12-foe-argmax-vs-foulplay.md) | laya v12 + 상대 예측(EX-196) argmax 대 foul-play, Blim 128경기(CPU) | Completed |
| [EX-201](../research/policy-learning/experiments/EX-201-laya-engine-value-vs-foulplay-unlimited.md) | laya 엔진 가치 학습(EX-200) argmax 대 foul-play, Blim 128경기, 시간 제한 없음(CPU) | Completed |
| [EX-202](../research/policy-learning/experiments/EX-202-laya-v12-foe-vs-foulplay-unlimited.md) | laya v12 + 상대 예측(EX-196) argmax 대 foul-play, Blim 128경기, 시간 제한 없음(CPU) | Completed |
| [EX-203](../research/policy-learning/experiments/EX-203-laya-engine-value-ladder.md) | v12 엔진 가치 학습(EX-200) 공식 Showdown gen9ou 래더 대전(GPU 서빙, 2026-11-23 08:00 KST까지) | Completed |
| [EX-204](../research/policy-learning/experiments/EX-204-laya-engine-value-ladder-loss-analysis.md) | EX-203 래더 고레이팅(1500 이상) 패배 원인 분석(CPU) | Completed |
| [EX-205](../research/policy-learning/experiments/EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md) | laya v13 입력 교정(무재학습 EX-200) argmax 대 foul-play, Blim 128경기, 시간 제한 없음(CPU) | Completed |
| [EX-206](../research/policy-learning/experiments/EX-206-laya-search-2a-vs-foulplay-unlimited.md) | 2-A 온라인 다중턴 탐색(EX-200 + v13 + GPU 0 서빙 + MCTS 5k 사전확률 융합) 대 foul-play, Blim 128경기(시간 제한 없음) | Completed |
| [EX-208](../research/policy-learning/experiments/EX-208-laya-search-2b-vs-foulplay-unlimited.md) | 2-B 온라인 다중턴 탐색 + 신경망 상태가치 V_phi 결합 대 foul-play, Blim 128경기(시간 제한 없음) | Completed |
| [EX-210](../research/policy-learning/experiments/EX-210-laya-mcts5k-q-rerank-1b-vs-foulplay-unlimited.md) | 1-B 오프라인 MCTS-5k Q 재정렬 학습 모델(EX-209, v13 단일 forward) 대 foul-play, Blim 128경기(시간 제한 없음) | Completed |
| [EX-212](../research/policy-learning/experiments/EX-212-laya-search-2bv2-vs-foulplay-unlimited.md) | 2-B v2 탐색 개선(foe PP 파싱 수정·스케일 정규화·duel lose 완화·Taunt 흡수 보정, CPU 서빙) 대 foul-play, Blim 128경기 | Stopped |
| [EX-214](../research/policy-learning/experiments/EX-214-laya-v14-search2bv2-vs-foulplay-unlimited.md) | v14 학습 모델(EX-213) + 2-B v2 온라인 탐색 결합 대 foul-play, Blim 128경기 | Planned |
| [EX-217](../research/policy-learning/experiments/EX-217-laya-main-waya-mcts50k-vphiv2-vs-foulplay.md) | 방식 A(Laya 메인 합의형 블런더 가드 + MCTS 50k + V_phi v2 + 렌더러 무효 대면 수정) 대 foul-play, Blim 128경기 | Completed |
| [EX-219](../research/policy-learning/experiments/EX-219-laya-way-c1-vs-foulplay-unlimited.md) | 방식 C-1 학습 모델(EX-218, v14+walled_duel) 대 foul-play, Blim 128경기 | Planned |

## 평가 / 배틀32

| ID | 제목 | 상태 |
|---|---|---|
| [EX-119](../research/policy-learning/experiments/EX-119-laya-compact-imitation-battle32.md) | laya 압축 입력 모방 모델 EX-089 표준 32경기 | Completed |

## 평가 / 서빙 기술 검증

| ID | 제목 | 상태 |
|---|---|---|
| [EP-190](../research/rule-learning/plans/EP-190-jevk5-vllm-serving-check.md) | JevK5 추가 LoRA vLLM 서빙 확인 | Completed |

## 평가 / 오프라인 QA

| ID | 제목 | 상태 |
|---|---|---|
| [D-159](../research/rule-learning/decisions/D-159-showdown-ruleqa.md) | Showdown 규칙 Q&A 데이터셋 v1 | Accepted |
| [D-161](../research/rule-learning/decisions/D-161-tacit-ruleqa-lora.md) | Tacit 규칙 Q&A LoRA 1회 | Accepted |
| [EP-169](../research/rule-learning/plans/EP-169-showdown-ruleqa.md) | Showdown 규칙 Q&A·State 데이터셋 v1 | Completed |
| [EP-173](../research/rule-learning/plans/EP-173-tacit-ruleqa-lora.md) | Tacit 규칙 Q&A LoRA | Completed |
| [EX-107](../research/rule-learning/experiments/EX-107-tacit-ruleqa-lora.md) | Tacit-9B 규칙 Q&A LoRA | Completed |

## 평가 / 오프라인 진단

| ID | 제목 | 상태 |
|---|---|---|
| [EX-222](../research/policy-learning/experiments/EX-222-multiturn-2ply-waya-v2-ab.md) | 다수 턴 2-ply Top-K 탐색기 + Way A v2 가드레일 오프라인 A/B 진단 | Completed |

## 평가 / 정보 제거

| ID | 제목 | 상태 |
|---|---|---|
| [D-092](../research/input-and-memory/decisions/D-092-jev-offline-input.md) | JEV 오프라인 입력 표현 개선 | Accepted |
| [D-095](../research/input-and-memory/decisions/D-095-jev-compact32.md) | 자기 벤치 축약 동일32경기 | Accepted |
| [D-137](../research/input-and-memory/decisions/D-137-jev9b-no-damage.md) | JEV-9B 피해 예측 제거 평가 | Accepted |
| [EP-093](../research/input-and-memory/plans/EP-093-jev-offline-input.md) | JEV 입력 표현 개선·오프라인 검증 | Completed |
| [EP-095](../research/input-and-memory/plans/EP-095-jev-compact32.md) | 자기 벤치 축약 동일32경기 | Completed |
| [EP-143](../research/input-and-memory/plans/EP-143-jev9b-no-damage.md) | JEV-9B 피해 예측 제거와 EX-089 비교 | Completed |
| [EX-058](../research/input-and-memory/experiments/EX-058-jev-improved32.md) | 개선 JEV 입력 동일32경기 | Completed |
| [EX-059](../research/input-and-memory/experiments/EX-059-jev-compact32.md) | 자기 벤치 축약 JEV 입력 동일32경기 | Completed |
| [EX-090](../research/input-and-memory/experiments/EX-090-jev9b-no-damage.md) | JEV-9B 피해 예측 제거 신규32경기 | Completed |

## 학습 / LoRA

| ID | 제목 | 상태 |
|---|---|---|
| [D-098](../research/action-value/decisions/D-098-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 첫 행동가치 학습 | Accepted |
| [D-127](../research/fixed-matchup-learning/decisions/D-127-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Accepted |
| [D-161](../research/rule-learning/decisions/D-161-tacit-ruleqa-lora.md) | Tacit 규칙 Q&A LoRA 1회 | Accepted |
| [D-169](../research/rule-learning/decisions/D-169-jevk5-ruleqa-lora.md) | JevK5 규칙 선택형 추가 LoRA | Accepted |
| [D-180](../research/rule-learning/decisions/D-180-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Accepted |
| [EP-102](../research/action-value/plans/EP-102-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 첫 학습 검증 | Completed |
| [EP-108](../research/action-value/plans/EP-108-joint-q-training.md) | EX-065 기반 Base 공동 q 학습 | Blocked |
| [EP-115](../research/policy-learning/plans/EP-115-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EP-116](../research/policy-learning/plans/EP-116-selfplay-rlcd.md) | 자기대국과 RLCD 확률 보정 | Completed |
| [EP-132](../research/fixed-matchup-learning/plans/EP-132-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 자기대국 학습 실행 | Completed |
| [EP-133](../research/action-value/plans/EP-133-joint-q-battle.md) | EX066 epoch3의 GPU0 실제 배틀 평가 | Completed |
| [EP-173](../research/rule-learning/plans/EP-173-tacit-ruleqa-lora.md) | Tacit 규칙 Q&A LoRA | Completed |
| [EP-184](../research/rule-learning/plans/EP-184-jevk5-ruleqa-lora.md) | JevK5 규칙 선택형 추가 LoRA | Completed |
| [EP-203](../research/rule-learning/plans/EP-203-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |
| [EX-061](../research/action-value/experiments/EX-061-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 행동가치 개발 실험 | Completed |
| [EX-066](../research/action-value/experiments/EX-066-joint-q-training.md) | Qwen3.5-4B-Base 공동 q 학습·독립 평가 | Blocked — 새 프로세스 재로딩 gate 실패 |
| [EX-071](../research/policy-learning/experiments/EX-071-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EX-107](../research/rule-learning/experiments/EX-107-tacit-ruleqa-lora.md) | Tacit-9B 규칙 Q&A LoRA | Completed |
| [EX-113](../research/rule-learning/experiments/EX-113-jevk5-ruleqa-lora.md) | JevK5-9B 규칙 선택형 추가 LoRA | Completed |
| [EX-116](../research/rule-learning/experiments/EX-116-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |

## 학습 / RLCD

| ID | 제목 | 상태 |
|---|---|---|
| [D-096](../research/policy-learning/decisions/D-096-pokemon-training-objective.md) | 세 RLCD 환경을 활용한 포켓몬 전용 학습 당면 목표 채택 | Accepted |
| [D-112](../research/policy-learning/decisions/D-112-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 채택 | Accepted |
| [D-114](../research/policy-learning/decisions/D-114-selfplay-rlcd.md) | 단일 GPU 자기대국과 선택 행동 확률 보정 | Accepted |
| [EP-099](../research/policy-learning/plans/EP-099-pokemon-training-objective.md) | 포켓몬 전용 모델 학습 당면 목표 문서화 | Completed |
| [EP-102](../research/action-value/plans/EP-102-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 첫 학습 검증 | Completed |
| [EP-116](../research/policy-learning/plans/EP-116-selfplay-rlcd.md) | 자기대국과 RLCD 확률 보정 | Completed |
| [EX-072](../research/policy-learning/experiments/EX-072-selfplay-rlcd.md) | 자기대국과 RLCD 확률 보정: 단일 GPU 24시간 | Completed — 실험 완료, 성능 개선 미입증 |

## 학습 / SFT

| ID | 제목 | 상태 |
|---|---|---|
| [D-224](../research/policy-learning/decisions/D-224-batch-b-waya-v2-ladder-wayc1-clean-wayb.md) | 배치 B 병행 실행: EX-223 방식 A v2 공식 래더(EX-224) + 정화 교사 방식 C-1(EX-225) → 프롬프트 도구 주입 방식 B(EX-226) DDP 자동 연쇄 | Accepted |
| [EP-248](../research/policy-learning/plans/EP-248-batch-b-waya-v2-ladder-wayc1-clean-wayb.md) | 배치 B: EX-223 방식 A v2 공식 래더 병행 + 정화 방식 C-1 → 방식 B GPU 0·1 DDP 자동 연쇄 | Completed |
| [EX-107](../research/rule-learning/experiments/EX-107-tacit-ruleqa-lora.md) | Tacit-9B 규칙 Q&A LoRA | Completed |
| [EX-226](../research/policy-learning/experiments/EX-226-laya-way-b-tool-inject-train.md) | 방식 B: calc-duel-free + MCTS50k/V_phi v3 5단계 matchup & eval 프롬프트 주입 + 35% Tool Dropout + 인간 앵커 보존 학습 (GPU 0·1 DDP) | Completed |

## 학습 / System1

| ID | 제목 | 상태 |
|---|---|---|
| [D-180](../research/rule-learning/decisions/D-180-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Accepted |
| [EP-203](../research/rule-learning/plans/EP-203-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |
| [EX-116](../research/rule-learning/experiments/EX-116-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |

## 학습 / laya

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
| [D-198](../research/policy-learning/decisions/D-198-laya-past-turn-input-v6.md) | laya 과거 턴 입력 두 가지(v6s 반복 표시·v6h 긴 기록 2048토큰) 동시 학습과 배틀 | Accepted |
| [D-200](../research/policy-learning/decisions/D-200-laya-loop-break-opponent-sets.md) | laya 손해 루프 탈출(학습 가중·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험 | Accepted |
| [D-201](../research/policy-learning/decisions/D-201-laya-engine-judge-v8.md) | laya 실패 표시를 고정 Showdown 엔진 판정기로 바꾼 렌더러 v8 | Accepted |
| [D-202](../research/policy-learning/decisions/D-202-laya-opponent-threat-v9.md) | laya 상대 가정 세트 노력치 보정과 최악 피해 표시(렌더러 v9) | Accepted |
| [D-204](../research/policy-learning/decisions/D-204-laya-renderer-v10-all-info.md) | laya 렌더러 v10: 지금까지의 정보 전부 + lock + 전략 정보, 2,048토큰 | Accepted |
| [D-208](../research/policy-learning/decisions/D-208-laya-ladder-r1500-v10.md) | 최근 래더(레이팅 1500 이상) 리플레이를 더한 v10 학습(GPU 4장 DDP, 24시간) | Accepted |
| [D-209](../research/policy-learning/decisions/D-209-laya-ladder-postmortem-v11.md) | laya v10rt 공식 래더 패배 원인 추가 분석과 재학습 v11(입력 수정·정책 교정) 설계 | Accepted |
| [D-210](../research/policy-learning/decisions/D-210-laya-v11rtc-policy-correction-values.md) | v11rtc 정책 교정 수단 확정(EX-169 결과 적용)과 가중 배수 보정 | Accepted |
| [D-213](../research/policy-learning/decisions/D-213-laya-fp1-foulplay-input.md) | laya 입력을 foul-play 추적·poke-engine 계산으로 전부 바꾼 렌더러 fp1과 처음부터 전체 학습 | Accepted |
| [D-215](../research/policy-learning/decisions/D-215-laya-foulplay-distill-then-rl.md) | v11rtc에 foul-play 탐색을 증류한 뒤, foul-play 상대 강화학습으로 다듬는다 | Accepted |
| [D-216](../research/policy-learning/decisions/D-216-laya-opponent-prediction-one-turn-read.md) | laya 상대 행동 예측 학습과 한 턴 읽기 | Accepted |
| [D-217](../research/policy-learning/decisions/D-217-laya-engine-value-rerank-training.md) | foul-play 엔진 평가로 laya 후보 순위를 다시 매긴 target 학습 | Accepted |
| [EP-208](../research/policy-learning/plans/EP-208-laya-compact-imitation.md) | laya 압축 입력 모방 학습·배틀 에이전트 | Completed |
| [EP-210](../research/policy-learning/plans/EP-210-laya-renderer-v2.md) | laya 모듈형 렌더러 v2 학습과 v1·v2 비교 | Completed |
| [EP-212](../research/policy-learning/plans/EP-212-laya-tera-knowledge.md) | laya v2 테라 지식 데이터 학습과 배틀 비교(GPU1) | Completed |
| [EP-213](../research/policy-learning/plans/EP-213-laya-effect-knowledge.md) | laya v2+테라+효과 지식 데이터 학습과 배틀 비교(GPU2) | Completed |
| [EP-214](../research/policy-learning/plans/EP-214-laya-renderer-v3.md) | laya 렌더러 v3(상대 세트 추론) 학습과 배틀 비교(GPU0) | Completed |
| [EP-215](../research/policy-learning/plans/EP-215-laya-renderer-v4.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) 학습과 배틀 비교(GPU1) | Completed |
| [EP-216](../research/policy-learning/plans/EP-216-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방 학습과 배틀 비교(GPU0) | Completed |
| [EP-218](../research/policy-learning/plans/EP-218-laya-renderer-v5-item-state.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) 학습과 배틀 비교(GPU0·GPU2) | Completed |
| [EP-221](../research/policy-learning/plans/EP-221-laya-past-turn-input-v6.md) | laya 과거 턴 입력 v6s·v6h 동시 학습과 배틀 비교(GPU0·GPU1) | Completed |
| [EP-223](../research/policy-learning/plans/EP-223-laya-loop-break-opponent-sets.md) | laya 손해 루프 탈출(가중 학습·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험(GPU0~3) | Completed |
| [EP-224](../research/policy-learning/plans/EP-224-laya-engine-judge-v8.md) | laya 엔진 판정기(고정 Showdown 실패 판정)와 렌더러 v8 학습·배틀(GPU1·GPU2) | Completed |
| [EP-225](../research/policy-learning/plans/EP-225-laya-opponent-threat-v9.md) | laya 상대 노력치 보정·최악 피해 표시 렌더러 v9 학습·배틀(GPU3) | Completed |
| [EP-227](../research/policy-learning/plans/EP-227-laya-renderer-v10.md) | laya 렌더러 v10(정보 전부 + lock + 전략, 2,048토큰) 학습과 Abyssal 배틀 | Completed |
| [EP-230](../research/policy-learning/plans/EP-230-laya-ladder-r1500-v10.md) | 최근 래더(레이팅 1500 이상) 리플레이 자료와 v10 학습(GPU 4장 DDP), Abyssal 배틀 | Completed |
| [EP-231](../research/policy-learning/plans/EP-231-laya-ladder-postmortem-v11.md) | laya v10rt 공식 래더 패배 원인 추가 분석과 재학습 v11(v11rt·v11rtc) | Active |
| [EP-234](../research/policy-learning/plans/EP-234-laya-fp1-foulplay-input.md) | laya fp1 렌더러(foul-play 기반 입력) 자료·처음부터 전체 학습·foul-play 배틀 | Active |
| [EP-236](../research/policy-learning/plans/EP-236-laya-v11rtc-foulplay-distill-rl.md) | v11rtc에 foul-play 탐색 증류 → foul-play 상대 강화학습 → foul-play·공식 래더 평가 | Paused |
| [EP-238](../research/policy-learning/plans/EP-238-laya-opponent-prediction-one-turn-read.md) | laya 상대 행동 예측 학습 → 한 턴 읽기 선택 → 입력 통합 | Completed |
| [EP-239](../research/policy-learning/plans/EP-239-laya-engine-value-rerank-training.md) | foul-play 엔진 평가 target 학습과 시간 제한 없는 foul-play 평가 | Completed |
| [EX-118](../research/policy-learning/experiments/EX-118-laya-compact-imitation-training.md) | laya 압축 입력 리플레이 모방 학습 | Completed |
| [EX-121](../research/policy-learning/experiments/EX-121-laya-v2-all-training.md) | laya 모듈형 렌더러 v2(4종 전부) 학습과 v1 쌍비교 | Completed |
| [EX-124](../research/policy-learning/experiments/EX-124-laya-v2-tera-knowledge-training.md) | laya v2 + 테라 기본 지식 데이터 학습(GPU1) | Completed |
| [EX-126](../research/policy-learning/experiments/EX-126-laya-v2-tera-effect-training.md) | laya v2 + 테라 + 효과 지식 데이터 학습(GPU2) | Completed |
| [EX-128](../research/policy-learning/experiments/EX-128-laya-v3-tera-training.md) | laya 렌더러 v3(상대 세트 추론) + 테라 지식 학습(GPU0) | Completed |
| [EX-130](../research/policy-learning/experiments/EX-130-laya-v4-tera-training.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) + 테라 지식 학습(GPU1) | Completed |
| [EX-132](../research/policy-learning/experiments/EX-132-laya-v2t-outcome-weighted-training.md) | laya v2+테라 승패 가중 모방 학습(GPU0) | Completed |
| [EX-136](../research/policy-learning/experiments/EX-136-laya-v5-tera-training.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) + 테라 지식 학습(GPU0) | Completed |
| [EX-141](../research/policy-learning/experiments/EX-141-laya-v6s-streaks-training.md) | laya 렌더러 v6s(같은 기술 반복 표시) + 테라 지식 학습(GPU0) | Completed |
| [EX-142](../research/policy-learning/experiments/EX-142-laya-v6h-long-history-training.md) | laya 렌더러 v6h(긴 과거 기록, 2048토큰) + 테라 지식 학습(GPU1) | Completed |
| [EX-146](../research/policy-learning/experiments/EX-146-laya-v6sl-loop-weighted-training.md) | laya v6s + 루프 탈출 행 가중 학습(v6sl, GPU1) | Completed |
| [EX-149](../research/policy-learning/experiments/EX-149-laya-v7-opponent-sets-training.md) | laya 렌더러 v7(v6s + 상대 세트 추정 `oppset2`, Protean 실패 표시 보정) 학습(GPU0) | Completed |
| [EX-152](../research/policy-learning/experiments/EX-152-laya-v8-engine-fails-training.md) | laya 렌더러 v8(v7 + 엔진 판정기 실패 표시) 학습(GPU1) | Completed |
| [EX-155](../research/policy-learning/experiments/EX-155-laya-v8l-likely-fails-training.md) | laya 렌더러 v8l(v8 + `likely fails` 표시) 학습(GPU2) | Completed |
| [EX-157](../research/policy-learning/experiments/EX-157-laya-v9-opponent-threat-training.md) | laya 렌더러 v9(v7 + 상대 노력치 보정·최악 피해 표시) 학습(GPU3) | Completed |
| [EX-161](../research/policy-learning/experiments/EX-161-laya-v10-all-info-training.md) | laya 렌더러 v10(정보 전부 + lock + 전략, 2,048토큰) 학습(GPU0) | Completed |
| [EX-167](../research/policy-learning/experiments/EX-167-laya-v10-ladder-training.md) | laya v10 + 최근 래더 자료 학습(GPU 4장 DDP, 약 24시간) | Completed |
| [EX-171](../research/policy-learning/experiments/EX-171-laya-v11rt-training.md) | laya v11rt 학습(v10rt + 입력 수정, 1 epoch) | Completed |
| [EX-172](../research/policy-learning/experiments/EX-172-laya-v11rtc-training.md) | laya v11rtc 학습(v10rt + 입력 수정 + 정책 교정, 1 epoch) | Completed |
| [EX-178](../research/policy-learning/experiments/EX-178-laya-fp1-training.md) | laya fp1 처음부터 전체 학습(GPU 4장 DDP, 약 24시간) | Completed |
| [EX-183](../research/policy-learning/experiments/EX-183-laya-v11rtc-distill-training.md) | v11rtc + foul-play 탐색 증류 학습(1 epoch, GPU 4장) | Completed |
| [EX-186](../research/policy-learning/experiments/EX-186-laya-distill-foulplay-rl.md) | 증류 모델에서 시작하는 foul-play 상대 강화학습(KL 제약, 학습 팀) | Paused |
| [EX-196](../research/policy-learning/experiments/EX-196-laya-v12-foe-training.md) | laya v12 + 상대 예측 이어 학습(EX-192에서 1 epoch, GPU 4장) | Completed |
| [EX-199](../research/policy-learning/experiments/EX-199-laya-engine-value-targets.md) | laya 후보의 foul-play 엔진 한 턴 가치와 soft target 자료(CPU·GPU) | Completed |
| [EX-200](../research/policy-learning/experiments/EX-200-laya-engine-value-training.md) | laya 엔진 가치 target 이어 학습(EX-196에서 1 epoch, GPU 4장) | Completed |

## 학습 / soft-CE

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
| [D-198](../research/policy-learning/decisions/D-198-laya-past-turn-input-v6.md) | laya 과거 턴 입력 두 가지(v6s 반복 표시·v6h 긴 기록 2048토큰) 동시 학습과 배틀 | Accepted |
| [D-200](../research/policy-learning/decisions/D-200-laya-loop-break-opponent-sets.md) | laya 손해 루프 탈출(학습 가중·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험 | Accepted |
| [D-201](../research/policy-learning/decisions/D-201-laya-engine-judge-v8.md) | laya 실패 표시를 고정 Showdown 엔진 판정기로 바꾼 렌더러 v8 | Accepted |
| [D-202](../research/policy-learning/decisions/D-202-laya-opponent-threat-v9.md) | laya 상대 가정 세트 노력치 보정과 최악 피해 표시(렌더러 v9) | Accepted |
| [D-204](../research/policy-learning/decisions/D-204-laya-renderer-v10-all-info.md) | laya 렌더러 v10: 지금까지의 정보 전부 + lock + 전략 정보, 2,048토큰 | Accepted |
| [D-213](../research/policy-learning/decisions/D-213-laya-fp1-foulplay-input.md) | laya 입력을 foul-play 추적·poke-engine 계산으로 전부 바꾼 렌더러 fp1과 처음부터 전체 학습 | Accepted |
| [EP-208](../research/policy-learning/plans/EP-208-laya-compact-imitation.md) | laya 압축 입력 모방 학습·배틀 에이전트 | Completed |
| [EP-210](../research/policy-learning/plans/EP-210-laya-renderer-v2.md) | laya 모듈형 렌더러 v2 학습과 v1·v2 비교 | Completed |
| [EP-212](../research/policy-learning/plans/EP-212-laya-tera-knowledge.md) | laya v2 테라 지식 데이터 학습과 배틀 비교(GPU1) | Completed |
| [EP-213](../research/policy-learning/plans/EP-213-laya-effect-knowledge.md) | laya v2+테라+효과 지식 데이터 학습과 배틀 비교(GPU2) | Completed |
| [EP-214](../research/policy-learning/plans/EP-214-laya-renderer-v3.md) | laya 렌더러 v3(상대 세트 추론) 학습과 배틀 비교(GPU0) | Completed |
| [EP-215](../research/policy-learning/plans/EP-215-laya-renderer-v4.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) 학습과 배틀 비교(GPU1) | Completed |
| [EP-216](../research/policy-learning/plans/EP-216-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방 학습과 배틀 비교(GPU0) | Completed |
| [EP-218](../research/policy-learning/plans/EP-218-laya-renderer-v5-item-state.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) 학습과 배틀 비교(GPU0·GPU2) | Completed |
| [EP-221](../research/policy-learning/plans/EP-221-laya-past-turn-input-v6.md) | laya 과거 턴 입력 v6s·v6h 동시 학습과 배틀 비교(GPU0·GPU1) | Completed |
| [EP-223](../research/policy-learning/plans/EP-223-laya-loop-break-opponent-sets.md) | laya 손해 루프 탈출(가중 학습·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험(GPU0~3) | Completed |
| [EP-224](../research/policy-learning/plans/EP-224-laya-engine-judge-v8.md) | laya 엔진 판정기(고정 Showdown 실패 판정)와 렌더러 v8 학습·배틀(GPU1·GPU2) | Completed |
| [EP-225](../research/policy-learning/plans/EP-225-laya-opponent-threat-v9.md) | laya 상대 노력치 보정·최악 피해 표시 렌더러 v9 학습·배틀(GPU3) | Completed |
| [EP-227](../research/policy-learning/plans/EP-227-laya-renderer-v10.md) | laya 렌더러 v10(정보 전부 + lock + 전략, 2,048토큰) 학습과 Abyssal 배틀 | Completed |
| [EP-230](../research/policy-learning/plans/EP-230-laya-ladder-r1500-v10.md) | 최근 래더(레이팅 1500 이상) 리플레이 자료와 v10 학습(GPU 4장 DDP), Abyssal 배틀 | Completed |
| [EP-231](../research/policy-learning/plans/EP-231-laya-ladder-postmortem-v11.md) | laya v10rt 공식 래더 패배 원인 추가 분석과 재학습 v11(v11rt·v11rtc) | Active |
| [EP-234](../research/policy-learning/plans/EP-234-laya-fp1-foulplay-input.md) | laya fp1 렌더러(foul-play 기반 입력) 자료·처음부터 전체 학습·foul-play 배틀 | Active |
| [EX-118](../research/policy-learning/experiments/EX-118-laya-compact-imitation-training.md) | laya 압축 입력 리플레이 모방 학습 | Completed |
| [EX-121](../research/policy-learning/experiments/EX-121-laya-v2-all-training.md) | laya 모듈형 렌더러 v2(4종 전부) 학습과 v1 쌍비교 | Completed |
| [EX-124](../research/policy-learning/experiments/EX-124-laya-v2-tera-knowledge-training.md) | laya v2 + 테라 기본 지식 데이터 학습(GPU1) | Completed |
| [EX-126](../research/policy-learning/experiments/EX-126-laya-v2-tera-effect-training.md) | laya v2 + 테라 + 효과 지식 데이터 학습(GPU2) | Completed |
| [EX-128](../research/policy-learning/experiments/EX-128-laya-v3-tera-training.md) | laya 렌더러 v3(상대 세트 추론) + 테라 지식 학습(GPU0) | Completed |
| [EX-130](../research/policy-learning/experiments/EX-130-laya-v4-tera-training.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) + 테라 지식 학습(GPU1) | Completed |
| [EX-132](../research/policy-learning/experiments/EX-132-laya-v2t-outcome-weighted-training.md) | laya v2+테라 승패 가중 모방 학습(GPU0) | Completed |
| [EX-136](../research/policy-learning/experiments/EX-136-laya-v5-tera-training.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) + 테라 지식 학습(GPU0) | Completed |
| [EX-141](../research/policy-learning/experiments/EX-141-laya-v6s-streaks-training.md) | laya 렌더러 v6s(같은 기술 반복 표시) + 테라 지식 학습(GPU0) | Completed |
| [EX-142](../research/policy-learning/experiments/EX-142-laya-v6h-long-history-training.md) | laya 렌더러 v6h(긴 과거 기록, 2048토큰) + 테라 지식 학습(GPU1) | Completed |
| [EX-146](../research/policy-learning/experiments/EX-146-laya-v6sl-loop-weighted-training.md) | laya v6s + 루프 탈출 행 가중 학습(v6sl, GPU1) | Completed |
| [EX-149](../research/policy-learning/experiments/EX-149-laya-v7-opponent-sets-training.md) | laya 렌더러 v7(v6s + 상대 세트 추정 `oppset2`, Protean 실패 표시 보정) 학습(GPU0) | Completed |
| [EX-152](../research/policy-learning/experiments/EX-152-laya-v8-engine-fails-training.md) | laya 렌더러 v8(v7 + 엔진 판정기 실패 표시) 학습(GPU1) | Completed |
| [EX-155](../research/policy-learning/experiments/EX-155-laya-v8l-likely-fails-training.md) | laya 렌더러 v8l(v8 + `likely fails` 표시) 학습(GPU2) | Completed |
| [EX-157](../research/policy-learning/experiments/EX-157-laya-v9-opponent-threat-training.md) | laya 렌더러 v9(v7 + 상대 노력치 보정·최악 피해 표시) 학습(GPU3) | Completed |
| [EX-161](../research/policy-learning/experiments/EX-161-laya-v10-all-info-training.md) | laya 렌더러 v10(정보 전부 + lock + 전략, 2,048토큰) 학습(GPU0) | Completed |
| [EX-167](../research/policy-learning/experiments/EX-167-laya-v10-ladder-training.md) | laya v10 + 최근 래더 자료 학습(GPU 4장 DDP, 약 24시간) | Completed |
| [EX-171](../research/policy-learning/experiments/EX-171-laya-v11rt-training.md) | laya v11rt 학습(v10rt + 입력 수정, 1 epoch) | Completed |
| [EX-172](../research/policy-learning/experiments/EX-172-laya-v11rtc-training.md) | laya v11rtc 학습(v10rt + 입력 수정 + 정책 교정, 1 epoch) | Completed |
| [EX-178](../research/policy-learning/experiments/EX-178-laya-fp1-training.md) | laya fp1 처음부터 전체 학습(GPU 4장 DDP, 약 24시간) | Completed |

## 학습 / 가치망

| ID | 제목 | 상태 |
|---|---|---|
| [D-223](../research/policy-learning/decisions/D-223-vphi-v3-future-horizon-and-multiturn-search.md) | 미래 영향력 반영 상태가치망 V_phi v3 및 다수 턴 2-ply 탐색 · Way A v2 가드레일 | Accepted |
| [EP-247](../research/policy-learning/plans/EP-247-vphi-v3-future-horizon-and-multiturn-search.md) | 미래 영향력 반영 가치함수 V_phi v3 및 2-ply 다수 턴 탐색 · Way A v2 검증 (GPU 0·1 전용) | Completed |
| [EX-221](../research/policy-learning/experiments/EX-221-laya-state-value-v3-future-train.md) | 미래 영향력 반영 상태가치망 V_phi v3 데이터 구축 및 학습 (GPU 0) | Completed |

## 학습 / 가치함수

| ID | 제목 | 상태 |
|---|---|---|
| [D-219](../research/policy-learning/decisions/D-219-laya-multiturn-search-and-value.md) | 1턴 시야·정적 가치 편향 극복을 위한 다중턴 탐색(2-A)·신경망 상태가치(2-B)·경량 MCTS-Q 재정렬 학습(1-B) (GPU 0·1 전용) | Accepted |
| [D-221](../research/policy-learning/decisions/D-221-laya-main-waya-mcts50k-vphi-v2.md) | Laya 메인 합의형 블런더 가드(방식 A), MCTS 50k 심화, 상성·도구·특성·기술 반영 가치망 V_phi v2 및 렌더러 무효 대면 보완 | Accepted |
| [EP-243](../research/policy-learning/plans/EP-243-laya-multiturn-search-value-distill.md) | 다중턴 온라인 탐색(2-A)·신경망 상태가치(2-B)·경량 MCTS-Q 재정렬 학습(1-B) (GPU 0·1 전용) | Active |
| [EP-245](../research/policy-learning/plans/EP-245-laya-main-blunder-veto-mcts50k-vphi-v2.md) | Laya 메인 합의형 블런더 가드(방식 A): 상성·도구·특성·기술 반영 V_phi v2 보강 및 MCTS 50k 결합 (GPU 0·1 전용) | Completed |
| [EX-207](../research/policy-learning/experiments/EX-207-laya-state-value-2b-train.md) | 2-B 리플레이 승패 기반 신경망 상태가치 모델 V_phi(poke_engine.State) 데이터 추출 및 학습(GPU 0·1) | Completed |
| [EX-208](../research/policy-learning/experiments/EX-208-laya-search-2b-vs-foulplay-unlimited.md) | 2-B 온라인 다중턴 탐색 + 신경망 상태가치 V_phi 결합 대 foul-play, Blim 128경기(시간 제한 없음) | Completed |
| [EX-216](../research/policy-learning/experiments/EX-216-laya-state-value-v2-matchup-train.md) | 상성·도구·특성·기술 기계적 매치업 피처 반영 상태가치망 V_phi v2 학습 및 검증 (GPU 0) | Completed |

## 학습 / 강화학습

| ID | 제목 | 상태 |
|---|---|---|
| [D-215](../research/policy-learning/decisions/D-215-laya-foulplay-distill-then-rl.md) | v11rtc에 foul-play 탐색을 증류한 뒤, foul-play 상대 강화학습으로 다듬는다 | Accepted |
| [EP-236](../research/policy-learning/plans/EP-236-laya-v11rtc-foulplay-distill-rl.md) | v11rtc에 foul-play 탐색 증류 → foul-play 상대 강화학습 → foul-play·공식 래더 평가 | Paused |
| [EX-186](../research/policy-learning/experiments/EX-186-laya-distill-foulplay-rl.md) | 증류 모델에서 시작하는 foul-play 상대 강화학습(KL 제약, 학습 팀) | Paused |

## 학습 / 공동 q

| ID | 제목 | 상태 |
|---|---|---|
| [EX-066](../research/action-value/experiments/EX-066-joint-q-training.md) | Qwen3.5-4B-Base 공동 q 학습·독립 평가 | Blocked — 새 프로세스 재로딩 gate 실패 |

## 학습 / 규칙 데이터 생성

| ID | 제목 | 상태 |
|---|---|---|
| [EP-195](../research/rule-learning/plans/EP-195-gen9-status-system1-data.md) | Gen9 상태이상 System 1 학습자료 | Completed |
| [EP-196](../research/rule-learning/plans/EP-196-gen9-priority-system1-data.md) | Gen9 행동 우선도 System 1 자료 | Completed |
| [EP-197](../research/rule-learning/plans/EP-197-gen9-weather-terrain-system1-data.md) | Gen9 날씨·영역 System 1 자료 | Completed |

## 학습 / 리플레이 결과 지도

| ID | 제목 | 상태 |
|---|---|---|
| [D-175](../research/rule-learning/decisions/D-175-replay-ko-system1-data.md) | 실제 리플레이의 관측 KO 결과 학습자료 | Accepted |
| [EP-198](../research/rule-learning/plans/EP-198-replay-ko-system1-data.md) | 실제 리플레이 KO 결과 예측 System 1 자료 | Completed |

## 학습 / 모방

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
| [D-198](../research/policy-learning/decisions/D-198-laya-past-turn-input-v6.md) | laya 과거 턴 입력 두 가지(v6s 반복 표시·v6h 긴 기록 2048토큰) 동시 학습과 배틀 | Accepted |
| [D-200](../research/policy-learning/decisions/D-200-laya-loop-break-opponent-sets.md) | laya 손해 루프 탈출(학습 가중·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험 | Accepted |
| [D-201](../research/policy-learning/decisions/D-201-laya-engine-judge-v8.md) | laya 실패 표시를 고정 Showdown 엔진 판정기로 바꾼 렌더러 v8 | Accepted |
| [D-202](../research/policy-learning/decisions/D-202-laya-opponent-threat-v9.md) | laya 상대 가정 세트 노력치 보정과 최악 피해 표시(렌더러 v9) | Accepted |
| [D-204](../research/policy-learning/decisions/D-204-laya-renderer-v10-all-info.md) | laya 렌더러 v10: 지금까지의 정보 전부 + lock + 전략 정보, 2,048토큰 | Accepted |
| [D-208](../research/policy-learning/decisions/D-208-laya-ladder-r1500-v10.md) | 최근 래더(레이팅 1500 이상) 리플레이를 더한 v10 학습(GPU 4장 DDP, 24시간) | Accepted |
| [D-209](../research/policy-learning/decisions/D-209-laya-ladder-postmortem-v11.md) | laya v10rt 공식 래더 패배 원인 추가 분석과 재학습 v11(입력 수정·정책 교정) 설계 | Accepted |
| [D-210](../research/policy-learning/decisions/D-210-laya-v11rtc-policy-correction-values.md) | v11rtc 정책 교정 수단 확정(EX-169 결과 적용)과 가중 배수 보정 | Accepted |
| [D-213](../research/policy-learning/decisions/D-213-laya-fp1-foulplay-input.md) | laya 입력을 foul-play 추적·poke-engine 계산으로 전부 바꾼 렌더러 fp1과 처음부터 전체 학습 | Accepted |
| [EP-208](../research/policy-learning/plans/EP-208-laya-compact-imitation.md) | laya 압축 입력 모방 학습·배틀 에이전트 | Completed |
| [EP-210](../research/policy-learning/plans/EP-210-laya-renderer-v2.md) | laya 모듈형 렌더러 v2 학습과 v1·v2 비교 | Completed |
| [EP-212](../research/policy-learning/plans/EP-212-laya-tera-knowledge.md) | laya v2 테라 지식 데이터 학습과 배틀 비교(GPU1) | Completed |
| [EP-213](../research/policy-learning/plans/EP-213-laya-effect-knowledge.md) | laya v2+테라+효과 지식 데이터 학습과 배틀 비교(GPU2) | Completed |
| [EP-214](../research/policy-learning/plans/EP-214-laya-renderer-v3.md) | laya 렌더러 v3(상대 세트 추론) 학습과 배틀 비교(GPU0) | Completed |
| [EP-215](../research/policy-learning/plans/EP-215-laya-renderer-v4.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) 학습과 배틀 비교(GPU1) | Completed |
| [EP-216](../research/policy-learning/plans/EP-216-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방 학습과 배틀 비교(GPU0) | Completed |
| [EP-218](../research/policy-learning/plans/EP-218-laya-renderer-v5-item-state.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) 학습과 배틀 비교(GPU0·GPU2) | Completed |
| [EP-221](../research/policy-learning/plans/EP-221-laya-past-turn-input-v6.md) | laya 과거 턴 입력 v6s·v6h 동시 학습과 배틀 비교(GPU0·GPU1) | Completed |
| [EP-223](../research/policy-learning/plans/EP-223-laya-loop-break-opponent-sets.md) | laya 손해 루프 탈출(가중 학습·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험(GPU0~3) | Completed |
| [EP-224](../research/policy-learning/plans/EP-224-laya-engine-judge-v8.md) | laya 엔진 판정기(고정 Showdown 실패 판정)와 렌더러 v8 학습·배틀(GPU1·GPU2) | Completed |
| [EP-225](../research/policy-learning/plans/EP-225-laya-opponent-threat-v9.md) | laya 상대 노력치 보정·최악 피해 표시 렌더러 v9 학습·배틀(GPU3) | Completed |
| [EP-227](../research/policy-learning/plans/EP-227-laya-renderer-v10.md) | laya 렌더러 v10(정보 전부 + lock + 전략, 2,048토큰) 학습과 Abyssal 배틀 | Completed |
| [EP-230](../research/policy-learning/plans/EP-230-laya-ladder-r1500-v10.md) | 최근 래더(레이팅 1500 이상) 리플레이 자료와 v10 학습(GPU 4장 DDP), Abyssal 배틀 | Completed |
| [EP-231](../research/policy-learning/plans/EP-231-laya-ladder-postmortem-v11.md) | laya v10rt 공식 래더 패배 원인 추가 분석과 재학습 v11(v11rt·v11rtc) | Active |
| [EP-234](../research/policy-learning/plans/EP-234-laya-fp1-foulplay-input.md) | laya fp1 렌더러(foul-play 기반 입력) 자료·처음부터 전체 학습·foul-play 배틀 | Active |
| [EX-118](../research/policy-learning/experiments/EX-118-laya-compact-imitation-training.md) | laya 압축 입력 리플레이 모방 학습 | Completed |
| [EX-121](../research/policy-learning/experiments/EX-121-laya-v2-all-training.md) | laya 모듈형 렌더러 v2(4종 전부) 학습과 v1 쌍비교 | Completed |
| [EX-124](../research/policy-learning/experiments/EX-124-laya-v2-tera-knowledge-training.md) | laya v2 + 테라 기본 지식 데이터 학습(GPU1) | Completed |
| [EX-126](../research/policy-learning/experiments/EX-126-laya-v2-tera-effect-training.md) | laya v2 + 테라 + 효과 지식 데이터 학습(GPU2) | Completed |
| [EX-128](../research/policy-learning/experiments/EX-128-laya-v3-tera-training.md) | laya 렌더러 v3(상대 세트 추론) + 테라 지식 학습(GPU0) | Completed |
| [EX-130](../research/policy-learning/experiments/EX-130-laya-v4-tera-training.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) + 테라 지식 학습(GPU1) | Completed |
| [EX-132](../research/policy-learning/experiments/EX-132-laya-v2t-outcome-weighted-training.md) | laya v2+테라 승패 가중 모방 학습(GPU0) | Completed |
| [EX-136](../research/policy-learning/experiments/EX-136-laya-v5-tera-training.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) + 테라 지식 학습(GPU0) | Completed |
| [EX-141](../research/policy-learning/experiments/EX-141-laya-v6s-streaks-training.md) | laya 렌더러 v6s(같은 기술 반복 표시) + 테라 지식 학습(GPU0) | Completed |
| [EX-142](../research/policy-learning/experiments/EX-142-laya-v6h-long-history-training.md) | laya 렌더러 v6h(긴 과거 기록, 2048토큰) + 테라 지식 학습(GPU1) | Completed |
| [EX-146](../research/policy-learning/experiments/EX-146-laya-v6sl-loop-weighted-training.md) | laya v6s + 루프 탈출 행 가중 학습(v6sl, GPU1) | Completed |
| [EX-149](../research/policy-learning/experiments/EX-149-laya-v7-opponent-sets-training.md) | laya 렌더러 v7(v6s + 상대 세트 추정 `oppset2`, Protean 실패 표시 보정) 학습(GPU0) | Completed |
| [EX-152](../research/policy-learning/experiments/EX-152-laya-v8-engine-fails-training.md) | laya 렌더러 v8(v7 + 엔진 판정기 실패 표시) 학습(GPU1) | Completed |
| [EX-155](../research/policy-learning/experiments/EX-155-laya-v8l-likely-fails-training.md) | laya 렌더러 v8l(v8 + `likely fails` 표시) 학습(GPU2) | Completed |
| [EX-157](../research/policy-learning/experiments/EX-157-laya-v9-opponent-threat-training.md) | laya 렌더러 v9(v7 + 상대 노력치 보정·최악 피해 표시) 학습(GPU3) | Completed |
| [EX-161](../research/policy-learning/experiments/EX-161-laya-v10-all-info-training.md) | laya 렌더러 v10(정보 전부 + lock + 전략, 2,048토큰) 학습(GPU0) | Completed |
| [EX-167](../research/policy-learning/experiments/EX-167-laya-v10-ladder-training.md) | laya v10 + 최근 래더 자료 학습(GPU 4장 DDP, 약 24시간) | Completed |
| [EX-171](../research/policy-learning/experiments/EX-171-laya-v11rt-training.md) | laya v11rt 학습(v10rt + 입력 수정, 1 epoch) | Completed |
| [EX-172](../research/policy-learning/experiments/EX-172-laya-v11rtc-training.md) | laya v11rtc 학습(v10rt + 입력 수정 + 정책 교정, 1 epoch) | Completed |
| [EX-178](../research/policy-learning/experiments/EX-178-laya-fp1-training.md) | laya fp1 처음부터 전체 학습(GPU 4장 DDP, 약 24시간) | Completed |
| [EX-192](../research/policy-learning/experiments/EX-192-laya-v12-training.md) | laya v12 처음부터 학습(GPU 4장 DDP, 3 epoch, 약 24시간) | Completed |

## 학습 / 모방 학습

| ID | 제목 | 상태 |
|---|---|---|
| [D-112](../research/policy-learning/decisions/D-112-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 채택 | Accepted |
| [D-113](../research/policy-learning/decisions/D-113-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Accepted |
| [D-115](../research/policy-learning/decisions/D-115-abyssal-first-objective.md) | Abyssal 상대 효율적 승리를 당면 단기 목표로 채택 | Accepted |
| [EP-114](../research/policy-learning/plans/EP-114-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 구체화 | Completed |
| [EP-115](../research/policy-learning/plans/EP-115-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EP-116](../research/policy-learning/plans/EP-116-selfplay-rlcd.md) | 자기대국과 RLCD 확률 보정 | Completed |
| [EX-071](../research/policy-learning/experiments/EX-071-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |

## 학습 / 본문 근거 역할 주석

| ID | 제목 | 상태 |
|---|---|---|
| [D-177](../research/rule-learning/decisions/D-177-smogon-role-system1-data.md) | Smogon 분석의 역할 근거 학습 | Accepted |
| [EP-200](../research/rule-learning/plans/EP-200-smogon-role-system1-data.md) | Smogon 전략 기반 역할 System 1 자료 | Completed |

## 학습 / 분류 데이터 생성

| ID | 제목 | 상태 |
|---|---|---|
| [EP-193](../research/rule-learning/plans/EP-193-gen9-type-system1-data.md) | Gen9 타입 System 1 판별 학습자료 | Completed |

## 학습 / 상대 모델

| ID | 제목 | 상태 |
|---|---|---|
| [D-216](../research/policy-learning/decisions/D-216-laya-opponent-prediction-one-turn-read.md) | laya 상대 행동 예측 학습과 한 턴 읽기 | Accepted |
| [EP-238](../research/policy-learning/plans/EP-238-laya-opponent-prediction-one-turn-read.md) | laya 상대 행동 예측 학습 → 한 턴 읽기 선택 → 입력 통합 | Completed |
| [EX-196](../research/policy-learning/experiments/EX-196-laya-v12-foe-training.md) | laya v12 + 상대 예측 이어 학습(EX-192에서 1 epoch, GPU 4장) | Completed |

## 학습 / 선택지 교차엔트로피

| ID | 제목 | 상태 |
|---|---|---|
| [D-175](../research/rule-learning/decisions/D-175-replay-ko-system1-data.md) | 실제 리플레이의 관측 KO 결과 학습자료 | Accepted |
| [D-176](../research/rule-learning/decisions/D-176-conditional-ko-system1-data.md) | 조건부 KO와 관측 KO의 분리 | Accepted |
| [D-177](../research/rule-learning/decisions/D-177-smogon-role-system1-data.md) | Smogon 분석의 역할 근거 학습 | Accepted |
| [D-178](../research/rule-learning/decisions/D-178-gen9-mechanics-system1-data.md) | 우선순위별 규칙 적용과 정보 충분성 자료 | Accepted |
| [EP-193](../research/rule-learning/plans/EP-193-gen9-type-system1-data.md) | Gen9 타입 System 1 판별 학습자료 | Completed |
| [EP-195](../research/rule-learning/plans/EP-195-gen9-status-system1-data.md) | Gen9 상태이상 System 1 학습자료 | Completed |
| [EP-196](../research/rule-learning/plans/EP-196-gen9-priority-system1-data.md) | Gen9 행동 우선도 System 1 자료 | Completed |
| [EP-197](../research/rule-learning/plans/EP-197-gen9-weather-terrain-system1-data.md) | Gen9 날씨·영역 System 1 자료 | Completed |
| [EP-198](../research/rule-learning/plans/EP-198-replay-ko-system1-data.md) | 실제 리플레이 KO 결과 예측 System 1 자료 | Completed |
| [EP-199](../research/rule-learning/plans/EP-199-conditional-ko-system1-data.md) | 조건부 확정 KO 판정 자료 | Completed |
| [EP-200](../research/rule-learning/plans/EP-200-smogon-role-system1-data.md) | Smogon 전략 기반 역할 System 1 자료 | Completed |
| [EP-201](../research/rule-learning/plans/EP-201-gen9-mechanics-system1-data.md) | 우선순위별 Gen9 규칙 적용 System 1 자료 | Completed |
| [EX-113](../research/rule-learning/experiments/EX-113-jevk5-ruleqa-lora.md) | JevK5-9B 규칙 선택형 추가 LoRA | Completed |

## 학습 / 자기대국

| ID | 제목 | 상태 |
|---|---|---|
| [D-112](../research/policy-learning/decisions/D-112-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 채택 | Accepted |
| [D-113](../research/policy-learning/decisions/D-113-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Accepted |
| [D-114](../research/policy-learning/decisions/D-114-selfplay-rlcd.md) | 단일 GPU 자기대국과 선택 행동 확률 보정 | Accepted |
| [D-115](../research/policy-learning/decisions/D-115-abyssal-first-objective.md) | Abyssal 상대 효율적 승리를 당면 단기 목표로 채택 | Accepted |
| [D-119](../research/fixed-matchup-learning/decisions/D-119-fixed-matchup-mcts.md) | 고정 대진 공개 상태 MCTS 정책 학습 | Accepted |
| [D-127](../research/fixed-matchup-learning/decisions/D-127-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Accepted |
| [EP-114](../research/policy-learning/plans/EP-114-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 구체화 | Completed |
| [EP-115](../research/policy-learning/plans/EP-115-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EP-116](../research/policy-learning/plans/EP-116-selfplay-rlcd.md) | 자기대국과 RLCD 확률 보정 | Completed |
| [EP-118](../research/policy-learning/plans/EP-118-abyssal-first-objective.md) | Abyssal 우선 단기 목표 정비 | Completed |
| [EP-127](../research/fixed-matchup-learning/plans/EP-127-fixed-matchup-first-round.md) | 첫1라운드 학습 | Blocked — 원실행1경기 시간초과·학습0; 시간 규범 변경 완료 후 재개 미실행 |
| [EP-132](../research/fixed-matchup-learning/plans/EP-132-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 자기대국 학습 실행 | Completed |
| [EX-072](../research/policy-learning/experiments/EX-072-selfplay-rlcd.md) | 자기대국과 RLCD 확률 보정: 단일 GPU 24시간 | Completed — 실험 완료, 성능 개선 미입증 |
| [EX-076](../research/fixed-matchup-learning/experiments/EX-076-fixed-matchup-mcts.md) | 고정 A/B 공개 상태 MCTS 정책 학습 | Incomplete — 교정 후 기술 검증/측정 통과, 평가 예산 gate 초과로 학습/test 보류 |
| [EX-077](../research/fixed-matchup-learning/experiments/EX-077-fixed-matchup-day.md) | 하루 내 고정 대진 공개 상태 학습 | Incomplete — 사용자 요청 중지; 학습/test 미시작 |
| [EX-078](../research/fixed-matchup-learning/experiments/EX-078-fixed-matchup-first-round.md) | 첫1라운드 학습 체크포인트 | Completed — D-125 복구·첫라운드 진단 완료; 원실행 Incomplete 보존 |
| [EX-079](../research/fixed-matchup-learning/experiments/EX-079-fixed-matchup-stopping.md) | 종료조건 기반 고정 대진 추가 학습 | Completed — 추가학습·시험·감사/뷰어·정리 완료; 주효능 기준 미달 |
| [EX-080](../research/fixed-matchup-learning/experiments/EX-080-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Completed — 시도 3 학습(round40 둔화 종료)·선택(round36)·잠긴 test·감사/뷰어/봉인·정리 완료; 주효능 미입증 (시도 1·2는 도구 결함으로 학습 전 중단·보존) |

## 학습 / 정책 강화학습

| ID | 제목 | 상태 |
|---|---|---|
| [EX-073](../research/policy-learning/experiments/EX-073-abyssal-rl.md) | Abyssal 우선 정책 학습: 4GPU·24시간 | Incomplete — 학습·test·독립 감사 완료, 최종 뷰어 검증 시간 초과 |
| [EX-074](../research/policy-learning/experiments/EX-074-abyssal-rl-continue.md) | 57라운드 계승·동일 설정 추가12시간 학습 | Completed — 실험 완료·57라운드 출발 대비 통계적 개선·성능 목표 미달 |
| [EX-075](../research/policy-learning/experiments/EX-075-abyssal-rl-next.md) | 82라운드 계승·동일 설정 추가12시간 1회 | Completed — 필수 검증·평가·뷰어·봉인·정리 완료; 개선 미입증·목표 미달 |

## 학습 / 조건부 KO 판정

| ID | 제목 | 상태 |
|---|---|---|
| [D-176](../research/rule-learning/decisions/D-176-conditional-ko-system1-data.md) | 조건부 KO와 관측 KO의 분리 | Accepted |
| [EP-199](../research/rule-learning/plans/EP-199-conditional-ko-system1-data.md) | 조건부 확정 KO 판정 자료 | Completed |

## 학습 / 증류

| ID | 제목 | 상태 |
|---|---|---|
| [D-215](../research/policy-learning/decisions/D-215-laya-foulplay-distill-then-rl.md) | v11rtc에 foul-play 탐색을 증류한 뒤, foul-play 상대 강화학습으로 다듬는다 | Accepted |
| [D-219](../research/policy-learning/decisions/D-219-laya-multiturn-search-and-value.md) | 1턴 시야·정적 가치 편향 극복을 위한 다중턴 탐색(2-A)·신경망 상태가치(2-B)·경량 MCTS-Q 재정렬 학습(1-B) (GPU 0·1 전용) | Accepted |
| [D-224](../research/policy-learning/decisions/D-224-batch-b-waya-v2-ladder-wayc1-clean-wayb.md) | 배치 B 병행 실행: EX-223 방식 A v2 공식 래더(EX-224) + 정화 교사 방식 C-1(EX-225) → 프롬프트 도구 주입 방식 B(EX-226) DDP 자동 연쇄 | Accepted |
| [EP-236](../research/policy-learning/plans/EP-236-laya-v11rtc-foulplay-distill-rl.md) | v11rtc에 foul-play 탐색 증류 → foul-play 상대 강화학습 → foul-play·공식 래더 평가 | Paused |
| [EP-243](../research/policy-learning/plans/EP-243-laya-multiturn-search-value-distill.md) | 다중턴 온라인 탐색(2-A)·신경망 상태가치(2-B)·경량 MCTS-Q 재정렬 학습(1-B) (GPU 0·1 전용) | Active |
| [EP-248](../research/policy-learning/plans/EP-248-batch-b-waya-v2-ladder-wayc1-clean-wayb.md) | 배치 B: EX-223 방식 A v2 공식 래더 병행 + 정화 방식 C-1 → 방식 B GPU 0·1 DDP 자동 연쇄 | Completed |
| [EX-182](../research/policy-learning/experiments/EX-182-laya-distill-teacher-labels.md) | 사람 학습 국면의 foul-play 탐색 교사 라벨(CPU) | Completed |
| [EX-183](../research/policy-learning/experiments/EX-183-laya-v11rtc-distill-training.md) | v11rtc + foul-play 탐색 증류 학습(1 epoch, GPU 4장) | Completed |
| [EX-209](../research/policy-learning/experiments/EX-209-laya-mcts5k-q-rerank-1b-train.md) | 1-B 오프라인 경량 MCTS-5k 루트 Q 후보 재정렬 타깃 생성 및 v13 단일 모델 학습(GPU 0·1) | Completed |
| [EX-225](../research/policy-learning/experiments/EX-225-laya-way-c1-clean-vphiv3-2ply-train.md) | 방식 C-1 오염 제거판: EX-221 V_phi v3 + 2-ply 정화 교사 증류 학습 (GPU 0·1 DDP) | Completed |
| [EX-226](../research/policy-learning/experiments/EX-226-laya-way-b-tool-inject-train.md) | 방식 B: calc-duel-free + MCTS50k/V_phi v3 5단계 matchup & eval 프롬프트 주입 + 35% Tool Dropout + 인간 앵커 보존 학습 (GPU 0·1 DDP) | Completed |

## 학습 / 증류·재정렬

| ID | 제목 | 상태 |
|---|---|---|
| [D-222](../research/policy-learning/decisions/D-222-laya-way-c1-v14-walled-teacher50k.md) | 방식 C-1: v14+walled_duel 입력 및 Hard-Example MCTS 50k + EX-216 V_phi v2 교사 증류 학습 | Accepted |
| [EP-244](../research/policy-learning/plans/EP-244-laya-search-2bv2-and-v14-training.md) | 상대 회복·흡수 대면 대응: 2-B v2 탐색 개선(CPU 서빙) 및 v14 입력·MCTS-5k Q 재학습 병행 (GPU 0·1 전용) | Paused |
| [EP-246](../research/policy-learning/plans/EP-246-laya-way-c1-v14-walled-teacher50k-distill.md) | 방식 C-1: v14+walled_duel 입력 및 Hard-Example MCTS 50k + EX-216 V_phi v2 교사 증류 학습 (GPU 0·1 전용) | Paused |
| [EX-213](../research/policy-learning/experiments/EX-213-laya-v14-data-and-mcts5k-training.md) | v14 회복·흡수 인지 입력 렌더러 데이터 생성 및 MCTS-5k Q 단일 모델 DDP 학습(GPU 0·1) | Stopped |
| [EX-218](../research/policy-learning/experiments/EX-218-laya-way-c1-v14-walled-teacher50k-train.md) | 방식 C-1: v14+walled_duel 데이터·Hard-Example MCTS 50k + EX-216 V_phi v2 교사 타깃 생성 및 DDP 학습 (GPU 0·1) | Stopped |

## 학습 / 학습 데이터 생성

| ID | 제목 | 상태 |
|---|---|---|
| [D-174](../research/rule-learning/decisions/D-174-gen9-type-matchup-dataset.md) | Gen9 타입 상성 전수 자료 | Accepted |
| [EP-192](../research/rule-learning/plans/EP-192-gen9-type-matchup-dataset.md) | Gen9 타입 상성 전수 학습 데이터 | Completed |

## 학습 / 합성 규칙 자료

| ID | 제목 | 상태 |
|---|---|---|
| [D-178](../research/rule-learning/decisions/D-178-gen9-mechanics-system1-data.md) | 우선순위별 규칙 적용과 정보 충분성 자료 | Accepted |
| [EP-201](../research/rule-learning/plans/EP-201-gen9-mechanics-system1-data.md) | 우선순위별 Gen9 규칙 적용 System 1 자료 | Completed |

## 학습 / 행동가치

| ID | 제목 | 상태 |
|---|---|---|
| [D-098](../research/action-value/decisions/D-098-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 첫 행동가치 학습 | Accepted |
| [D-099](../research/action-value/decisions/D-099-qwen-local-battle.md) | Qwen 행동가치 로컬 서빙·배틀 연결 | Accepted |
| [D-103](../research/action-value/decisions/D-103-joint-q-data.md) | 다경기 공동 q 데이터 | Accepted |
| [D-104](../research/action-value/decisions/D-104-joint-q-training.md) | EX-065 기반 Base 공동 q 학습 | Accepted |
| [D-105](../research/action-value/decisions/D-105-joint-q-gpu2.md) | 공동 q 학습의 GPU2 지정 | Accepted |
| [D-106](../research/action-value/decisions/D-106-joint-q-idle-gpu.md) | 공동 q 학습의 유휴 GPU 대체 | Accepted |
| [EP-107](../research/action-value/plans/EP-107-joint-q-data.md) | Abyssal 80경기 공동 q 데이터 | Completed |
| [EP-108](../research/action-value/plans/EP-108-joint-q-training.md) | EX-065 기반 Base 공동 q 학습 | Blocked |
| [EP-110](../research/action-value/plans/EP-110-abyssal-tera-joint-q.md) | Abyssal Tera 정책과 보완 공동 q 데이터 | Completed |
| [EX-061](../research/action-value/experiments/EX-061-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 행동가치 개발 실험 | Completed |
