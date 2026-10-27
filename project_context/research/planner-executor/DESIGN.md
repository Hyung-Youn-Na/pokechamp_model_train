# 전략 계획과 행동 실행 — 연구 설계

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="jev-planner-environment"></a>

<a id="glm-plannerjev-설정-환경"></a>
### GLM planner–JEV 설정 환경

D-158의 [EX-105](experiments/EX-105-tacit-vllm-low.md)는 사용자 소유 Tacit vLLM 서버를 이용하는 별도 재평가다. 기존 조건의 사전11/실제1경기와 판단 비교를 유지하되 backend/cache/sampler/계측 변경과 외부 서버 소유권을 명시하며 조건 원문은 EX-105다.

D-157의 [EX-104](experiments/EX-104-tacit-thinking-low.md)는 EX-103 조건의 Tacit thinking 패키지 새1경기와 동일입력 첫 판단/추론후 판단 비교다. 공식 프롬프트 차이·그림자 판단의 한계와 고정3사례 진단을 포함하며 조건/한도/해석 원문은 EX-104를 따른다.

D-156의 [EX-103](experiments/EX-103-jev-omni-low.md)은 EX-102 대비 Jev-Omni 패키지와 GLM low의 결합 처치다. 조건·gate·중단·비교 원문은 EX-103을 따른다.

D-155/EX-102는 EX-101의 reasoning_effort만 low→high로 바꾼 동일 대진 새1경기다.
나머지 사건호출/모델/입력/한도를 유지하며 조건·검증·중단 원문은 EX-102를 따른다.
단일 궤적 비교로 일반 성능이나 인과효과를 주장하지 않는다.

D-154/EX-101은 EX-100 대비 주기호출 제거와 공개 교체/출전 폼 사건 추가만의 처치다.
상세 조건·한도·검증은 EX-101을 규범 참조한다. 저장궤적28결정 재생은 호출위치 검증이며
새 경기 호출수 예측이나 성능평가가 아니다. 단일경기로 일반성능·인과효과를 주장하지 않는다.

D-152/EX-099는 EX-098 대비 경기/전체 시간 상한을null로 해제하고 GLM 출력을131072로
늘린 결합 처치의 새1경기다. 나머지 조건·호출/메모리·통신/출력복구 경계는 유지한다.
과거 사용자 중단/실패·봉인은 보존하며 일반 성능/인과효과를 주장하지 않는다.

D-151/EX-098은 EX-097 대비 GLM reasoning_effort만low→high로 바꾼 새1경기다.
원 입력/프롬프트/모델/한도를 유지하며 지연·usage·Ruination 행동 사례와 결과를 기술적으로 비교한다.
서로 다른 궤적의 단일 표본으로 추론 강도의 일반 성능/인과효과를 주장하지 않는다.

D-150/EX-097부터 새 GLM planner 기본 temperature는0이며 response_format 범위에서
최초+추가5회까지 형식 오류를 재생성한다. 전략적 의미 판단은 재시도하지 않는다.
관측/옵션·전체 한도/원문/usage를 보존하고 과거 동결 조건은 그대로 둔다.
EX-096 대비 온도와 복구범위를 함께 바꾼 단일 사례이며 일반 성능/인과 효과는 미평가다.

D-146/EX-094는 GLM content JSON 구문 오류의 최초+추가5회 재생성을 허용하는 출력복구 처치다.
같은 메시지/관측/옵션과 전체 호출/시간한도를 유지하고 원문/usage·HTTP시도를 모두 보존한다.
정상JSON의 계획 스키마/의미 위반은 대상이 아니다. EX-093과의 차이를 복구 정책으로 식별한다.

D-145/EX-093은 D-143의 변경 수행 지시문을 EX-092와 동일 대진·모델·호출정책의 새1경기에서
관찰한다. 단일 샘플의 기술·행동 사례 비교이며 일반 성능 향상/인과효과를 확정하지 않는다.
조건·한도·중단/복구·분모는 EX-093을 따른다. 기존 결과·뷰어·봉인은 보존한다.

D-143/EP-149는 JEV의 계획 목표 충족 확인·불필요한 반복 회피·유효한 미완료 목표 진전을
명시하는 수행 프롬프트 처치다. 현재 조건이 달라지면 목표 충족 여부를 재평가한다.
Planner 프롬프트/호출·관측·후보는 유지하고 변경은 새 설정에만 적용한다. CPU 연결 검증은
행동 개선·승률 효과의 증거가 아니며 실제 비교에서 수행 지시문 차이를 별도 조건으로 식별한다.

D-142/EX-092는 EX-088 첫 대진을 현재GLM planner/JEV-9B·역할guide·표시이름으로 새1경기
수집하는 첫 실제 샘플이다. 조건·한도·검증/중단·분모는 EX-092 원문에 둔다.
과거27B와의 효능 비교나 일반 승률 추정이 아니며 원 결과·봉인을 보존한다.

