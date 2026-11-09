# EX-163 — laya v8lt argmax 대 교체 읽기 상대(abyssal-read), EX-120 일정 128경기(GPU1)

- 상태: Completed
- 생성일: 2026-11-03
- 책임자: Claude Code
- 관련 exec plan: [EP-228](../plans/EP-228-laya-switch-read-and-mixing.md)
- 관련 decision: [D-205](../decisions/D-205-laya-switch-read-and-mixing.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-156](EX-156-laya-v8t-v8lt-battle256.md) `laya-v8lt` 대 Abyssal의 같은 슬롯(같은 체크포인트, 결정적 경로)
- 기준 연구선: `research/model-training`

## 질문 및 목적

사람처럼 교체를 읽는 상대(모델 정책은 보지 않음)를 만나면, v8lt의 성적이 Abyssal을 상대할 때보다 떨어지는가? v8lt가 위협받을 때 얼마나 자주 예측한 포켓몬으로 교체하는가(정직함)? EX-164의 기준선이기도 하다.

## 가설 또는 qualification 목표

- **qualification**: 단위 검사 통과. mock 2경기 정상(CPU, `laya-v8lt-initial`, 분모 밖). 읽기 상대 사건이 `opponent-events.jsonl`에 남는다.
- **판정**(실행 전 동결): 같은 슬롯 점수 차(EX-163 − EX-156 v8lt)의 조합 클러스터 bootstrap 95%(10,000회, 시드 20261065)로 판정한다.
  - 상한 < 0: "읽기 상대가 v8lt 성적을 낮춤"
  - 하한 > 0: "읽기 상대에게 v8lt 성적이 더 높음"
  - 그 외: "구별되지 않음"
  - 정상 종료가 120/128 미만: 판정 보류
- **정직함 지표**(보고):
  - 상황 수, 판정된 상황 수, 적중(예측 후보로 교체)·남음·다른 교체의 수
  - 적중률 = 적중 / 판정된 상황
  - 읽기 발동 수와 발동 적중률
- **재현 검사**: 읽기가 한 번도 발동하지 않은 경기는 EX-156 같은 슬롯과 결과·턴이 같아야 한다. 다르면 보고한다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 자원 |
|---|---|---|---|
| `laya-v8lt` 대 `abyssal-read` | EX-155 selected, v8l 렌더, argmax, EX-120 일정(새 팀 32개, 128슬롯, 같은 시드), 300턴/600결정 | 상대: Abyssal → `abyssal-read`(D-205 결정 1) | GPU1·8109 |

## 실행

- 실행기: `python -m integration.laya_mindgame.battle {mock,prepare,execute,export} --study ex163`, 연결 실행 `scripts/laya-mindgame-ep228 ex163`
- 실행 순서와 확인 사항:
  - **prepare**: EX-155·EX-156의 완료·봉인을 확인하고, v8l 렌더러와 자료 생성기가 같은지 확인한다. 원문 동결, laya_imitation `source_identity`, `laya_mindgame` 파일 해시, 체크포인트 해시를 남긴다.
  - **execute**: 위 해시들이 바뀌지 않았는지 확인하고 실행한다.
  - **export**: EX-156 기준 비교, 뷰어 `exports/battle_viewers/ex163`, 보고서, 봉인 순서로 마친다.
- 배틀 표시: `.pokechamp-data/battle-window/EX-163`
- 상한 10시간. 자동 재실행 없음.

## 결과

2026-11-03 06:45Z~08:23Z, GPU1·8109. 정상 종료 128/128, 감사 모두 통과했다. 보고서는 `runs/model-training/EX-163/report.md`, 뷰어는 `exports/battle_viewers/ex163/index.html`(뷰어 확인 `exec-plans/evidence/ep228/ex163-viewer-check.json`, 페이지 오류 0)이다.

- **판정: 구별되지 않음.** v8lt 대 abyssal-read는 110승 0무 18패(0.859)이고, 같은 슬롯 EX-156 v8lt 대 Abyssal은 0.875다.
  - 차이는 −0.0156, 조합 클러스터 95% [−0.0625, +0.0234]다.
  - 슬롯별로는 이 실행 우세 3, 기준 우세 5, 같음 120이다.
- **재현 검사**: 읽기가 발동하지 않은 73경기가 모두 기준과 결과·턴이 같았다.
- **정직함 지표**:
  - 상황 674번 중 판정된 562번에서, 예측 후보로 교체(적중) 95번(16.9%), 남음 326번, 다른 포켓몬으로 교체 141번이었다. 활성이 기절한 상황 97번은 뺐다.
  - 읽기 발동 66번 가운데 판정된 62번 중 적중은 2번이다.
- **실패·무효 기술**: 139/3,340.
- **결함과 이탈**(EP-228 진행에 상세 기록): mock 단계 결함 2건은 고친 뒤 처음부터 다시 실행했다. 실행 중 Stellar 핫픽스(07:58Z, 사용자 승인)가 있었다. 위험 슬롯 m10-s1-a는 정상 종료했다. 이 경기에서 Stellar 테라스탈은 일어나지 않았으므로, 핫픽스가 실제로 작동한 결정은 없다.

## 결론 및 후속 작업

- 상성표 기반 읽기 상대 앞에서 v8lt는 대체로 남았다. 위협받은 상황의 58%를 남았고 예측대로 교체한 건 17%다. 그래서 읽기는 거의 맞지 않았고(3%), 성적 차이도 구별되지 않았다.
- 사람이 읽은 장면(8번 중 7번 적중)과 차이가 크다. 사람은 읽을 장면을 골랐고, 받아낼 포켓몬을 상성 하나가 아니라 매치업 전체로 판단했다. 이 측정기는 그런 정직함을 잡지 못한다.
- 후속은 상대 모델 + 한 턴 탐색([D-206](../decisions/D-206-laya-opponent-model-search.md), EP-229)이다.
