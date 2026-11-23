# EX-202 — laya v12 + 상대 예측(EX-196) argmax 대 foul-play, Blim 128경기, 시간 제한 없음(CPU)

- 상태: Completed
- 생성일: 2026-11-22
- 책임자: Claude Code
- 관련 exec plan: [EP-239](../plans/EP-239-laya-engine-value-rerank-training.md)
- 관련 decision: [D-217](../decisions/D-217-laya-engine-value-rerank-training.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

EX-201의 같은 슬롯 대조군이다. EX-198을 시간 제한 없이 다시 돌린다(EX-198에서는 6경기가 1,200초에 잘렸다).

## 조건

- EX-198과 같은 모델·서빙·슬롯. 시간 제한은 EX-201과 같이 모두 해제한다. EX-201과 동시에 돈다(포트 분리).
- 2026-11-22T05:37Z mock 통과(1-1, 감사 통과), 05:41Z 128슬롯 준비, 05:41:54Z 실행 시작.
- **중단과 재개(halt-1)**: 06:52Z, 38번째 슬롯 `fp-b31-s1-a`(19턴)에서 foul-play 쪽 poke-engine이 panic했다(`generate_instructions.rs:2182` "Taunt duration cannot be 3 when taunt volatile is active", 표본 4개 모두). 탐색 pool이 `pyo3_runtime.PanicException`을 pickle하지 못해 `PicklingError`가 되었고, actor가 이를 phase 실패로 기록해 실행기가 모든 lane을 멈췄다(완료 37, 실패 1, 미시도 90). 실행 lane은 실행 단계가 0으로 끝났다고 보고 정리(export)까지 진행했다.
  - 조치: foul-play와 기존 actor는 고치지 않았다. `integration/laya_value/actor_unlimited.py`만 고쳐서, 엔진 panic이면 그 경기만 `incomplete`(reason `engine_panic`, failure_scope battle)로 끝내고 다른 경기는 계속하게 했다. 다른 오류는 그대로 둔다. 동결 identity는 이 파일의 sha만 바뀌었다(b4dc50b0 → 9d89f56e). `scripts/laya-battles-ep239`는 이제 `phase_error`가 있으면 export하지 않고 멈춘다.
  - 처음 실행의 result·report·뷰어·checksum·동결 identity·lane 로그는 `EX-202/halt-1/`로 옮겼다(`README.json`). 재개는 실행기의 기존 재개 규칙(이미 시도한 슬롯은 다시 두지 않음)을 따른다. `fp-b31-s1-a`는 실패 1건으로 남는다.
  - 첫 재개(07:06Z)는 이전 서빙 로그 파일이 남아 슬롯을 시작하기 전에 `FileExistsError`로 끝났다. 그 산출물도 `halt-1/`로 옮겼다. 두 번째 재개는 07:08:41Z에 남은 90슬롯을 시작했다.
- 중단 전 37경기 중간 결과(참고): 11승 26패, 0.297, EX-198 같은 슬롯 대비 +0.054 [−0.050, +0.158]. 판정은 전체가 끝난 뒤 한다.

## 결과

2026-11-22T10:24Z 실행 완료, 10:38Z export(`runs/model-training/EX-202/report.md`, 뷰어 `exports/battle_viewers/ex202`). 재개 뒤 엔진 panic은 다시 나지 않았다.

- 127 완료 + 실패 1(`fp-b31-s1-a`, halt-1). 41승 86패, 0.323, 조합 클러스터 95% [0.252, 0.397].
- 같은 슬롯 EX-198(1,200초 제한) 대비 0.000 [−0.072, +0.073] (121슬롯; 나쁨 18, 나음 18). EX-174 v10rt 대비 −0.008 [−0.109, +0.088].
- 결정 지연 p50 3.87초, p95 7.35초.
- 시간 제한을 풀어도 EX-196 argmax 성적은 바뀌지 않았다. EX-201의 같은 슬롯 대조군으로 쓴다.

## 결론 및 후속 작업

아직 없다.
