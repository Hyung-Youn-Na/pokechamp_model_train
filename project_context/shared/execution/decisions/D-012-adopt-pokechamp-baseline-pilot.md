# D-012 — PokéChamp 기준선 pilot 채택

- 상태 (Status): Accepted
- 날짜 (Date): 2026-09-06
- 근거: 사용자가 검토한 기준선 실험 계획에 대해 `Implement the plan`을 지시했다.

## 결정

현재 pinned minimax(K=2, optimized), IO, Abyssal, OneStep, Random을 Gen9 OU에서 비교한다.
LLM은 공통 glm-5.3-flash/Ollama Cloud, low effort, 8192 context, 최대 512 output tokens다.
알고리즘 내부 temperature와 정상 damage-calculator 분기는 보존한다. 모델 오류 후
fallback으로 성공을 만들지 않는다. IO와 minimax 비교는 방법 bundle 비교다.

팀 1·2를 포함한 8개는 개발용, 나머지 5개는 확증용이다. Seed 20260906의 명시적 배정,
대진별 공통 2개 블록과 팀/진영 교환으로 10대진 × 2블록 × 2경기 = 40개 pilot slot을 만든다.
Pilot은 추정·운영 목적이며 우월성 가설을 검정하지 않는다. 본 실험 N과 자원 한도는
pilot 보고서 이후 사용자 결정 사항으로 남긴다. 승패를 보고 표본을 늘리지 않는다.

C-008 qualification의 고정 seed와 IO-only 검증은 유지한다. 별도 benchmark 경로에서만
경기별 seed와 call role을 사용한다. Source submodule은 수정하지 않는다. Benchmark는
C-009 actor별 관찰 bundle 두 개와 C-010 match/control record를 연결한다. 기존 bundle의
classification/efficacy_evidence를 소급 변경하지 않는다. 관찰 bundle만으로 효능을 주장하지 않는다.

## 검증 및 해석

모든 attempt와 제외 이유를 보존한다. Transport/rate-limit/provider timeout만 동일 slot으로
한 번 재시도한다. Auth/configuration/evidence 오류는 batch를 중단한다. 출력/알고리즘 오류와
watchdog 중단은 패배가 아니며 성공할 때까지 재시도하지 않는다. 확증 자료를 개발·학습에 넣지 않는다.
원본 대조군을 개선판과 같은 시기에 재측정한다. 한번 열람한 확증 세트는 이후 개발용이다.

## 영향

EP-004와 EX-001이 실행과 evidence를 관리한다. 본 실험, L1-L5 구현, 논문 수치 재현은 미승인 범위다.

## 구현 검증에 따른 실행 기록 분리

Peer cancellation 보완으로 EX-001을 7-slot 후 중단·보존하고 EX-002를 새 source snapshot으로
실행한다. 연구 조건과 40-slot protocol은 같으며 두 cohort를 섞지 않는다.

## 실행 후 관찰과 도구 보완 (2026-09-07)

EX-002는 40-slot 처리를 완료했다. Actor 자체 원인은 출력 검증 8건/시간 초과 1건이지만
worker 종료 관찰 순서로 match summary 5건이 일반 algorithm 분류였다. Actor 원자료와 원
summary를 보존하고, 실행 후 최종 actor 오류의 재집계로 이후 auth 중단·transient retry를
보호했다. 해당 실험에 transient/hard-stop actor 오류는 없어 누락된 retry/batch stop은 없다.
이 보완은 agent 선택 정책이나 이미 수집한 outcome/eligibility를 바꾸지 않는다.

분석은 자체/peer 오류와 실제 action fallback을 구별하고, main 자원을 대진별로 환산한다.
분석 source 사본과 hash를 파생 보고서에 남긴다. 관찰된 upstream `depth` 오류를 숨기거나
외부 pinned 구현을 수정하지 않으며, 본 실험 확대와 알고리즘 수정 조건은 별도 결정 사항이다.
