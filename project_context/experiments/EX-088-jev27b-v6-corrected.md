# EX-088 — 교정 v6 JEV-27B 신규32경기

- 상태: Completed
- 완료일: 2026-10-14
- 등록일: 2026-10-13
- 승인: 현재 사용자의 새64경기 명시 승인 / D-136 / EP-141
- 연구선·branch: `research/model-training`; checkout `/workspace`
- 시작 commit: `a4659bf298c7935714f9fbd25246db2d831c5926`
- 미커밋 상태: 기존 EX-084/085/086/087의 구현·문서·사후교정을 모두 보존한다.

기본 열람: [전체32경기 · Damage-calc](../../exports/battle_viewers/ex088-damage-v1/index.html).
[EP-142](../exec-plans/completed/EP-142-jev-damage-viewer.md)의 표시 재내보내기이며,
[수집 당시 봉인 뷰어](../../exports/battle_viewers/ex088/index.html)와 원자료를 보존한다.

## 채택 조건과 변경 범위

[EX-086](EX-086-jev27b-public-memory-v6.md)의 질문/처치·동결모델·대진·자원/시간·검증·
실패/복구·감사·완료·해석 절을 본 실험의 공통 protocol로 참조 채택한다. 당시 결과/중단은
계승하지 않는다. 아래 ID/출력·교정source·새 승인만 바꾸고 나머지 조건은 그대로 유지한다.
EX-089에도 본 공통 조건을 적용한다.

진영/필드 대상과 포켓몬 대상을 프로토콜 타입으로 구분하는 공개facts 교정과 SQLite/transport
경로 충돌의 사후 집계 교정을 사용한다. 이들은 C-067의 원래 의도를 구현하는 결함 수정이며
v6의 정보 경계·계산식·추천자료·자기상세·후보/명령/순서·선택 정책을 추가로 바꾸지 않는다.
수정 전/후와 CPU 검증 근거는 [EP-140 중단 보고](../exec-plans/evidence/ep140/report.md)다.

27B는 `autotrust/JEV-27B` revision `51740a8891c2a8baefd969237fd44187b3e3a115`, 공식LoRA
병합·BF16 backbone·FP32 head·bare-v1·공식 보정값을 유지한다. GPU0–3의14/18/18/14층,
embedding GPU0·norm/head GPU3·단일 Choice·16후보/32768토큰 무절단을 유지한다.
EX-083의 고유32슬롯/16진영교환쌍·팀·seed·제출순서·Abyssal·Gen9 OU·timer off를 전부 새로
실행한다. EX-088 뒤EX-089가 네GPU를 독점하며 경기/추론 동시성은 각각1이다.

모델별 본서버1회 적재·사전최대8추론(선봉6/일반13/강제교체5/공개벤치 긴 입력과
짧음→김→짧음→김)을 새로 승인했다. 같은 서버로 수집한다. 반복선택 동일·확률차이≤1e-4·
allocated회수/reserved비증가·실제배치/후보 연결 기준은 유지한다.591건GPU재생·모델간 확률일치
검사·독립2회 재적재0이다. 과거 검증은 새 source와 차이/재사용 범위를 명시한다.
앞선 결함이 드러낸 진영 이벤트 coverage gap은 기존 actor 공개prefix의 CPU facts 점검으로
확인할 수 있다. 과거 결과를 재감사하거나 모델 호출/평가 성적에 넣지 않는다.

## 자원·중단·집계

GPU당 allocator40GiB/전체44GiB·소유호스트32GiB·합산디스크100GiB, 경과시간 상한null,
HTTP600초·같은ID/본문의 최대3회 재전송10/30/60초·중복추론 방지를 유지한다.
두 모델·공유환경·정적자료·EX-083/085·중단EX-086/087 및 그 증거/뷰어·새EX-088/089와
뷰어·임시복사를 처음부터 합산하며 학습·양자화·offload·모델 중복복사0이다.
과거8사전+18수집 추론과 원시계를 이번 사용량/시계에 연결하되 새 유효 성적 분모와 구분한다.

