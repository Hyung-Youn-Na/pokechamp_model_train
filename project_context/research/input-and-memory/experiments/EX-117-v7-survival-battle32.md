# EX-117 — 생존·교체 비용 v7 GPT-6 Luna 32경기

- 상태: Stopped
- 생성일: 2026-10-21
- 책임자: Codex
- 승인: 사용자 개정 입력으로 GPT-6 Luna Decisions 32경기 시작 지시 / D-182 / EP-206
- 연구선·checkout: research/model-training /workspace

## 질문·처치·통제

D-181/EP-205 생존 판단·교체 기회비용 지시문을 사용한 탐색 평가다.
EX-115의32대진·16진영교환쌍·팀·seed·순서·Abyssal·Gen9 OU를 재사용한다.
모델 gpt-6-luna, OpenAI Decisions API; 경기/HTTP 동시성1·타이머off·단일후보 자동선택이다.
입력 jev-choice-v7 / candidate-action-v1, 관측·계산·공개정보·후보/명령·피해/스피드 방법은 유지한다.
변경 지시문 SHA-256: 6a4bd45bb2e4d89a58a8daff959b3e29fb2691fffd6b575b9d00397ae01f1e64.
기준 지시문은 EX115의 ca467ea2a507dfbff21df2fbcc93f262d732816b83d0b92c43f06a7a23a042b4.
실행기/뷰어의 실험 ID 연결은 별도 출처 변경이며 입력 처치를 추가하지 않는다.

## 통신·응답·결함·한도

EX115와 동일하게 연결/timeout·408/429/5xx는 동일 결정·동일 본문으로 통신 재시도한다.
요청60초·2/5/10/20/30/60초 뒤60초 반복 및 더 긴 Retry-After를 따른다.
거부/누락/후보밖/파싱불가 응답만 최초 포함 최대3회, 통신 시도는 별도 무제한이다.
첫 합법 선택을 사용하고 낮은 확률/전략적 품질로 재질의하지 않는다. 소진은 경기실패로 격리한다.
본32슬롯 외 추가 유료 사전호출·기준선·보충·재수집0, fallback0·자동재개0이다.
전체시간/요청수/턴 상한은 EX115와 같이 없음. 최초 시작 시각·누적 사용량을 보존한다.
RD11.1/C018 적용: 기술결함은 영향 의존범위 중지·원자료 보존·독립검증한다.
입력/수집 무결성·인증/요청오류/모델불일치 등 공유 기술오류에는 실행기가 신규 경기 제출을 멈춘다.
이번 실행기는 부분 재개·재수집을 지원하지 않으며 실패한 시도를 보충하지 않는다.
RD11.2/C046에 따라 합법 판단 오류는 전체중단 사유가 아니다. 오류는 evidence와 원장에 기록한다.
과거 중단/무효/봉인·EX115 처치와 결과는 보존한다.

## 진입 검증·동결

EX115 저장1021입력을 같은 현재 변환 경로로 복원/재구성하여 instructions 외 동일함을 확인한다.
실제997논리 API 요청의 input/choices/기타 필드는 그대로인지 대조하고 문자/바이트 증가를 기록한다.
EP205 대표3종 검증과 관련 CPU/UI 검사, API0 모의2경기의 재생성/전송/최종감사 및
뷰어 원문 전수대조·이동후 오프라인을 확인한다. EX115의 총바이트 감소 gate는 이번 범위에 적용하지 않는다.
모의 이후 같은 source/data의 지시문·소스·자료identity·일정·protocol을 본수집 전에 동결한다.
새 실행은 동결 identity를 매 경기 확인한다. 검사 통과가 효능 근거는 아니다.

## 평가·완료

예정32/시도/유효/실패/무효/미실행, 완료쌍/16, 승무패 및 (승+0.5×무)/유효경기를 보고한다.
주비교는 EX115의 공통 유효슬롯과 완료쌍 점수 차이다. 누락을 승패로 치환하지 않는다.
모든 확인 HTTP usage·미확정 usage·지연·통신/응답 재시도를 보고한다.
기본 IO 설명 정확성은 RD8.1에 따라 미평가다. 성능 방향을 사전 전제하지 않는다.
개발대진·과거시점·모델변동·선택 후 경기전개의 교란이 있어 단독 인과효과/일반 승률 개선을 주장하지 않는다.
유효32경기/16쌍·경기별 및 최종감사·보고/비교·viewer·봉인/소유자원반환이 완료 기준이다.
부족한 분모·검증 실패는 미완료로 보존한다. 시작 요청은 완료 결과와 구분해 보고한다.

## 환경·출력·뷰어

기준/실제 branch research/model-training, 시작 commit feda62f733c1b470364868262c789ec857ef67f5.
다수 미커밋 소스는 source/ 및 environment.json에 보존한다. 기존 pokechamp/.venv/bin/python을 쓴다.
GPU0, 소유 Showdown8109·CPU 및 외부API를 사용하며 병행 EP203 학습환경/자원은 건드리지 않는다.
출력 /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-117.
실행 scripts/candidate-action-battle --experiment EX-117: mock/prepare/execute/status/export.
동일 승인으로 collect가 수집→보고·비교→뷰어/검증→봉인/완료receipt를 연결한다.
C047/UI battle-viewer-ui-v1, renderer candidate-action-researcher-v2 (실험 ID 표시 연결).
기본5탭 뒤 재구성 전 입력 → 후보별 적용 결과 → 선택·전송. 기존 source의 판본/정확한 파일은
manifest 및 내보내기 provenance에 보존한다. exports/battle_viewers/ex117에 별도 내보낸다.
지원 근거 EP202의 UI/합성 검사와 새 EP206의 모의 검증. 이전 내보내기는 불변이다.
뷰어 변경일지는 shared/viewers/CHANGELOG.md에 등록한다. 브라우저는 기존 /tmp/ep037/tools 환경을 쓴다.

## 결과

2026-10-21 17:33 KST 본수집을 시작했다. 준비1021입력/997요청 전수동치·46검사·모의2경기/뷰어를 통과하고
source/data/일정/protocol을 동결했다. 첫 실제 요청의 gpt-6-luna 모델과 개정 instructions 전달을 확인했다.
현재 진행은 collection/progress.json과 collection/ledger.json, 종료 결과는 evidence/completion.json 및 report.md에 기록한다.
위 기록은 시작 당시 확인이다. 최종 판정과 분모는 아래 종결 결과를 따른다.
[진행 원장](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-117/collection/ledger.json) ·
[시작 기록](../../../exec-plans/evidence/ep206/launch.json).

## 종결 결과

32시도·유효30/32·완료14/16쌍,12승0무18패(40.0%). 실패2·무효0·미실행0.
슬롯4/11의 HTTP200 refusal가 각3회 반복되어 응답복구를 소진했다. 실패는 패배에 포함하지 않는다.
EX115 공통30슬롯은60.0%→40.0%(-20.0%p), 공통14쌍 평균차이-17.86%p다.
HTTP1187·논리1183·자동26·총1209입력, 통신재시도0·응답재질의4·복구성공0.
확인입력17,946,111토큰·미확정0. 수집약36.9분.
경기별/최종감사·1209결정 원문내보내기·이동후6종/3폭/실제리플레이·봉인/소유8109 반환 완료.
유효32/16쌍 기준 미달로 Stopped이며 보충·재수집0이다. 과거 비교로 지시문 단독 효과를 확정하지 않는다.
[종결 확인](../../../exec-plans/evidence/ep206/report.md) ·
[동결 보고](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-117/evidence/report.md) ·
[뷰어](../../../../exports/battle_viewers/ex117/index.html).
