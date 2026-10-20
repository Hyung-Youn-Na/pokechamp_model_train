# EP-148 — GLM planner–JEV 첫 실제 샘플

- 상태: Completed
- 완료일: 2026-10-15
- 생성일: 2026-10-15
- 책임자: Codex
- 승인: 현재 사용자 EX-088 첫 대진 샘플 실행 지시 / D-142
- 연구선·checkout: research/model-training, /workspace
- 시작 commit: a4659bf298c7935714f9fbd25246db2d831c5926; 기존 미커밋 변경 보존
- 실행 조건 원문: [EX-092](../../experiments/EX-092-planner-first-battle-sample.md)
- 증거: project_context/exec-plans/evidence/ep148/

## 목표·범위

EX-088 첫 대진의 현재 planner–JEV 실제1경기와 요청/계획/선택/사용량·결과 뷰어를 제공한다.
INDEX/CHARTER·매뉴얼·STATUS/색인·RD/C-070/071/072·기존EX-088/089와 active EP-134/140 및
과거 JEV/Z.ai 중단계획의 보존 경계를 확인했다. 새 ID와 출력에서만 실행한다.
독립 agent는 live lifecycle을 읽기/CPU로 검토하고 주 에이전트가 등록·동결·실행·감사/종결을 담당한다.

## 완료 기준

- [x] 새EX/ADR/EP 등록·대진/자원/한도 준비
- [x] 실제1경기 실행·계획/선택/원문 및 실패 포함 분모 보존
- [x] 실행·사용량·후보/명령/원문 연결 감사
- [x] 오프라인 뷰어·봉인·소유 GPU/프로세스/잠금/포트 반환
- [x] EX·상태·보고·뷰어 링크 제공

## 검증·중단

EX-092의 사전조건/중단·복구/분모를 따른다. 기존 CPU/모의/모델 검증의 재사용 범위와
첫 실제 연결의 미검증 범위를 구분한다. 수집 중 source/prompt 변경·모델 대체·재경기0이다.
실제 실행 이전 도구 결함은 증거 보존·교정/독립검증 후 같은 범위에서 준비할 수 있지만
상한/최초시계를 초기화하거나 이미 시도한 경기를 다시 수행하지 않는다.

## 진행

- 2026-10-15 — EX-088 첫 일정·팀/seed와 현재9B/GLM 설정 확인. GPU0–3 유휴·포트/자격증명
  확인, 실제 추론/API/새배틀 전 등록. 상세 실행 근거는 EX-092에 둔다.
- 새EX-092 준비본을 고정했다. 독립읽기/CPU검토에서 입력자료587파일identity·9B17파일receipt와
  lifecycle 경계를 확인했고, 합산95.315GiB/100GiB를 확인하여 실제 실행에 진입한다.
- 55턴 승리로1경기 정상종료, 실제GLM30/JEV66·자동2·68명령을 수집했다. 독립 기술감사와
  원문export/대표 오프라인 화면·복사/다운로드, 봉인·소유자원 반환을 완료했다.
  브라우저검사의 고정파일명 가정만 실제목록 링크로 교정했으며 원자료/수집source는 불변이다.

## 결과·증거

[최종 보고](../evidence/ep148/report.md) · [완료](../evidence/ep148/completion.json) ·
[감사](../evidence/ep148/audit.json) · [실제 경기 뷰어](../../../exports/battle_viewers/ex092/index.html).
추가 경기/재개는 없고1경기 샘플의 해석 한계를 유지한다.