새64경기의 승인 범위 안에서만 실행한다. 실행 불가능한 선택은 해당 경기 실패로 격리하고,
공유 입력/감사/무결성 결함은 양쪽 의존 작업을 중단한다. 모델 한정 자원/서빙 실패는 공유
비영향과 반환을 입증하면 다른 모델을 계속한다. 본수집source변경·재경기·보충·자동재개0이다.
사전 도구 교정은 원본/사용량 보존과 독립 검증을 요구하며 실제 모델/수치/자원 실패를 완화하지 않는다.

비교는 EX-088−EX-083, EX-089−EX-085, EX-089−EX-088의 공통 유효 진영교환쌍에서
승1/무0.5/패0 쌍평균 동일가중이다. 실패를 패배로 바꾸지 않고 모든 실패/미실행·사용량·사전비용을
분리한다. EX-083의2GPU23+4GPU9 구성을 명시하고 결합 처치의 고정 대진 탐색으로 해석한다.
일반 성능이나 모델 크기만의 효과를 주장하지 않는다.

신규 경기별1회 감사·종료 완전성/산술·전수 원문/턴 로그 내보내기/대조·모델별 최대5대표
오프라인 화면·모든 쓰기 종료 후 봉인·GPU/잠금/포트 반환·문서 갱신을 수행한다.
각 모델 유효32경기/16쌍이 완료 기준이며 미달이면 실제 분모와 미완료를 보존한다.

## 경로와 환경

명령 `scripts/jev-eval {prepare|execute|status} --experiment EX-088`.
run `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-088`,
viewer `/workspace/exports/battle_viewers/ex088/index.html`, protocol/source/evidence는 새 run에 둔다.
모델 `.pokechamp-data/jev27b-runtime/.venv/bin/python`, actor `pokechamp/.venv/bin/python`,
브라우저 `/tmp/ep037/tools/bin/python`과 기존 가중치를 그대로 사용한다.
기존 경로 덮어쓰기·중단 실험을 편집해 재개하기는 금지하며 새 ID를 명시 매핑한다.

## 최종 결과

신규32경기/32시도·유효32·완료16쌍이며15승0무17패, 점수46.875%다.
실패0·무효0·미실행0·완료율100%이며 최종 기술 감사를 통과했다.
EX-083과의 공통 유효16쌍에서53.125%→46.875%, 차이−6.25%p다.
새모델 비교는 EX-089−EX-088=−28.125%p이며 공통 유효16쌍이다.
기준EX-083의2GPU23+4GPU9 구성을 유지해 해석하고 일반 성능 개선을 주장하지 않는다.

저장880결정·849본수집 추론/HTTP POST·31자동선택·880명령이며 재전송/중복추론0이다.
본수집 입력13,009,311토큰·출력0·usage 미확정0이다. 본서버1회 적재와 사전8추론
(입력112,916토큰·65.219초)은 별도 비용으로 보존했다.
경기별1회 감사·종료 완전성/산술·전수 내보내기와 모델별5대표 오프라인 화면 검증을 통과했다.
뷰어는880결정·공개8,748행·원문981파일을 포함하며 실패 표시는 합성fixture로 구분했다.
모든 쓰기 종료 뒤 run/collection/viewer 봉인과 종결 시GPU/잠금/포트 반환을 확인했다.

[통합 최종 보고](../exec-plans/evidence/ep141/report.md) ·
[비교 검증](../exec-plans/evidence/ep141/final-comparisons.json) ·
[봉인/무결성](../exec-plans/evidence/ep141/final-integrity.json) ·
[32경기 Damage-calc 뷰어](../../exports/battle_viewers/ex088-damage-v1/index.html).
원 실행의 동결 protocol/source·원자료와 완료 기록은 위 run 경로에 보존한다.

저장 계산의 결정별 연결·표시 판본 검증은 [EP-142 보고](../exec-plans/evidence/ep142/report.md)에
기록한다. 새 경기·모델 호출·피해 재계산 없이 당시 자료만 표시하며 위 성적/분모는 유지한다.
