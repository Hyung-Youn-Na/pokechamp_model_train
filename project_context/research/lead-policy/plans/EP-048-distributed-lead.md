# EP-048 — Ollama Cloud·Z.ai 동시성4+4 선봉 비교

- 상태: Blocked
- 최종 갱신일: 2026-09-16
- 생성일: 2026-09-15
- 승인: 현재 사용자가 제공한 계획의 구현·검증·수집 지시. [D-059](../decisions/D-059-distributed-lead.md)
- 조건 원문: [EX-042](../experiments/EX-042-distributed-lead.md), [C-039](../CONTRACTS.md#c-039-distributed-lead)

## 목표·범위

공급자별 동시성4, 공유 원장·최초 시계·중단 상태의32경기/16쌍을 구현·검증·봉인·실행·보고한다.
EX-039/040/041 및 겹치는 EP-035/032/030의 중단과 봉인을 보존한다. INDEX/CHARTER·RD11.1·C-018/033–038 및 관련 원문을 확인했다.
변경 범위는 integration/pokechamp 실행기·검증·보고 및 project_context·운영 매뉴얼이다.

## 완료 기준

- [x] 공급자 배정·명시 전달·독립 permit·무제한 원장·시간/중단/중복 방지 및 과거 호환 회귀
- [x] 모의 HTTP fake32·공급자별 별도 로컬 대응2경기·입력/wire/원장/viewer/permit 검증
- [x] 최종 source·설정·배정·승인·검증 봉인·EX-042 등록
- [ ] 첫 네 경기 gate·후속28경기, 유효32·완료16쌍
- [x] 보고·viewer·manifest·기존 자료 보존·소유 자원 정리

## 중단·복구

EX-042 원문의 전체 중단·시간 한도·보충/재수집/재개0 및 RD11.1/C-018을 따른다.
수집 source/평가 기준은 고정한다. 추가 모델 호출 없는 사후 평가 교정은 원자료/별도 근거에 연결한다.
미달 시 비교 미완료로 보존하며 중단 처리 완료를 Completed로 바꾸지 않는다.

## 진행·증거

- 2026-09-15: 구현 전 등록. 현재 source 및 과거 실행 자료 hash를 evidence/ep048/before-hashes.json에 보존했다.

- 사전 로컬 v1은 첫4 gate와32경기 정상 종료·자원 정리를 확인했다. 최종 경계(첫 개별 gate 실패 즉시 전체 halt·완료 판정의 gate/정리 증거 확인)를 보강하기 위해 v1 보고 생성만 종료하고 원자료를 보존했다. 실제 모델 호출0이며 최종 source 검증은 별도 v2로 수행한다. 전체 회귀와 로컬 실행은 공통 runtime 잠금 때문에 순차 수행한다.
- EX-042 마지막 요청 보존은 공통 정리 기한까지의 잔여시간을 따르며, 소유 프로세스 종료·포트/소켓 정리를 위해 마지막60초를 확보한다. 신규 수집 cutoff20100/총21600초는 불변이다.

- 최종 source243개: 전체 회귀1111통과·로컬 서버 점유로 건너뛴 peer 취소 검사 별도1통과, EX-042 신규15검사 및 정적 검사/compileall 통과. 회귀 전후 source 일치를 확인했다. 근거: evidence/ep048/full-tests.log, peer-cancel-test.log, distributed-tests.log, static-check.log, source-candidate.json. 최종 로컬 v2 검증 중이며 외부 모델 호출0이다.

- 최종 [구현·검증 보고](../../../exec-plans/evidence/ep048/implementation-report.md) 완료. source243개·공급자/일정·승인·검증을 봉인하고 EX-042 전용 등록을 완료했다. [실행 봉인](../../../exec-plans/evidence/ep048/execution-freeze.json). 실제 첫 네 경기 수집에 진입하며 수집 중 source/평가 기준 변경·별도 probe/smoke0이다.
- 첫 Ollama b02-r2/Z.ai b03-r3 네 경기 모두 유효 종료하고 첫 gate를 통과했다. 원장327 HTTP 시도·326 응답 중 Z.ai 연결 오류1건은 같은 논리 요청의 재시도로 회복했으며 gate 오류0이다. `.pokechamp-data/b2-lead/ex042-cloud/first-pair-check.json`에 입력·wire·원장·viewer·permit 검증을 봉인했고 후속28경기를 공급자별4 상한으로 수집 중이다.

## 최종 상태 — 2026-09-16

실제32경기 시도·유효26·완료12쌍으로 비교 완료 기준에 미달했다. Ollama HTTP500 개별 실패3경기, Z.ai COURT_CHANGE 계산 미지원 원발생1경기 및 전체 중단 영향2경기다. 소유 자원 정리·보고·viewer·manifest·과거 자료/source 보존을 완료했으며 현재 실행·감시 중인 작업은 없다. 재개/재수집0이며 Blocked로 보존한다.

[최종 보고](../../../exec-plans/evidence/ep048/final-report.md)·[최종 감사 v2](../../../exec-plans/evidence/ep048/final-audit-v2.json)·[실패 영향](../../../exec-plans/evidence/ep048/failure-impact.json)·[manifest](../../../exec-plans/evidence/ep048/final-manifest.json)를 참조한다. 독립 감사 v1의 재시도 provenance 비교 오류는 원본을 보존하고 별도 v2에서 바로잡았다. 수집 source·입력·평가 기준 변경은 없다.
