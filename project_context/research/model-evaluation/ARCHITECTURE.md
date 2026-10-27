# 모델 패키지 배틀 평가·연결 — 구성 설명

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="minicpm5-2b-jev-계산기-포함-평가"></a>
## MiniCPM5-2B-Jev 계산기 포함 평가

D-138/EP-144의 EX-091은 `integration/minicpm5_jev/`에 두 고정 revision의 다운로드/공식 파일
검증, 손실 없는 MiniCPM formatter, strict 헤드/LoRA 로더와 CPU 전수검사를 둔다.
공식 `MiniCPMSystemOne`의 BF16 backbone·FP32 비병합 LoRA·FP32 선택 헤드와 prior/온도를
사용하며 단일 causal row를 SDPA flash로 실행한다. JSON 평탄화·지시문 strip·절단·날짜 보강·
후보 순환은 호출하지 않는다. 사용자 텍스트의 제어토큰 표기는 일반 텍스트로 토큰화한다.
기반 모델의255 label-token 행과 저장 헤드를 대조하고 실제 token ID/후보 대응을 기록한다.

공통 `jev-eval`은 EX-091에 `jev-choice-v6`, GPU0 하나, 디스크 한도null과 EX-089 기준선을
연결한다. 준비·모델·감사·usage는 같은 formatter를 사용하며 기존 프로필의 제한은 유지한다.
저장1,139입력 CPU 검사는 피해량을 재계산하지 않고, 그중6/13/5후보·최장/최단 입력으로
8사전추론을 준비한다. 새 뷰어는 저장 피해 계산을 기본 연결하고 최대5대표 화면 안에서 검사한다.
EP-144의 독립 감지기는 단계 receipt와 workflow PID identity만30초마다 읽어 현재 대화에
한 번씩 알린다. 실행기/최종화는 알람 응답과 무관하게 진행하며 다른 모델 자동 실행은 없다.

<a id="quyet-medium-2단계-로컬-평가"></a>
## Quyet-Medium 2단계 로컬 평가

`integration/quyet/`와 `scripts/quyet`는 EX-084 전용 경로다. 기존 jev-choice-v4 관측 생성기와
Abyssal/Showdown 실행·고정 대진·리플레이를 재사용한다. 같은 관측에서 유형(move/switch)을
고르고 해당 유형의 세부 후보를 선택하며 최종 명령만 한 번 전송한다. 선봉/강제교체는 직접 선택한다.
공식 Quyet 패키지의 prompt v1·보정값·strict 추론을 기존 JEV 환경에서 사용하고 텍스트32층을
GPU0–3에8층씩 배치한다. HTTP 영속 원장은 결정/단계별 중복 추론을 차단한다.
새 경기별 감사·단계별 원문 뷰어·EX-083 고유 결과와의 대응 비교를 분리한다.
조건/한도/중단·검증 원문은 [EX-084](experiments/EX-084-quyet-medium-two-stage.md)다.

<a id="jev-9b-명시-단일-choice-경로-d-134"></a>
## JEV-9B 명시 단일 Choice 경로 (D-134)

`integration/jev9b/`와 `scripts/jev9b`는 EX-085 전용 모델 identity·32층 배치·출력·실행을
연결한다. 기존 JEV-27B 로더/HTTP 원장·jev-choice-v4 관측 생성·배틀 player·Abyssal과
감사/뷰어 자산을 재사용하며 기존 기본 프로필은 유지한다. 공식 BF16 backbone+LoRA 병합·
FP32 24×4096 head·bare-v1 보정값을 명시해 전체 후보를 단일 Choice로 선택한다.
GPU0–3의6/10/10/6층 배치·40/44GiB 한도와 최대8회 사전 추론 후 같은 서버 수집을 연결한다.
경기별 감사 receipt·종료 완전성/산술·EX-083 공통쌍 비교·전수 원문 내보내기와 대표 오프라인
검증을 구분한다. 조건·분모·중단·해석은 C-066/EX-085를 따른다.

<a id="d-108-kev-r1-실시간-연결"></a>
## D-108 Kev r1 실시간 연결

`kev_player.InputGenerator`가 기존 `joint_q.serializer.generate`와 원 Dex/Smogon/RoleDB를
공유하여 validation/live 입력을 생성한다. `kev_value`는 payload_json 문자열과 학습 문구의
후보별 noul 질문을 loopback `/v1/systemone`에 전달한다. 플레이어는 모든 후보 확률을 검증한
후 원순서 최대값을 고르고 rqid/합법 목록을 재검증한다. 단일 후보도 호출하며 대체 선택은 없다.

