# 배틀 정책 학습·개선 — 기록 목록

<!-- generated: scripts/context-catalog build -->

원문은 한 곳에 두며 다른 주제의 관련 기록은 색인과 원문 링크로 연결한다.

| ID | 제목 | 상태 |
|---|---|---|
| [D-096](decisions/D-096-pokemon-training-objective.md) | 세 RLCD 환경을 활용한 포켓몬 전용 학습 당면 목표 채택 | Accepted |
| [D-112](decisions/D-112-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 채택 | Accepted |
| [D-113](decisions/D-113-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Accepted |
| [D-114](decisions/D-114-selfplay-rlcd.md) | 단일 GPU 자기대국과 선택 행동 확률 보정 | Accepted |
| [D-115](decisions/D-115-abyssal-first-objective.md) | Abyssal 상대 효율적 승리를 당면 단기 목표로 채택 | Accepted |
| [D-116](decisions/D-116-abyssal-rl.md) | Abyssal 전용 4GPU·24시간 학습 승인 | Accepted |
| [D-117](decisions/D-117-abyssal-rl-continue.md) | 57라운드 계승·동일 설정 추가12시간 승인 | Accepted |
| [D-118](decisions/D-118-abyssal-rl-next.md) | 82라운드 계승·추가12시간 1회 승인 | Accepted |
| [D-183](decisions/D-183-laya-compact-imitation.md) | laya 압축 입력 모방 학습과 표준 배틀 평가 | Accepted |
| [D-184](decisions/D-184-laya-team-generalization.md) | laya 모방 모델의 새 팀 일반화 평가 | Accepted |
| [D-185](decisions/D-185-laya-modular-renderer-v2.md) | laya 모듈형 렌더러 v2(기술 변형·속도·교체·피해량) | Accepted |
| [D-187](decisions/D-187-laya-tera-knowledge.md) | laya v2에 테라 기본 지식 데이터 추가(GPU1) | Accepted |
| [D-188](decisions/D-188-laya-effect-knowledge.md) | laya v2+테라에 기술·도구·특성 효과 지식 데이터 추가(GPU2) | Accepted |
| [D-189](decisions/D-189-laya-renderer-v3-opponent-sets.md) | laya 렌더러 v3(상대 세트 추론)와 래더 대비 학습(GPU0) | Accepted |
| [D-190](decisions/D-190-laya-ex129-gate-override.md) | EX-128 진행 조건 미충족에도 EX-129 배틀 실행(사용자 결정) | Accepted |
| [D-191](decisions/D-191-no-offline-battle-gate.md) | 오프라인 test 평가로 배틀 평가를 거르지 않는다 | Accepted |
| [D-192](decisions/D-192-laya-renderer-v4-fail-out.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해)와 GPU1 학습·배틀 | Accepted |
| [D-193](decisions/D-193-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방(GPU0 학습·배틀) | Accepted |
| [D-194](decisions/D-194-laya-head-to-head-evaluation.md) | laya 직접 대결 평가(GPU2, EX-120 일정) | Accepted |
| [D-195](decisions/D-195-laya-item-state-renderer-v5.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터)와 학습·배틀 | Accepted |
| [D-196](decisions/D-196-laya-v2t-corrected-input-battle.md) | laya v2+테라(EX-124)를 재학습 없이 D-195 보정 입력으로 배틀(GPU1) | Accepted |
| [D-197](decisions/D-197-laya-v2t-tera-decision-defence.md) | laya v2+테라(EX-124) fix 입력에서 테라 합산 결정과 테라 방어 문구 배틀(재학습 없음, GPU1) | Accepted |
| [D-198](decisions/D-198-laya-past-turn-input-v6.md) | laya 과거 턴 입력 두 가지(v6s 반복 표시·v6h 긴 기록 2048토큰) 동시 학습과 배틀 | Accepted |
| [D-199](decisions/D-199-laya-play-teams-abyssal-battle.md) | laya-play 완성 팀(Smogon 샘플·Blim)으로 v5t·v6st·v6ht 대 Abyssal 비교 | Accepted |
| [D-200](decisions/D-200-laya-loop-break-opponent-sets.md) | laya 손해 루프 탈출(학습 가중·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험 | Accepted |
| [D-201](decisions/D-201-laya-engine-judge-v8.md) | laya 실패 표시를 고정 Showdown 엔진 판정기로 바꾼 렌더러 v8 | Accepted |
| [D-202](decisions/D-202-laya-opponent-threat-v9.md) | laya 상대 가정 세트 노력치 보정과 최악 피해 표시(렌더러 v9) | Accepted |
| [D-203](decisions/D-203-laya-human-teams-v7-v8-v9.md) | laya v7t·v8t·v9t를 사람이 짠 완성 팀으로 Abyssal과 비교(GPU0·1·2) | Accepted |
| [D-204](decisions/D-204-laya-renderer-v10-all-info.md) | laya 렌더러 v10: 지금까지의 정보 전부 + lock + 전략 정보, 2,048토큰 | Accepted |
| [D-205](decisions/D-205-laya-switch-read-and-mixing.md) | laya 교체 읽기 상대(정직함 측정)와 교체 갈림길 섞기(재학습 없음) | Accepted |
| [D-206](decisions/D-206-laya-opponent-model-search.md) | laya 상대 모델 + 한 턴 탐색(세트 표본 추정), 재학습 없음 | Accepted |
| [D-208](decisions/D-208-laya-ladder-r1500-v10.md) | 최근 래더(레이팅 1500 이상) 리플레이를 더한 v10 학습(GPU 4장 DDP, 24시간) | Accepted |
| [D-209](decisions/D-209-laya-ladder-postmortem-v11.md) | laya v10rt 공식 래더 패배 원인 추가 분석과 재학습 v11(입력 수정·정책 교정) 설계 | Accepted |
| [D-210](decisions/D-210-laya-v11rtc-policy-correction-values.md) | v11rtc 정책 교정 수단 확정(EX-169 결과 적용)과 가중 배수 보정 | Accepted |
| [D-211](decisions/D-211-laya-foulplay-opponent.md) | foul-play(탐색 봇)를 laya의 고정 상대로 도입하고 v10rt와 EX-120 일정으로 대전 | Accepted |
| [D-212](decisions/D-212-laya-foulplay-blim-teams.md) | foul-play 대전을 Blim 팀 일정으로 바꾸고 EX-173을 중지 | Accepted |
| [D-213](decisions/D-213-laya-fp1-foulplay-input.md) | laya 입력을 foul-play 추적·poke-engine 계산으로 전부 바꾼 렌더러 fp1과 처음부터 전체 학습 | Accepted |
| [D-214](decisions/D-214-laya-foulplay-primary-ladder-final.md) | laya 정책 개선의 개발 목표를 foul-play 상대 점수로, 최종 실험을 공식 래더 대전으로 둔다 | Accepted |
| [D-215](decisions/D-215-laya-foulplay-distill-then-rl.md) | v11rtc에 foul-play 탐색을 증류한 뒤, foul-play 상대 강화학습으로 다듬는다 | Accepted |
| [D-216](decisions/D-216-laya-opponent-prediction-one-turn-read.md) | laya 상대 행동 예측 학습과 한 턴 읽기 | Accepted |
| [D-217](decisions/D-217-laya-engine-value-rerank-training.md) | foul-play 엔진 평가로 laya 후보 순위를 다시 매긴 target 학습 | Accepted |
| [D-218](decisions/D-218-laya-v13-input-bugfixes.md) | laya 렌더러 v13 입력 결함 수정(폼 스펙·테라 방어 재계산·선공 Roost 지면화·Ivy Cudgel 타입) | Accepted |
| [D-219](decisions/D-219-laya-multiturn-search-and-value.md) | 1턴 시야·정적 가치 편향 극복을 위한 다중턴 탐색(2-A)·신경망 상태가치(2-B)·경량 MCTS-Q 재정렬 학습(1-B) (GPU 0·1 전용) | Accepted |
| [EP-099](plans/EP-099-pokemon-training-objective.md) | 포켓몬 전용 모델 학습 당면 목표 문서화 | Completed |
| [EP-114](plans/EP-114-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 구체화 | Completed |
| [EP-115](plans/EP-115-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EP-116](plans/EP-116-selfplay-rlcd.md) | 자기대국과 RLCD 확률 보정 | Completed |
| [EP-117](plans/EP-117-selfplay-finalization-recovery.md) | EX-072 오프라인 뷰어 검증·최종화 복구 | Completed |
| [EP-118](plans/EP-118-abyssal-first-objective.md) | Abyssal 우선 단기 목표 정비 | Completed |
| [EP-119](plans/EP-119-abyssal-rl.md) | Abyssal 우선 4GPU·24시간 학습 | Blocked — 학습·test 완료, 뷰어 전수 검증 시간 초과로 실험 미완료 |
| [EP-120](plans/EP-120-abyssal-preflight-recovery.md) | EX-073 수치 사전검사 복구 도구 | Completed |
| [EP-121](plans/EP-121-abyssal-rl-continue.md) | 57라운드 계승 추가12시간 | Completed |
| [EP-122](plans/EP-122-abyssal-rl-next.md) | 82라운드 계승 추가12시간 | Completed |
| [EP-208](plans/EP-208-laya-compact-imitation.md) | laya 압축 입력 모방 학습·배틀 에이전트 | Completed |
| [EP-209](plans/EP-209-laya-team-generalization.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EP-210](plans/EP-210-laya-renderer-v2.md) | laya 모듈형 렌더러 v2 학습과 v1·v2 비교 | Completed |
| [EP-212](plans/EP-212-laya-tera-knowledge.md) | laya v2 테라 지식 데이터 학습과 배틀 비교(GPU1) | Completed |
| [EP-213](plans/EP-213-laya-effect-knowledge.md) | laya v2+테라+효과 지식 데이터 학습과 배틀 비교(GPU2) | Completed |
| [EP-214](plans/EP-214-laya-renderer-v3.md) | laya 렌더러 v3(상대 세트 추론) 학습과 배틀 비교(GPU0) | Completed |
| [EP-215](plans/EP-215-laya-renderer-v4.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) 학습과 배틀 비교(GPU1) | Completed |
| [EP-216](plans/EP-216-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방 학습과 배틀 비교(GPU0) | Completed |
| [EP-217](plans/EP-217-laya-head-to-head-evaluation.md) | laya 직접 대결 평가 하네스와 벤치마크(GPU2) | Completed |
| [EP-218](plans/EP-218-laya-renderer-v5-item-state.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) 학습과 배틀 비교(GPU0·GPU2) | Completed |
| [EP-219](plans/EP-219-laya-v2t-corrected-input-battle.md) | laya v2+테라 보정 입력 배틀(재학습 없음, GPU1) | Completed |
| [EP-220](plans/EP-220-laya-v2t-tera-decision-defence.md) | laya v2+테라 fix 입력 테라 합산 결정·테라 방어 문구 배틀(재학습 없음, GPU1) | Completed |
| [EP-221](plans/EP-221-laya-past-turn-input-v6.md) | laya 과거 턴 입력 v6s·v6h 동시 학습과 배틀 비교(GPU0·GPU1) | Completed |
| [EP-222](plans/EP-222-laya-play-teams-abyssal-battle.md) | laya-play 완성 팀으로 v5t·v6st·v6ht 대 Abyssal 비교(GPU2) | Completed |
| [EP-223](plans/EP-223-laya-loop-break-opponent-sets.md) | laya 손해 루프 탈출(가중 학습·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험(GPU0~3) | Completed |
| [EP-224](plans/EP-224-laya-engine-judge-v8.md) | laya 엔진 판정기(고정 Showdown 실패 판정)와 렌더러 v8 학습·배틀(GPU1·GPU2) | Completed |
| [EP-225](plans/EP-225-laya-opponent-threat-v9.md) | laya 상대 노력치 보정·최악 피해 표시 렌더러 v9 학습·배틀(GPU3) | Completed |
| [EP-226](plans/EP-226-laya-human-teams-v7-v8-v9.md) | laya v7t·v8t·v9t 사람 팀 비교 배틀(GPU0·1·2) | Stopped |
| [EP-227](plans/EP-227-laya-renderer-v10.md) | laya 렌더러 v10(정보 전부 + lock + 전략, 2,048토큰) 학습과 Abyssal 배틀 | Completed |
| [EP-228](plans/EP-228-laya-switch-read-and-mixing.md) | laya 교체 읽기 상대(정직함 측정)와 v8lt 교체 갈림길 섞기 배틀(재학습 없음, GPU1~3) | Completed |
| [EP-229](plans/EP-229-laya-opponent-model-search.md) | laya 상대 모델 + 한 턴 탐색(세트 표본 추정) | Active |
| [EP-230](plans/EP-230-laya-ladder-r1500-v10.md) | 최근 래더(레이팅 1500 이상) 리플레이 자료와 v10 학습(GPU 4장 DDP), Abyssal 배틀 | Completed |
| [EP-231](plans/EP-231-laya-ladder-postmortem-v11.md) | laya v10rt 공식 래더 패배 원인 추가 분석과 재학습 v11(v11rt·v11rtc) | Active |
| [EP-232](plans/EP-232-laya-foulplay-v10rt.md) | foul-play(탐색 봇) 대 laya v10rt 128경기(CPU; EX-173 EX-120 팀 → 중지, EX-174 Blim 팀) | Completed |
| [EP-233](plans/EP-233-laya-foulplay-v11.md) | foul-play 대 laya v11rt·v11rtc, EX-174 Blim 일정 128경기씩(CPU) | Stopped |
| [EP-234](plans/EP-234-laya-fp1-foulplay-input.md) | laya fp1 렌더러(foul-play 기반 입력) 자료·처음부터 전체 학습·foul-play 배틀 | Active |
| [EP-235](plans/EP-235-laya-v10rt-search-regret.md) | laya v10rt 결정과 foul-play 탐색의 대조 진단(EX-174 기록, CPU) | Completed |
| [EP-236](plans/EP-236-laya-v11rtc-foulplay-distill-rl.md) | v11rtc에 foul-play 탐색 증류 → foul-play 상대 강화학습 → foul-play·공식 래더 평가 | Paused |
| [EP-237](plans/EP-237-laya-observed-public-info-input.md) | laya 입력에 foul-play의 경기 중 추론 전부 반영(렌더러 v12) | Active |
| [EP-238](plans/EP-238-laya-opponent-prediction-one-turn-read.md) | laya 상대 행동 예측 학습 → 한 턴 읽기 선택 → 입력 통합 | Completed |
| [EP-239](plans/EP-239-laya-engine-value-rerank-training.md) | foul-play 엔진 평가 target 학습과 시간 제한 없는 foul-play 평가 | Completed |
| [EP-240](plans/EP-240-laya-v13-input-bugfixes.md) | laya 렌더러 v13 입력 결함 수정(폼 스펙·테라 방어·선공 Roost·Ivy Cudgel)과 검증 | Completed |
| [EP-241](plans/EP-241-laya-v13-zeroshot-vs-foulplay.md) | laya v13 입력 교정(무재학습 EX-200) 대 foul-play Blim 128경기(시간 제한 없음) | Completed |
| [EP-242](plans/EP-242-laya-lead-matchup-2b.md) | laya 2b 선봉 선택 모듈(`lead_policy.py`, 상대 선봉 추정 × 6×6 매치업 기대값 + 모델 사전확률 재가중) 구현 | Completed |
| [EP-243](plans/EP-243-laya-multiturn-search-value-distill.md) | 다중턴 온라인 탐색(2-A)·신경망 상태가치(2-B)·경량 MCTS-Q 재정렬 학습(1-B) (GPU 0·1 전용) | Active |
| [EX-071](experiments/EX-071-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EX-072](experiments/EX-072-selfplay-rlcd.md) | 자기대국과 RLCD 확률 보정: 단일 GPU 24시간 | Completed — 실험 완료, 성능 개선 미입증 |
| [EX-073](experiments/EX-073-abyssal-rl.md) | Abyssal 우선 정책 학습: 4GPU·24시간 | Incomplete — 학습·test·독립 감사 완료, 최종 뷰어 검증 시간 초과 |
| [EX-074](experiments/EX-074-abyssal-rl-continue.md) | 57라운드 계승·동일 설정 추가12시간 학습 | Completed — 실험 완료·57라운드 출발 대비 통계적 개선·성능 목표 미달 |
| [EX-075](experiments/EX-075-abyssal-rl-next.md) | 82라운드 계승·동일 설정 추가12시간 1회 | Completed — 필수 검증·평가·뷰어·봉인·정리 완료; 개선 미입증·목표 미달 |
| [EX-118](experiments/EX-118-laya-compact-imitation-training.md) | laya 압축 입력 리플레이 모방 학습 | Completed |
| [EX-119](experiments/EX-119-laya-compact-imitation-battle32.md) | laya 압축 입력 모방 모델 EX-089 표준 32경기 | Completed |
| [EX-120](experiments/EX-120-laya-team-generalization128.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EX-121](experiments/EX-121-laya-v2-all-training.md) | laya 모듈형 렌더러 v2(4종 전부) 학습과 v1 쌍비교 | Completed |
| [EX-122](experiments/EX-122-laya-v1-v2-battle256.md) | laya v1·v2 같은 실행 256경기 비교 (EX-120 일정) | Completed |
| [EX-124](experiments/EX-124-laya-v2-tera-knowledge-training.md) | laya v2 + 테라 기본 지식 데이터 학습(GPU1) | Completed |
| [EX-125](experiments/EX-125-laya-v2-tera-battle256.md) | laya v2와 v2+테라 지식 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-126](experiments/EX-126-laya-v2-tera-effect-training.md) | laya v2 + 테라 + 효과 지식 데이터 학습(GPU2) | Completed |
| [EX-127](experiments/EX-127-laya-v2t-v2te-battle256.md) | laya v2+테라와 v2+테라+효과 지식 같은 실행 256경기(GPU2, EX-120 일정) | Completed |
| [EX-128](experiments/EX-128-laya-v3-tera-training.md) | laya 렌더러 v3(상대 세트 추론) + 테라 지식 학습(GPU0) | Completed |
| [EX-129](experiments/EX-129-laya-v2t-v3t-battle256.md) | laya v2+테라와 v3+테라 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-130](experiments/EX-130-laya-v4-tera-training.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) + 테라 지식 학습(GPU1) | Completed |
| [EX-131](experiments/EX-131-laya-v2t-v4t-battle256.md) | laya v2+테라와 v4+테라 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-132](experiments/EX-132-laya-v2t-outcome-weighted-training.md) | laya v2+테라 승패 가중 모방 학습(GPU0) | Completed |
| [EX-133](experiments/EX-133-laya-v2t-v2tw-battle256.md) | laya v2+테라와 v2+테라 승패 가중 모방 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-134](experiments/EX-134-laya-head-to-head512.md) | laya v2+테라 대 v2·v1·v2+테라+효과·v3+테라 직접 대결 512경기(GPU2, EX-120 일정) | Completed |
| [EX-135](experiments/EX-135-laya-head-to-head-v2tw-v4t.md) | laya v2+테라 대 승패 가중·v4+테라 직접 대결 256경기(GPU2, EX-120 일정) | Completed |
| [EX-136](experiments/EX-136-laya-v5-tera-training.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) + 테라 지식 학습(GPU0) | Completed |
| [EX-137](experiments/EX-137-laya-v4t-v5t-battle256.md) | laya v4+테라와 v5+테라 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-138](experiments/EX-138-laya-head-to-head-v5t.md) | laya v5+테라 대 v2+테라·v4+테라 직접 대결 256경기(GPU2, EX-120 일정) | Completed |
| [EX-139](experiments/EX-139-laya-v2t-corrected-input-battle256.md) | laya v2+테라(EX-124) 보정 입력 fix·info 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-140](experiments/EX-140-laya-v2t-tera-decision-defence384.md) | laya v2+테라(EX-124) fix 입력 테라 합산 결정(k=1·3)과 테라 방어 문구 384경기(GPU1, EX-120 일정) | Completed |
| [EX-141](experiments/EX-141-laya-v6s-streaks-training.md) | laya 렌더러 v6s(같은 기술 반복 표시) + 테라 지식 학습(GPU0) | Completed |
| [EX-142](experiments/EX-142-laya-v6h-long-history-training.md) | laya 렌더러 v6h(긴 과거 기록, 2048토큰) + 테라 지식 학습(GPU1) | Completed |
| [EX-143](experiments/EX-143-laya-v5t-v6st-battle256.md) | laya v5+테라와 v6st (반복 표시) 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-144](experiments/EX-144-laya-v5t-v6ht-battle256.md) | laya v5+테라와 v6ht (긴 기록 2048토큰) 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-145](experiments/EX-145-laya-play-teams-v5t-v6st-v6ht-battle.md) | laya-play 완성 팀 74개로 v5t·v6st·v6ht 대 Abyssal(GPU2) | Completed |
| [EX-146](experiments/EX-146-laya-v6sl-loop-weighted-training.md) | laya v6s + 루프 탈출 행 가중 학습(v6sl, GPU1) | Completed |
| [EX-147](experiments/EX-147-laya-v6st-v6slt-battle256.md) | laya v6st 대 v6slt(루프 탈출 가중) 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-148](experiments/EX-148-laya-loop-decision-rule.md) | laya 루프 결정 규칙(재학습 없음): v6st·v6ht 정체 루프 기술 제외, EX-120 일정 대 Abyssal | Completed |
| [EX-149](experiments/EX-149-laya-v7-opponent-sets-training.md) | laya 렌더러 v7(v6s + 상대 세트 추정 `oppset2`, Protean 실패 표시 보정) 학습(GPU0) | Completed |
| [EX-150](experiments/EX-150-laya-v6st-v7t-battle256.md) | laya v6st 대 v7t(상대 세트 추정) 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-151](experiments/EX-151-laya-engine-judge-validation.md) | laya 엔진 판정기 구축과 실전·사람 리플레이 검증 | Completed |
| [EX-152](experiments/EX-152-laya-v8-engine-fails-training.md) | laya 렌더러 v8(v7 + 엔진 판정기 실패 표시) 학습(GPU1) | Completed |
| [EX-153](experiments/EX-153-laya-v7t-v8t-battle256.md) | laya v7t 대 v8t(엔진 실패 표시) 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-154](experiments/EX-154-laya-head-to-head-v8t-v7t.md) | laya v8t 대 v7t 직접 대결 128경기(GPU2, EX-120 일정) | Stopped |
| [EX-155](experiments/EX-155-laya-v8l-likely-fails-training.md) | laya 렌더러 v8l(v8 + `likely fails` 표시) 학습(GPU2) | Completed |
| [EX-156](experiments/EX-156-laya-v8t-v8lt-battle256.md) | laya v8t 대 v8lt(`likely fails` 표시) 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-157](experiments/EX-157-laya-v9-opponent-threat-training.md) | laya 렌더러 v9(v7 + 상대 노력치 보정·최악 피해 표시) 학습(GPU3) | Completed |
| [EX-158](experiments/EX-158-laya-v7t-v9t-battle256.md) | laya v7t 대 v9t(상대 위협 표시) 같은 실행 256경기(GPU3, EX-120 일정) | Completed |
| [EX-159](experiments/EX-159-laya-human-teams-v7t-v8t-v9t.md) | laya v7t·v8t·v9t 사람이 짠 완성 팀 123개 대 Abyssal(GPU0·1·2) | Stopped |
| [EX-160](experiments/EX-160-laya-human-teams-v8lt.md) | laya v8lt 사람이 짠 완성 팀 123개 대 Abyssal(EX-159 일정, GPU3) | Stopped |
| [EX-161](experiments/EX-161-laya-v10-all-info-training.md) | laya 렌더러 v10(정보 전부 + lock + 전략, 2,048토큰) 학습(GPU0) | Completed |
| [EX-162](experiments/EX-162-laya-v7t-v10t-battle256.md) | laya v7t 대 v10t(정보 전부 + lock + 전략) 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-163](experiments/EX-163-laya-v8lt-vs-switch-reader.md) | laya v8lt argmax 대 교체 읽기 상대(abyssal-read), EX-120 일정 128경기(GPU1) | Completed |
| [EX-164](experiments/EX-164-laya-v8lt-switch-mixing.md) | laya v8lt 교체 갈림길 섞기(재학습 없음): 대 Abyssal·대 교체 읽기 상대, 각 128경기(GPU2·GPU3) | Completed |
| [EX-165](experiments/EX-165-laya-opponent-prediction-scenes.md) | laya 상대 시점 예측(세트 표본) 장면 검증: 사람 test 4경기, v8lt(CPU) | Completed |
| [EX-166](experiments/EX-166-laya-ladder-r1500-data.md) | 최근 래더(레이팅 1500 이상) 리플레이의 v10 학습 자료(CPU) | Completed |
| [EX-167](experiments/EX-167-laya-v10-ladder-training.md) | laya v10 + 최근 래더 자료 학습(GPU 4장 DDP, 약 24시간) | Completed |
| [EX-168](experiments/EX-168-laya-v10t-v10rt-battle256.md) | laya v10t 대 v10rt(최근 래더 자료 추가) 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-169](experiments/EX-169-laya-v10rt-ladder-loss-analysis.md) | laya v10rt 공식 래더 83판 패배 원인 추가 분석(CPU, 추론만 GPU) | Completed |
| [EX-170](experiments/EX-170-laya-v11-data.md) | laya 렌더러 v11 학습 자료(판정 재생성·재렌더, 가중·교정 행, CPU) | Running |
| [EX-171](experiments/EX-171-laya-v11rt-training.md) | laya v11rt 학습(v10rt + 입력 수정, 1 epoch) | Completed |
| [EX-172](experiments/EX-172-laya-v11rtc-training.md) | laya v11rtc 학습(v10rt + 입력 수정 + 정책 교정, 1 epoch) | Completed |
| [EX-173](experiments/EX-173-laya-v10rt-vs-foulplay128.md) | laya v10rt 대 foul-play(MCTS 3초 × 병렬 4), EX-120 일정 128경기(CPU) | Stopped |
| [EX-174](experiments/EX-174-laya-v10rt-vs-foulplay-blim128.md) | laya v10rt 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기(CPU) | Completed |
| [EX-175](experiments/EX-175-laya-v11rt-vs-foulplay-blim128.md) | laya v11rt 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기(CPU) | Stopped |
| [EX-176](experiments/EX-176-laya-v11rtc-vs-foulplay-blim128.md) | laya v11rtc 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기(CPU) | Stopped |
| [EX-177](experiments/EX-177-laya-fp1-data.md) | laya fp1 학습 자료(foul-play 추적·표본·poke-engine 재렌더, CPU) | Completed |
| [EX-178](experiments/EX-178-laya-fp1-training.md) | laya fp1 처음부터 전체 학습(GPU 4장 DDP, 약 24시간) | Completed |
| [EX-179](experiments/EX-179-laya-fp1-vs-foulplay-blim128.md) | laya fp1 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기 | Planned |
| [EX-180](experiments/EX-180-laya-fp1e2-vs-foulplay-blim128.md) | laya fp1 epoch-2 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기(CPU) | Running |
| [EX-181](experiments/EX-181-laya-v10rt-foulplay-search-regret.md) | EX-174 v10rt 결정 대 foul-play 탐색(같은 자리·같은 설정) 불일치·값 차이 진단(CPU) | Completed |
| [EX-182](experiments/EX-182-laya-distill-teacher-labels.md) | 사람 학습 국면의 foul-play 탐색 교사 라벨(CPU) | Completed |
| [EX-183](experiments/EX-183-laya-v11rtc-distill-training.md) | v11rtc + foul-play 탐색 증류 학습(1 epoch, GPU 4장) | Completed |
| [EX-184](experiments/EX-184-laya-v11rtc-vs-foulplay-blim128.md) | v11rtc 대 foul-play, Blim 팀 64개 128경기(CPU, 기준 완료본) | Planned |
| [EX-185](experiments/EX-185-laya-distill-vs-foulplay-blim128.md) | 증류 모델(EX-183) 대 foul-play, Blim 팀 64개 128경기(CPU) | Stopped |
| [EX-186](experiments/EX-186-laya-distill-foulplay-rl.md) | 증류 모델에서 시작하는 foul-play 상대 강화학습(KL 제약, 학습 팀) | Paused |
| [EX-187](experiments/EX-187-laya-distill-rl-vs-foulplay-blim128.md) | 강화학습 모델(EX-186) 대 foul-play, Blim 팀 64개 128경기(CPU) | Paused |
| [EX-188](experiments/EX-188-laya-distill-ladder-final.md) | EP-236 최종 후보의 공식 Showdown gen9ou 래더 대전 | Paused |
| [EX-189](experiments/EX-189-laya-v11d-ladder-interim.md) | v11d(EX-183) 공식 Showdown gen9ou 래더 중간 대전(GPU 서빙, 2026-11-20 23:00 KST까지) | Stopped |
| [EX-190](experiments/EX-190-laya-obsinfo-frequency.md) | foul-play 경기 중 추론이 laya v11 입력을 바꾸는 빈도(EX-184·185 결정, 학습 없음) | Completed |
| [EX-191](experiments/EX-191-laya-v12-data.md) | laya v12 학습 자료(렌더러 v12로 v11 행 재렌더) | Completed |
| [EX-192](experiments/EX-192-laya-v12-training.md) | laya v12 처음부터 학습(GPU 4장 DDP, 3 epoch, 약 24시간) | Completed |
| [EX-193](experiments/EX-193-laya-v12-vs-foulplay-blim128.md) | laya v12(EX-192) 대 foul-play, Blim 팀 64개 128경기(CPU) | Completed |
| [EX-194](experiments/EX-194-laya-v12-ladder.md) | v12(EX-192) 공식 Showdown gen9ou 래더 대전(GPU 서빙, 2026-11-21 23:59 KST까지) | Completed |
| [EX-195](experiments/EX-195-laya-foe-prediction-data.md) | laya 상대 행동 예측 자료와 새 모방 행(v12, CPU) | Completed |
| [EX-196](experiments/EX-196-laya-v12-foe-training.md) | laya v12 + 상대 예측 이어 학습(EX-192에서 1 epoch, GPU 4장) | Completed |
| [EX-197](experiments/EX-197-laya-one-turn-read-vs-foulplay.md) | laya 한 턴 읽기 선택 대 foul-play, Blim 128경기(CPU) | Completed |
| [EX-198](experiments/EX-198-laya-v12-foe-argmax-vs-foulplay.md) | laya v12 + 상대 예측(EX-196) argmax 대 foul-play, Blim 128경기(CPU) | Completed |
| [EX-199](experiments/EX-199-laya-engine-value-targets.md) | laya 후보의 foul-play 엔진 한 턴 가치와 soft target 자료(CPU·GPU) | Completed |
| [EX-200](experiments/EX-200-laya-engine-value-training.md) | laya 엔진 가치 target 이어 학습(EX-196에서 1 epoch, GPU 4장) | Completed |
| [EX-201](experiments/EX-201-laya-engine-value-vs-foulplay-unlimited.md) | laya 엔진 가치 학습(EX-200) argmax 대 foul-play, Blim 128경기, 시간 제한 없음(CPU) | Completed |
| [EX-202](experiments/EX-202-laya-v12-foe-vs-foulplay-unlimited.md) | laya v12 + 상대 예측(EX-196) argmax 대 foul-play, Blim 128경기, 시간 제한 없음(CPU) | Completed |
| [EX-203](experiments/EX-203-laya-engine-value-ladder.md) | v12 엔진 가치 학습(EX-200) 공식 Showdown gen9ou 래더 대전(GPU 서빙, 2026-11-23 08:00 KST까지) | Completed |
| [EX-204](experiments/EX-204-laya-engine-value-ladder-loss-analysis.md) | EX-203 래더 고레이팅(1500 이상) 패배 원인 분석(CPU) | Completed |
| [EX-205](experiments/EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md) | laya v13 입력 교정(무재학습 EX-200) argmax 대 foul-play, Blim 128경기, 시간 제한 없음(CPU) | Completed |
| [EX-206](experiments/EX-206-laya-search-2a-vs-foulplay-unlimited.md) | 2-A 온라인 다중턴 탐색(EX-200 + v13 + GPU 0 서빙 + MCTS 5k 사전확률 융합) 대 foul-play, Blim 128경기(시간 제한 없음) | Completed |
| [EX-207](experiments/EX-207-laya-state-value-2b-train.md) | 2-B 리플레이 승패 기반 신경망 상태가치 모델 V_phi(poke_engine.State) 데이터 추출 및 학습(GPU 0·1) | Completed |
| [EX-208](experiments/EX-208-laya-search-2b-vs-foulplay-unlimited.md) | 2-B 온라인 다중턴 탐색 + 신경망 상태가치 V_phi 결합 대 foul-play, Blim 128경기(시간 제한 없음) | Running |
| [EX-209](experiments/EX-209-laya-mcts5k-q-rerank-1b-train.md) | 1-B 오프라인 경량 MCTS-5k 루트 Q 후보 재정렬 타깃 생성 및 v13 단일 모델 학습(GPU 0·1) | Running |
| [EX-210](experiments/EX-210-laya-mcts5k-q-rerank-1b-vs-foulplay-unlimited.md) | 1-B 오프라인 MCTS-5k Q 재정렬 학습 모델(EX-209, v13 단일 forward) 대 foul-play, Blim 128경기(시간 제한 없음) | Planned |
