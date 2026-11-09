# EP-228 — laya 교체 읽기 상대(정직함 측정)와 v8lt 교체 갈림길 섞기 배틀(재학습 없음, GPU1~3)

- 상태: Completed
- 생성일: 2026-11-03
- 책임자: Claude Code
- 승인 근거·범위: 사용자 지시(2026-11-03 대화). 원문은 "A, B를 등록하고 진행해주세요. 직접 보는 방식은 실제 사람과는 거리가 있으므로 제외해주세요."이고, 설계는 [D-205](../decisions/D-205-laya-switch-read-and-mixing.md)에 있다. 구현, mock, 배틀 3갈래, 기록까지 이어서 진행한다. 오프라인 결과로 배틀을 거르지 않는다([D-191](../decisions/D-191-no-offline-battle-gate.md)).
- 관련 contract / decision / experiment: [C-047](../../../CONTRACTS.md#c-047-viewer-export), [D-205](../decisions/D-205-laya-switch-read-and-mixing.md), [EX-163](../experiments/EX-163-laya-v8lt-vs-switch-reader.md), [EX-164](../experiments/EX-164-laya-v8lt-switch-mixing.md), [EX-155](../experiments/EX-155-laya-v8l-likely-fails-training.md), [EX-156](../experiments/EX-156-laya-v8t-v8lt-battle256.md)
- 기준 연구선: `research/model-training`
- 작업 checkout과 interpreter/launcher: `/workspace`(미커밋 새 파일). 단계 실행은 laya venv(`.tools/laya-0.4.13/worktrees/pokemon-training/.venv`), 워커는 `pokechamp/.venv`, Showdown은 node다.
- 새 산출물: `runs/model-training/EX-163`, `runs/model-training/EX-164/{abyssal,reader}`, 뷰어 `/workspace/exports/battle_viewers/{ex163,ex164-abyssal,ex164-reader}/`, 증거 `project_context/exec-plans/evidence/ep228/`
- 참조 원자료(읽기 전용): EX-155 체크포인트, EX-156 실행(기준), EX-120 일정 묶음, `dex_gen9.json`, `usage_sets_v3.json`, poke_env `gen9pokedex.json`

## 목표와 맥락

사람 플레이어가 말하는 "정직함"(위협받으면 늘 받아낼 포켓몬으로 교체해서 읽힌다)을 교체 읽기 상대로 측정한다. 교체 갈림길에서만 남기를 섞는 서빙 규칙이 이를 줄이는지도 본다(D-205).

## 범위와 불변 조건

- **포함**: `integration/laya_mindgame/`(`estimate`, `mix`, `reader`, `serve`, `battle`, `tests/test_mindgame.py`), `scripts/laya-mindgame-ep228`, 뷰어 변경일지 항목, 기록
- **보존**:
  - 아래 파일은 바이트 단위로 같아야 한다. EP-227 v10 레인(EX-162)의 동결 대상이다.
    - `integration/laya_imitation`, `integration/laya_v10`
    - `integration/pokechamp/imitation`
    - `scripts/laya-imitation`, `scripts/laya-imitation-ep227`
  - 기존 자료·산출물·봉인도 그대로 둔다.
- **자원**: GPU1·8109(EX-163), GPU2·8108(EX-164 abyssal), GPU3·8106(EX-164 reader)을 쓴다. 시작할 때 비어 있음을 확인한다. GPU0·8107은 EP-227 것이라 쓰지 않는다. 외부 프로세스 종료와 장치 reset은 금지한다.
- **배틀 표시**: prepare 직전에 `.pokechamp-data/battle-window/EX-163`·`EX-164-abyssal`·`EX-164-reader`를 두고, export 뒤 지운다.
- **외부 호출**: 없다.

## 완료 기준

- [x] D-205, EP-228, EX-163, EX-164 등록, catalog build/check
- [x] `laya_mindgame` 구현과 단위 검사 8개 통과(두 인터프리터), ruff(E9·F63·F7·F82·F401·F811) 통과
- [x] 오프라인 확인(EX-156 v8lt 4,906결정): 섞기 규칙 작동 145결정(3.0%), 바뀌는 결정 67, 작동 경기 74/128. 보고 전용이다.
- [x] 갈래별 mock 2경기 정상 → prepare → execute
- [x] export(EX-164 reader 갈래는 EX-163 execute 뒤), 뷰어 확인(3개, 1440·390폭, 페이지 오류 0), 봉인
- [x] 결과를 EX 문서, STATUS, catalog에 기록

## 절차

1. 구현과 단위 검사
2. 기록 등록
3. 세 레인 시작: `scripts/laya-mindgame-ep228 ex163|ex164a|ex164r`, 로그 `runs/model-training/EP-228-<lane>.log`
4. 결과 기록

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 자동 재실행은 없다. mock이 실패하면 그 레인은 prepare 전에 멈춘다. 단계가 실패하면 그 레인만 멈춘다. 레인 실행 중에는 `integration/laya_mindgame`을 고치지 않는다.

## 진행

- 2026-11-03 — 사용자와 설계했다. 문제(정직함)의 원인을 argmax 서빙과 경기 중 적응 부재로 나눴다. 모든 결정에 샘플링하는 안은 사용자 지적으로 버렸다. 측정(A)과 교체 갈림길 섞기(B)를 먼저 하기로 했고, 읽기 상대가 모델 정책을 직접 보는 방식은 사용자가 제외했다.
- 2026-11-03 — 구현을 마쳤다. 배틀 클라이언트(`pokechamp/imitation/player.validate_response`)가 응답 확률의 argmax만 받으므로, 섞기가 작동한 결정은 추첨된 행동을 1로 두어 응답한다. 추첨 전 비율과 정책 출력은 응답의 `mix_rule`·`model_probabilities`에 남긴다. bootstrap 시드는 EX-161·EX-162와 겹치지 않게 20261065~67로 정했다.

- 2026-11-03 06:37Z — 레인 ex163·ex164a를 시작했다. ex163 mock이 실패했다(`AttributeError: 'Battle' object has no attribute 'teampreview_opponent_team'`).
  - 원인: 이 poke_env 판본에는 팀 미리보기의 공개 속성이 없고 `_teampreview_opponent_team`만 있다.
  - 조치: `reader.bench`를 고치고 회귀 검사를 더했다. 실패한 mock은 `EX-163/diagnostics/mock-v1-failed/`(결함 기록 포함)로 옮기고, ex163을 mock부터 다시 시작했다. prepare 전이라 동결된 것은 없었다.
  - ex164a의 mock 2경기는 정상이었다.
- 2026-11-03 06:40Z — EX-163 mock 읽기 기록에서 두 번째 결함을 찾았다.
  - 원인: 팀 미리보기로만 아는 포켓몬은 poke_env에서 `max_hp` 0이라 HP가 0%로 잡혔다. 그 결과 추정 피해가 모두 0으로 잘렸고, 예측 교체 대상이 이름순으로 정해졌다.
  - 영향: 처치(읽기 상대) 자체에 영향을 주는 결함이다.
  - 조치: 06:41Z에 세 레인을 모두 멈췄다(이 레인의 프로세스만 종료). EX-163 execute는 1슬롯 진행 중이었고 끝난 경기는 없었다. EX-164 abyssal은 2경기를 끝냈고, EX-164 reader는 mock 중이었다. 실행 폴더는 그대로 `EX-163/diagnostics/run-v2-stopped`, `EX-164/diagnostics/{abyssal-run-v1-stopped,reader-mock-v1-stopped}`로 옮겼고 결함 기록을 함께 두었다. 이 경기들은 어느 분모에도 넣지 않는다.
  - 수정: `max_hp` 0이면 HP를 100%로 본다. 회귀 검사를 더해 검사 9개가 통과했다.
  - 재시작: 동결 해시와 코드가 모든 갈래에서 같도록 세 레인을 06:42Z에 mock부터 다시 시작했다.
- 2026-11-03 06:42Z — ex164r mock이 `git worktree add`(exit 128)에서 실패했다.
  - 원인: 멈춘 경기의 pokemon-showdown worktree 등록이 남아 있었다(폴더는 diagnostics로 옮김).
  - 조치: `git -C /workspace/pokemon-showdown worktree prune`으로 정리 대상 3개를 지웠다. 모두 EP-228이 멈춘 경기이고 다른 등록은 그대로다. mock은 `EX-164/diagnostics/reader-mock-v2-failed`로 옮기고 ex164r을 다시 시작했다.
- 2026-11-03 07:58Z — **실행 중 핫픽스(사용자 승인 이탈)**.
  - 결함: poke_env는 Tera Stellar 포켓몬의 타입을 `STELLAR`로 준다. `estimate.effectiveness`에 이 타입이 없어서, 모델 포켓몬이 Stellar로 테라스탈하면 읽기 상대가 KeyError로 멈춘다(단계 중단). 그러면 남은 25경기를 두지 못하고 판정 보류가 된다.
  - 발견 경위와 시점: 학습 자료 행 수 세기 중에 발견했다. 남은 위험 슬롯은 읽기 갈래마다 `m10-s1-a`(Enamorus Tera Stellar) 하나였고, 아직 시작 전이었다.
  - 사용자 결정: 16:58 KST에 "지금 핫픽스"를 골랐다.
  - 수정 내용:
    - `reader._types`: stellar는 그 종의 원래 타입으로 본다.
    - `estimate.effectiveness`: 모르는 타입은 등배로 본다.
    - 회귀 검사를 더해 검사 10개가 통과했다.
  - 동결과의 차이: prepare 때 동결한 `estimate.py`·`reader.py` 해시와 지금 코드가 다르다. 전후 해시와 수정 시점의 경기 수는 세 실행 폴더의 `diagnostics/hotfix-stellar.json`에 있다.
  - 영향: 현재 타입에 stellar가 없는 경기는 바이트 단위로 같게 동작한다. 모델 쪽 스냅샷은 stellar를 타입에 넣지 않으므로(`replay.py`) 섞기 규칙은 영향이 없다.

## 결과 및 증거

- 2026-11-03 08:28Z에 세 레인을 모두 마쳤다(06:45Z 시작, GPU1~3과 포트 반환, battle-window 표시 제거).
- [EX-163](../experiments/EX-163-laya-v8lt-vs-switch-reader.md): 구별되지 않음(−0.016 [−0.063, +0.023]). 읽기 적중률 16.9%.
- [EX-164](../experiments/EX-164-laya-v8lt-switch-mixing.md):
  - abyssal 갈래: 퇴보를 배제하지 못함(−0.047 [−0.102, +0.008]).
  - reader 갈래: 구별되지 않음(−0.031 [−0.094, +0.031]). 적중률 차이 −0.010 [−0.033, +0.012].
- 증거: 실행 폴더의 `report.md`·`comparison.json`·`checksums.sha256`, 결함·핫픽스 기록 `diagnostics/`, 뷰어 확인 `exec-plans/evidence/ep228/`
- 후속: [EP-229](EP-229-laya-opponent-model-search.md)(상대 모델 + 한 턴 탐색)
