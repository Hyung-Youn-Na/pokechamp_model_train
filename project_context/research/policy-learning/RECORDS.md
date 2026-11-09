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
