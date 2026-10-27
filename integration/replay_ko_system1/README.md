# 실제 리플레이 KO 결과 예측 — System 1

실제 Gen9 OU 공개 리플레이에서 **주어진 공격이 즉시 처리되는 동안 상대를 직접 KO시켰는지**를 학습하는 자료다.
정답·설명 completion 없이 후보 logits로 관측 결과를 선택하는 지도 판별 학습용이다.

## 무엇을 판단하는가

입력은 해당 `|move|` 직전까지의 공개 이력과 조건으로 제시한 공격자·기술·대상이다.
공격 이름/대상은 실제 move행에서 추출하지만 **명시된 질문 조건**이며, 공격의 선택 자체를 예측하거나 모방하지 않는다.
`[miss]`, `[still]`, 호출출처 등 move행의 결과 힌트는 입력에 붙이지 않는다.

두 정답 후보는 `Direct target KO occurred` / `No direct target KO occurred`다.
이후 피해·기절·급소·명중 결과는 label/evidence에만 들어간다.
공개 HP는 반올림된 표시이고 숨은 능력치·아이템·세트·난수를 복원하지 않는다. 플레이어의 모든 자기 정보를 가진 상태가 아닌 **공개 관전자 시점**이다.

**한 번 관측된 KO는 확정 KO나 KO확률100%의 증거가 아니다.** 같은 공개 상황에서도 숨은 세트·난수 등에 따라 결과가 달라질 수 있다.
미선택 기술의 반사실 KO 여부·최적 행동·승률을 라벨링하지 않는다. 출력 확률을 자연분포에서 보정된 KO확률이라고 주장하지 않는다.
입력시점은 공격 직전이며 턴 시작이 아니다. 그 턴에 먼저 일어난 공개 교체/행동은 포함된다.

## 원천과 채택

로컬 보관 `milkkarten/pokechamp` revision `b5820ff5d0c8d5e5cec692d55f756b6e5a66a203`의 **train Parquet만** 사용한다.
기록 당시 `gamemode=gen9ou`, `gen=9`, singles의 실제 공개 로그다. 현재 OU 규칙으로 모든 종/세트가 합법임을 주장하지 않는다.
원본 train 파일을 hash 검증하며 원dataset test 본문은 읽지 않는다.

정렬된 train샤드에서 Gen9OU 최대10,000경기를 검토하고, 필터 이후 KO/비KO 사례가 모두 있는 최대1,000경기를 채택한다.
경기별 해시순서로 KO 최대2·비KO 최대2개를 선택하며 전체입력6144토큰 초과는 절단하지 않고 제외한다.
따라서 최대4,000문항이며 실제 분모·제외 이유는 `coverage.json`에 있다.
이는 편의·조건부 표집으로 **자연 KO 빈도나 일반 경기 분포를 보존하지 않는다**. KO경기가 충분한 경기 위주 선택이라는 한계도 있다.

- 기존 로컬 Gen9 OU 리플레이 ID 전체를 제외한다.
- EX071 validation/test ID·양팀 로스터, 역사 평가팀·실배틀 일정팀의 종 목록을 metadata만 읽어 보수적으로 제외한다.
- 로스터는 base species로 합쳐 비교하므로 폼이 다른 유사 팀도 제외될 수 있다.
- 새 모집단에서 경기 ID와 익명화한 전체 공개 mechanics 중복을 제거한다.
- 알려지지 않은 다른 데이터/평가와의 중복·유사팀은 완전히 해소했다고 주장하지 않는다.

새 자료는 **학습pool**이며 별도 validation/test를 만들지 않는다.
향후 분할은 metadata의 replay_group과 team_signatures를 함께 고려해야 한다. 같은 경기의 여러 문항을 행단위로 나누지 않는다.

## 직접 KO 라벨 규칙

