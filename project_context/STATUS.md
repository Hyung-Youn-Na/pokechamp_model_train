# 프로젝트 상태

- 기준일: 2026-11-18
- 연구선·checkout: `research/model-training` · `/workspace`
- 목표: 포켓몬 모델 학습·정책 개선·독립 평가. [CHARTER](CHARTER.md)

<a id="current-objective"></a>

## 현재 목표

규칙 이해 학습과 행동 적용, 입력 표현 및 모델 정책의 평가를 목적별로 관리한다.
학습·모델 선택과 분리한 평가를 사용하며 연구 주제별 범위는 [연구 목록](research/INDEX.md)을 따른다.

<a id="active-work"></a>

## 현재 작업

2026-11-18 기준: [EP-231](research/policy-learning/plans/EP-231-laya-ladder-postmortem-v11.md) 공식 래더는 사용자 지시로 v11rtc 단일·CPU 서빙·팀 `t9ff547d715`(17:30 KST에 `te76a9c3ec1`에서 교체)로 돌았고 11-18 22:59 KST에 종료됐다(run 159). 11-19 08:46 KST부터 사용자 지시로 팀 `t9f05bb6c11`을 v11rtc CPU 서빙으로 시험했고, 10:29 KST부터 모델을 fp1 epoch-2(EX-180 체크포인트 복사본, CPU)로 바꿨다가 10:39 KST 사용자 지시로 멈췄다(진행 중인 판만 끝까지 둠). 10:59 KST부터 사용자 지시로 v10t(팀 `t95bfb45561`, CPU)를 18:00 KST까지 돌린다. 11:23 KST부터 사용자 지시로 레이팅이 1150 밑으로 떨어지면 판 경계에서 v10rt(laya-play 서빙 pid 350990, 같은 팀·종료 시각)로 바꾸는 감시(`exports/laya-play/runtime/switch_v10rt_below1150.sh`)가 돈다(시작 시 1195). [EX-180](research/policy-learning/experiments/EX-180-laya-fp1e2-vs-foulplay-blim128.md)(fp1 epoch-2 대 foul-play 128경기, CPU)이 함께 돈다. [EP-234](research/policy-learning/plans/EP-234-laya-fp1-foulplay-input.md) EX-178 학습이 GPU 0~3에서 돈다(11-19 17:00 KST 무렵 종료 예상). battle-window 표시 파일은 없다.

### laya 배틀 정책(policy-learning)

- **진행 중**: [EP-234](research/policy-learning/plans/EP-234-laya-fp1-foulplay-input.md)(D-213, 2026-11-18). 입력을 foul-play 추적·표본과 poke-engine 계산으로 전부 바꾼 렌더러 fp1([EX-177](research/policy-learning/experiments/EX-177-laya-fp1-data.md))로, EX-167과 같은 출발점에서 처음부터 학습한다([EX-178](research/policy-learning/experiments/EX-178-laya-fp1-training.md)). 그다음 foul-play Blim 128경기([EX-179](research/policy-learning/experiments/EX-179-laya-fp1-vs-foulplay-blim128.md))로 v10rt와 같은 슬롯에서 비교한다. 기록 문장과 테라 지식 행은 뺀다. 2026-11-18: EX-177 완료(train 1,241,896행, 제외 0.023%, 서빙 일치 518/518), EX-178 학습 중(약 24.4시간).

