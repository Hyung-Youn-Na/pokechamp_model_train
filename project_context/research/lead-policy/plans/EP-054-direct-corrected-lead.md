# EP-054 — 교정 선봉 직접 본실험

- 상태: Blocked
- 생성일: 2026-09-16
- 책임자: Codex
- 승인: [사용자 지시](../../../exec-plans/evidence/ep054/approval.md), [D-065](../decisions/D-065-direct-corrected-lead.md)
- 조건 원문: [EX-044](../experiments/EX-044-direct-corrected-lead.md)

## 목표·범위

EX-043 사후 cwd 수정본을 새 실행 identity에 연결하고 별도 사전 검사 없이 본32 수집·감사·보고·보존·정리를 수행한다. integration/pokechamp 실행/등록/보고 연결 및 project_context 기록이 범위다. INDEX/CHARTER·RD11.1·C-018/041 및 겹치는 EP-030/032/035/041/044/045/048/053을 확인했다. 기존 중단·원자료·봉인을 보존한다.

## 완료 기준

- [x] 새 identity·승인/생략 상태·source/config/schedule 봉인 및 본실험 진입
- [ ] 유효32·완료16대응쌍
- [x] 실패 포함 전수 감사·viewer·보고·manifest·보존·정리

## 검증·중단

별도 사전 테스트/점검은 skipped_by_user다. 통과로 기록하거나 기존 결과를 새 source 검증으로 재사용하지 않는다. 본실험 실행 중 감사와 수집 이후 보고·보존은 유지한다. EX-044 중단/기한/복구0과 RD11.1/C-018 적용. 미달은 Blocked로 보존한다.

## 진행

2026-09-16 새 실행 승인·구현 전 등록. 별도 모의 호출0.

- source264파일·새 승인/설정/32행 일정 봉인 후 올바른 cwd에서 본실험 진입. 별도 사전 테스트/점검0, receipt는 local_passed=false/wire_passed=false/preflight_status=skipped_by_user.

- 본실험 첫4경기 정상 종료·각 입력 감사 및 첫4 기술 gate 통과. 같은 원장/최초 시계/소스로 후속28 수집 중. 이전 cwd 오류 재발 없음.

- 본실험16시도 후 b04-r3-s0의 Magic Bounce 반사 Toxic을 상대 보유 기술에 포함하는 실제 입력 결함으로 전체 신규 수집 중단. 원인 경기 입력 불일치22결정, 이전 cwd 오류는 재발하지 않음. 실패/취소 포함16경기 입력 감사 및 자원 정리 완료. 새 예약/HTTP는 중단 이후0. 보고/manifest 마무리 중이며 재개/재수집0.

- 최종: 유효8·실패7·무효1·미실행16·완료2쌍. 본실험 목표 미달로 Blocked 유지. 1,076결정/1,060snapshot/1,059예약 전수 연결; 실제 입력 결함22결정1경기 무효. HTTP 전 취소1건은 원본을 보존한 별도 감사 정정으로 실패 유지. 1,058응답·timeout 미수신1건, 중단 후 호출0. 과거48,715파일/source264 보존·32actor viewer·자원 정리 완료. [최종 보고](../../../exec-plans/evidence/ep054/final-report.md). 입력 결함 미수정, 추가 수집0.
