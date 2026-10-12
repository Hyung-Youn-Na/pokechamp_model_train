# D-106 — 공동 q 학습의 유휴 GPU 대체

- 상태: Accepted
- 날짜: 2026-09-30
- 승인: 현재 사용자의 “만약 해당 GPU가 활용중이면 다른 유휴 gpu를 찾아서 사용해주세요.”

## 결정과 근거

[D-105](D-105-joint-q-gpu2.md)의 GPU2 우선 지정에 사용 중일 때 다른 유휴 GPU를 쓰는
후속 승인을 적용한다. GPU2는 다른 프로세스가 사용 중이며 물리 GPU1 A6000 48GB는 유휴다.
이번 학습·사전검사·독립 진단·재로딩·평가는 GPU1 한 장으로 고정한다.
모델·데이터·입력·학습량·평가 기준은 그대로 유지한다.

GPU2의 CPU 준비를 완료한 시점에도 GPU forward·학습 update·test 평가는0이었다.
`versions/prepared-gpu2/`에 완료 준비본·source·protocol·검사를 보존한다. 처음 GPU1의
사전검사 실패와 D-105 지정 때의 CPU 중단 증거도 보존한다. 최초 시계를 유지하고 GPU1로
새 source/config를 동결하여 원 token/cache 동일성과 padding 교정의 독립 증거를 확인한다.
receipt는 이 명시적 GPU 대체와 기존 준비 중단만 연결하며 다른 중단이나 학습/test 재수집은
허용하지 않는다. 다른 소유자의 프로세스는 종료하지 않는다.

실행 조건의 원문은 [EX-066](../experiments/EX-066-joint-q-training.md),
진행은 [EP-108](../exec-plans/active/EP-108-joint-q-training.md)이다.
