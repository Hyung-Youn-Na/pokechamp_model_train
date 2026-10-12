# EP-122 — 82라운드 계승 추가12시간

- 상태: Completed
- 생성일: 2026-10-06
- 책임자: Codex
- 승인: 사용자 추가12시간1회 요청·82라운드 명시 선택 / [D-118](../../decisions/D-118-abyssal-rl-next.md)
- 관련: EX-075, [C-059](../../CONTRACTS.md#c-059-abyssal-rl-next); INDEX/CHARTER·EP-119/108/103 보존 경계 확인.

## 목표·범위

EX-074 마지막 전체82라운드에서 동일 설정·추가12시간을 별도 EX-075로 실행한다.
조건은 [EX-075](../../experiments/EX-075-abyssal-rl-next.md)가 소유한다.
새 abyssal_rl_next 및 CLI/검사/제어 문서만 수정하며 EX-073/074 source·자료·판정은 보존한다.
준비/부모복원과 문서를 분리 위임하고 주 에이전트가 통합·필수 검증·자동 실행을 맡는다.

## 완료 기준

- [x] 부모82라운드 CPU 출처/가중치/optimizer504/4rank RNG·새 test128·모든 슬롯·CPU 필수 검사
- [x] 4GPU 수치 gate·실제 SIGTERM 전체rank 재개
- [x] 추가 후보 dev·보정 판단·잠긴 test512·독립 감사
- [x] 전 경기 내보내기·최대12경기 브라우저 확인·봉인·소유 자원 정리
- [x] 단계별 영속 중복 방지 알람·최종 문서·보고

## 중단·복구

INDEX 공통 기준·RD11.1/C-018·RD11.2/C-046 적용. 경기 재시도/재질의/대체0.
첫 GPU 검사부터12시간/48GPU시간, 기준 완화·자동 연장0. 팀 부족은 실행 전 중단한다.
반복 대화형 감시·전수/점진 브라우저 검사는 하지 않는다.
문서 갱신은 source 동결 전에 끝내고 동결 중 수정하지 않는다.

## 진행

- 2026-10-06 — 사용자82라운드 계승 선택으로 등록. 구현/CPU 준비 중, 신규 GPU·배틀0.

## 계승·실행 경계

부모 `checkpoint-1791231770617072612.pt`의 EX-074 local25/전체82 가중치·optimizer·
4rank RNG와 출처를 CPU에서 검증한다. 기존2674update(2164+510)와 이번 추가 update를
구분하고 local1/전체83부터 표시한다. 과거 PPO buffer는 재사용하지 않는다.
기존 선택77라운드를 출발점으로 대체하거나 해당 모델 대비 우월성을 주장하지 않는다.
새 test128·seed20261006·모든 슬롯을 동결하고 EX-075 내부 재개만 허용한다.

이번 승인 단위는12시간1회다. 정상·중단 종료 후 자동 다음 주기를 시작하지 않는다.
연구·평가·수치·시간·알람·표본 뷰어 조건은 EX-075의 명시적 계승과 변경표를 따른다.
종료 알람에서 해당 receipt1회 확인·최종 문서 갱신·결과/보고서/뷰어 링크를 제공한다.

- 2026-10-06 — D-118/EX-075/C-059 및 RD·STATUS·ARCHITECTURE·색인 등록.
  신규 GPU·배틀0, 구현·검증 완료 미판정. source 동결 전 문서 작업을 완료한다.

- 2026-10-06 — CPU 준비·통합184검사(학습118·뷰어17·actor49) 및 Chromium 의존성 검사 통과.
  부모 가중치504/optimizer504/4rank RNG·새 test128·17,048슬롯 동결 완료.
  [CPU receipt](../../../.pokechamp-data/experiments/ex075-abyssal-rl-next/verification/cpu.json),
  [준비 manifest](../../../.pokechamp-data/experiments/ex075-abyssal-rl-next/prepared/manifest.json),
  [EX-074 소스 보존](../evidence/ep122/ex074-source-preservation.json).
  추가12시간 단일 실행을 분리 프로세스로 시작하는 단계다. GPU 수치·실제 재개 검사는 실행 내부에서 수행하며 아직 통과 미판정이다.

## 최종 검증·완료 — 2026-10-06

18:09:46 KST 최종화 종료. 모든 완료 기준 충족, 개선 입증 및 승률 목표는 미달이다.
추가27라운드/388update로 전체109라운드·누적3062update에 도달했고 선택은 전체102라운드다.
4GPU 수치·부모 복원·실제 SIGTERM 4rank 재개·전수2904경기/88287결정 독립 감사 통과.
모든 정상 경기 export와 이동 후 오프라인12경기/362결정 표본 검증, 봉인 완료.
selection/test_entry/terminal 알람 전달 완료. 종료 후 supervisor/알람 프로세스 없음,
GPU0–3 메모리0MiB·사용률0%, 소유 포트8030–8033/8100–8107 해제 확인.

- [최종 보고서](../../../.pokechamp-data/experiments/ex075-abyssal-rl-next/final/report.md)
- [해시 확인한 결과](../../../.pokechamp-data/experiments/ex075-abyssal-rl-next/final/result.json)
- [종료 receipt](../../../.pokechamp-data/experiments/ex075-abyssal-rl-next/completed.json)
- [독립 감사](../../../.pokechamp-data/experiments/ex075-abyssal-rl-next/final/independent-audit.json)
- [표본 뷰어 검증](../../../.pokechamp-data/experiments/ex075-abyssal-rl-next/final/viewer-check.json)
- [뷰어](../../../exports/battle_viewers/ex075/index.html)

세부 성능·자원은 EX-075와 최종 보고서가 소유한다. 추가 주기는 시작하지 않았다.
