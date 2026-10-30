# EX-143 — laya v5+테라와 v6st (반복 표시) 같은 실행 256경기(GPU0, EX-120 일정)

- 상태: Completed
- 생성일: 2026-10-29
- 책임자: Claude Code
- 관련 exec plan: [EP-221](../plans/EP-221-laya-past-turn-input-v6.md)
- 관련 decision: [D-198](../decisions/D-198-laya-past-turn-input-v6.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 선행: [EX-141](EX-141-laya-v6s-streaks-training.md)(학습 완료만, 판정 무관), [EX-136](EX-136-laya-v5-tera-training.md), [EX-120](EX-120-laya-team-generalization128.md)(일정)
- 기준 연구선: `research/model-training`

## 질문 및 목적

같은 일정과 같은 상대(Abyssal)에서, 같은 기술 연속 사용(streak)을 표시한 v6s 입력 모델이 v5+테라보다 배틀 성적이 나은가? 같은 기술 반복이 줄어드는가?

## 가설 또는 qualification 목표

- **진행 조건**: EX-141 학습·평가 완료만 본다. 오프라인 결과는 진행 여부를 정하지 않는다(D-191).
- **qualification**: 모델별 128슬롯이 처리되고, 분모 산술이 맞고, 봉인된다.
- **판정**(실행 전 동결): 같은 슬롯 점수 차이(`laya-v6st` − `laya-v5t`)를 조합(32) 클러스터 bootstrap 95%(10,000회, 시드 20261034)로 본다.
  - 하한 > 0 → "v6s가 배틀 성적을 개선"
  - 하한 > −0.05 → "비퇴보"
  - 그 외 → "퇴보를 배제하지 못함"
  - 어느 모델이든 정상 종료가 120/128 미만이면 판정을 보류한다.
- **보고 지표**(판정 외):
  - **결정성 확인**: 이번 v5t 128슬롯의 결과가 EX-137 v5t와 같은 슬롯에서 일치하는 수. 파서 opt-in 필드 추가가 v5 동작을 바꾸지 않았는지 확인한다.
  - **같은 기술 반복**: 같은 활성 포켓몬이 같은 기술을 3턴 이상 연속 쓴 구간의 수와 최장 길이(모델별), 실패·무효 기술 비율과 반복 지표(`comparison.failed_moves`), 테라 사용


## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| laya-v5t | EX-120 봉인 일정 128슬롯, Abyssal, 300턴/600결정, GPU0 서빙 | EX-136 selected, `laya-compact-v5[counters,damage,fails,items,moves,out,speed,switch]` | `runs/model-training/EX-143/games/v5t-*` |
| laya-v6st | 같음 | EX-141 selected, `laya-compact-v6[counters,damage,fails,items,moves,out,speed,streaks,switch]` | `runs/model-training/EX-143/games/v6st-*` |

- **진행 순서**: EX-137과 같은 구조다. EX-120 쌍마다 두 모델 쌍을 연달아 두고, 먼저 할 모델은 시드 20261034의 digest로 정한다.
- **fallback, 재질의, 재경기**: 없다. 단일 후보는 자동 제출한다.
- **분모**: 모델별 예정 128
- **단계 상한**: 10시간

## 환경 및 출처

- 배틀: `pokechamp/.venv`, `BattleServer`, 포트 8107(`port8107.lock`)
- 서빙: laya venv, GPU0(`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`, `gpu0.lock`, UUID와 유휴 확인), node 계산기
- 실행기: `scripts/laya-imitation compare10 {mock,prepare,execute,export}`, 연결 실행 `scripts/laya-imitation-ep221`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-143`

## 격리 및 오염 통제

- 일정: EX-120 collection 봉인을 확인한 뒤 복사한다.
- 자원 분리: GPU1·GPU2·GPU3과 그 포트는 쓰지 않는다. 다른 연결 실행(EX-144)과 같은 코드를 쓰므로 실행 중 코드를 고치지 않는다.
- **viewer 출력과 완료 요건**: [C-047](../../../CONTRACTS.md#c-047-viewer-export)에 따라 `/workspace/exports/battle_viewers/ex143/index.html`에 두고 상위 목록에 연결한다.
- **viewer 적용 규격**: [battle-viewer-ui-v1](../../../shared/viewers/CONTRACTS.md#battle-viewer-ui-v1), 생성기 `laya-imitation-researcher-v1`. 압축 입력 탭은 모델별 렌더러(v5/v6s)로 복원한다.
- **재개**: 원장 기준으로 미실행 슬롯만 진행한다.

## 절차

1. mock: v6s 렌더러와 기반 체크포인트(`laya-v6st-initial`, CPU)로 2경기. 분모 밖이다.
2. prepare: 두 체크포인트의 완료·봉인, 렌더러 일치, 일정 봉인을 확인한 뒤 동결한다.
3. execute: 256슬롯을 진행하고 경기별로 감사한다.
4. export: 보고, 뷰어, 오프라인 검사, 봉인

## 승인·무효화·중단 조건

- **승인**: 256슬롯이 처리되고, 분모 산술이 맞고, 봉인된다.
- **무효**: 입력 경계 위반, 신원 불일치, 감사 실패(그 경기만)
- **중단**: 10시간 상한, 수집 결함(phase 오류)

## 테스트·평가 도구 결함 복구

C-018과 EX-119 절차를 적용한다. 도구 결함으로 오염된 슬롯만 수정과 독립 검증을 거친 뒤 1회 재수집할 수 있다. 원본은 `diagnostics/`에 보존한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 배틀 run | `/mnt/.../runs/model-training/EX-143` | `checksums.sha256`, `report.md` | 예정 |
| 뷰어 | `/workspace/exports/battle_viewers/ex143/index.html` | `checksums.sha256` | 예정 |

## 결과

- 판정: **퇴보를 배제하지 못함**. 같은 슬롯 점수 차이(v6st − v5t) −0.023, 조합 클러스터 95% [−0.102, +0.055]. v6st가 나은 슬롯 10, v5t가 나은 슬롯 13, 같음 105.
- 모델별: v5t 109승 0무 19패, v6st 106승 0무 22패. 정상 종료 256/256.
- 결정성 확인: 이번 v5t 128슬롯이 EX-137 v5t와 결과·턴 수 모두 128/128 같다. 파서 opt-in 필드가 v5 동작을 바꾸지 않았다.
- 같은 활성 포켓몬의 같은 기술 3턴 이상 연속 구간(작업 중 집계, 정상 의도 반복 포함): v5t 195구간(5턴 이상 56, 최장 32), v6st 253구간(5턴 이상 77, 최장 32). v6st에서 Roost·Knock Off·Haze·Body Press 반복이 많았다.
- 테라 사용 경기: v5t 32, v6st 23.
- 기록: 2026-10-29 10:48~12:56 UTC 실행, 뷰어 `/workspace/exports/battle_viewers/ex143/index.html`(뷰어 검사 1440·390 통과)

## 분석 및 한계

- 상대는 Abyssal 하나이고 테라를 쓰지 않는다. Abyssal이 회복·내구 루프를 얼마나 만드는지에 따라 이 변경이 드러나는 결정 수가 제한될 수 있다(반복 구간 수로 센다).
- 128쌍 차이로 작은 효과는 구별되지 않을 수 있다.

## 결론 및 후속 작업

- 반복 표시(v6s)는 배틀 성적을 개선하지 못했고, 퇴보를 배제할 수도 없다. 같은 기술 반복 구간은 오히려 늘었다.
- 반복 구간 집계는 정상적인 반복(상대 교체 중 같은 공격 등)과 무의미한 루프를 구분하지 않는다. 루프만 따로 세려면 상대 HP 변화나 실패 여부로 나눠야 한다.
