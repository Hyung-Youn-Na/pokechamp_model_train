# EP-053 — 교정 B2 개선 선봉 비교

- 상태: Blocked
- 생성일: 2026-09-16
- 책임자: Codex
- 승인: 현재 사용자 계획 구현 지시, [D-064](../../decisions/D-064-corrected-lead.md)
- 조건 원문: [EX-043](../../experiments/EX-043-corrected-lead.md)

## 목표·범위

EX-043 등록/분산 실행/최신 선봉/전송 및 종료 경기 입력 감사 연결을 구현하고 최종 검증·봉인·수집·전수 감사·보고·보존·정리한다. integration/pokechamp와 project_context·운영 문서가 범위다. INDEX/CHARTER·RD·C-018/033–040·겹치는 EP-030/032/035/041/044/045/048을 확인했다. 과거 중단·봉인·원자료를 보존한다.

## 완료 기준

- [x] EX-043 준비/등록/실행/감사/보고와 과거 호환 구현
- [x] EX 사전 검증 전부 통과·최종 source/설정/일정/감사기 봉인
- [ ] 첫4 gate·후속28 수집, 유효32·완료16쌍
- [x] 실패 포함 전수 연결·viewer·보고·manifest·보존·소유 자원 정리

## 검증·중단

EX-043 사전 검증·중단/복구0·최초 시계·완료 판단을 따른다. INDEX workflow와 RD11.1/C-018 적용. 구현 전 등록하며 source 변경 후 이전 검사 결과를 새 source의 검증으로 재사용하지 않는다. 미달 시 비교 미완료 유지.

## 진행

- 2026-09-16: 관련 원문 확인, 구현 전 등록. 유료 호출0.

- EX-043 별도 namespace·provider 배정·최신 선봉/전송·binding·CLI 연결 및 입력 감사 장벽 구현. 변경 경로27검사 통과(최초 fixture의 immutable seal 덮어쓰기와 과거 completion fixture 호환 오류는 사전 단계에서 교정).
- 사전 로컬 v1 첫4경기 입력 재생/공개 사실 차이0. 실패 경기의 snapshot 부재/입력 자격 집계 및 감사 시간 제한 보강을 위해 후속 제출을 로컬 halt로 차단했다. 실행 자원 정리 후 보고 생성만 중단했으며 원자료/8actor/감사/cleanup 보존. 유료 호출0, 최종 fake32 근거로 사용하지 않는다.
- 전체 integration 검사 진행. 최종 소스에서는 온라인 감사가 정리 기한을 넘지 않도록 독립 프로세스 그룹의 시간 제한과 종료 후 오프라인 감사 연결을 검증한다.

- 전체 integration1,276통과·전후 source 일치. 온라인 감사 기한/프로세스 종료·receipt 경로 보강 후 영향93검사 통과. 최종264source 봉인으로 local-final fake32 진행 중; 첫4 gate 오류0. EX-039–042 과거 봉인 검증 통과, 과거32,557파일 보존 기준 확보.

- 최종 local-final32유효/16쌍·별도4유효/2쌍·입력/기술/독립 wire 검사 통과. [구현 보고](../evidence/ep053/implementation-report.md)·[실행 봉인](../evidence/ep053/execution-freeze.json)·[진입 receipt](../evidence/ep053/entry-verification.json). EX-043 실제 첫4 수집 시작, 추가 probe/smoke0·수집 source 변경0.

- 최종: 실제 launcher cwd 설정 오류를 발견하여 첫4 gate 전 전체 중단. 시도4·실패4·미실행28·유효0·완료쌍0으로 비교 미완료. 동일 소스/기준의 올바른 cwd 사후 감사로 입력 차이0을 확인하고 원본을 보존한 별도 정정 보고 생성. 이후 감사 subprocess cwd 고정·영향39검사 통과. 재개/재수집0. 실패 포함 viewer·원장·응답·전수 감사·manifest·과거 보존·소유 자원 정리 완료. [최종 보고](../evidence/ep053/final-report.md).
