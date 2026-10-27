# 전략 계획과 행동 실행 — 실행 계약

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="c-071-planner-role-guide"></a>

<a id="c-071--planner-역할자원-guide의-선택과-동결"></a>
## C-071 — Planner 역할·자원 guide의 선택과 동결

D-140/EP-146의 새 load_config는 prompts.guide를 UTF-8 파일 원문/path/sha256으로 해석하고
미지정 시 role-resource-guide-v1.txt를 기본으로 쓴다. 준비·미리보기·실제 요청은 동결된 guide
본문을 사용한다. 새 system은 planner 역할/출력 지시와 guide를 합치며 원 JEV 계산 안내를
자동 덧붙이지 않는다. guide 필드가 없는 과거 준비 설정은 C-070 당시 조립을 보존한다.
matrix.planner_prompts 항목은 선택적 guide 파일로 해당 조합의 안내를 지정할 수 있으며,
중복 제거/비교는 planner 지시와 guide의 원문을 함께 프롬프트 identity로 센다.

새 안내는 현재 역할·양측 승리 경로·유일 대응책·보존/교환·영구적 진전·위험/계획 전환을 다룬다.
자기 role_summary는 지원 가능한 능력, 상대 role_summary는 종족의 가능한 역할이다.
상대의 실제 역할/숨은 세트/미래 선택을 확정하지 않으며 가설과 관측을 구분한다.
피해/스피드는 현재 출전 대면의 조건부 보조 근거이며 벤치/미래 교체·정확한 보존HP를 보증하지 않는다.
공식 state·후보·user 이력·JEV 원지시문·Choice 의미·출력6필드·호출정책은 변경하지 않는다.
기존 봉인·뷰어·보고서를 수정하지 않으며 guide 변경은 새 프롬프트 처치다. 실제 품질/효능은 미평가다.

<a id="c-070-jev-planner"></a>

<a id="c-070--전략-plannerjev-실행-경계"></a>
## C-070 — 전략 planner–JEV 실행 경계

D-158/EX-105의 tacit9b-vllm은 외부 사용자 서버에 연결하는 CPU 프런트다. 모든 후보 logprob_token_ids를 판독하고 공식 thinking/마감 의미를 보존한다. HTTP/실제 출력량과 미관측 physical forward/allocator를 구분하며 외부 서버 소유권을 획득하거나 종료하지 않는다. 조건·자원/identity 감사는 EX-105를 따른다.

D-157/EX-104의 tacit9b는 공식 BF16 Transformers 라벨 판독과 always thinking 경로를 사용한다. 첫 판단은 기록만 하며 추론 입력에 주입하지 않고 최종 선택을 실행한다. 원입력 무절단32768/16, 생성8192와 마감후 native 문맥한도를 각각 검사한다. 논리 pipeline 중복방지와 실제 단계 forward/생성토큰을 구분하고 전후 분포·원추론·자연/강제 종료를 보존한다. 세부 조건은 EX-104를 따른다.

D-156/EX-103의 jev-omni는 공식 숫자형 텍스트 processor·BF16 분류·256슬롯 head를 사용한다. 전체 입력/후보를 보존하며 무절단32768/16 한도·원 index 역매핑·원확률 진단·실입력 usage/output0·단일 GPU0/동시1·장부 중복방지를 유지한다.

D-154의 명시 선택 active_change는 양측 공개 switch/drag/replace, form_change는 현재 출전 대상
detailschange/-formechange/-transform으로 검출한다. 위치문자 없는 벤치 대상은 제외한다.
공개 좌표로 사건을 보존하고 다음 다후보 결정에서 갱신한다. 단일후보 보류·중복제거·겹친사유
한호출을 유지하며 기존 기본 events 목록은 바꾸지 않는다. events 정책은 주기값을 사용하지 않는다.

D-153부터 Z.ai planner.model은glm-5.3-flash 또는glm-5.3을 명시 선택한다.
공통 기본 Flash/low와 기존 동결 설정·transport는 유지하며 새 모델 권한 실패 시 자동 대체하지 않는다.
EX-100의glm-5.3/low와 구체 조건은 해당EX 원문을 따른다.

D-152부터 명시적 battle_seconds/total_seconds=null은 경과시간 상한 없음이다.
전역 RunBudget·조건/Session·양쪽 actor deadline/상대 watchdog까지 적용한다. JSON에는null을
유지하고 내부 비교에서만 무한대를 사용한다. 유한 과거 값/기본은 불변이며 호출/메모리/
통신 timeout·재시도·사용자 취소/자식 실패 감시/자원 정리는 유지한다. 실제 경과시간은 기록한다.
EX-099의 GLM max_tokens131072와 구체 한도/중단 원문은 해당 EX가 소유한다.

D-147부터 새 jev-planner의 세 모델은 disk_bytes=null을 명시하고 용량 상한에 따른
준비/실행 중단을 하지 않는다. 기존 모델 profile의 배치/메모리 한도는 그대로 두고
`planner-<기존 profile>` 자원 profile로 부모·모델 서버 감시에 연결한다. 디스크 사용량은
계속 기록하며 실제 공간/I/O 오류를 무시하지 않는다. 과거 EX/동결 profile의100GiB 기록은 보존한다.

