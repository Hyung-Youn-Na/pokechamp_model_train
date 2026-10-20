# EX-112 — 후보별 현재 대면 요약 gpt-6-luna 32경기

- 상태: Stopped
- 생성일: 2026-10-20
- 승인: 현재 사용자 제공 계획의 구현·검증·실행 요청 / D-168 / EP-183
- 연구선·checkout: research/model-training /workspace
- 시작 commit: a4659bf298c7935714f9fbd25246db2d831c5926 (기존 미커밋 변경 보존; freeze environment.json에 실제 상태 기록)

## 질문·처치·조건

후보별 공개 규칙 적용결과가 차단 후보 선택 빈도 및 배틀 성적과 어떻게 연관되는지 탐색한다.
EX110과 같은 gpt-6-luna, Abyssal, Gen9 OU, 32대진·16진영교환쌍·팀·게임/actor seed·순서를 사용한다.
기존 v6 상세 정보·지시문·후보 ID/순서/명령·피해/스피드·테라 허용·timer off·단일후보 자동선택을 유지한다.
기술후보의 current_matchup만 추가한다. 기반 schema jev-choice-v6와 추가 profile candidate-matchup-v1,
규칙·입력자료·실행/감사/평가 소스·대진을 manifest에서 별도 동결한다. 숨은 상대세트/미래는 입력에 넣지 않는다.
기준선은 [EX110](EX-110-openai-decisions-retry32.md)의 16승16패·50%이며 새 기준선·별도 유료 장면 비교는 없다.

## 평가 원문

주지표는 모델 판단에서 공개 차단(public_effects.result == blocked) 후보와 다른 선택지가
함께 있는 턴 중 차단 후보 선택 비율이다. 기준선 기대치는 15/71(약21.1%)이며 동일 동결 판정기로 재산출한다.
자동선택·모든 후보 차단·불확실 판정을 별도 집계한다. 교체 등 요약 비대상 후보도 다른 선택지에 포함한다.
타입배율0·계산피해0·반사·주요 상태이상 차단은 별도 지표이며 피해기의 부가 상태차단을 기술 전체 무효로 세지 않는다.
차단 후보를 선택한 모든 사례에서 리플레이를 연결하고 상대 유지/교체/테라/선행상태변화와 실제결과를 검토한다.
유효 승무패·점수율 (승+0.5×무)/유효경기·기존대비 차이·동일슬롯과16쌍 성적변화를 보고한다.
논리요청·물리HTTP시도·재시도·확인usage·미확정사용량·대기·지연을 구분한다.
동일한 판단기 코드로 두 원자료를 평가하며 과거 봉인·판정은 수정하지 않는다.

## 통신·오류·복구

EX110의 RetrySession을 재사용한다. 연결/timeout·HTTP408/429/5xx는 동일 논리ID/본문으로 계속 재시도한다.
개별요청60초, 2/5/10/20/30/60초 이후60초 반복, 더 긴 Retry-After 존중.
전체/경기 시간·요청/재시도/턴/결정 상한 없음, 동시 경기/HTTP1. 명시적 취소 지원.
인증·잘못된 요청·입력/관측/전송/수집 무결성 오류는 통신재시도로 숨기지 않는다.
나쁜 합법 선택은 그대로 실행하며 실행 불가능한 응답은 C046에 따라 해당경기 실패로 격리한다.
RD11.1/C018 도구결함은 의존단계 중지·원자료보존·교정/독립검증·영향보고를 따른다.
실행 중 동결 소스를 바꾸지 않는다. 자동 보충 경기 및 입력오염 경기 재수집0, 자동재개0.
모든 물리 시도를 기록하며 미응답의 공급자 실행·비용과 중복처리는 미확정이다.

## 절차·완료 기준

EP182의 변경 없는19검사·43엔진장면·976입력 보존 증거를 재사용한다.
새연결부의 실제 HTTP본문 전달/역복원·자기테라·선봉/강제교체·동일본문 재시도·프로필감사를 검사한다.
실제 API0 모의2경기로 수집·감사·내보내기를 통과한 후 새32경기를 순차 실행한다.
유효32경기·완료16쌍, 경기별 전수감사·비교보고·오프라인 뷰어·증거봉인·소유자원 반환이 완료 기준이다.
성적에 따른 조기종료·합격선 없음. 분모 부족은 실패/무효/미실행을 보존하고 미완료로 보고한다.

## 환경·출력·해석

기존 pokechamp/.venv/bin/python과 공식관측·계산기를 사용하며 GPU는 사용하지 않는다.
실행기 scripts/openai-decisions-matchup-battle: prepare/execute/status/export (mock은 무API 검증).
새출력 /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-112
뷰어 /workspace/exports/battle_viewers/ex112/index.html. 키는 기존 .env에서 읽고 증거/자식환경에는 넣지 않는다.
과거 기준선과의 탐색비교다. 실행시점·모델변동, 선택 후 달라지는 경기전개, 개발에 사용한 대진의 한계를
명시하며 인과효과·일반적 승률개선·단순 문자열 배치만의 효과로 확대하지 않는다.

## 결과·완료 분모 미달

32슬롯 시도·유효31·완료15쌍, 17승0무14패(유효 점수54.84%). 실패1·무효0·미실행0이다.
슬롯22의6턴 HTTP200 type=refusal로 실행 choice가 없어 해당 경기만 실패 처리했다. 이유는 미제공이며
미전송·무fallback·보충0이다. 이후 독립 경기까지 모두 시도했으나 사전32유효/16쌍 기준 미달이다.

동일 동결 판정기의 차단 선택은 EX110 15/71(21.13%)→EX112 0/29(0%). 기준선의 차단 선택15사례는
실제면역14·자기 Eject Button 교체로 미실행1이며 신규 차단 선택0이다. 전체유효 점수차 +4.84%p와
공통31슬롯 +3.23%p·공통15완료쌍 +3.33%p를 구분한다. 미완결쌍·실패 분모를 보존한다.

본API 논리884·HTTP886·503재시도2·대기4초, 확인 입력12,823,412토큰·출력0·미확정시도2.
913입력·912전송·32시도 전수/최종 감사, 오프라인 뷰어·사례검토·소유자원 반환을 완료했다.
추가 API/경기 없이 원자료·source·protocol·비교·뷰어를 봉인했다. 탐색 비교의 인과/일반화 제한은 유지한다.

[최종보고](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-112/evidence/report.md) · [비교](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-112/evidence/comparison/report.md) ·
[사례검토](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-112/evidence/case-review.md) · [종결](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-112/evidence/completion.json) ·
[뷰어](../../exports/battle_viewers/ex112/index.html).
