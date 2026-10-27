# D-132 — EX-082 정상23경기 계승·4GPU 잔여9경기

- Status: Accepted
- Date: 2026-10-13
- 승인: 현재 사용자 제공 계획의 구현·검증·계승 실행 지시

EX-082의 정상23경기는 보존하고 실패 슬롯 `b04-r2-s0`만 같은 대진·seed로 처음부터
한 번 추가 시도한 뒤 원순서의 미실행8경기를 진행한다. D-130/EX-082의 원자료·봉인·실패·
Blocked는 바꾸지 않고 별도 EX-083에 연결한다.

단일 모델을 GPU0–3에 명시 분할하고 allocator40GiB와 장치 전체44GiB 중단선을 구분한다.
모델·정밀도·보정값·입력·동시성은 유지하며 수치 동등성과 연속 메모리 gate 통과 후에만
본 수집한다. 구체적 조건·분모·중단/해석 원문은
[EX-083](../experiments/EX-083-jev27b-four-gpu-continuation.md), runtime은
[C-064](../CONTRACTS.md#c-064-jev27b-continuation), 진행은
[EP-137](../plans/EP-137-jev27b-four-gpu-continuation.md)이다.

근거는 기존 44GiB 초과 중단과 이번 명시적 사용자 지시다. 다른 대안의 추가 검토 기록은 없다.
학습·양자화·offload·추가 재경기·상한 완화를 허용하지 않으며 혼합 GPU 구간 평가로 보고한다.
