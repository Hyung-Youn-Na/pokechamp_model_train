# 규칙 이해 학습·적용 — 실행 계약

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="c-074-ruleqa"></a>

<a id="c-074--데이터-전용-규칙-qa-state"></a>
## C-074 — 데이터 전용 규칙 Q&A State

D-159/EP-169의 jev-ruleqa-state-v1은 실제 Node 장면의 행동 선택 경계에서 actor 공개 로그와
자기 request만 공식 관측기→공개 사실 재구성→jev-choice-v6→names-v1에 전달한다.
양측 행동 제출 전 또는 피벗/강제 교체 중간 선택에서 자른다. 상대 내부세트·미래·seed·oracle은
입력에 넣지 않고 evidence에 분리한다. v6 복사본의 state.version과 confusion volatile의 name/kind/general_effect만 허용 교정하며,
confusion 상태와 Confusion 기술을 구별한다. 수치/관측/합법 후보는 그대로 유지한다.
지원 밖 설명 충돌은 제외한다. 추천세트 조건부 피해를 실제 숨은 세트의 보장으로 해석하지 않는다.
QA 지시문·QA 선택지는 배틀 행동 지시문·후보와 분리하고 GLM 전략은 사용하지 않는다.
canonical의 ID/규칙/묶음/표현/조건/State/질문/선택지/정답/근거/split과 비공개 evidence를 분리한다.
prepare/generate/validate/export만 제공하며 검증 완료 자료만 학습용 messages와 선택형으로 내보낸다.

검증된 장면의 질문 표현을 교정하는 generate --relabel-from은 같은 명세·engine·자료와 관측/계산기
source를 요구한다. spec/input/result/evidence를 보존하고 새 질문만 생성하며 provenance와 이전 판본을
남긴다. canonical의 State/후보와 질문 필드를 보호된 공개 투영에 직접 대조하고 전수 validate·의미 검토를
다시 거친 후 export한다. 질문·표현·실행 제어·검증 코드 외 source 변경에는 이 경로를 사용하지 않는다.

<a id="c-076--규칙-qa-학습-경계"></a>
## C-076 — 규칙 Q&A 학습 경계

D-161/EX-107의 학습 입력은 기존 messages system/user만이며 assistant는 target이다. canonical 관리 ID·규칙·정답 metadata·비공개 evidence는 입력에 합치지 않는다. 생성 prefix 일치·assistant-only loss·정답 예측 위치 logits·GPU1–3 UUID/공용 잠금·완전 checkpoint/test 선택 잠금은 EX-107을 따른다.

<a id="c-077--학습-tacit-배틀-경계"></a>
## C-077 — 학습 Tacit 배틀 경계

D-162/EX108은 공식관측·자기request·공개prefix·자기팀의 v6/RuleQA 공개State만 사용한다. 단일 option ID를 현재 합법명령에 연결하고 오류는 등록된 결정적 대체, 기술오류는 중단한다. EX107 adapter선택/재로딩·GPU1 UUID/잠금·일회예약을 gate로 삼는다. 세부원문은 EX108, viewer는 C047이다.


<a id="c-083--jevk5-규칙-선택형-학습"></a>
## C-083 — JevK5 규칙 선택형 학습

D169/EX113은 QA선택지와 배틀행동을 분리하고 공식 비Thinking 입력 마지막 위치의 선택지 제한 CE를 DDP forward로 계산한다. 완전checkpoint·test선택/보정잠금·원확률재로딩·자원 경계는 EX113을 따른다.


## C-084 — 학습 JevK5 실전 판독

D173/EX114는 기존v6 원정보와 합법후보를 유지하고 선택어댑터의 후보점수를 첫argmax로 연결한다. 사용자서버를 유지하고 별도GPU2/32768 임시서버의 정체성·자원·완료조건을 EX114로 고정한다. 본수집 소스변경/재경기0, 공급자판단 오류는 C046으로 격리한다.

## Gen9 타입 상성 전수 자료

