# Qwen 후보 상태 입력의 결정별 지침과 별도 진단

EX-063의 피드백을 **결정 종류에 맞는 행동 순서와 상태 변화의 연결**로 구현한다.
속도나 타입 설명이 없었다고 해석하지 않으며, q만으로 모델이 정보를 무시했는지 판단하지 않는다.
승인·방법·실행 조건 원문은 [D-102](../project_context/research/action-value/decisions/D-102-qwen-candidate-state.md),
[연구 설계](../project_context/RESEARCH_DESIGN.md),
[EX-064](../project_context/research/action-value/experiments/EX-064-qwen-candidate-state.md)다.

## 지침 구성

`decision_instructions.compose(original_instructions, decision_kind)`는 현재 결정의 평가 절차,
새 공통 해석 규칙, 기존 instructions 전문을 차례대로 결합한다. 기존 전문은 그대로 보존하며
세 절차 파일에 복제하지 않는다. 실행 prompt는 기존 입력과 같은 영어로 작성한다.

| 결정 | 앞부분에 추가하는 평가 절차 |
|---|---|
| `lead` | 공개 미리보기의 가능한 상대 선봉을 조건부로 비교한다. 초기 대면·첫 행동·불리한 대면의 대응·팀의 중요한 대응 수단을 고려한다. `active` 표시는 배틀 진입 증거가 아니다. |
| `turn_action` | 합법성과 행동 순서→올바른 시점의 테라·교체·진입→선행 행동 효과→후행 행동 가능 여부→변경 후 반격→잔여 HP와 KO→교체·테라 비용→턴 종료와 이후 가치를 비교한다. |
| `forced_switch` | 교체 시점과 남은 행동→진입 효과와 진입 후 상태→실제로 남은 공격→다음 유효 행동과 중요한 대응 수단을 비교한다. 완료된 공격을 재적용하지 않는다. |

공통 규칙은 관측과 조건부 가정, 동일 상대 세트 안의 속도·내구·화력, 추천 세트의 제한,
계산 조건의 유효성, 미지원 상태의 `unknown`, 합법 후보 ID와 기존 출력 계약을 유지한다.
현재 후보의 가치를 바꾸는 요소에 집중하며 매번 긴 체크리스트를 요구하지 않는다.
즉시 KO를 고정 최우선으로 두지 않는다. 생존이나 KO를 포기할 때 얻는 구체적인 포지셔닝,
핵심 포켓몬 보존, 승리 조건 기여를 함께 비교한다.

원 instructions에서 교체와 미래 행동 순서 변화를 피해 계산에서 제외한다고 한 것은 **원본
현재 상태 계산의 적용 범위**다. 후보 평가에서 이 사건들을 무시하라는 뜻이 아니다. 추가
후보 상태 계산이 있으면 대상·시점·조건이 일치하는 계산을 따로 사용하고, 없으면 바뀐 피해를
임의로 계산하지 않는다. 자발적 교체는 기술을 대신하며 진입 포켓몬이 남은 공격을 받을 수 있다.
강제 교체는 기절 뒤인지 턴 도중 pivot인지에 따라 남은 행동이 달라지고, 불명확하면 조건부로
남긴다.

후보에 `evaluation_ref`가 있으면 해당 action ID로 `state.candidate_evaluations`의 기록을
찾는다. 다른 후보의 예측이나 다른 피해 대상을 대신 사용하지 않는다. 큰 계산 기록을 후보
설명과 이진 질문마다 복제하지 않고 한 곳에 보관하는 참조다.
`same_outcomes_as_action_id`는 명시된 동일 수치 시나리오만 공유한다. 선택 후보의 테라 사용,
타입 변화와 자원 비용은 그 후보의 메타데이터를 따로 적용한다.

`scenario_rows`는 기술 후보의 `state.candidate_scenario_columns`, 교체 후보의
`state.candidate_switch_columns`에 명시된 순서로 해석한다. `null`은 지원되는 값이 없다는
뜻이며 `unknown`은 불확실성으로 유지한다. 반복된 긴 `general_effect` 원문은
`state.effect_descriptions`와 `general_effect_ref`로, 팀의 조건부 역할 설명·범위 원문은
`state.role_descriptions`와 `description_ref`·`scope_ref`로 공유한다. 역할 ID와 관측 구분,
이름·수치·조건은 보존하며 다른 `description` 필드는 바꾸지 않는다.
`candidate_descriptions.expand()`로 원문을 정확히 복원할 수 있다. 이 구조 변경도 입력
형식 treatment에 포함되며, 원문 공유가 현재 효과의 발동이나 유리한 대면을 확정하지 않는다.

## 진단 입력·출력

`qwen_diagnostics.validate(body)`, `encode(body, tokenizer)`, `parse(text, action_id)`는 모델
실행과 분리된 입력·출력 검사다. 요청은 다음 네 필드만 받는다.

| 필드 | 의미 |
|---|---|
| `observation` | 허용된 원본 또는 별도 입력 버전의 관측 |
| `actions` | 원순서의 합법 후보와 기존 명령 매핑 |
| `action_id` | 진단할 합법 후보 하나 |
| `scenario` | 공개 정보로 구성한 조건부 시나리오 객체 |

