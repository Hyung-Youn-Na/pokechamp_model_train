# EP-151 — 변경 수행 프롬프트 샘플1경기

- 상태: Blocked
- 실패 종결일: 2026-10-15
- 생성일: 2026-10-15
- 책임자: Codex
- 승인: 현재 사용자 바뀐 프롬프트의 이전과 같은1경기 실행 지시 / D-145
- 조건 원문: [EX-093](../experiments/EX-093-planner-goal-completion-sample.md)
- 연구선/branch·checkout: `research/model-training`, `/workspace`; 시작 commit `a4659bf`
- 기존 미커밋 변경 보존. actor `pokechamp/.venv/bin/python`, model `.pokechamp-data/jev27b-runtime/.venv/bin/python`
- 새 run: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-093`
- 새 증거: `project_context/exec-plans/evidence/ep151`; 새 뷰어 `exports/battle_viewers/ex093`
- 참조: EX-092 보고/봉인 manifest·EX-088 첫슬롯, 기존 원문은 읽기 전용

## 목표·범위

D-143 수행 지시문의 실제1경기·기술감사·통합뷰어·봉인·정리까지 수행한다.
INDEX/CHARTER·매뉴얼·STATUS·RD·C-070/073·겹치는 active EP-134/140과 과거
JEV 중단 EP-062/064/075/077/080의 보존 경계를 확인한다. 기존 실행을 재개하지 않는다.

## 완료 기준

- [x] 새EX/ADR/EP·일정/프롬프트 차이·필수자산/자원 확인·source 동결
- [x] 실제1경기 실행·원문/사용량/실패 포함 분모 보존
- [x] 저장 원문 기술감사·EX-092와 탐색적 사례 비교
- [x] 통합뷰어·이동후 오프라인 검사·run/뷰어 봉인·소유자원 반환
- [x] 보고·EX/상태/색인 동기화

## 검증·중단

EX-093의 한도·사전조건·중단/복구를 따른다. 설명 정확성은 RD8.1/C-032의 기본 제외다.
모델/formatter·수집기의 이전 검증을 source 차이에 맞춰 재사용한다. 수행 지시문 변경은
EP-149에서 CPU 검증됐고 통합뷰어는 EP-150에서 검증됐다. 새 유료 probe/재경기0이다.
도구 결함은 RD11.1/C-018로 보존/영향확인·독립검증하며 실제 수집source를 중간에 바꾸지 않는다.

## 진행

- 2026-10-15 — 승인 범위 등록. 준비 중이며 모델/실제배틀 실행 전.

- 2026-10-15 — 진입검사 통과·source/prompt 동결 후 live 실행 시작. 합산99.255GiB/100GiB.
  중복 임시export3개만 제거했으며 정식 원자료/뷰어와 최종 임시 검증본은 보존했다.
  전체 참조·임시자료를 포함한 추가 resource monitor로 기존 한도를 감시한다.


## 실패 종결·미충족 기준

- [ ] EX-093의 정상1경기 완료 기준:14턴 GLM JSON 구문 오류로 정상0/1이다.

재질의/재경기0이며 실패 분모를 보존했다.17관측/16전송·7GLM호출의 기술감사와 부분
통합뷰어·원문전수 대조·대표오프라인·봉인·GPU/프로세스/잠금/포트 반환을 완료했다.
정상완료 목표 미달로 Blocked를 active/에 보존하며 자동재개하지 않는다.
[실패 보고](../../../exec-plans/evidence/ep151/report.md) · [감사](../../../exec-plans/evidence/ep151/audit.json) ·
[뷰어](../../../../exports/battle_viewers/ex093/index.html).
