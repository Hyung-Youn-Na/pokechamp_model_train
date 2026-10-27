# Gen9 규칙 적용 System One 자료 v1

사용자가 지정한 우선순위 1→5로 제공하는 **4,128문항·29규칙군** 학습 pool이다.
System One은 설명을 생성하지 않고 입력 마지막 토큰의 선택지 점수에 교차엔트로피를 적용하는 형식이다.
정답 지도학습이며 모델의 사고방식·실전 성능·추론 속도 개선을 입증한 자료는 아니다. 실제 학습은 실행하지 않았다.

| 순서 | 파일 접두어 | 내용 | 문항 |
|---|---|---|---:|
| 1 | `p1-abilities-items` | 공격 면역·흡수, Wonder Guard, Focus Sash/Sturdy, 특성 무시·억제·Ability Shield | 517 |
| 2 | `p2-switch-residual` | 설치물 진입, 접지·Boots, 독압정 흡수, 끈적끈적네트, 독 재진입, 잔여 HP·기절 | 2,037 |
| 3 | `p3-move-conditions` | PP·도발·구애·앵콜·사슬묶기·돌격조끼, 멘탈허브, 방어·대타출동·조건부 기술 | 455 |
| 4 | `p4-information-sufficiency` | 공개 정보로 확정 가능한지, 숨은 도구·특성·스피드·공격 능력치와 난수 구별 | 399 |
| 5 | `p5-combined-turn` | 행동 순서→방어/공격 실행→고정 피해→KO 방지→모래/도구/상태 잔여 효과 | 720 |

## 파일과 사용

각 접두어마다 `.choice.jsonl`과 `.jevk5.tokens.jsonl`이 있다. `all.*`은 같은 문항을 1→5 순으로 합친 파일이다.
합본과 개별 파일, CSV를 독립 표본으로 중복 합산하지 않는다. `training_order.json`은 제공 순서이며 실제 학습 스케줄이 아니다.

- `*.choice.jsonl`: `input.state`와 `input.question`만 모델 입력이다. `target_index`와 `target_distribution`은 지도 정답이다.
- `*.jevk5.tokens.jsonl`: 로컬 JevK5 고정 tokenizer의 공식 비Thinking chat template로 만든 무절단 `input_ids`, 문항별 `label_ids`, `target`, `expected`다.
- `questions.ko.csv`: 한국어 열 이름의 조건·질문·정답 열람표. 질문과 조건은 기존 자료와 같은 영어이며 학습기에 넣는 파일이 아니다.
- `canonical.jsonl`: 정답·oracle·비공개 가능세계·규칙 metadata를 포함한 감사 원장이다. 전체를 모델 입력에 넣지 않는다.
- `coverage.json`, `validation.json`, `review_samples.json`, `manifest.json`, `checksums.sha256`: 범위·검증·규칙별 예·출처.
- `generator-source/`, `loss.py`: 생성 소스와 단일 문항 선택 CE helper. 엔진 전체 복사본은 포함하지 않으며 아래 pin이 필요하다.

문항마다 선택지 순서를 섞으므로 같은 답의 글자/인덱스가 고정되어 있지 않다. `label_ids[target]`가 정답 토큰이다.
`loss.choice_loss(last_vocab_logits, label_ids, target)`는 **마지막 실제 입력 토큰**의 `[vocab]` logits를 받아 유효 후보에만 CE를 적용한다.
배치 padding 위치를 사용하지 않는다. 설명/assistant 정답 completion 토큰은 0개다.
관리 ID·우선순위·규칙·정답·근거·가중치·그룹은 입력에서 제외한다. 기존 EX113 학습기에 자동 연결되는 schema는 아니다.

모두 train pool이며 validation/test를 따로 만들지 않았다. `semantic_group`은 보수적으로 전체 규칙군을 묶는다.
`inverse_rule_weight`와 `inverse_group_weight`는 선택적 metadata이며 이번에는 같은 묶음이므로 둘을 곱하지 않는다.
문항 수 불균형과 정답 비율은 `coverage.json`에 제공한다. 가중치나 curriculum을 실제 채택한 학습 실험은 별도다.

## 정답 의미와 경계