D-141/EP-147의 새 후보 표시명(names-v1)은 기존 관측의 이름을 후보 설명에 병기하는
입력 표현 처치다. ID/순서/명령·모델·계산·호출 정책을 유지하고 planner on/off에 같은 표현을 쓴다.
표시 추가 전후는 executor 입력 조건 차이로 기록하며 planner만의 효과로 해석하지 않는다.
가독성 개선과 실제 행동 선택/배틀 성능은 구분한다.

D-140/EP-146의 새 planner 기본 guide는 역할·양측 승리 경로·핵심 자원 보존/소모를 중심으로
구성한다. 입력 필드 제거가 아닌 system 안내 변경이며 기존 v6 state/후보/계산·수행 지시·
호출 정책을 유지한다. 상대 역할/승리 경로는 공개 근거에 따라 지지되는 조건부 가설로 다루고
역할 DB의 종족 가능성을 실제 세트로 확정하지 않는다. 새 지식 안내의 적합성과 성능은 별개이며
문헌에 근거한 설계나 무호출 검사만으로 GLM의 전략 품질·배틀 성능 향상을 주장하지 않는다.
실제 비교에서는 planner front prompt와 guide를 함께 프롬프트 조건으로 기록한다.

D-139/EP-145는 정책 개선 연구를 위한 호출·프롬프트 독립 설정 환경의 구현 범위다.
기본 수행 모델은 JEV-9B와 계산기 포함 교정v6, planner는 glm-5.3-flash의 전략 조언이다.
호출 정책 비교는 프롬프트/수행 모델/관측/일정을 고정하고, 프롬프트 비교는 호출 정책을 고정한다.
모델 패키지나 입력을 함께 바꾸면 결합 처치로 표시한다. off의 원래 JEV 입력을 기준 경로로 유지한다.
승리 조건·보존 대상·위협·Tera 방침·조건부 우선순위를 제공하되 최종 행동은 JEV가 선택한다.
Planner는 현재 관측·누적 공개 사실에 이전 계획과 이후 공개 사건을 더해 읽는다.
기본 최초+3턴/기절/Tera/강제교체 이외 정책 선택과 두 prompt는 모두 설정으로 명시한다.
같은 관측을 저장 재생하여 호출·입력 구성을 검증하는 것은 정책 변경 뒤 배틀 성능의 평가가 아니다.
실제 배틀 비교는 후속 EX에서 새 일정·예산·분모·실패/복구·해석을 정하며 이번에 실행하지 않는다.
이번 로컬 검증에 기존 자료를 읽는 것은 학습 편입·holdout 독립성 주장·실제 공급자/GPU 검증이 아니다.

이 브랜치의 현재 목적은 **모델 학습·정책 개선·독립 평가**다. 분리 전에 등록한 D별 절의 `Current`,
“현재 실행”, “이번 실행”은 각 결정이 채택한 당시 범위에 적용되며 현재 실행 지시가 아니다.
동결 D별 본문·EX/ADR 원문을 유지하고 현재 실행 여부는 [STATUS](../../STATUS.md)에서 확인한다.

[D-138](../model-evaluation/decisions/D-138-minicpm5-2b-jev.md)의 [EX-091](../model-evaluation/experiments/EX-091-minicpm5-2b-jev.md)을
교정v6·계산기 포함 MiniCPM5-2B-Jev의 고정 대진 패키지 탐색 규범으로 편입한다.
EX-089를 기준선으로 GPU0·디스크 상한null의 새32경기/16쌍을 평가한다. 모델/토크나이저/
전용 포맷/배치 차이를 함께 명시하며 조건·검증·알람·분모·해석은 EX-091 원문을 따른다.

[D-137](../input-and-memory/decisions/D-137-jev9b-no-damage.md)의 [EX-090](../input-and-memory/experiments/EX-090-jev9b-no-damage.md)을
피해 예측 정보·관련 설명 제거의 고정 대진 탐색 규범으로 편입한다. EX-089 결과를 기준선으로
재사용하며 스피드 비교를 유지한 새32경기/16쌍을 평가한다. 주지표·통제·검증·자원·실패/복구·
분모·해석은 EX-090 원문을 따른다. 입력 길이와 경기 진행 변화가 포함되며 일반화·동등성을 주장하지 않는다.

[D-136](../input-and-memory/decisions/D-136-jev-v6-corrected-evaluation.md)의 사용자 재승인으로
[EX-088](../input-and-memory/experiments/EX-088-jev27b-v6-corrected.md)/[EX-089](../input-and-memory/experiments/EX-089-jev9b-v6-corrected.md)를
교정v6의 새64경기 평가로 편입한다. 원질문/처치·기준/한도/해석은 유지하고 비교는
EX-088−EX-083, EX-089−EX-085, EX-089−EX-088이다. 기존 중단 결과는 별도 보존한다.

