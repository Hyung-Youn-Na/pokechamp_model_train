# EX-061 — EX-060 기반 Qwen3.5-4B 행동가치 개발 실험

- 상태: Completed
- 등록일: 2026-09-28
- 승인: 사용자 계획 구현 지시 / D-098 / EP-102

## 질문·자료·해석

RQ: 양측 Abyssal 후속 q 학습으로 동일 개발 자료의 q 오차·표본 regret이 어떻게 바뀌는가?
EX-060 전체22관측·167행동·5,344분기(후보당32회)를 읽기 전용 재집계한다.
모두 개발 학습 자료이며 독립 validation/test 없음. 반전만 추출하지 않는다.
타깃 [q,1-q], q=(승+0.5무)/32. 서로 다른 행동 q의 합은1일 필요가 없다.

## 동결 실행 조건

- EVE worktree `.venv-eve-rlcd`, dependency lock 불변.
- `Qwen/Qwen3.5-4B`, revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`.
  공식 `Qwen3_5ForCausalLM`·text config, vision/MTP 공식 제외만 허용·text tensor 일치 검사.
- 원관측·규칙·역할 전문, 합법 후보·평가 행동. provenance/집계/원선택/미래 정보 제외.
  Qwen chat template `enable_thinking=False`, A=true/B=false 마지막 hidden letter readout.
  `max_len=16384`, 초과 오류·절단0·질문별 독립 forward·microbatch1.
- LoRA r8/alpha16/dropout0, text backbone 모든 Linear, embedding/LM head 고정.
  기본/adapter FP32, forward BF16 autocast, readout/loss FP32.
  gradient checkpointing `use_reentrant=False`, `use_cache=False`.
- 손실 `mean_s mean_a (0.5 * sum((pi-[q,1-q])**2))`.
  관측마다 모든 후보 gradient를 평균한 뒤 update. bandit RLCD와 구분한 전체 정보 학습.
- AdamW lr5e-5, betas(0.9,0.95), weight_decay0, clip1.
  seed20260929, epoch별 관측/후보 shuffle, 3epoch·66update·501학습 forward/backward.
- 물리 GPU1 RTX A6000 48GB 한 장·시간 상한 없음. GPU시간·VRAM 실측 보존.
  단가 미제공으로 금액 미산정. API0·새 배틀0.
- 최장 입력 forward/backward 사전검사(update0) → 무학습167예측 → epoch별167예측 →
  마지막 checkpoint 새 프로세스 재로딩167예측. 평가 forward835회 예정.

## 지표·성공

관측별 후보 평균을22관측 평균한 q MSE, binary Brier(2×MSE), MAE.
후보 q 차이가 있는11관측의 가치 오차·regret·최고 표본평균 선택률·순위는 별도 분모다.
단일 후보2개·모든 후보 q0인9개는 학습/전체 오차에 유지한다.
선택은 최대 예측 q, 동률은 원후보 순서. q_values와 합법 choice/command를 저장한다.
불확실성은 같은 관측·반복의 모든 후보를 함께 재표집하며 표본 최고와 확정 최선을 구분한다.

기술 성공: 유한 loss/gradient·66update·LoRA 변경·기본 가중치 불변·재로딩 최대 차이≤1e-4.
개발 적합 성공: 전체 및11관측 MSE 각각 기준선보다≥10% 감소·11관측 평균 regret 비증가.
적합 기준 미달도 정상 결과. 배틀 성능 저하나 코드 실패로 해석하지 않는다.
q는 고정 숨은 상태·원대진·Abyssal 후속 정책 조건의 교사 값이며 학습 모델 전경기 승률이 아니다.
0/32승의 불확실성·원대진 선택 편향·Abyssal 일반 테라 미사용 한계를 유지한다.

## 검증·중단·복구

집계 일치·최종 입력 경계·타깃 변경 후 동일 토큰·합법 명령·무절단,
RLCD 기대경사·LoRA/freeze·저장 재현성을 검사한다.
입력 누출·집계 불일치·행동 매핑 오류·필수 가중치 불일치·비유한 loss/gradient·CUDA OOM은
의존 학습 전체 중단이다. 처치/자원 조건의 조용한 변경을 막기 위한 예외다.
느리다는 이유로 중단하지 않는다. 해당 실패 뒤 GPU 학습 재시도/재수집0.
GPU 전 구현·fixture 결함은 RD11.1/C-018 교정·독립 검증 가능.
평가 코드만 결함이면 온전한 저장 예측 전부를 같은 사전 기준으로 재평가한다.
최초 GPU 사전검사부터 누적 wall/GPU 측정, halt/error·partial checkpoint·progress 보존,
실행 덮어쓰기 거부. 공급자/API/배틀이 없어 RD11.2/C-046 경기 격리는 해당 없음.

## 후속 평가 경계·결과

EX-058 원대진·EX-060 전체는 후속 독립 배틀 평가에서 제외한다. 팀/대진 계열·동일 상태
행동/반복을 분할 양쪽에 두지 않는다.64블록×진영2×모델2=256경기 탐색안의 팀·seed·봉인은
별도 계획이며 이번 범위 밖이다.
고정3epoch·66update·501학습/835평가 forward 완료. 기술 성공 true, 동결 MSE/Brier·regret 기준의
개발 적합 true. 재로딩 최대 확률 차이0.0, base 불변·LoRA 변경·유한 loss/gradient 확인.
전체/11관측 MSE는 기준선 대비41.2%/43.4% 감소, 11관측 regret0.2982955→0.0681818·최고 선택3/11→7/11.
전체 MAE는0.1557491→0.1662501로6.7% 증가했으며 모든 오차 지표의 개선은 아니다.
원자료 보존·새 자료 봉인·GPU/감시 정리 완료, 추가 배틀0·독립 성능 미평가.
실행 source-v1 보존, 종료 후 source-v2의 CUDA peak 로그만 교정·GPU 재실행0.
준비 cache metadata 실패·제어 daemon 복구·CPU 환경 호출 교정은 처치 변경 없이 별도 증거에 보존했다.
실행 자료 `.pokechamp-data/training/ex061/`, [최종 보고](../../../exec-plans/evidence/ep102/report.md),
[전수 검증](../../../exec-plans/evidence/ep102/final-verification.json), [봉인·정리](../../../exec-plans/evidence/ep102/closure.json).
