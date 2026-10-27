# 규칙 이해 학습·적용 — 연구 설계

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="12-해석-규칙-interpretation-rules"></a>
## 12. 해석 규칙 (Interpretation Rules)

1. L1-L5 전체 효능 비교의 H1이 미정이므로 어떤 기존 또는 신규 result도 그 H1을
   support/reject한 것으로 분류할 수 없다. 개별 실험의 판정은 해당 동결 EX를 따른다.
2. Hypothesis support는 사전에 선언한 contrast, expected direction, metric, denominator,
   uncertainty rule을 충족하고 필요한 evidence가 온전할 때만 주장한다.
3. Qualification success는 interface와 evidence pipeline이 의도대로 작동한다는 뜻이며 efficacy
   success가 아니다. Infrastructure failure도 treatment의 연구적 실패가 아니다.
4. 여러 factor가 함께 달라진 comparison은 bundle 차이만 설명한다. 특정 layer, memory contract
   또는 learning algorithm의 독립 기여로 귀속하지 않는다.
5. 다른 model/provider, game version, routing, cadence 또는 interface의 operational comparison은
   caveat를 유지하며 controlled single-variable ablation으로 relabel하지 않는다.
6. 같은 point estimate는 equivalence를 증명하지 않는다. 작은 sample, 겹치는 interval 또는
   nonsignificant result를 효과 없음의 증거로 해석하지 않는다. L1-L5 전체 효능 비교의
   equivalence margin, significance level, minimum effect는 모두 TBD다.
7. Legacy archive는 새 RQ와 eligibility rule이 명시적으로 연결될 때만 secondary evidence로
   사용할 수 있다. 원저자의 claim을 새 연구 결론으로 그대로 가져오지 않는다.
8. Missing 또는 invalid attempt를 조용히 삭제하지 않는다. 모든 exclusion과 retry는 record와
   denominator 설명에 남긴다.
9. 정보 추가·표현 변경의 효과와 계층형 메모리 구조의 효과를 구분한다. 예를 들어 게임 규칙
   사전 추가의 결과만으로 L1-L5 구조의 기여를 주장하지 않는다. 구조 자체를 비교할 때는
   가능한 한 동일 정보에 접근하는 비계층 기준선을 두고, 정보 접근·예산 등 일치시키지 못한
   차이를 명시한다. 정보와 구조를 함께 바꾼 비교는 그 결합 효과로 해석한다.
10. D-063 이전 실험은 당시 목적·조건·유효성·분모 안에서 중간 목표의 참고 근거로 연결한다.
    새 RQ의 사전 검증 결과로 소급 변경하지 않으며, 기존 무효·미완료·Blocked 판정을 유지한다.

<a id="showdown-ruleqa"></a>

<a id="d-159--신규-showdown-규칙-데이터-v1"></a>
## D-159 — 신규 Showdown 규칙 데이터 v1

Gen9 singles의 24규칙군에 한정한다: 단일 상성 방향, 복합 상성, Flying/접지,
Levitate/Mold Breaker, 일반 Tera 방어, Tera/STAB/기술 타입, Stealth Rock 비중첩,
Stealth Rock 진입 피해, Spikes 층/접지, Boots 제거, Balloon 소실, Rapid Spin 명중/면역,
Ruination, 고정 피해, 피해 단위/null/0, 조건부 KO, 혼란, 마비, 화상/Guts,
우선도/속도/Trick Room, 교체/피벗/강제 교체, Protect/명중/성공, Gigaton Hammer,
공개/비공개/제거/억제. Stellar·다른 세대·더블·특수 포맷은 제외한다.

규칙군당40대조묶음, 묶음당2상황, 상황당 짧은 Q&A/전체 State Q&A/전체 State 선택형이다.
영어 템플릿과 1–3문장 근거, 한국어 검토 보고를 제공한다. 총1,920상황·5,760문항이며
표현과 두 export는 독립 표본으로 합산하지 않는다. seed20261019, 규칙군별 묶음32/4/4를
train/validation/test에 배정한다. 이름·ID만 다른 동일/근접 문제와 파생 문항은 split을 넘지 않는다.

