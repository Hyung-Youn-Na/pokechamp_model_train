# EP-044 — Z.ai B2 선봉 정책32 재비교

- 상태: Blocked — 첫 HTTP429 중단·비교 미완료
- 생성일: 2026-09-15
- 승인: 현재 사용자가 제공한 EX-040 계획의 구현·검증·실행 지시, [D-055](../decisions/D-055-b2-lead-zai.md)
- 조건 원문: [EX-040](../experiments/EX-040-b2-lead-zai.md)

## 목표·범위

EX-039 종료 자료를 보존하고 새 Z.ai32경기/16대응쌍을 준비·실행·검증·보고한다.
실험 식별자별 protocol/binding, 공급자 검증, 평가기 교정, EX-040 첫429 영속 중단을 구현한다.
B2 입력·계산·프롬프트·합법 출력복구·선봉 정책과 기존 정책 hash·EX-039 binding은 유지한다.

## 완료 기준

- [x] EX-039 source/봉인 대조, 식별자·원장·공급자·평가기 및 관련 회귀
- [x] 모의 Z.ai HTTP, fake32, 모의 공급자 로컬 실제 actor/Showdown 대응2경기
- [x] 최종 source·팀·일정·설정·승인·검증 receipt 봉인
- [ ] 첫 b03-r3 대응쌍 기술 gate 및 후속30경기 — gate 통과, 후속8시도 후429 중단·22미실행
- [ ] 유효32·완료16쌍 — 유효2·완료1쌍으로 미충족
- [x] 부분 보고·양쪽 viewer·manifest·기존 자료 보존·소유 자원 정리

## 중단·복구

RD11.1/C-018 적용, 유료 재수집/재시도0. EX-040에만 첫429 전체 신규 경기/요청 중단을 적용한다.
공유 결함은 신규 수집 중단·진행 응답 보존·정리, 수집 중 source/평가기준 교체0, 자동 재개0.
평가 구현 교정은 온전한 양쪽 자료에 사전 기준대로 동일 적용한다. 상세 한도·분모는 EX-040 원문이다.

## 진행·증거

2026-09-15: INDEX/CHARTER/STATUS·관련 active EP-041/035/032/030·RD/C/ADR와 EX-039 확인 후 등록.
EX-039 추출/실행 행동 평가 오류의 보존 정정 구현을 확인했다. 추가 유료 호출0.
증거 위치: `../evidence/ep044/`.

- EX-040 전용 protocol/binding·최초 시계 hash·첫429 admission 차단 구현. 기존 정책 hash와 EX-039 전역 binding 유지.
- 관련 회귀274통과, 추가 model mismatch fixture 중복 keyword 오류를 교정한 최종 EX-04014검사 통과. Ruff/compileall 통과. 검사는 중복 합산하지 않는다.
- EX-039 source214·과거 보존6831파일 hash 일치. 모의 Z.ai 실제 worker fake32 첫 대응쌍 기술 gate 통과 후 잔여 로컬 경기 실행 중. 유료 호출0.

- fake32 최종 유효32/완료16쌍/기술오류0,1761모의 HTTP 및64actor 검사. 별도 모의 공급자 대응2경기/204HTTP·4actor 검사 통과. 독립 wire 대조·permit 반환·포트 종료 확인.

- source217개·팀·일정·공급자·검증·승인 봉인 및 EX-040 전용 등록 완료. 실제 Z.ai 첫 b03-r3 대응쌍 수집 시작. 수집 source 고정, 별도 유료 smoke/probe0. [봉인](../../../exec-plans/evidence/ep044/execution-freeze.json).

- 실제 첫 b03-r3 두 경기 유효 종료·기술 gate 통과.140예약/140응답, 선봉·B2·원장·viewer·permit 검증 완료. 같은 source/원장/최초 시계로 잔여30 수집 중. [gate](../../../../.pokechamp-data/b2-lead/ex040-zai/first-pair-check.json).

## 최종 결과·미완료 범위

첫 HTTP429는 `b02-r1-s1-a1/p2` self_action 요청149번에서 발생했다. 신규 경기/HTTP 중단 후
이미 진행한 응답을 보존하고 정리했다. 자동 재개·재시도·보충/재수집0이다.
예정32·시도10·유효2·실패/취소8·무효0·미실행22, 완료 대응쌍1/16이다.
양쪽 정책 각1승1패, 완료쌍 동일가중 LLM 점수0.5. 전체 비교는 미완료다.
149예약/148모델응답·HTTP4291건 사용량 미확정. 실제429는1건이며8경기의 rate_limit은 중단 전파 분류다.
429 이후 신규HTTP0, 추가 진입1건은 예약/HTTP 전에 거부됐다. 기술오류/미연결 요청0.
source217·EX-039 보존6831파일 hash 일치,10경기 server/임시 worktree 제거·worker0·permit0·소유 포트/소켓·runtime lock 정리를 확인했다.

[최종 보고서](../../../exec-plans/evidence/ep044/final-report.md) · [독립 감사](../../../exec-plans/evidence/ep044/final-audit.json) ·
[최종 manifest](../../../exec-plans/evidence/ep044/final-manifest.json). 보고·보존·중단 처리 완료를 비교 완료로 바꾸지 않고
active/의 Blocked로 보존한다. 후속 수집은 이 plan에서 자동 재개하지 않는다.
