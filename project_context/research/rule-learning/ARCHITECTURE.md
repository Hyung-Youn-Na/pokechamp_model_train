# 규칙 이해 학습·적용 — 구성 설명

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="showdown-규칙-qa-데이터-경로-d-159--c-074"></a>
## Showdown 규칙 Q&A 데이터 경로 (D-159 / C-074)

`integration/pokechamp/rule_qa/`와 `scripts/pokechamp-ruleqa`가 별도 데이터 생성 경로다.
Gen9 OU 팀 validator와 CPU simulator가 제어 장면/선택 경계/독립 oracle 분기를 만들고,
`state.Builder`가 actor 공개 prefix와 자기 request로 공식 관측·v6·names-v1을 재사용한다.
배틀 행동 지시문은 QA 입력에 넣지 않고 원 State/실제 후보와 QA 선택지를 분리한다.
데이터 전용 confusion 설명 교정은 원 v6와 별도로 검증한다.

공개 사실의 질문 판정과 실제 Showdown/Dex/기존 계산기 대조 후, 동일 핵심 사실·동일 State를
공유하는 원천 묶음을 연결해 분할한다. canonical의 세 표현에서 SFT messages와 선택형을 만든다.
전수 의미/경계/분할/토큰 검사와96상황 별도 의미 검토가 export를 차단하는 gate다.
검증된 동일 장면의 표현 교정은 보호된 scene 구성요소를 유지하는 relabel 경로로 기록한다.
[완료/검증](plans/EP-169-showdown-ruleqa.md) · [구현 안내](../../../integration/pokechamp/rule_qa/README.md).

<a id="tacit-규칙-qa-학습-경로-d-161--c-076"></a>
## Tacit 규칙 Q&A 학습 경로 (D-161 / C-076)

`integration/pokechamp/rule_qa_training/`의 CPU controller가 기존 messages/canonical을 검증·토큰화하고,
물리GPU1·2·3 공용 잠금과 UUID를 설정한 뒤 DDP worker3개를 시작한다. assistant 위치 logits의
문항 평균 loss로 LoRA를 학습한다. validation 선택과 test 잠금을 분리하며 저장 adapter를 재로딩한다.
실험 원문은 [EX-107](experiments/EX-107-tacit-ruleqa-lora.md), CLI/출력은 [안내](../../../integration/pokechamp/rule_qa_training/README.md)를 따른다.

<a id="학습-tacit-실전-예약-경로-d-162--c-077"></a>
## 학습 Tacit 실전 예약 경로 (D-162 / C-077)

`integration/tacit_ruleqa_battle/`은 EX106의 관측/전송/감사/뷰어 경계를 분리 계승한다.
EX107의 선택 adapter와 재로딩 완료 후 GPU1 단독 서버에서 전체 공개State의 행동ID를 생성한다.
`scripts/tacit-ruleqa-battle schedule`의 단일 예약은 prepare→6gate→32경기→감사/뷰어/반환을 수행한다.
실행 조건은 [EX108](experiments/EX-108-tacit-ruleqa-battle32.md), 운영은 [안내](../../../integration/tacit_ruleqa_battle/README.md)를 따른다.


<a id="jevk5-규칙-선택형-추가-lora"></a>
## JevK5 규칙 선택형 추가 LoRA

`integration/jevk5_ruleqa_training/`과 `scripts/jevk5-ruleqa-train`은 EX113 전용 독립 경로다.
원state_mc→공식비Thinking prompt→마지막위치 선택지 CE/DDP→validation 선택/보정→test→비병합export로 이어진다.
순차모델적재·공용GPU잠금·hostRSS감시·완전checkpoint와 출력봉인을 포함한다.
조건은 [EX113](experiments/EX-113-jevk5-ruleqa-lora.md), 운영은 [안내](../../../integration/jevk5_ruleqa_training/README.md).


## 학습 JevK5 규칙 LoRA 실전32

`integration/jevk5_ruleqa_battle/`과 `scripts/jevk5-ruleqa-battle`은 EX114 독립 경로다.
EX111의 v6판독/감사를 분리계승하고 GPU2의32768토큰 임시동일모델서버를 소유·정리한다.
사용자GPU1서버와 EX113 어댑터/봉인은 유지한다. UIv1 기본5탭 뒤 프롬프트·선택지확률·선택/전송을 둔다.
조건·완료는 [EX114](experiments/EX-114-jevk5-ruleqa-battle32.md), 선행검증은 [EP191](plans/EP-191-jevk5-ruleqa-battle32.md).

