# Gen9 상태이상 System 1 학습자료

설명·CoT·assistant 정답문장을 생성하지 않고 **후보 점수에서 답을 바로 선택하는 지도 판별 학습자료**다.
총 **22,423문항 / 34규칙군**이다. 실제 모델학습·forward·GPU 사용은 하지 않았다.

## 내용

| 영역 | 문항 |
|---|---:|
| 주요 상태6 × 원래단일/복합타입171 × 테라상태20의 타입면역 | 20,520 |
| 전기자석파·뱀눈초리·버섯포자·도깨비불·맹독의 기술별 면역 | 855 |
| 부식(Corrosion)과 독/맹독의 타입면역 우회 | 684 |
| 테라스탈 후 기존 주요 상태 유지 | 114 |
| 능력의 상태 예방 | 72 |
| Electric/Misty Terrain·접지/반무적 조건 | 48 |
| 기존 주요 상태가 있는 경우의 새 상태 적용 | 42 |
| 맑음·Utility Umbrella와 얼음 | 12 |
| 혼란/풀죽음 예방 | 8 |
| 피해·속도·확률·기간·회복·OU 수면규칙 | 68 |

주요 상태는 **화상·마비·독·맹독·잠듦·얼음**이며, **혼란·풀죽음은 별도 volatile**로 구분한다.
34규칙군의 세부 분모는 `coverage.json`, 규칙별 대표 문항과 근거는 `review_samples.json`에서 확인한다.

- 화상 지속피해·일반 물리피해 감소, 근성·객기 예외, 특수기술과의 차이
- 마비 속도·속보, 행동불능 확률
- 일반 독/맹독 피해·누적상한·교체 후 카운터, 포이즌힐·매직가드
- 잠듦의 행동 판정 횟수·sleepUsable·잠자기, 얼음의 자연해동·불꽃 피해
- 혼란 자해확률·위력, 풀죽음의 당해 턴 효과
- 자연회복·리샘/유루열매·탈피·촉촉바디와 조건부 회복

## 범위와 주의할 구분

고정된 Showdown Gen9 구현을 기준으로 한 **합성 규칙 문제**다. 실제 OU 합법 종/특성/세트 목록이 아니다.
타입×테라×상태 면역만 전수이며 모든 특성·도구·기술·상태 조합을 전수지원하지 않는다.
날씨/필드·반무적은 명시한 gate만 검사하는 문제가 있으며 실제 기술 명중 성공을 주장하지 않는다.
수치피해 예제는 정수 계산이 명확한 최대HP/현재HP를 사용한다. 모든 HP 반올림 경계를 망라하지 않는다.

로컬 Gen9OU는 **Sleep Moves Clause**를 쓰므로 상대에게 수면을 유발하는 기술의 포맷합법성과
게임 자체의 잠듦 효과를 구분한다. Spore를 이용한 면역 문제는 포맷금지를 제외한 Gen9 메커니즘 문제로 명시했다.
타입면역 문제의 “잠듦 허용”이 OU에서 수면기술을 사용할 수 있다는 뜻은 아니다. 잠자기(Rest)는 별도 규칙이다.
얼음은 freeze이며 Frostbite를 이 포맷의 상태로 추가하지 않았다.

마비·얼음·혼란의 확률 문제는 **그 상태의 행동 판정에 도달했을 때**를 묻는다.
수면/풀죽음 등이 먼저 막으면 뒤의 판정이 실행되지 않을 수 있으므로 확률을 무조건 독립으로 곱하지 않는다.
혼란 자해·탈피는 고정 엔진의 정확한33/100을 라벨로 사용한다. 실기 게임의1/3과 동일하다고 주장하지 않는다.
확률 라벨은 한 번의 난수 결과에서 추측하지 않고 함수의 확률 인자와 양쪽 분기를 검사했다.

## 파일·학습 방법