[D-139](decisions/D-139-jev-planner-environment.md)/EP-145의 새 설정 경로에 적용한다.
호출/프롬프트/모델/평가 설정을 분리하고 실행별 원문·revision·source를 고정한다.
off는 v6 입력과 지시문을 그대로 전달하며 planner 필드/자격증명/호출을 요구하지 않는다.
활성 정책은 첫 다후보 결정에서 시작한다. 단일 후보는 두 모델 무호출이며 사건을 소진하지 않는다.
periodic은 마지막 성공 계획과 현재 Showdown 턴 차이(선봉0)로 계산하고 사건 호출도 기준을 갱신한다.
기절·공개 Tera는 actor 수신 공개행, 강제교체는 자기 request 사건이며 각각 고유 위치/rqid로 식별한다.
같은 턴 다른 rqid는 별도 결정, 같은 요청은 모델/전송 중복 없이 재사용한다. 같은 rqid의 서로 다른
관측/후보는 일관성 오류다. 겹친 trigger는 한 번 호출하고 모든 이유를 보존한다.

Planner와 수행 모델은 동일한 불변 관측·후보·공개 prefix cutoff를 쓴다. Planner는 현재 v6 입력과
이전 계획·그 이후 공개 사건만 읽으며 비공개 요청·상대 실제세트·미래행을 추가하지 않는다.
계획은 경기/actor별로 격리하고 갱신 또는 종료까지 유지한다. 출력은 objective/priorities/preserve/
threats/tera_policy/contingencies JSON이며 전략 조언이다. 후보 생성·삭제·재정렬/명령 대행을 하지 않는다.
수행 입력에 계획·생성/경과 턴과 현재 관측 우선 지시를 추가한다. Planner reasoning은 별도 기록만 한다.
응답 후·실제 전송 전 최신 rqid/후보/취소를 검증하며 오래된 결정은 전송하지 않는다.

D-143/EP-149의 새 수행 지시문은 각 계획 목표의 현재 충족 여부를 확인하고, 충족 조건이
유지되는 동안 불필요한 반복을 피하며, 유효한 미완료 목표를 진전시키도록 한다. 조건 변화 시
재평가하고 현재 위협·보존 우선순위와 원래 승리 목표를 유지한다. 선택 조언이며 후보 필터나
완료 상태 추적기를 추가하지 않는다. 기존 동결 지시문은 보존하고 새 기본 설정에만 적용한다.

D-150부터 새 기본 planner.temperature=0, planner.retry_scope=response_format이다.
json_retries(기본5)를 전체 출력 재생성의 단일 상한으로 사용한다. JSON 구문/중복키/비유한값·
계획 스키마·빈/잘린 응답·성공HTTP envelope 오류를 같은 입력/옵션으로 재생성한다.
원문/usage/오류/생성차수와 모든 물리HTTP를 기록·예산에 포함하며 전송 재시도는 별도 기존 정책이다.
유효 계획의 전략적 의미는 검사/복구 대상이 아니다. retry_scope 부재는json_syntax로 과거를 보존한다.
과거 명시 온도는 그대로 유지하고 새 기본 설정·예제는0을 사용한다.

D-146 당시 설정 planner.json_retries는0–5(기본5)이며 content JSONDecodeError에만
최초+추가5회까지 같은 messages/옵션으로 재생성한다. 과거 동결 설정의 필드 부재는0이다.
매 JSON 생성차수/물리HTTP의 원문·usage와 누적시도를 기록하고 모든 HTTP를 전체 예산에 센다.
정상JSON의 스키마 위반·중복키/의미 오류와 응답 envelope 오류는 대상이 아니다. 소진된
파싱불가/형식위반 계획과 실행불가 JEV 선택은 해당 경기만 실패 처리한다. 합법 선택·잘못된 전략은
원문/진단과 함께 계속하며 의미 오류를 gate로 쓰지 않는다. 공유 입력/무결성 오류는 RD11.1을 따른다.
Z.ai 전송 재시도는 C-038을 재사용하고 최종429는 신규 수집 중단이다. Planner 생성 기본은
enabled/low, temperature0/top_p0.95/max_tokens8192이며 새 설정에만 적용한다. 기존 provider 기본값은 불변이다.
관측·계획·선택·실제 메시지·호출사유/미호출·HTTP시도/usage/지연·실패를 연결하고 비밀은 기록하지 않는다.
전체 수행 입력32768토큰 한도는 무절단 거부하며 공식 모델별 formatter/Choice 수치를 유지한다.

preview/prepare는 모델 무호출이다. run은 mock/live를 명시하며 실제 모드는 새 실험 기록·일정·
호출/자원 한도를 필요로 한다. 이번 승인에는 live 실행이 없다. 비교는 mock/replay/live와 예정/완료/
실패/미실행 분모를 구분한다. 저장 궤적 재생은 승률 실험으로 해석하지 않는다. 새 viewer는 저장된
planner/수행 원문과 결정 연결을 오프라인 제공하고 기존 viewer·봉인 자료를 덮어쓰지 않는다.
