# EP-041 — B2 선봉 정책 대응 비교 실행

- 상태: Blocked — 사용자 지시로 실행·감시 종료, 비교 미완료
- 생성일: 2026-09-14
- 책임자: Codex
- 승인 근거: [사용자 지시 원문](../evidence/ep041/user-instruction.txt), [D-053](../../decisions/D-053-b2-lead-comparison.md)
- 관련: [EX-039](../../experiments/EX-039-b2-lead-proposal.md), C-018/029/031/032/033, D-052

## 목표·범위

EX-039의 동일 B2 source에서 선봉 정책만 비교하는 실제32경기/16대응쌍의 준비·실행·기술 검증·분석·보고·정리를 수행한다.
조건·일정·예산·gate·실패·분모의 원문은 EX-039다. 기존 Blocked9개와 과거 원자료는 보존한다.
parent coordinator·공통 요청 원장·평가·보고 연결을 구현할 수 있다. 배틀 prompt·압축·계산·전투 정책·모델·팀·upstream은 변경하지 않는다.
C-032에 따라 설명 오류 annotation은 수행하지 않고 설명 정확성·전략적 최적성은 미평가로 남긴다.

## 완료 기준

- [x] EP-040 최종 source 대비 차이 조사, 필요한 구현·로컬 회귀 및 source/config/prompt/model/팀/일정/정책 봉인
- [x] 금액 상한 제외 지시 및 승인 근거·실행 등록 영속 결합
- [ ] 첫 제출 슬롯의 전체 대응쌍2경기 기술 gate, 통과 후 동일 source/원장/최초 시계로30경기
- [ ] 유효32경기·완료16쌍 (미달 시 비교 미완료, 중단 처리 완료로 대체하지 않음)
- [ ] 사전 지표·모든 분모·미확정 사용량·기술 연결·viewer·manifest·검증 명령·해석 제한 보고
- [ ] 소유 자원·permit 정리, 보존 확인, EX/EP/색인/STATUS 동기화

## 검증

EP-040 report.md/completion-audit.json의 최종121검사·worker2경기 및 보존 source와 현재 파일을 비교한다.
변경한 coordinator gate/중복·중단, 원장 동시 예약/중복/미확정, 완전·불완전 대응쌍 집계를 독립 사례로 검사한다.
필요한 worker/B2 회귀 후 최종 source를 봉인하며 로컬 fake는 본 실험 분모에서 제외한다.

## 진행·차단

- 2026-09-14: INDEX/CHARTER/STATUS, 관련 active plan, RD/C/ADR 및 EP-040 최종 보고·감사·EX-039 확인. 구현 전 등록.
- 최초 금액 미기입 질문은 아래 사용자 후속 지시로 해결됐다. 현재 비용 관련 blocker는 없다.
- C-018/RD11.1 적용, 재수집0. 공유 결함은 영향범위(불명확 시 전체) 신규 제출 중단, 개별 선봉/provider/timeout/전송 실패는 경기 실패다. 수집 중 source/기준 교체 및 halt 후 재개0.

## 결과·증거

실제 Cloud 수집·감시 종료. 증거는 `../evidence/ep041/`에 등록한다. 실험 목표 완료 여부는 위 기준 전체로 판단한다.

- 2026-09-14: 사용자 후속 지시로 금액 상한 제외. 질문 해결, 요청·시간 상한 유지. EP-040 최종 parent source211개와 현재 파일 전부 동일함을 구현 전 확인했다. 첫 대응쌍은 b03-r3이다.

- 최종 변경 경로130검사, 공통 원장34회귀, Ruff/compileall 통과. 최초95검사 이후 범위를 EP-036 및 공통 원장까지 확인했다. 새 coordinator의 fake32 실행 중 첫 b03-r3 대응쌍 기술 gate 통과.

- 로컬 최종:32유효/16쌍,64 actor 선봉·최초 출전 일치,1761 fake요청/응답·미확정0·기술오류0·permit0. source214개 및 EX-039 조건/일정/승인/entry를 봉인하고 실제 Cloud 첫 대응쌍 실행에 진입한다. evidence/ep041/execution-freeze.json, entry-verification.json, source-preservation.json 참조.

- 2026-09-14 06:38:49.755503 UTC 최초 실제 Cloud 예약. 선봉2건의 엄격 JSON 응답과 네 actor /team 전송을 관측했고 첫 대응쌍의 유효 종료/gate를 기다린다. 이후 source 변경0.