- **진행 중**: [EP-231](research/policy-learning/plans/EP-231-laya-ladder-postmortem-v11.md)(D-209, 2026-11-16). v10rt를 공식 Showdown 래더에 올린 83판(48승 35패, 레이팅 1042 → 1288)의 패배 원인을 더 분석하고([EX-169](research/policy-learning/experiments/EX-169-laya-v10rt-ladder-loss-analysis.md)), 입력 수정 렌더러 v11로 `v11rt`(입력 수정만)와 `v11rtc`(입력 수정 + 정책 교정)를 v10rt에서 1 epoch 이어 학습한다([EX-170](research/policy-learning/experiments/EX-170-laya-v11-data.md)~[EX-172](research/policy-learning/experiments/EX-172-laya-v11rtc-training.md)). 메모리는 `scripts/mem-guard 100` 아래에서 100 GB를 넘지 않게 한다. 공식 래더 비교는 사용자 지시를 기다린다. 2026-11-18 기준: EX-169~172 완료. 남은 것은 laya-play 모델 등록과 공식 래더 비교(지시 대기)다.
- **최근 완료**:
  - [EP-233](research/policy-learning/plans/EP-233-laya-foulplay-v11.md)(2026-11-18, 사용자 지시로 중지): v11rt([EX-175](research/policy-learning/experiments/EX-175-laya-v11rt-vs-foulplay-blim128.md))·v11rtc([EX-176](research/policy-learning/experiments/EX-176-laya-v11rtc-vs-foulplay-blim128.md))를 EX-174 Blim 일정으로 foul-play와 붙였다. 중지 시점 v11rt 15승 44패(0.254), v11rtc 12승 39패(0.235). EX-174 v10rt 대비 같은 슬롯 차이 −0.05·−0.06, 구간이 0을 포함한다(판정 보류).
  - [EP-232](research/policy-learning/plans/EP-232-laya-foulplay-v10rt.md)(D-211·D-212, 2026-11-17): 탐색 봇 foul-play(MCTS, 결정당 약 7초)를 고정 상대로 붙였다. Blim 팀 64개 128경기([EX-174](research/policy-learning/experiments/EX-174-laya-v10rt-vs-foulplay-blim128.md))에서 v10rt 42승 85패(정상 127), 점수 0.331 [0.250, 0.414]. Abyssal과 달리 포화되지 않는다. EX-120 팀 일정 EX-173은 경기 없이 중지했다.
  - [EP-230](research/policy-learning/plans/EP-230-laya-ladder-r1500-v10.md)(D-208, 2026-11-07): 최근 래더(레이팅 1500 이상) 경기를 더해 v10을 GPU 4장 DDP로 학습했다.
    - 자료([EX-166](research/policy-learning/experiments/EX-166-laya-ladder-r1500-data.md))는 30,000경기 중 25,296경기를 골랐고, 학습에는 최신 17,510경기 1,111,776행을 썼다.
    - 학습([EX-167](research/policy-learning/experiments/EX-167-laya-v10-ladder-training.md)): 잠긴 test NLL이 대회 −0.038, 래더 −0.099로 둘 다 나아졌다. 테라 지식 held-out은 A 96.2 → 79.3%로 떨어졌다.
    - 배틀([EX-168](research/policy-learning/experiments/EX-168-laya-v10t-v10rt-battle256.md)): v10t 111-17, v10rt 110-18로 퇴보를 배제하지 못했다.
  - [EP-227](research/policy-learning/plans/EP-227-laya-renderer-v10.md)(D-204, 2026-11-03): v1~v9 정보와 lock·전략 정보를 모두 넣은 2,048토큰 v10이다.
    - 학습([EX-161](research/policy-learning/experiments/EX-161-laya-v10-all-info-training.md)): 잠긴 test NLL 1.4332 → 1.3686.
    - 배틀([EX-162](research/policy-learning/experiments/EX-162-laya-v7t-v10t-battle256.md)): v7t 112-16, v10t 111-17로 퇴보를 배제하지 못했다. 기술 실패율은 5.17 → 1.91%다.
- **해석**: v7t 이후 Abyssal 상대 점수는 0.86~0.88에 모여 판본끼리 구별되지 않는다(포화). 잠긴 test 개선이 배틀 성적으로 확인되지 않으므로, 판별은 사람 대전과 직접 대결로 한다. 2026-11-19 [D-214](research/policy-learning/decisions/D-214-laya-foulplay-primary-ladder-final.md)부터 새 laya 배틀 정책 계획은 foul-play 상대 점수(EX-174 Blim 일정)를 개발 목표로 두고, 최종 실험은 공식 래더 대전으로 한다. 흐름은 [배틀 정책 학습·개선](research/policy-learning/INDEX.md)에 정리했다.
- **대기**: [EP-229](research/policy-learning/plans/EP-229-laya-opponent-model-search.md)(D-206, 상대 모델 + 한 턴 탐색). 1단계 [EX-165](research/policy-learning/experiments/EX-165-laya-opponent-prediction-scenes.md)는 완료했다. 모방 모델만으로는 읽는 상대를 예측하지 못한다. 2단계 등록은 사용자 확인을 기다린다.
- **배포**: laya-play v1.10.0(2026-11-07, `Hyung-Youn-Na/laya-play` 태그 `v1.10.0`)에서 v7t·v8t·v8lt·v9t·v10t·v10rt를 `--model`로 고를 수 있다. 사람 테스트 실행기(`.artifacts/laya-v7test`)는 11-05 재부팅 뒤 꺼져 있다.
- **이전 완료 계획**(결과는 각 EP 결과 절):
  - [EP-215](research/policy-learning/plans/EP-215-laya-renderer-v4.md): v4는 실패 기술을 줄였지만 대 v2t 퇴보를 배제하지 못했다.
  - [EP-216](research/policy-learning/plans/EP-216-laya-outcome-weighted-imitation.md): 승패 가중 모방은 악화했다.
  - [EP-217](research/policy-learning/plans/EP-217-laya-head-to-head-evaluation.md): 직접 대결 하네스는 v1만 구별했다. Abyssal이 구별하지 못한 쌍은 직접 대결도 구별하지 못했다.
  - [EP-218](research/policy-learning/plans/EP-218-laya-renderer-v5-item-state.md): v5는 대 v4t 비퇴보다.
  - [EP-219](research/policy-learning/plans/EP-219-laya-v2t-corrected-input-battle.md)·[EP-220](research/policy-learning/plans/EP-220-laya-v2t-tera-decision-defence.md): 테라 합산 결정은 악화, 방어 문구는 구별되지 않음이다.
  - [EP-221](research/policy-learning/plans/EP-221-laya-past-turn-input-v6.md)·[EP-222](research/policy-learning/plans/EP-222-laya-play-teams-abyssal-battle.md): v6s·v6h.
  - [EP-223](research/policy-learning/plans/EP-223-laya-loop-break-opponent-sets.md): 루프 규칙 v6ht-lp만 개선이고 직접 대결로는 확인되지 않았다. v7은 비퇴보다.
  - [EP-224](research/policy-learning/plans/EP-224-laya-engine-judge-v8.md): v8·v8l. EX-154 직접 대결은 CLI 선택지 누락으로 실행되지 않았다(Stopped).
  - [EP-225](research/policy-learning/plans/EP-225-laya-opponent-threat-v9.md): v9.
  - [EP-226](research/policy-learning/plans/EP-226-laya-human-teams-v7-v8-v9.md): 사람 팀, 사용자 요청으로 중지했다.
  - [EP-228](research/policy-learning/plans/EP-228-laya-switch-read-and-mixing.md): 교체 읽기·섞기.