고정 **Generation 9 singles**의 합성 제어 상태다. 실제 OU 합법 종·기술·특성·도구 조합이라는 주장은 하지 않는다.
명시한 유한 그리드만 다루며 모든 기술·특성·도구 및 모든 상호작용의 전수 자료가 아니다.

1순위의 KO 방지 문항은 입력에 명시한 합성 고정 피해 500/타격을 사용한다. 일반 기술의 위력만으로 500 피해를 추정한 것이 아니다.
특성 무시는 특성을 영구 제거하는 것과 다르다. Ability Shield가 억제를 예방하는 것과 이미 적용된 Gastro Acid를 치료하는 것도 구분한다.

2순위는 개별 SwitchIn/Residual 이벤트 제어 문항과 실제 교체 실행 문항의 범위를 입력에 표시한다.
독·화상은 이미 걸린 상태로 주어진다. 작은 합성 최대 HP도 최소 1 피해/회복과 반올림 경계를 검증하기 위해 포함한다.
모래→도구→독/화상 순서와 HP 0 이후 회복 불가를 확인한다. 교체 중 독 누적 단계 초기화도 별도로 다룬다.

3순위는 선택 가능한 기술 목록과 이미 선택한 기술의 실행 조건을 구별한다.
보호가 이미 성립한 상황과 연속 방어 성공 확률을 혼합하지 않는다. 명중을 조건으로 주는 문항에서는 성공을 보장하는 명시조건이 있다.
구애 고정은 Tackle 기준, 선택 목록은 Tackle/Growl의 제한된 그리드다. 모든 사용 제한·특수 세대 기술을 포함하지 않는다.

4순위의 가능 값 목록은 **이 합성 문제에서 허용된 숨은 조건 전체**다. 실제 공개 경기에서 모든 가능한 세트를 추론했다는 뜻은 아니다.
원천의 숨은 실제값 하나를 정답에 사용하는 대신 각 가능한 조건을 엔진으로 모두 확인한다.
각 조건에서 사건의 확실성 등급이 모두 같으면 그 등급으로 답하고, 다르면 정보 부족으로 답한다.
등급은 반드시 발생 / 반드시 미발생 / 모든 허용 조건에서 난수 의존 / 조건에 따라 등급이 달라 정보 부족이다.
난수 의존은 정확한 확률을 뜻하지 않는다. 능력치가 알려져 있어도 난수에 따라 KO가 달라질 수 있으며, 숨은 정보가 있어도 면역 등으로 결과가 일정할 수 있다.

5순위는 실제 `Battle.makeChoices`로 한 턴 전체를 실행하고 독립적인 순서·HP 계산과 대조한다.
양쪽에 건강한 예비 포켓몬이 있고 원래 active 두 마리의 턴 종료 HP를 묻는다. 교체를 묻는 문항은 아니다.
Seismic Toss의 고정 레벨 피해를 사용하여 피해 난수·급소를 확정 결과로 오인하지 않는다.
스피드 동률이 없고 Protect는 첫 연속 사용으로 성공한다. 입력의 합성 HP·타입·능력치가 모든 조건을 정한다.

## 출처·검증

Pokémon Showdown pin: `e64915c0eab066db1d3e732b1280386468dd7415`.
실행한 `dist` 파일과 생성 코드의 해시를 manifest에 기록한다. 원본 snapshot·기존 자료·평가 분할은 변경하지 않았다.
공식 엔진의 실제 메서드/이벤트와 별도 예상 규칙·산술을 대조하며, native template, 후보 단일 토큰,
metadata 변형 불변, 정답 유일성, 저장 대응, 개별 파일/합본·CSV 일치, 입력 중복을 전수 검사한다.
주 에이전트 및 별도 에이전트의 의미 검토는 인간 블라인드 검토가 아니다. CPU 합성 logits 손실 검증만 수행하고 모델 forward/GPU/학습/API/서빙 변경은 없다.

재생성은 저장소 루트에서 `scripts/mechanics-system1-data --output <새 경로>`를 실행한다. 기존 출력 덮어쓰기는 거부한다.
Showdown MIT 및 공식 prompt 라이선스/NOTICE를 동봉한다. 통제·보고 원문은 EP201/D178과 `project_context/exec-plans/evidence/ep201/`이다.
