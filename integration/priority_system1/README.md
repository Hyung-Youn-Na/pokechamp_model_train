# Gen9 행동 우선도 System 1 학습자료

설명문·CoT·assistant 정답 completion 없이 **후보 logits에서 답을 직접 선택하는 지도 판별 자료**다.
총 **10,160문항 / 15규칙군**이며, 실제 모델학습·forward·GPU 사용은 하지 않았다.

## 포함 범위

| 영역 | 문항 |
|---|---:|
| Gen9 표준 기술 목록의 기본 정수 우선도 | 685 |
| Prankster·Gale Wings(최대/비최대HP)·Triage의 우선도 변경 | 2,740 |
| 정수 우선도·실효 스피드·Trick Room의 두 행동 비교 | 3,872 |
| 같은 우선도 구간에서 먼저/나중 행동 효과 비교 | 2,816 |
| 대표 예외·성공 조건·필드 차단·행동 단계 | 47 |

세부 분모는 `coverage.json`, 규칙군별 예시는 `review_samples.json`에 있다.
표준 기술 필터는 고정 Dex의 `exists && gen<=9 && !isNonstandard && !isZ && !isMax`다.
이685개가 모두 OU에서 합법적인 종/세트에 채용 가능하다는 뜻은 아니다. 더블용 기술도 기본 우선도 참조에는 포함된다.

기본 우선도 구간은 `[-7,-6,-5,-4,-3,0,1,2,3,4,5]`다.
비교 문제는 이11구간×11구간×실효스피드4값×4값×TrickRoom2상태의 전수다.
스피드 값은50/100/200/400으로 고정했다. 상태·랭크·도구·필드 보정이 이미 반영된 **실효 스피드**를 입력한다.

## 구분해서 배우는 규칙

- 높은 정수 우선도가 먼저다. **Trick Room은 정수 우선도 순서를 뒤집지 않는다.**
- 같은 우선도 안에서는 먼저/나중 행동 효과를 적용하고, 그 조건도 같으면 실효 스피드로 비교한다.
- Trick Room은 이 범위에서 같은 순서 조건의 스피드 비교를 반대로 한다. 속도까지 같으면 고정 승자가 없는 **동속**이다.
- Quick Claw·Quick Draw의 발동은 정수 기술 우선도 상승과 다르다. 발동확률과 이미 발동한 상황을 분리했다.
- Prankster·Gale Wings·Triage는 명시된 조건에 따라 정수 우선도를 바꾼다. Grassy Glide는 별도 접지/필드 조건을 다룬다.
- Psychic Terrain의 우선도 공격 차단과 Prankster의 Dark 대상 차단은 행동 순서와 별개의 성공 조건이다.
- Sucker Punch·Protect는 우선도가 높아도 명시 조건에서 실패할 수 있다.
- 일반 선택 교체·테라스탈 발동·기술 실행은 서로 다른 행동 단계다.

대표 예외에는 Quick Claw/Mycelium Might, Stall/Lagging Tail, Grassy Glide, Psychic Terrain,
Sucker Punch·Protect, Trick Room 유지/재사용, Prankster/Dark, 교체/Tera 단계가 포함된다.
모든 특성·도구·기술 상호작용을 전수 검증한 것은 아니다. After You·Quash·Dancer 등의 전체 queue 재배열,
강제교체/피벗의 모든 타이밍, 턴 중 스피드 변화와 극단적 engine Speed wrap 사례는 이 자료의 전수범위 밖이다.
문항의 입력 시점에 주어진 행동 대기열/조건을 기준으로 답한다.

## System 1 학습 파일

