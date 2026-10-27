# Smogon 전략 기반 포켓몬 역할 — System 1

**2026-10-19에 수집한 Smogon Gen9 OU 전략 자료**를 기준으로 만든 역할 근거 판별 데이터다.
기존409종 역할 DB의 추론 라벨을 정답으로 가져오지 않았다. 실제 모델학습·forward·GPU 사용은 하지 않았다.

## 원천과 범위

EP175 보관본의215세트 중 사이트에서 outdated로 표시되지 않은208세트를 구분하고,
그중 본문이 있는 **177세트·92종**을 주석 대상으로 삼았다. 현행 빈본문31세트와 오래된7세트는 제외했다.
“현행”은 수집 당시 사이트 표시이며 독립적인 최신 메타 판정은 아니다. 2026-10-19 이후 사이트 변경을 새로 수집한 자료가 아니다.
공유 폼의 중복은 원천 sets.jsonl에서 제거되어 있다. 입력 구성까지 같은 항목은 묶어 긍정근거 합집합을 사용한다.

포함 역할은21개다: 벽 돌파, 랭크업 스위퍼, 후반 정리, 리벤지 킬러, 스피드 제어,
공격/수비 피벗, 물리/특수막이, 수비 체크, 설치기 담당·제거·유지·억제, 상태이상 유포,
팀 회복, 날씨·필드·벽 전개, 장기전 방해, 강제교체. 세부 정의는 `roles.json`에 있다.
설치 예방(Magic Bounce 등), 이미 깔린 설치물 제거, 아군 설치물 제거 방해를 서로 구분한다.

## 라벨의 정확한 의미

각 세트의 본문을 읽고 **해당 세트 자신의 역할**로 근거가 확인되는 항목을 주석했다.
팀원·상대의 역할을 주어와 혼동하지 않았고, 기술을 보유했다는 이유만으로 역할을 추가하지 않는다.
설명에만 제안되고 구조화된 기술/도구/테라 선택지에 없는 대안에만 의존하는 역할은 제외한다.
같은 세트가 여러 역할을 가질 수 있으며 하나의 주역할을 강제하지 않는다.

각 질문의 두 답은 다음과 같다.

- `Supported by the included Smogon analysis`: 해당 세트 또는 목록에 있는 변형을 해당 역할로 뒷받침하는 근거가 주석되어 있다.
- `Not established by the included analysis annotation`: 포함된 분석에 대해 채택한 주석에서 근거가 확인되지 않았다.

두 번째 답은 **그 포켓몬이 실제로 그 역할을 수행할 수 없다는 뜻이 아니다.**
첫 번째 답도 현재 경기의 실제 역할·최적 행동·승률을 보장하지 않는다.
이는 Smogon 원문에 근거해 Codex가 작성한 주석이며, Smogon이 제공한 공식 role 라벨이나 인간 블라인드 검토 결과가 아니다.

세트의 여러 기술/도구/테라 대안은 그대로 보존한다. 긍정역할은 적어도 하나의 명시된 변형에서 성립할 수 있으며,
모든 선택지 조합에 같은 역할이 적용된다는 뜻은 아니다. 조건은 annotation 근거에 별도로 기록했다.

## 모델 입력과 System 1 형식

입력에는 포켓몬·기술 슬롯의 선택지·특성·도구·테라·성격·EV/IV·레벨 목록과 질문 대상 역할/일반 정의만 넣는다.
세트 제목(예: 이름에 포함된 Wallbreaker/Pivot), 전략 본문, 긍정근거, 출처 URL, 역할목록, prior/usage는 입력에 넣지 않는다.
이것은 알려진 전체 세트 구성에 대한 과제이며 실전 상대의 숨은 세트·EV를 안다고 가정한 데이터가 아니다.

- `all.choice.jsonl`: `input.state`/`input.question`만 입력; target_index/target_distribution은 정답.
- `all.jevk5.tokens.jsonl`: JevK5 native 비Thinking 입력과2개 후보 문자 토큰.
- `sets.multilabel.jsonl`: 세트별21역할의 source_support_targets와 긍정역할 목록. 0은 역할 불가가 아니라 근거 미확인이다.
- `roles.ko.csv`: 사람이 확인하는 세트명·한국어 역할·조건·출처 목록. CSV의 세트명/역할목록을 모델 입력으로 합치지 않는다.
- `annotations.json`: 원본문 문자좌표·근거hash·짧은 주석·조건. 전체 본문이나 인용문을 입력으로 복사하지 않았다.
- `excluded-sets.json`, `source-attribution.json`: 제외 사유, 원 작성/검수자·URL·수집본 연결.
- `canonical.jsonl`, `coverage.json`, `validation.json`, `manifest.json`: 관리 원본·분모·검증·출처.

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

설명이나 정답 completion을 붙이지 않는다. 마지막 실제 입력 위치의 유효후보 logits에 CE를 계산한다.
복수역할 행렬을 별도 분류기에 사용하더라도 target의 의미는 **분석 근거의 확인 여부**로 유지해야 한다.
기존 EX113 학습기를 자동 변경하지 않는다. 패딩 배치에서는 실입력 끝·유효후보를 따로 처리한다.

## 검증과 한계

177개 설명 전부의 주석 기록과 긍정 근거의 원문 위치를 대조했다. 역할/주어/조건은 분리 주석 및 교차검토했다.
세트 제목·본문·라벨·metadata를 바꿔도 모델 입력이 달라지지 않는지 검사한다.
native template 동치·단일문자 후보·무절단 길이·저장행 대응·CPU 선택CE를 검증한다.
이 검사는 주석의 전략적 정확성이100%이거나 실전 효능이 검증되었다는 뜻이 아니다.

전부 학습pool이며 별도 validation/test가 없다. 같은 구성/전략/포켓몬 종의 여러 질문은 독립 표본이 아니다.
향후 평가 분할에서는 이 그룹을 함께 고려해야 한다. 역할 지식이 기존 자료·평가 포켓몬과 겹칠 수 있다.
형식·근거위치 검증과 주석 의미검토를 구분하고, 빈 설명·미지원 역할·드문 조건은 추정으로 메우지 않는다.

원문은 [Smogon Strategy Dex](https://www.smogon.com/dex/sv/formats/ou/)의 보관 snapshot이다.
각 원 URL·작성/검수자·원문좌표를 제공하고 새로 공식역할라벨이라고 표시하지 않는다. 외부에 게시하지 않았다.
JevK5 prompt 라이선스/NOTICE는 동봉했다. 원 Smogon 자료·기존 역할DB·모델·서빙은 변경하지 않았다.
재생성: `/workspace/scripts/smogon-role-system1-data --output <새 경로>`.