- 실제 첫 b03-r3 대응쌍2경기 유효 종료·기술 gate 통과. 원장/trace/viewer·선봉 입력/전송/최초 출전·B2 검증·permit 반환을 확인했고 같은 source/원장/최초 시계로 나머지30 제출을 시작했다. 본32 분모에 첫2를 포함한다. 상세 first-pair-check.json 참조.

- 2026-09-14 07:21:47 UTC: b01-r1-s0의 p2 self_action 요청733이 provider ReadTimeout으로 응답 미수신, 상대 actor는 peer_failure로 정리됐다. 해당 경기 실패를 상대 승리로 세지 않고 유료 재시도0을 유지한다. 개별 provider 실패 격리 규칙에 따라 남은 예정 슬롯 수집은 계속한다. 이 실패로 유효32경기·완료16쌍 기준은 달성할 수 없으므로 최종 비교는 미완료로 보고하며, 수집·분석·정리 업무를 끝까지 수행한다.

- 2026-09-14 07:32:30 UTC: 사용자 후속 지시로 이미 제출된20경기(당시 유효10·timeout2·진행8)는 그대로 진행하고 미제출12경기는 보류한다. 실행기에는 선택적 hold API가 없어 다음 슬롯 b01-r3-s1의 신규 dispatch checksum 게시 직전에 임시 FIFO 대기를 설치했다. 로컬 봉인/대기/해제 검증 후 적용했으며 parent source/기존 원자료/모델/전투 처치 변경0, 기존 worker·permit thread는 계속 실행한다. 보류 슬롯은 worker 제출/유료 요청 전에 대기한다. 단순 dispatch JSON 생성만으로 시도 분모에 넣지 않으며 실제 worker 시작과 batch event를 대조해야 한다. 원문·설치 증거: operator-submission-hold.json. 후속 사용자 지시 전 보류를 해제하지 않는다. 최초 요청/수집/정리 시계는 유지한다.

- 보류 적용 후 실제 pool.submit 이전 대기 진입 및 신규 actor/요청0을 확인했다(operator-hold-verification.json). 기존20경기가 모두 종료됐고 실행기 기준 유효17·전투 ReadTimeout3·미실행 보류12다. 누적1478예약/1475응답·미수신3건(733,824,1342)은 모두 원장에 남아 있다. 경기/계산기 프로세스·8100–8107 포트·임시 worktree는 종료/정리됐고 coordinator는 의도적으로 보류 중이다. 최초 수집시한이 만료돼도 제출을 재개하지 않는 운영 deadline guard를 두었다. 아직 최종 broker 종료/plan 완료는 아니다.

- 부분 기술 감사의 최초 보고는 실행기 유효17 중3경기를 evaluator assertion으로 무효 표시했다. 원인은 diagnostics/team_preview.py:140이 decision_result.canonical_parsed_output(추출 결과)을 action_resolution.executed_action(실행 결과)과 동일시하여 기존 B2 first_legal_fallback을 거부한 평가 구현 오류다. 실제4사례는 추출null·합법 대체행동·실제 wire가 일치했다. 사전 EX-039의 합법 출력복구 허용 기준은 바꾸지 않고, 원본 source/보고서를 보존한 채 별도 offline evaluator로 해당3경기만 재검증한다. live source 변경/추가 Cloud/재수집0. output-recovery-evaluation-correction.json 및 held-report-correction.json에 정정 근거를 연결한다.

- 종료분 부분 분석 완료: 정정 후17유효/3실패/0무효/12미실행 보류,4완료쌍. 영향3경기 offline 재검증·6회귀·4실제복구 재현·40 actor 선봉/최초 출전·독립 승패/원장/token 대조 통과. [부분 보고서](../evidence/ep041/held-report.md), [부분 감사](../evidence/ep041/held-reconciliation-audit.json), [부분 manifest](../evidence/ep041/held-manifest.json)를 연결한다. 과거130778파일 보존·source214일치·upstream pins clean. 신규12제출/최종broker정리가 보류되어 전체 완료 기준은 미달이며 Active를 유지한다.

- 사용자 후속 지시로 감시2개와 보류 coordinator까지 종료했다. 미실행12경기는 시작하지 않았고 공급자 설정 변경은 수행하지 않았다. 최종 정리·원장 불변·기존 증거 보존은 [종료 기록](../evidence/ep041/closure/report.md)과 [종료 감사](../evidence/ep041/closure/shutdown-audit.json)로 연결한다. 실험 기준 미달이므로 Blocked로 보존하며 자동 재개하지 않는다. 원본 halt의 integrity 표기는 KeyboardInterrupt 공통 처리 결과이며 실제 중단 근거는 사용자의 전체 종료 지시다.