D174/EP192 데이터는 타입/테라 조건만 질문 입력에 두고 multiplier/정답/계산근거는 target 또는 관리metadata로 분리한다. Showdown 전수대조와 커버리지검증을 통과한 자료만 새 경로로 내보낸다. 선택형은 기존 state_mc와 다른 명시적 schema이며 암묵적으로 학습기에 연결하지 않는다.

EP193은 원공격/방어/테라만 입력하는57차원 분류와 JevK5 마지막입력위치6후보 CE를 제공한다. 정답/근거/계산결과/그룹/가중치는 입력에서 제외한다. 고정배율 클래스와 문항별 후보인덱스는 별개이며 실제학습은 별도승인범위다.

## 상태이상 System 1 자료

EP195의 상태자료는 input.state/question만 모델 입력이며 target/oracle/근거/그룹/가중치는 별도다. 문항별2~5유효후보에 마지막입력위치 CE를 적용하며 정답completion0이다. hook 대조와 제어 Battle 메서드 확인은 실제 OU합법 경기/전체효과 검증과 구분한다.

## 행동우선도 System 1 자료

EP196은 input.state/question만 후보CE 입력으로 쓰고 oracle/정답/메타데이터를 분리한다. 정수기술우선도와같은구간fractional정렬을구분하고 native비Thinking 마지막입력위치의2~11후보를읽는다. 실제학습/기존실행기변경은자료생성범위밖이다.

## 날씨·영역 System 1 자료

EP197은input.state/question만입력하고정답/oracle/metadata를분리한다. 필드1.3배의고정소수점5325/4096을근거에기록하고답은근사값으로명시한다. 반무적gate검사는실제명중/행동가능성으로확대하지않는다. 기존모델/학습기·봉인은변경하지않는다.

## 실제 리플레이 KO System 1 자료

EP198은 공격 직전 전체 허용 공개 prefix와 actor/move/target만 입력한다. move행의 결과 flags·후속피해/기절·선수명/닉네임/승패/레이팅/ID는 입력에서 제외한다. 직접 target HP0+후속 faint를 원본 좌표에서 독립 감사하며 간접/불명확 프레임은 제외한다. 원본train만 사용하고 긴입력을절단하지않는다.

## 조건부 KO System 1 판정

EP199는명시조건/정확한HP/검증된범위를입력으로제공하고min>=HP, min<HP<=max, max<HP의3라벨을engine16롤및HP적용에대조한다. 원래결과/급소를라벨계산에사용하지않는다. 미검증원자료는targetnull/훈련사용false로표시하고기존봉인을보존한다.

## Smogon 전략 기반 역할 System 1

EP200은세트구성/질의역할정의만입력하고제목·본문·근거·출처·role목록·prior/usage를제외한다. 21역할의이진source-support와복수역할행렬의0은근거미확인을뜻한다. 긍정근거는원문문자좌표/UTF8해시와조건으로연결하며빈본문/outdated를보충하지않는다.

## 우선순위별 규칙 적용 System 1

EP201은 input.state/question만 모델에 전달하고 가능세계·oracle·정답·관리 정보를 분리한다. 1→5 개별 파일과 합본은 같은 표본이며 중복 합산하지 않는다. 제어 이벤트와 실제 턴 실행의 범위, 고정 피해·명중 조건을 문항에 명시한다. native 비Thinking 마지막 실제 입력 위치에서 문항별 2~7후보 CE를 적용하며 정답 completion은 없다. 정보 부족은 허용된 숨은 조건에 따라 사건의 확실성 등급이 갈릴 때만 사용한다.

## 전체 System One 학습

[D-180](decisions/D-180-jevk5-system1-full-training.md)의 [EX-116](experiments/EX-116-jevk5-system1-full-training.md)을 새 전체자료 학습·독립평가의 범위 한정 규범으로 채택한다. 새 구현은 `integration/jevk5_system1_training/`이며 기존 EX113과 자료 생성 계약은 보존한다.

## 전체 System One 선택모델 배틀

[D186](decisions/D-186-jevk5-system1-battle32.md)의 [EX123](experiments/EX-123-jevk5-system1-battle32.md)을 GPU1·2·3의선택epoch2 실전32 평가에한정해적용한다. 기존 EX116/114·서버·봉인은보존한다.
