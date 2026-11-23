# D-218 — laya 렌더러 v13 입력 결함 수정(폼 스펙·테라 방어 재계산·선공 Roost 지면화·Ivy Cudgel 타입)

- 상태: Accepted
- 생성일: 2026-11-23
- 책임자: Antigravity (Gemini)
- 관련: [EP-240](../plans/EP-240-laya-v13-input-bugfixes.md), [EP-237](../plans/EP-237-laya-observed-public-info-input.md), [EX-203](../experiments/EX-203-laya-engine-value-ladder.md), [EX-204](../experiments/EX-204-laya-engine-value-ladder-loss-analysis.md), [D-191](D-191-no-offline-battle-gate.md)

## 맥락

EX-203(1500+ 래더 35판 및 상위 봇 16판)의 실제 서빙 입력(`laya-compact-v12`)을 재현·감사한 결과, 치명적인 오판을 직접 유발한 렌더러·계산기 입력 결함 4건이 확인됐다.

1. **배틀 중 폼 변환 종의 스펙 유실(`formespec`)**: `ogerponwellspringtera` 등 배틀 중 변신·테라 폼이 `assumed_sets_v2.json`에 없어 `features._assumed`가 기본값(`Serious`, `252 HP / 128 Def / 128 SpD`, 공격 EV 0, 도구 없음)과 `source='default'`를 반환하고, `spreads.opp_spec`·`render_v12.opp_spec`가 `source=='default'`에서 조기 반환한다. 그 결과 `gen9ou-2718021055` 4턴에서 Tera-Water Ogerpon의 `Ivy Cudgel` 피해가 실제 49~52% 대신 **31–37%**로 표시되고 `duel`이 `even`으로 오판됐다. 또한 테라 후 특성(`embodyaspect*`, `teraformzero`)이 `foulplay_full_sets_gen9ou.json`의 테라 전 특성과 불일치해 `sets.candidates`가 0건으로 비어 버린다.
2. **테라 방어 계산의 단일 기술 편향(`teradefence`)**: `strategy.tera_defence`가 테라 전 최악 기술 하나만 테라 후 타입으로 재계산한다. `gen9ou-2717998063` 16턴에서 Dondozo(물)의 Tera Dark 선택지에 `tera takes hornleech 17-20%`만 표시됐고, 물 반감 상실로 치명적이 된 `ivycudgel`(실제 43–51%, 28.2% HP 즉사)이 누락됐다.
3. **선공 `Roost` 지면화 미반영(`roostground`)**: 비행 타입이 선공으로 `Roost`를 쓰면 해당 턴 비행 타입이 사라져 땅 기술에 약점을 찔리지만, `move:roost:normal` 선택지와 `render_v11.duel`의 회복 판정이 이를 반영하지 못한다. `gen9ou-2717995159` 10~13턴에서 Corviknight는 Ting-Lu의 `Earthquake`(실제 50% 피해) 앞에서 `worst ruination 25%`·`duel -> even`만 보고 4턴 연속 `Roost`를 낭비했다.
4. **`Ivy Cudgel` 폼별 타입 미반영(`ivycudgel`)**: `features.effective_move`가 `ivycudgel`의 폼별 타입(물·불꽃·바위)을 처리하지 않아 `worst x1/x2` 상성 요약이 풀 타입 기준으로 잘못 계산된다(`gen9ou-2718021055` 4턴 Cinderace `worst x1`).

## 결정

사용자 지시(2026-11-23 대화: "실험으로 바로 들어가도록 하겠습니다. 일단 드러난 입력 버그를 수정하는 작업을 먼저 진행해주세요.")에 따라 새 래퍼 패키지 `integration/laya_v13/`을 만든다.

1. **기존 패키지 보존**: `laya_imitation`·`laya_threat`·`laya_v10`·`laya_v11`·`laya_v12`·`laya_foe`·`laya_value` 및 기존 동결 자료·봉인은 바이트 단위로 유지한다. `render_v13.install()`은 `render_v12.install()` 위에 런타임 패치로만 적용한다.
2. **수정 항목 4건**:
   - `formespec`: `features._assumed`에 폼→기본종 fallback을 추가하고, `spreads.opp_spec`가 `source=='default'`라도 `usage`에 등록된 종이면 조건화 스펙을 적용하며, `sets.candidates`에서 `embodyaspect*`/`teraformzero`를 테라 전 특성으로 매핑해 결합 세트 추론을 복구한다.
   - `teradefence`: `strategy.tera_defence`가 상대 후보 기술·도구·테라 조합 전체를 아군 테라 후 방어 타입으로 재계산해 실제 최악 피해 기술과 범위를 `tera takes <move> <lo>-<hi>%`로 표시한다.
   - `roostground`: 비행 타입이 상대보다 느리지 않을 때 `move:roost:normal`(및 비행 테라 `move:roost:tera`)에 지면화 후 피해가 기존 최악 위협을 넘으면 `; grounded takes <move> <lo>-<hi>%`를 추가하고, `duel` 회복 판정에서 선공 `Roost` 유일 회복 포켓몬이 지면화 후 50% 이상 피해를 받으면 `even`으로 바꾸지 않는다.
   - `ivycudgel`: `features.effective_move`에서 Ogerpon 폼·가면에 따라 `ivycudgel`의 타입과 STAB을 반영한다.
3. **검증**: 단위 검사, EX-203 핵심 오판 턴 재현 대조, EX-203 1500+ 35판 전수 회귀 및 토큰 예산(상태 ≤ 2,048, 선택지 ≤ 64) 검사를 완료한 뒤 후속 재학습·배틀 평가를 진행한다.

## 결과

[EP-240](../plans/EP-240-laya-v13-input-bugfixes.md)에서 구현과 검증을 추적한다.
