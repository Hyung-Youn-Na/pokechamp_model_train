# 입력·관측·메모리 — 실행 계약

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="c-072-candidate-display-names"></a>

<a id="c-072--후보-display_name과-실행-식별자"></a>
## C-072 — 후보 display_name과 실행 식별자

D-141/EP-147의 새 planner 설정은 executor.candidate_display=names-v1을 기본으로 동결한다.
original 또는 필드 없는 과거 동결 설정은 입력을 그대로 보존한다. names-v1은 현재 결정의
자기 팀/기술 명시 slot으로 이름을 해석하여 후보 객체에 display_name만 추가한다.
일반 기술/Tera·선봉/교체를 구분하며 ID·후보순서·slot·move_ref·명령·확률 대응은 바꾸지 않는다.
동명이거나 임시복사된 기술도 현재 슬롯을 사용하고 배열 위치·이전 턴·상대 비공개 정보로 추정하지 않는다.
이름을 해석할 근거가 없으면 미확인을 표시하며 이름 때문에 실행 행동을 바꾸지 않는다.

같은 표시 후보를 planner current.criteria와 JEV Choice 입력에 전달한다. planner off도
선택한 표현 조건을 사용하므로 새 names-v1 on/off 비교는 표시명이 같은 조건이다.
기존 C-070의 원입력 off는 과거 설정/original에서 유지한다. 미리보기·기록·뷰어는 실제 전달
표시명을 사용하고, 기존 이름 없는 기록은 당시 관측으로 표시한다. 표시명으로 명령을 복원하지 않는다.
이 설정 차이는 executor 입력 조건 차이로 식별하며 단순 planner 프롬프트 효과로 집계하지 않는다.
기존 v6 생성기·과거 실행/봉인/뷰어는 보존한다. 실제 성능 효과는 미평가다.

<a id="c-068-jev-no-damage"></a>

<a id="c-068--jev-피해-예측-제거-입력과-단독-평가"></a>
## C-068 — JEV 피해 예측 제거 입력과 단독 평가

D-137/EX-090의 `jev-choice-v6-no-damage`에 적용한다. C-067의 공개 정보·현재 관측·추천세트
필터·스피드 비교·자기상세·후보/명령/순서·로그 의미를 유지하며 양방향 피해 범위/계산불가 사유
필드와 해당 프롬프트 설명만 생략한다. 일반 피해/배틀 규칙·기술위력·타입표는 유지한다.
관측 정규화와 추천세트 준비를 피해 시나리오 생성에서 분리하며 outgoing/incoming 계산0,
speed용 계산만 허용한다. 결과를 계산한 뒤 숨기지 않는다. 감사에는 비활성화 처치와 스피드 호출을
남긴다. 기존 입력 버전/기본 동작과 봉인 자료는 불변이다.
실행·사전검증·경기별 감사는 동일 프로필을 명시 선택한다. EX-089 저장 입력의 CPU 대조와
단독 실행·동결/자원·최대8추론/단일서버·감사/비교/뷰어/봉인/반환 원문은 EX-090을 따른다.
다른 모델 선행/후속 실행이나 기존 수집 재개를 요구하지 않는다.

<a id="c-067-jev-public-memory-v6"></a>

<a id="c-067--상대-공개-정보-v6와-턴-로그"></a>
## C-067 — 상대 공개 정보 v6와 턴 로그

D-135/EX-086/087 및 D-136/EX-088/089에 적용한다. EX-088/089는 교정된 구현의 새 평가이며
이전 중단·봉인을 바꾸지 않는다. 현재 공식 관측과 동일 행 cutoff의 전체 actor 공개prefix로
상대 facts를 재구성하며 이전payload·정답세트·foreign request·미래·근거 없는 관측 추정을 쓰지 않는다.
cutoff/개체 식별이 모호하면 실패하고 근거 없는 속성은 unknown이다. 원관측·근거·보완 이유는 감사에만 둔다.
일반 기술은 교체/시간 후 유지하고 Mimic/Transform 일시복사·Sketch 지속변경·호출/반사를 구별한다.
도구는 공개 현재소유/소모/Knock Off/Trick/회수 순서를 적용하며 prevItem으로 부활시키지 않는다.
특성은 Trace/Skill Swap 소유자·공개 baseAbility·현재특성·교체복귀·억제/해제를 구별하며
숨은 Ability Shield 등을 추정하지 않는다. 기존 effect id/name/general_effect·knowledge·
suppressed/underlying_ability를 재사용하고 특성 정체를 발동 증거로 사용하지 않는다.
상대 벤치에도 moves/item/ability/baseAbility를 유지하되 공개HP hp_percent/hp_precision만 사용한다.
비공개 회복을 추정하지 않고 교체 해제 boosts/volatile/일시효과를 벤치에 누적하지 않는다.
같은 helper를 현재대면 정규화·추천세트 필터에 연결한다. 피해량/스피드 식·자료·현재출전끼리
계산범위는 불변이며 벤치계산0, 현재효과 불확정은 기존 unavailable/null+사유다.
공통함수에는 선택적v6 경로만 추가하고 v4/v5 기본·후보/명령/순서·자기상세·정책은 보존한다.

새 뷰어의 상대HP는 공개비율/정밀도·0/unknown을, 도구/특성은 부재/억제를 실제 저장입력으로 표시한다.
턴로그 원천은 events.jsonl의 해당 모델username 수신 배틀protocol만이다. sequence/line_index를
보존하고 request/sentchoice·private control/debug/chat/outbound를 배제하며 미해소split은 거부한다.
준비0/각턴·고정BattleTextParser의 읽기쉬운 로그·미지원원문·같은 구간의 펼치기/복사/다운로드를 제공한다.
선택턴 전체와 결정후 결과를 구분하고 결정전까지 전환은 프레임 중간 행cutoff를 지킨다.
결정→턴, 턴→첫결정 연결·동일턴 다중결정·결정없는턴을 지원한다. win/tie는 마지막턴,
종료없는 실패는 진행중중단이다. 전체로그를 모델의 최근3턴 로그에 합치지 않는다.
새HTML/JS/변환기를 실행source에 포함하고 이동후 오프라인 열람을 지원한다.
자원/단일적재8추론·수집·중단·감사/표본검증·봉인 조건은 각 평가의 EX-086/087 또는
EX-088/089 원문을 따른다. 새 ID/출력은 명시 코호트로 연결하고 중단 결과를 덮어쓰지 않는다.