`kev_acceptance`는 validation3관측의 bytes와 저장 development 예측을 순차 gate로 확인한다.
`kev_control`은 서버를 시작하지 않고 로컬 checkpoint/head·Base 캐시·프로세스/GPU3와 준비
receipt를 대조한다. `kev_battle`은 EX-065 자기 packed 팀을 그대로 제출하는 Kev-p2와
새 reviewed108 상대의 Abyssal-p1을 별도 CPU 프로세스/소유 Showdown에서 한 번 실행한다.
모델 생성기에는 원 own.text만 전달하며 제출 형식과 구분한다. 원문 전송 기록의 전수 감사와
휴대 가능한 열람본은 `kev_audit`/`kev_viewer`가 담당한다. 수락 검사의 실제 완료 여부는
[EP-111](plans/EP-111-kev-battle.md), 조건은 EX-068, runtime은 C-054를 따른다.
재진입 명령·서버 승인 경계는 [Kev 안내](../../../integration/pokechamp/KEV.md)에 있다.

D-110의 `kev_main`은 이 worker·입력/선택/감사 경로를 재사용하여 EX-065의 원 test20 대진을
순차 실행한다. 양 packed 팀·simulator/actor seed·원순서를 동결하고 각 경기의 별도 Session과
전역 admission·시간 상한·판단 오류 경기 격리를 관리한다. 추가 사전검사는 사용자 지시로
생략하며 실제 진입의 동일성 확인과 경기별 원자료 감사/봉인은 유지한다. 전체 결과와
역사 기준선 분석·20경기 열람본은 [EP-112](plans/EP-112-kev-test-battles.md)와
[EX-069](experiments/EX-069-kev-test-battles.md)를 따른다.

D-111의 `kev_continuation`은 EX-069 첫 대진만 가져오는 전용1회 실행기다. 명시적
`kev-continuation-noul-v1`을 설정→기존 worker→Session→HTTP 생성/검증에 전달한다.
state/후보/명령과 기존 프로필 기본값은 유지하며 독립 감사·뷰어는 선언별 질문을 대조한다.
CPU receipt·소스/질문/모델 동결 후 감독 프로세스가 GPU3 소유 서버·수집 자식과 누적 시계/
정리 여유를 관리한다. 전역 시작/경기 admission으로 출력 경로를 바꾼 반복을 차단한다.
조건과 해석은 [EX-070](experiments/EX-070-kev-continuation-question.md)을 따른다.

<a id="strategist-텍스트-행동-평가"></a>
## Strategist 텍스트 행동 평가

`integration/strategist_eval`·`scripts/strategist-eval`은 EX-106 전용 단계 실행기다.
공식 관측·public_facts_v6의 공개 사실을 간결한 SFT 영어 문자열로 투영하고
별도 FP32 비병합 PEFT 프로세스에 JSONL 요청을 한 번 전달한다. 이름을 합법 후보의
슬롯 명령으로 연결하며 출력 오류만 seeded 균등 대체한다. JEV 입력·계산기는 사용하지 않는다.
공식 수신 cursor/요청 잠금·Showdown 소유 수명 관리를 재사용하고 Abyssal을 별도 seed 프로세스로
실행한다. 양측 테라 전송을 차단한다. 감사·분모·오프라인 입력/원응답/텍스트 리플레이와
네트워크 애니메이션 링크를 제공한다. 원문은 C-075와 EX-106이다.

<a id="openai-decisions-v6-상세-평가"></a>
## OpenAI Decisions v6 상세 평가

[D-164](decisions/D-164-openai-decisions-v6-battle32.md)/C-079의 EX-109는
`scripts/openai-decisions-battle` → 기존 CPU actor/공식 관측·v6 Adapter →
`integration/openai_decisions_battle`의 손실 없는 HTTP 변환 → OpenAI Decisions →
합법 원choice·현재rqid/명령 재검증 → Showdown 순서다. 단일후보는 API 미호출이며
Abyssal은 별도 seeded 프로세스다. GPU·planner·모델학습을 사용하지 않는다.
원 v6 입력과 실제 HTTP/내부 호환응답을 구분하고 경기별 공식cutoff·계산·전송을 재생성 감사한다.
[실행 안내](../../../integration/openai_decisions_battle/README.md).

D-165/EX110은 같은배틀 경로에 `RetrySession`을 주입하며 연결/timeout·408/429/5xx에서
논리ID/본문을 유지한 채 backoff 후 재전송한다. 개별시도60초·전체/경기/횟수 상한 없음과
상시취소를 분리한다. 반복HTTP도 단일선택/명령이며 원장/감사는 각 시도를 대조한다.
기존 EX109 Session과 당시 source/봉인은 별도로 보존한다.


<a id="jevk5-9b-v6-상세-평가"></a>
## JevK5-9B v6 상세 평가

D-166/EX111의 integration/jevk5_battle은 기존 v6 관측·대진/공식cutoff 실행을 재사용하고
사용자 소유 vLLM18847/GPU0의 모든 후보 logprob을 읽는다. native 비Thinking prompt·공식temperature1.316과 원ID 역매핑을 사용한다. 독립 Showdown8108과 출력·원장·뷰어를 가지며 EX110/기존 서빙 수명은 변경하지 않는다.
