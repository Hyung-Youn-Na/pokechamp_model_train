# Gen9 타입 상성 전수 학습 데이터 v1

Gen9 OU에서 사용하는 9세대 타입 규칙의 **합성 전수 계산 문제**다.
실제 OU 합법 포켓몬 종·세트의 목록이나 실제 배틀 표본이 아니다. 실재하지 않는 타입 조합도 학습용으로 포함한다.

## 범위와 문항 수

| 자료 | 조합 | 문항 수 |
|---|---|---:|
| 기본 | 표준 공격타입18 × 방어타입171(단일18 + 순서 없는 서로 다른 복합153) | 3,078 |
| 테라·스텔라 확장 | 아래 전체에서 기본을 제외 | 61,902 |
| 전체 | 공격타입19 × 원래 방어타입171 × 방어상태20(미테라+일반테라18+스텔라) | 64,980 |

Stellar는 일반적인 기본 방어 타입으로 취급하지 않는다. Stellar 공격은 공격자가 이미 Stellar 테라스탈한 상태의 Tera Blast다.
일반 테라스탈은 기존 방어 타입을 테라 타입 하나로 바꾸고, 스텔라는 기존 방어 타입을 유지한다.
Stellar Tera Blast는 상대 미테라 시1배, 일반/스텔라 테라 상태이면2배다. 복합타입이라고4배가 되지 않는다.

정답은 `0 / 0.25 / 0.5 / 1 / 2 / 4` 중 하나인 **타입 상성 배율**이다.
자속(STAB), 특성(예: Levitate), 도구, 날씨, 필드, 접지 변경, 추가 제3타입, 무타입 및
Freeze-Dry/Flying Press/Thousand Arrows 등 기술별 예외는 제외한다. 위에 명시한 Stellar Tera Blast 상성 규칙은 포함한다.
종별 기술 습득·테라 제한도 판정하지 않는다. 피해량·KO확률·최적행동·공격자 자속 배율 데이터가 아니다.

예: Electric→Water/Ground = 2×0 = 0배. 같은 방어자가 Water로 테라하면2배이며, Stellar로 테라하면0배를 유지한다.
Fire→Water/Dragon = 0.5×0.5 = 0.25배, Ice→Dragon/Flying = 2×2 = 4배다.

## 파일과 학습 입력

- `exports/base.messages.jsonl`: 기본 3,078문항의 영어 SFT 대화. 먼저 기본 타입 계산을 학습할 때 사용한다.
- `exports/extension.messages.jsonl`: 테라·스텔라 61,902문항의 SFT 대화.
- `exports/{base,extension}.multiple_choice.jsonl`: 같은 문항의 6지선다 표현. 위치는 문항 ID 해시로 결정적으로 섞는다.
- `exports/{base,extension}.csv`: 정답·분해 계수·유효 방어 타입을 확인하는 표.
- `canonical.jsonl`: 입력조건과 정답·근거·식별자·그룹을 보존한 관리 원본.
- `examples.json`, `type_chart.json`: 예시 및 사용한 타입표.
- `validation.json`, `manifest.json`, `checksums.sha256`: 검증·출처·파일 무결성.
- `generator-source/`, `SHOWDOWN_LICENSE`: 생성 소스 사본과 사용한 Showdown 라이선스.

SFT에서는 **`messages`만** 학습기에 넘긴다. system/user는 입력이고 assistant는 target이다.
`id`와 `semantic_group`은 관리용이며 모델 입력에 합치지 않는다.
선택형에서는 `system`, `question`, `options`만 입력으로 사용하고 `answer_id`가 정답 target이다.
`rationale`은 설명 target이지 질문 입력이 아니다. 기존 JevK5 `state_mc` 로더와 다른 schema이므로 전용 변환이 필요하다.
canonical/CSV의 `multiplier`, `factors`, `effective_defender_types` 등을 입력에 넣으면 정답 누출이 된다.

## 중복과 평가 경계

전체는 **학습 pool**이며 validation/test로 자동 분할하지 않았다. 모든 경우를 학습에 넣고 같은 자료로 독립 정확도를 주장하면 안 된다.
`semantic_group`은 공격타입·유효방어타입(스텔라 공격은 상대 테라 여부)이 같은 계산을 묶는다.
총64,980개 상황은64,980개의 독립 상성 사실이 아니다. 기본3,078계산과 스텔라2계산으로 축약된다.
확장에는 원래 타입만 다른 같은 정답/계산이 많이 포함된다. 전체를 균등 학습하면 단일 테라방어 문제가 과대표집된다.
기본과 확장을 별도로 제공하므로 후속 학습 목적에 맞게 비중을 정해야 한다. 본 작업에서 비중 튜닝이나 모델학습은 하지 않았다.
SFT/선택형/CSV는 같은 문항의 다른 표현이며 독립 표본으로 합산하지 않는다.
기존 규칙QA 데이터와 타입지식이 겹칠 수 있어 기존 test와 독립인 새 평가셋으로 취급하지 않는다.

## 정답·검증·출처

로컬 Pokémon Showdown commit `e64915c0eab066db1d3e732b1280386468dd7415`의 Gen9 타입표에서 Python 곱셈으로 정답을 계산했다.
별도 Node oracle이 실제 built `Dex.getImmunity`와 `Pokemon.getTypes/runEffectiveness`를 호출해 전체64,980건과 타입순서 반전을 대조한다.
oracle의 Type/Effectiveness 이벤트는 통과 함수로 고정해 범위 밖 특성·도구·기술효과를 제거했다. 실제 경기 시뮬레이션 결과라는 뜻은 아니다.
Cartesian 누락/중복·6개 선택지 유일정답·경계11사례·출력파일 원본대조를 함께 검사한다.

- [Showdown 타입표](https://github.com/smogon/pokemon-showdown/blob/e64915c0eab066db1d3e732b1280386468dd7415/data/typechart.ts)
- [Showdown Pokemon 타입/상성 구현](https://github.com/smogon/pokemon-showdown/blob/e64915c0eab066db1d3e732b1280386468dd7415/sim/pokemon.ts)
- [Smogon의 Stellar 연구 기록](https://www.smogon.com/forums/threads/scarlet-violet-battle-mechanics-research.3709545/page-48)

Showdown은 동봉한 MIT 라이선스를 따른다. Pokémon 명칭·상표 등은 해당 권리자에게 속한다.
이 로컬 생성물을 저장소의 다른 구성요소 라이선스로 자동 재표시하거나 외부에 게시하지 않았다.
재생성 명령은 `/workspace/scripts/type-matchup-dataset --output <새 경로>`다. 기존 출력 덮어쓰기를 거부한다.
EP192/D174 범위이며 GPU·모델추론·실제 학습·배틀 평가는 수행하지 않았다.
