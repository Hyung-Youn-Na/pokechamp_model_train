# D-202 — laya 상대 가정 세트 노력치 보정과 최악 피해 표시(렌더러 v9)

- 상태: Accepted
- 날짜: 2026-11-02

## 맥락

- **사람 대전 분석**(2026-11-02, laya-v7test, 사용자 Cinderace Kyurem BO 4판): Choice Specs Kyurem의 Blizzard(썰렁개그로 눈을 깐 뒤 Tera Ice)를 반감으로 받으려 교체한 포켓몬이 크게 손해를 봤다. 모델 입력을 다시 렌더링해 원인을 확인했다.
  - `assumed_sets_v2.json`의 Kyurem 가정 세트가 Choice Specs + Adamant 공격 252 / 특공 0이다. EX-071에 3번 나온 물리 Dragon Dance 세트의 노력치에 Specs가 붙은 혼합 세트다. 특수기 `dmg`·`hit`가 약 25% 낮다. 예: Kingambit이 받는 Tera Ice Blizzard가 표시 45~53%, 실제 세트 60~71%, 실전 60%. Ting-Lu는 표시 72~86%, 실제 97~115%다. 108종 중 Hoopa-Unbound(Specs + Brave 공격 252)도 같은 모순이다.
  - 교체 선택지의 `hit`는 상대가 이미 쓴 기술로만 계산한다. 썰렁개그로 막 들어온 Kyurem에는 교체 후보 `hit`가 없었다. 모델은 `takes ice x0.5`만 보고 Iron Crown으로 바꿨고, Tera Ice Blizzard에 56%를 잃었다.
  - 테라하기 전의 `hit`에는 같은 타입 테라 STAB(1.5 → 2.0)이 들어가지 않는다. 미공개 도구는 가정 도구 하나만 쓴다.
- **사용자 지시**(2026-11-02): GPU3으로 이 문제를 해결하는 렌더러 학습을 계획하고 자동으로 진행한다(퇴근 중 무승인).
- EP-224가 `integration/laya_imitation`으로 학습 중이다. 그 패키지는 배틀 prepare 해시와 v7·v8 렌더 동일성 검사 대상이라 고칠 수 없다.

## 결정

1. **렌더러 v9**(`integration/laya_threat/`, 새 패키지, laya_imitation 해시 범위 밖): v7 모듈 전부 위에 두 가지를 바꾼다.
   - **노력치 보정**(`spreads.py`): 상대 계산 세트(`features._opp_spec`)의 성격·노력치가 공격 분류와 모순이면, 그 분류에 맞는 usage(2026-08) 최다 노력치로 바꾼다. 분류는 Choice Specs면 특수, Choice Band면 물리다(강제: 그 능력치 노력치 128 이상, 그 능력치를 낮추지 않는 성격). 그 밖에는 공개된 공격기(보조·고정 피해 기술 제외)의 엄격한 다수다. 이때는 그 능력치를 낮추는 성격에 노력치 128 미만일 때만 모순으로 본다(공격 노력치 없는 수비형 세트는 그대로). 공개된 공격기가 없으면 바꾸지 않는다. v9 렌더 중에만 `features._opp_spec`을 바꿔 끼우므로 `dmg`·`hit`·`out`이 모두 보정 세트로 다시 계산된다.
   - **최악 피해**(`threat.py`): 상대 활성의 공개 공격기와 유력 미공개 공격기(v7 likely ≥ 0.20, 최대 4개), 미공개 도구면 가정 도구와 usage 최다 공격 도구(Specs·Band·Life Orb·Expert Belt, ≥ 0.15), 테라 전이면 usage 최다 테라 타입(≥ 0.25)을 넣은 경우 중 최대 피해를 계산한다.
     - 교체 선택지: 최대 20% 이상이고 `hit`가 없거나 최대가 `hit` 최대보다 10 이상 크면 `; risk a-b% <기술>`을 붙인다.
     - 행동 결정: 최대 20% 이상이면 OPP 묶음 뒤에 `opp threat: <기술> a-b% to me (<도구>?, tera <타입>)` 줄을 넣는다.
   - **토큰 한도**: v7 행이 이미 EX-149 한도에 붙어 있어서 렌더러가 고정 laya 토크나이저로 한도를 지킨다. 선택지가 48토큰을 넘으면 기술 이름을 빼거나 표시하지 않는다. 행이 넘으면 threat 줄, 그다음 risk 표시를 작은 것부터 뺀다. 사전 측정에서 한도 내 행은 v7과 같은 511/512다.
2. **학습(EX-157)**: v9 데이터 `laya-compact-imitation/v9-all`. 시작 모델·설정·분할·테라 지식 행은 EX-149와 같다. GPU3, 학습 시간 상한 없음. 학습 함수는 laya_imitation `training.run`에 새 `Spec`을 넘겨 그대로 쓴다.
3. **배틀(EX-158)**: D-191에 따라 오프라인 결과와 관계없이 v7t 대 v9t를 EX-120 일정 256경기, Abyssal 상대로 둔다(GPU3·8106, EX-150·EX-153과 같은 비퇴보 기준 margin 0.05). mock을 먼저 돌린다. 서빙은 `integration.laya_threat.serve`(laya_imitation 서빙의 모델 목록·데이터셋 매핑·렌더 검사를 그 프로세스 안에서만 확장)다.
4. **보존**: laya_imitation·파서·`scripts/laya-imitation`은 바꾸지 않는다. EP-224 산출물·레인은 건드리지 않는다. 배틀 중에는 `.pokechamp-data/battle-window/EX-158` 표시 파일을 둔다.

## 거절한 대안

- **`assumed_sets_v2.json` 수정**: v2~v8 서빙 전부가 이 파일의 바이트 동일성을 검사한다. EP-224 진행 중에는 고칠 수 없고, 고치면 기존 모델 서빙이 모두 거부된다.
- **usage 최다 도구를 계산 기본값으로**: Kyurem은 Assault Vest(0.26)가 되어 Specs(0.22) 위협이 더 숨는다. 기본값은 가정 세트 도구를 유지하고, 위협은 최악값으로 따로 보인다.
- **usage 기술 다수결로 노력치 분류**: 공개 기술 없는 수비형 Skarmory(Bold)가 Brave Bird 때문에 물리형으로 바뀌었다(사전 점검). 공개된 공격기만 근거로 쓴다.
- **받은 피해로 도구 추정 갱신, 썰렁개그 다음 상대 예고**: 효과는 있겠지만 기록 해석이 더 필요하다. 이번 범위에서 뺀다.

## 근거와 한계

- 최악값은 usage 기반 후보 안에서의 최대다. 후보 밖 기술·도구·테라는 다루지 않는다.
- 단일 시드 학습이다. 배틀 상대는 Abyssal 하나이고, 상대가 Specs Kyurem·썰렁개그 연계를 쓰는 판은 EX-120 일정에 드물다.

## 영향

- 새 코드: `integration/laya_threat/`(`spreads.py`, `threat.py`, `render_v9.py`, `data_v9.py`, `serve.py`, `evaluation_v9.py`, `battle_v9.py`, `cli.py`, `paths.py`, `tests/`), `scripts/laya-imitation-ep225`
- 자료: `laya-compact-imitation/v9-all`. 산출물: `runs/model-training/EX-157`, `EX-158`, 뷰어 `exports/battle_viewers/ex158/`
