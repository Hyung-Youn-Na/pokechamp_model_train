# EX-034 — baseline 고정과 실행기 지원 조사

2026-09-11 현재 source를 읽고 EX-033 실제 A 요청과 봉인을 대조했다. 이번 변경은 문서·팀 data·
로컬 검증 evidence에 한정하며 공개 API/CLI·실행 코드·prompt·submodule은 변경하지 않았다.
`schedule.json`은 **연구 설계 data**다. 현 CLI에서 읽을 수 있는 실행 manifest라고 표시하지 않는다.

## 원본 A 고정값

| 항목 | EX-033에서 보존할 값/경로 |
|---|---|
| PokéChamp | `0f84c460319ebe733f8c3028e58a2a5452c60d85` |
| Showdown | `e64915c0eab066db1d3e732b1280386468dd7415`, `gen9ou`, timer off |
| A 정책 | method `io`, `action_policy=upstream`, 원본 출력 파싱/재질의/fallback |
| 입력 생성 | 원본 `state_translate2`, `LLMPlayer`의 기존 분기·후보 전달; A에 B의 교정 관측·prior·계산기·설명서 입력 없음 |
| 모델/endpoint | `glm-5.3-flash`, `https://ollama.com` |
| 생성 옵션 | thinking `low`, temperature0, model seed100, 출력131072, `num_ctx` 생략/provider 기본 context |
| 역할 | A 행동 모델1개, 상대는 기존 `AbyssalPlayer`/`OneStepPlayer` |
| 추가 기능 | 별도 LLM 요약·통합·외부 메모리 주입·새 전략 해설0; 원본의 최근16턴 `get_turn_summary` 문자열 조립은 유지 |
| 운영 | HTTP timeout300초, 경기 watchdog1200초, 배틀/계정/모델 상한10, provider retry0 |
| 원본 IO 루프 | 최대10회 파싱 시도; EX-033 A457개 실제 호출은 모두 attempt1. Provider retry0과 구분 |
| runtime/계산 환경 | EX-033에 봉인된 `mechanics-v2` 등 기존 runtime identity 유지; 수정된 B 입력을 A로 옮기지 않음 |

전체 [EX-033 source173개 봉인](../../exec-plans/evidence/ep027/source-config-final.json)을
현재 source와 대조했고, [A457 실제 요청](../../exec-plans/evidence/ep028/a-usage.json)의 옵션이
위 값과 일치한다. A의 동적 system prompt는 실제16개 hash가 관측됐으므로 하나의 고정 문자열로
대체하지 않는다. 기존 생성 코드와 분기·adapter를 고정하고 새 팀의 상태가 반영되는 내용을
그대로 기록한다. User prompt에 덧붙이는 upstream JSON 시작 문자열도 기존 adapter 동작이다.

명시적 source 근거는 [benchmark.py](../../../integration/pokechamp/benchmark.py)의 actor 구성,
[benchmark_player.py](../../../integration/pokechamp/benchmark_player.py)의 원본 IO 계측,
[cloud.py](../../../integration/pokechamp/cloud.py)의 요청 옵션과 upstream 추출,
[원본 prompts.py](../../../pokechamp/pokechamp/prompts.py)의 `state_translate2`다.
기존 `CORE_REPEAT_CONFIG`의 reference 값에 `retry_transient=1`이 남아 있어도 실제 병렬 execution의
retry0 검증과 구분한다. Reference JSON을 복사하여64경기 운영 정책으로 사용하지 않는다.

## 지원 여부와 필요한 변경

