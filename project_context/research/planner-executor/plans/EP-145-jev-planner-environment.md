# EP-145 — GLM planner–JEV 실험 설정 환경

- 상태: Completed
- 완료일: 2026-10-15
- 생성일: 2026-10-15
- 책임자: Codex
- 승인: 현재 사용자 `Implement the plan.` / D-139
- 기준/실제 연구선: `research/model-training`; checkout `/workspace`
- 시작 commit: `a4659bf298c7935714f9fbd25246db2d831c5926`; 기존 JEV·문서 미커밋 변경 보존
- interpreter: actor `pokechamp/.venv/bin/python`, CPU tokenizer는 기존 JEV 모델 환경
- 새 증거: `project_context/exec-plans/evidence/ep145/`; 모의 출력은 해당 증거 하위
- 관련 원문: [C-070](../CONTRACTS.md#c-070-jev-planner),
  [D-139](../decisions/D-139-jev-planner-environment.md)

## 목표·범위

호출 규칙과 프롬프트 파일만 바꾸어 입력 미리보기·모의 비교·기록 열람을 재현할 수 있게 한다.
새 `integration/jev_planner/`와 `scripts/jev-planner`에 설정·동기 planner·JEV 연결·비교·뷰어를 둔다.
기존 formatter/모델/관측/로컬 서버는 명시 프로필로 재사용하고 과거 실행기 기본값은 유지한다.
INDEX/CHARTER·매뉴얼·RD/C와 겹치는 active EP-013/044/045/048/062/064/075/077/080/134/140의
보존 경계를 확인했다. 구현 시작 전 새 범위를 등록하며 과거 실행은 재개하지 않는다.

유료 모델 API·GPU 추론·모델 다운로드·환경 재설치는 범위 밖이다. 실제 실행 인터페이스는
새 EX·일정·호출/자원 한도를 요구하며 이번에는 모의 공급자와 CPU/로컬 Showdown으로 검증한다.
기존 평가 자료는 대표 기술 검사에만 읽고 학습·효능 평가에 편입하지 않는다.
독립 core/planner, 배틀 연결, 보고/뷰어를 서브에이전트에 분리 위임한다. 주 에이전트는
공유 설정·CLI·문서·통합 및 필수 검증을 담당하며 같은 파일을 동시에 수정하지 않는다.

## 완료 기준

- [x] 승인·EP/ADR·연구/실행 계약 등록
- [x] 독립 JSON 설정·프롬프트2종·6호출 정책·3수행모델 선택
- [x] 동기 planner·동일 cutoff·단일후보 무호출·중복 방지·경기 실패 격리
- [x] preview/prepare/run 모의·실제 인터페이스와 실행별 원문 고정
- [x] 호출/계획/선택/비용 비교·오프라인 viewer
- [x] 관련 CPU 회귀·모의 로컬 배틀·대표 무절단 토큰화·오프라인 화면 검증
- [x] 사용 예제·한국어 안내·검증 보고·관련 상태/색인 갱신

## 검증·중단

단일후보 뒤 사건 누적·동일턴 다른 rqid·같은 rqid 재전송·계획 대기 중 새 로그·사건/주기 중복과
주기 재설정, off 입력 보존, 후보/명령 순서, 비공개/미래정보 배제·모델별 formatter를 검사한다.
모의 공급자로 실제 로컬 선택/전송과 실패 격리를 확인한다. 관련 변경·실패 없는 전수 재감사는
추가하지 않으며 identity·관측·원자료 보존 검사는 유지한다. 적용 범위는 C-070과 RD11.1/11.2다.
이번 비실험 작업의 유료 복구/재수집·실험 시계는 해당 없음이다. 검증 실패는 영향받는 경로를
수정·재검증하고 기존 기록을 보존한다. 환경 검증 완료는 실제 공급자/GPU 성공이나 효능 검증이 아니다.

## 진행

- 2026-10-15 — 사용자 확정 계획 구현 범위 등록. API/GPU/새 모델 실험0.
- 동기 controller·공개 사건·Z.ai 전송, 새 배틀/runtime, 집계/오프라인 뷰어를 분리 구현하고
  설정·CLI·예제·문서와 통합했다. 과거 실행기/모델 수치·가중치·미커밋 작업은 보존했다.
- 독립 검토에서 cleanup 보고 누락·교차 trace 분모·SIGTERM 정리·다른 이벤트루프 종료,
  실제 방 이름 재사용·동일rqid 변경/취소·팀거절 자동대체·종결쓰기 오류 분모를 보완했다.
- 최종 관련153 CPU검사, 11조건 모의trace, CLI 로컬4경기, 별도 출력실패/방재사용3경기,
  3모델 대표6입력씩CPU토큰화 및 이동후 오프라인 원문/복사/다운로드 검증을 완료했다.
  모델 API/GPU 추론0이며 실제 모델 성능·연결은 미평가다.

## 결과·증거

[최종 보고](../../../exec-plans/evidence/ep145/report.md) · [종결 검증](../../../exec-plans/evidence/ep145/completion.json) ·
[사용법](../../../../integration/jev_planner/README.md) ·
[11조건 모의 뷰어](../../../../exports/battle_viewers/ep145-planner-demo/index.html) ·
[로컬4경기 모의 뷰어](../../../../exports/battle_viewers/ep145-planner-local/index.html).
이번 환경 구축의 완료이며 후속 유료 API·GPU·배틀 실험을 실행한 상태가 아니다.
