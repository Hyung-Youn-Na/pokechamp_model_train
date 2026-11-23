# EX-188 — EP-236 최종 후보의 공식 Showdown gen9ou 래더 대전

- 상태: Paused
- 생성일: 2026-11-19
- 책임자: Claude Code
- 관련 exec plan: [EP-236](../plans/EP-236-laya-v11rtc-foulplay-distill-rl.md)
- 관련 decision: [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md)
- 비교 대상: 같은 계정(nhy_test1629)의 v11rtc·v10rt 래더 기록(같은 팀 구간)
- 기준 연구선: `research/model-training`

## 질문 및 목적

foul-play 점수로 고른 후보(EX-185·EX-187 중 점수가 높은 쪽, 같으면 EX-185)가 사람 래더에서도 v11rtc보다 나은가?

## 가설 또는 qualification 목표

- **판정 없음(보고 전용)**: D-214 결정 2의 지표(판 수, 승패, 레이팅 변화, 경기 전 레이팅 기대 대비 초과 승수, 상대 평균 레이팅)를 보고한다.
- 실행 전: laya-play 등록 경로 로컬 1판(전 결정 서빙 응답, 지연)을 확인한다.

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 모델 | 위 규칙의 후보 하나 |
| 팀 | `t95bfb45561`(래더 기록이 가장 많은 팀, v11rtc·v10rt 같은 팀 기록과 비교) |
| 정책·서빙 | argmax, guard 없음, CPU 서빙 스레드 8, laya-play 등록 경로 |
| 분량 | 최대 60판 또는 12시간 중 먼저 오는 쪽. 시작·종료 시각은 실행 전에 진행 절에 적는다 |

## 실행

- 실행기: `scripts/laya-distill-ep236 ladder`(laya-play `official.sh` 루프). 계정을 쓰는 다른 작업이 없을 때만 시작한다.

## 결과

아직 없다.

## 결론 및 후속 작업

아직 없다.