<a id="c-014--개선-io-조건의-입력출력실행-경계"></a>
## C-014 — 개선 IO 조건의 입력·출력·실행 경계

[D-019](decisions/D-019-improved-io.md)의 B/C는 C-008 JSON-only 및 C-012 출력의 별도
명시적 조건이다. 고정 정책+영문 근거1–2문장+마지막 줄 단일 행동 JSON을 사용한다.
추가 JSON·중복 key·후보 밖 행동은 거부한다. A는 C-013 upstream을 유지한다.
최신 자기 request와 원래 자기 세트, 상대 공개 사실 및 별도 고정 prior 추정만 입력한다.
@smogon/calc 0.11.0 actor별 프로세스와 계산 identity/범위/미지원 검사를 LLM 전에 적용한다.
C의 요약은 같은 battle/actor의 결정 이후 반영된 protocol까지 참조하고 최신 관측을 덮어쓰지 않는다.
B/C 첫 입력·계산·출력·요약 오류는 해당 경기 중단이며 repair/fallback은 없다.
모든 역할·조건은 배틀10/계정10/모델10의 단일 broker를 공유한다. 실행 설정 부재나
순차 경로는 새 조건에서 거부하며 기존 설정 부재의 의미는 보존한다.
조건 ID 및 프롬프트/prior/계산기 lockfile/평가 source는 봉인한다. node_modules/빌드는 제외한다.

[D-020](decisions/D-020-project-owned-ruination-patch.md)에 따라 B/C 계산기 identity는
`@smogon/calc 0.11.0` + `ruination-v1` + 패치 JSON SHA-256 + 적용 파일별 SHA-256이다.
설치는 `npm ci --ignore-scripts` 다음 명시적 `npm run patch:calc`를 요구한다. Worker는
모듈 로드 전 읽기 전용 검증을 수행한다. 누락·버전·해시 불일치는 원인이 있는 CalculationError로
종료하며 어떤 LLM 역할도 호출하지 않는다. 응답 engine_patch를 Python 수신부와 입력 검증기에서
기대값과 대조하고 trace/오프라인 결과에 보존한다. 패치·적용/검증 코드를 source seal에 포함한다.

D-022 재개에서는 실제 발생 계산/입력 오류의 프로젝트 소유 후속 패치를 허용한다.
0.11.0과 engine_patch 응답 구조를 유지하고 새 ID/해시·설치/Node/Python 검증을 함께 갱신한다.
실행 중 패치는 금지하며 실패 source·입력·응답 및 receipt는 불변이다. 단계 receipt는 전체
분모·검증 결과·현재 source 및 선행 receipt/output seal과 연결하고 검증 실패 시 다음 단계를
거부한다. 최초 Cloud 시계는 독립 봉인하여 재시작에도 초기화하지 않는다.

재개 범위 보충: [D-026](decisions/D-026-continue-io-experiment.md)의 EX-023은 C-014/D-022
운영 경계를 유지하며 EX-022 후속 상태 교정을 사용한다. 과거 EX-020의 halt/clock은 불변이고,
새 사용자 승인에 연결된 별도 EX-023 시계와 source/단계 identity를 사용한다.

D-027/EX-024는 `evidence.io_summary_prompt_version`으로 요약/통합의 같은 버전·해시를
Cloud 검증과 실제 배틀에 고정한다. 필드 부재는 원본 v1.0.0이다. 검토 대기는 봉인 응답으로
재개하며 Cloud 검증에서 미검토 요약을 후속 요약/통합/행동에 사용하지 않는다. 버전별 halt와
전체 halt를 구별하고, 최대3개 유료 source/프롬프트 조합이 최초 제출 시계를 공유한다.

<a id="c-015--독립-요약-harness-진단"></a>
## C-015 — 독립 요약 harness 진단

[D-023](decisions/D-023-summary-harness-diagnostics.md)의 EX-021은 C-014/D-022 운영 경로와
분리한다. 모델 요약 사실·형식 오류에 한해 측정 결과로 보존하고144개 예정 표본을 계속 수집한다.
Provider·환경·무결성·입력 변환 오류는 전체 중단하며 재시도·보충·재질문·실행 중 수정은 없다.
prepare는 원자료·봉인 재구성 코드·48입력·144일정·독립 평가 기준 해시를 고정한다.
run은 호출별 독립 backend/context와 계정/모델10/10 broker, 제출 intent와 worker 응답 선봉인,
최초 제출 기준45분/60분 영속 시계를 사용한다. report --review는 가린 응답과 근거/검토
해시를 연결하며 미완료·미확정·대응 누락을 명시한다. 미래/상대 비공개 정보와 정답 문구는
입력 금지다. EX-020 halt/receipt/clock과 EP-011 Blocked를 변경하지 않는다.


C-015의 입력/평가 근거 무결성 실패가 수집 후 발견되어도 전체 비교 자격을 철회한다.
봉인된 halt와 실패 근거를 확인한 report는 효과 추정 없이 무효·미완료 보고서만 생성하고
--review로 정상 비교를 복구할 수 없다. run은 halt가 있는 디렉터리의 제출을 거부한다.
기존 receipt와 원자료는 당시 상태로 보존하며 후속 로컬 교정은 별도 provenance로 기록한다.

<a id="c-016--상태-의미와-요약-thinking-진단"></a>
## C-016 — 상태 의미와 요약 thinking 진단

[D-024](decisions/D-024-state-summary-thinking.md)의 EX-022는 정비된 운영 경로로 생성한
장면당 하나의 입력·독립 원본 정답과 low/high72일정을 봉인한다. profile이 조건·분모·시계를
정의하며 EX-021의144 가정을 재사용하지 않는다. summary/summary_rollup만 검증된
summary_thinking_effort를 사용하고 기본/행동은 low다. 실제 think와 request 기록은 같은
요청별 결정값을 쓴다. 잘못된 설정은 네트워크 전에 거부한다.
시간 의미는 행 순서의 발생 턴/마지막 갱신 턴/경과 counter/설치 턴/겹 수를 구별한다.
Future Sight는 원본 시작 행이 있을 때만 observed_start_turn을 기록한다. 예약은 대상
위치에 유지되며 교체된 사용자 효과 counter와 분리한다. 근거 부재는 미상이다.
운영/진단 의미 주석은 parent 공통 해석을 사용하지만 평가 정답은 해당 변환을 사용하지 않는다.
C-015의 응답 선봉인·영속 시계·halt·미확정 보존을 적용한다. 모델 오류만 수집 계속이며
provider/환경/무결성/입력/평가 기준 오류는 전체 중단한다. EX-020/021의 과거 자료는 불변이다.

