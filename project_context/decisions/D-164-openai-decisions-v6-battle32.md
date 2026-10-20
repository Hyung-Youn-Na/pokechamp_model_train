# D-164 — OpenAI Decisions v6 상세32경기

- 상태: Accepted
- 날짜: 2026-10-20
- 승인: 사용자의 v6 상세 입력 기반 OpenAI decision 모델32경기 실행 요청

## 결정·근거

기존 EX-089의 팀·고유32슬롯·16진영교환쌍·seed·Abyssal·Gen9 OU·테라 허용·timer off를
새 EX-109에 명시 채택한다. 교정된 v6 상세 상태·전체 합법 후보·원 지시문을 유지하며
planner와 후보 표시명 추가는 사용하지 않는다. OpenAI gpt-6-luna의 전용 Decisions API에
state를 JSON 텍스트로, 후보ID/내용을 choice value/description으로 전달한다.

모델/서빙/전송 형식이 다른 탐색 평가다. 기본 API 환경 준비만 승인했던 D-163에서 이번
새32경기·최대3사전 연결 요청으로 범위를 확장한다. 재시도0·재경기0이며 다른 모델로 대체하지 않는다.
C-046의 합법 선택 우선·보조 확률 진단과 C-047의 뷰어 완료 요건을 적용한다.

## 영향·증거

배틀과 계산은 CPU 기존 환경, 모델은 OpenAI API다. GPU 로딩·학습은 없다.
조건/한도/해석은 [EX-109](../experiments/EX-109-openai-decisions-v6-battle32.md),
구현/검증은 [EP-179](../exec-plans/active/EP-179-openai-decisions-v6-battle32.md)에서 관리한다.
[공식 API](https://developers.openai.com/api/reference/resources/decisions/methods/create).