[D-135](../input-and-memory/decisions/D-135-jev-public-memory-v6.md)의
[EX-086](../input-and-memory/experiments/EX-086-jev27b-public-memory-v6.md) 공통 protocol과
[EX-087](../input-and-memory/experiments/EX-087-jev9b-public-memory-v6.md)의 모델별 차이를 공개 정보 보존/현재 상태
교정 결합 처치의 고정 대진 탐색 규범으로 편입한다. 신규64경기이며 비교·한도·검증·실패/복구·
분모·해석은 해당 원문을 따른다. 기존 EX-083/085 결과·뷰어·봉인은 보존한다.

[D-134](../model-evaluation/decisions/D-134-jev9b-single-choice.md)의
[EX-085](../model-evaluation/experiments/EX-085-jev9b-single-choice.md)를 동일 입력·단일 선택 정책의 공식
JEV-9B/JEV-27B 패키지 고정 대진 탐색 평가 규범으로 편입한다. 조건·한도·검증·분모·
복구·해석의 원문은 EX-085다. 기존32경기는 비교에만 사용한다.

[D-133](../model-evaluation/decisions/D-133-quyet-medium-two-stage.md)의
[EX-084](../model-evaluation/experiments/EX-084-quyet-medium-two-stage.md)를 새 Quyet-Medium 2단계/긴 입력
처치의 고정 대진 탐색 평가 규범으로 편입한다. 신규32경기이며 EX-083 성적은 비교에만 쓴다.
질문·처치·한도·검증·실패/복구·분모·비교/해석의 원문은 EX-084다.

[D-132](../model-evaluation/decisions/D-132-jev27b-four-gpu-continuation.md)의 별도
[EX-083](../model-evaluation/experiments/EX-083-jev27b-four-gpu-continuation.md)는 정상23경기 계승·4GPU 잔여9경기의
진입/자원/재시도/분모·혼합구간 해석 원문으로 편입한다. EX-082의 당시 판정·조건은 보존한다.

[D-130](../model-evaluation/decisions/D-130-jev27b-ex058-reproduction.md)에 따라
[EX-082](../model-evaluation/experiments/EX-082-jev27b-ex058-reproduction.md)의 질문·처치·동결 조건·진입 gate·
자원/시간·분모·실패/복구·비교/해석을 공개 JEV-27B의 EX-058 재현 평가 규범으로 편입한다.
과거 클라우드 모델과 로컬 공개 모델의 고정 대진 탐색 비교이며 다른 실험의 조건은 불변이다.

공통 연구 목적·미정 설계·평가·해석은 §1–15의 명시된 적용 범위를 따른다.
브랜치 목적은 [§1](../../shared/governance/DESIGN.md#branch-research-objective)에서 구분한다. 새 기본 IO 테스트는
[§8.1](../../RESEARCH_DESIGN.md#io-explanation-review), 도구 결함 복구는 [§11.1](../../RESEARCH_DESIGN.md#defect-recovery), 공급자 판단 오류는
[§11.2](../../RESEARCH_DESIGN.md#provider-judgment-errors)를 먼저 확인한다.
새 상세 효과 사전의 지식 추가·해석 범위는 [D-057](../input-and-memory/DESIGN.md#d-057-배틀선봉-상세-효과-사전), 선봉의 두 독립 개선은 [D-061](../lead-policy/DESIGN.md#d-061-선봉-전략규칙-입력-개선)을 따른다.
이 절의 안내는 각 규칙의 기존 적용 시점·예외를 바꾸지 않는다.

§0 및 D별 실험·진단 절은 당시 채택된 범위에 적용되며 새 작업의 실행·검증 목록으로 자동 상속하지 않는다.
`Current` 표시는 설계 채택을 뜻하며 실행 중이라는 뜻은 아니다. 현재 실행 상태는
[실행 계획 색인](../../exec-plans/INDEX.md), 과거 결과·정정은 [실험 색인](../../experiments/INDEX.md)에서 찾는다.
새 호출에 적용되는 D별 공통 기본값은 [D-013/014](../../shared/execution/DESIGN.md#0-d-012-기준선-pilot의-현재-설계),
[D-045](../../shared/execution/DESIGN.md#d-045-전체-cloud-기본-동시성8) 및 [C-029](../../shared/execution/CONTRACTS.md#c-029--새-cloud-기본-동시성8)의 기존 범위를 유지한다.

중복을 줄인 절은 EP-039의 2026-09-14 대조 시점에 정확히 지정한 기존 동결 EX/EP 원문 범위를 이 문서의 규범 내용으로
참조 편입한다. 연구 설계의 domain authority와 원문 소유권은 이전하지 않으며,
참조 문서의 나머지 본문이나 이후 변경을 자동 채택하지 않는다. 참조 원문에 있는 과거 승인·명령은
현재 작업 지시나 중단 실험의 재개 권한이 아니다. 고유 규범은 이 문서에 남긴다.
