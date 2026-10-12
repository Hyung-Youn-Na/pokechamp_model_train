# 선봉 전용 규칙 자산

[C-040](../../../project_context/CONTRACTS.md#c-040-lead-components), D-061의 선봉 전송 전용 자산이다.
`effects/`의 v1 자산은 수정하지 않는다. `matchup-v2.txt`는 영어 전략 원문,
`rules-guide.txt`는 추가 필드 설명이다. 네 조합은 런타임에 기존 구조 설명과 결합하고 각 구성요소 및 결합 prompt hash를 봉인한다.

`node integration/pokechamp/lead_rules/extract.cjs <새 출력 디렉터리>`로 고정 Showdown
Gen9 Dex 자산과 provenance/LICENSE를 재추출한다. `provenance.json`은 commit, 자산/추출기/license hash와 추출 방법을 기록한다.
Dex 기본 종 열거에 없는 `cosmeticFormes`도 별도 펼쳐 공개 외형 폼을 보존한다.
타입 표는 18개 일반 공격 타입에 대한 비테라 기본 배율이며 Stellar·기술별 타입 예외·전체 피해 계산은 포함하지 않는다.
독 상태 `tox`의 타입 면역은 `psn`과 동일하게 조회한다. 예외 효과는 기존 상세 desc에서 확인한다.

가능 기술 범주는 날씨 변경(날씨 속성 및 Chilly Reception), 설치기 제거/교환
(Rapid Spin, Mortal Spin, Defog, Tidy Up, Court Change), Taunt/Encore,
자기 교체(`selfSwitch`), 우선도 공격(기본 양수 또는 조건부 `onModifyPriority`)으로 고정한다.
Gen9 OU `TeamValidator.validateSet`으로 각 종·특성·단일 기술을 검사한다.
필수 폼 도구 외 임의 세트/도구는 추가하지 않으며, 가능 특성 확인은 실제 learnset 기술로 검사한다.
이는 기술·특성의 주변적 가능성이지 네 기술 동시 호환 세트나 채택 확률이 아니다. Baton Pass/Shed Tail 등 금지 기술은 제외된다.

자기 슬롯 연결은 오직 그 슬롯의 공급된 `moves`를 사용한다. 공개 상대에는 실제 특성/기술을 추가하지 않고
별도 `lead_rules`의 가능 목록과 공통/조건별 폼 정보를 제공한다. 공개 마스킹 폼은 종족의 관련 폼들을 보존하며
OU 가능 목록이 빈 폼도 기본 사실을 유지한다. 종·기술 미해결은 입력 오류로 실패하며 추정으로 대체하지 않는다.
Smogon 세트·EV·도구·선택 확률은 런타임 자산에 포함하지 않는다.
