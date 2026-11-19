# EX-179 — laya fp1 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기

- 상태: Planned
- 생성일: 2026-11-18
- 책임자: Claude Code
- 관련 exec plan: [EP-234](../plans/EP-234-laya-fp1-foulplay-input.md)
- 관련 decision: [D-213](../decisions/D-213-laya-fp1-foulplay-input.md), [D-212](../decisions/D-212-laya-foulplay-blim-teams.md), [D-211](../decisions/D-211-laya-foulplay-opponent.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md)의 v10rt(같은 슬롯, 42/0/85, 0.331). 참고로 [EX-175](EX-175-laya-v11rt-vs-foulplay-blim128.md) v11rt(부분, 0.254)
- 기준 연구선: `research/model-training`

## 질문 및 목적

입력을 foul-play 기반으로 바꾸고 처음부터 학습한 laya(fp1)는 같은 Blim 일정에서 foul-play에게 얼마나 이기는가? v10rt와 같은 슬롯에서 얼마나 다른가?

## 가설 또는 qualification 목표

- **판정 없음(보고 전용)**. 정상 종료가 120/128 미만이면 "판정 보류"를 적는다.
- **보고 지표**: 승/무/패, 평균 점수와 조합 클러스터 bootstrap 95%(10,000회, EX-120 요약기), EX-174 대비 같은 슬롯 차이, 교환 쌍 분포, 팀 유형별 점수, 실패 기술률, 테라, 결정 지연(추적기 포함), 승리·패배 턴.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 자원 |
|---|---|---|---|
| Blim 일정 128슬롯 × fp1 | EX-174와 같다: collection, 시드, 진영 교환, foul-play `8f541f8`·3,000ms·병렬 4·스레드 1·2026-10 통계, 300턴/600결정, 경기당 1,200초 | laya 쪽 모델 EX-178 selected, 서빙 `serve_fp1`(경기 중 같은 추적기) | 포트 8100~8103. 서빙은 GPU가 비어 있으면 GPU(승패에 영향 없음) |

## 실행

- 실행기: `integration/foulplay/battle.py`에 `STUDIES['EX-179']`를 추가하는 방식, 연결 실행 `scripts/laya-fp1-ep234 battle EX-179`.
- 순서: mock(첫 쌍 2경기, 분모 밖) → prepare → execute → export. 상한 10시간, 자동 재실행 없음.

## 결과

아직 없다.

## 결론 및 후속 작업

아직 없다.
