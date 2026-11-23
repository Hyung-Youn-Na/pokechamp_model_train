# EX-193 — laya v12(EX-192) 대 foul-play, Blim 팀 64개 128경기(CPU)

- 상태: Completed
- 생성일: 2026-11-20
- 책임자: Claude Code
- 관련 exec plan: [EP-237](../plans/EP-237-laya-observed-public-info-input.md)
- 관련 decision: [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-184](EX-184-laya-v11rtc-vs-foulplay-blim128.md)(v11rtc, 같은 슬롯), [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md)(v10rt)
- 기준 연구선: `research/model-training`

## 질문 및 목적

v12 입력 모델이 foul-play 상대로 v11rtc·v10rt보다 나은가(D-214 개발 지표, 보고 전용)?

## 조건

EX-184와 같다(EX-174 봉인 Blim 128슬롯, foul-play MCTS 3초 × 4, CPU 서빙, argmax, 포트 8100~8103).

- 모델: EX-192 selected(epoch 2). 서빙 모델 이름은 `laya-v11rtc`로 둔다(배틀 작업자가 `serve_v11.MODELS`를 읽음). checkpoint sha256으로 구별한다.
- 서빙: `integration/laya_v12/serve_v12.py`. `foulplay.serve_v11`과 같고 `render_v11.install()` 자리에 `render_v12.install()`을 쓴다. 사용 통계 확장과 guard는 없다. ready 기록에 `v12_render`(판본·세트 sha·코드 해시)가 있어야 시작한다.
- 실행기: `integration/laya_v12/battle_v12.py`. `foulplay.battle`은 고치지 않고 감싼다. prepare 때 live v12 렌더러와 `v12-ladder` 생성 소스가 일치하는지 검사하고, 동결 identity에 v12 파일을 더한다. export 때 v12를 설치해 뷰어가 서빙한 입력을 보여 준다. 스크립트는 `scripts/laya-v12-battle-ep237`(mock 2/2 → prepare → execute 128 → export, mem-guard 25).
- 같은 슬롯 기준선은 EX-184(v11rtc)다. 보고서에 EX-174(v10rt) 같은 슬롯 차이를 한 줄 더한다.

## 결과

- 실행: mock 2/2(1승 1패, audit 통과) → prepare(checkpoint sha `9e051c71…`) → execute 2026-11-21T09:30Z~13:07Z(약 3.6시간) → export 13:20Z. 128슬롯 모두 completed(실패·미완 0).
- v12: 41승 0무 87패, 평균 점수 0.320, 조합 클러스터 95% [0.250, 0.391]. 참고로 EX-184 v11rtc는 45승 82패(0.354)였다.
- 같은 슬롯 차이:
  - EX-184 v11rtc 대비 -0.031, 95% [-0.126, +0.070](127슬롯; 나쁨 22, 나음 18, 같음 87).
  - EX-174 v10rt 대비 -0.008, 95% [-0.118, +0.105](127슬롯; 나쁨 25, 나음 24, 같음 78).
- 지연: v12 결정 p50 2.14초, p95 4.36초(CPU). EX-184는 2.29초, 4.78초였다. foul-play 탐색은 p50 7.25초로 EX-184의 7.30초와 같았다. 20:54 KST부터 병행한 EX-194 래더(GPU 3)가 탐색 시간을 바꾸지 않았다.
- 테라는 76경기에서 썼다(18승 58패). 실패 기술 비율은 3.9%다.
- 뷰어: `exports/battle_viewers/ex193/index.html`(8,000결정). 보고: `runs/model-training/EX-193/report.md`.

## 결론 및 후속 작업

- 잠긴 test의 사람 선택 재현은 크게 나아졌지만(EX-192), foul-play 상대 성적은 v11rtc·v10rt와 구별되지 않았다. 차이의 95% 구간이 0을 포함하고, 점 추정은 약간 낮다. 입력에 foul-play 추론을 넣는 것만으로는 탐색 상대에 대한 약점이 줄지 않았다.
- 128경기 규모로는 ±0.1 안팎의 차이를 구별하지 못한다. 다음 판단에는 래더(EX-194)와 국면별 분석을 함께 본다.
