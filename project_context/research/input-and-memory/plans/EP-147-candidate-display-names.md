# EP-147 — 후보 표시 이름 추가

- 상태: Completed
- 완료일: 2026-10-15
- 생성일: 2026-10-15
- 책임자: Codex
- 승인: 현재 사용자 표시 이름 추가 지시 / D-141
- 연구선·checkout: research/model-training, /workspace
- 시작 commit: a4659bf298c7935714f9fbd25246db2d831c5926; 기존 미커밋 작업 보존
- 검증 환경: 기존 actor Python·브라우저; API/GPU/새배틀0
- 증거: project_context/exec-plans/evidence/ep147/

## 범위·불변 조건

새 planner–JEV 후보 설명과 미리보기·기록·뷰어에 표시 이름을 연결한다.
INDEX/CHARTER·매뉴얼·STATUS/plan색인·RD/C, 완료EP-145/146과 active EP-140의 보존 경계를
확인했다. 기존 v6 원 관측/생성기·계산·후보 ID/순서·실행 명령·모델/출력·원자료는 보존한다.
같은 결정의 명시 slot 참조를 사용하고 배열 인덱스나 이전 턴의 이름을 사용하지 않는다.
표시명 없는 과거 동결 설정은 원 동작을 유지하며 새 입력 조건을 manifest에 기록한다.

## 완료 기준·검증

- [x] D-141·C-072·EP 등록
- [x] display_name 생성·설정 기본/호환·planner/JEV/preview 전달
- [x] 뷰어에서 실제 전달 이름 표시·기존 입력 fallback
- [x] 슬롯 재배열/현재 기술 변경/Tera/선봉/교체·정보 부재·후보/명령 보존의 관련 검사
- [x] 대표 실제 저장 입력·3formatter·새 모의 뷰어 검증 및 문서/상태 갱신

이 작업은 표시 설명 추가이며 유료 API/GPU 추론·새배틀·환경변경은 포함하지 않는다.
모의 기록/표시는 배틀 성능 증거가 아니다. 비실험 작업이므로 실험 재수집/시계는 해당 없음이다.

## 진행

- 2026-10-15 — 사용자 요청과 보존 범위를 확인하여 등록했다.
- names-v1·original/legacy 경계와 같은 planner/JEV 후보 전달, 새 뷰어 표시를 구현했다.
  관련94+추가1검사와 저장3결정/24후보·3formatter 대조, 모의재생/오프라인 표시를 확인했다.
  실제 API/GPU/새배틀0이며 과거 출력·봉인은 보존했다.

## 결과·증거

[완료 보고](../../../exec-plans/evidence/ep147/report.md) · [검증](../../../exec-plans/evidence/ep147/completion.json) ·
[표시 예시](../../../../exports/battle_viewers/ep147-candidate-names/index.html).
