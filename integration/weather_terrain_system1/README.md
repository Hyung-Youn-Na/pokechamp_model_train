# Gen9 날씨·영역 System 1 학습자료

설명·CoT·assistant 정답 completion 없이 **유효 후보 logits에서 바로 답을 선택하는 지도 판별 자료**다.
총 **12,178문항·22개 규칙군**이다. 실제 모델학습·forward·GPU 사용은 하지 않았다. 전체는 학습pool이며 독립 평가셋이 아니다.

## 범위

- 날씨: **맑음·비·모래바람·눈**, 날씨 없음.
- 영역: **일렉트릭·그래스·미스트·사이코필드**, 필드 없음.
- 날씨에 따른 피해 보정, 모래의 바위 타입 특방/눈의 얼음 타입 방어, 모래 피해의 타입 면역.
- 공격자/방어자 접지에 따른 필드 위력 보정, 특정 지면 기술 완화, 필드의 회복·예방 효과.
- 지속 시간·확장 도구, 날씨/필드 공존·덮어쓰기, 대표 특성·도구·기술 예외.

타입/테라 관련 검사는 **171타입조합 ×20테라상태 ×3검사 =10,260문항**이다.
일반 날씨 피해 보정은5날씨×18기술타입×공격자/방어자우산2²=360문항,
필드 위력 보정은5필드×18기술타입×양측접지/반무적2⁴=1,440문항,
그래스필드의 특정 지면 기술 대조는16문항이다. 지속/회복/예방/대표기술 등 제어 예외102문항을 추가했다. 세부 분모는 `coverage.json`을 따른다.

이것은 **고정 Showdown Gen9 규칙의 합성 문제**이며 실제 OU 합법 종/세트의 전수 목록이 아니다.
명시한 유한 그리드만 전수다. 모든 특성·도구·기술·더블 상호작용을 포함하지 않는다.
원시날씨·Delta Stream·이전세대 우박·Trick/Magic/Wonder Room 전체는 이 자료의 범위 밖이다.
특성 예제는 쓱쓱·엽록소·모래헤치기·눈치우기 및 날씨 억제 등을 다루며, Protosynthesis·Quark Drive·Solar Power는 포함하지 않았다.
상태이상/우선도 자료와 개념이 겹칠 수 있으며 별도 독립 지식 표본으로 합산하지 않는다.

## 구분해서 학습하는 내용

- **눈은 우박이 아니다.** Gen9 눈은 얼음 타입 방어를 높이며 자체 잔여 피해를 주지 않는다.
- 모래는 바위 타입 특방을 높이고, 바위·땅·강철의 타입 면역과 그 외 피해 방지 효과를 구분한다.
- 날씨와 필드는 서로 다른 층이다. 한 날씨와 한 필드가 공존할 수 있고, 같은 층의 새 효과는 기존 효과를 대체한다.
- 필드 기술 강화는 보통 공격자의 접지, 미스트필드의 드래곤 완화는 방어자의 접지를 본다.
- **미스트필드는 페어리 기술을 강화하지 않는다.** 그래스필드는 모든 땅 기술을 일괄 약화하지 않는다.
- 위력 보정·피해 보정·능력치 보정·최종 HP 변화는 다른 값이다. 문항에서 요청하는 값을 읽는다.
- 보통 “1.3배”라고 부르는 필드 위력 보정은 이 엔진의 고정소수점 `[5325,4096]`이며 답은 `approximately 1.3x`로 표기했다.
- Utility Umbrella의 공격자/방어자 역할과 Hydro Steam 예외를 분리한다.
- Cloud Nine/Air Lock의 날씨 억제는 남은 날씨 정보를 삭제하는 것과 다르다.

반무적 상태가 들어간 일부 문제는 해당 hook의 적용 조건만 검사한다. 실제로 기술이 실행·명중할 수 있다는 뜻이 아니다.
수치 예제는 명시한 HP·회복 가능량을 기준으로 하며 모든 반올림·최소피해 경계를 전수지원하지 않는다.

## 파일과 System 1 손실

- `all.choice.jsonl`: `input.state`/`input.question`과 후보순서 기준 target.
- `all.jevk5.tokens.jsonl`: JevK5 공식 비Thinking 입력토큰과 후보 label_ids/target/expected.
- `canonical.jsonl`: 정답·oracle 근거가 포함된 관리 원본. 통째로 입력하지 않는다.
- `coverage.json`, `validation.json`, `manifest.json`, `checksums.sha256`: 분모·검증·출처·무결성.
- `review_samples.json`: 규칙군별 대표 사례. 학습 입력이 아니다.
- `loss.py`: 후보 수에 맞춰 마지막 위치의 CE를 계산하는 단일행 예제.

**입력은 `input.state`와 `input.question`만** 사용한다. target·oracle·ID·그룹·가중치는 입력에서 제외한다.
토큰행에는 정답문자·설명 completion이 붙지 않는다. `label_ids`는 유효후보 문자 토큰,
`target`은 현재 후보순서의 정답 인덱스, `expected`는 같은 순서의 one-hot이다.

```python
import json
import torch
from loss import choice_loss
row = json.loads(open('all.jevk5.tokens.jsonl').readline())
ids = torch.tensor([row['input_ids']], device=device)
# 별도 설정/승인으로 이미 적재한 지원 모델을 사용하는 한 행 예시:
logits = model(input_ids=ids, logits_to_keep=1, use_cache=False).logits[0, -1]
loss = choice_loss(logits, row['label_ids'], row['target'])
```

`CE(마지막 실제 입력 위치의 유효후보 logits, target)`만 계산한다. 전체 completion SFT loss를 사용하지 않는다.
추론도 같은 후보 logits의 argmax로 답을 선택한다. 패딩 배치에서는 각 행의 실입력 끝과 유효후보 수를 지켜야 한다.
기존 EX113 실행기를 이 자료로 자동 교체하지 않는다. System 1은 직접판정 목적이며 실제 모델사고방식·성능 입증이 아니다.

## 검증·가중치·출처

고정 Dex/Pokemon 메서드·condition/ability/item/move hooks와 제어 Battle 메서드를 실제 호출해 예상값과 대조했다.
모든 행의 후보 유일정답·metadata 변조시 입력불변·native template 동치·무절단 토큰·저장대응을 검사한다.
후보 CE는 합성 logits로 수치값·gradient·순서불변·비후보 제외를 확인하며 실제 모델을 적재하지 않는다.

타입 그리드가 많으므로 `metadata.rule_id`와 선택적 `inverse_rule_weight`로 규칙군 비중을 조절할 수 있다.
`inverse_group_weight`와 `semantic_group`은 문항 관리용이며 개념 독립성을 보장하지 않는다.
가중치를 자동 적용하거나 함께 곱하지 않는다. 실제 혼합 비중·평가 분할은 후속 학습 계획에서 정한다.

원천은 로컬 [Pokémon Showdown](https://github.com/smogon/pokemon-showdown)의
`e64915c0eab066db1d3e732b1280386468dd7415`이며 실제 built 소스의 hash도 manifest에 보존한다.
Showdown MIT와 JevK5 prompt 라이선스/NOTICE를 동봉했다. 기존 자료·모델·서빙은 변경하지 않았고 외부에 게시하지 않았다.
재생성은 `/workspace/scripts/weather-terrain-system1-data --output <새 경로>`다. 기존 출력 덮어쓰기는 거부한다.
