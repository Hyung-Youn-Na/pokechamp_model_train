# 조건부 확정 KO 판정 — System 1

이 자료의 명칭은 **조건부 확정 KO 판정 학습자료**다. 실제 리플레이의 관측 KO 라벨을 이름만 바꾼 자료가 아니다.

## 세 가지 학습 라벨

명중 판정 성공·비급소·단타·명시된 정확한 세트/상태에서의 검증된 최소/최대 피해와 대상 현재 HP를 비교한다.
타입 면역은 유지하며, 피격 이전 교체/회복·기절 없이 해당 피해 판정까지 도달한 상황을 가정한다.

| 표시 | 조건 |
|---|---|
| **조건부 확정 KO** | 최소 피해 ≥ 대상 현재 HP |
| **난수 KO 가능** | 최소 피해 < 대상 현재 HP ≤ 최대 피해 |
| **조건부 KO 불가** | 최대 피해 < 대상 현재 HP |

`min_damage == HP`는 확정 KO, `max_damage == HP`는 최소 피해도HP이상인 경우를 제외하면 난수 KO 가능이다.
정답은 원경기에서 급소가 났는지·실제로 KO했는지와 무관하게 계산한다.
이것은 **제공된 피해 계산기 범위의 KO 판정 과제**다. 원시 리플레이만으로 피해량을 예측하는 과제가 아니다.

## 기존 리플레이에 대한 표시

EP198의3,981개 원래 문제는 `original-replay-qualification.jsonl`에
**“정보 부족 — 원경기 조건부 KO 미판정”**으로 연결했다.
이는 원경기에 대해 실제로 KO불가라는 라벨이 아니며, 모든 가능한 공개정보 추론을 해봤다는 뜻도 아니다.
이번 자료에 원래 정확한 세트와 검증된 비급소 피해범위가 없으므로 **원래 관측 라벨을 조건부 정답으로 전환하지 않았다는 표시**다.
이 파일의 `use_as_conditional_training_target`은 false이고 target은 null이다. 이 행들을 정보부족 정답의 훈련셋으로 자동 사용하지 않는다.
원래 관측결과 데이터와 봉인은 변경하지 않았다.

## 새 학습 문제의 출처와 가정

리플레이 공개 prefix에서 현재 공격자 종·대상 종과 조건으로 제시한 기술을 가져온다.
**정확한 세트와 HP는 새로 명시한 제어 조건**이며 원경기의 숨은 세트·실제 HP를 복원한 값이 아니다.
원래 실제 KO/급소 결과를 새 라벨에 사용하지 않는다.

고정 조건:

- Gen9 단일 공격, 양측 레벨100·IV31·EV0·Hardy.
- No Ability·도구 없음·상태이상/랭크/날씨/필드/벽/volatile 없음·테라 없음.
- 명중 판정 성공, 비급소, 1타. 타입 면역은 적용한다.
- Focus Sash·Sturdy·Disguise·Substitute 등 KO 방지 효과 없음.
- 피해 난수85~100의16가지를 실제 Showdown getDamage로 계산한다.
- 대상 HP는1~최대HP 안의 명시된 경계값/최대HP다. 원래 리플레이의 HP백분율을 정확한 HP로 추정하지 않는다.

변동 위력·다단·강제급소·고정피해·조건부 폼·특수콜백/특수능력치 경로 등은 첫 판본에서 보수적으로 제외한다.
모든 기술·아이템·특성 상호작용이나 실제 OU 합법 종/세트 전수를 지원하지 않는다.
이 고정조건은 학습문제의 계산조건이며 실전 추천 세트가 아니다.

## System 1 파일과 사용

- `all.choice.jsonl`: `input.state`의 정확한 조건/HP/검증된 피해범위와 question/criteria를 입력으로 사용한다.
- `all.jevk5.tokens.jsonl`: native JevK5 비Thinking 입력, label_ids, target, expected.
- `canonical.jsonl`: 라벨/16피해값/원천 연결을 포함한 관리 원본. 전체를 입력하지 않는다.
- `original-replay-qualification.jsonl`: 기존3,981개 관측문제의 조건부 변환 미검증 표시.
- `calculation-evidence.json`: 프로필별16피해값과 실제engine HP적용 경계검증, 제외사유.
- `coverage.json`, `validation.json`, `manifest.json`, `checksums.sha256`: 실제 분모·검증·출처.

원래 경기ID·원천문항ID·정답·16개중KO개수는metadata/evidence에만 둔다.
`verified_noncritical_damage_range_hp`는 이 과제에서 사용하도록 **제공한 조건부 계산 근거**이며 target은3분류다.
설명·정답 completion을 붙이지 않고 마지막 실제 입력 위치의3개 후보 logits에 CE를 적용한다.

```python
import json
import torch
from loss import choice_loss
row = json.loads(open('all.jevk5.tokens.jsonl').readline())
ids = torch.tensor([row['input_ids']], device=device)
# 별도로 적재한 지원 모델을 사용하는 예시:
logits = model(input_ids=ids, logits_to_keep=1, use_cache=False).logits[0, -1]
loss = choice_loss(logits, row['label_ids'], row['target'])
```

실제 모델학습·forward·GPU 사용은 하지 않았다. 기존 EX113 학습기에 자동으로 연결하지 않는다.
모두 학습pool이며 독립 test/성능 입증이 아니다. 같은프로필·연결된원경기들을 분할할 때 묶어야 한다.
원자료의 균형표집 및 새 경계HP 문항은 자연스러운 실제 KO 발생률을 보존하지 않는다.

## 검증과 해석

최소/최대값만 임의로 만들지 않고16개 engine 피해값을 열거한다.
engine 원래randomizer와 정수 연산을 대조하고, 각 유효 HP 경계에서 실제 Pokemon.damage의HP0/기절 판정을 확인한다.
최솟값/최댓값 판정과16개전체롤의 KO개수(16/일부/0)가 일치해야 한다.
원래 관측라벨이 바뀌어도 새 계산프로필/라벨에는 영향을 주지 않는다.

Showdown `e64915c0eab066db1d3e732b1280386468dd7415`의 실제built소스hash와 원자료봉인을 기록한다.
원경기에는 적용하지 않은 No Ability/도구없음 등의 조건을 실제 사실처럼 사용하면 안 된다.
부모 리플레이 원천의 라이선스 미선언 경계와 로컬 제공 범위를 유지하며 외부에 게시하지 않았다.
Showdown MIT 및 JevK5 prompt 라이선스/NOTICE는 동봉했다.
재생성: `/workspace/scripts/conditional-ko-system1-data --output <새 경로>`.
