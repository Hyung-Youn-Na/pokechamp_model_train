# D-148 — JEV-35B-NVFP4 단일 GPU 동일 대진 샘플

- 상태: Accepted
- 날짜: 2026-10-15
- 승인: 현재 사용자가 제공한 계획의 구현·검증·실행 지시

EX-094 첫 슬롯의 새1경기를 autotrust/JEV-35B-NVFP4 고정 revision으로 실행한다.
GPU0 단독 Marlin W4A16·공식 System 1 서버와 전용 Python3.11 환경을 추가한다.
기존 세 모델 경로·EX-093/094 원문·봉인·중단 상태를 보존한다.
공식 CUDA12.9 vLLM0.31.0과 Transformers5.17.0을 사용하며 드라이버 변경·모델 대체·GPU
추가·양자화 변경을 자동 수행하지 않는다. 진입 실패 시 GLM/배틀 호출을 하지 않는다.
조건·예산·검증·실패 분모와 완료 기준의 원문은 [EX-095](../experiments/EX-095-jev35b-nvfp4-sample.md),
구현·검증 진행은 [EP-154](../plans/EP-154-jev35b-nvfp4-sample.md)다.
