# D-108 — pokechamp r1 Kev-4B 연결 검증

- 상태: Accepted
- 날짜: 2026-09-30
- 승인: 현재 사용자의 학습된 Kev-4B 연결·수락 검사 의뢰

읽기 전용 `/ref/kev`의 로컬 r1 LoRA/head를 결정 서버로 사용한다. C-051 JointInput의
compact JSON 문자열과 학습 builder의 후보별 noul 질문을 그대로 보내며 최대 p(true),
동률 원순서로 명령을 선택한다. 원 Abyssal 선택·private 정보·타깃은 입력에 넣지 않는다.

새 실행은 validation 재현과 1경기 연결 smoke다. 승패로 성능 개선을 주장하지 않는다.
서버 시작은 사용자가 별도로 허용하거나 직접 준비해야 하며, 허용 시 `/ref/kev/.venv/bin/python`,
GPU3만 사용한다. `/ref/kev` 수정·uv sync/run·재학습·Kev test partition 열람은 금지한다.
원 실행/가중치와 EX-066은 보존한다. 동결 실행 조건은 EX-068, runtime은 C-054,
진행은 EP-111이 소유한다.
