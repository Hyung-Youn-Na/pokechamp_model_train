# EX-164 — laya v8lt 교체 갈림길 섞기(재학습 없음): 대 Abyssal·대 교체 읽기 상대, 각 128경기(GPU2·GPU3)

- 상태: Completed
- 생성일: 2026-11-03
- 책임자: Claude Code
- 관련 exec plan: [EP-228](../plans/EP-228-laya-switch-read-and-mixing.md)
- 관련 decision: [D-205](../decisions/D-205-laya-switch-read-and-mixing.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상:
  - abyssal 갈래: [EX-156](EX-156-laya-v8t-v8lt-battle256.md) `laya-v8lt` 대 Abyssal의 같은 슬롯
  - reader 갈래: [EX-163](EX-163-laya-v8lt-vs-switch-reader.md) `laya-v8lt` 대 `abyssal-read`의 같은 슬롯
- 기준 연구선: `research/model-training`

## 질문 및 목적

교체 갈림길에서만 남기를 섞으면 교체 읽기 상대에게 덜 읽히고 성적이 나아지는가? Abyssal 상대로는 퇴보하지 않는가?

## 가설 또는 qualification 목표

- **qualification**:
  - 단위 검사 통과. 갈래마다 mock 2경기가 정상이다(CPU, `laya-v8lt-mix-initial`, 분모 밖).
  - 서빙 응답에 `mix_rule`과 `model_probabilities`가 남는다.
  - 섞기로 바뀐 결정이 없으면 원래 argmax와 같다.
- **판정**(실행 전 동결, 같은 슬롯 점수 차의 조합 클러스터 bootstrap 95%, 10,000회):
  - **abyssal 갈래**(mix − EX-156 v8lt, 시드 20261066):
    - 하한 > 0: "섞기가 배틀 성적을 개선"
    - 하한 > −0.05: "비퇴보"
    - 그 외: "퇴보를 배제하지 못함"
  - **reader 갈래**(mix − EX-163 v8lt, 시드 20261067):
    - 하한 > 0: "섞기가 읽기 상대 성적을 개선"
    - 상한 < 0: "악화"
    - 그 외: "구별되지 않음"
  - 갈래마다 정상 종료가 120/128 미만이면 판정 보류다.
- **정직함 지표**(보고, reader 갈래): 읽기 상대의 적중률을 EX-163과 비교한다. 차이(mix − v8lt)는 같은 조합을 짝지어 재표집한 95% 구간으로 보고한다(시드 20261067). 발동 수와 발동 적중률도 함께 보고한다.
- **섞기 지표**(보고): 응답 결정 수, 규칙 작동 수(남기에 비율을 배정한 결정), 실제로 바뀐 결정 수, 사유별 수
- **재현 검사**: 섞기로 바뀐 결정이 없는 경기는 기준 경기와 결과·턴이 같아야 한다(abyssal 갈래는 EX-156, reader 갈래는 EX-163).

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 자원 |
|---|---|---|---|
| `laya-v8lt-mix` 대 Abyssal | EX-155 selected, v8l 렌더, EX-120 일정 128슬롯(같은 시드), 300턴/600결정 | 서빙 결정: argmax → 교체 갈림길 섞기(D-205 결정 2) | GPU2·8108 |
| `laya-v8lt-mix` 대 `abyssal-read` | 같음, 상대는 EX-163과 같은 `abyssal-read` | 같음 | GPU3·8106 |

섞기 규칙(`mix.py`, `switch-dilemma-mix-v1`)의 상수는 다음과 같다.
- usage 하한 0.10, 남기 후보 하한 0.05, 남기 비율 상한 0.5, 최소 비율 0.05
- 효과가 굉장함 기준 ×2, 추첨 소금값 `EX-164`

배틀 클라이언트는 응답 확률의 argmax만 받는다. 그래서 규칙이 작동한 결정의 응답 `probabilities`는 추첨된 결정을 1로 둔 값이고, 추첨 전 비율은 `mix_rule.mixed`, 정책 출력은 `model_probabilities`에 있다.

## 실행

- 실행기: `python -m integration.laya_mindgame.battle {mock,prepare,execute,export} --study ex164a|ex164r`, 연결 실행 `scripts/laya-mindgame-ep228 ex164a|ex164r`
- 서빙: `python -m integration.laya_mindgame.serve`. laya_imitation 서빙에 감싼 정책을 넘기며, laya_imitation 파일은 고치지 않는다.
- 해시 동결: EX-163과 같이 prepare에서 남기고 execute에서 확인한다.
- export 시점: reader 갈래의 export(EX-163과 비교)는 EX-163이 execute를 마친 뒤에 한다.
- 출력 위치: 실행 `runs/model-training/EX-164/{abyssal,reader}`, 뷰어 `exports/battle_viewers/ex164-abyssal`·`ex164-reader`
- 배틀 표시: `.pokechamp-data/battle-window/EX-164-abyssal`·`EX-164-reader`
- 상한은 갈래마다 10시간이다. 자동 재실행 없음.

## 결과

2026-11-03 06:45Z~08:28Z. 두 갈래 모두 정상 종료 128/128, 감사 모두 통과했다.
- 보고서: `runs/model-training/EX-164/{abyssal,reader}/report.md`
- 뷰어: `exports/battle_viewers/ex164-abyssal`, `ex164-reader`(뷰어 확인 `exec-plans/evidence/ep228/`, 페이지 오류 0)

**abyssal 갈래**(GPU2·8108)
- **판정: 퇴보를 배제하지 못함.** mix 106승 0무 22패(0.828) 대 EX-156 v8lt 0.875다.
  - 차이는 −0.0469, 95% [−0.1016, +0.0078]다. 이 실행 우세 4, 기준 우세 10, 같음 114다.
- 재현 검사 84/84 일치.
- 섞기: 응답 4,823번 중 규칙 작동 136번, 실제로 바뀐 결정 58번이다(오프라인 예상은 145번·67번).

**reader 갈래**(GPU3·8106)
- **판정: 구별되지 않음.** mix 106승 0무 22패(0.828) 대 EX-163 v8lt 0.859다.
  - 차이는 −0.0312, 95% [−0.0938, +0.0313]다. 이 실행 우세 7, 기준 우세 11, 같음 110이다.
- 재현 검사 83/83 일치.
- 섞기: 규칙 작동 131번, 실제로 바뀐 결정 62번이다.
- **정직함 지표**:
  - 적중률은 15.95%(78/489)이고 EX-163은 16.90%다. 차이는 −0.0095, 95% [−0.0330, +0.0122]로 구별되지 않는다.
  - 읽기 발동 65번 가운데 판정된 62번 중 적중은 2번이다.

실패·무효 기술은 139/3,343(abyssal), 130/3,351(reader)이다.

## 결론 및 후속 작업

- 교체 갈림길 섞기는 Abyssal 상대로 퇴보를 배제하지 못했고(바뀐 경기 14개 중 10개 악화), 읽기 상대에 대한 정직함 지표도 바꾸지 못했다. 원래 읽힐 교체가 적었다.
- 상성표 기반 한 턴 근사로 정한 섞기는 득보다 실이 커 보인다. 이 규칙을 그대로 사람 대전에 쓰는 것은 권하지 않는다.
- 후속은 상대 예측에 근거한 탐색([D-206](../decisions/D-206-laya-opponent-model-search.md), EP-229)이다.
