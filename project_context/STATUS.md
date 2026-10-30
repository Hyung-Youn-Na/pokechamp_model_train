# 프로젝트 상태

- 기준일: 2026-10-26
- 연구선·checkout: `research/model-training` · `/workspace`
- 목표: 포켓몬 모델 학습·정책 개선·독립 평가. [CHARTER](CHARTER.md)

<a id="current-objective"></a>

## 현재 목표

규칙 이해 학습과 행동 적용, 입력 표현 및 모델 정책의 평가를 목적별로 관리한다.
학습·모델 선택과 분리한 평가를 사용하며 연구 주제별 범위는 [연구 목록](research/INDEX.md)을 따른다.

<a id="active-work"></a>

## 현재 작업

[EP-211](research/rule-learning/plans/EP-211-jevk5-system1-battle32.md)에 EX116 선택epoch2의 GPU1·2·3 실전32 결과를 기록했다. 정상32경기·5승27패이며 감사·뷰어·봉인·소유자원 반환을 완료했다. GPU0/8107의 EP210과 분리했다.


[EP-203](research/rule-learning/plans/EP-203-jevk5-system1-full-training.md)에 전체 System One 학습·독립평가 완료 근거와 실제 개선 여부를 기록했다. 배틀·서버 교체는 별도 범위다.

[EP-208](research/policy-learning/plans/EP-208-laya-compact-imitation.md)에서 EX-071 스냅샷을 1,024토큰 이하로 압축해 laya 0.4.13을 학습하고([EX-118](research/policy-learning/experiments/EX-118-laya-compact-imitation-training.md)) EX-089 표준 32경기로 평가한다([EX-119](research/policy-learning/experiments/EX-119-laya-compact-imitation-battle32.md)). 환경은 [EP-207](shared/execution/plans/EP-207-laya-0413-environment.md)이며 GPU0·포트8107만 사용해 EP-203(GPU1–3)과 자원이 겹치지 않는다. 2026-10-22 완료: 잠긴 test NLL 1.4716·일치율 46.78%, 배틀 25승0무7패(32/32 정상). 후속 [EX-120](research/policy-learning/experiments/EX-120-laya-team-generalization128.md)(D-184/EP-209)에서 새 팀 32개 128경기를 평가했다. 결과는 89승0무39패(0.695), 조합 클러스터 95% [0.617, 0.773]로 새 팀에서도 Abyssal보다 우세했다. 렌더러 v2([EX-121](research/policy-learning/experiments/EX-121-laya-v2-all-training.md)/[EX-122](research/policy-learning/experiments/EX-122-laya-v1-v2-battle256.md), EP-210)는 test NLL 1.4435(차이 구별되지 않음)이고 같은 실행 256경기에서 v2 102승26패, v1 89승39패로 개선(+0.102 [0.023, 0.180])됐다. 테라 지식 실험(EP-212, GPU1·8109): [EX-124](research/policy-learning/experiments/EX-124-laya-v2-tera-knowledge-training.md)에서 지식은 held-out 96%까지 습득했지만 테라 재현은 개선 없음이었다. [EX-125](research/policy-learning/experiments/EX-125-laya-v2-tera-battle256.md)는 111승17패 대 102승26패, 차이 +0.070 [0.000, 0.141]로 구별되지 않음이고, 테라 사용은 16에서 22경기다. GPU1과 8109는 반환됐다. GPU0과 포트 8107은 반환됐다.

[EP-214](research/policy-learning/plans/EP-214-laya-renderer-v3.md)(D-189, GPU0·8107)에서 래더 대비로 상대 세트 추론 렌더러 v3를 학습하고([EX-128](research/policy-learning/experiments/EX-128-laya-v3-tera-training.md), EX-124 대비 교체 행 NLL), 진행 조건 충족 시 Abyssal 256경기 비퇴보를 확인한다([EX-129](research/policy-learning/experiments/EX-129-laya-v2t-v3t-battle256.md)). 사용자 지시로 학습과 배틀은 별도 승인 없이 이어서 실행한다. 2026-10-25 시작. EX-128 완료: test NLL 1.4391(EX-124 1.4506), 교체 −0.034 [−0.085, +0.016], 전체 −0.012 [−0.043, +0.0200]로 진행 조건 미충족(비열등 상한 0.000034 초과). 사용자 결정으로 이탈을 [D-190](research/policy-learning/decisions/D-190-laya-ex129-gate-override.md)에 기록하고 EX-129를 실행 중이다.

