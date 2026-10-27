# EP-194 — EX-112 입력 구조 참조 문서

- 상태: Completed
- 생성일: 2026-10-21
- 승인: 사용자의 이전 채팅 입력 구조를 적절한 위치에 문서화하는 요청.
- 연구선·checkout·시작 commit: research/model-training /workspace feda62f733c1b470364868262c789ec857ef67f5.
- 기존 미커밋 변경 보존. 문서 전용 작업으로 실행 interpreter는 해당 없음; 색인은 기존 Python 사용.
- 관련: EX-112, EP-182/183, C-067/C-081/C-082 및 OpenAI 변환 코드.
- 새 산출물: 같은 주제의 EX112_INPUT_STRUCTURE.md, 탐색 링크, 등록/생성 색인.

## 범위

채팅에서 설명한 jev-choice-v6 + candidate-matchup-v1의 전체 필드 구조·역할·조건부 필드·
타입 상성표/후보 요약 관계와 실제 API 포장 형식을 한국어로 정리한다.
새 문서는 설명용 참조이며 입력/계약/연구 방법·평가·원자료·뷰어를 변경하지 않는다.
INDEX/CHARTER/매뉴얼·STATUS/계획 색인, 입력 주제 INDEX/CONTRACTS/ARCHITECTURE,
관련 EP-182/183/140 및 기존 설명서의 버전 범위를 확인했다. 기존 Blocked/Paused는 유지한다.

## 완료 기준

- [x] 논리 입력/팀/기술/계산/상성표/속도/로그/후보별 요약/API 구조와 해석 경계 기록
- [x] 주제 색인·EX-112·구현 README·기존 입력 안내에서 새 참조 연결
- [x] 저장 자료/코드와 대조, 링크·문서 확인, catalog build/check

## 검증·중단

앞선 채팅에서 읽은 EX112 저장 입력과 실제 변환/요약 코드를 기준으로 필드와 조건을 대조한다.
문서 작업이므로 runtime/브라우저/모델 테스트는 수행하지 않는다. 비실험으로 재수집/시계 해당 없음.
충돌 발견 시 INDEX 절차를 따르며 상위 규범을 임의 변경하지 않는다.

## 진행·결과

- 2026-10-21 — 승인 범위 등록. EX112 범위를 명시한 목적별 참조 문서로 정리한다.

- 2026-10-21 — [입력 구조 참조](../input-structures/EX112_INPUT_STRUCTURE.md)를 작성하고 주제 색인·EX112·
  candidate_matchup README·기존 입력 요약 설명서에서 연결했다.
  저장913결정의 state/self_team/opponent_team/후보 키 명칭을 대조하고 세부 의미·API 형식은
  변환/요약 코드와 확인했다. 참조 문서의13개 링크·앵커 및 코드 블록/공백 검사 통과.
  catalog build/check를 완료했다. 코드·입력·원자료·뷰어·기존 판정 변경0이며 runtime 검사는 미실행이다.
  승인된 문서 작업의 미충족 기준은 없다.