<a id="c-017--고정-이전-메모리-lowmax-요약-진단"></a>
## C-017 — 고정 이전 메모리 low/max 요약 진단

[D-028](decisions/D-028-summary-max-diagnostic.md)의 EX-025는 summary-max-v1 profile로
22입력/132일정·v1.1.2·원문 검토된 고정 이전 요약·입력별 평가 기준을 봉인한다.
summary_thinking_effort는 low/high/max를 검증하고 summary/summary_rollup에만 적용한다.
운영 기본·행동은 low다. 진단의 low/max는 같은 SDK 호환 전송 어댑터를 사용하며
실제 직렬화 think·역할·prompt hash와 trace를 대조한다. SDK/canonical submodule은 변경하지 않는다.
C-015/016의 독립 context·선봉인·무결성·중복제출 거부·전체 무효화 정책을 유지하고,
profile의 최초 제출부터13500초 신규제출/14400초 총시간과132유료 상한을 적용한다.
모델 오류 응답은 다른 입력으로 전파하지 않고 수집 계속한다. 과거 중단 상태는 불변이다.


<a id="c-019--요약-없는-ab-profile-및-복구-실행-경계"></a>
## C-019 — 요약 없는 A/B profile 및 복구 실행 경계

[D-030](decisions/D-030-io-battle-only.md)의 `io-battle-only-v1`은 C-014의 관측·prior·계산·
fixed 행동 출력 경계를 재사용하되 A/B만 허용한다. B는 요약 prompt 선택/품질 gate/cadence에
의존하지 않으며 summary=null, lesson_memory=[], 요약/통합 역할 호출과 archive0을 검증한다.
기존 A/B/C profile과 과거 receipt 검증은 보존한다. A는 C-013 upstream fallback이다.

준비/단계 receipt는 profile·조건·운영 입력/독립 평가/실제 prompt/계산/source identity를
연결한다. 전체 공개 prefix와 최근10결정 전송 window를 구별한다. 필수 판단 근거의 실제
입력 도달성을 원문과 별도로 대조한다. Cloud intent와 worker 선봉인 응답을 연결하고
모든 실제 HTTP 직전 요청을 최초 clock/누적4000상한에 원자적으로 예약한다. 미확정도
차감하지 않는다. Source는 수집 중 불변이다. 배틀10/계정10/모델10 및 provider retry0이다.

새 profile 복구는 별도 봉인 기록과 identity에서만 실행한다. 원인·영향·원본/수정 source·
기준·독립 검증·관련 회귀·무효/재평가/재수집 단위를 연결한다. 영향 대응은 양쪽을 포함하며
공유 결함의 영향 집합을 누락하지 않는다. 복구1차·180/16/64 및 최초4시간/4000요청을
공유한다. 기존 halt/receipt/clock을 삭제/덮어쓰기하지 않고 모델 오답을 복구 사유로 쓰지 않는다.
이 새 경로의 구현·검증 범위는 EP-018/EX-026에 기록하며 기존 실행기의 복구 한계는 유지한다.


C-019 평가 복구 보충: English 문장은 ASCII 문장 부호로 한정되지 않는다. D-030의 새 profile만
typographic 대시/따옴표를 언어 검사에 허용하며 정확한 JSON·후보·문장 수 계약은 유지한다.
평가 교정 e1은 원래 입력/처치/기준 동등성을 확인하고 온전한 응답을 재호출하지 않는다.
미확정 요청이 있으면 미실행 재개 경로를 거부한다. 별도 새 판정과 미제출 ID만 최초 시계·누적
상한에 연결하며 c0 halt/응답은 보존한다. 유료 재수집 차수와 평가 교정 재개는 구별한다.

C-019 필드 설명서 보충([D-031](decisions/D-031-battle-field-guide.md)): 새 요약 없는 B 준비는
행동 v1.1.0을 기본으로 선택하며 버전 부재의 과거 설정은 v1.0.0이다. A 및 요약 실험 선택은
유지한다. 단일 fields.json에서 경로/자료형/단위/시점/불확실성을 렌더링하고 기존 policy에
결합한다. prepare·Cloud worker·actor는 공통 조립 함수를 사용하며 매 시스템 메시지에 한 번
포함한다. 사용자 JSON·합법 후보·출력 계약은 유지한다. v1.1.0은 원문 request JSON까지
중첩 경로와 동적 키를 검사하고 미설명 필드를 제거하지 않고 경로를 보고하여 거부한다.
선택 버전·원본/설명서/완성 prompt hash는 manifest·execution·요청에 연결하며 불일치를
거부한다. 과거 receipt를 새 설명서 기준으로 소급 검증하지 않는다. EX-026 재개나 Cloud
gate 통과를 뜻하지 않으며 이번 승인 범위는 구현·로컬 검증이다.

<a id="c-020--명시적-battle-guide-live-v1-실험-정책"></a>
## C-020 — 명시적 battle-guide-live-v1 실험 정책

[D-032](decisions/D-032-battle-guide-live.md)의 사용자 승인으로 C-019 새 정책 선택을 추가한다.
정책 없는 과거 자료는 D-030 상한·엄격한 의미 gate를 그대로 적용한다.

A는 upstream IO·fallback, B는 교정 관측·고정 prior·계산기·필드 설명서 v1.1.0이다.
B 요약·통합·메모리 주입0. 모델 glm-5.3-flash/low/temperature0/seed100/출력131072/
provider 기본 context, 요청 timeout300초·경기 watchdog1200초·provider retry0을 유지한다.
`battle-guide-live-v1` 정책을 prepare에서 선택하고 manifest·study·execution·receipt·보고서에
봉인한다. 정책 부재는 D-030이다. 새 정책의 전체 비용·시간·행동 요청 상한은 없으며
요청/시간 상한은 명시적 null이다. 알려진 정책과 identity 일치 없이 null을 인정하지 않는다.
최초 Cloud 시각·요청·실패·미확정·token·경과 시간은 계속 누적한다.

로컬 회귀·운영15장면 의미/입력 도달성·사후피해3·필드완전성/전달·fake32(32/32,
실제 동시10, 격리오류0, 설명서 요청당1회, 요약0; native library thread1) 후
Cloud90(15장면×요청동시성1/10×3반복)을 수집한다. 출력/합법행동90/90, provider오류/
미확정0, HTTP overlap10, 병렬p95≤순차p95×2와 전체 원문/실제입력/계산 대조 검토를 요구한다.
설명 사실·진영·시점·계산 오류는 측정값이며 기술 gate와 분리한다. 오류가 남으면 의미
검증 통과로 표시하지 않는다. 출력·합법행동·입력/증거무결성·검토 완전성은 필수다.