[EP-215](research/policy-learning/plans/EP-215-laya-renderer-v4.md)(D-192, GPU1·8109)에서 EX-122 실패 반복 분석에 따라 확정 실패 표시와 교체 후보 공격 피해를 넣은 렌더러 v4를 학습하고([EX-130](research/policy-learning/experiments/EX-130-laya-v4-tera-training.md), EX-124 대비 보고 전용), 오프라인 결과와 관계없이 Abyssal 256경기로 비교한다([EX-131](research/policy-learning/experiments/EX-131-laya-v2t-v4t-battle256.md), D-191). 2026-10-26 시작.

[EP-216](research/policy-learning/plans/EP-216-laya-outcome-weighted-imitation.md)(D-193, GPU0·8107)에서 EX-124와 같은 설정에 리플레이 승패 가중치(이긴 쪽 1.0, 진 쪽 0.5, 평균 1)만 더해 모방 학습하고([EX-132](research/policy-learning/experiments/EX-132-laya-v2t-outcome-weighted-training.md)), 오프라인 결과와 관계없이 Abyssal 256경기로 비교한다([EX-133](research/policy-learning/experiments/EX-133-laya-v2t-v2tw-battle256.md)). 2026-10-26 시작.

[EP-217](research/policy-learning/plans/EP-217-laya-head-to-head-evaluation.md)(D-194, GPU2·8108)에서 Abyssal 천장(v2t 0.867)을 넘는 판별을 위해 laya 직접 대결 하네스를 만들었다. v2t 대 v2·v1·v2te·v3t 512경기([EX-134](research/policy-learning/experiments/EX-134-laya-head-to-head512.md))를 진행하고, EX-132·EX-130 봉인 뒤 v2t 대 v2tw·v4t([EX-135](research/policy-learning/experiments/EX-135-laya-head-to-head-v2tw-v4t.md))를 이어서 둔다. 2026-10-26 시작. 같은 작업에서 [EX-127](research/policy-learning/experiments/EX-127-laya-v2t-v2te-battle256.md) export를 마쳐 EP-213을 완료했다(v2te − v2t −0.070 [−0.148, +0.008], 구별되지 않음).

[EP-219](research/policy-learning/plans/EP-219-laya-v2t-corrected-input-battle.md)(D-196, GPU1·8109)에서 v2+테라(EX-124)를 재학습 없이 D-195 보정 입력으로 서빙해 Abyssal 256경기를 뒀다([EX-139](research/policy-learning/experiments/EX-139-laya-v2t-corrected-input-battle256.md)). 2026-10-27 완료: fix 110승 18패(EX-125 v2t 대비 −0.008 [−0.023, 0.000]), info 108승 20패(−0.023 [−0.063, +0.016]), 둘 다 구별되지 않음. 공개된 풍선 상대 지면 기술은 9회에서 0회가 됐다.

[EP-220](research/policy-learning/plans/EP-220-laya-v2t-tera-decision-defence.md)(D-197, GPU1·8109)에서 같은 체크포인트·fix 입력으로 테라 합산 결정(k=1·3)과 테라 방어 문구를 재학습 없이 시험한다([EX-140](research/policy-learning/experiments/EX-140-laya-v2t-tera-decision-defence384.md), 384경기, 기준 EX-139 fix). 모델이 테라 확률은 사람만큼 매기지만 1순위 선택 때문에 거의 쓰지 않는다는 분석에 따른 것이다. EP-218(GPU0·GPU2)과 자원이 분리돼 있고, 코드 작업은 EX-136 학습 중에 끝냈다. 2026-10-27 05:28Z에 실행을 시작했다.

[EP-221](research/policy-learning/plans/EP-221-laya-past-turn-input-v6.md)(D-198, GPU0·8107, GPU1·8109)에서 같은 기술 반복을 줄이기 위해 과거 턴 입력 두 가지를 동시에 학습한다. v6s는 1,024 안에 반복 표시(`streak`)를 넣고([EX-141](research/policy-learning/experiments/EX-141-laya-v6s-streaks-training.md)), v6h는 2,048토큰으로 늘려 4턴 이전까지 기록을 넣는다([EX-142](research/policy-learning/experiments/EX-142-laya-v6h-long-history-training.md), 파서 opt-in 필드 `early_history`). 2026-10-30 완료: 두 방법 모두 반복을 줄이지 못했고 배틀은 둘 다 "퇴보를 배제하지 못함"이다(EX-143 −0.023, EX-144 −0.063). v6h는 교체 결정의 사람 선택 재현만 나아졌다. [EP-222](research/policy-learning/plans/EP-222-laya-play-teams-abyssal-battle.md)(D-199, GPU2·8108)에서 laya-play 완성 팀 74개로 v5t·v6st·v6ht를 Abyssal과 다시 비교한다(EX-145, 888경기). 2026-10-30 시작.

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
