# 후보별 현재 대면 상성·효과 요약

`candidate-matchup-v1`은 **기존 v6 입력 전체를 유지하면서 기술 후보의 `current_matchup`만 추가**한다.
후보 ID/순서/명령·원 지시문·상성표·계산값은 그대로다. 요약 제거로 원 입력을 정확히 복원할 수 있다.
현재 프로필을 새 실험에서 명시 선택하며, 기존 실험이나 진행 중인 수집에 자동 적용하지 않는다.

## 구성과 해석

| 필드 | 의미 |
|---|---|
| `move`, `target` | 후보가 가리키는 실제 기술과 현재 상대 이름/슬롯 |
| `type_matchup` | 타입별 배율과 곱. 지원한 기술별 타입 예외를 적용하고 도구/특성·접지 효과는 별도 |
| `public_effects` | 공개 정보로 확인한 차단 조건과 면역 해제 조건. 불명확한 예외는 `unknown` |
| `status_effect` | 주요 상태이상의 적용 가능성을 별도로 확인. 피해 기술의 상태 부가효과도 피해와 분리 |
| `damage` | 기존 v6의 `current` 또는 선택한 자기 테라의 `self_tera` 피해 범위를 그대로 복사 |

범위는 **상대가 그대로 있고 상대 테라·교체·다른 행동으로 상태가 변하지 않는 현재 대면**이다.
상대 테라 가정 범위를 현재 피해로 사용하지 않으며 기존 v6 원 필드에는 그대로 보존한다.
피해는 기존 유한 추천세트·명중 조건부 계산이며 0이라는 숫자로 면역 원인을 역추정하지 않는다.

`blocked`는 지원하는 공개 규칙에서 충분한 차단 근거를 찾았다는 뜻이다.
`reflected`는 현재 대상에게 직접 적용되는 대신 반사되는 경우다. 반사 뒤 Synchronize처럼
다시 상태를 전달하는 후속 연쇄 효과는 별도이며 이 요약으로 무효화하거나 예측하지 않는다.
`no_known_blocker`는 실행 성공의 보장이 아니며, `unknown`은 면역 해제나 기술 유효함의 증거가 아니다.
공개되지 않은 Ring Target/Ability Shield 등으로 판정이 달라질 수 있으면 미상으로 유지한다.
실제 숨은 상대 세트·미래 이벤트·과거 모델 선택은 요약 계산에 넣지 않는다.

## 지원과 한계

- 타입표의 단일/복합 배율, Freeze-Dry의 Water 예외.
- Tera Blast의 현재/선택한 자기 테라 타입, Weather Ball의 확인 가능한 날씨 타입,
  지원한 Normal 타입 변환 특성. Stellar·기타 동적 타입/상성 예외는 미상이다.
- Flying/접지·Gravity·Ingrain·Smack Down·Iron Ball·Ring Target·Air Balloon·Levitate,
  Mold Breaker 계열과 Ability Shield, 명시적 억제·Magic Room·Embargo·Klutz를 구분한다.
- 타입 흡수/면역 특성, 지원한 sound/bullet/wind/powder 차단, Good as Gold, Magic Bounce,
  현재 Protect·Prankster와 Dark 타입의 조건을 별도 표시한다.
- 마비/화상/독/수면 등 주요 상태에 대한 지원한 타입·특성·기존 상태·Substitute·terrain·Safeguard 규칙.
  Corrosion/Infiltrator와 Nuzzle 같은 피해+상태 기술을 구분한다. 부가효과의 발동 확률은 예측하지 않는다.
- 회복·설치기 등 자신/진영 대상 기술은 상대 피해 상성을 적용하지 않는다.
  구체적인 전체 실행 성공, 미래 행동, 모든 기술·특성 콜백을 재현하는 엔진은 아니다.
- 지연/호출/타입 미지원 기술·복합 특성/억제 불확실성은 사유와 함께 미상으로 둔다.
  지원 밖 효과를 0 또는 효과 없음으로 대체하지 않는다.

## 사용

모델이나 API를 호출하지 않고 저장 입력을 변환한다. 원 이벤트 전체가 아닌 v6 `state/questions` JSON을 입력한다.

```bash
scripts/candidate-matchup --input original-v6.json --output enriched-v6.json
scripts/candidate-matchup --input original-v6.json --output openai-request.json --format openai
```

출력 옆의 `.provenance.json`에 원본/출력 해시·게임 규칙/구현 정체성·프로필을 기록한다.
기존 출력이나 원자료는 덮어쓰지 않는다. `openai` 형식은 실제 요청 준비까지만 하며 API 키를 읽지 않는다.
단일 후보는 원래 정책대로 자동 선택하므로 OpenAI Choice 요청으로 만들지 않는다.

```python
from integration.candidate_matchup import decorate, remove_summaries

enriched = decorate(original_v6_payload)
assert remove_summaries(enriched) == original_v6_payload
```

새 실행기에는 `integration.candidate_matchup.adapter.Adapter` 또는 모듈의 비동기 `generate`를
명시 연결할 수 있다. `Adapter.close()`로 기존 v6 계산기 자원을 반환한다.
기반 `state.version=jev-choice-v6`와 별도로 manifest에 `candidate_matchup_profile=candidate-matchup-v1` 및
`adapter.data_identity()`를 기록하고, 요약 포함 재생성 감사를 사용해야 한다.
기존 고정 실험 ID의 입력 프로필이나 감사기를 조용히 변경하지 않는다.

## 검증

```bash
PYTHONPATH=/workspace:/workspace/pokechamp pokechamp/.venv/bin/python -m pytest integration/candidate_matchup/tests -q
```

게임 규칙은 pinned Showdown Dex를 읽으며 공식 관측/기존 계산기 설치나 소스는 수정하지 않는다.
오프라인 보존·게임 엔진 대조는 모델 선택 개선이나 승률 향상을 입증하지 않는다.
조건/진행 원문: [D-167](../../project_context/decisions/D-167-candidate-matchup-summary.md),
[EP-182](../../project_context/exec-plans/completed/EP-182-candidate-matchup-summary.md).

검증 결과와 실제 입력 전후 예시는 [EP182 보고](../../project_context/exec-plans/evidence/ep182/report.md)와
[예시](../../project_context/exec-plans/evidence/ep182/examples.md)에 있다.
Ruination 같은 고정/비율 피해에는 타입표의 약점/저항 배율을 그대로 곱하지 않으며 해당 설명을 별도 표시한다.
