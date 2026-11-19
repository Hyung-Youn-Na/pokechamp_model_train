# EP-231 — laya v10rt 공식 래더 패배 원인 추가 분석과 재학습 v11(v11rt·v11rtc)

- 상태: Active
- 생성일: 2026-11-16
- 책임자: Claude Code
- 승인 근거·범위: 사용자 결정(2026-11-16 대화, 승인된 계획)과 [D-209](../decisions/D-209-laya-ladder-postmortem-v11.md). 추가 원인 분석 → 설계 확정 → 자료 재생성 → GPU 학습 → 오프라인 평가까지 중간 확인 없이 진행한다. 공식 래더 비교는 따로 지시받는다. 오프라인 결과로 래더 비교를 거르지 않는다([D-191](../decisions/D-191-no-offline-battle-gate.md)).
- 관련 contract / decision / experiment: [C-055](../../../CONTRACTS.md#c-055-imitation), [D-208](../decisions/D-208-laya-ladder-r1500-v10.md), [D-204](../decisions/D-204-laya-renderer-v10-all-info.md), [EX-169](../experiments/EX-169-laya-v10rt-ladder-loss-analysis.md), [EX-170](../experiments/EX-170-laya-v11-data.md), [EX-171](../experiments/EX-171-laya-v11rt-training.md), [EX-172](../experiments/EX-172-laya-v11rtc-training.md), [EX-167](../experiments/EX-167-laya-v10-ladder-training.md)
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit·미커밋 변경: `research/model-training`, `a4e5964`, 시작 시 추적 파일 변경 없음(미추적 `data/`만 있음)
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv(`pokemon-v10` worktree 우선, EP-227과 같음), `pokechamp/.venv`, Metamon CPU venv, node. laya-play 작업 트리 `/workspace/exports/laya-play`(브랜치 `local`, `dd9190a` 위 미커밋 변경)
- 새 산출물:
  - 실행: `runs/model-training/EX-169`·`EX-170`·`EX-171`·`EX-172`, 메모리 기록 `runs/model-training/EX-17x-memory.log`
  - 자료: `datasets/generated/laya-engine-judge/v2`, `laya-ladder-engine-judge/v2`, `laya-compact-imitation/v11-all`·`v11-ladder`·`v11-ladder-merged`, 가중·교정 행(이름은 EX-170에서 확정)
- 참조 원자료(읽기 전용): laya-play 래더 판 기록(`/workspace/exports/laya-play/games/`), `v10-ladder-merged`·`v10-all`·`v10-ladder`, EX-071·EX-166 저장소(item-state, v5 사실값, early-history), 래더 원본 로그(`/workspace/data/showdown-replays/ladder-recent/`)와 목록(`ladder-index/`), 테라 지식 train, EX-167 체크포인트와 평가 행

## 목표와 맥락

v10rt의 공식 래더 패배 원인을 판 단위와 정책 단위로 더 가르고, 그 결과로 재학습 모델 두 개(`v11rt`, `v11rtc`)를 만들어 오프라인 평가까지 마친다(D-209). 1차 분석은 `/workspace/exports/laya-play/docs/analysis/2026-11-16-ladder-analysis.md`다.

## 범위와 불변 조건

- **포함**: `integration/laya_v11/`(분석, 렌더 덧씌우기, 판정 저장소·행 생성, 가중·교정 행, 학습 실행기, 평가, 단위 검사), `scripts/laya-v11-ep231`, 기록. laya-play 작업 트리에는 `--guard`와 새 모델 등록만 더한다(미커밋).
- **보존**: `laya_v10`·`laya_ladder`·`laya_engine`·`laya_imitation`·`laya_threat`·`pokechamp/imitation` 파일과 기존 자료·산출물·봉인은 바이트 단위로 같다. laya-play는 커밋·푸시·배포하지 않는다.
- **자원**: GPU 2·3번(시작 시 비어 있음과 battle-window 표시 없음을 확인). GPU 0·1은 다른 컨테이너가 쓴다. 외부 프로세스 종료와 장치 reset은 금지한다.
- **메모리**: 무거운 단계는 모두 `scripts/mem-guard 100` 아래에서 돈다. 동시 학습 여부는 D-209 결정 6의 규칙으로 정한다.
- **외부 호출**: 없다. 공식 서버 접속은 래더 비교 지시 뒤에만 한다.

## 완료 기준

- [x] D-209, EP-231, EX-169~172 등록, catalog build/check
- [x] 래더 판 기록 보존(`runs/model-training/EX-169/source/`)
- [x] EX-169: A1~A6 실행과 보고, D-209 규칙 적용 결과 기록(D-210)
- [x] `laya_v11` 구현과 단위 검사(`duel` 회복, 수정 판정기, 형태 이름, 가중 평균 1, 교정 행 목표 합 1)
- [x] EX-170: 판정 저장소 재생성 → v11 행 → 합치기 → parity → 바뀐 행 집계 → 가중·제외·교정 행
- [x] EX-171·EX-172: 사전 측정 → 학습 → 선택 → 평가·봉인
- [ ] laya-play 작업 트리에 `--model v11rt`·`v11rtc`, `--guard` 추가와 자체 점검
- [ ] 결과를 EX 문서, STATUS, catalog에 기록

## 절차

1. 등록하고 래더 판 기록을 보존한다.
2. EX-169 분석을 구현하고 실행한다.
3. D-209 규칙을 적용해 `v11rtc`의 수단을 정하고 EX-170 조건에 적는다. 사용자에게 보고하되 기다리지 않는다.
4. 교정 행용 로컬 대전과 EX-170 자료를 만든다.
5. EX-171·EX-172를 학습하고 평가한다.
6. laya-play 서빙을 준비하고 기록한다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 자동 재실행은 없다. 각 EX의 중단 조건에서 멈춘다. parity 불일치, 보존 해시 변경, loss NaN, GPU 오류, mem-guard 종료(137)는 멈추고 보고한다.

## 진행

- 2026-11-16 — 사용자와 범위·수단·모델 수·래더 규모·메모리 상한을 정했다(D-209). 등록했다. 시작 시 GPU 2·3은 비어 있고 GPU 0·1은 다른 컨테이너가 쓰고 있다. 호스트 메모리는 125 GB 중 여유 84 GB였다(16:54 KST).

- 2026-11-16 — 여기까지 진행하고 세션 사용 한도로 멈췄다(18:21 KST). 이어서 할 때 이 항목부터 본다.
  - **끝난 것**
    - 판 기록 보존: `runs/model-training/EX-169/source/`. 로컬에 기록이 있는 판은 73판(완료 70판 40승 30패, 미리보기 기권 3판)이다. 11-15의 10판은 다른 머신에서 둬 결과(`replays.csv`)만 있다.
    - 봇 결정 2,426개를 당시 서빙 설정으로 다시 렌더했다(`tables/decisions.jsonl`). v10rt로 다시 채점한 확률이 기록과 2,383개 모두 일치한다(최대 차이 6e-6, `tables/verify.json`).
    - A1 `tables/a1-tags-win-loss.json`, A2 `tables/a2-three-way.json`, A4 `tables/a4-dead-hindsight.json`·`a4-rating-strata.json`, A5 `tables/a5-rules.json`, 가중 모의 `tables/a2-weight-simulation.json`, A6 `scenes/scenes.jsonl`(926장면).
    - 코드: `integration/laya_v11/`(`analysis/`, `render_v11.py`, `data_v11.py`, `policy.py`, `localplay.py`, `localplay_challenger.py`), `scripts/laya-v11-ep231`. 로컬 봇 대 봇은 1판 시험이 정상 종료했다.
  - **분석에서 나온 것**(EX-169 결과 절에는 아직 옮기지 않았다)
    - v10rt의 확률 분포는 학습에 쓰지 않은 사람 국면에서 사람 선택 비율과 맞는다(교체 0.254 대 0.245). argmax로 고르면 교체가 0.172로 줄고 정체 streak 반복은 0.693(사람 0.556)으로 는다. 봇 자기 국면에서는 교체 0.082, 실패 뒤 같은 기술 반복 0.630(사람 0.358)이다. H1이 지지된다.
    - 실패 표시 선택은 3판에 몰려 있고(27·11·2건) 승패와 연결되지 않는다. 진 판에서 더 많은 것은 `duel lose` 잔류다(100결정당 +6.1 [+1.5, +10.9]).
    - 진 30판 중 8판은 능력치를 쌓은 상대에게 2마리 이상 잃었다. laboratoryworker는 같은 첫 수순으로 Dragapult를 2~3턴에 4판 연속 잡았다.
    - 레이팅 구간별로 문제 행동률이 줄지 않는다 → 상위 레이팅 가중은 채택하지 않는다. Toxic Spikes 2층 사람 선택률은 10.5% → 판정은 그대로 둔다.
    - 라벨 정제 대상은 합친 train의 약 0.5%(v10 표시 기준 6,160행)다.
    - D-209의 가중 ×4는 과하다(`duel lose` 교체 argmax 0.578, 사람 0.358). 사람 비율에 맞는 값은 정체 탈출 1.9, `duel lose` 교체 1.4, 상대 +2 교체 2.2다. `policy.py`에 이 값을 넣었고, **D-210으로 등록해야 한다(미등록)**.
    - 결정 규칙 모의: 확정 실패·직전 실패 제외는 봇 결정 70개를 바꾸고 실패 선택 49 → 8. "교체 확률 합이 최고 기술보다 크면 교체"는 사람 국면 교체율을 0.257로 되돌린다(일치율 −1.0%p). 뒤 규칙은 D-209에 없으므로 래더 비교군으로 넣을지 사용자에게 묻는다.
  - **돌고 있는 것**(끝나면 스스로 종료): A3 채점(`tables/a3-counterfactual.jsonl`, GPU3), 대회 자료 판정 저장소 `laya-engine-judge/v2`.
  - **남은 것**: A3 표와 EX-169 결과·보고 작성 → D-210 등록 → 로컬 대전 512판(`localplay`, GPU 2·3) → 래더 판정 저장소와 v11 행(`data_v11 judge ladder`, `rows tour|ladder`, `merge`, `diff`) → `policy weights`·`corrections` → 학습 실행기(미작성)와 메모리 사전 측정 → EX-171·172 학습·평가 → laya-play `--guard`·모델 등록. 단위 검사(`tests/`)도 아직 없다.
  - 알아 둘 점: v11 `duel`은 16:05 판 3턴부터 `lose`지만 2턴은 `win`(9 대 9+)으로 남는다. EX-170 qualification에 적은 "2~3턴"과 다르므로 결과에 그대로 적는다. 호스트 메모리 여유가 84~87 GB라 학습은 순차(모델당 GPU 2장)가 될 가능성이 높다.

- 2026-11-16 — 21:51 KST에 이어서 진행했다.
  - EX-169 완료(보고 `runs/model-training/EX-169/report.md`). A3: 가장 유력한 기술에 `fails`를 붙이면 확률 0.489 → 0.144, `duel` 승패를 뒤집으면 교체 확률 합 1.5%p 변화. D-210 등록(가중 배수 1.9 / 1.4 / 2.2, 테라 지식·상위 레이팅 가중 미채택).
  - 구현: `render_v11.py`(판정기 수정, 형태 이름, 회복 반영 `duel`, 특성 표기), `data_v11.py`, `policy.py`, `train_v11.py`, `evaluation_v11.py`, `tests/test_v11.py`(9개 통과). 대회 자료 판정 저장소 `laya-engine-judge/v2` 완료(145초).
  - **메모리**: 22:05 KST에 호스트 여유가 12 GB까지 내려갔다. 래더 판정(64 작업 프로세스, 30 GB), 로컬 대전(서빙 6개·봇 24개, 34 GB), 대회 자료 행 생성(13 GB)을 동시에 돌렸고 다른 컨테이너가 약 30 GB를 쓰고 있었다. 작업별 상한(60 + 40 + 25 GB)의 합이 호스트 여유보다 컸다. 종료된 프로세스나 OOM은 없다. 로컬 대전을 정상 종료해 여유 47 GB로 되돌렸다. 이후로는 동시에 도는 작업의 상한 합을 80 GB 이하로 두고, 무거운 작업을 시작하기 전에 `free -g`를 확인한다.
  - 로컬 대전은 두 번 멈췄다(서빙 수를 늘리려 1회, 위 메모리 문제로 1회). 끝난 판의 기록은 `runs/model-training/EX-170/localplay/games/`에 남아 있고 이어서 채운다.

- 2026-11-17 — 02:51 KST에 이어서 진행했다(세션 사용 한도로 약 4.5시간 멈춤).
  - EX-170 자료 완료(00:06 KST): 래더 판정 저장소, `v11-all`·`v11-ladder`·`v11-ladder-merged`, 서빙 일치 512/512(두 원천), v10 대비 차이 집계, 제외·가중. 자료 단계 실행기는 일을 마친 뒤 "syntax error"로 끝났다. 실행 중에 `scripts/laya-v11-ep231`을 고친 탓이고 산출물에는 영향이 없다. 스크립트를 함수 하나로 감싸 실행 중 수정에 안전하게 바꿨다.
  - 로컬 대전: GPU 서빙 구성이 23:15 KST에 메모리 상한 40 GB에 걸려 종료됐다(166판 완료). 남은 판은 CPU 서빙으로 돌린다. 03:00 KST에 시작한 CPU 구성은 서빙이 프로세스당 코어 약 30개를 써서 부하가 230까지 올랐고 진행이 없었다. 03:12 KST에 서빙당 8스레드로 제한해 다시 시작했다.
  - EX-171 학습을 03:00 KST에 시작했다(GPU 2·3 순차, 사전 측정 13.4시간 예상). 순차로 정한 이유는 EX-171 실행 절에 있다. EX-172는 EX-171 채점·보고 뒤 자동으로 이어진다(`scripts/laya-v11-ep231 train-b`가 대기 중).
  - laya-play 작업 트리(미커밋): `app/integration/laya_v11/{guard.py,serve.py}`, `bot.py`의 `--guard`, `ladder_replays.py`의 정책 표기, `tests/test_guard.py`(관련 테스트 15개 통과). 새 서빙의 실제 응답 대조는 CPU가 붐벼 끝내지 못했다. 학습 뒤 다시 한다.

- 2026-11-17~18 — 교정 행 생성이 10:41 KST에 작업 프로세스 32개로 상한 25 GB를 넘겨 종료됐다. 15:03에 8개·35 GB로 재실행해 1,203행을 만들었다. EX-171 완료(18:24 KST), EX-172 완료(11-18 09:14 KST).
- 남은 것: laya-play에 `v11rt`·`v11rtc` 가중치 등록과 자체 점검, 새 서빙(guard) 실제 응답 대조, 공식 래더 비교(지시 대기).

## 결과 및 증거

- [EX-169](../experiments/EX-169-laya-v10rt-ladder-loss-analysis.md): 패배 원인 분석, D-210.
- [EX-171](../experiments/EX-171-laya-v11rt-training.md): 입력 수정만으로는 test·행동 지표 모두 v10rt와 구별되지 않는다.
- [EX-172](../experiments/EX-172-laya-v11rtc-training.md): 행동 지표는 사람 비율 쪽으로 움직였고(교체 증가, 반복·실패 선택 감소) test NLL은 약간 나빠지는 쪽이다(구별되지 않음).

- 2026-11-18 — 사용자 지시로 공식 래더 비교를 시작했다(09:34 KST~18:00 KST). 계정 하나(nhy_test1629)로 v11rt·v11rtc를 한 판씩 번갈아 두고(동시 검색 불가), 팀 `t95bfb45561`(v10rt 11-17 래더와 같음), argmax(guard 끔). 서빙은 laya-play `integration.laya_v11.serve`(usage extension 켬), v11rt GPU 2·v11rtc GPU 3, 체크포인트는 EX-171·EX-172 `checkpoints/selected`를 직접 쓴다(laya-play `models/` 등록은 아직 안 함). 루프 로그 `exports/laya-play/runtime/logs/ladder-loop-20261118.log`.
  - laya-play 작업 트리(미커밋): `bot.py`가 판마다 `render`(서빙 렌더러 판본 라벨, `v11_render` 우선)를 기록하고, `ladder_replays.py`가 `replays.md`·`.csv`에 모델·렌더러 열과 모델·렌더러별 전적을 적는다. 2026-11-17까지 222판은 모두 v10rt·v10으로 채웠다. 첫 두 판(223·224)은 라벨 함수가 ready 파일의 `render`(자료 manifest 값, v10)를 읽어 `v10+usage`로 잘못 적혔고, `v11_render`를 먼저 보도록 고친 뒤 `index.jsonl`·`result.json`의 값을 `v11+usage`로 바로잡았다. 서빙 자체는 v11 입력이었다(서빙 로그 `v11 input`, 판정 `v2-protect`).
  - 2026-11-18 14:22 KST — 사용자 지시로 교대를 멈추고 v11rtc만 둔다(종료 18:00 KST 유지). 교대 시점 v11rt 28판 13승 15패(레이팅 합 −40), v11rtc 27판 16승 11패(+141). v11rt 서빙(GPU 2)은 내렸고, v11rtc 서빙(GPU 3)과 진행 중이던 56번째 판(v11rtc)은 그대로 이었다. 새 루프는 같은 로그에 이어 적는다.