smoke8은 b04 Abyssal/OneStep×양쪽×A/B, 실제 동시8·유효8/8·구성/IO오류0·요약0·격리
검증을 요구한다. 본 비교32는 Abyssal/OneStep×b01–b04×양쪽16대진에 A/B 대응,
EX-016 팀/게임 seed 고정·순서 seed20260908·배틀최대10/계정·모델요청최대10이다.
smoke 기반32판 시간 및50% 여유 추정은 보고용이며 남은 전체 시간으로 진입을 막지 않는다.
smoke는 본 비교에 합치지 않는다.

Cloud 기술 gate 실패는 후속 배틀을 차단한다. 실제 배틀 출력/provider/환경 오류·watchdog은
신규 배틀 제출 중지와 진행 자료 보존·정리를 요구한다. 합법 완료 설명 오류는 승패 제외
사유가 아니다. 모델 오답 재추첨·실험 중 prompt 변경은 금지한다.
D-029/C-018 영향입증·독립재현·수정·회귀 후 복구한다. 입력/처치/수집 재수집 최대1차,
영향 A/B 대응 양쪽·공유영향 전체를 포함하며 누적 gate180/smoke16/compare64를 유지한다.
이는 전체 행동 요청 상한과 별개다. 평가 구현 오류는 온전 응답을 대칭 재평가하고 rubric
교정은 공개된 별도 수정 분석이다. 원자료/halt/최초시계/누적사용량을 초기화하지 않는다.
기존 EX-026 및 모든 실험의 응답·판정·halt·시계·Blocked는 보존한다.

상대별 (승+0.5×무)/유효완료, 두 상대 동일가중 평균, 완료대응 B−A·누락과 예정/시도/
완료/실패/무효/미실행/미확정/복구를 분리 보고한다. B gate·배틀 설명 전수검토의 오류 종류/
근거/분모, A fallback·호출/token/HTTP지연/배치시간/동시성·정리를 보고한다.
전체 B 구성의 개발 대진 탐색적 비교이며 설명서 단독 효과나 L1–L5 전체 효능으로 귀속하지 않는다.

<a id="c-021--battle-guide-direct32-v1-실행출력-복구-경계"></a>
## C-021 — battle-guide-direct32-v1 실행·출력 복구 경계

[D-033](decisions/D-033-battle-guide-direct32.md)의 명시적 사용자 변경을 새 EX-028에만 적용한다. C-014/C-019/C-020의 기존 엄격 gate·출력 중단 경로는 유지한다.

A는 EX-027의 upstream IO·fallback, B는 교정 관측·고정 prior·계산기·필드 설명서 v1.1.0이며 요약·통합·메모리 주입0이다.
모델 glm-5.3-flash, thinking low, temperature0, seed100, 출력131072, provider 기본 context,
요청 timeout300초·watchdog1200초·배틀/계정/모델 요청 최대10을 유지한다.
EX-027/EX-016 개발팀·게임 seed·Abyssal/OneStep×b01–b04×양쪽16대진의 A/B32판과 순서 seed20260908을 고정한다.

명시적 battle-guide-direct32-v1에서만 사전 회귀·15장면·fake32·Cloud90·smoke8을 skipped_by_user로 기록하고
설정·source·prompt·대진 봉인 후 compare32에 직접 진입한다. 생략한 gate 통과 receipt는 만들지 않는다.
전체 비용·시간·행동 요청 상한은 없고 provider retry·추가 재수집은0이다. 기존32 slot을 각1회 시도한다.
최초시계·원장·미확정과 사용량을 보존하며 수집 중 source/prompt를 수정하지 않는다.

B는 기존 출력 계약을 먼저 적용한다. 실패하면 원문에서 유일한 JSON 객체 행동을 중복 키 거부와
정확한 후보·강제교체·테라 조건으로 검사해 추출한다. JSON 없음/복수/중복 키/불법이면 봉인된 후보의
첫 행동을 사용한다. 원출력 판정·추출 행동·실제 실행 행동·선택 출처를 별도로 기록하며 재호출하지 않는다.
출력·설명 오류는 계속한다. Provider·timeout·watchdog·경기별 환경 실패는 해당 경기만 종료한다.
합법 후보 부재·공유 입력/계산 결함·설정 불일치·증거/격리 무결성 문제는 영향 범위를 중지한다.
범위 불명확은 잠재 영향 전체를 중지한다. C-018의 증거 보존·영향 분석을 적용하되 재수집0이며
기존 EX-027 및 다른 실험의 원자료·halt·시계·Blocked는 변경하지 않는다.

Viewer는 문제 턴 수·완료/실패·문제 목록·battle/actor/decision 링크를 제공한다.
출력 형식 오류/행동 추출/대체 행동/설명 오류/실행 실패를 텍스트와 색으로 구별하고 원문·오류·추출/전송 행동을 표시한다.
B 수집 설명은 원문·실제 입력·계산/공개 근거에 사후 전수 대조하고 사실·진영·시점·계산 오류를 별도 봉인 annotation으로 연결한다.
검토 전은 미검토다. 원자료를 수정하지 않는다.

자연 종료·실제 행동/입력/증거가 온전한 경기는 대체 행동·오류 표식을 포함해 성적에 포함한다.
정상 출력만 있었던 경기 수, 상대별 (승+0.5무)/유효완료, 두 상대 동일 가중 평균,
완료 대응 B−A·누락/실패/미확정·A/B fallback·호출/token/시간/동시성을 보고한다.
오류 처리 정책을 포함한 전체 구성의 개발 대진 탐색 비교이며 설명서 단독 효과나 L1–L5 효능으로 해석하지 않는다.

<a id="c-022--battle-guide-calcfix32-v1-계산기-교정-및-실행-경계"></a>
## C-022 — battle-guide-calcfix32-v1 계산기 교정 및 실행 경계

[D-034](decisions/D-034-calculator-entry-calcfix32.md)의 EX-029에서만 신규 정책을 선택한다.
C-021의 출력복구·실패격리·재수집0을 유지하되 결함재현·독립검증·회귀/source/설정 검증을 진입조건으로 봉인한다.
기존 정책의 hash/동작과 원자료는 보존한다. species fallback 억제는 인스턴스에만 적용하고 라이브러리/JSON/EV/IV/prior/prompt는 유지한다.
EX-028 대진과 정확히 대조하며 최초시계·원장·미확정1건을 참조하고 누적사용량을 보고한다. 상세조건은 D-034/EX-029를 따른다.