학습 타깃·미래 seed·snapshot·상대 원선택·provenance 같은 금지 필드는 재귀적으로 거절한다.
후보 coverage·명령·설명 참조를 검사한다. 입력과 출력 예약512토큰의 합이16,384를 넘으면
절단하지 않고 실패한다. 후보별 진단 prompt/token hash와 입력 토큰을 반환한다.

원 요청을 그대로 검사한 뒤 진단 모델 입력의 새 복사본에만
`qwen-diagnostic-candidate-projection-v1`을 적용한다. 추가 계산의 `candidate_evaluations`에서
평가 후보와 명시적으로 연결된 동일 수치·비테라 비교 기준만 남긴다. 관측 사실·기존 피해·
지침·전체 합법 후보 ID·명령·이름·세트 가정·열 정의·설명 catalog는 보존한다. 모델 입력의
`diagnostic_projection`은 다른 후보의 추가 계산을 이번 진단에서만 생략했음을 표시한다.
생략된 `evaluation_ref`는 `unknown` 결과나 원 q 입력의 계산 부재를 뜻하지 않는다.
audit의 `projection_info`에 버전·보존 ID·생략 ID·투영 관측 hash를 기록하며, 요청 기록과
q 관측·계약은 바꾸지 않는다. 이 별도 진단 형식과 비용도 q 입력과 구분해서 보고한다.

생성 결과는 `action_id`, `scenario`, `order`, `post_state`, `damage_applicability`, `survival`,
`ko`의 짧은 JSON이다. 생존과 KO는 JSON `true`/`false`, 문자열 `conditional`/`unknown`,
또는 `status`와 짧은 조건을 가진 객체를 허용한다. 최종 능력치 단계, 현재 피해량 적용 여부,
재계산 미제공처럼 검증 가능한 결과만 기록한다. 정확한 변경 후 피해량이 제공되지 않았다면
`unknown` 또는 `not_provided`와 짧은 사유를 사용한다.

예를 들어 3턴 Close Combat 선공 조건에서는 자기 방어가 +1에서0으로 바뀌고 기존 반격
피해량의 적용 조건이 달라졌다는 예측을 확인한다. 그 사실만으로 실제 기절 원인을 방어 하락
하나로 확정하지 않으며 미확인 특성·HP 임계치도 별도 조건이다.

진단 prompt는 q의 A/B 최종 질문을 사용하지 않는다. 긴 내부 사고 설명을 요구하거나 저장하지
않으며, JSON 외의 응답·중복 키·후보 ID 불일치·추가 필드·비유한 수·장문 reasoning은 검사에서
거절한다. 모델 원문은 호출 측 실패 행에 보존한다. 실패를 repair하거나 재시도해 지우지 않는다.

개발 서버의 `/diagnose`는 기본으로 비활성화하며 명시적인 `--diagnostics`에서만 제공한다.
생성은 동일 모델의 greedy·비사고 모드, 최대 새512토큰, 요청별 cache와 기존 직렬 GPU 경계를
사용한다. 전역 q 설정과 A/B readout은 변경하지 않는다. 예정 q 비교 뒤 진단을 별도 실행하고,
진단 전후 동일 q와 가중치 불변을 확인한다.

## q 계약과 검증의 해석

기존 후보별 A/B forward, 독립 q, 최댓값 선택, 동률 원순서, 합법 명령과 전송 검사는 유지한다.
진단은 동일 고정 base+LoRA의 별도 생성 호출이며 q 응답이나 선택·전송 입력에 되먹이지 않는다.
기술적으로 JSON 생성이 가능하다는 사실과 실제 모델의 JSON·상태 예측 정확성은 별도다.
진단이 맞아도 실제 q 산출에서 그 예측을 사용했다는 증거로 해석하지 않는다.

EX-064는 기존 입력/기존 지침, 기존 입력/결정별 지침, 보완 입력/결정별 지침을 비교한다.
조건부 상태 정확성과 후보 순위 변화를 별도로 보고하고 특정 후보1위를 유일한 정답으로
삼지 않는다. 진단의 예정 호출에는 JSON 실패·시간초과·길이 초과도 포함한다. q 토큰·지연과
별도 진단의 입력·출력 토큰·시간을 분리한다.

q의 학습 타깃은 후보 실행 뒤 양측 Abyssal이 이어가는 조건의 값이며 Qwen 전경기 정책의
보정된 승률이 아니다. 고정 모델 입력 변경에는 학습 당시 입력 분포에서 벗어나는 영향도
포함된다. 저장된 개발 장면의 개선만으로 독립 배틀 성능이나 전체 승률 개선을 주장하지 않는다.

최종 구현은 빈 unknown 결과를 테라 이득 부재의 증거로 공유하지 않으며, 미지원 자기 후공
효과가 있으면 최종 생존·KO도 unknown으로 유지한다. 실제 고정 모델 비교와 종료 후 보정의
범위·검증·비용·한계는 [EP-106 보고](../project_context/exec-plans/evidence/ep106/report.md)를 따른다.
