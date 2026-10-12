# EP-045 — Z.ai 기본 동시성4·EX-041 재실험

- 상태: Blocked
- 생성일: 2026-09-15
- 승인: 현재 사용자 동시성 반감·Z.ai 기본4 요청 및 계획 구현 지시, [D-056](../../decisions/D-056-zai-concurrency4.md)
- 조건 원문: [EX-041](../../experiments/EX-041-b2-lead-zai4.md)

## 목표·범위

새 Z.ai 준비 기본값4·명시 설정 우선·과거 호환과 EX-041 독립 식별자/binding을 구현한다.
동일 B2 선봉 정책 새32경기/16쌍을 로컬 검증·봉인 후 실행·보고·보존·정리한다.
겹치는 EP-044/041/035/032/030 및 공통 INDEX/CHARTER·RD·C-018/029/033/034/035를 확인했다.
기존 중단 실험은 재개하지 않으며 B2 입력·처치·평가 기준은 유지한다.

## 완료 기준

- [x] 공급자 기본값·명시 설정·기존 봉인 및 EX-041 식별자/중단 회귀
- [x] 모의 Z.ai 동시성4 fake32 및 실제 로컬 대응2경기·wire/원장/viewer/permit 검증
- [x] 최종 source·조건·승인·검증 봉인 및 독립 실행 등록
- [x] 첫 b03-r3 대응2경기 기술 gate·후속30경기
- [ ] 유효32·완료16쌍 및 모든 기술 검증
- [x] 보고·viewer·manifest·과거 보존·소유 자원 정리·상태 동기화

## 중단·복구

EX-041 첫429/공유결함 신규 수집 중단·진행 응답 보존·정리, 자동 재개/유료재수집0.
RD11.1/C-018에 따라 결함 증거·영향을 보존하며 수집 중 source/기준 변경0이다.
미달 시 Blocked로 보존하고 중단 처리 완료를 비교 완료로 바꾸지 않는다.

## 진행

2026-09-15: 구현 전 등록. 증거는 ../evidence/ep045/에 보존한다.

- 2026-09-15: 첫 회귀176, 동시성 검사39, 최종 변경 경로67, 관련 회귀109 통과(중복 합산하지 않음). Ruff/compileall 통과.
- 실제 MockTransport 요청8개의 최대 HTTP 동시성4·permit4/반환0 및 coordinator 동시4 검증.
- 기존 EX-039/040 자료8024파일과 과거 source/정책 hash·일정 확인. 현재 source로 fake32 실행 중, 유료 호출0.

- 로컬 최종 fake32 유효32/16쌍/기술오류0, 별도 대응2경기 통과. 1965모의HTTP의 wire/원문/reasoning/token/원장 대조 통과.
- [구현·로컬 검증 보고](../evidence/ep045/implementation-report.md). 최종 source 봉인 후 실제 첫 대응쌍 진입 예정.

- source219개·설정·승인·검증 봉인 및 EX-041 전용 실행 등록 완료. 실제 첫 b03-r3 두 경기 수집에 진입한다. 수집 중 source 변경0·추가 probe/smoke0.

- 실제 첫 b03-r3 대응2경기 유효 종료·기술 gate 통과(errors=[]).152예약/152응답, 선봉·B2·원장·viewer·permit 반환 검증. 같은 source/원장/최초 시계로 나머지30경기를 동시성4로 수집 중이다.

- 실제 b01-r1-s0 p1의 요청412가 HTTP ReadTimeout(300255ms)으로 응답 미수신. 해당 경기 실패·상대 승리로 계산하지 않으며 재시도0이다. 개별 실패 규칙에 따라 예정 잔여 경기만 계속한다. 유효32 기준은 미달이므로 최종 비교는 미완료로 보고한다. [기록](../evidence/ep045/first-timeout.json).

- 실제 b03-r1-s0 p1의 요청974가 ConnectError(4011ms)로 응답 미수신. 개별 전송 실패로 보존하고 재시도 없이 잔여 예정 경기를 계속한다. 현재 실패2경기이며 공유 halt는 없다. [기록](../evidence/ep045/first-transport-error.json).

- b01-r3-s1 p2 요청1603·b02-r3-s1 p1 요청1604가 ConnectError(각4006/4005ms)로 추가 실패했다. 현재 실패4(timeout1·transport3)이며 공유 halt/429 없이 예정 잔여 경기만 계속한다. [추가 전송 오류 기록](../evidence/ep045/transport-errors-2-3.json).

- 최초 요청 후 약194분에 예정32경기 모두 제출. 정상 종료24·개별 실패4(timeout1·transport3)·진행4이며 첫429/공유 halt는 없다. 마지막4경기 종료 후 기술 감사·보고·정리를 수행한다.

- 약221분에 예정32경기 수집 종료: 정상28·개별 실패4(timeout1·transport3), 완료 대응쌍12. 예약2315·보존 응답2311, HTTP429/공유 halt0. cleanup 기록 생성·전체 viewer/기술 보고 생성 및 최종 감사 진행 중이다.

## 최종 결과·검증

Z.ai 새 준비 기본 동시성4 구현·로컬 검증 및 EX-041 예정32경기 수집·보고·보존·정리를 완료했다.
유효28·실패4(timeout1·transport3)·무효0·미실행0·완료 대응쌍12/16으로 유효32/16쌍 기준은 미달이다.
따라서 plan은 `Blocked`로 active에 보존하며, 보고·정리 완료를 비교 완료로 바꾸지 않는다.

- [최종 보고서](../evidence/ep045/final-report.md), [독립 감사](../evidence/ep045/final-audit.json), [manifest](../evidence/ep045/final-manifest.json).
- 기술 검증 오류0·미연결 요청0. 실제 최대 배틀/계정HTTP/모델HTTP 모두4, HTTP429/공유 halt0.
- source219개·기존 EX-039/040 자료8024개 파일 hash 일치.32경기 소유 Showdown/임시 worktree 제거, worker0·permit0·포트/소켓 정리·runtime 잠금 반환·upstream clean 확인.
- 수집 종료 후 추가 요청0, 유료 재시도/보충/재수집0. 최초 요청부터6시간 이내 최종 감사 완료.