<a id="c-023--계산기-입력-로컬-조사수정-경계"></a>
## C-023 — 계산기 입력 로컬 조사·수정 경계

[D-035](decisions/D-035-calculator-input-audit.md)/EX-030은 전체 입력 경로의 독립 로컬 진단이다.
발동·소비 이력은 battle별 Pokémon identity에 연결하고 최근10결정 이후에도 유지한다.
불명확한 이력을 미발동으로 가정하지 않는다. 매 등장/배틀당1회 특성을 구분한다.
새 상태·의미는 새 버전·입력 검증·필드 설명·provenance로 연결하며 과거 artifact의 의미는 보존한다.
원시/관측/worker/최종 입력을 별도 검증하고 지원하지 않는 상태는 정상 계산으로 제시하지 않는다.
기존 기능을 검사 통과 목적으로 제거하지 않는다. 명중 조건부 피해와 시점 경계를 유지한다.
기존636입력은 공개 cutoff까지 재생하고 영향은 별도 정정 분석한다. 유료 호출·재수집은0이다.


C-023의 구현 버전은 `calculator-input-v2`와 `battle-v1.2.0`이다. identity.input_version,
current_observation.calculator_semantics, calculation_bundle.semantics_version은 일치해야 한다.
Pokémon별 ability_history에는 battle/actor/ident, history_complete, entries, activations,
suppressed, qp_source, team_faints가 있다. battle_types와 effective_types를 분리한다.
worker는 source/context/output hash로 검증된 mechanics-v2 메모리 overlay를 사용한다.
request_sha256·bundle_sha256, scenario coverage, 최신 raw request 및 필수 이력/소유권 검증이
provider transport보다 앞선다. 필드 설명서는 원문 request JSON까지 경로를 확인한다.

scenario_state는 current_decision/after_selected_switch_entry/after_selected_terastallization을
구분하며 진입 hazard HP·status, 유효 weather/terrain, 활성화 후 items를 공개한다.
damage_variants는 hit수/위력 분기를 나타내고 확률값이 아니다. 선택 테라 incoming coverage는
어느 기술의 랭크 변화도 적용하기 전 상태다. Future Sight의 미래 target/field는 UNKNOWN이다.
역사적 v1.0/v1.1 자산·artifact는 원래 의미를 유지하며 v1.2에서 v2 상태를 생략하는 downgrade는
거부한다. 상세 지원 경계·독립 검증은 [EX-030 보고서](../../exec-plans/evidence/ep023/report.md)를 따른다.


D-037 기술명 정규화: worker는 검증한 pinned generation move의 canonical 이름으로 Move를 생성한다.
입력 ID/표시 이름/대소문자 차이가 날씨·아이템·지형·타입 변경 분기를 누락시키지 않아야 한다.
알 수 없는 기술은 기존처럼 실패한다. 이 bugfix는 schema/semantics 버전을 바꾸지 않으며 source hash로 구분한다.
과거 qualification/원자료는 보존하고 기존 source용 qualification을 새 source에서 재사용하지 않는다.
[검증 범위](../../exec-plans/evidence/ep025/report.md).

D-043 Protect 만료 교정: B는 전체 actor 공개 prefix의 발생 이후 turn/upkeep·교대·기절·해제로
입증된 만료 PROTECT만 effects에서 제거하고 parser_effects는 원형 보존한다. 공개 유효 활성의
parser 누락은 보완하고, 근거 부족·모순은 제거 근거로 삼지 않는다. 현재 PROTECT 계산 거부는 유지한다.
수명 근거는 내부 전달 및 별도 검증 기록에만 남기며 기존 JSON/프롬프트/calculator-input-v2는 유지한다.
수정본은 새 source hash와 protect-expiry-v1 검증으로 식별하고 EX-036 중단·과거 qualification은 보존한다.

D-062 입력 교정: 전체 actor 공개 prefix의 `-activate ... move: Court Change`로 입증된 실행
알림은 계산용 effects에서만 제외하고 parser_effects를 보존한다. `-swapsideconditions`는 pinned
Showdown의 교환 대상 진영 효과 기록을 설치 시점·원본 참조·중첩 그대로 이동한다. 명시적인
`-status ... [from] ability ... [of] holder`의 공개 특성은 그 보유자에 귀속하며 피해자에게 옮기지
않는다. 상대의 effective_types는 기절 시 pinned Showdown의 테라 해제를 반영한다. 기존 parser
표현과 관측 tera_type·CLI/schema/calculator-input-v2·계산 미지원 거부는 유지하고 source hash로
구분한다. 검증·과거 입력 영향은 [EP-051](plans/EP-051-court-change-input-audit.md)에서
별도 기록하며 과거 입력을 소급 교정하거나 기존 실험을 재개하지 않는다.

<a id="c-024--battle-guide-inputfix32-v1-교정-입력-실행-경계"></a>
## C-024 — battle-guide-inputfix32-v1 교정 입력 실행 경계

[D-036](decisions/D-036-calculator-inputfix32.md)의 명시적 사용자 승인에 따라 EX-031에서 새 A16/B16을 실행한다.
C-021 출력복구·실패격리·재수집0을 유지하며 B만 calculator-input-v2/battle-v1.2.0/mechanics-v2다.
EX-028 봉인 대진·설정·순서를 유지하며 qualification과 semantics/runtime patch를 최종 source 및 실제 요청까지 연결한다.
기존 정책 정의/hash/과거 실험은 보존한다. 필수 로컬 검증 뒤 Cloud90/smoke8/별도fake32 없이 직접32판을 실행한다.
EX-028/029 사용량은 각 원본을 한 번씩 연결하고 미확정1건을 유지한다.
전수 검토·분모·보존·실패 정책·완료 판단의 사전 등록은 [EP-024](plans/EP-024-calculator-inputfix32.md)를 따른다.
성능 비교 완료는 유효32판/16대응에만 표시하며 과거 무효 결과 합산·계산기 단독/L1–L5 효과 귀속은 금지한다.


<a id="c-025--battle-guide-movefix32-v1-수정-완료본-실행-경계"></a>
## C-025 — battle-guide-movefix32-v1 수정 완료본 실행 경계

