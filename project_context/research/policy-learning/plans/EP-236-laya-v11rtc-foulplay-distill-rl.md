# EP-236 — v11rtc에 foul-play 탐색 증류 → foul-play 상대 강화학습 → foul-play·공식 래더 평가

- 상태: Paused
- 생성일: 2026-11-19
- 책임자: Claude Code
- 승인 근거·범위: 사용자 지시(2026-11-19 대화, 강화학습 논의 뒤 "1번 증류를 먼저하고 2번으로 다듬는 작업을 진행해주세요"), [D-215](../decisions/D-215-laya-foulplay-distill-then-rl.md), [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md). 구현 → EX-182(교사 라벨) → EX-183(증류 학습) ∥ EX-184(v11rtc 기준 경기) → EX-185(증류 모델 경기) → EX-186(강화학습) → EX-187(강화학습 모델 경기) → EX-188(공식 래더)을 차례로 진행한다. 외부 호출은 EX-188의 공식 Showdown 래더뿐이다.
- 관련 contract / decision / experiment: [C-047](../../../CONTRACTS.md#c-047-viewer-export), [D-191](../decisions/D-191-no-offline-battle-gate.md), [D-211](../decisions/D-211-laya-foulplay-opponent.md), [D-212](../decisions/D-212-laya-foulplay-blim-teams.md), [EX-172](../experiments/EX-172-laya-v11rtc-training.md), [EX-174](../experiments/EX-174-laya-v10rt-vs-foulplay-blim128.md), [EX-176](../experiments/EX-176-laya-v11rtc-vs-foulplay-blim128.md), [EX-177](../experiments/EX-177-laya-fp1-data.md), [EX-181](../experiments/EX-181-laya-v10rt-foulplay-search-regret.md)
- 겹치는 등록 plan:
  - [EP-234](EP-234-laya-fp1-foulplay-input.md)(Active): fp1 추적기(`integration/laya_fp1/tracker.py`)·`render_fp1.engine_choice`를 import만 한다(바꾸지 않음). EX-179는 사용자 결정 대기이며, 돌게 되면 foul-play 경기끼리 CPU가 겹치지 않게 순서를 맞춘다.
  - [EP-235](EP-235-laya-v10rt-search-regret.md)(Completed): `integration/laya_regret/search.py`를 import만 한다.
  - [EP-231](EP-231-laya-ladder-postmortem-v11.md)(Active): 공식 래더 계정을 쓰는 작업이 있으면 EX-188 전에 사용자와 맞춘다(계정 하나, 동시 한 모델).
  - [EP-229](EP-229-laya-opponent-model-search.md)(Active, 2단계 대기): 탐색으로 정책을 고친다는 개념이 겹친다. 파일·자원 충돌은 없다.
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit·미커밋 변경: `research/model-training`, `ee13b70`. EP-234·EP-235의 미커밋 기록·코드(`laya_fp1/battle_fp1.py`·`evaluation_fp1.py`, `laya_regret/`)가 있다(이 계획은 import만 함).
- 작업 checkout과 interpreter/launcher: `/workspace`. 교사·경기 재구성은 foul-play venv(`.tools/foul-play/.venv`, poke-engine 0.0.48, `PYTHONHASHSEED=0`), 학습·평가·서빙은 laya venv(EP-230·EP-231과 같음). 실행기 `scripts/laya-distill-ep236`.
- 새 산출물:
  - 코드: `integration/laya_distill/`, `scripts/laya-distill-ep236`
  - 자료: `datasets/generated/laya-distill/v1/`(교사 행·교사 validation·학습용 가중)
  - 실행 산출물: `runs/model-training/EX-182~188`, 뷰어 `exports/battle_viewers/ex184·ex185·ex187`
- 참조 원자료(읽기 전용): `v11-ladder-merged`(train·validation), 래더·대회 원 로그와 recovered 기록, EX-172 체크포인트·가중·교정 행, EX-174 collection, foul-play 봉인 자료

## 목표와 맥락

foul-play 상대 점수(D-214)를 v11rtc보다 올린다. 탐색 방문 분포를 결정마다 배우고(증류), 그 모델을 foul-play 상대 경기의 승패로 다듬는다(강화학습). 근거와 한계는 D-215에 있다.

## 범위와 불변 조건

- **포함**: `integration/laya_distill/`, `scripts/laya-distill-ep236`, 새 자료·실행 산출물, 기록.
- **보존**: 기존 패키지(`laya_imitation`·`laya_ladder`·`laya_v10`·`laya_v11`·`laya_fp1`·`laya_regret`·`foulplay`)와 자료·봉인, `.tools/foul-play/src`는 바이트 단위로 같게 둔다. 동작을 바꿀 때는 새 모듈에서 감싼다.
- **분리**: 교사 국면은 `v11-ladder-merged` train 경기에서만 고른다. 평가 Blim 64팀(EX-174 collection)은 강화학습 팀에서 뺀다(여섯 종이 같은 팀 제외).
- **자원**:
  - CPU 작업(교사 탐색, foul-play 경기)은 `scripts/mem-guard` 아래, nice 19.
  - 교사 탐색은 foul-play 경기가 돌지 않을 때만 돈다(시간 기반 탐색의 강도가 줄지 않게, EP-235와 같은 규칙).
  - 학습은 GPU 0~3, 상한 60 GB. 동시에 도는 작업의 상한 합은 100 GB 이하로 두고, 무거운 작업 전에 `free -g`를 확인한다.
- **외부 호출**: EX-188 공식 래더만. 시작 전 모델·팀·정책·서빙·시각을 기록한다.

## 완료 기준

- [x] D-215·EP-236·EX-182~188 등록, catalog build/check
- [ ] 교사·증류·강화학습·경기 연결 구현, 단위 검사
- [x] EX-182 qualification 통과, 교사 자료 생성
- [x] EX-183 학습·선택·잠긴 test 보고
- [ ] EX-184·EX-185 mock 2/2 → execute 128 → export(뷰어·보고·봉인)
- [ ] EX-186 강화학습(라운드 기록), EX-187 경기·export
- [ ] EX-188 공식 래더(후보 하나), 보고
- [ ] 결과를 EX·STATUS·catalog에 기록하고 보고
- [ ] 완료 뒤 [EP-237](EP-237-laya-observed-public-info-input.md)(예약, foul-play 경기 중 추론 전부 반영)을 시작한다

## 절차

1. 구현: 교사(`teacher.py`: 추적기 → 표본 → MCTS → 합치기 → laya 선택지 id 대응) → 자료(`data_distill.py`: 국면 선택, 교사 행, 가중) → 학습 래퍼(`train_distill.py`: `train_v11` 경로) → 경기(`battle_distill.py`: EP-232 실행기에 EX-184·185·187 study) → 강화학습(`rl.py`).
2. `scripts/laya-distill-ep236 teacher` → `train` ∥ `battle EX-184` → `battle EX-185` → `rl` → `battle EX-187` → `ladder`.
3. 각 단계는 산출물이 있으면 건너뛰고, 실패하면 멈춘다. 자동 재실행은 없다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 각 EX의 중단 조건에서 멈추고 보고한다.

## 진행

- 2026-11-19 — 사용자 지시로 등록했다.
- 2026-11-19 — 구현(`integration/laya_distill/`: `paths.py`, `data_distill.py`(선택·교사·자료), `train_distill.py`(`train_v11` 인자 고정, EX-183 등록), `evaluation_distill.py`, `battle_distill.py`(EX-184·185·187 study), `tests/test_distill.py` 3개 통과, `scripts/laya-distill-ep236`). 강화학습(`rl.py`)은 EX-185 뒤에 구현한다.
  - 교사 국면 선택(16:55 KST): train 1,800경기 53,508국면, validation 80경기 2,364국면(`EX-182/selection.json`).
  - 1경기 시험(반복 2만): 탐색 선택지가 모두 laya id에 대응했다(버린 몫 0). 교체는 `switch <name>`, 기술은 정규화 id.
  - 서빙 모델 이름은 EX-184·185·187 모두 `laya-v11rtc`(`serve_v11.MODELS`를 읽는 작업 프로세스는 이 모듈을 import하지 않음)이고, 체크포인트 해시로 구별한다.
- 2026-11-19 16:56 KST(07:56Z) — EX-182 qualification 시작(50경기 1,482국면, 국면마다 탐색 2회, 작업자 96, nice 19, mem-guard 40). foul-play 경기는 돌지 않는다.
- 2026-11-19 17:26 KST — qualification 1차 미달: 대응 없는 탐색 몫이 0.1을 넘는 결정 1.55%(기준 1%). 나머지는 통과(대응 없는 몫 평균 0.0089, 반복 1순위 일치 81.5%, 표본당 3.93초, 사람 선택 일치 44.3%). 원인은 기술 고정 국면(구애 도구 등) 23결정이다. fp1 추적기가 만드는 request에 고정 표시가 없어 탐색이 쓸 수 없는 기술을 고른다. 수정: `data_distill.restrict`가 탐색 전에 laya 선택지(실제 request의 합법 수)에 없는 기술을 사용 불가로, `:tera` 선택지가 없으면 테라 불가로, 교체 선택지가 없으면 교체 불가로 둔다(추적기는 그대로). 해당 4결정 재시험에서 대응 없는 몫 0. 1차 기록은 `EX-182/qualification-attempt1-unrestricted/`에 두고 qualification을 다시 돌린다(D-029 공통 복구: 도구 결함, 분모 밖 사전 검사).
- 2026-11-19 17:5x KST — qualification 2차 통과(대응 없는 몫 평균 0.0·행 비율 0.0, 반복 1순위 일치 82.0%, 표본당 3.91초, 사람 선택 일치 43.7%). 같은 실행에서 label 시작(1,880경기).
- 2026-11-20 00:52 KST(15:52:03Z) — label 1,731/1,880경기(약 51.5k국면)에서 mem-guard 40 GB 한도로 중단(작업자 97개, 7시간 동안 36→40 GB로 서서히 증가, 오류 0). 마지막 행이 온전하고 `staged()`가 sample_id로 중복을 없애므로, 끝난 경기를 건너뛰고 남은 149경기만 다시 돌린다(같은 한도).
- 2026-11-20 08:50 KST(11-19 23:50Z) — 재개분이 148/149경기를 01:28 KST(16:28Z)에 끝낸 뒤 풀이 멈췄다(작업자 전부 대기, CPU 0, 1경기 `gen9ou-2669985156` 미완). 작업 하나가 풀에서 사라진 것으로 본다. 중지하고(작업자 34 GB 반환) 그 1경기만 다시 돌린다.

- 2026-11-20 09:20 KST(00:20Z) — 남은 1경기 `gen9ou-2669985156`이 단독 실행에서도 poke-engine segfault로 죽음을 확인했다(두 번의 풀 정지 원인: 죽은 작업자의 작업이 사라져 `imap_unordered`가 영원히 기다림). `paths.EXCLUDED_GAMES`로 빼고 build 완료(교사 train 53,462·validation 2,364행, 버린 행 16). 09:23 KST에 EX-183 학습(GPU 0~3)과 EX-184 경기(CPU)를 시작했다.

- 2026-11-20 10:20 KST(01:20Z) — EX-183 사전 측정: 학습 행 480,876, 예상 3.0시간, GPU 최대 22.1 GiB, 재로딩 logit 차 0. 60 update 손실은 앞 절반 1.338 → 뒤 절반 1.395로 줄지 않았다(qualification 문구 미충족). 이어 학습하는 같은 경로의 EX-171(1.388 → 1.469)·EX-172(1.258 → 1.397)도 같은 모양이었고 그대로 진행했다. 60 update는 섞인 행의 잡음이 커서 이 항목이 이어 학습에서 판별력이 없다고 보고 학습을 계속한다(4지점 validation으로 판단). 학습은 00:34Z 시작, 15,028 step, 지점 0(EX-172) 교사 validation CE 1.993·1순위 일치 0.462.

- 2026-11-20 12:55 KST(03:55Z) — EX-183 완료(선택 지점 4; 교사 CE −0.091 [−0.099, −0.082], 1순위 +0.016 [+0.006, +0.027], 잠긴 test NLL 대회 +0.006·래더 +0.009 구별 안 됨). EX-184 execute 완료(45/0/82, 0.354 [0.273, 0.441], 1 미완료; v10rt 같은 슬롯 +0.024 [−0.055, +0.102]), export 진행 중. export 뒤 EX-185를 이어 시작한다.

- 2026-11-20 13:56 KST(04:56Z) — 사용자 지시("오늘 오후 11시까지 레더 대전을 진행하고 싶은데 추후 강화학습에 문제가 없도록 해줘")로 [EX-189](../experiments/EX-189-laya-v11d-ladder-interim.md)(v11d 공식 래더 중간 대전, 보고 전용)를 등록하고 시작했다. GPU 3 서빙(CPU는 EX-185에 남김), 팀 `t9ff547d715`, 23:00 KST까지, `scripts/laya-ladder-ex189`. laya-play에 `laya-v11d` 이름을 더했다(`app/integration/laya_v11/serve.py`, `app/laya_play/bot.py`). 첫 시작은 `official.sh`가 `--serving`이 아닌 `runtime/serving.ready.json`(멈춘 v10rt 서비스)로 /health를 확인해 2회 실패했다(경기 없음). 실행기가 루프 동안 그 파일을 v11d 서빙으로 바꾸고 끝나면 되돌리게 고쳐 다시 시작했다. 강화학습과의 관계: 래더는 학습 자료를 만들지 않고, EX-186 수집(로컬 포트 8100~8103)과 포트·계정이 겹치지 않으며, 갱신은 GPU 3을 서빙과 나눠 쓴다(GPU당 48 GB).

- 2026-11-20 15:29 KST — 사용자 지시("시간을 아끼기 위해 EX185는 조기 종료를 해주세요. 강화학습 계획도 일단 보류 하겠습니다. 대신에 아까 예약해둔 EP-237을 시작하기 위한 점검을 하고 싶습니다")로 EX-185를 91/128에서 중지(v11d 22/0/67, 같은 슬롯 − v11rtc −0.080 [−0.186, +0.024], 판정 보류)하고 EX-186~188을 보류(Paused)했다. 이 계획은 Paused다. EP-237은 시작 전 점검(토큰 한도·반영 가능성)부터 한다.

## 결과 및 증거

아직 없다.
