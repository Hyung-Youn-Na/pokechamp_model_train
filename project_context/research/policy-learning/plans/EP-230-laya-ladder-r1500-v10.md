# EP-230 — 최근 래더(레이팅 1500 이상) 리플레이 자료와 v10 학습(GPU 4장 DDP), Abyssal 배틀

- 상태: Completed
- 생성일: 2026-11-04
- 책임자: Claude Code
- 승인 근거·범위: 사용자 결정(2026-11-04 대화)과 [D-208](../decisions/D-208-laya-ladder-r1500-v10.md). 사용자가 수집에서 배틀까지 진행을 지시했다. 오프라인 결과로 배틀을 거르지 않는다([D-191](../decisions/D-191-no-offline-battle-gate.md)).
- 관련 contract / decision / experiment: [C-055](../../../CONTRACTS.md#c-055-imitation), [D-207](../../../shared/datasets/decisions/D-207-lift-reviewed108-species-limit.md), [EX-166](../experiments/EX-166-laya-ladder-r1500-data.md), [EX-167](../experiments/EX-167-laya-v10-ladder-training.md), [EX-168](../experiments/EX-168-laya-v10t-v10rt-battle256.md), [EX-161](../experiments/EX-161-laya-v10-all-info-training.md), [EX-162](../experiments/EX-162-laya-v7t-v10t-battle256.md)
- 기준 연구선: `research/model-training`
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv(`pokemon-v10` worktree 우선, EP-227과 같음), `pokechamp/.venv`, Metamon CPU venv, node
- 새 산출물:
  - 원본: `/workspace/data/showdown-replays/ladder-recent/gen9ou-r1500-newest/`
  - 자료: `datasets/generated/laya-ladder-source/v1`, `laya-ladder-item-state/v1`, `laya-ladder-features-v5/v1`, `laya-ladder-early-history/v1`, `laya-ladder-engine-judge/v1`, `laya-compact-imitation/v10-ladder`, `v10-ladder-merged`
  - 실행: `runs/model-training/EX-166`·`EX-167`·`EX-168`, 뷰어 `/workspace/exports/battle_viewers/ex168/`
- 참조 원자료(읽기 전용): `ladder-index/gen9ou-20260504-20261104`, Metamon 팀 캐시(`/tmp/metamon_cache/teams/modern_replays/gen9ou`), `/workspace/data/smogon-stats/chaos/`, EX-071 `prepared/`, `v10-all`, 테라 지식 train, EX-161 체크포인트, EX-120 일정

## 목표와 맥락

대회 리플레이 2,793경기(EX-071)에 최근 래더 경기를 더해 같은 v10 입력으로 학습하고, v10t와 Abyssal 상대 성적을 비교한다(D-208).

## 범위와 불변 조건

- **포함**: `integration/laya_ladder/`(수집 정리, 분류·필터, 세트 보강, 특성 귀속 수정 복원, 행 생성, 저장소 경로 바꿔 끼우기, DDP 학습, 평가·배틀 등록), 실행 스크립트, 단위 검사, 기록
- **보존**: `laya_imitation`·`laya_v10`·`laya_engine`·`laya_threat`·`pokechamp/imitation` 파일과 기존 자료·산출물·봉인은 바이트 단위로 같다. 사람 테스트 실행기(`.artifacts/laya-v7test`, CPU)는 건드리지 않는다.
- **자원**:
  - 학습: GPU0~3 전부(시작 시 비어 있음과 battle-window 표시 없음을 확인)
  - 배틀: GPU0·포트 8107
  - 외부 프로세스 종료와 장치 reset은 금지한다.
- **배틀 표시**: EX-168 prepare 직전 `.pokechamp-data/battle-window/EX-168`을 두고, export 뒤 지운다.
- **외부 호출**: 공개 리플레이 로그 받기(`replay.pokemonshowdown.com`, 연결 3개, 요청 사이 0.4초)뿐이다. 학습·서빙은 외부 호출이 없다.

## 완료 기준

- [x] D-208, EP-230, EX-166~168 등록, catalog build/check
- [x] 최신 25,000경기 로그 받기
- [x] `laya_ladder` 구현과 단위 검사(특성 귀속 수정, 보강 결정성, 분할, DDP 1 step이 단일 GPU와 같은 loss)
- [x] EX-166: 분류·필터 → 세트 보강 → 복원 → 행 → 저장소 → v10 행 → 예산 → 합친 자료
- [x] EX-167: 사전 측정(4장 처리량) → 학습 → 평가·봉인
- [x] EX-168: mock → prepare → execute → export·뷰어 확인
- [x] 결과를 EX 문서, STATUS, catalog에 기록

## 절차

1. 로그를 받는다(백그라운드).
2. 구현과 단위 검사를 한다.
3. EX-167 사전 측정으로 래더 train 행 수를 정한다(3 epoch ≈ 24시간).
4. EX-166 자료를 만든다.
5. EX-167을 학습하고 평가한다.
6. EX-168 배틀을 한다.
7. 기록한다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 자동 재실행은 없다. 각 EX의 중단 조건에서 멈춘다.

## 진행

- 2026-11-04 — 사용자와 조건을 정했다(D-208). 05:59Z부터 최신 25,000경기(08-19 23:11Z ~ 11-04 01:30Z) 로그 받기를 시작했다. 봇 이름 30개를 뺐다.
- 2026-11-04 — DDP 학습기 `laya_ladder.train_ddp`:
  - 각 GPU 프로세스는 자기 몫(고정 순열의 rank, rank+4, …)만 읽고 토큰화한다(메모리 125 GB).
  - 검사 세 번이 실패했고, 원인은 모두 검사 쪽이었다.
    - 0번 프로세스 검증 단계가 `array('i')` 토큰을 list로 기대했다(검증 항목은 list로 둠).
    - laya 헤드의 dropout 0.1 때문에 같은 입력도 train 모드에서 매번 달랐다.
    - DDP는 eval 모드에서 기울기를 동기화하지 않는다.
  - 원인 하나는 DDP 쪽이었다. 기울기가 없는 `act_head` 4개가 버킷 동기화를 막았다. `act_head`를 고정해 해결했다.
  - 최종 검사: dropout 0·train 모드에서 4장(8×2×4)과 1장(8×8)의 손실이 같고, 기울기 상대 차이 1.4e-6, 재로딩 logit 차이 0. `runs/model-training/EX-167/check/result.json`.
- 2026-11-04 — 4장 처리량(v10-all train, 갱신 60회, 장당 8 × 누적 2): checkpointing 켬 0.0269초/행(장당 최대 9.9 GB), 끔 0.0216초/행(22.0 GB). GPU 1장 EX-161 0.091초/행의 3.4배·4.2배. `runs/model-training/EX-167/measure/`.
- 2026-11-04 — 특성 귀속 수정(`laya_ladder.abilities`, 줄 수 유지 재작성): 탐색 표본 878경기에서 지원 시점의 불가능한 특성 13 → 1, 특성이 바뀐 자리 34, `conflicting_original_ability`로 빠지던 시점 3개가 살아났다. 기술·도구는 바뀌지 않았다.
- 2026-11-04 — 끝까지 시험(표본 160경기, `.pokechamp-data/laya-ladder-trial`):
  - 원천 단계는 Kev 환경(`/ref/kev/.venv`, EX-071 `KEV_PYTHON`)에서 돈다. Qwen 토크나이저 검사가 peft를 요구한다.
  - Pool 초기화 실패가 작업 프로세스를 무한히 다시 띄우는 문제를 고쳤다(오류를 첫 작업에서 올림).
  - 래더 행은 EX-071처럼 D-195 이전 스냅샷 형식으로 저장한다. 처음에는 현재 파서 형식이라 item-state 동일성 검사가 전부 달랐다.
  - 결과: 선별 116경기, 보강 60세트, eligible 7,022행(남은 경기당 약 61행), item-state·early-history 동일 7,022/7,022, v10 제외 0, parity 210/210, `generator_matches` 참. DDP 학습 경로(3 epoch, 선택, 온도)도 작은 자료로 끝까지 돌았다.
- 2026-11-04 — 합치기 시험: 래더 행 길이는 v10-all의 0.979배, 예산은 학습 행 1,304,181(래더 1,117,027). 25,000경기로 모자랄 수 있어 받기가 끝나면 5,000경기를 더 받는다.
- 2026-11-04 — 08:32Z 25,000경기 받기 완료, 09:02Z 30,000경기로 늘림 완료. 09:02Z EX-166 원천 단계가 분류 뒤 `select`에서 멈췄다(`ValueError: expected six distinct species`). 후보 26,901 중 3경기에서 한쪽 팀이 5마리였다. 이 경기를 `not_six_species`로 빼도록 고치고(D-208 결정 2) 레인을 다시 시작했다. 분류 결과는 그대로 재사용한다.
- 2026-11-04 — 선별 25,296경기(test 150·validation 60·train 25,086), 복원 train eligible 1,580,283행, item-state 동일 1,581,819/1,581,819. 10:15Z early-history 단계에서 저장소 프로세스가 메모리 부족으로 죽었다(`Killed`). 기존 `early_history.reparse`는 모든 행의 결과를 메모리에 모은다. `laya_ladder.stores._early_history`가 같은 shard·worker·동일성 규칙으로 결과를 디스크에 두고 offset으로 읽어 쓴다. 표본 160경기 자료에서 기존 함수 결과와 파일·summary·parity가 바이트 단위로 같다(manifest는 시각과 `driver`만 다름). 합치기도 래더 train을 메모리에 올리지 않게 바꿨다(표본에서 같은 경기·행, 래더 행 순서만 파일 순서). 10:37Z 레인을 다시 시작했다.
- 2026-11-04 — 저장소 완료: early-history 동일 1,581,819/1,581,819(10:37Z 재시작 뒤), 엔진 판정 11:26Z, v10 행 12:30Z(길이 초과 제외 0), parity 512/512·`generator_matches` 참. 합치기 12:32Z: 래더 최신 17,510경기 1,111,776행(가장 오래된 업로드 2026-08-23T22:47Z), 학습 행 합계 예산 1,298,921, 예상 24.0시간.
- 2026-11-04 — 12:32Z EX-167 학습 시작 단계에서 멈춤: `resources.gpu`의 `nvidia-smi` 확인이 커널 D 상태로 돌아오지 않는다. 다른 터미널의 `watch -n 1 nvidia-smi`가 10:13:42Z에 띄운 `nvidia-smi`가 `do_exit` 중 D 상태로 남아 있고(10:15Z 메모리 부족과 같은 시각), 이후 모든 `nvidia-smi`가 드라이버 잠금(`down`)에서 막힌다. 학습 프로세스와 `status.json`은 아직 없다. 장치 reset·외부 프로세스 종료는 범위 밖이라 사용자 판단을 기다린다. 드라이버가 풀리면 대기 중인 레인이 그대로 학습을 시작한다.
- 2026-11-05 — 사용자가 메모리 문제로 호스트를 강제 재부팅했다(05:11Z 부팅). 확인:
  - EX-167에는 `check/`·`measure/`뿐이고 `status.json`·체크포인트가 없다. `status.json`은 각 프로세스가 자기 몫을 읽고 토큰화한 뒤 쓰므로, 학습은 시작되지 않았거나 자료를 읽는 중에 끊겼다. EP-230.log는 12:32:09Z `EX-167 train` 줄에서 끝난다.
  - 메모리 부족은 11-04 10:15Z early-history 저장소 단계(기존 driver)의 것이 기록상 유일하다. 그때 멈춘 `nvidia-smi`로 드라이버가 잠겼다(위 항목).
  - 학습 적재 메모리(CPU, 합친 train 4,000행 표본에서 외삽): 프로세스당 약 6.9 GB(행 1.4 GB + 토큰 항목 5.5 GB), 4개 약 28 GB. 호스트 125 GB 안이다.
  - 재부팅 뒤: GPU0~3 UUID 같음, 사용 0 MiB, D 상태 프로세스 없음. 봉인 확인: 원천 `prepared`, item-state, v5, early-history, 엔진 판정, `v10-ladder`, `v10-ladder-merged`, `v10-all` 모두 정상.
  - 사용자 지시로 학습·테스트는 다시 시작하지 않았다. v10t 사람 테스트 실행기도 재부팅으로 꺼진 채다.
- 2026-11-05 — 사용자 지시: "프로세스의 메모리 최대제한을 100GB로 제한해서 학습을 시작". 컨테이너의 memory cgroup은 읽기 전용(Docker, cgroup v1, CAP_SYS_ADMIN 없음)이라 커널 한도를 걸 수 없어 `scripts/mem-guard`로 대신했다.
  - 명령의 프로세스 트리와 세션 전체 PSS 합을 2초마다 재고, 100 GB를 넘으면 전부 SIGKILL한다.
  - 모든 프로세스의 `oom_score_adj`를 1000으로 두어, 커널 OOM이 나도 이 프로세스들이 먼저 죽는다.
  - 1 GB 한도 시험에서 fork한 자식까지 종료되고 정상 종료 코드가 전달됨을 확인했다. 사용량은 `runs/model-training/EX-167-memory.log`에 1분마다 남는다.
  - 23:43Z EX-167 학습만 시작했다(`train_ddp train`, 레인 아님). 평가와 EX-168은 학습 뒤 사용자 확인을 받는다.
- 2026-11-06 — 22:55Z EX-167 학습 종료(exit 0, mem-guard 최대 45.0 GB, 82,826초). validation(v10-all 512 + 래더 512) 원 NLL: 학습 전 2.0766, epoch 1 1.4729, 2 1.3861, 3 1.3681. 선택 epoch 3, 온도 1.081(보정 NLL 1.3628, ECE 0.025). EX-161 validation(v10-all 512)과는 구성이 달라 비교하지 않는다. `runs/model-training/EX-167/selection.json`.
- 2026-11-07 — 사용자 지시로 06:31Z 레인 `scripts/laya-ladder-ep230 run`을 mem-guard 100 GB로 다시 실행했다(사용량 `runs/model-training/EX-168-memory.log`). EX-167 평가 뒤 EX-168 mock·prepare·execute·export로 이어진다.
- 2026-11-07 — 06:38Z EX-167 평가 완료(`runs/model-training/EX-167/report.md`). 잠긴 test, EX-167 − EX-161 같은 행 차이(replay 클러스터 95%): EX-071 대회 test NLL 1.3686 → 1.3305, −0.0380 [−0.0702, −0.0059], 일치율 +0.98%p; EX-166 래더 test 1.4274 → 1.3284, −0.0990 [−0.1388, −0.0594], +5.18%p. 대회 test의 교체 행은 −0.0049 [−0.0651, +0.0559]로 구별되지 않는다.
- 2026-11-07 — 06:39Z EX-168 mock 실패(배틀 0경기): 배틀 워커(pokechamp env, laya 없음)가 `laya_ladder.battle`을 불러올 때 맨 위 `from .serve import MODEL`이 `serve_v10 → laya_imitation.policy → laya`를 끌어와 `ModuleNotFoundError`로 끝났다. `laya_ladder/serve.py`가 `serve_v10`을 `__main__`에서만 불러오도록 고쳤다(prepare 전이라 동결 해시 없음). 실패 기록은 `runs/model-training/EX-168/diagnostics/mock-failed-1/`. 06:40Z 레인 재실행, mock 2경기 정상(감사 통과), 06:41Z battle-window 표시 후 prepare.
- 2026-11-07 — EX-168 완료(06:41:51Z execute → 08:44Z export → 08:56Z 레인 종료, exit 0, mem-guard 최대 9.3 GB). 정상 256/256. v10rt 110-0-18(0.859), v10t 111-0-17(0.867), 같은 슬롯 차이 −0.0078 [−0.0859, +0.0703] → **퇴보를 배제하지 못함**(우세 9 대 10, 같음 109). 보고 지표: 테라 사용 경기 33 대 27, 실패·무효 2.00% 대 1.91%(v10rt Sleep Talk 14회 연속 1경기), 지연 p50 0.193 대 0.194초. 뷰어 확인 통과(`exec-plans/evidence/ep230/ex168-viewer-check.json`). `runs/model-training/EX-168/report.md`.
- 2026-11-07 — laya-play v1.10.0(커밋 `731f118`, 태그 `v1.10.0`)에 `--model v10rt`를 넣었다. 서빙은 `integration.laya_ladder.serve`, 가중치는 `/workspace/exports/laya-play-v1.10.0-model-v10rt.zip`이다. 패키지 자체 점검은 v10rt·v10t 모두 24/24, 확률 차이 0이었다.

## 결과 및 증거

- [EX-166](../experiments/EX-166-laya-ladder-r1500-data.md): 30,000경기 중 선별 25,296(train 25,086), train eligible 1,580,283행. 학습에는 최신 17,510경기 1,111,776행을 썼다. 길이 초과 제외 0, parity 512/512.
- [EX-167](../experiments/EX-167-laya-v10-ladder-training.md): 잠긴 test, EX-161 대비 같은 행 차이.
  - 대회 test NLL 1.3686 → 1.3305(−0.0380 [−0.0702, −0.0059]).
  - 래더 test 1.4274 → 1.3284(−0.0990 [−0.1388, −0.0594]), 일치율 47.95 → 53.12%.
  - 대회 test 교체 행은 구별되지 않는다.
  - 테라 지식 held-out은 A 96.2 → 79.3%, B 95.8 → 86.9%로 떨어졌다.
- [EX-168](../experiments/EX-168-laya-v10t-v10rt-battle256.md): v10t 111-17, v10rt 110-18, 차이 −0.0078 [−0.0859, +0.0703] → 퇴보를 배제하지 못함.
- 결론: 래더 자료는 사람 선택 재현(특히 래더 장면)을 개선했지만 Abyssal 성적에서는 구별되지 않는다(포화). 테라 지식은 희석됐다. 판별은 사람 대전(laya-play v1.10.0 `v10rt`)이나 직접 대결로 해야 한다.
