# EP-227 — laya 렌더러 v10(정보 전부 + lock + 전략, 2,048토큰) 학습과 Abyssal 배틀

- 상태: Completed
- 생성일: 2026-11-03
- 책임자: Claude Code
- 승인 근거·범위: 사용자 설계 결정(2026-11-03 대화)과 [D-204](../decisions/D-204-laya-renderer-v10-all-info.md). **설계 단계다. 구현·자료 생성·측정·학습·배틀은 사용자가 시작을 지시한 뒤에 한다.** 2026-11-03 사용자 시작 지시("일단은 v10만으로 학습해보자", 상대 성향·내 패턴 정보와 확률 샘플링은 넣지 않음). 시작 지시 뒤에는 학습에서 배틀까지 이어서 진행하고, 오프라인 결과로 배틀을 거르지 않는다([D-191](../decisions/D-191-no-offline-battle-gate.md)).
- 관련 contract / decision / experiment: [C-055](../../../CONTRACTS.md#c-055-imitation), [EX-161](../experiments/EX-161-laya-v10-all-info-training.md), [EX-162](../experiments/EX-162-laya-v7t-v10t-battle256.md), [EX-149](../experiments/EX-149-laya-v7-opponent-sets-training.md), [EX-152](../experiments/EX-152-laya-v8-engine-fails-training.md), [EX-155](../experiments/EX-155-laya-v8l-likely-fails-training.md), [EX-157](../experiments/EX-157-laya-v9-opponent-threat-training.md), [EX-142](../experiments/EX-142-laya-v6h-long-history-training.md)
- 기준 연구선: `research/model-training`
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv(선택지 한도 인자가 들어간 새 worktree), `pokechamp/.venv`, node
- 새 산출물: `datasets/generated/laya-compact-features/v10`, `laya-compact-imitation/v10-all`, `runs/model-training/EX-161`·`EX-162`, 뷰어 `/workspace/exports/battle_viewers/ex162/`
- 참조 원자료(읽기 전용): EX-071 `prepared/`, `laya-item-state/v1`, `laya-early-history/v1`, `laya-engine-judge/v1`, `laya-compact-features/v5`, `usage_sets_v3.json`, EX-149 체크포인트(배틀 비교)

## 목표와 맥락

지금까지 따로 더해 온 정보(v1~v9)와 새 lock·전략 정보를 한 입력에 모두 넣은 v10을 학습하고, v7t와 같은 실행에서 Abyssal 상대 성적을 비교한다(D-204).

## 범위와 불변 조건

- **포함**:
  - laya 선택지 한도 인자(laya 저장소의 별도 PR, `tests/test_hooks_api.py` 갱신)
  - `integration/laya_v10/`, 실행 스크립트, 단위 검사, 기록
- **보존**: laya_imitation·laya_engine·laya_threat·laya_teamset 파일과 기존 자료·산출물·봉인은 바이트 단위로 같다. 기존 체크포인트 서빙은 선택지 48 그대로다.
- **자원**: GPU0·포트 8107(시작 시 비어 있음과 battle-window 표시 없음을 확인). 외부 프로세스 종료와 장치 reset은 금지한다.
- **배틀 표시**: EX-162 prepare 직전 `.pokechamp-data/battle-window/EX-162`를 두고, export 뒤 지운다.
- **외부 호출**: 없다.

## 완료 기준

- [x] D-204, EP-227, EX-161, EX-162 등록, catalog build/check
- [x] laya 선택지 한도 인자(`option_max_len`, 기본 48): `.tools/laya-0.4.13/worktrees/pokemon-v10` 미커밋 변경, 패치 `.tools/laya-0.4.13/pokemon-v10-option-len.patch`. CI 게이트(ruff, compileall, router·criteria·hooks·hooks_api)와 새 `tests/test_option_max_len.py` 통과. 기본값은 0.4.13과 바이트 단위로 같다. laya 저장소 PR은 사용자가 요청할 때 연다
- [x] `laya_v10` 구현(`history`, `lock`, `strategy`, `render_v10`, `data_v10`, `training_v10`, `serve_v10`, `evaluation_v10`, `battle_v10`, `cli`, `pp_gen9.json`), 단위 검사 6개(기록·PP·Pressure·lock·v7 줄 보존·결정성), ruff 통과. 연결 실행 `scripts/laya-imitation-ep227 run`, 로그 `runs/model-training/EP-227.log`
- [x] 사전 측정(validation 512) → 한도 확정 → 사실값·자료·parity
- [x] EX-161 학습·평가·봉인
- [x] EX-162 mock → prepare → execute → export·뷰어 확인
- [x] 결과를 EX 문서, STATUS, catalog에 기록

## 절차

1. 사용자 시작 지시를 확인한다.
2. laya PR을 만들고 worktree를 준비한다.
3. 구현과 단위 검사를 한다.
4. 사전 측정을 한다(D-204 결정 5의 한도 규칙).
5. 사실값 → 자료 → parity를 만든다.
6. EX-161 학습과 평가를 한다.
7. EX-162 배틀을 한다.
8. 기록한다.

연결 실행 스크립트 하나로 4~7을 잇는다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 자동 재실행은 없다. 각 EX의 중단 조건에서 멈춘다. 정보별 확인 지표는 중단 조건이 아니다(D-204).

## 진행

- 2026-11-03 — 사용자와 설계했다. 정보 범위(#1~41), 2,048토큰, 평가는 Abyssal까지, 1,024 판본 없음, 확인 지표는 보고 전용으로 정했다. 학습 시작점은 `e929ae5c`로 정했다(D-204 결정 4). 실행하지 않았다.
- 2026-11-03 — 사용자 시작 지시. laya 선택지 한도 인자는 `.tools/laya-0.4.13/worktrees/pokemon-v10`(branch `pokemon-v10-option-len`, 기준 6f0496f7)에서 커밋 없이 작업하고, v10 실행은 `PYTHONPATH`로 이 worktree를 앞세워 기존 venv를 쓴다(기존 `pokemon-training` worktree는 그대로).
- 2026-11-03 — 구현 메모: 기존 패키지는 고치지 않는다. 학습·평가는 v10 프로세스 안에서 `laya.train` 함수에 선택지 한도를 넘기고, `laya_imitation.policy.Policy`를 `Policy10`으로 바꾼다(`training_v10.install`). 배틀 워커는 `integration.laya_v10.battle_v10 worker`이며, v10 모델 요청에만 `early_history`를 넣는다(v7t 입력 불변). 사실값 저장소(`laya-compact-features/v10`)는 따로 만들지 않고 v9처럼 자료 생성 때 행마다 계산한다. 렌더 속도 약 0.07초/행.
- 2026-11-03 — CPU 확인: validation 512행에서 표시가 있는 행 수: `board` 512, `wincon` 506, `answer` 504, `duel` 388, `opp threat` 389, `risk` 386, `opp wall` 302, `hazards` 281, `opp heals` 266, `tera takes` 182, `locked?` 34, `pp` 26, `locks` 21(사람이 고른 행 15), `locked` 8, `likely fails` 8. 학습 경로에서 선택지 64토큰이 실제로 쓰이는 것을 확인했다. 레인을 시작했다.
- 2026-11-03 05:28Z — 사전 측정(validation 512): 기본 한도(2,048 / head 768 / 선택지 64)에서 제외 0. 전체 p50 990, p99 1,296, 최대 1,370. head 최대 562. 선택지 p95 52, 최대 55. 한도를 확정했다.
- 2026-11-03 05:29Z — 자료 생성 도구 결함: `strategy._run`의 계산 캐시가 20만 개를 넘을 때, 이미 캐시에 있다고 센 키까지 지운 뒤 조회해 KeyError가 났다. 기록된 행은 없었다(train 분할 미완료, 빈 `v10-all` 디렉터리는 지웠다). 기록은 `runs/model-training/EX-161/diagnostics/data-v1/defect.json`에 남겼다. 비우는 순서를 고쳤고 회귀 검사를 추가했다(검사 7개 통과). 렌더 결과는 바뀌지 않으므로 측정은 다시 하지 않았다. 05:30Z에 레인을 다시 시작했다(C-018 복구 절차, 학습 시작 전).
- 2026-11-03 05:30Z — 자료 train 130,411 · validation 512 · test 1,024, 제외 0. 05:35Z parity 512행 불일치 0. 05:36Z 학습 시작(사전검사 loss 2.1553 → 1.9875).
- 2026-11-03 19:56Z — 학습 완료(3 epoch 51,412초, 선택 epoch 2). 평가 19:56~19:59Z.
- 2026-11-03 19:59Z — EX-162 mock 2/2 정상. 20:01Z battle-window 표시, prepare(256슬롯, 서빙 v7t `2b654e32…`, v10t `d440b0f1…`), execute(22:25Z 종료), export, 22:31Z 표시 삭제, 뷰어 확인 통과. 레인 22:31:35Z 정상 종료.

## 결과 및 증거

- [EX-161](../experiments/EX-161-laya-v10-all-info-training.md): 잠긴 test NLL 1.4332 → 1.3686(같은 행 −0.0610, 95% [−0.0918, −0.0288]), 일치율 45.78 → 48.63%. 실패 선택지 확률 합 0.0528 → 0.0313, 최악 80% 이상 교체 확률 합 0.2064 → 0.1833, `locks` 행 일치율 +11.86%p. 테라 지식 A 96.9 → 96.2%.
- [EX-162](../experiments/EX-162-laya-v7t-v10t-battle256.md): v7t 112-16, v10t 111-17, 차이 −0.0078 [−0.0703, +0.0547] → 퇴보를 배제하지 못함. 기술 실패율 5.17 → 1.91%, 결정 지연 p50 0.143 → 0.219초.
- 결론: v10은 사람 선택 재현과 실패 선택지 회피가 v7보다 낫지만, Abyssal 성적은 구별되지 않는다(포화). v10t는 laya-play v1.9.0에 배포했고, 래더 자료를 더한 후속은 [EP-230](EP-230-laya-ladder-r1500-v10.md)이다.
