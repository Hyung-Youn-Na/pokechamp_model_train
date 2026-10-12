# D-129 — EX066 epoch3의 GPU0 배틀 평가

- 상태: Accepted
- 날짜: 2026-10-08
- 승인: 현재 대화의 GPU0 실제 배틀 요청, test20·기존 재현 기준 복구·8시간 선택 및 계획 구현 지시

EX-066의 선택 epoch3 체크포인트를 읽기 전용으로 사용하여 별도 EX-081에서 실제 대전을 평가한다.
사용자는 EX-065 기존 test20 대진, 원 재로딩 허용오차1e-4 복구 후 대전, 전체8시간을 선택했다.
추가 학습·EX-066 오프라인 test 평가·초기 모델의 새 대전은 포함하지 않는다.
EX-066 STOP·원 예측·가중치·봉인과 Blocked 판정은 보존하고 별도 복구 증거를 연결한다.
GPU0 소유 서버·Showdown·worker 시작/정리는 승인 범위며 다른 GPU/실행·공유 환경은 변경하지 않는다.

실행 조건 원문은 [EX-081](../experiments/EX-081-joint-q-battle.md), 진행은
[EP-133](../exec-plans/completed/EP-133-joint-q-battle.md), runtime 경계는 C-062다.