양성은 같은 공격 프레임에서 상대 target의 직접 `-damage`가HP0을 기록하고 뒤이어 같은 target의 `faint`가 있는 경우다.
문자열 `fnt` 유무만 보지 않고 HP수치를 확인한다. 일반 다단히트는 한 공격 전체를 묶고 기합의띠 후 후속 타격 KO도 양성이다.
음성은 직접 타격 후 생존, 명시적 miss·면역·Protect 등으로 확인된 비KO다.

다음 move/cant/교체/강제교체/턴/잔여전환/승패 경계에서 프레임을 닫는다.
독·날씨·설치물·반동·도구 피해를 직접 target 피해로 합치지 않는다. target이 간접효과로 기절한 혼합 프레임은 제외한다.
지연 공격·불명확 호출·일루전/변신·대타출동 상호작용·일부 특수KO·자기대상·절단/불명확 로그는 보수적으로 제외한다.
이 제외는 해당 규칙이 중요하지 않다는 뜻이 아니라 첫 판본의 귀속 정확성을 위한 범위다.

입력은 허용한 mechanics 이벤트의 전체 과거 prefix다. 선수명·닉네임·채팅·레이팅·timestamp·승자·경기ID는 모델 입력에서 제거한다.
능력치/피해 계산을 새로 추정하거나 공개되지 않은 정보를 이후 턴에서 가져오지 않는다.

## 파일과 손실

- `all.choice.jsonl`: `input.state`와 `input.question`만 입력, target_index/target_distribution은 정답.
- `all.jevk5.tokens.jsonl`: JevK5 비Thinking input_ids·label_ids·target·expected. 정답/설명 completion 없음.
- `canonical.jsonl`: 같은 입력과 감사용 outcome frame·좌표. 전체를 모델 입력에 넣지 않는다.
- `replays.json`, `replay-exclusions.json`, `holdout-protection.json`: 채택·제외·알려진 평가 자료 보호.
- `review_samples.json`: 관측 결과 유형별 검토 사례와 근거. 학습 입력이 아니다.
- `coverage.json`, `validation.json`, `manifest.json`, `checksums.sha256`: 실제 분모·검증·출처.
- `loss.py`: 2후보 마지막위치 CE 예제.

```python
import json
import torch
from loss import choice_loss
row = json.loads(open('all.jevk5.tokens.jsonl').readline())
ids = torch.tensor([row['input_ids']], device=device)
# 별도로 적재한 지원 모델을 사용하는 예시. 이 자료 생성은 모델을 적재하지 않는다.
logits = model(input_ids=ids, logits_to_keep=1, use_cache=False).logits[0, -1]
loss = choice_loss(logits, row['label_ids'], row['target'])
```

metadata의 결과유형·ID·레이팅·원자료좌표, evidence의 피해/급소/기절은 모두 입력에서 제외한다.
같은 행의 target은 실제결과 one-hot이며, 이를 확정KO 규칙이나 모든 행동의 q로 해석하지 않는다.
기존 EX113 학습기/서빙을 자동 변경하지 않는다. 실제 모델학습·추론·배틀·GPU 사용은 없다.

## 검증과 보존

합성 parser 경계 검사와 실제 원자료 좌표/공개prefix/정답 전수 대조, native template 동치·무절단 길이·저장행 대응을 확인한다.
미래결과만 바꾸면 모델 입력이 그대로이고, 과거공개상태를 바꾸면 입력이 바뀌는지를 검사한다.
실제 결과유형별 독립 사례 검토도 기록한다. 사람의 블라인드 검토나 독립 모델성능 평가를 뜻하지 않는다.

전체 원본 경기 사본은 원본 생성경로의 `source-evidence/`에만 보존하며 다운로드 ZIP에는 넣지 않는다.
재감사를 위한 원dataset의 파일·행·로그hash는 남긴다. 원천 README에 라이선스 선언이 없어 다른 자료의 라이선스를 승계하지 않았다.
이 자료는 로컬 사용자 제공용이며 외부에 게시하지 않았다. JevK5 prompt LICENSE/NOTICE를 별도로 동봉했다.
재생성: `/workspace/scripts/replay-ko-system1-data --output <새 경로>`. 기존 출력 덮어쓰기는 거부한다.