| 경계 | 현재 확인한 동작 | 이 설계를 실행하려면 필요한 변경 |
|---|---|---|
| 외부 팀 읽기 | [cli._team_path](../../../integration/pokechamp/cli.py)는 고정 submodule의 `gen9ou{id}.txt`; [benchmark.plan](../../../integration/pokechamp/benchmark.py)은1–13만 등록. Actor도 그 경로를 직접 읽음 | 별도 팀 registry에서 읽기 전용 원본 path/hash/ID를 해결하고 prepare→actor→bundle의 동일 팀 바이트를 검증. 원본13팀 수정으로 우회하지 않음 |
| 명시적64행 대진 | `make_schedule`은 열거된40/8/32 및 A/B/C profile만 허용하고, `verify_plan`은 원래 생성 표와 완전 일치를 요구 | 별도 승인된 A 진단 profile에서64행·팀 배정·진영·seed·순서와 독립 집계를 검증; 기존 profile 제약 유지 |
| A 단독 비교 | [conditions.schedule](../../../integration/pokechamp/improved_io/conditions.py)은 `(A,B)`/`(A,B,C)`만 허용 | A-only 조건1개와 비A 상대2개를 명시하고 B gate/대응쌍 완료 요구를 새 profile에 적용하지 않게 구현 |
| 준비·정책 identity | [battle_only_prepare](../../../integration/pokechamp/improved_io/battle_only_prepare.py)는 EX-016 개발 대진, [direct32](../../../integration/pokechamp/improved_io/direct32.py)는 봉인32표에 결합 | 별도 D/EX/EP 실행 identity, 이 설계의 hash, 승인된 상한·시계·gate/검증 정책을 봉인. 기존 EX-033 manifest를 편집하거나 halt 해제하지 않음 |
| seed 전달·배틀 격리 | 행별 `battle_seed`/actor seed, 임시 서버와 실제 seed 검사가 이미 존재 | 새 표의 seed가 p1/p2/team과 연결되는지 검사하고 Python/NumPy/PYTHONHASHSEED·서버 사용값을 receipt에 기록 |
| 생략값 정규화 | Showdown TeamValidator는 생략 성별을 `Math.random()`으로 채움. 기존 seed preload는 이 경로를 고정하지 않음 | 원문 생략을 보존한 team hash와 실제 packed team을 별도 봉인. 전체 bitwise 재현으로 주장하지 않으며, 추가 RNG 통제는 baseline 영향과 함께 별도 설계 |
| 증거 수집 | C-009 bundle에 실제 prompt/응답/decision/전송/public protocol 기록 가능 | 새 팀 registry provenance와 A의 무호출·복수호출·fallback까지 전수검토 inventory/annotation 연결을 검증 |
| 보고 | 기존 비교는 A/B 대응·B 설명 오류에 초점 | A task×정책×팀배정 성적/실패 분모, A의 모든 행동·기회·미확정/입력/실행 원인, 후속 가설 보고 |
| 실패/재수집 | direct32 계열의 경기별 실패격리·공유 영향 중단 지원. 새 profile과 선택적 복구의 연결은 미구현 | slot1회/provider0/보충0을 봉인하고 공유 결함의 중단 범위·원자료/halt/시계 보존 검증. 재수집 기능은 이번 설계에 필요하지 않음 |

저수준 Player가 팀 문자열을 받을 수 있다는 사실은 현재 연구 실행기가 외부 팀 manifest를
지원한다는 뜻이 아니다. 지원 여부는 위 등록·검증·실제 actor 전달 경로 전체로 판단했다.
새 schema를 기존 `plan.json`에 억지로 넣거나 검증기를 끄는 방식은 사용하지 않는다.

## 후속 실행의 구체적인 경계

실행기 구현은 이번 EP-028의 완료 기준이 아니다. 후속 구현 범위는 외부 팀 registry, A-only
고정64표, identity·예산/시계, 분모/검토 보고와 위 경로 검증으로 한정할 수 있다.
필요한 로컬 검증은 팀 바이트/hash·seed 실제 전달, 64행 입력/출력 연결, A baseline 보존,
무호출·출력실패·경기별 실패·공유 중단 사례와 관련 회귀다. 이 문서는 EX-033에서 생략했던
유료 gate를 새 실험에서도 생략하도록 승인하거나 그 gate가 통과했다고 기록하지 않는다.

사용자가 후속 실행을 지시할 때 별도 bounded plan에 대상64 slot·팀/설계 hash·구현 검증 결과,
추정1,828요청과 장기전3,656–7,312요청 감도, 실제 승인할 비용/시간/호출 상한·정리 여유와
최초 Cloud 시각 규칙을 기록한다. 현재 승인된 유료 대전 수는0이고 현재 최초 시계는 없다.
기존 EX-033의 누적 장부를 새 승인으로 초기화하거나 과거 결과를 새64경기 분모에 섞지 않는다.
별도 실행 요청이 없는 현재에는 추가 승인을 요구하지 않고 준비 결과를 종결한다.
