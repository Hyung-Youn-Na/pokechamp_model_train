# EP-129 — 실패1경기 재수집·1라운드 재개

- 상태: Completed
- 생성일: 2026-10-07
- 승인: 사용자 실패1경기 재수집·이어서 진행 지시 / D-125
- 원문: EX-078 승인된 복구·D-124·C-060·RD11.1

## 범위

INDEX/CHARTER와 겹치는 EP127/126/125·완료EP128의 보존 경계를 확인했다.
원EX078 정상31·P0·업데이트0 checkpoint/시계를 보존 계승하고 실패1만 재수집한다.
준비helper·원/새identity 연결·원자료해시·경기감사·CPU/GPU 검증을 수행하며 단일1라운드
checkpoint까지 자동 진행하고 단계 알람으로 보고한다. 원자료/과거중단판정은 수정하지 않는다.

## 완료 기준

- [x] 원봉인/31정상/원P0·checkpoint0/RNG·실패1 검증·새identity 동결
- [x] 허용된1경기 재수집·전체32 정상·첫라운드checkpoint/reload 검증
- [x] 전수감사·뷰어·봉인·자원반환·보고

## 복구

EX078/D125의 실패한 단일 슬롯1회만 허용한다. 재실패하면 보존·보고하고 추가수집하지 않는다.
시간상한은 없고 단일GPU·1라운드·300턴·탐색/학습량·무결성/취소 조건은 유지한다.

## 진행·검증

- 원source와 현재 모델·탐색·시뮬레이터·관측·일정·checkpoint 코드9개가 byte 단위로
  동일하다. 경기 코드 차이는 null 시간 상한 처리에 한정됨을 대조했다.
  [대조](../evidence/ep129/numerical-source-check.json) · [시간 처리 변경](../evidence/ep129/battle-time-only.diff).

- 복구CPU15검사 통과. 실제 부모 봉인/31경기 감사·P0/checkpoint0/RNG 검증도 통과했다.
  새identity `22d0be412e4d4f1532009cc6391e7f905ba62eda25c0f1b3cf30be34ed99eb38`.
  [검사](../evidence/ep129/tests-recovery.log) · [준비](../evidence/ep129/prepare.json).
- 정상31·원최초시각/null예산·원학습전상태를 계승했고 pending은 지정 실패1개뿐이다.
  전용실행기와 모델 비호출 단계알람을 시작했다. 이후 반복 대화형 감시는 하지 않는다.
  [실행](../evidence/ep129/controller.json) · [알람](../evidence/ep129/alarm-launch.json).

## 완료 결과

승인 범위의 검증·보고·상태 정리를 완료했다. [최종 보고](../evidence/ep129/report.md).