새 CPU Showdown 장면만 생성한다. Dex/시뮬레이션/기존 계산기를 고정하고 정답과 조건을
구조화된 사실에서 판정한다. 설명에서 정답을 역추론하지 않는다. 확률과 조건부 결과를 구별하고
최적 행동을 주장하지 않는다. 공개 사실만으로 결정 불가능하면 명시적 불확실성 문제만
cannot determine를 허용하며 나머지는 제외한다. 기존 EX-083/088/105는 선정 근거로만 사용한다.

전수 oracle·설명·선택형 유일정답·정보경계·관련조건 대조·무관변형 불변·State 교정 범위·
경계 사례·분할 중복 검사를 수행한다. Tacit-9B/JEV-27B tokenizer로 실제 질문/선택지를 포함한
입력32,768 이하를 무절단 검사한다. 규칙군별4상황 총96상황을 별도 의미 검토한다.
실패 규칙군의 export는 차단하고 실패/수정 근거를 보존한다. 학습·추론·승률 평가와
효능 주장은 범위 밖이며, CPU worker≤4·GPU/API/추가 다운로드0이다.

D-159의 구현·자료·검증 결과는 [EP-169](plans/EP-169-showdown-ruleqa.md)에 연결한다.
완료는 규칙 자료의 검증을 뜻하며 모델/배틀 효과의 입증이 아니다. 제어 개입·소규모 팀·같은 템플릿 계열의
분할이라는 실제 자료 범위와 규칙별 예외는 해당 manifest/report에서 확인한다.

<a id="tacit-규칙-qa-lora"></a>
## Tacit 규칙 Q&A LoRA

D-161의 [EX-107](experiments/EX-107-tacit-ruleqa-lora.md)을 별도 학습 실험 규범으로 채택한다. D-159 자료 생성 범위를 소급 변경하지 않는다. 기존 split·validation 선택·잠긴 test로 같은 템플릿 내 적용을 비교하고 배틀·긴 Thinking·미지 형식 일반화를 주장하지 않는다.

<a id="학습-tacit-실전32"></a>
## 학습 Tacit 실전32

D-162의 [EX-108](experiments/EX-108-tacit-ruleqa-battle32.md)을 별도 단독 배틀 탐색으로 채택한다. EX107의 선택/잠긴test를 변경하지 않고 선택adapter 검증후 실행한다. 규칙QA와 실제 행동선택 전이를 구분하고 기반모델 미비교의 한계를 유지한다.


<a id="jevk5-규칙-선택형-lora"></a>
## JevK5 규칙 선택형 LoRA

D169의 [EX113](experiments/EX-113-jevk5-ruleqa-lora.md)을 독립 학습·보정·평가 규범으로 채택한다. 기존 test 재사용과 동일템플릿 한계를 유지하며 배틀효과로 확대하지 않는다.


## 학습 JevK5 실전32

D173의 [EX114](experiments/EX-114-jevk5-ruleqa-battle32.md)을 규칙QA에서 v6 행동선택으로의 전이 탐색 규범으로 채택한다. 과거고정대진 참고비교와 QA보정값의배틀미검증·길이차이 한계를 유지한다.

## Gen9 타입 상성 전수 자료

D174/EP192의 gen9-type-matchup-v1은 표준타입·일반테라·스텔라의 타입상성을 전수열거한 학습pool이다. 실제 종의 OU합법성이나 배틀 성능을 평가하지 않으며 기존 D159 자료/분할은 보존한다.

[EP193](plans/EP-193-gen9-type-system1-data.md)은 같은 원자료의 System 1 목적 직접분류/선택CE 표현을 제공한다. 설명생성 SFT를 사용하지 않지만 정답지도 분류이며, 모델사고방식·속도·성능 효과는 미평가다.

## 상태이상 System 1 자료

