# EX-184 — v11rtc 대 foul-play, Blim 팀 64개 128경기(CPU, 기준 완료본)

- 상태: Planned
- 생성일: 2026-11-19
- 책임자: Claude Code
- 관련 exec plan: [EP-236](../plans/EP-236-laya-v11rtc-foulplay-distill-rl.md)
- 관련 decision: [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-215](../decisions/D-215-laya-foulplay-distill-then-rl.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md) v10rt(같은 슬롯). [EX-176](EX-176-laya-v11rtc-vs-foulplay-blim128.md)(같은 모델, 51경기에서 중지)
- 기준 연구선: `research/model-training`

## 질문 및 목적

EX-176이 중지돼 v11rtc의 Blim 128슬롯 점수가 없다. 증류·강화학습 후보의 같은 슬롯 기준을 만든다.

## 가설 또는 qualification 목표

- **판정 없음(보고 전용)**. 정상 종료가 120/128 미만이면 "판정 보류"를 적는다.
- **보고 지표**: EX-174와 같다(승/무/패, 평균 점수와 조합 클러스터 bootstrap 95%, EX-174 대비 같은 슬롯 차이, 실패 기술률, 테라, 결정 지연, 승리·패배 턴).

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 일정·상대 | EX-174와 같다(collection, 시드, 진영 교환, foul-play `8f541f8`·3,000ms·병렬 4·스레드 1·2026-10 통계, 300턴/600결정, 경기당 1,200초) |
| laya | EX-172 `checkpoints/selected`, 렌더러 v11, 서빙 `integration/foulplay/serve_v11`(EX-176과 같음), CPU, argmax |
| 자원 | CPU, 포트 8100~8103, `scripts/mem-guard 25` |

## 실행

- 실행기: `scripts/laya-distill-ep236 battle EX-184`(`integration/laya_distill/battle_distill.py`, EP-232 실행기). mock(첫 쌍 2경기, 분모 밖) → prepare → execute → export. 상한 10시간, 자동 재실행 없음.

## 결과

아직 없다.

## 결론 및 후속 작업

아직 없다.
