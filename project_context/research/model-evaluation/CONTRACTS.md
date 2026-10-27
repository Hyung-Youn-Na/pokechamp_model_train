# 모델 패키지 배틀 평가·연결 — 실행 계약

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="c-069-minicpm5-2b-jev"></a>

<a id="c-069--minicpm5-2b-jev-손실-없는-choice-평가"></a>
## C-069 — MiniCPM5-2B-Jev 손실 없는 Choice 평가

D-138/EX-091에 적용한다. C-067의 교정v6 정보·후보/명령/순서·프롬프트·감사/턴로그를
유지하고 MiniCPM 채팅/질문/선택지/답변 틀에 원state·전체 후보 JSON을 손실 없이 넣는다.
공식 서버의 평탄화·절단은 사용하지 않으며 공식 기본 서버 재현으로 표기하지 않는다.
모델·기반 revision/공식 파일 identity, 병합하지 않은 LoRA·BF16 backbone·FP32255×2048
헤드/label-token행·저장 온도/K별prior를 검증한다. PriDe·날짜 보강·보정 환경변수 덮어쓰기는
금지한다. 동일 formatter를 준비·모델·감사·usage에 적용하며 최대16후보/32768토큰을
무절단 검증한다. 단일 후보는 무호출이며 전송/영속 중복추론 방지·판단실패 격리를 유지한다.
GPU0만 소유/잠금/감시/반환하고 EX-091의 nullable 디스크 상한null을 모든 준비/실행/
브라우저 복사 검사에 적용한다. 사용량과 실제 공간/I/O 오류는 계속 기록한다.
단독 실행·1,139입력 전수 검사·단일 적재/최대8추론·단계 알람·비교/뷰어/봉인/반환은
[EX-091](experiments/EX-091-minicpm5-2b-jev.md)을 따른다. 기존 프로필·동결 조건은 불변이다.

<a id="c-066-jev9b-single-choice"></a>

<a id="c-066--jev-9b-단일-choice-실행-경계"></a>
## C-066 — JEV-9B 단일 Choice 실행 경계

[D-134](decisions/D-134-jev9b-single-choice.md) / [EX-085](experiments/EX-085-jev9b-single-choice.md)에 적용한다.
C-063/C-064의 jev-choice-v4 관측·후보·무절단·전송/중복 추론 방지 의미를 재사용하되
모델 identity·FP32 24×4096 head·보정값·경로·32층 배치를 명시 프로필로 분리한다.
기술·테라·교체 전체 후보에서 단일 Choice, 선봉/강제 교체 직접 선택, 단일 후보 무호출이다.
전체32768토큰·공식16후보 한도를 넘으면 추론 전에 거부한다. 기존 기본 프로필은 유지한다.
C-046 판단 실패 경기 격리·C-047 원문 내보내기를 적용하며 자원·최대8회 단일 서버 gate·
경기별1회 감사/종료 완전성·뷰어 표본 예외·복구/분모는 EX-085 원문을 따른다.

<a id="c-065-quyet-two-stage"></a>

<a id="c-065--quyet-2단계-choice-실행-경계"></a>
## C-065 — Quyet 2단계 Choice 실행 경계

[D-133](decisions/D-133-quyet-medium-two-stage.md) / [EX-084](experiments/EX-084-quyet-medium-two-stage.md)에 적용한다.
jev-choice-v4의 관측·상세 정보·계산/지식을 유지하고 move/switch와 세부 행동을 분리한다.
유형 설명은 세부 후보 전체, 세부 질문은 선택 유형의 원 ID/내용/순서만 포함한다.
같은 상태를 두 단계에 전달하고 중간 관측·추측을 추가하지 않는다. 공식10후보·prompt v1·
Choice 보정값과 strict=True를 사용하며 상태/전체32768 초과는 무절단 거부한다.
자동 선택은 실제 호출/응답과 구분하고 단계별 원문/formatter/확률/usage/지연을 보존한다.
세부 확률은 조건부이며 미선택 유형의 분포를 합성하지 않는다. 결정/단계별 ID와 같은 본문
재전송·영속 중복 추론 방지, 단계 사이/전송 직전 rqid·후보·취소 검사로 최종 명령을 한 번 보낸다.
C-046의 판단 오류 경기 격리, C-047의 원문 내보내기를 적용한다. 자원·최대9회 GPU gate·
경기별1회 감사/종결 확인·뷰어 표본 예외·실패/복구·분모의 원문은 EX-084다.

<a id="c-064-jev27b-continuation"></a>

