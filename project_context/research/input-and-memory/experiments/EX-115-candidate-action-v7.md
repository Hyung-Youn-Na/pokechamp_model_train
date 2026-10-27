# EX-115 — 후보 중심 v7 GPT-6 Luna 32경기

- 상태: Completed
- 완료일: 2026-10-21
- 생성일: 2026-10-21
- 승인: 현재 사용자 제공 계획 구현·검증·실행 지시 / D-179 / EP-202
- 연구선·checkout: research/model-training /workspace

## 질문·처치·통제

jev-choice-v7 / candidate-action-v1과 실행 불가 응답 복구를 함께 적용하는 탐색 평가다.
EX-112의32대진·16진영교환쌍·팀·seed·순서·Abyssal·Gen9 OU를 재사용한다.
gpt-6-luna Decisions API, 경기/HTTP 동시성1, 타이머off, 단일후보 자동선택이다.
state는 공통 관측·팀·벤치/사용불가 기술·상대 공개 기술/받는 피해·전체 상성표·역할·스피드를 보존한다.
기술 후보에는 기술 설명/PP/대상/테라/상성/차단/상태효과/피해를 직접 넣고 상태 중복을 제거한다.
선택 분기 피해를 먼저, 나머지 모든 가정 분기를 별도 영역에 보존한다. 값·조건·미제공 이유는 유지한다.
일반·테라 기술 각각 설명을 포함하며 선봉/교체는 이름·슬롯과 공통 state를 사용한다.
영어 공통 지시문으로 반복 주의/범위를 통합하되 개별 예외/근거는 유지한다.
공개 정보 경계·후보ID/순서/명령·피해/스피드 방법 불변; 새 교체피해/전략추정0.
실제 요청은 state→input, 후보→choices[].description JSON 문자열이다.

## 통신·응답·결함

연결/timeout·408/429/5xx는 동일 결정·동일 본문 무제한 재시도, 요청60초,
2/5/10/20/30/60초 후60초 반복 및 더 긴 Retry-After 존중. 전체시간/요청/턴 상한 없음.
HTTP 성공으로 다음 응답 시도에 진입하면 통신 backoff 순서를 새로 시작한다.
거부·누락·후보밖·파싱불가 응답은 같은 입력 최대2회 추가(최초 포함3회); 통신 재시도와 별도다.
첫 실행가능 합법 선택을 사용한다. 낮은 confidence/확률 이상/전략적 품질로 재질의하지 않는다.
소진은 경기실패로 격리하고 나머지 독립슬롯 진행. 보충·fallback·프롬프트 수정 재질의0.
인증/요청오류/모델불일치/입력·수집 무결성 오류는 기술오류다. RD11.1/C018 적용,
영향 의존범위 중지·원자료/최초시계/사용량 보존·독립검증; 본경기 재수집0, 자동재개0.
모든 응답·HTTP시도/사용량을 보존하며 실패 응답의 확인 usage도 포함하고 미확정 별도 보고.

## 진입 검증과 동결

EX-112 저장913입력에서 관측·기술·모든 피해·후보/명령 보존을 전수 검사한다.
884논리 API 요청의 전달텍스트 UTF-8 총량/중앙/p95를 전후 비교한다. 보존과 총량 감소가 필수 gate다.
전달텍스트는 API가 파싱한 input+instructions+모든 choices.description 문자열의 합이며,
JSON 포장/이스케이프 포함 HTTP 본문 길이도 별도 보고한다. 바이트를 토큰으로 부르지 않는다. 선봉/강제교체/일반·테라/사용불가/동적타입/0/unknown 검사,
거부후성공·3회소진·통신혼합·취소·합법확률이상 검사 및 실제 API0 모의2경기 수집/감사/뷰어 필수.
본수집 전 실행소스·프롬프트·자료·대진·protocol과 미커밋 변경을 별도 snapshot/manifest로 고정한다.

## 평가와 완료

승무패, 점수율(승+0.5×무)/유효경기, 완료율(유효/32), 완료쌍/16,
입력사용량·지연·통신재시도/응답복구 빈도를 보고한다. EX112 주비교, EX110 보조참고;
공통 유효슬롯·공통 완료쌍으로 비교하고 실패·무효·미실행을 승패로 대체하지 않는다.
공개 차단+다른선택지가 있는 모델 선택의 차단선택률은 EX112 동일 판정기 보조지표다.
유효32경기·16쌍, 경기별 전수/최종감사·비교보고·뷰어링크·증거봉인·소유자원반환이 완료 기준이다.
기본 IO 설명 정확성 평가는 RD8.1에 따라 미평가. 별도 유료 사전호출/신규 기준선0.
과거비교·모델시점변동·경기전개·개발대진 한계를 보고하며 배치만의 인과효과/일반승률 개선은 주장하지 않는다.

## 환경·뷰어·출력

기존 /workspace/pokechamp/.venv/bin/python, GPU 사용 0, 기존 자격증명 값은 노출하지 않는다.
새 출력 /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-115.
뷰어 exports/battle_viewers/ex115, battle-viewer-ui-v1 / candidate-action-researcher-v1.
기본5탭 뒤 재구성 전 입력 → 후보별 적용 결과 → 선택·전송. 응답 시도 원문/최종선택 구분.
EP202에서 실행 전 지원·원문전수대조·대표 이동후 오프라인/리플레이 동기화를 검증한다.
정확한 생성기 소스는 동결 manifest/provenance 및 run의 renderer-manifest.json/renderer-source에 보존한다.
공유 CSS·행동 이름 JS·리플레이 bridge도 별도 동결하며 최종 내보내기 전후 identity를 대조한다. 이전 판본 불변.

## 결과

유효32/32·완료16/16쌍,20승0무12패·점수율62.5%.실패/무효/미실행0이다.
EX112 공통31슬롯은54.84%→61.29%(+6.45%p), 공통15쌍 차이 +6.67%p다.
EX110 공통32슬롯/16쌍 차이는 +12.5%p. 차단 선택은 EX112 0/29·EX110 15/71·신규0/76이다.
본HTTP997·자동24·입력/전송1021, 통신 재시도/응답 재질의0, 확인 입력14,903,986토큰·출력0·미확정0.
본수집에서는 실행 불가 응답이 없었으며 응답 복구 경로는 단위/모의 검사로만 확인했다.
경기별/최종감사·뷰어1021결정 원문 전수대조·이동후 오프라인/실제리플레이·봉인·소유자원 반환을 완료했다.
사전 완료 기준을 충족했으며 입력 배치 단독 인과효과/일반 승률 개선/복구 효능을 주장하지 않는다.

[최종 보고](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-115/evidence/report.md) · [비교](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-115/evidence/comparison/report.md) ·
[종결](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-115/evidence/completion.json) · [봉인 확인](../../../exec-plans/evidence/ep202/seal-receipt.json) ·
[뷰어](../../../../exports/battle_viewers/ex115/index.html).
