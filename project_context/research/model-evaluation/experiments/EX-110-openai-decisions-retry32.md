# EX-110 — OpenAI Decisions 통신 재시도 새32경기

- 상태: Completed
- 완료일: 2026-10-20
- 생성일: 2026-10-20
- 승인: 사용자 연결실패/시간초과로 제한하지 않는 재설정·재실험 지시 / D-165 / EP-180
- branch/checkout: research/model-training / /workspace; 시작commit a4659bf298c7935714f9fbd25246db2d831c5926

## 질문·고정 조건

통신 실패에 대한 지속 재시도 하에서 gpt-6-luna의 v6 상세 고정 대진32경기를 완수하고
승무패·완료율·API 시도/사용량/지연을 탐색한다. EX109의 결과를 새분모에 계승하지 않는다.
[EX-109](EX-109-openai-decisions-v6-battle32.md)의 모델·v6 상세 state/지시문·손실 없는 choice 변환,
EX089 고유32슬롯·16진영교환쌍·양측seed/대진/순서·Abyssal·Gen9 OU·테라 허용·timer off와
자기벤치 상세·피해/스피드 포함·planner/names-v1/RuleQA 교정off를 동일하게 채택한다.
단일 후보 무호출·합법원choice 실행·보조확률 진단은 유지한다. 병렬경기/동시HTTP는1이다.

## 변경한 통신·시간 정책

- 연결/읽기/쓰기/풀 통신 오류 및 HTTP408/429/5xx: 같은 논리 decision과 동일 HTTP본문으로 성공까지 재시도.
- 개별요청 timeout60초, 실패 후2/5/10/20/30/60초와 이후60초의 backoff; Retry-After가 더 길면 존중.
- 재시도횟수·총HTTP요청·전체/단계/경기 경과시간·300턴/600결정 상한 없음. 정상 게임종료를 기다린다.
- HTTP400/401/403/404 등 비일시적요청/권한 문제, 입력/관측/전송/수집/무결성 결함은 기술 오류다.
- 사용자 명시중지와 프로세스 취소는 재시도 중에도 반영한다. HTTP 미응답은 실제 공급자 처리/비용 미확정.
- API의 idempotency/중복추론 억제 보장을 가정하지 않는다. 성공 반환값만 실행하며 모든시도/원문/usage를 보존한다.

이 정책은 EX109의 실패/원시계를 지우는 변경이 아니다. EX109 총327API시도와 확인4,260,141입력토큰·
미응답1을 이전사용량으로 별도 연결하며 EX110의 새32경기 성적과 합치지 않는다.

## 절차·검증·분모

1. 새 retry wrapper에4회 이상 연속실패→성공, 동일본문/ID,backoff,취소,권한거부 즉시구분,
   무경과시간/요청상한·확률불일치 원choice·사용량미확정을 모의로 검증한다.
2. 기존 EX109의 공식cutoff/v6역변환·3종API연결·모의2경기/175입력 검증은 입력/행동 경로에만 재사용한다.
   새모델 호출 gate를 추가하지 않으며 retry/원장/감사와 뷰어의 변경 부분은 새로 검증한다.
3. 새source·protocol·동일대진 동결 후32슬롯을 순차 수행한다. 경기별1회 입력/계산/원HTTP와
   선택/실제전송/종료 감사, 종료 시 분모/사용량 산술을 확인한다.
4. 신규 유효32/16쌍·전수 원문/뷰어·봉인·소유Showdown/Abyssal/포트 반환·보고가 완료 기준이다.

C-046의 실행 불가능한 모델 선택은 경기별실패이며 전략오답/보조확률 이상은 그대로 측정한다.
RD11.1/C-018의 실제수집 도구결함은 의존 중지·원자료 기반 교정/독립검증을 요구한다.
새프로필의 정상통신 재시도는 별도 재승인 없이 수행한다. 입력오염 경기의 재수집은0이며
관측/평가 결함과 API통신을 혼동하지 않는다. 설명정확성은 기본 미평가다.

정상 승1/무0.5/패0, 유효수/전체32 완료율·완료쌍·실패/무효/미실행·논리요청/HTTP시도·
확인usage/미확정실패시도·재시도 대기/실제latency를 구분한다. 고정 대진의 탐색 결과이며
모델크기만의 효과·일반 승률 우위를 주장하지 않는다.

## 환경·출력

scripts/openai-decisions-retry-battle; actor pokechamp/.venv/bin/python; GPU0, 기존관측/계산환경 재사용.
run /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-110
viewer /workspace/exports/battle_viewers/ex110/index.html. 원EX109/뷰어/봉인/중단은 보존한다.
root .env는 현재키를 읽되 소스/원장/자식환경에 값을 넣지 않는다.

## 결과

신규32경기/32시도·유효32·완료16쌍, **16승0무16패·승률/점수50%**다.
실패0·무효0·미실행0, 경기별32회·최종 기술 감사와976결정 원문 대조를 통과했다.
본API952요청/952응답·단일후보 자동24·전송976이며 실제통신오류/재시도/usage미확정0이다.
확인 입력12,453,182토큰·출력0, HTTP 중앙0.305초·p95 0.668초(nearest-rank), 수집/감사 약32.65분이다.

폴더 이동/오프라인4실제대표와 합성재시도1의 표시·탐색·다운로드 검증을 마쳤다.
원자료/뷰어 봉인·소유Showdown/Abyssal 종료·8109반환을 확인했다. 추가 경기/API호출은 없다.
이전EX109 사용량/실패는 새32경기 성적에 포함하지 않고 별도 누적비용으로 보존한다.

[최종 보고서](../../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-110/evidence/report.md) · [지표](../../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-110/evidence/metrics.json) ·
[종결](../../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-110/evidence/completion.json) · [32경기 뷰어](../../../../exports/battle_viewers/ex110/index.html).