- `all.choice.jsonl`: 모델 독립 선택형 입력과 후보별 정답.
- `all.jevk5.tokens.jsonl`: 공식 JevK5 비Thinking tokenizer 입력과 단일문자 후보 토큰.
- `canonical.jsonl`: 정답·oracle 근거를 포함한 관리 원본. 전체를 모델 입력으로 쓰면 안 된다.
- `coverage.json`, `validation.json`, `manifest.json`, `checksums.sha256`: 분모·검증·출처·무결성.
- `review_samples.json`: 규칙별 예시와 검증 근거. 학습 입력이 아니다.
- `loss.py`: 후보 수가 다른 문항을 지원하는 단일행 CE 예제.

선택형 행에서 **`input.state`와 `input.question`만 입력**이다.
`target_index`/`target_distribution`은 정답 target이며 metadata의 ID·rule·group·가중치는 입력에서 제외한다.
토큰행의 `input_ids`에는 정답문자나 설명 completion이 없다. `label_ids`는 현재 문항의 유효후보 문자토큰,
`target`은 후보순서 인덱스, `expected`는 같은 순서의 one-hot이다. 문항별 후보 수는2~5개다.

```python
import json
import torch
from loss import choice_loss

row = json.loads(open('all.jevk5.tokens.jsonl').readline())
ids = torch.tensor([row['input_ids']], device=device)
# 별도 승인/설정으로 적재한 JevK5 계열 모델에서 한 행을 읽는 예시:
logits = model(input_ids=ids, logits_to_keep=1, use_cache=False).logits[0, -1]
loss = choice_loss(logits, row['label_ids'], row['target'])
```

손실은 `CE(마지막 실제 입력 위치의 유효후보 logits, target)`이다. 전체 completion SFT loss를 사용하지 않는다.
추론은 같은 후보 logits의 argmax로 답을 고르며 생성토큰이 필요 없다. 공식 prefix의 빈 think 구간은 reasoning target이 아니다.
배치패딩을 도입하면 각 행의 마지막 실입력 위치와 유효후보 수를 지켜야 한다.
기존 EX113 학습기는 고정 데이터/실험 규격이므로 이 파일로 자동 교체하지 않는다.

## 균형·검증·출처

현재 전부 학습pool이며 별도 validation/test가 없다. 기존 규칙QA와 지식이 겹칠 수 있어 독립평가로 간주하지 않는다.
타입면역20520행이 많으므로 `metadata.rule_id`로 묶어 후속 학습에서 비중을 정할 수 있다.
`inverse_rule_weight`는 각 규칙군 합계1, `inverse_group_weight`는 같은 의미그룹 합계1인 선택적 가중치다.
둘은 서로 다른 균형 목적이며 자동으로 곱하거나 학습에 적용하지 않는다. 실제비중은 후속 계획에서 정한다.
같은 `semantic_group`을 행단위로 나눠 학습·평가에 동시에 넣지 않는다. 분할만으로 다른 규칙군의 개념중복이 사라지는 것은 아니다.

전수 oracle 정답 대조·원라벨/후보/저장행 대응·metadata 변조시 입력불변·native template 동치·무절단 길이를 확인한다.
Node oracle은 직접 Dex/Pokemon 메서드·condition/ability/item hook·OU rule table과 제어된 Battle 메서드를 사용한다.
일부 hook의 주변효과를 명시적으로 제거했고, 실제 포맷대전 전체를 재현했다는 주장은 하지 않는다.
첫 준비 검사에서 Magma Armor의 별도 면역 hook과 직접기술실행의 PP준비를 교정했으며 최종자료에 실패행을 넣지 않았다.

원천: Pokémon Showdown `e64915c0eab066db1d3e732b1280386468dd7415`의
[data/conditions.ts](https://github.com/smogon/pokemon-showdown/blob/e64915c0eab066db1d3e732b1280386468dd7415/data/conditions.ts),
[data/abilities.ts](https://github.com/smogon/pokemon-showdown/blob/e64915c0eab066db1d3e732b1280386468dd7415/data/abilities.ts),
[data/moves.ts](https://github.com/smogon/pokemon-showdown/blob/e64915c0eab066db1d3e732b1280386468dd7415/data/moves.ts) 등.
실제 built 소스의 hash도 manifest에 보존한다. Showdown MIT 및 JevK5 prompt 라이선스/NOTICE를 동봉했다.
이 자료는 외부에 게시하지 않았다. 재생성은 `/workspace/scripts/status-system1-data --output <새 경로>`로 수행한다.