<a id="c-064--ex-083-4gpu-계승-실행-경계"></a>
## C-064 — EX-083 4GPU 계승 실행 경계

[D-132](decisions/D-132-jev27b-four-gpu-continuation.md)과
[EX-083](experiments/EX-083-jev27b-four-gpu-continuation.md)에 적용한다.
C-063의 입력/후보·무절단·HTTP 형식·중복 추론 방지 의미를 유지하고 EX-083에 한해
장치 배치·자원/서빙 identity·부모 계승·새 진입 gate를 명시 변경한다.
`jev27b continue --parent --directory`는 봉인된 EX-082의 정상23만 계승하고 원24–32번만
새로 실행한다. 원24번 추가1회 이외 재경기0, 기존 execute의 덮어쓰기/재개 거부는 유지한다.
네 GPU0–3의 잠금/UUID/유휴 확인 후 CUDA 초기화·40GiB allocator/44GiB 전체 사용량 감시와
소유 자원 회수를 같은 장치 집합에 적용한다. 부모 원자료·실패·봉인·Blocked는 불변이며
새 manifest에 전체32슬롯·계승/신규구간·각 시도 및 원자료 hash를 기록한다.
독립 재로딩·591응답 전수 대조·같은 서버 연속 메모리/일반턴 gate의 조건과 중단/집계 원문은
EX-083이다. 부모와 신규구간을 감사하고 실패를 포함한 총시도·고유경기 분모를 구분한다.

<a id="c-063-jev27b-local"></a>

<a id="c-063--jev-27b-로컬-choice-재현-경계"></a>
## C-063 — JEV-27B 로컬 Choice 재현 경계

[D-130](decisions/D-130-jev27b-ex058-reproduction.md)과
[EX-082](experiments/EX-082-jev27b-ex058-reproduction.md)에만 적용한다. 기존 jev-choice-v4의
입력/명령/최신 rqid 경계와 choice-action-v3 실패 격리를 유지한다. 공식 bare formatter에
상태·지시문·후보 객체 전체와 순서를 보존하고 확률을 원 후보 ID에 대응한다. 입력 한도32768·
무절단, 단일 후보 무호출이다. loopback HTTP의 revision/서빙 identity를 확인하고 동일 본문·
request ID의 재전송에서 서버가 추론 결과를 재사용한다. 다른 본문에 같은 ID는 거부한다.
시간/자원·진입/중단 gate 원문은 EX-082다. GPU0·1만 소유하고 EX-080/GPU2·3·공유 환경·
기존 입력 source를 보존한다. 과거 HTTPS·재시도·시간 상한 계약을 소급 변경하지 않는다.

<a id="c-045-jev-battle"></a>

<a id="c-045--jev-choice-배틀-프로필"></a>
## C-045 — JEV Choice 배틀 프로필

