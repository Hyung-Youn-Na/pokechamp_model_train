# EP-152 — GLM JSON 구문 재시도·샘플1경기

- 상태: Completed
- 완료일: 2026-10-15
- 생성일: 2026-10-15
- 책임자: Codex
- 승인: 현재 사용자 JSON 오류 최대5회 재시도 설정·다시 실행 지시 / D-146
- 조건: [EX-094](../../experiments/EX-094-planner-json-retry-sample.md)
- 연구선/실제 branch: research/model-training, checkout /workspace, 시작 commit a4659bf
- 기존 미커밋 변경 보존. actor pokechamp/.venv/bin/python, model .pokechamp-data/jev27b-runtime/.venv/bin/python
- 새 run: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-094
- 증거: project_context/exec-plans/evidence/ep152, 뷰어 exports/battle_viewers/ex094
- 읽기전용 참조: EX-093 보고/봉인/실패 응답, EX-092/088 대진, 모델 영수증

## 목표·범위

Planner 설정/클라이언트·집계/뷰어에 JSON 구문 재시도 원문·물리시도·usage를 연결하고
합성검증 후 변경 수행 지시문의 새1경기·감사·뷰어·반환을 수행한다.
INDEX/CHARTER·매뉴얼·STATUS/색인·RD/C-070/073·겹치는 active EP-151/134/140과
JEV 중단계획의 기존 보존 경계를 유지한다. EX-093을 재개하거나 봉인을 고치지 않는다.

## 완료 기준

- [x] 재시도 계약/설정·동결/기록·통합뷰어 연결
- [x] 최초+5상한·실제 EX-093 실패 응답 회복·비대상 오류·혼합HTTP/예산/취소·과거설정 CPU검증
- [x] 새EX/일정/필수자산/자원·source 동결 후 실제 정상1경기
- [x] 실패 포함 원문/usage 감사·대표 이동후 오프라인·봉인·소유자원 반환
- [x] 보고·상태·색인 동기화

## 검증·중단

EX-094의 예산/복구/실패 격리를 따른다. 실제 수집 중 source/prompt 변경0, 새 GPU probe/재경기0.
설명 정확성은 RD8.1/C-032 기본 제외이며 합법 선택을 임의 수정하지 않는다.
도구 결함은 RD11.1/C-018에 따라 증거 보존·영향확인·독립검증하고 한도/시계를 초기화하지 않는다.

## 진행

- 2026-10-15 — 승인 등록, 구현 전.

- 2026-10-15 — CPU178통과/브라우저환경부재2skip·별도브라우저2통과, 실제 EX-093 구문오류를 무호출 재생해 회복을 확인했다. 진입검사/99.298GiB·기존프롬프트 동일·json_retries=5 확인 뒤 새source를 동결한다.


## 결과·증거

최초+추가5회 JSON 구문 재시도 설정·기록/집계/표시와 CPU178·별도브라우저2검사를 완료했다.
EX-094는64턴 패배로 정상1경기 종료했다. 실제 JSON구문재시도0이며74결정/69JEV추론·자동5,
GLM28생성/HTTP를 보존했다. 전수감사/원문 대조·오프라인 통합뷰어·봉인·자원 반환을 완료했다.
GPU0–3 실제 적재/메모리 원장과 SQLite69추론 완료를 확인했다. EX-093의 Blocked는 보존한다.
[완료 보고](../evidence/ep152/report.md) · [감사](../evidence/ep152/audit.json) ·
[뷰어](../../../exports/battle_viewers/ex094/index.html).
