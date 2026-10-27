# Gen9 타입 System 1 판별 학습자료

설명문·CoT·assistant completion을 학습하지 않고 타입 상태에서 답을 직접 선택하는 자료다.
정답 라벨을 사용하는 **지도 분류/선택지 교차엔트로피 학습**이며, 비지도학습이나 RL 궤적 데이터가 아니다.
System 1은 이 직접 판정 방식의 목적을 뜻한다. 실제 모델의 사고 방식·속도·성능을 검증했다는 뜻은 아니다.

원자료 EP192의64,980경우(기본3,078 + 테라/스텔라61,902)를 보존한다. 기존 SFT와 서로 다른 독립 표본은 아니다.
순수 타입 상성만 다루며 자속·특성·도구·필드·기타기술예외는 제외한다. 실제 OU합법 종 조합이 아닌 합성 타입문제다.

## 1. 작은 분류기/MLP/encoder용

`base.classification.npz`와 `extension.classification.npz`는 다음 배열을 담는다.

- `X`: `[N,57]`, uint8. 공격타입19 one-hot + 원래방어타입18 multi-hot + 방어테라상태20 one-hot.
- `y`: `[N]`, int64. 클래스0..5는 `[0, 0.25, 0.5, 1, 2, 4]`배에 대응한다.
- `inverse_group_weight_subset`: 선택적 반복보정 가중치. 해당 파일 안에서 같은 계산 그룹의 합이1이다.

열 순서는 `schema.json`의 `feature_names`에 고정했다. 유효방어타입이나 중간 계산결과는 X에 넣지 않는다.
텍스트 버전 `{base,extension}.classification.jsonl`에는 같은 features/target_class/target_distribution과 metadata가 있다.
NPZ 행순서는 해당 JSONL과 같다. 모델 입력은 `X` 또는 `features`뿐이다.

```python
import numpy as np
import torch
from losses import class_loss

with np.load('base.classification.npz', allow_pickle=False) as data:
    x = torch.from_numpy(data['X'].astype('float32'))
    y = torch.from_numpy(data['y'])
# 이미 별도로 구성한 분류기에서:
logits = classifier(x)             # [N, 6]
loss = class_loss(logits, y)
```

## 2. JevK5/선택지 readout용

`{base,extension}.choice.jsonl`은 다음 구조다.

- `input.state`: attack_type, defender_types, defender_tera_type만 포함.
- `input.question`: 고정 판정 instructions와6개배율 criteria. 정답 위치는 문항별로 섞여 있다.
- `target_index`, `target_distribution`: 후보순서 기준 정답과 one-hot target.
- `metadata`: 식별자·그룹·선택적 가중치. 모델 입력에서 제외한다.

`{base,extension}.jevk5.tokens.jsonl`은 로컬 고정 JevK5 tokenizer로 준비한 직접 학습용 표현이다.

- `input_ids`: 공식 비Thinking system/user+빈 assistant generation prefix. **정답문자나 설명토큰을 붙이지 않았다.**
- `label_ids`: A..F의6개 단일토큰 ID.
- `target`: 후보순서의 정답 인덱스. 위 고정배율 class index와 다를 수 있다.
- `expected`: 후보순서 one-hot. softmax 전 logits에 CE를 적용한다.
- `option_ids`, `metadata`: 매핑/관리용. 추가 입력으로 연결하지 않는다.

학습은 `CE(logits[마지막 입력 위치, label_ids], target)`만 사용한다. 추론은 같은6개 logits의 argmax로 끝내며 생성토큰은 필요 없다.
이 데이터는 제한선택지 CE용이다. 일반 causal-LM trainer의 전체 token labels로 넣으면 의도한 목적과 달라진다.
공식 비Thinking prefix에 빈 `<think>...</think>`가 있지만 생성/지도할 reasoning은 없다.

```python
import json
import torch
from losses import class_loss

row = json.loads(open('base.jevk5.tokens.jsonl').readline())
ids = torch.tensor([row['input_ids']], device=device)
# 이미 적재한 지원 모델에서 한 행을 읽는 예시(이 패키지는 모델을 적재/학습하지 않음):
logits = model(input_ids=ids, logits_to_keep=1, use_cache=False).logits[0, -1]
scores = logits[row['label_ids']][None].float()
loss = class_loss(scores, torch.tensor([row['target']], device=device))
```

배치에서 패딩을 쓰는 경우 `losses.py`의 `choice_loss`는 attention_mask의 마지막 실토큰 위치를 사용한다.
예제는 `[B,L,V]` logits를 받으므로 메모리 효율화는 사용하는 모델에 맞게 별도로 구성한다.
기존 EX113 실행기는 고정경로·별도schema·예산을 사용하므로 이 자료를 넣고 그대로 실행하면 안 된다.
새 학습기에 데이터로 연결할 수 있게 구성했으며 기존모델/서빙/학습기를 수정하지 않았다.

## 반복·평가·검증

모든 행은 학습pool이다. train/validation/test를 만들지 않았으며 독립 성능평가 자료가 아니다.
실질 계산그룹은3,080개다. `metadata.semantic_group`은 반복 식별용이며 모델 입력이 아니다.
`inverse_group_weight_subset`은 기본/확장 각각의 그룹 반복 보정, `inverse_group_weight_all`은 합친pool의 보정이다.
둘을 곱하지 않는다. 기본/확장 비율·클래스 균형·평가 분할은 실제 후속 학습 계획에서 정한다.
같은 그룹을 임의 행단위로 나누면 답이 같은 계산이 train/test에 걸칠 수 있다.

원자료 봉인·정답을 확인하고 모든 행의 벡터/클래스/선택지 매핑과 저장파일 대응을 대조했다.
정답·근거·metadata를 바꿔도 입력이 같음을 전수검사했다. 공식 native template 동치·무절단 token 길이·단일문자 token을 확인했다.
`validation.json`과 `manifest.json`에 결과와 tokenizer/source 출처를 기록한다.
CPU 합성logits로 손실·gradient·패딩 위치를 검사했으며 실제 모델 forward·학습·GPU 사용은 없다.
JevK5 prompt의 라이선스/출처는 `PROMPT_LICENSE`와 `PROMPT_NOTICE`를 따른다.
재생성: `/workspace/scripts/type-system1-data --output <새 경로>`. 기존 자료 덮어쓰기는 거부한다.