D-071의 jev-choice-v1은 C-044 native state/questions를 사용한다. 공식 관측 actor·요청 cutoff와
합법 후보를 재사용하되 B/B2 정규화·계산·출력 계약과 독립한다. 모델에는 자기 요청·공개 관측·
최근 완료3턴 공개 이벤트만 투영한다. 상대 미공개 능력/아이템/HP는 unknown이다.
Choice 후보 ID는 요청 슬롯 기반이고 기술/테라기술/교체를 분리한다. 선봉도6후보 choice다.
D-072의 choice-values-v2는 확률의 유한0..1·전체 후보와 키 일치, confidence0..1 및 최댓값 선택을 검증한다. 확률 합계는 검사하지 않고 원값을 재정규화하지 않는다. D-075의 새 choice-action-v3는 [C-046](../../CONTRACTS.md#c-046-provider-judgment)을 따른다. 새 manifest에 validation_version을 기록한다. 미기재 과거 manifest는 choice-sum-v1(합1 허용오차1e-4)로 감사하여 당시 판정을 보존한다.
단일 후보 자동 실행·대기 무호출, 요청ID/후보 재검증 후 명령 전송. 전송 실패/입력/응답 오류는
실패 폐쇄하며 대체 행동0이다. 입력/원응답/후보/선택/전송/모델/usage/지연을 보존한다.
초기 실행의 상한·복구·분모는 EX-047, D-073 수정본 재실행은 EX-048을 따른다. 기존 공급자 선택과 과거 정책 hash는 유지한다.

D-079의 새 `jev-choice-v2`는 자기 선봉을 request 슬롯으로 구성하며 공개 프리뷰와
종족·순서로 연결하지 않는다. 초기 상태는 teamPreview·turn0·init/teampreview 및
전투 이벤트 부재로 확인한 경계에만 적용한다. status는 자기 condition에서 판독하며
미확인 condition을 정상으로 간주하지 않는다. boosts/효과의 빈 객체는 변화/효과 없음,
status의 빈 문자열은 상태이상 없음, tera_type의 빈 문자열은 테라 미적용이다.
teraType은 설정 타입, terastallized/tera_type은 적용 타입이다. unknown은 근거 부재다.
일반 턴의 관측 연결은 유일한 자기 ident에 한정하고 모호성은 거부한다.
초기 PP는 검증된 고정 서버/Dex의 `showdown-gen9-max-pp-v1` 정책과 Gen9 OU 시작 전
경계가 함께 있을 때만 기본 PP×8/5(noPPBoosts 예외)로 채운다. 그 외 unknown의 이유를
명시하며 현재 active.moves의 PP가 우선한다. 상대 비공개 정보는 보강하지 않는다.
과거 감사는 manifest 버전의 v1 입력/prompt를 재현하며 과거 봉인·판정을 갱신하지 않는다.
D-080/EX-051은 v2의 실제2경기 검증 범위이며 EX-049/050의 choice-action-v3·상한·기술 중단·
경기 출력 실패 격리를 새 identity에 적용한다. 구체 조건과 승인 범위는 EX-051을 따른다.

D-082의 새 기본 `jev-choice-v3`는 v2 관측·PP 산출/검증·후보·명령·선택 검증을 유지한다.
사용자 제공 GENERATION 9 SINGLES MECHANICS 전문을 지시문에 그대로 추가한다.
`state.effect_reference`는 고정 `gen9-effects-v1`의 items/abilities/moves별 정규화 ID →
{name, desc} 영어 원문이며 자기 정보·확인된 상대·합법 후보·최근 공개 이력의 참조만 수록한다.
설명 재귀 확장·미확인 상대 세트 보강은 금지한다. 사전은 보유·발동 증거가 아님을 지시한다.
JEV 전용 수집기는 후보 move.id를 읽으며 불리언 terastallize를 효과로 해석하지 않는다.
실제 참조 설명 누락·사전 무결성 오류는 입력 생성 실패다. 새 모델 payload의 모든 위치에서
current_pp_source를 제거하되 current_pp_reason·PP 값은 유지한다. 원래 관측/request·manifest의
초기 PP 정책 및 사전 버전/hash/출처는 모델 밖 감사 기록으로 보존한다.
v1/v2 프롬프트·투영·과거 EX-051/052 원자료/봉인/뷰어는 보존하고 당시 버전으로 감사한다.

<a id="d-081--ex-052-jev-일정-실행-확장"></a>
## D-081 / EX-052 JEV 일정 실행 확장

C-045/046 입력·선택 의미를 유지하고 별도 일정 실행 경로에서 actor별 프로세스/RNG와
전체 누적 예산·일정 기반 감사를 적용한다. 원문 조건은 EX-052이며 과거2경기 기본값/감사는 보존한다.

<a id="c-054-kev-battle"></a>

<a id="c-054--kev-pokechamp-r1-배틀-연결"></a>
## C-054 — Kev pokechamp r1 배틀 연결

D-108의 `kev-joint-noul-v1`은 C-051의 생성기와 원 serializer/snapshot/RoleDB를 그대로 사용한다.
`JointInput.payload_json`을 문자열 state로 보내며 별도 system/chat template을 추가하지 않는다.
actions 원순서의 ID별 noul 질문은 Kev 학습 builder의 QUESTION/describe와 정확히 같다.
criteria·타깃·원선택·private·seed를 보내지 않는다. 모든 응답 ID/type/유한0..1 값을 검증하고
최대 p(true), 동률 원순서로 선택한다. 확률 합계 정규화0, 단일 후보도 호출한다.
원 commands로 매핑하고 전송 직전 rqid/합법 목록·만료를 재검증한다. 불완전/불량/stale/timeout은
무전송이며 fallback0이다. 입력 SHA-256·원 요청/응답·후보 p·선택/명령·지연·재검증/전송을 기록한다.
서버는 loopback HTTP만 사용하며 redirect/외부 proxy/재시도0이다. 모델 bf16·T1과
run/Base/revision/adapter/head provenance를 고정한다. 원 D-108 실행의 unmerged 설정은 보존하며,
D-109의 명시적 추가 승인에 따른 `ex068-v3`는 merged·fused 경로를 사용한다. 새 준비/프로세스
receipt에 이 조건과 원 실패·추가 호출 한도를 연결한다. 원 자원·gate·실행/중단 범위는 EX-068을 따른다.
D-110의 EX-069 본 테스트는 이 통과한 서빙·입력/선택 경로를 재사용하고 사용자 지시로 추가
사전검사를 생략한다. EX-065 test의 팀/seed 메타데이터만 새20경기에 사용하며 저장 test
입력/타깃을 모델에 전달하지 않는다. 별도 경기 admission과 본 실행 한도는 EX-069가 소유한다.

D-111의 명시적 `kev-continuation-noul-v1`은 EX-070의 정확한 한 줄 질문만 사용한다. 기존
`kev-joint-noul-v1`의 기본값·학습 질문 바이트는 유지한다. 설정→worker→Session→HTTP 요청
생성/검증에 profile을 전달하며 HTTP body 필드는 늘리지 않는다. 알 수 없는 profile과 선언에
맞지 않는 질문/순서는 요청·독립 감사·뷰어에서 거부한다. 같은 관측의 state 문자열·후보·명령,
서빙·선택 규칙·공용 생성기·학습 코드/타깃은 유지한다. 새 전용 admission·질문/소스/모델 동결과
실행 예산/중단 원문은 EX-070을 따른다.

<a id="c-075--strategist-텍스트-행동-경계"></a>
## C-075 — Strategist 텍스트 행동 경계

D-160/EX-106에만 적용한다. 공식 관측과 자기 request로 짧은 입력/합법 후보를 구성한다. 원문 첫 행동 줄을 유일 후보에 연결하고 모델 출력 오류만 등록된 seeded 균등 대체로 처리한다. 단일 후보는 미호출 자동선택이다. 전송 직전 rqid/후보 재검증과 양측 테라 차단을 유지한다. 상세 조건/한도/오류 분류는 [EX-106](experiments/EX-106-strategist-first-battle.md), 공통 결함 경계는 C-018이다.

<a id="c-079-openai-decisions-battle"></a>

<a id="c-079--openai-decisions-v6-배틀-경계"></a>
## C-079 — OpenAI Decisions v6 배틀 경계

D-164/EX-109에서 C-067의 상세 입력과 원 후보/명령 순서를 유지하며
OpenAI Decisions의 input/choice 질문으로 손실 없이 변환한다. 원 v6 payload와 실제
HTTP JSON·응답은 각각 보존하고 내부 호환 응답을 원 HTTP 응답으로 표시하지 않는다.
단일 후보 무호출, 나머지 choice 원값 실행·C-046 판단 오류 격리, 전송 전 rqid/후보 재검증을 적용한다.
키/Authorization은 원장·소스·자식 프로세스에 넣지 않는다. 요청·실패·usage·사전/본수집을 구분한다.
새 provider의 연결·실행 상한/실패·감사/복구는 EX-109, 뷰어는 C-047을 따른다.

<a id="c-080-openai-decisions-retry"></a>

<a id="c-080--openai-통신-지속-재시도"></a>
## C-080 — OpenAI 통신 지속 재시도

D-165/EX110에서 C-079의 v6/후보/실행 경계를 유지하고 통신정책만 별도 프로필로 확장한다.
연결·timeout·408/429/5xx는 같은 논리ID/본문으로 무횟수 상한 재시도하며 모든 물리시도를 기록한다.
개별HTTP60초는 재시도 경계이고 전체/경기시간·요청수 상한은 없다. backoff/Retry-After·취소를 지원한다.
명백한 요청/인증/권한 오류와 관측/수집 무결성 오류는 일시적통신으로 숨기지 않는다.
원choice를 변경하지 않고 raw/내부호환 응답·재시도/미응답사용량을 구분한다. 공급자 내부 중복추론0은 미보장이다.
EX109의 당시재시도0·중단/봉인은 보존한다.


<a id="c-080--jevk5-외부-vllm-선택지-판독"></a>
## C-080 — JevK5 외부 vLLM 선택지 판독

D-166/EX111의 v6 상세 입력은 원state/instructions/criteria를 가역 변환한다. JevK5 native 비Thinking prompt와 모든 후보 단일 token ID의 raw logprob을 사용하고 softmax(z/1.316)로 사전 정의한 결정을 산출한다. 원HTTP·prompt token·logprob·보정분포/선택을 구분해 보존한다. 생성 글자는 정책이 아니며 생성1토큰 usage는 포함한다. 사용자 소유 서버 PID/명령/모델/GPU identity를 확인하되 종료하지 않는다. 실패·재시도·상한·검증은 EX111을 따른다.