## Gen9 타입 상성 전수 자료

integration/type_matchup_dataset은 고정 Showdown 타입표→Python 전수조합/계산→Node Dex/Pokemon 대조→SFT/선택형/CSV 내보내기의 CPU 경로다. 기존 모델·배틀·규칙QA 소스/봉인은 변경하지 않는다. 세부 조건과 결과는 [EP192](plans/EP-192-gen9-type-matchup-dataset.md)에 연결한다.

integration/type_system1 및 scripts/type-system1-data는 EP192 봉인을 읽어 JSONL/NPZ와 CPU native tokenizer 입력을 새로 만든다. 기존 EX113 실행기는 변경하지 않으며 재사용승인이 아니다. [EP193](plans/EP-193-gen9-type-system1-data.md)에 검증/출력을 연결한다.

## 상태이상 System 1 자료

integration/status_system1은 core.cjs의 타입·상태 gate와 facts.cjs의효과/치료 hook·제어damage oracle을 build.py로 검증·토큰화한다. scripts/status-system1-data는 CPU자료생성만 수행하며 기존모델/학습기를 변경하지 않는다. [EP195](plans/EP-195-gen9-status-system1-data.md)에출처/교정/결과를연결한다.

## 행동우선도 System 1 자료

integration/priority_system1의 core.cjs는 Dex기술/특성과순서비교를, facts.cjs는제어예외hooks/queue/실행메서드를대조한다. build.py가입력분리와native토큰을검증하고 scripts/priority-system1-data로새자료만생성한다. [EP196](plans/EP-196-gen9-priority-system1-data.md)에증거를연결한다.

## 날씨·영역 System 1 자료

integration/weather_terrain_system1의core.cjs는타입/테라·날씨/필드그리드, facts.cjs는제어효과/유지/예외를검증한다. build.py가native비Thinking선택CE자료를새경로로생성한다. scripts/weather-terrain-system1-data 및 [EP197](plans/EP-197-gen9-weather-terrain-system1-data.md)에출처/결과를연결한다.

## 실제 리플레이 KO System 1 자료

integration/replay_ko_system1은 train Parquet→보호ID/팀제외→parser.py 공개prefix/관측라벨→audit.py 독립원본대조→native토큰/선택CE자료로 이어진다. scripts/replay-ko-system1-data는CPU자료생성전용이다. 원본경기사본은source-evidence에보존하고다운로드묶음에서제외한다. [EP198](plans/EP-198-replay-ko-system1-data.md)에근거를연결한다.

## 조건부 KO System 1 판정

integration/conditional_ko_system1의calculate.cjs는고정프로필의16난수피해와HP경계를검증한다. build.py가원자료자격표시와별도조건부판정문항을만든다. scripts/conditional-ko-system1-data는CPU자료전용이며 [EP199](plans/EP-199-conditional-ko-system1-data.md)에출처/범위를연결한다.

## Smogon 전략 기반 역할 System 1

integration/smogon_role_system1은EP175 sets/strategies와분리주석177개를입력으로source-support문항·복수역할행렬·한국어CSV를생성한다. scripts/smogon-role-system1-data가native선택CE입력/누출/근거좌표를검증한다. [EP200](plans/EP-200-smogon-role-system1-data.md)에주석/교차검토/출력을연결한다.

## 우선순위별 규칙 적용 System 1

integration/mechanics_system1의 p1~p5.cjs는 고정 엔진과 독립 예상값으로 각 영역을 검증한다. generate.cjs는 1→5 순으로 결합하고 build.py는 입력 투영·선택지 순서·native token·저장 대응을 검증하여 개별 파일/합본·CSV를 만든다. scripts/mechanics-system1-data는 CPU 자료 생성 전용이다. [EP201](plans/EP-201-gen9-mechanics-system1-data.md)에 검토·교정·내보내기 근거를 연결한다.

## 전체 System One 학습

[D-180](decisions/D-180-jevk5-system1-full-training.md)의 [EX-116](experiments/EX-116-jevk5-system1-full-training.md)을 새 전체자료 학습·독립평가의 범위 한정 규범으로 채택한다. 새 구현은 `integration/jevk5_system1_training/`이며 기존 EX113과 자료 생성 계약은 보존한다.

## 전체 System One 선택모델 배틀

[D186](decisions/D-186-jevk5-system1-battle32.md)의 [EX123](experiments/EX-123-jevk5-system1-battle32.md)을 GPU1·2·3의선택epoch2 실전32 평가에한정해적용한다. 기존 EX116/114·서버·봉인은보존한다.
