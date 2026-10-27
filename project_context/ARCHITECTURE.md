# 전체 시스템 구성

현재 연구선의 목적은 포켓몬 모델 학습·정책 개선·독립 평가다. [CHARTER](CHARTER.md)와 [현재 상태](STATUS.md)를 함께 읽는다.
D-170에 따라 이 파일은 공통 원문과 주제별 원문 연결을 담당한다. 이전 절은 아래 링크의 주제 문서가 편집 원문이며 적용 범위를 자동 확대하지 않는다.
L1–L5를 명시한 설계·미정 항목은 별도 연구선의 보존 범위다. 과거 실험의 Current·현재·이번 표시는 그 당시 범위이며 실행 지시가 아니다.

공통 흐름: 공식 관측 → 입력·후보 구성 → 모델/계획/학습 정책 → 합법 행동 전송 → 기록·평가·뷰어.


<a id="repository-경계"></a>
## Repository 경계

| 경계 | 관찰된 책임 |
|---|---|
| [`AgenticSTS/`](../AgenticSTS) | Python agent runtime, prompt/context 조합, L3 조회, L4/L5 로직, 실험·재현 script, test, monitor backend/frontend, 정적 leaderboard |
| [`AgenticSTS-Mod/`](../AgenticSTS-Mod) | .NET 9/Godot/Harmony mod fork. 실행 중인 game state를 직렬화하고 action을 검증·주입하며 HTTP/SSE를 제공한다. |
| [`AgenticSTS-Data/`](../AgenticSTS-Data) | 공개 분석에 사용된 고정 dynamic store와 run/evolution/experiment artifact |
| [`docs/`](../docs) 및 [`assets/`](../assets) | Root release/site 자료·figure 및 PokéChamp 입력·요약 설명 문서. Agent runtime의 일부가 아니다. |
| [`pokechamp/`](../pokechamp) | Decision D-007에서 pin한 외부 PokéChamp source submodule. Parent integration은 이 worktree를 수정하지 않는다. |
| [`pokemon-showdown/`](../pokemon-showdown) | Local battle server용으로 pin한 외부 Showdown fork submodule. Canonical worktree는 실행 중에도 clean하게 유지한다. |
| [`integration/pokechamp/`](../integration/pokechamp) 및 [`scripts/pokechamp-env`](../scripts/pokechamp-env) | Parent-owned bootstrap, 명시 선택 Cloud adapter, deterministic server wrapper, qualification CLI와 test |

Release는 세 개의 최상위 component directory를 포함한 하나의 Git repository로 묶여 있다.
Python component에서 data와 mod directory는 sibling path다. Dynamic-data path 해석은
`AgenticSTS/src/storage/paths.py`에 집중되어 있다.

## 주제별 원문과 이전 앵커

