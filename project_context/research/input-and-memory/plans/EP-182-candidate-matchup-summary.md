# EP-182 — 후보별 현재 대면 상성·효과 요약

- 상태: Completed
- 완료일: 2026-10-20
- 생성일: 2026-10-20
- 승인: 후보별 현재 상대 적용결과를 추가하고 v6정보/후보를 유지하자는 제안에 대한 사용자 “오케이 그러면 그렇게 가자”
- 관련: D-167 / C-081 / C-067·C-079, RD의 후보별 현재 대면 요약 절
- branch/checkout: research/model-training /workspace; 시작commit a4659bf298c7935714f9fbd25246db2d831c5926
- 환경: 기존 pokechamp/.venv Python 및 pinned Showdown Dex의 CPU 읽기
- 새코드: integration/candidate_matchup, scripts/candidate-matchup
- 증거: project_context/exec-plans/evidence/ep182 및 .artifacts/candidate-matchup/ep182

## 범위·불변 조건

v6의 원state·상성표·지시문·후보ID/순서/명령을 유지하고 기술후보에 current_matchup 하나를 추가한다.
타입배율·공개면역/무효/반사·기존조건부피해를 분리하며 미상/미지원은unknown이다.
상대교체/테라/행동으로 상태가 바뀌지 않는 현재대면 기준이며 자기 선택Tera는 해당피해branch를 사용한다.
후보 제거/재순위/모델판단 변경·새유료API/32경기/실험 재개는 없다. 모델 선택/승률 효과는 미평가다.

INDEX/CHARTER·매뉴얼·STATUS·RD/계약과 겹치는 EP140/179/181 및 이전읽은 JEV입력 active를 확인했다.
진행 중 EP181은 integration/pokechamp 전체를 source동결하므로 이 subtree·jev27b/jev_eval/jevk5_battle은 수정하지 않는다.
새독립package에서 기존v6를 읽기/호출만 하며 실제진행중 실험의 입력/설정은 바꾸지 않는다.
기존 C-080 표제중복(OpenAI retry/JevK5)을 발견했으며 이번규범은 고유 C-081 anchor를 사용한다.
기존중복ID의 authority를 임의로 정리하지 않고 이작업의 입력 규범에는 의존하지 않는다.

## 완료 기준

- [x] 기술후보별 요약·기술/도구/특성 예외·상태기술·unknown 처리 구현
- [x] v6 무변경/가역제거·후보/명령/순서·OpenAI 변환 무손실 검사
- [x] 저장EX110 면역사례·976결정의 오프라인 보존/coverage 및 독립규칙 검증
- [x] 사용가능 CLI/API·전후예제·지원/한계·현재상태/색인 갱신

## 검증·중단

실행결과/미래/비공개 상대세트를 입력에 넣지 않고 현재v6 payload만 소비한다.
타입0/계산피해0/효과실패를 혼동하지 않는다. 지원 밖 결과를 false/0으로 강제하지 않는다.
실제 API·GPU/배틀0, 비실험 작업이므로 실험시계/재수집/배틀뷰어 요건은 해당없다.

## 진행

- 사용자승인 범위를 등록했다. 현재대면 타입/도구면역과 변화기 예외 원문을 pinned Showdown에서 확인 중이다.

## 결과·증거

- 독립 candidate-matchup-v1 overlay·CLI·OpenAI 요청 변환·옵트인 runtime adapter를 구현했다.
- 19검사 통과(그 안의 pinned Showdown CPU 규칙장면43개). 타입/도구/특성/접지·상태·반사/후속연쇄를 구분했다.
- EX110 저장976결정/5657기술후보에서 요약 제거 후 원JSON/순서 동일, 후보/명령 및 OpenAI 역변환 무손실을 확인했다.
- 지원한 공개 차단과 양수피해의 충돌0. 입력바이트 중앙증가15.44%이며 토큰/선택성능/승률은 미평가다.
- 진행중 동결 runtime/submodule·원v6 생성기·이전실험·뷰어는 수정하지 않았다. 실제API/모델/GPU/실배틀0이다.
- [최종 보고](../../../exec-plans/evidence/ep182/report.md), [전후 예시](../../../exec-plans/evidence/ep182/examples.md),
  [검증](../../../exec-plans/evidence/ep182/validation.json), [사용법](../../../../integration/candidate_matchup/README.md).
