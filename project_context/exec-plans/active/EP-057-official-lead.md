# EP-057 — 공식 관측 B2 선봉 정책 본실험

- 상태: Blocked
- 생성일: 2026-09-17
- 책임자: Codex
- 승인: 현재 사용자 계획 구현 지시, [D-067](../../decisions/D-067-official-lead.md)
- 조건 원문: [EX-045](../../experiments/EX-045-official-lead.md), C-043/044, RD11.1/C-018

## 목표·범위

공식 관측을 공통 입력으로 선봉 정책32경기 비교의 구현·검증·봉인·실행·보고·정리를 수행한다.
integration/pokechamp 실행·감사·검사·운영 문서 및 project_context 기록이 범위다.
INDEX/CHARTER·RD/C 및 겹치는 EP-030/032/035/041/044/045/048/053/054를 확인했다.
과거 실행/원자료/중단/봉인과 upstream을 보존한다. 실험 조건·예산·gate·복구0은 EX-045 원문을 따른다.

## 완료 기준

- [x] 새 준비/등록/공급자별 공식 관측 설정/공식 cutoff 감사·실패 provenance 구현
- [x] 관련 및 전체 integration 회귀, EP-056 보존 자료 감사
- [x] 새 로컬4경기 통과·실행 봉인
- [ ] 본 첫4 gate·후속28경기, 유효32/완료16쌍
- [x] 실패 포함 감사/한국어 보고/viewer/봉인/과거 보존/자원 정리·상태 동기화

## 검증·중단

EX-045 검증 목록과 gate를 적용하며 검증 중 source를 고정한다. 무유료 로컬 실패는 보존하고 자동 재경기하지 않는다.
미달은 비교 미완료다. 중단 처리 완료로 plan을 Completed로 바꾸지 않는다. 유료 추가 probe0.

## 진행·증거

- 2026-09-17: 사용자 승인 범위·과거 보존 경계를 확인하고 구현 전 등록. 증거는 ../evidence/ep057/.

- EX-045 별도 분산 identity·공급자별 공식 backend/build·prompt 및 등록 binding·예약 검증·숫자 슬롯 보고 연결을 구현했다. official-cutoff-v1 감사는 행 경계 공식 재생/정규화/계산/원문/전송/원장/응답/슬롯과 실패 누락 사유를 기록한다. 과거 EX 분기는 유지한다.
- 초기 관련74검사 중72통과, 새 fixture의 공식 예약 identity 누락과 불완전 계산 fixture2건을 교정했다. 수정 뒤 신규14검사 통과. 추가4+4/등록 회귀를 포함한 최종 전체 integration 검사 진행 중이며 소스291개 고정.
- EP-056 로컬 과거 prompt를 현재 전송 identity로 읽은 최초 대조 실패를 보존했다(preserved-v1). 공식 관측의 최종 prompt 전환 전 자료이므로 과거 호출을 새 EX 입력으로 재명명하지 않는다. EP-056 보존100개 원문 경계의 재생 경로에 새 독립 원문 검사를 연결했고, 반사 기술 특성 보유자·[of] 아이템 보유자 oracle 보완 후 최종100/100·원문 검사 오류0(preserved-final/official-cutoff.json). 유료 호출/새 로컬 경기 아직0.

- 최종 전체 integration1,336개 통과(667.61초), Python compileall 통과. 검사 전후 source291개 일치. preserved-final100경계·원문 독립 검사 통과. 새 로컬4경기를 local-v1에서 시작했으며 실제 공급자 호출0, 경기당600초·각1시도·재경기0을 유지한다.

- local-v1:4경기 모두 정상 종료(403–441초),228관측/224모의 HTTP·입력/원문/계산/슬롯/원장 전수 감사·첫4 gate 통과, 기술오류0·permit0. source291개 그대로 유지. 새 cloud 설정의 자격정보를 비노출 검증하고 execution-freeze.json/entry-verification.json 및 독립 EX-045 등록 완료. 별도 유료 probe0. 본실험 첫4 수집에 진입하며 이후 source/prompt/기준을 바꾸지 않는다.

- 최초 유료 예약 2026-09-17 05:50:20.160108 UTC. 신규 수집 차단11:25:20 UTC, 정리 기한11:50:20 UTC이며 재시작/시계 초기화0. 공급자별 첫2경기 수집 중; operator 진행 계측은 evidence/ep057/progress/에 분리 보존한다.

- 본 첫4경기 모두 정상 종료·official-cutoff-v1 감사·첫4 기술 gate 통과. 최초 예약 약28분 뒤 후속28 수집 진입; 공급자별 새4경기 제출·배정 이전0·재시도0. 원본 gate receipt는 ex045-cloud/first-pair-check.json.

- 후속4+4에서 공식 queue 즉시 소비 가정 위반으로 전체 중단. 수집 source/기준 변경·재수집/재개0. 유효4/32·완료2/16쌍으로 비교 미완료이며 Blocked 유지. 실패 포함12시도 감사·한국어 보고·24actor viewer·정리·과거40,346파일/소스291개 보존을 완료했다. [최종 보고](../evidence/ep057/final-report.md)·[manifest](../evidence/ep057/final-manifest.json)에 원인·오프라인 재현·분모·검증을 연결한다.
