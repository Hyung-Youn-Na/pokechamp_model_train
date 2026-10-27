# 모델 패키지 배틀 평가·연결 — 연구 설계

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="kev-battle-connection"></a>

<a id="d-108-kev-r1-연결-검증"></a>
### D-108 Kev r1 연결 검증

[EX-068](experiments/EX-068-kev-battle.md)의 validation 재현과 Kev-p2 대 Abyssal-p1 한 경기는
기술적 연결 검사다. 기존 WEAK 오프라인 신호나 이 한 경기의 승패로 배틀 효과를 주장하지 않는다.
원 serializer·자기 팀·bf16/T1을 고정하고 Tera 허용과 사용 이후 학습 분포 밖 상태를 기록한다.
효과 비교는 독립 protocol·같은 상대 팀/seed의 짝지은 기준선·사전 경기 수가 있는 별도 범위다.

[D-109](decisions/D-109-kev-fused-validation.md)는 원 예측 불일치 후 사용자가 승인한 별도
merged·fused 경로의 추가 수락 검사다. 원 입력·dev 비교 기준은 유지하며 원 실패를 보존한다.
이 설정 묶음의 차이를 개별 커널이나 merge의 독립 인과 효과로 해석하지 않는다. 원 시계와
누적 사용량, 승인된 추가3요청 및 전체1경기 경계는 EX-068의 추가 실행 절에서 관리한다.

[D-110](decisions/D-110-kev-test-battles.md) / [EX-069](experiments/EX-069-kev-test-battles.md)는
기존 EX-065 test20 대진의 고정 Kev 정책 본 평가다. 추가 사전검사는 사용자 지시로 생략하고
test 팀/seed 메타데이터를 사용하며, 잠긴 suite의 저장 test 입력/타깃을 읽지 않는다.
표본/지표/원 Abyssal 참고 비교·불확실성·실행 방식 차이의 해석은 EX-069에 사전 고정한다.
EX-068의 연결 검사 및 과거 실패·판정을 소급 변경하지 않는다.

[D-111](decisions/D-111-kev-continuation-question.md) / [EX-070](experiments/EX-070-kev-continuation-question.md)는
후보 질문만 Kev 후속 정책 문구로 바꾼 동일 첫 대진1경기 진단이다. 정확한 질문·통제·상한·분모·
비교를 EX-070에 동결한다. 재학습 없이 현재 Abyssal 후속 정책 학습 타깃은 유지하므로 새 문구가
Kev 후속 승률의 정확한 추정을 보장하지 않는다. 이미 결과를 확인한 단일 대진이며 승률 개선이나
전패 원인을 확정하지 않는다. 후보 p/선택 직접 비교는 동일 JointInput 바이트의 결정에 한정한다.

<a id="d-071-jev-choice-기술-진단"></a>
## D-071 JEV Choice 기술 진단

[EX-047](experiments/EX-047-jev-battle.md)의 간결한 공식 관측·Choice/선봉·Abyssal2경기 진단을
채택한다. 계산과 사전을 제외한 별도 처치이며 B2의 표현 변경이나 모델 단독 효과 비교가 아니다.
상한/분모/중단·유료복구0은 EX-047을 따른다. 2경기 승패로 효능을 주장하지 않는다.

<a id="d-072-jev-수치-표현-호환성-교정"></a>
## D-072 JEV 수치 표현 호환성 교정

사용자 지적에 따라 확률 합계를 새 JEV 출력 수락 조건에서 제거한다. runtime 원문은 C-045다.
과거 EX-047의 동결 기준·실행 판정·미완료는 보존하고 새 기준의 저장 응답 검증은 별도 오프라인
근거로 기록한다. 실제 실험 재개나 완주를 뜻하지 않는다.

<a id="d-073-jev-수정본-재실행"></a>
## D-073 JEV 수정본 재실행

사용자 재실행 지시에 따른 [EX-048](experiments/EX-048-jev-repeat.md)의2경기 조건·상한·중단·완료 기준을 채택한다. EX-047과 별도 원장/시계로 수집하고 과거 실패를 보존한다.

<a id="d-081-jev-대-abyssal32-탐색-측정"></a>
## D-081 JEV 대 Abyssal32 탐색 측정

[EX-052](experiments/EX-052-jev-abyssal32.md)의 EX-046 대진 재사용·Abyssal 고정·JEV32경기와
완료쌍 평균점수·분모·기술통계 해석을 채택한다. 모델 우열이나 L1-L5 효능 비교가 아니다.

<a id="strategist-첫-배틀-탐색-평가"></a>
## Strategist 첫 배틀 탐색 평가

D-160의 EX-106은 단독 텍스트 행동 생성 모델의 완주·합법성 탐색이다. 실험별 방법·예산·대체 정책·분모·해석 원문은 [EX-106](experiments/EX-106-strategist-first-battle.md)이며 기존 JEV 비교 조건을 상속하지 않는다.

<a id="openai-decisions-v6-상세-고정-대진-탐색"></a>
## OpenAI Decisions v6 상세 고정 대진 탐색

D-164/[EX-109](experiments/EX-109-openai-decisions-v6-battle32.md)는 v6 상세 입력을
OpenAI gpt-6-luna의 단일 Choice로 평가하는 새32경기다. 기존 입력·후보 의미를 보존하고
provider/전송 형식 차이를 명시하며 일반 성능·모델 크기만의 효과를 주장하지 않는다.
구체 조건/예산/완료분모/복구는 EX-109, 기술 계약은 C-079에 둔다.

<a id="openai-통신-재시도-새32경기"></a>
## OpenAI 통신 재시도 새32경기

D-165/EX110은 사용자의 후속 지시에 따라 연결실패/timeout의 반복으로 제한하지 않는
새32경기다. EX109 원결과를 새분모에 계승하지 않고 같은모델/v6/대진에서 통신·시간정책만 바꾼다.
조건·미확정사용량·분모/복구는 EX110, runtime은 C-080에 둔다.


<a id="jevk5-9b-v6-상세32경기"></a>
## JevK5-9B v6 상세32경기

D-166의 [EX-111](experiments/EX-111-jevk5-v6-battle32.md)을 별도 탐색 평가 규범으로 채택한다. v6 원정보·고정대진과 JevK5 native 선택지 점수 판독/공식temperature를 결합한다. 기존 결과·중단·진행 중 EX110은 보존하며 단일모델 고정대진 결과를 인과/일반화 효과로 확대하지 않는다.
