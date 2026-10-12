# EX-075 — 82라운드 계승 추가 학습

조건 원문: [EX-075](../../../project_context/experiments/EX-075-abyssal-rl-next.md).
작업: [EP-121](../../../project_context/exec-plans/active/EP-122-abyssal-rl-next.md).

```bash
scripts/pokechamp-abyssal-rl-next prepare
scripts/pokechamp-abyssal-rl-next verify
scripts/pokechamp-abyssal-rl-next run
scripts/pokechamp-abyssal-rl-next status
scripts/pokechamp-abyssal-rl-next run --resume
scripts/pokechamp-abyssal-rl-next finalize
```

CPU에서 부모 round82 가중치·optimizer504상태·4rank RNG와 출처를 검증하고 새 test128을
선정한다. 원 train/dev·BC를 유지하고 원 train 순환은 전체83라운드부터 이어간다.
새 RNG seed20261006, 부모2674update와 추가 update는 분리한다. 이전 PPO buffer를 재사용하지 않는다.
`run --resume`는 이번 EX-075의 원 시계·자료·manifest·checkpoint만 허용한다.
첫 GPU 사전검사부터12시간/48GPU시간이며 전체GPU 소유권·고정 수치 검사·실제 SIGTERM 재개
검증을 통과한 후 자동 단계 전환한다. 허용오차·경기 재시도·예산을 자동 완화하지 않는다.

모든 정상 경기 뷰어를 내보내며 브라우저 전수/점진 전수 검사는 실행하지 않는다.
오프라인 브라우저 검사는 여섯 단계별 슬롯ID순 첫·마지막 최대12경기로 제한한다.
별도 `alarms` 모듈이 receipt·실행 프로세스를 확인하며 모델을 호출하지 않는다.
알람 수신 후 반복 대화형 조회 없이 해당 receipt를 한 번 확인해 보고한다.
전체 종료 시 최종 보고·뷰어·미충족 기준·자원 정리와 문서 상태를 갱신한다.
