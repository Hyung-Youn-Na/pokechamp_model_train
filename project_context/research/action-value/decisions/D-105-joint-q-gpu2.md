# D-105 — 공동 q 학습의 GPU2 지정

- 상태: Accepted
- 날짜: 2026-09-30
- 승인: 현재 사용자의 “학습은 2번 gpu를 사용하도록 해주세요.”

## 결정과 근거

[D-104](D-104-joint-q-training.md)의 EX-066 학습은 물리 GPU2 A6000 48GB 한 장을 사용한다.
사전검사·독립 진단·재로딩·평가도 같은 GPU로 맞춘다. 물리 GPU1에서 수행한 최초 사전검사와
padding 결함 재현은 과거 증거로 보존한다. 모델·데이터·입력·타깃·학습량·평가 기준은 유지한다.

GPU 변경 지시가 도착한 시점에는 학습 update와 test 평가가 모두0이었다. 진행 중인 CPU
재준비만 정상 중단하여 `versions/prepare-gpu1-interrupted/`에 source·부분 입력·중단 원문을
보존한다. 기존 최초 시계는 유지하고 GPU2 설정으로 다시 동결한다. 원 token/cache 파일의
동일성과 padding 교정의 독립 검증을 확인한 receipt만 이 준비 중단과 원 사전검사의 재검사를
연결한다. 다른 중단을 우회하거나 학습/test 재수집을 허용하지 않는다.

실행 조건의 원문은 [EX-066](../experiments/EX-066-joint-q-training.md),
진행은 [EP-108](../plans/EP-108-joint-q-training.md)이다.