D-038/EP-026/EX-032에만 적용한다. C-021의 출력복구·실패격리·재수집0과 C-024의 v2 전달 경계를 유지한다.
새 정책·qualification은 EP-025 봉인 기준 source/검증과 새 실행 연결 변경분 검사를 함께 연결한다.
593회귀·독립28조건/16roll·81재생은 반복하지 않으며 최종 전체 source 재검사로 주장하지 않는다.
과거 정책 hash/receipt는 불변, 새 source/config/manifest를 봉인한다. EX-028/029/031 자체 사용량을 각각 한 번 연결한다.
필수 연결 검사 후 fake32/Cloud90/smoke8 없이 새32판을 실행한다. 상세 조건·중단·완료 기준은 EP-026을 따른다.

<a id="c-026--외부-환경-장애-후-동일-조건-새-반복"></a>
## C-026 — 외부 환경 장애 후 동일 조건 새 반복

D-039/EP-027/EX-033의 명시적 새 실행 승인에 한해 C-025의 처치·검증 재사용·보고 경계를 적용한다.
새 battle-guide-external-repeat32-v1의 runtime identity는 EX-033/D-039이며 이전 정책/hash는 유지한다.
외부 요인 귀속은 사용자 보고이고 독립 OOM 확정과 구분한다. 기존 permit 코드를 수정한 것으로 표시하지 않는다.
기존 실행·halt를 보존하며 새 준비에 EX-032의 보고/원장/시계/halt·승인·동일조건 근거를 봉인한다.
EX-028/029/031/032 각각 자체 사용량+새 실행을 한 번씩만 누적하고 과거 미확정1건을 보존한다.
이번 전체32판 반복 외 추가 보충/재수집0이다. 재발 시 기존 공유 결함 중단 규칙과 실제분모 보고를 유지한다.


<a id="d-041-원본-a64-진단-실행"></a>
## D-041 원본 A64 진단 실행

[D-041](decisions/D-041-a-diagnostic64.md)의 명시적 사용자 승인으로 EX-034 준비에서 EX-035 실행으로 진행한다.
EX-034 평가 protocol v1은 유지하고 운영 watchdog만3600초로 변경한다.
새 a-diagnostic64-v1은 A-only, 첫10 검사 후54, 로컬/fake64 필수, Cloud90/smoke8 없음,
최초 요청부터20700초 수집/21600초 총시간·8000요청 원자 예약·동시성10·재수집0이다.
기존 정책/원자료는 보존하며 상세 사전등록은 [EP-029](plans/EP-029-a-diagnostic64.md)를 따른다.

<a id="c-027--ab-head-to-head32-v1-실행-경계"></a>
## C-027 — ab-head-to-head32-v1 실행 경계