<a id="아키텍처-architecture"></a>
- [분리 전 안내](shared/governance/ARCHITECTURE.md#아키텍처-architecture)
<a id="공개-정보-v6와-jev-공통-평가"></a>
- [공개 정보 v6와 JEV 공통 평가](research/input-and-memory/ARCHITECTURE.md#공개-정보-v6와-jev-공통-평가)
<a id="전략-planner-설정-경로"></a>
- [전략 planner 설정 경로](research/planner-executor/ARCHITECTURE.md#전략-planner-설정-경로)
<a id="보존된-v6-평가-경로"></a>
- [보존된 v6 평가 경로](research/input-and-memory/ARCHITECTURE.md#보존된-v6-평가-경로)
<a id="minicpm5-2b-jev-계산기-포함-평가"></a>
- [MiniCPM5-2B-Jev 계산기 포함 평가](research/model-evaluation/ARCHITECTURE.md#minicpm5-2b-jev-계산기-포함-평가)
<a id="quyet-medium-2단계-로컬-평가"></a>
- [Quyet-Medium 2단계 로컬 평가](research/model-evaluation/ARCHITECTURE.md#quyet-medium-2단계-로컬-평가)
<a id="고정-대진-공개-상태-정책-학습"></a>
- [고정 대진 공개 상태 정책 학습](research/fixed-matchup-learning/ARCHITECTURE.md#고정-대진-공개-상태-정책-학습)
<a id="환경과-qualification"></a>
- [환경과 qualification](shared/execution/ARCHITECTURE.md#환경과-qualification)
<a id="연구-관측봉인viewer"></a>
- [연구 관측·봉인·viewer](shared/viewers/ARCHITECTURE.md#연구-관측봉인viewer)
<a id="execution-boundaries"></a><a id="병렬-실행admission현재-제한"></a>
- [병렬 실행·admission·현재 제한](shared/execution/ARCHITECTURE.md#execution-boundaries)
<a id="기준선행동-후보fallback-경로"></a>
- [기준선·행동 후보·fallback 경로](shared/execution/ARCHITECTURE.md#기준선행동-후보fallback-경로)
<a id="battle-input"></a><a id="관측계산행동-설명서"></a>
- [관측·계산·행동 설명서](research/input-and-memory/ARCHITECTURE.md#battle-input)
<a id="전달-표현과-b2-전송"></a>
- [전달 표현과 B2 전송](research/input-and-memory/ARCHITECTURE.md#전달-표현과-b2-전송)
<a id="b2-선봉-선택"></a>
- [B2 선봉 선택](research/lead-policy/ARCHITECTURE.md#b2-선봉-선택)
<a id="요청별-상세-효과-사전"></a>
- [요청별 상세 효과 사전](research/input-and-memory/ARCHITECTURE.md#요청별-상세-효과-사전)
<a id="요약독립-진단-경로"></a>
- [요약·독립 진단 경로](research/input-and-memory/ARCHITECTURE.md#요약독립-진단-경로)
<a id="실험-정책별-실행-연결"></a>
- [실험 정책별 실행 연결](research/input-and-memory/ARCHITECTURE.md#실험-정책별-실행-연결)
<a id="상속-시스템과-미정-목표-아키텍처"></a>
- [상속 시스템과 미정 목표 아키텍처](research/l1-l5-port/ARCHITECTURE.md#상속-시스템과-미정-목표-아키텍처)
<a id="d-056-공급자-기본-동시성과-ex-041"></a>
- [D-056 공급자 기본 동시성과 EX-041](research/lead-policy/ARCHITECTURE.md#d-056-공급자-기본-동시성과-ex-041)
<a id="d-060-전송-시도와-논리-요청"></a>
- [D-060 전송 시도와 논리 요청](shared/execution/ARCHITECTURE.md#d-060-전송-시도와-논리-요청)
<a id="ex-042-공급자별-큐와-공유-수집-상태"></a>
- [EX-042 공급자별 큐와 공유 수집 상태](research/lead-policy/ARCHITECTURE.md#ex-042-공급자별-큐와-공유-수집-상태)
<a id="선봉-전략dex-규칙-구성"></a>
- [선봉 전략·Dex 규칙 구성](research/lead-policy/ARCHITECTURE.md#선봉-전략dex-규칙-구성)
<a id="ex-043-교정-b2-비교"></a>
- [EX-043 교정 B2 비교](research/lead-policy/ARCHITECTURE.md#ex-043-교정-b2-비교)
<a id="ex-044-직접-본실험-연결"></a>
- [EX-044 직접 본실험 연결](research/lead-policy/ARCHITECTURE.md#ex-044-직접-본실험-연결)
<a id="플레이어별-관측-tracker-진단"></a>
- [플레이어별 관측 tracker 진단](research/input-and-memory/ARCHITECTURE.md#플레이어별-관측-tracker-진단)
<a id="공식-관측의-bb2-운영-경로"></a>
- [공식 관측의 B/B2 운영 경로](research/input-and-memory/ARCHITECTURE.md#공식-관측의-bb2-운영-경로)
<a id="ex-045-공식-관측-분산-비교"></a>
- [EX-045 공식 관측 분산 비교](research/lead-policy/ARCHITECTURE.md#ex-045-공식-관측-분산-비교)
<a id="jev-9b-명시-단일-choice-경로-d-134"></a>
- [JEV-9B 명시 단일 Choice 경로 (D-134)](research/model-evaluation/ARCHITECTURE.md#jev-9b-명시-단일-choice-경로-d-134)
<a id="jev-provider-재시도-d-084"></a>
- [JEV provider 재시도 (D-084)](shared/execution/ARCHITECTURE.md#jev-provider-재시도-d-084)
<a id="d-088-ex-056-직접-본실험"></a>
- [D-088 EX-056 직접 본실험](research/input-and-memory/ARCHITECTURE.md#d-088-ex-056-직접-본실험)
<a id="d-089-ex-057-모델-고정-본실험"></a>
- [D-089 EX-057 모델 고정 본실험](research/input-and-memory/ARCHITECTURE.md#d-089-ex-057-모델-고정-본실험)
<a id="d-094-ex-058-개선-입력-연결"></a>
- [D-094 EX-058 개선 입력 연결](research/input-and-memory/ARCHITECTURE.md#d-094-ex-058-개선-입력-연결)
<a id="d-095-ex-059-자기-벤치-축약-연결"></a>
- [D-095 EX-059 자기 벤치 축약 연결](research/input-and-memory/ARCHITECTURE.md#d-095-ex-059-자기-벤치-축약-연결)
<a id="d-097-ex-060-한-경기-분기-수집"></a>
- [D-097 EX-060 한 경기 분기 수집](research/action-value/ARCHITECTURE.md#d-097-ex-060-한-경기-분기-수집)
<a id="d-098-ex-061-후보별-행동가치-학습"></a>
- [D-098 EX-061 후보별 행동가치 학습](research/action-value/ARCHITECTURE.md#d-098-ex-061-후보별-행동가치-학습)
<a id="d-099-ex-062-실시간-후보별-행동가치"></a>
- [D-099 EX-062 실시간 후보별 행동가치](research/action-value/ARCHITECTURE.md#d-099-ex-062-실시간-후보별-행동가치)
<a id="d-100-ex-063-학습-원대진-실전-진단"></a>
- [D-100 EX-063 학습 원대진 실전 진단](research/action-value/ARCHITECTURE.md#d-100-ex-063-학습-원대진-실전-진단)
<a id="d-101-결정-이름-표시"></a>
- [D-101 결정 이름 표시](shared/viewers/ARCHITECTURE.md#d-101-결정-이름-표시)
<a id="d-103-ex-065-공동-q-데이터-경로"></a>
- [D-103 EX-065 공동 q 데이터 경로](research/action-value/ARCHITECTURE.md#d-103-ex-065-공동-q-데이터-경로)
<a id="d-104-ex-066-base-공동-q-학습-경로"></a>
- [D-104 EX-066 Base 공동 q 학습 경로](research/action-value/ARCHITECTURE.md#d-104-ex-066-base-공동-q-학습-경로)
<a id="d-129-ex081-공동-q-체크포인트-배틀-경로"></a>
- [D-129 EX081 공동 q 체크포인트 배틀 경로](research/action-value/ARCHITECTURE.md#d-129-ex081-공동-q-체크포인트-배틀-경로)
<a id="d-108-kev-r1-실시간-연결"></a>
- [D-108 Kev r1 실시간 연결](research/model-evaluation/ARCHITECTURE.md#d-108-kev-r1-실시간-연결)
<a id="d-107-ex-067-abyssal-tera-보완-수집"></a>
- [D-107 EX-067 Abyssal Tera 보완 수집](research/action-value/ARCHITECTURE.md#d-107-ex-067-abyssal-tera-보완-수집)
<a id="d-113-ex-071-리플레이-모방-학습-경로"></a>
- [D-113 EX-071 리플레이 모방 학습 경로](research/policy-learning/ARCHITECTURE.md#d-113-ex-071-리플레이-모방-학습-경로)
<a id="d-114-ex-072-자기대국확률-보정-경로"></a>
- [D-114 EX-072 자기대국·확률 보정 경로](research/policy-learning/ARCHITECTURE.md#d-114-ex-072-자기대국확률-보정-경로)
<a id="d-116-ex-073-abyssal-전용-동기-4gpu-경로"></a>
- [D-116 EX-073 Abyssal 전용 동기 4GPU 경로](research/policy-learning/ARCHITECTURE.md#d-116-ex-073-abyssal-전용-동기-4gpu-경로)
<a id="d-117-ex-074-계승-경로"></a>
- [D-117 EX-074 계승 경로](research/policy-learning/ARCHITECTURE.md#d-117-ex-074-계승-경로)
<a id="d-118-ex-075-계승-경로"></a>
- [D-118 EX-075 계승 경로](research/policy-learning/ARCHITECTURE.md#d-118-ex-075-계승-경로)
<a id="life-orb-공개-입력-교정"></a>
- [Life Orb 공개 입력 교정](research/input-and-memory/ARCHITECTURE.md#life-orb-공개-입력-교정)
<a id="showdown-규칙-qa-데이터-경로-d-159--c-074"></a>
- [Showdown 규칙 Q&A 데이터 경로 (D-159 / C-074)](research/rule-learning/ARCHITECTURE.md#showdown-규칙-qa-데이터-경로-d-159--c-074)
<a id="strategist-텍스트-행동-평가"></a>
- [Strategist 텍스트 행동 평가](research/model-evaluation/ARCHITECTURE.md#strategist-텍스트-행동-평가)
<a id="tacit-규칙-qa-학습-경로-d-161--c-076"></a>
- [Tacit 규칙 Q&A 학습 경로 (D-161 / C-076)](research/rule-learning/ARCHITECTURE.md#tacit-규칙-qa-학습-경로-d-161--c-076)
<a id="학습-tacit-실전-예약-경로-d-162--c-077"></a>
- [학습 Tacit 실전 예약 경로 (D-162 / C-077)](research/rule-learning/ARCHITECTURE.md#학습-tacit-실전-예약-경로-d-162--c-077)
<a id="독립-openai-decisions-api-환경"></a>
- [독립 OpenAI Decisions API 환경](shared/execution/ARCHITECTURE.md#독립-openai-decisions-api-환경)
<a id="openai-decisions-v6-상세-평가"></a>
- [OpenAI Decisions v6 상세 평가](research/model-evaluation/ARCHITECTURE.md#openai-decisions-v6-상세-평가)
<a id="jevk5-9b-v6-상세-평가"></a>
- [JevK5-9B v6 상세 평가](research/model-evaluation/ARCHITECTURE.md#jevk5-9b-v6-상세-평가)
<a id="후보별-현재-대면-요약"></a>
- [후보별 현재 대면 요약](research/input-and-memory/ARCHITECTURE.md#후보별-현재-대면-요약)
<a id="ex112-후보별-요약-배틀-연결"></a>
- [EX112 후보별 요약 배틀 연결](research/input-and-memory/ARCHITECTURE.md#ex112-후보별-요약-배틀-연결)
<a id="jevk5-규칙-선택형-추가-lora"></a>
- [JevK5 규칙 선택형 추가 LoRA](research/rule-learning/ARCHITECTURE.md#jevk5-규칙-선택형-추가-lora)