- `all.choice.jsonl`: 구조화 상태·질문·후보와 target_index/target_distribution.
- `all.jevk5.tokens.jsonl`: 고정 JevK5 native 비Thinking 입력과 label_ids/target/expected.
- `canonical.jsonl`: 정답·oracle 근거가 있는 관리 원본. 통째로 입력하지 않는다.
- `coverage.json`, `validation.json`, `manifest.json`, `checksums.sha256`: 분모·검증·출처·무결성.
- `review_samples.json`: 규칙군별 대표 문항. 모델 입력이 아니다.
- `loss.py`: 문항별 후보 수를 지원하는 단일행 CE 함수.

선택형의 **`input.state`와 `input.question`만** 모델 입력이다.
정답·oracle·ID·규칙군·가중치는 입력에 합치지 않는다. 토큰행의 `input_ids`에는 정답문자/설명 target이 붙지 않는다.
`label_ids`는 현재 후보 문자 토큰, `target`은 후보순서 정답 인덱스다. 후보 수는2~11개이며 문항별로 순서를 섞었다.
손실은 `CE(마지막 실제 입력 위치의 유효후보 logits, target)`다. 추론은 같은 logits의 argmax로 끝난다.

```python
import json
import torch
from loss import choice_loss
row = json.loads(open('all.jevk5.tokens.jsonl').readline())
ids = torch.tensor([row['input_ids']], device=device)
# 별도로 적재·설정한 지원 모델을 사용하는 한 행 예시:
logits = model(input_ids=ids, logits_to_keep=1, use_cache=False).logits[0, -1]
loss = choice_loss(logits, row['label_ids'], row['target'])
```

기존 EX113 실행기는 고정 데이터/예산을 사용하므로 이 파일로 자동 교체하지 않는다.
배치 패딩을 쓸 때는 각 행의 마지막 실입력 위치·유효후보 수를 지켜야 한다.
전체completion SFT loss를 사용하지 않는다. System 1은 직접 판정 목적이지 모델의 실제 사고방식·속도 입증이 아니다.

## 검증·균형·출처

기술 기본 우선도는 고정 Dex 참조값이며 대표11구간 기준기술을 별도 확인했다.
특성·예외는 실제 Showdown hook/제어 Battle 메서드를 호출해 예상값과 대조했다.
순서 비교는 `Pokemon.getActionSpeed`와 `Battle.comparePriority`를 사용하며 독립 비교식·좌우교환·동률을 검사했다.
Quick Claw의 실제 기술우선도0과 행동 정렬값0.1도 별도 확인했다. 이는 실제 OU 합법 세트의 대전 결과가 아니다.
모든 행의 후보 유일정답·metadata 변조 입력불변·native template 동치·무절단 토큰·저장대응을 확인한다.

현재 전부 학습pool이며 validation/test를 만들지 않았다. 기존 상태이상·규칙QA와 개념이 겹칠 수 있다.
`metadata.rule_id`로 비중을 정할 수 있고 `inverse_rule_weight`는 각 규칙군 합계1이 되는 선택적 가중치다.
`semantic_group`/`inverse_group_weight`는 동일 문항의 표현 관리용이며 개념적 독립성을 보장하지 않는다.
가중치를 자동 적용하지 않으며 실제 학습 비중·평가 분할은 후속 계획에서 정한다.

원천: Pokémon Showdown `e64915c0eab066db1d3e732b1280386468dd7415`의
[기술/특성 규칙](https://github.com/smogon/pokemon-showdown/tree/e64915c0eab066db1d3e732b1280386468dd7415/data),
[행동 정렬](https://github.com/smogon/pokemon-showdown/blob/e64915c0eab066db1d3e732b1280386468dd7415/sim/battle.ts),
[행동 스피드](https://github.com/smogon/pokemon-showdown/blob/e64915c0eab066db1d3e732b1280386468dd7415/sim/pokemon.ts).
실제 built 소스 hash와 prompt 출처를 manifest에 보존하고 MIT/NOTICE를 동봉했다. 외부에 게시하지 않았다.
재생성은 `/workspace/scripts/priority-system1-data --output <새 경로>`다. 기존자료는 덮어쓰지 않는다.
