# EP-223 — laya 손해 루프 탈출(가중 학습·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험(GPU0~3)

- 상태: Completed
- 생성일: 2026-10-31
- 책임자: Claude Code
- 승인 근거·범위: 사용자 지시(2026-10-31, "취침 중 가용 GPU로 최대한 많은 실험을 승인 없이 진행")와 [D-200](../decisions/D-200-laya-loop-break-opponent-sets.md). 구현, 학습, 평가, 배틀을 별도 승인 없이 이어서 진행한다. 오프라인 결과로 배틀을 거르지 않는다([D-191](../decisions/D-191-no-offline-battle-gate.md)).
- 관련 contract / decision / experiment: [C-055](../CONTRACTS.md#c-055-imitation), [EX-146](../experiments/EX-146-laya-v6sl-loop-weighted-training.md), [EX-147](../experiments/EX-147-laya-v6st-v6slt-battle256.md), [EX-148](../experiments/EX-148-laya-loop-decision-rule.md), [EX-149](../experiments/EX-149-laya-v7-opponent-sets-training.md), [EX-150](../experiments/EX-150-laya-v6st-v7t-battle256.md), [EX-141](../experiments/EX-141-laya-v6s-streaks-training.md), [EX-143](../experiments/EX-143-laya-v5t-v6st-battle256.md), [EX-144](../experiments/EX-144-laya-v5t-v6ht-battle256.md)
- 기준 연구선: `research/model-training`
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv, `pokechamp/.venv`, node. 실행기 `scripts/laya-imitation`, 연결 실행 `scripts/laya-imitation-ep223 <lane>`
- 새 산출물과 검증 출력 위치:
  - `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/laya-loop-weights/v1`
  - `.../laya-compact-features/v7`, `.../laya-compact-imitation/v7-all`
  - `.../runs/model-training/EX-146` ~ `EX-150`, 연결 실행 로그 `.../runs/model-training/EP-223-<lane>.log`
  - 뷰어 `/workspace/exports/battle_viewers/ex147/`, `ex148/`, `ex150/`
- 참조 원자료(읽기 전용): `v6s-all`, `laya-compact-features/v5`, EX-071 `prepared/`, EX-141·EX-142 산출물, EX-143·EX-144 경기, 사람 대전 `/workspace/data/NHJ-20261101`

## 목표와 맥락

NHJ-20261101 사람 대전에서 보인 두 약점(회복·Protect 상대 손해 루프, 미공개 상대의 보편 세트 미예측)에 대해 세 가지 방법을 동시에 측정한다. 조건과 판정은 각 EX가 소유한다.

## 범위와 불변 조건

- **포함**: D-200 영향 절의 새 코드와 수정, 설정·Spec·Study, CLI, 연결 실행 스크립트, 단위 검사
- **보존**:
  - 기존 렌더러·사실값 파일(`serving.V6_RENDER_FILES`, `features_v3.py`, `usage_sets_v3.json`)은 바이트 단위로 같다. v1~v6 출력, 서빙 동일성 검사, EX-118~145 산출물·봉인은 그대로다.
  - 사람 라벨과 분할은 바꾸지 않는다.
- **자원**:
  - GPU0·8107: v7 자료 생성 뒤 EX-149 학습 → EX-150
  - GPU1·8109: EX-146 학습 → EX-147
  - GPU2·8108: EX-148 v6st-lp
  - GPU3·8106: EX-148 v6ht-lp
  - 외부 프로세스 종료와 장치 reset은 금지한다. laya-v6test 실행기(GPU3·8310/8380)가 켜져 있으면 EX-148 v6ht-lp는 GPU3 대신 GPU2 레인 뒤에 이어 둔다.
- **외부 호출**: 없다.
- **코드 동결**: 첫 배틀 prepare 전에 모든 코드와 단위 검사를 끝낸다. 그 뒤 연결 실행이 모두 끝날 때까지 `integration/laya_imitation`을 수정하지 않는다.

## 완료 기준

- [x] D-200, EP-223, EX-146~150 등록, catalog build/check
- [x] `loop_weights` 생성·봉인(완료), EX-146 학습·평가(진행 중)
- [x] `loop_decision`, 서빙 모델 이름, EX-148 오프라인 지표, mock, 배틀 두 레인
- [x] v7 렌더러·사실값, 단위 검사, 사전 측정, `v7` 정보 캐시·`v7-all` 자료·parity, EX-149 학습·평가
- [x] EX-147, EX-150 mock·배틀·보고·뷰어
- [x] 결과를 EX 문서, STATUS, catalog에 기록

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| 기존 렌더 보존 | 렌더러 파일 해시가 v6s-all `generator-source`와 같음(`renderer_matches_dataset('v6s')`) | `tests/test_loop_v7.py` | 통과(코드 동결 시 단위 검사 114 통과·5 skip, v6s·v6h·v7 렌더러 동일) |
| 루프 규칙 | 정체·진행·대안 없음·교체 직후 사례 | `tests/test_loop_v7.py` | 통과(파일 전체 8건). 배틀 재현 검사: 규칙 미작동 경기 83/83·82/82가 기준과 같음 |
| v7 세트 표시 | 공개 칸 고정, 제거 아이템, watch, 벤치 요약, Protean 압정 실패 | `tests/test_loop_v7.py` | 통과(파일 전체 8건) |
| 오프라인·서빙 일치 | `v7 parity` validation 512행 | `EX-149/diagnostics/parity.json` | 511행 불일치 0(길이 초과 1행 제외) |

## 진행

- 2026-10-31 — 승인과 등록. 구현과 단위 검사(`tests/test_loop_v7.py` 8건, 관련 v6·서빙·직접 대결 검사 포함 42건 통과).
- 2026-10-31 17:16Z — `laya-loop-weights/v1` 생성(정체 루프 사람 변경 1,456행 ×4, 평균 1, scale 0.9676)·봉인. EX-146 사전검사 통과 뒤 GPU1 레인 시작.
- 2026-10-31 — EX-149 사전 측정: 벤치 기술 3개에서 validation 초과 8/512(1.56%) → D-200 사전 등록 순서대로 2개로 줄여 1/512(0.20%). 확정 특성(usage ≥ 0.995)도 `opp set`에 표시하도록 바꾼 뒤 재측정 1/512.
- 2026-10-31 17:29Z — GPU0 레인 시작: `v7-all` 생성(제외 454행, 0.344%), parity 511/511, EX-149 학습 시작.
- 2026-10-31 — EX-148 mock 2/2 정상(감사 통과, 응답 24건 모두 `loop_rule` 기록). EX-148 오프라인(EX-141 잠긴 test): 정체 행 22, 규칙 작동 11. 사람이 바꾼 6행에서 argmax 0·규칙 5 일치, 사람이 또 쓴 5행에서 argmax 5·규칙 0 일치(표본이 작아 보고만).
- 2026-10-31 — mock: EX-150 2/2, EX-148-H1 4/4 정상. EX-148-H2 첫 mock은 직접 대결 worker가 `early_history`를 요청하지 않아 HTTP 422로 멈췄다(`mock-failed-1-no-early-history`로 보존). `headtohead.worker`에 battle과 같은 opt-in을 넣고 다시 4/4 정상. 직접 대결 뷰어 export에 v6s·v6h·v7 렌더러를 추가했다.
- 2026-10-31 — 후속 직접 대결 EX-147-H(GPU2, v6slt 대 v6st)·EX-150-H(GPU3, v7t 대 v6st)를 `scripts/laya-imitation-ep223b`로 추가했다(학습 봉인 뒤 시작).
- 2026-10-31 17:40Z — 코드 동결(`.pokechamp-data/ep223-code-frozen`, 단위 검사 114 통과·5 skip, v6s·v6h·v7 렌더러 동일). `lp`(GPU2)·`lp-h2h`(GPU3)·`h2h147`·`h2h150` 레인 시작. EX-148 첫 6경기 정상, 규칙이 작동하지 않은 경기는 기준과 결과·턴 수가 같다.
- 2026-10-31 23:23Z — EX-148-H2 export 실패: 실행기가 `h2h`를 배틀 환경(pokechamp venv)으로 실행하는데, v6h 렌더러의 길이 맞춤(`data_v6.fitter`)은 laya 토크나이저가 필요하다(`ModuleNotFoundError: laya`). 경기(123/128 정상)와 판정은 영향 없다. 이 때문에 EX-148-H2를 기다리던 EX-150-H가 시작되지 않았다.
- 2026-11-01 23:5xZ — `scripts/laya-imitation`에서 `h2h … export`만 laya 환경으로 실행하도록 고쳤다(그 밖의 h2h 단계는 그대로). 빈 뷰어 디렉터리를 지우고 EX-148-H2 export를 다시 실행해 완료·봉인했다.
- 2026-11-02 00:00Z — 대기 중이던 `h2h150` 레인이 EX-150-H를 시작했다: mock 4/4 정상, prepare(v7t `2b654e32…`, v6st `5a93ba95…`), 00:03Z execute(GPU3·8106).
- 2026-11-02 — EX-150 실패 기술 증가(v6st 86 → v7t 171) 분석(읽기 전용):
  - 경기 5판에 142건이 몰려 있다. 그중 3판(m06-s2-b 115턴, m31-s1-b 111턴, m30-s1-a 118턴)은 `; fails`로 표시된 수를 반복했다(Gliscor Spikes ×29, 지면 무효 상대 Earthquake ×29, Gholdengo에 Body Press ×14, Sleep Talk ×13).
  - v7t가 표시된 실패 수를 고른 85결정 모두에 실패하지 않는 선택지가 있었다. 표시된 선택지의 확률 합 평균은 v7t 0.81, v6st 0.53이다.
  - 잠긴 test(실패 표시 행 234)에서는 차이가 작다: 표시된 선택지 확률 합 EX-141 0.038, EX-149 0.048, EX-146 0.037. argmax 3·4·1회.
  - 표시 없는 실패는 규칙 공백이다. 상대가 마지막 한 마리일 때 Whirlwind ×32(m09-s1-b). 등장 뒤 이미 행동한 First Impression ×15(m22-s1-b, 서빙에서 `acted`를 모름).
  - 5판 중 v7t는 4승 1패다(같은 슬롯 v6st는 18~52턴에 끝났다).
- 린트: `data_v7.py` 미사용 import 2건(F401)은 v7 `generator-source`에 고정된 파일이라 고치지 않았다(동작 무관).
- 운영 메모: GPU1 레인 실행 중 `scripts/laya-imitation-ep223`을 고쳤다. bash가 `case` 블록을 이미 읽어 레인 동작(학습·평가·EX-147 mock 포함 배틀)은 그대로이고, 마지막 완료 줄만 문법 오류로 끝난다. EX-147 mock은 이 레인이 직접 실행한다.
- 2026-10-31 20:01Z — `lp-h2h` 레인: EX-148-H1 17:40Z~19:58Z, 127/128 정상(미완료 1), 구별되지 않음. 뷰어 자동 확인은 표 행 수 assertion에서 실패했다(직접 대결 뷰어의 기존 문제, 경기와 무관). 이어서 EX-148-H2 실행(위 23:23Z 항목).
- 2026-10-31 20:32Z — `lp` 레인 종료: EX-148 17:41Z~20:28Z, 256/256 정상, 재현 검사 83/83·82/82, 뷰어 확인 통과.
- 2026-11-01 05:43Z — `h2h147` 레인 종료: EX-147-H mock 4/4, 02:53Z~05:40Z 128/128 정상. 뷰어 자동 확인은 같은 assertion에서 실패했다.
- 2026-11-01 05:47Z — `v6sl` 레인 종료: EX-146 학습 17:16Z~02:45Z·평가, EX-147 mock 2/2, 02:48Z~05:45Z 256/256 정상, 뷰어 확인 통과. 마지막 줄은 위 운영 메모대로 문법 오류로 끝났다.
- 2026-11-01 07:11Z — `v7` 레인 종료: EX-149 학습 17:30Z~04:26Z·평가, EX-150 04:29Z~07:09Z 256/256 정상, 뷰어 확인 통과.
- 2026-11-02 02:25Z — `h2h150` 레인 종료: EX-150-H 00:03Z~02:21Z, 126/128 정상(미완료 2). 뷰어 자동 확인은 같은 assertion에서 실패했다. 이로써 EP-223 레인이 모두 끝났다. 직접 대결 뷰어 세 개(`ex147-h2h`, `ex148-h2h-v6st`, `ex150-h2h`)와 다시 export한 `ex148-h2h-v6ht`의 수동 확인 기록은 없다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 자동 재실행은 없다. 각 레인은 실패한 단계에서 멈추고 다른 레인은 계속한다.

## 결과 및 증거

- [EX-146](../experiments/EX-146-laya-v6sl-loop-weighted-training.md): 잠긴 test NLL 1.4286 → 1.4357(+0.0071, 95% [−0.0145, +0.0283]), 일치율 48.29 → 47.31%. 정체 행 반복 확률은 사람이 바꾼 9행 0.4012 → 0.2807, 사람이 또 쓴 12행 0.7325 → 0.6399로 함께 줄었다.
- [EX-147](../experiments/EX-147-laya-v6st-v6slt-battle256.md): v6st 106-22, v6slt 98-30, 차이 −0.0625 [−0.1484, +0.0234] → 퇴보를 배제하지 못함. 실패 기술 86 → 52, 테라 사용 경기 23 → 10. 직접 대결 EX-147-H v6slt 60-68(0.469 [0.383, 0.555]) → 구별되지 않음.
- [EX-148](../experiments/EX-148-laya-loop-decision-rule.md): v6st-lp 0.828 대 EX-143 0.828, 차이 0.0000 [−0.0391, +0.0391] → 구별되지 않음. v6ht-lp 0.867 대 EX-144 0.789, 차이 +0.0781 [+0.0312, +0.1328] → 규칙이 배틀 성적을 개선. 긴 반복 75 → 48, 107 → 52. 직접 대결 H1 0.472 [0.406, 0.543], H2 0.431 [0.355, 0.504] → 둘 다 구별되지 않음.
- [EX-149](../experiments/EX-149-laya-v7-opponent-sets-training.md): 잠긴 test NLL 1.4286 → 1.4332(+0.0016, 95% [−0.0274, +0.0300]), 일치율 48.29 → 45.78%. 강제 교체 행 NLL +0.0754 [+0.0238, +0.1267]. 미공개 칸 묶음별 차이는 모두 0을 포함한다.
- [EX-150](../experiments/EX-150-laya-v6st-v7t-battle256.md): v6st 106-22, v7t 112-16, 차이 +0.0469 [−0.0234, +0.1172] → 비퇴보. 실패 기술 86 → 171(5판에 142건). 직접 대결 EX-150-H v7t 61-65(0.484 [0.413, 0.555]) → 구별되지 않음.
- 결론: Abyssal 상대 개선은 v6ht의 루프 결정 규칙에서만 나왔고, 같은 체크포인트 직접 대결로는 확인되지 않았다. 가중 학습(v6slt)은 퇴보를 배제하지 못했다. v7t는 비퇴보이지만 표시된 실패 수 반복과 규칙 공백으로 실패 기술이 늘었고, 이것이 [EP-224](EP-224-laya-engine-judge-v8.md) 엔진 판정기로 이어졌다.