[EP195](plans/EP-195-gen9-status-system1-data.md)은 고정 Gen9의 상태이상 지식을 System1 직접선택형으로 만든다. 타입/테라 면역만 전수이고 특성·필드·지속효과·회복은 명시적 제어문항이다. 포맷 수면기술금지와 게임 수면효과, 확률과 확정결과를 구분한다. 기존 D159 자료/평가분할을 변경하지 않는다.

## 행동우선도 System 1 자료

[EP196](plans/EP-196-gen9-priority-system1-data.md)은 기술의 정수우선도·같은구간 행동순서·성공조건을 분리한 System1 자료다. 고정기술필터/명시스피드범위의 비교를 검증하고 동속은 확정승자로 라벨링하지 않는다. 종/세트합법성이나 모든queue변경·극단속도 사례를 전수지원하지 않는다.

## 날씨·영역 System 1 자료

[EP197](plans/EP-197-gen9-weather-terrain-system1-data.md)은4종날씨/4종terrain 및없음의규칙을직접선택형으로구성한다. 날씨/필드층·능력치/위력/피해/HP·접지주체·눈/우박을구분하고명시한그리드만전수검증한다. 대표예외외전상호작용·실제OU합법세트/모델효과는주장하지않는다.

## 실제 리플레이 KO System 1 자료

[D175](decisions/D-175-replay-ko-system1-data.md)/[EP198](plans/EP-198-replay-ko-system1-data.md)은 실제 리플레이의 공개 공격 직전 정보와 조건으로 주어진 기술로 관측된 직접 KO 여부를 학습하는 자료다. 숨은 세트/난수를 복원하지 않으며 단일 실현 결과를 확정 KO·자연분포 확률·최적 행동으로 해석하지 않는다. 기존 평가 자료를 보존하고 알려진 ID/팀 중복을 제외한다.

## 조건부 KO System 1 판정

[D176](decisions/D-176-conditional-ko-system1-data.md)/[EP199](plans/EP-199-conditional-ko-system1-data.md)은 공개리플레이의 종/기술을 출처로 한 명시적 제어조건과 검증된 비급소 피해범위를 제공하는 조건부KO 판정 과제다. 원관측결과를확정KO로바꾸지않고원경기조건부근거미확인을별도표시한다. 원경기숨은세트/HP복원·피해량예측·실전성능으로확대하지않는다.

## Smogon 전략 기반 역할 System 1

[D177](decisions/D-177-smogon-role-system1-data.md)/[EP200](plans/EP-200-smogon-role-system1-data.md)은 최근Smogon수집본의세트분석에근거한역할주석을사용한다. 기존409종DB추론라벨은사용하지않는다. 복수역할을허용하고미확인은실제역할불가가아닌source-support 미확인이다. 세트구성에없는본문전용변형/팀원역할을혼합하지않고공식Smogon role라벨·독립효능으로주장하지않는다.

## 우선순위별 규칙 적용 System 1

[D178](decisions/D-178-gen9-mechanics-system1-data.md)/[EP201](plans/EP-201-gen9-mechanics-system1-data.md)은 특성·도구, 교체·잔여, 기술 조건, 정보 충분성, 한 턴 결합 순으로 제어 자료를 구성한다. 정보 충분성은 명시된 가능세계 전체의 확실성 등급 일치 여부이며, 알려진 난수와 숨은 조건을 구분한다. 실제 공개 경기의 모든 가능한 세트를 복원하거나 독립 실전 효과를 평가한 것은 아니다.

## 전체 System One 학습

[D-180](decisions/D-180-jevk5-system1-full-training.md)의 [EX-116](experiments/EX-116-jevk5-system1-full-training.md)을 새 전체자료 학습·독립평가의 범위 한정 규범으로 채택한다. 새 구현은 `integration/jevk5_system1_training/`이며 기존 EX113과 자료 생성 계약은 보존한다.

## 전체 System One 선택모델 배틀

[D186](decisions/D-186-jevk5-system1-battle32.md)의 [EX123](experiments/EX-123-jevk5-system1-battle32.md)을 GPU1·2·3의선택epoch2 실전32 평가에한정해적용한다. 기존 EX116/114·서버·봉인은보존한다.
