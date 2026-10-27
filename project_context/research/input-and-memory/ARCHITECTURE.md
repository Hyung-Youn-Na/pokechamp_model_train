# 입력·관측·메모리 — 구성 설명

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="공개-정보-v6와-jev-공통-평가"></a>
## 공개 정보 v6와 JEV 공통 평가

<a id="보존된-v6-평가-경로"></a>
### 보존된 v6 평가 경로

`integration/pokechamp/jev_v6_no_damage.py`는 D-137/EX-090의 별도 입력 프로필이다.
공통 `prepare_matchup`에서 관측 정규화·추천 세트·현재 기술을 준비한 뒤 피해 변환을 건너뛰고
스피드 비교만 실행한다. `SpeedOnlyEngine`은 speed 시나리오만 통과시키며 감사에 비활성화와
실제 스피드 호출 수를 남긴다. 피해 범위/사유 필드와 해당 prompt 설명만 생략하고 기존 기본값은 유지한다.
공통 실행기는 EX-090에 이 프로필을 명시 연결하며 EX-089 결과를 기준선으로 단독 평가한다.
신규 뷰어에는 피해 예측 비활성화·스피드 비교 유지를 표시하며 기존 Damage-calc 판본은 보존한다.

`integration/pokechamp/jev_v6.py`는 현재 공식 관측과 같은 행 cutoff의 전체 공개prefix에서
`diagnostics/public_facts_v6.py`로 공개 사실을 재구성한다. 현재 도구/특성·공개 기본 특성·
일반 기술과 일시/지속 복사를 구분하고 상대 벤치에 공개 정보를 유지한다. 같은 facts를
상태 투영·현재 대면 정규화·추천 세트 필터에 전달하며 계산식/자료·현재 출전끼리의 범위는 유지한다.
원관측·공개 근거·보완 이유는 모델 밖 감사에 저장한다. 기존 v4/v5는 선택 인자를 쓰지 않는 기본 경로다.

`integration/jev_eval/`과 `scripts/jev-eval`은 실험ID에27B/9B·v6·출력·4GPU 배치를 고정 연결한다.
기존 모델·환경·formatter·단일 Choice 전송과 원장을 재사용한다. CPU 재생성/토큰화 뒤
본서버를 한 번 적재해 최대8요청을 검증하고 같은 서버로 각32경기를 새로 수집한다.
공유 디스크 범위에 두 모델/공유환경/기존 참조/두 신규 출력·뷰어·임시 복사를 포함한다.
수집기는 경기별 한 번 감사하고 최종 산술/완전성을 검사하며 기존 출력 재개/덮어쓰기를 거부한다.

