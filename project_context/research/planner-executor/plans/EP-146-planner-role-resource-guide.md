# EP-146 — Planner 역할·승리 경로·자원 안내

- 상태: Completed
- 완료일: 2026-10-15
- 생성일: 2026-10-15
- 책임자: Codex
- 승인: 현재 사용자 역할 중심 거시전략 프롬프트 변경 요청 / D-140
- 기준/실제 연구선·checkout: `research/model-training`, `/workspace`
- 시작 commit: `a4659bf298c7935714f9fbd25246db2d831c5926`; 기존 미커밋 변경 보존
- interpreter: `pokechamp/.venv/bin/python` CPU 검사
- 새 증거: `project_context/exec-plans/evidence/ep146/`
- 계약: [C-071](../CONTRACTS.md#c-071-planner-role-guide), C-070

## 목표·범위

Planner 공통 안내를 역할·양측 승리 경로·보존/소모·교환·계획 전환 중심으로 변경한다.
INDEX/CHARTER·연구 매뉴얼·STATUS/plan색인·RD와 완료EP-145, 재개하지 않는 active EP-140의
공개 정보 경계를 확인했다. 참고 문헌은 출처·세대/format 범위를 명시하고 일반 원칙만 적용한다.
새 guide 파일과 선택/동결·조립·비교 식별, 사용자 설명을 변경한다. 기존 v6 입력·role DB·
계산·JEV 지시문·6필드 출력·호출 정책·원자료/뷰어는 변경하지 않는다.
역할 가설과 공개 사실·지원 능력을 구분하며 정확한 보존 HP나 상대 세트를 만들어내지 않는다.
유료 API·GPU·새배틀은 없고 구문/입력/동결·비교 경계와 무호출 미리보기만 검증한다.

## 완료 기준

- [x] ADR·EP·방법/계약 등록
- [x] 출처 기반 역할/승리경로/자원 안내와 한국어 구조 설명
- [x] prompts.guide 선택·동결·새 기본값·기존준비본 호환
- [x] guide 변경을 planner 프롬프트 차이로 식별·행렬 중복 제거 보완
- [x] 동일 관측·후보·JEV 경계와 관련 회귀·미리보기 검증
- [x] 결과/사용법·상태/색인 갱신

## 검증·중단

실제 입력/가중치 변경 없이 새 system guide만 바뀌는지 확인한다. 원문 동결 후 source prompt 편집이
준비본을 바꾸지 않는지, 동일 front prompt의 서로 다른 guide가 행렬에서 합쳐지지 않는지,
guide 없는 과거 메시지 조립과 비교를 유지하는지 검사한다. 내용 품질·승률은 미평가다.
추가 모델/배틀 실험 승인·예산은 없으며 비실험 문서/프롬프트 교정에 실험 재수집/시계는 해당 없다.

## 진행

- 2026-10-15 — 원문 조사와 기존 role_summary 경계를 확인하고 새 범위를 등록했다.
- 역할·승리경로·자원 guide와 선택/조립·동결·비교 식별을 구현했다.
  관련80 CPU검사, 기본 무호출preview, 독립 읽기/CPU검토를 완료했다. 실제API/GPU/새배틀0.

## 결과·증거

[최종 보고](../../../exec-plans/evidence/ep146/report.md) · [완료](../../../exec-plans/evidence/ep146/completion.json) ·
[설계·출처](../../../../docs/pokechamp-planner-macro-strategy.md) ·
[안내 원문](../../../../integration/jev_planner/prompts/role-resource-guide-v1.txt).
새 준비 설정부터 적용되며 실제 모델의 전략 품질과 배틀 성능은 미평가다.