### 규칙 이해 학습(rule-learning)

[EP-211](research/rule-learning/plans/EP-211-jevk5-system1-battle32.md)에 EX116 선택epoch2의 GPU1·2·3 실전32 결과를 기록했다. 정상32경기·5승27패이며 감사·뷰어·봉인·소유자원 반환을 완료했다.

[EP-203](research/rule-learning/plans/EP-203-jevk5-system1-full-training.md)에 전체 System One 학습·독립평가 완료 근거와 실제 개선 여부를 기록했다. 배틀·서버 교체는 별도 범위다.

우선순위별 5종 규칙 적용 System1 자료를
[EP-201](research/rule-learning/plans/EP-201-gen9-mechanics-system1-data.md)에서 생성·검증했다.
Smogon 역할·다른 규칙·관측 KO·조건부 KO 자료의 범위와 산출물은
[규칙 이해 학습·적용](research/rule-learning/INDEX.md)에서 찾는다.
사용자 소유 JevK5 LoRA vLLM 서버는
[EP-190](research/rule-learning/plans/EP-190-jevk5-vllm-serving-check.md)의 기술 확인을 완료한 상태로 유지한다.
기준 JevK5 규칙 선택형 LoRA의 학습 종결 근거는
[EP-184](research/rule-learning/plans/EP-184-jevk5-ruleqa-lora.md)에 둔다.

진행·중단 보존·완료의 전체 목록은 [계획 상태 색인](catalog/plans.md)에 둔다.
중단 기록은 현재 실행 작업과 구분하며 원래 조건과 판정을 유지한다.
Blocked의 현재 처리 필요·후속 종결·확인 사항은 [별도 분류](catalog/blocked.md)에서 확인한다.

## 현재 제약과 다음 단계

- 학습 QA 성적과 실제 배틀 성능을 구분한다. 새로운 비교·평가의 조건은 해당 D·EP·EX에서 정한다.
- 기존 Blocked/Paused, 원자료·동결 protocol·봉인을 유지한다. 새 구조는 실행 재개 승인이 아니다.
- L1–L5 이식은 별도 연구선이며 [보존 맥락](research/l1-l5-port/INDEX.md)에서 연결한다.
- 후속 학습·배틀 평가는 새 범위와 조건을 등록한 뒤 수행한다.
- 문서는 목적별 원문과 생성 색인으로 관리한다. 새 등록·상태 변경 후 catalog build/check를 수행한다.
- 새 배틀 실험의 viewer는 [매뉴얼](RESEARCH_MANUAL.md#battle-viewer-workflow)에 따라
  규격·생성기 판본·확장을 고정하고 실행 전 지원을 확인한다.
  [현재 구현 차이](shared/viewers/ARCHITECTURE.md#viewer-ui-support)를 선행 작업에 반영한다.

## 근거와 작업 안내

[방법별 탐색](catalog/by-method.md) · [실험 목록](catalog/experiments.md) ·
[연구 매뉴얼](RESEARCH_MANUAL.md) · [외부 자산·복원](RESEARCH_WORKFLOW.md)

상태 상세·검증 수치·완료 일지는 각 EP/EX와 최종 보고서에 둔다.
개편 전 상태는 기준선 Git `feda62f`에서 확인하며 현재 문서에 완료 이력을 덧붙이지 않는다.