새 뷰어는 해당 모델username의 수신 protocol만 턴0/각턴으로 나누고 원래sequence/line_index를
유지한다. 고정BattleTextParser로 내보낼 때 변환하며 해석 불가 공개 행은 원문을 유지한다.
저장 입력의 HP/공개정보 요약, 같은턴 다중결정·결정없는턴, 결정전 정확cutoff·결정후 결과 구분과
원문 복사/다운로드를 로컬HTML/JS로 제공한다. EX-083/085 뷰어는 변경하지 않는다.
EP-142의 `jev-eval reexport`는 완료된 EX-088/089의 원자료·기존 뷰어 봉인을 검증하고
`ex088-damage-v1`·`ex089-damage-v1`에 Damage-calc 표시 판본을 만든다.
`damage_data.py`가 입력 이벤트의 감사 경로/해시·입력 identity로 저장 계산을 연결하고,
`damage_viewer.js`가 결정별 로컬 스크립트를 지연 적재한다. 모델 입력 요약과 원래 시나리오
조건/결과를 분리하며 필터·50행 페이지·상세·JSON 내보내기를 제공한다.
기존 요청/응답/선택·턴 로그를 보존하고 계산기나 모델을 실행하지 않는다. 출처에는 수집 당시
소스와 새 renderer 복사본을 별도로 기록하며 원 판본·봉인은 유지한다.
규범·실행조건은 [C-067](CONTRACTS.md#c-067-jev-public-memory-v6)과 EX-088/089를 따른다.
공유 결함으로 중단한 EX-086/087의 당시 조건·자료·봉인은 보존한다.

<a id="battle-input"></a>

<a id="관측계산행동-설명서"></a>
## 관측·계산·행동 설명서

`integration/pokechamp/improved_io/`는 관측·고정 prior·계산기·고정 행동 출력 및 배틀 내 요약을 제공한다.
`posthoc.py`만 검토용 상대 정답을 읽는다. 전체 공개 prefix의 상태 복원과 최근10결정 전송 window를
구별한다. 실제 입력·요약 lifecycle은 [입력·요약 구조](../../../docs/pokechamp-input-summary.md),
prompt 원문은 [부록](../../../docs/pokechamp-prompt-originals.md)에 있다.

`protocol.py`가 원본 행 순서·HP·필드 시점·Future Sight slot을 해석한다. `state.py`는
raw parser_effects와 현재 effects를 구분하며 소비 item을 prior로 되살리지 않는다.
`public_revelations`는 공개 특성 holder, 자기 귀속 item 발동·획득·제거를 시간순 반영한다.
Drought는 명시적인 `[of]` holder를 사용하며 upkeep/holder 없는 날씨행으로 특성을 추론하지 않는다.
`oracle.py`는 원문에서 공개 특성·item·정답을 별도로 확인한다. weather 숫자 의미는
last_weather_protocol_turn이며 실제 시작 턴은 protocol event annotation에서 확인한다.
`calculations.py`는 pinned getHealth의99/100 예외와 float 순서를 따른다.

[D-034](decisions/D-034-calculator-entry-calcfix32.md)의 worker는 명시적 무특성/관측 완료 등장 특성에서
인스턴스 ability와 인스턴스 species 기본 특성 fallback을 함께 비워 clone 후 복구를 막는다.
공유 종 데이터와 설치 라이브러리는 변경하지 않는다.
[D-035](decisions/D-035-calculator-input-audit.md)의 `lifecycle.py`는 최근 창과 별도로 전체 공개
prefix에서 Pokémon별 소비·억제·QP 원천·팀 기절 이력을 재구성한다. `state.py`가 v2 상태를
정규화하고 `calculations.py`가 현재/선택 교대/선택 테라 시나리오를 만든다. worker의
`scenarios-v2.cjs`가 진입 hazard·필드·소모 아이템을 투영하고 `state-patch.cjs`는 검증된
mechanics-v2 overlay를 메모리에서만 컴파일한다. 설치 라이브러리·공유 종 데이터는 보존한다.

`gate.py`와 backend는 state/request/bundle identity·내용·coverage·최신 원문 request·필수 이력을
검증하며 새 `battle-v1.2.0` 설명서는 모든 추가 필드를 포함한다. 미래 전체 턴·실행 확률은
계산하지 않으며 지연 공격·미공개 교체·지원하지 않는 이력 기술은 명시적 경계를 유지한다.
EX-029의 당시 source와 중단 결과는 보존하며 교정으로 과거 실험을 유효화하지 않는다.
[전체 조사·수정 보고서](../../exec-plans/evidence/ep023/report.md)와
[별도 영향 분석](../../exec-plans/evidence/ep023/impact.md)이 현재 검증 범위를 정의한다.

기술명 생성은 [D-037](decisions/D-037-calculator-move-names.md)에 따라 pinned Gen9 canonical
이름을 사용하며 Weather Ball 및 동일 원인 기술을 처리한다. [EP-025 검증](../../exec-plans/evidence/ep025/report.md).
Protect 만료는 raw 효과를 보존하면서 현재 효과만 교정한다. [EP-031 검증](../../exec-plans/evidence/ep031/protect-expiry-v1/report.md).
Court Change 실행 알림도 전체 공개 prefix로 확인한 보유자의 계산용 효과에서만 제거한다.
공개 `-swapsideconditions`는 원래 설치 기록을 유지해 해당 진영 효과만 교환한다. 공개 상태이상
행의 특성 보유자는 명시적 `[of]`로 연결하고, 상대 기절 후 effective_types는 테라 전 타입으로
돌아간다. parser 원문 표현·관측 tera_type은 보존한다. [D-062](decisions/D-062-court-change-input-audit.md).
지연 기술의 슬롯 없는 대상은 공개 switch/drag/replace/faint 근거의 유일한 슬롯으로만 복구하고
명시 슬롯을 우선한다. 근거 부족·모호함은 기존 오류를 유지하며 Doom Desire 시작 표기를 지원한다.
[EP-036 검증](../../exec-plans/evidence/ep036/report.md). 이 수정은 전수 과거 계산 재생 완료나 EX-038 유효화가 아니다.


`improved_io/battle_prompts.py`는 선택 버전의 `fields.json` 경로/자료형/의미를
일정 순서로 렌더링하고 원본 policy와 조립한다. 현재 새 B prepare는 D-066의 공식 관측 v1.4.0, 명시적 legacy는 D-057의 v1.3.0, 과거 버전 부재는
v1.0.0이며 summary 버전 선택 및 A 경로는 유지한다. `battle-prompt.json`에 전체 system·
identity·입력별 크기를 봉인하고 manifest·execution evidence·worker/actor 요청에 같은
identity를 연결한다. Backend가 실제 system/user를 대조하며 v1.1.0의 재귀 경로 검사는
원문 request JSON까지 포함한다. 15장면 외 선택적 request·지연 효과·미상 교체 분기는
fixture로 확인한다. 기존 v1.1.0/v1.2.0 설명서는 입력 해석 문서이며 사전 게임효과 지식이나 평가 정답이 아니다.
D-057의 v1.3.0은 아래 일반 게임 효과 사전을 별도로 추가한다.
구현·로컬 검증 결과는 [EP-019](plans/EP-019-battle-field-guide.md),
자세한 의미 근거는 [필드 설명서](../../../docs/pokechamp-battle-field-guide.md)를 따른다.

새 관측 준비 기본값은 [observation](../../../integration/pokechamp/observation/__init__.py)의
`PREPARATION_DEFAULT`와 B/B2 prepare의 명시적 버전 봉인에서 확인한다. 범용 prompt 함수의
`DEFAULT_VERSION=v1.3.0`은 legacy 호환용이며 새 공식 준비 선택과 구분한다. D-031/EP-019의 v1.1.0은 당시 구현 범위이며 과거 명시 버전은 그대로 검증한다.

<a id="전달-표현과-b2-전송"></a>
## 전달 표현과 B2 전송

`integration/pokechamp/improved_io/delivery/`는 현재 관측 생성과 live FixedBackend 사이에
자동 삽입되지 않는 별도 오프라인 변환/검증 경로다. 원본 전체를 기존 v2 schema·memory·
patch·state/request/bundle hash로 검증한 후 B0/B1/B2/B3를 선택한다.
원본 B0 prompt, 제외 목록, 공통 의미 설명서, 계산 scenario join·반복문장/배열 공유,
최근10결정 request 변경분 및 독립 역변환이 분리되어 있다.
`Delivery`는 system/user 문자열과 별도 원본 연결 로그를 제공한다. `capture_request`가
원본을 다시 검증하고 재생성 결과와 완전 일치를 확인해 최종 messages를 네트워크 없이 포착한다.
`audit-ex037`는 원본 bundle 봉인·actor/decision/event·최근10결정 window까지 대조한다.
후보 버전과 calculator-input-v2 의미 버전은 독립적이며 운영 selector·계산식·출력복구는 불변이다.
[설명·CLI·필드 매핑](../../../docs/pokechamp-b-prompt-optimization.md).

D-047/C-031의 opt-in 경로는 FixedPlayer의 검증된 전체 입력에서 EP-034 B2를 생성한다.
FixedBackend는 원본·B2·실제 문자열 일치를 검사하고 요청 전 `input_snapshot`을 필수 보존한다.
provider에는 B2 system/user를 보내며 원본은 출력 검증·복구에 사용한다. 요청 metadata의
`delivery_identity`와 `input_snapshot_event_seq`가 원본 및 실제 전달 trace를 연결한다.
뷰어/검토 inventory는 검증용 원본과 실제 전달 입력을 구분한다. 기존 정책의 전체 입력 전송은 유지한다.

<a id="요청별-상세-효과-사전"></a>
## 요청별 상세 효과 사전

[D-057](decisions/D-057-effect-reference.md)/[C-037](CONTRACTS.md#c-037-effect-reference)의
`effects/`는 pinned Showdown Gen9 Dex `desc` 자산과 B/B2·선봉 모델용 projection을 제공한다.
원본 관측·가설·계산은 유지하고 실제 전송 필드/최근 이력에서 등장한 item/ability/move를
요청별 `effect_reference`에 한 번 수록한다. 선봉의 상대 공개 종족으로 비공개 세트를 조회하지 않는다.
새 schema는 공통 타입을 한 번 렌더링하고 B2의 scenarios/result/shared_text 및 선봉 하위 필드까지 검사한다.
원본+선택 버전으로 전송 직전 재생성하며 일반 B와 선봉에도 input_snapshot/hash/identity를 연결한다.
viewer는 실제 문자열·프롬프트/사전 identity·원본 snapshot을 표시한다. 개별 gate도 원본을 전송 전에 파일로 봉인한다.

EX 미지정 새 선봉 준비는 `preparation_version=official-observation-v1`, 배틀 v1.4.0·B2 b2-official-v1·
선봉 v1.2.0의 독립 구성요소·사전 gen9-effects-v1을 봉인한다. 선봉 구성요소의 현재 선택 경계는
[C-040](../lead-policy/CONTRACTS.md#c-040-lead-components)을 따른다. 이전 정책의 실행기/RNG/출력복구는 재사용하되
새 프롬프트 선택이 명시적으로 우선한다. 등록 EX·유료 예산은 없고 과거 실행 등록으로 전환할 수 없다.
과거 EX 지정·봉인은 기존 prompt/정책 hash를 유지한다. [자산·API](../../../integration/pokechamp/effects/README.md).

<a id="요약독립-진단-경로"></a>
## 요약·독립 진단 경로

`summary_diagnostics/`는 운영 improved_io와 분리된 prepare/run/report 경로다. EX-020 archive의
H0 복원과 H1–H3 변환, 독립 truth, 호출별 process/backend, 영속 clock·intent·응답 선봉인을 사용한다.
입력/평가 실패 halt에서는 효과 추정을 차단하고 비용·실패 근거·미완료 분모를 보존한다.
`memory.summary_context/summary_window`는 live actor와 Cloud에 같은 구간 의미를 제공하며
원문·주석은 현재 window만 전송한다. `prompt_versions.py`가 원본/후속 버전의 byte·hash를 연결한다.
`review_gate.py`는 응답 검토 후에만 같은 연쇄의 후속 입력을 구성하고 기존 halt·시계·receipt를 보존한다.
`maximum.py`의 고정 이전메모리는 이번 응답을 다른 호출의 입력으로 재사용하지 않는다.
`compat.py`는 원본 SDK를 보존하며 max 직렬화와 HTTP 본문 포착을 담당한다.

| 특정 진단·운영 경로 | 구현·검증 한계의 원문 |
|---|---|
| D-019/D-022 A/B/C 단계 receipt·offline/Cloud gate | [EP-011](plans/EP-011-improved-io.md), [EX-020](experiments/EX-020-resume-io.md) |
| H0–H3 독립 요약 진단, weather 입력/기준 오류 | [EX-021](experiments/EX-021-summary-harness-diagnostics.md) |
| 상태 의미·low/high 및 공개 특성 입력 교정 | [EX-022](experiments/EX-022-state-summary-thinking.md) |
| 후속 window·공개 item 입력 교정 | [EX-023](experiments/EX-023-continue-io.md) |
| 요약 prompt 버전별 검토 연쇄 | [EX-024](experiments/EX-024-low-summary-prompt-reexperiment.md) |
| low/max 고정 메모리, 실제 전송 입력의 필수 사실 도달성 미보장 | [EX-025](experiments/EX-025-summary-max-diagnostic.md) |

과거 입력·기준 실패/무효/중단 자료는 현재 source와 구별한다. 수정된 의미 검사로 과거 입력을
정상으로 인정하거나 이미 실패한 gate를 통과로 바꾸지 않는다.

<a id="실험-정책별-실행-연결"></a>
## 실험 정책별 실행 연결

`battle_only.py`는 요약 없는 A/B, `battle_only_budget.py`는 원자적 HTTP 전 예약과 최초 시계를
관리한다. `battle_only_recovery.py`는 기존 halt를 보존한 평가 교정과 영향 대응 재수집 경로를 구분한다.
지원·허용 범위는 선택한 정책과 기존 receipt에 한정되며 공통 예산 초기화·중복 제출을 거부한다.
`experiment_policy.py`는 정책 정의/hash를 manifest·execution·actor·receipt·원장·보고서에 연결한다.
정책 부재와 명시 정책의 gate/상한을 혼용하지 않으며 C-029는 새 execution 동시성에만 우선한다.
`direct32.py`는 별도 정책의 준비 봉인에서 본32판으로 연결한다. FixedBackend는 원출력 계약 판정과
행동 복구 결과를 분리하고 실제 send trace에 출처를 기록한다. `observability/issues.py`는 source 밖
annotation을 검증해 viewer에 연결한다. 새 기본 IO 설명 검토 제외는 [C-032](../../CONTRACTS.md#c-032-io-explanation-review)를 따른다.

| 정책별 연결 | 원문·실행 당시 한계 |
|---|---|
| D-030 요약 없는 A/B 및 평가 e1 | [EX-026](experiments/EX-026-io-battle-only.md) |
| D-032 명시 null 상한·기술/설명 판정 분리 | [EX-027](experiments/EX-027-battle-guide-live.md) |
| D-033 direct32와 출력 복구 | [EP-021](plans/EP-021-battle-guide-direct32.md) |
| D-036 inputfix32, v2/실제 요청 identity | [EP-024](plans/EP-024-calculator-inputfix32.md) |
| D-038 movefix32, 기준 source 봉인과 변경분 연결 | [EP-026](plans/EP-026-battle-guide-movefix32.md) |
| D-039 외부 환경 보고 후 새 identity 반복, 각 실험 자체 사용량만 합산 | [EP-027](plans/EP-027-external-memory-repeat32.md) |

`ab_head_to_head.py`가32행/16대응쌍·정책·팀/source를 봉인하고 EX-035의
`a_diagnostic.run/reserve/collection_deadline/inspect_batch`를 명시적 protocol 인자로 재사용한다.
기존 A-only 기본 경로의 정책 identity와 A/B 대 기준봇 경로는 유지한다.
`benchmark.actor_condition`은 새 `actor_conditions`에서 진영별 A/B를 읽고, 필드가 없으면
기존 경기 단위 `condition_id`를 사용한다. 각 actor는 별도 process·관측·계산기·bundle을 쓴다.
A는 upstream IO, B는 기존 battle-v1.2.0/calculator-input-v2/mechanics-v2와 출력복구다.
`POKECHAMP_AB_HEAD_TO_HEAD_ROOT`가 양쪽 Cloud 요청을 같은 원자 예약 원장에 연결한다.
`ab_head_to_head_report.py`는 조건/진영별 결과와 양쪽 모든 결정의 실제입력/원응답/선택/전송을
기록하고16대응쌍의 B점수 및 불완전쌍 누락을 보고한다. Method `io`로 조건을 합산하지 않는다.

<a id="플레이어별-관측-tracker-진단"></a>
## 플레이어별 관측 tracker 진단

`diagnostics/observation_run.py`는 기존 worker/recorder/격리 서버로 Abyssal 관측을 수집하고
메시지 순회의 결정 직전 행 위치를 별도로 기록한다. `observation_compare.py`는 각 actor의 동일
prefix를 현재 parser와 고정 공식 headless client에 재생하고 B2 관측 투영·원문·최초 차이를 연결한다.
`observation_client.cjs`는 기존 고정 서버의 공개 Dex와 공식 client TS를 별도 build로 사용하며 서버
자동 갱신이나 운영 입력 교체를 수행하지 않는다. 실제 과거 B2 전송 관측도 대조하지만 계산·전송·
행동 선택은 진단 범위 밖이다. [명령·출력 의미](../../../integration/pokechamp/diagnostics/observation-comparison.md)와
[EP-055 결과·지원 한계](../../exec-plans/evidence/ep055/report.md)를 참조한다.


<a id="공식-관측의-bb2-운영-경로"></a>
## 공식 관측의 B/B2 운영 경로

D-066/C-043의 `observation/`은 EP-055 어댑터에서 분리한 운영 모듈이다. 고정 client TS와
공개 Dex 빌드·설치 의존성·서버 dist를 검증한 후 actor별 Node를 만들고 battle별 증분 상태를 둔다.
`observability.player`가 원문을 기록한 뒤 기존 parser의 실제 행 순회에 cursor를 연결한다.
`FixedPlayer`는 해당 event/행 경계에서만 공식 상태를 얻고 동일 관측으로 prior·계산·모델 입력을 만든다.
자기 request/세트와 상대 공개 상태·종 추론·미확인을 구분하며 소비/기간/억제/지연 이력만 같은
원문에서 출처를 명시하여 보완한다. legacy Battle 객체 상태를 병합하지 않는다.

공식 choice와 요청 조건으로 검증한 후보는 숫자 슬롯 그대로 제출한다. 선봉 정책과 RNG는 유지한다.
`observation_snapshot`에 원문 경계·공식 상태·계산 전 정규화를 남기고 `input_snapshot`·
`llm_call`·`wire_action`에서 계산·실제 system/user·제출을 연결한다. 최근10결정 창의 첫 프레임을
자르면 `line_offset`이 원래 행 번호를 보존한다. 증분/전체 재생은 별도 검증 경로에서 대조한다.
Node 오류·기한 초과·경계/빌드 불일치·미지원 상태는 입력 중단이며 자동 legacy 대체는 없다.

새 B/B2 prepare는 `official-client-v1`과 빌드 identity를 명시적으로 봉인한다. 필드 부재는
legacy, 과거 EX 지정은 당시 소스이며 upstream/Abyssal/C는 전환하지 않는다. 관측·전달 버전과
계산 의미 버전은 독립이다. [운영 안내](../../../integration/pokechamp/observation/README.md)·
[EP-056 검증과 viewer](../../exec-plans/evidence/ep056/report.md).

<a id="d-088-ex-056-직접-본실험"></a>
## D-088 EX-056 직접 본실험

jev_study의 명시 EX-056은 EX-054 봉인 일정을 직접 읽고 별도 entry-record.json으로 사전 검사 생략과 실행 identity를 보존한다. 기존 receipt 경로와 구분하며 첫4 gate 없이 순차 수집·경기별 감사를 수행한다.

<a id="d-089-ex-057-모델-고정-본실험"></a>
## D-089 EX-057 모델 고정 본실험

jev_study의 EX-057은 EX-056 봉인 일정과 jev-1.13.0 설정을 결합한다. jev_comparison은 EX-057에 한해 요청 모델명 고정을 명시적으로 허용하고 전후 요청/반환 모델을 기록한다.

<a id="d-094-ex-058-개선-입력-연결"></a>
## D-094 EX-058 개선 입력 연결

별도 [D-130](../model-evaluation/decisions/D-130-jev27b-ex058-reproduction.md)의 `integration/jev27b/`는 기존
v4 입력·명령·계산기를 재사용하고 공개 JEV-27B를 loopback Choice 서버에 연결한다.
공식 bare formatter·BF16 backbone/병합 어댑터·FP32 head/보정값을 사용하며, 로딩 I/O는
호스트 상한을 위해 Transformers의 순차 safetensors pread로 처리한다. 설치 환경과 가중치
내용은 바꾸지 않는다. SQLite 요청 원장이 동일 ID/본문의 중복 추론을 막고, 실험 전용
Session은600초 통신 감지·경과시간 상한 null·경기 실패 격리·전수 감사를 제공한다.
진입 gate·자원·중단/비교 원문은 [EX-082](../model-evaluation/experiments/EX-082-jev27b-ex058-reproduction.md)다.

[D-132](../model-evaluation/decisions/D-132-jev27b-four-gpu-continuation.md)의 EX-083은 명시 `ex083` 프로필과
`jev27b continue --parent --directory`로4GPU 계승을 별도 연결한다. controller가 부모 봉인·
독립 재로딩·원591응답 재생·같은 서버 연속 메모리/일반턴 gate를 마친 뒤 collection에 진입한다.
전체 일정과 원시도 이력은 보존하며 신규 실행은 원24–32번뿐이다. 자원/배치/서빙 identity와
분모의 계약은 C-064/EX-083을 따르며 기존 EX-082 기본2GPU 경로와 자료는 유지한다.

jev_v4.Adapter는 EP-093 생성기를 그대로 호출하고 state.version만 jev-choice-v4로 바꾼다.
Session이 계산기·역할 DB·추천 세트 캐시를 소유하고 입력 생성은 asyncio.to_thread에서 처리한다.
JevPlayer는 자기 제출 팀 문자열만 전달한다. 계산/로그 감사는 input-audits의 별도 gzip 파일과
입력 이벤트의 hash로 연결한다. 감사기는 actor cutoff를 재생하고 같은 자기 팀으로 재산출한다.
실험 전용 EX-058은4사례 receipt 후1요청 probe를 수행하며 최초 wall/monotonic 시계를 본수집에
계승한다. 주 비교는 EX-057이고 기본 v3 경로·과거 실험은 유지한다.

<a id="d-095-ex-059-자기-벤치-축약-연결"></a>
## D-095 EX-059 자기 벤치 축약 연결

jev_v5는 v4의 비동기 어댑터·계산기/자료 캐시·probe를 재사용하고 compact=True와 별도 버전을
고정한다. 실행/재생 감사는 버전에 따라 상세/축약을 명시 선택하며 세션 중 처치 변경은 거부한다.
EX-059는 EX-058 봉인 일정과 팀을 연결하고 비교기는 v4/v5·축약 여부·고정 자료/지시문 일치를 검사한다.


<a id="life-orb-공개-입력-교정"></a>
### Life Orb 공개 입력 교정

[EP-123](plans/EP-123-life-orb-input.md): 공유 imitation replay/live serializer는
Life Orb의 `-damage ... [from] item: Life Orb`도 도구 공개로 기록한다. 공개 여부는 이력
window와 독립적으로 유지하고 현재 도구 값·제거·재획득은 기존 parser를 따른다.
기존 동결 실행 source와 저장 입력은 당시 형태를 보존한다.

<a id="후보별-현재-대면-요약"></a>
## 후보별 현재 대면 요약

D-167/C-081의 `integration/candidate_matchup`은 v6 payload를 복사하고 기술후보에만
current_matchup을 추가한다. pinned Showdown Dex의 공개타입/기술/특성 metadata와 현재
v6 상태·기존피해범위를 사용하며 원state/지시문/후보/명령은 유지한다.
CLI는 저장JSON→v6보강본 또는 OpenAI 요청을 생성하고 source/rules/output provenance를 기록한다.
옵트인 Adapter는 기존v6 생성기를 합성하며 기존runtime 기본값/진행중실험은 변경하지 않는다.
지원밖/미상은unknown이다. EP182는 오프라인 검증이며 후속 모델 선택/배틀 비교는 EX112에서 별도로 수행했다. [사용법](../../../integration/candidate_matchup/README.md).

<a id="ex112-후보별-요약-배틀-연결"></a>
## EX112 후보별 요약 배틀 연결

`integration/openai_decisions_matchup_battle`은 기존 OpenAI 배틀 lifecycle·RetrySession과
명시 candidate_matchup.adapter를 연결한다. study의 source/data 검증과 경기별 audit는 manifest의
candidate_matchup_profile에 따라 생성기를 고른다. 기반 schema는 jev-choice-v6다.
분석기는 원본 복원 후 같은 동결 요약 판정기로 EX110/112를 평가하고 미래 로그는 사후 사례 검토에만 쓴다.
뷰어는 실제 요청·요약 포함 입력·요약 제거 원본·후보별 요약·선택·공개로그를 별도 탭으로 제공한다.

## 후보 중심 v7

D-179/EX-115는 `integration/candidate_action`의 옵트인 adapter로 v6+matchup을 변환한다.
기술을 후보로 이동하고 공통 상태·비후보 기술·모든 피해 분기를 유지한다. 실제 요청 변환·
source/data identity·공식 재생성 감사는 `input_profile=candidate-action-v1`로 분기한다.
RecoverySession은 통신과 응답 시도를 분리하고 모든 HTTP usage를 집계한다.
[입력 구조·예시](input-structures/EX115_INPUT_STRUCTURE.md)와 [실행 안내](../../../integration/candidate_action/README.md)를 참조한다.