이 계약의 실행·분모·검토·보존 조건은 동일 원문을 유지한
[연구 설계 D-042](DESIGN.md#d-042-원본-ab-직접-대결32) 절 전체를
이 계약의 규범 내용으로 참조 편입한다. C-027의 실행 경계 권한과 기존 적용 범위는 유지한다.

<a id="c-028--ab-head-to-head32-protectfix-v1-실행-경계"></a>
## C-028 — ab-head-to-head32-protectfix-v1 실행 경계

[D-044](decisions/D-044-ab-head-to-head32-protectfix.md)와 [EX-037](experiments/EX-037-ab-head-to-head32-protectfix.md)의 현재 명시적 지시를 채택한다.
이 계약의 중복된 실행·실패·보고·완료 조건은
[EP-032 §목표·범위·승인·불변조건](plans/EP-032-ab-head-to-head32-protectfix.md#목표범위승인불변조건)의
“현재 사용자 제공 실행 계획을 명시적 승인 근거로 EX-037/EP-032/D-044를 등록한다.”부터
“중단 시에도 수집분 검토/보고/보존/정리와 실제분모·미완료 사유를 기록하며 중단처리 완료를 비교완료로 표시하지 않는다.”까지를
이 계약의 규범 내용으로 참조 편입한다. 해당 원문은 변경하지 않았으며 C-028의 권한을 이전하지 않는다.

<a id="c-030--b-오프라인-전달-표현"></a>
## C-030 — B 오프라인 전달 표현

D-046/EP-034의 B0–B3는 원본 battle-v1.2.0 및 calculator-input-v2를 먼저 검증한다.
후보 버전과 계산 의미 버전을 독립 필드로 봉인하고 누락·불일치는 거부한다.
원본 패치·state/request/bundle hash 검증은 유지한다. 원본 전체 + 후보 버전에서 생성한
system/user 문자열 및 원본 연결 정보와 실제 전달 값이 정확히 일치해야 한다.
B1의 명시적 제외 목록 외에는 모든 필드가 보존 또는 역변환 가능해야 한다.
B2 scenario 연결과 공유 참조는 유일하고 한 단계이며 시나리오 순서·타수/난수 분포를 유지한다.
B3는 window를 줄이지 않고 request 최초 상태/객체 변경분/삭제/배열 전체 교체를 사용한다.
null은 삭제가 아니며 미해석 protocol 행은 그대로 남긴다. 비어 있지 않은 메모리 및
Gen9 OU singles 외 범위는 거부한다. 이 인터페이스는 오프라인 전용이며 운영 기본값은 불변이다.


<a id="c-031--ex-038-b2-실제-전달-경계"></a>
## C-031 — EX-038 B2 실제 전달 경계

D-047/EP-035의 명시적 사용자 지시에 따라 C-030의 오프라인 한정을 새 EX-038 B2 경로에서만 확장한다.
원본 전체 입력 검증 후 EP-034 B2를 생성하고 전송 직전 원본·후보·실제 system/user 문자열 일치를 검사한다.
출력 검증과 복구는 원본 전체 입력을 사용한다. calculator-input-v2와 전달 후보 B2를 독립 기록한다.
요청 전 원본 snapshot 및 actor/결정 연결을 trace에 보존하고 실제 전송 문자열·hash·버전을 기록한다.
뷰어와 검토는 실제 B2 전달 표현과 검증용 원본을 구분한다. B2 변환기/설명서 동결, 기존 기본값 불변이다.
실행 한도·실패·중단·코드검증/생략 조건은 EX-038 사전 protocol을 따른다.

<a id="c-037-effect-reference"></a>

<a id="c-037--새-배틀선봉-효과-사전-전송"></a>
## C-037 — 새 배틀·선봉 효과 사전 전송

D-057의 새 버전은 C-030/031/033의 과거 동결 버전을 보존한 별도 선택이다.
effect_reference의 items/abilities/moves는 정규화 ID → name/desc이며 고정 Gen9 Dex 원문이다.
전송되는 자기 정보·공개 관측·기존 가설·계산 시나리오·이력에 등장한 항목만 요청별로 수록한다.
선봉은 C-033의 공개 cutoff를 유지하고 상대 종족으로 비공개 항목을 추정하지 않는다.
상태 sentinel은 제외하고 미해석 실제 ID/desc 누락은 경로·ID가 있는 input_contract 오류로 전송을 막는다.
원본·선택 버전으로 재생성한 system/user/identity와 실제 전송 문자열이 일치해야 한다.
원본 입력과 실제 문자열·사전/프롬프트/전달 버전은 준비·trace·viewer에 연결한다.
효과 설명은 일반 규칙이며 보유·발동·성공의 증거가 아니다. 계산에 반영된 효과를 재적용하지 않는다.
새 EX 미지정 준비는 개선 버전을 명시 봉인하고 과거 실행 승인·예산을 상속하지 않는다.

<a id="c-043-official-observation"></a>

<a id="c-043--새-bb2-공식-관측-경계"></a>
## C-043 — 새 B/B2 공식 관측 경계

D-066/EP-056에서 observation_backend를 official-client-v1 / legacy-poke-env로 분리한다.
필드 부재는 과거 legacy 의미다. EP-056 필수 검증 후 새 B/B2 준비 기본값은 official-client-v1이며 빌드 identity와 v1.4.0/B2 b2-official-v1을 명시적으로 봉인한다. 명시적 legacy와 과거 EX 지정은 기존 버전을 유지한다.
공식 commit f2faebd6892b314d785a0038f77309afed36970c·의존성·공개 Dex·빌드 해시를 검증한다.
actor 수신 원문만 battle별 순서대로 결정 직전 행까지 반영한다. turn/decision/rqid/event/행과
공식 상태→정규화→계산→실제 문자열을 연결한다. 자기 정확값은 같은 request/자기 제출 세트,
상대 초기 표시값·미확인은 사실로 취급하지 않으며 prior/종 추론과 분리한다.
시작/소모/특성 활성·억제/지연 이력은 같은 원문에서 근거를 명시해 보완하고 legacy 상태를 병합하지 않는다.
효과 값·중첩·기간을 보존하며 계산 의미를 표현할 수 없는 상태는 명시적으로 거부한다.
request 슬롯·PP·제한·강제 교체·테라 조건과 공식 choice 검증에서 실제 제출까지 같은 슬롯을 쓴다.
Node 오류/timeout·필수 정보 누락·경계/해시 불일치 시 입력을 중단하고 자동 대체하지 않는다.
D-068/EP-058에서 정상 타이머 양보는 실패로 판정하지 않고 queue 종료 통지까지 기다린다.
자기 request 정규화와 마지막 행 snapshot은 앞선 공개 로그 종료 뒤에 수행한다. Node 명령은
직렬 처리하며 비동기 예외/기한 초과에는 부분 상태를 폐기한다. Python 동기 API·요청 전체30초
한도와 관측 schema/build identity는 유지하고 연결 source 해시를 별도 봉인한다.
upstream/Abyssal/C와 과거 설정/봉인/선봉 정책은 유지한다. 관측 소스와 계산 의미 버전은 독립이다.

<a id="d-083--ex-053-v3-일정-실행"></a>
## D-083 / EX-053 v3 일정 실행

명시 --experiment EX-053은 EX-052 봉인 manifest의 일정·팀·모델 설정을 직접 검증한다.
EX-053 receipt는 실험/입력/프롬프트·사전 identity·소스·공식 빌드·팀·일정·설정을 결합한다.
고정 ex053-live에 최초1회만 진입하며 과거 receipt/출력은 허용하지 않는다.
C-045 v3와 C-046을 유지한다. 조건·예산·중단 원문은 EX-053이며 과거 버전 감사는 보존한다.

<a id="d-085-ex-054-실행-경계"></a>
## D-085 EX-054 실행 경계

명시 EX-054는 EX-053 봉인 manifest의 일정/팀/모델/처치를 확인하고 EX-052와 대조한다.
새 receipt는 EX-054 identity와 D-084 재시도3회·1/2/4초 대기를 결합한다. 고정 ex054-live에
최초1회만 진입하고 과거 receipt·출력으로는 진입하지 않는다. 전체 누적 물리 시도·시계·실패를 보존하며
시도별 원문·회복/소진 분모와 v2 비교를 감사한다. 조건·예산·중단 원문은 EX-054다.

<a id="d-088-ex-056-직접-본실험"></a>
## D-088 EX-056 직접 본실험

EX-056만 사전 검증 receipt 없이 승인/생략/실행 identity 기록으로 직접 진입한다. source/빌드/팀/일정/prompt/모델/재시도 정책을 기록하며 미실행 검사를 통과로 표시하지 않는다. 출력 중복·설정 일치·입력/합법성·원장/기한/취소·경기별 감사는 유지한다. 첫4 특별점검0, 고정 ex056-live, jev-provider-retry-v2(10/30/60초). 과거 진입 계약은 불변이다.

<a id="d-089-ex-057-모델-고정-본실험"></a>
## D-089 EX-057 모델 고정 본실험

EX-057은 EX-056와 같은 직접 진입 기록을 사용하되 요청 모델은 jev-1.13.0으로 검증한다. endpoint·일정·팀·처치는 EX-056 봉인과 일치해야 한다. 고정 ex057-live와 ep081에 새 identity를 보존한다. 기존 모델 동일성 검사는 과거 경로에 유지하며 EX-057 비교만 alias에서 고정 ID로의 승인된 차이를 허용한다.

<a id="d-092--별도-jev-오프라인-입력"></a>
## D-092 — 별도 JEV 오프라인 입력

[D-092](decisions/D-092-jev-offline-input.md)의 `jev-offline-v1`은 C-045의 운영 v3를 변경하지 않는다.
`diagnostics/jev_offline.py`에서 같은 공식 actor/cutoff와 합법 후보/명령을 사용한다. 자기 출전 기술은
`current_move_slots`에 기본 메타데이터·일반 효과·피해량·PP/대상/제한을 통합하고 후보는 슬롯 참조로 연결한다.
슬롯이 없는 자기 포켓몬은 `known_move_set`을 사용하며 `moves`는 상대 공개 기술에 한정한다.
효과는 객체의 `general_effect`로 옮기고 별도 효과 사전은 모델에 보내지 않는다. 상태와 일반 규칙은 구분한다.

내부 ident·initial_state_source·전체 prefix/원래 관측은 감사 자료로 보존하고 모델에서 제외한다.
volatile의 다른 포켓몬 참조는 진영/팀 슬롯으로 바꿔 관계를 유지한다. 상대 HP는 hp_percent와 rounded
정밀도로 제공하며 unknown/확인된 부재/해당 없음을 구별한다. 현재 방어 타입·테라 사용 여부와
공격 STAB용 pre-Tera 타입·설정 테라 타입을 구분하고 전체18타입 상성 행렬을 제공한다.

자기 벤치는 기본 상세다. 비교 옵션은 일반 턴에서만 known_move_set·stats를 생략한다.
선봉/강제교체는 상세를 유지한다. 상대 벤치는 종별 조건부 역할·공개 HP/상태 중심으로 요약한다.
역할 DB의 가능성을 실제 미공개 세트로 확정하지 않으며 역할 prior를 스피드 확률로 전용하지 않는다.

피해량은 EP-082의 고정 추천 세트·공개 이력 필터·계산기를 재사용하되 현재 요청 기술과 상대 공개
기술만 전달한다. 대상/최대 HP 대비 단위/테라 분기/조건을 표시하고 null·사유와 계산된0을 구분한다.
스피드는 같은 계산기의 현재 유효 스피드 지원 범위와 `by_set`의 자기 기준 빠름/동속/느림을
제공한다. [D-093](decisions/D-093-speed-uncertainty.md)에 따라 확률 필드를 제거하고
`speed_certainty`로 세트에 따른 차이·세트 내부 불확실성·유한 지원 내 일치를 구별한다.
관측과 일치하는 후보가 없거나 일부라도 계산 불가하면 unavailable로 두고 우위를 확정하지 않는다.
선봉/강제교체는 not_applicable이다. 스피드 우위와 실제 선공을 동일시하지 않는다.

최근3완료턴 로그는 고정 공식 BattleTextParser와 고정 서버 텍스트로 변환한다. 버전 차이의
자리표시자·능력치 이름 테이블만 호환하며 원문 문구/공식 파서는 수정하지 않는다. HP/정밀도·대상·
능력 변화량을 보충하고 미지원 이벤트는 원문을 보인다. 전체 프로토콜과 변환 감사는 내부에 보존한다.
API·새 배틀·운영 전환은 이 계약의 범위가 아니다. 검증 원문은 EP-093이다.

<a id="d-094--ex-058-개선-입력-실행-경계"></a>
## D-094 — EX-058 개선 입력 실행 경계

실험 전용 jev-choice-v4는 EP-093 생성 로직/지시문·상세 자기 벤치를 그대로 사용하고
모델 payload의 버전 표기만 변경한다. 자기 제출 팀/공개 cutoff만 계산에 사용한다.
세션 계산기·고정 자료를 재사용하고 비동기 수신을 막지 않으며 감사 자료를 payload 밖에 보존한다.
기존 null+사유는 유지하되 생성 예외/무결성 오류에 fallback0. 기본 v3·과거 재현은 불변.
[EX-058](experiments/EX-058-jev-improved32.md)의4사례·1요청 gate, 사전 요청에서 시작하는
공유6시간 시계·경기별 감사·실패 격리/전체 기술 중단을 적용한다.

<a id="d-095--ex-059-자기-벤치-축약-실행-경계"></a>
## D-095 — EX-059 자기 벤치 축약 실행 경계

실험 전용 jev-choice-v5는 EP-093 compact=True를 사용한다. 일반 턴 비출전 자기 포켓몬의
known_move_set·stats만 생략하며 선봉/강제교체·출전 자기 상세·그 외 처치는 v4와 유지한다.
v5/compact 여부를 실행기·감사기·비교 및 동결 identity에 명시한다. 기본 v3·과거 v4 재현은 유지한다.
D-094의 비동기 계산·관측 경계·감사 분리·실패 폐쇄와 [EX-059](experiments/EX-059-jev-compact32.md)의
4사례·1요청 gate 및 최초 예약부터 공유6시간을 적용한다.

<a id="c-081-candidate-matchup"></a>

<a id="c-081--후보별-현재-대면-요약"></a>
## C-081 — 후보별 현재 대면 요약

D-167의 candidate-matchup-v1은 v6 payload의 기술후보에 current_matchup만 추가하는 독립overlay다.
원state.version은 기반schema인 jev-choice-v6를 유지하며 overlay버전은 각요약과별도provenance에 표시한다.
원state/지시문/후보의 기존필드·ID·순서·명령은 불변이며 요약제거로 원payload가 정확히 복원돼야 한다.
현재 대상/타입배율·공개확인한면역/차단/반사·조건부피해를 분리하고 상대의 교체/테라/상태변화를 예측하지 않는다.
자기Tera 후보는 자기Tera 피해branch/기술타입을 구분한다. 기존 상대Tera 가정은 원v6에만 유지한다.
계산피해0은 면역원인의 증거로 역추정하지 않는다. 상태기술에는 일반타입배율을 무조건 적용하지 않는다.
숨은도구/특성·억제/해제·동적타입/미지원예외가 판정을 바꿀 수 있으면unknown으로 표시한다.
후보 삭제/재정렬·원선택 강제교정·새확률을 만들지 않는다. 소스/상태와 원본/보강본을 별도 식별한다.

<a id="c-082--요약-프로필-배틀감사-연결"></a>
## C-082 — 요약 프로필 배틀·감사 연결

D-168/EX112는 C081 overlay와 C079/통신 C080을 결합한다. manifest의 기반 schema와 candidate_matchup_profile을 분리하고 명시 프로필로 입력생성·자료정체성·공식관측 재생성 감사를 선택한다. 실제 HTTP 요청·원선택·전송명령을 대조한다. 기존 실험의 기본 입력/감사를 변경하지 않는다.

## candidate-action-v1 실행 경계

D-179/EX-115에서만 jev-choice-v7을 사용한다. 기존 계산·관측·후보/명령은 보존하고 기술·모든 피해 분기를 후보로 옮긴다. 공통 반복 문구는 영어 지시문에 보존한다. 실행 불가능 응답만 동일 본문 최대3회(통신 재시도 별도)이며 모든 원문/사용량을 보존한다. 상세 진입·감사·복구 규칙은 EX-115를 따른다. 기존 프로필 기본값 불변.

D-182/EX-117은 D-181 개정 지시문으로 같은 candidate-action-v1을 별도 실행한다.
새 prompt_sha256·EX ID·출력 및 동결을 사용하며 상세 진입·보존·복구는 EX117을 따른다.
