# EP-234 — laya fp1 렌더러(foul-play 기반 입력) 자료·처음부터 전체 학습·foul-play 배틀

- 상태: Active
- 생성일: 2026-11-18
- 책임자: Claude Code
- 승인 근거·범위: 사용자 지시(2026-11-18 대화, 초안 확인 뒤 "이대로 등록하고 구현 시작"), [D-213](../decisions/D-213-laya-fp1-foulplay-input.md). 구현 → 자료(EX-177) → 학습(EX-178) → 배틀(EX-179)을 중간 확인 없이 진행한다. 외부 호출은 없다(D-211 봉인 자료만 쓴다).
- 관련 contract / decision / experiment: [C-047](../../../CONTRACTS.md#c-047-viewer-export), [D-211](../decisions/D-211-laya-foulplay-opponent.md), [D-191](../decisions/D-191-no-offline-battle-gate.md), [EX-167](../experiments/EX-167-laya-v10-ladder-training.md), [EX-170](../experiments/EX-170-laya-v11-data.md), [EX-174](../experiments/EX-174-laya-v10rt-vs-foulplay-blim128.md)
- 겹치는 등록 plan:
  - [EP-231](EP-231-laya-ladder-postmortem-v11.md)(Active): 래더 비교가 GPU 2·3에서 2026-11-18 18:00 KST까지 돈다. 학습은 그 뒤에 시작하고, 자료 단계는 CPU로 병행한다. EP-231 프로세스는 건드리지 않는다.
  - [EP-229](EP-229-laya-opponent-model-search.md)(Active, 2단계 대기): 상대 모델 범위가 개념상 겹치지만 파일·자원 충돌은 없다.
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit·미커밋 변경: `research/model-training`, `a4e5964`. EP-231·EP-233의 미커밋 기록·catalog 변경이 있다(건드리지 않음).
- 작업 checkout과 interpreter/launcher: `/workspace`.
  - 추적·표본·엔진 단계는 foul-play venv(`/workspace/.tools/foul-play/.venv`, python 3.11, poke-engine 0.0.48)에서 돈다. 별도 프로세스이고 JSONL로 통신한다.
  - 학습·평가는 laya venv(EP-230과 같음)에서 돈다.
- 새 산출물:
  - 코드: `integration/laya_fp1/`, `scripts/laya-fp1-ep234`
  - 자료: `datasets/generated/laya-compact-imitation/fp1-ladder-merged`, `fp1-test`
  - 실행 산출물: `runs/model-training/EX-177~179`, 뷰어 `exports/battle_viewers/ex179/`
- 참조 원자료(읽기 전용): 래더·대회 원 로그, `v11-ladder-merged`·잠긴 test의 행 목록·라벨·선택지, EX-174 collection, foul-play 봉인 자료(`.tools/foul-play/data-SHA256SUMS`)

## 목표와 맥락

laya 입력을 foul-play 추적·표본과 poke-engine 계산으로 전부 바꾸고 처음부터 학습한다. 그다음 foul-play 상대 성적이 v10rt와 얼마나 다른지 본다(D-213).

## 범위와 불변 조건

- **포함**: `integration/laya_fp1/`, `scripts/laya-fp1-ep234`, 기록.
- **보존**: 기존 패키지(`laya_imitation`·`laya_ladder`·`laya_v10`·`laya_v11`·`foulplay`)와 자료·봉인, `.tools/foul-play/src`는 바이트 단위로 같게 둔다. foul-play 코드는 import만 한다.
- **자원**:
  - 자료 단계는 CPU, `scripts/mem-guard` 상한 40 GB다.
  - 학습은 GPU 0~3 DDP, 상한 100 GB다.
  - 동시에 도는 작업의 상한 합은 80 GB 이하로 두고, 무거운 작업 전에 `free -g`를 확인한다(EP-231 교훈).
- **외부 호출**: 없다.

## 완료 기준

- [x] D-213·EP-234·EX-177~179 등록, catalog build/check
- [ ] 추적기 어댑터·fp1 렌더러·서빙 구현, 단위 검사
- [x] EX-177 qualification 통과, 자료 생성·봉인
- [ ] EX-178 DDP 검사·사전 측정·3 epoch 학습·선택·잠긴 test 평가
- [ ] EX-179 mock 2/2 → execute 128 → export(뷰어·보고·봉인), 뷰어 브라우저 확인
- [ ] 결과를 EX·STATUS·catalog에 기록하고 보고

## 절차

1. 구현: 추적기 어댑터 → 렌더러 → 선택지 대응 → 서빙(배틀 actor 연결은 `integration/foulplay/serve_v11.py` 방식).
2. `scripts/laya-fp1-ep234 data`(EX-177) → `train`(EX-178) → `battle EX-179`.
3. 각 단계는 산출물이 있으면 건너뛰고, 실패하면 멈춘다. 자동 재실행은 없다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 아래는 그 자리에서 멈추고 보고한다.

- EX-177: 제외 비율 > 0.01, 서빙 일치 실패, 기본값 검사 실패
- EX-178: DDP 검사 불일치, loss NaN
- EX-179: 정상 종료 120 미만이면 판정 보류로 적는다

## 진행

- 2026-11-18 — 사용자와 범위를 정했다(입력 전부 교체, 처음부터 전체 학습, 기록 문장 제외). 초안 확인 뒤 등록했다.
- 2026-11-18 — 구현(`integration/laya_fp1/`: `tracker.py`, `render_fp1.py`, `data_fp1.py`, `tokens_fp1.py`, `train_fp1.py`, `probe.py`, `qualify.py`, `tests/test_fp1.py` 5개 통과, `scripts/laya-fp1-ep234`).
  - 추적기: 리플레이를 한 플레이어 시점으로 foul-play `Battle`에 흘린다. 결정마다 그 기록의 내 팀 스냅샷으로 request를 만들어 `request()` → `process_battle_updates()` 순서로 처리한다. 로그 변환은 두 가지다: 내 쪽 `x/100` HP를 실수 HP로, 과거 로그의 `-weather|Snow`를 `Snowscape`로. 내 선택이 드러나지 않은 결정(라벨 없음)은 +5 우선도 기술(`helpinghand`)로 기록해 그 턴의 스피드 추론을 건너뛴다.
  - 시험(래더 10판 1,272결정): 종·HP·랭크 불일치 0, 상대 스피드 범위가 좁혀진 결정 73%.
  - 알게 된 것: `calculate_damage`는 (일반 최대, 급소 최대)만 돌려주고 `-tera` 선택에는 오류 없이 0을 낸다. 그래서 데미지는 `generate_instructions` 갈래로 계산한다. 교체 명령은 `switch X`가 아니라 포켓몬 id만 쓴다. 엔진이 모르는 특성은 `NONE`, 모르는 도구는 `UNKNOWNITEM`으로 읽힌다(qualification 3 검사에 쓴다).
  - 표본 채우기의 세트 후보 거르기를 한 결정 안에서만 캐시했다. 렌더 결과가 캐시 전과 같음을 확인했다.
  - 첫 토큰 측정(400행)에서 선택지 하나의 길이가 64토큰을 넘는 행이 29%였다. 선택지 문장을 압축했다(기술 이름 반복 제거, `tera <type>`, % 기호 제거, 효과는 "아무 행동 없음" 기준선을 뺀 상위 3개). 재측정 1,268행 중 1행(0.08%)이다.
  - qualification 3 기준 미달(엔진이 구현하지 않은 도구, 상대 표본 세트의 `typeless` 테라)을 사용자에게 보고했다. 사용자 지시("1번으로 기록하고 진행")로 엔진 한계로 기록하고 진행한다.
- 2026-11-18 — EX-177 렌더를 12:32 KST(03:32Z)에 시작했다(작업자 96개, `scripts/mem-guard 40`, 20,061판, 참조 1,245,259행). 초당 약 2판, 예상 약 2.8시간, 메모리 약 12 GB. 첫 200판에서 오류 6건이 나왔다. 원인은 Greninja-Bond의 공개 이름 별칭(`greninja`)이다. 실행 중에는 코드를 고치지 않고(작업자가 재시작할 때 새 코드를 읽음), 렌더가 끝난 뒤 별칭을 고쳐 오류 난 경기만 다시 렌더한다.
- 2026-11-18 — EX-179용 `render_worker.py`(경기별 추적기), `serve_fp1.py`(입력에 `fp1` 항목을 받는 서빙), `battle_fp1.py`(EP-232 실행기에 EX-179 study·서빙·작업자 연결)를 새 파일로 만들었다. 시험은 EX-178 체크포인트가 나온 뒤 mock으로 한다. 뷰어 내보내기는 서빙 응답에 기록된 fp1 입력을 쓰도록 아직 맞춰야 한다.
- 2026-11-18 — 사용자가 EP-231 래더 비교를 v11rtc 단일 루프로 바꿨다. 사용자 지시("그 순서대로 진행")로, EX-177 자료가 준비되면 경기 사이에 v11rtc 서빙을 GPU 3에서 CPU로 옮기고(같은 체크포인트, torch 스레드 8, 루프 재시작·같은 종료 시각) GPU 0~3에서 EX-178을 18:00 KST 전에 시작한다. "EP-231 프로세스는 건드리지 않는다"의 사용자 승인 예외다. 근거: CPU v10rt 서빙 판단 지연 p50 0.87초·최대 1.28초(280회).
  - 사용자 추가 지시: CPU 루프는 학습 여부와 상관없이 23:00 KST(14:00Z)까지 돌리고, 팀은 래더에서 가장 좋다고 판단되는 것으로 고른다. 래더에 써 본 팀 3개(nhy_test1629, 결과 기록과 대조된 275판)를 레이팅 기대 승률 대비 초과 승수로 비교했다: `t95bfb45561` 142판 0.514, +1.5(상대 평균 1326) / `t6e257bdf5e` 60판 0.533, −0.7(1317) / `tcd9f36174b` 73판 0.548, −0.5(1183). 셋 다 잡음 범위이지만, 판 수가 가장 많고 높은 레이팅 상대에서 유일하게 기대 이상이며 EX-174 foul-play 2/2인 `t95bfb45561`(현재 팀)을 유지한다.
  - 사용자 재지시: 기존 팀이 아닌 blimAI 팀(`teams_blim.json` 65개, 로컬 검증기 gen9ou 65/65 통과) 중 포켓몬 특성으로 고른다. 기준은 EX-169의 봇 약점(교체율 0.082 대 사람 0.245, 직전 기술 반복, 능력치 쌓는 상대 앞 수동적)이다. 구애 도구 없음, 자가 회복·Rest 위주, 교체 없이 능력치 쌓기 대응(Unaware·Roar·화상), 한 자리에서 이기는 수단을 본다. `te76a9c3ec1`(Slowking-Galar, Corviknight IronDefense/BodyPress/Defog/Roost, Skeledirge Unaware/SlackOff/WillOWisp, Ting-Lu Rest/SleepTalk, Hydrapple NastyPlot Regenerator, Zamazenta IronDefense/BodyPress/Roar; 1860+, 2025-01)로 바꾼다. 차선은 `t9f05bb6c11`(Garganacl·Dondozo Unaware·Clodsire·Gholdengo·Dragonite·Meowscarada)이다.
  - 2026-11-18 15:50 KST(06:50Z) 전환 실행. **사고**: 루프 PID를 `$(pgrep -f ...)`로 넘겼는데 명령 치환 subshell까지 잡혀 PID 두 개가 한 인자로 들어갔다. 경계 대기 루프가 바로 끝나 진행 중이던 run 68(48턴, 61결정)에서 GPU 서빙이 내려갔고 봇이 기권했다. 래더 기록 `gen9ou-2715770446`(v11rtc 패, 1377 → 1348)은 서빙 중단 기권이므로 v11rtc 성적 비교에서 뺀다. 기존 루프는 서빙 소멸을 감지해 스스로 끝났다(15:50:52 KST). CPU 서빙(pid 2357639, 스레드 8)과 새 루프(pid 2357916, 팀 `te76a9c3ec1`, 14:00Z 종료)는 run 69부터 정상이다.
  - 2026-11-18 17:30 KST(08:30Z) 사용자 지시로 팀을 `t9ff547d715`(Blim "1850+ Lokix Volt Turn": Pecharunt·Iron Crown·Great Tusk·Zapdos·Dragapult Specs·Lokix Band)로 바꿨다. 근거는 최근 래더 r1500 29,996경기 팀 통계(여섯 마리 중 다섯 이상 일치 24판·플레이어 12명, 레이팅 기대 대비 +0.252, 플레이어 단위 bootstrap 95% [+0.09, +0.38]; 정확 일치 5판뿐, 약 60팀 동시 비교라 근거는 약함)다. `te76a9c3ec1`은 run 69~83에서 15판 7승 8패, 레이팅 합 −25(기권 1판 제외)였다. 진행 중이던 run 83을 끝까지 둔 뒤 기존 루프를 SIGKILL로 멈춰(trap이 서빙을 내리지 않게) 같은 서빙(pid 2357639)·종료 시각으로 새 루프(`exports/laya-play/runtime/ladder_v11rtc_cpu.sh`, `START_RUN=83`)를 띄웠다. run 84부터 새 팀으로 검색한다.
  - 루프는 22:59:50 KST(13:59Z) 종료 시각에 run 159를 끝으로 멈췄다. `t9ff547d715`는 76판 37승 39패(0.487), 레이팅 기대 대비 초과 승수 −0.1, 레이팅 합 +8(1323 → 1331, 상대 평균 1339)로 `te76a9c3ec1`(15판 7승 8패, −0.6)·`t95bfb45561`(146판 76승 70패, +2.9)과 구별되지 않는다. 래더 r1500 통계의 +0.25 초과는 laya 운용에서 재현되지 않았다.
  - 2026-11-19 08:46 KST(11-18 23:46Z) 사용자 지시로 팀 `t9f05bb6c11`(11-18 EX-169 봇 약점 기준 차선: Garganacl·Dondozo Unaware·Clodsire·Gholdengo·Dragonite·Meowscarada) 테스트를 18:00 KST(09:00Z)까지 돌린다. v11rtc CPU 서빙(같은 EX-172 체크포인트 sha256 `9b987f7465a5`, 스레드 8)을 다시 띄웠다(pid 2752044). 처음 루프는 setsid 래퍼 PID를 받아 대국 없이 바로 멈췄고, 실제 서빙 PID로 다시 띄웠다(루프 pid 2752613, run 160부터). 로그 `exports/laya-play/runtime/logs/ladder-loop-20261119.log`.
- 2026-11-19 — 사용자 지시("넵 시작해주세요")로 [EX-180](../experiments/EX-180-laya-fp1e2-vs-foulplay-blim128.md)을 추가했다. EX-178이 epoch 3을 도는 동안 epoch-2 체크포인트(고정 복사본)로 EX-179와 같은 조건의 foul-play Blim 128경기를 CPU로 돌린다. `battle_fp1.py`에 `STUDIES['EX-180']`, `scripts/laya-fp1-ep234`에 `battle EX-179|EX-180` 단계를 넣었다. EX-179는 selected 체크포인트로 그대로 남는다.
- 2026-11-19 10:28 KST — 사용자 지시("fp1 epoch 2로 레더 대전을 바꿔서 실행", 실제 래더 성능 측정)로 공식 래더 모델을 v11rtc에서 fp1 epoch-2로 바꾼다. 팀 `t9f05bb6c11`·종료 18:00 KST는 그대로다.
  - laya-play `bot.py`(작업 트리, 미커밋)에 fp1 경로를 넣었다: 서빙 모델이 `laya-fp1`이면 `Fp1Session`과 같은 `fp1` 항목(game·side·own_sets·public prefix·snapshot·decision kind·previous)을 입력에 붙인다. 서빙은 연구 checkout의 `integration.laya_fp1.serve_fp1`(EX-180 고정 복사본, sha256 `d2dea189…`, CPU 스레드 8, `runtime/serving-fp1e2.ready.json`)이고 모델 이름은 `laya-fp1`이다(serve_fp1이 이 이름만 받는다). 래더 기록의 모델 열은 `laya-fp1`, 렌더러 열은 `fp1-v1`이며 epoch-2 구간은 이 날짜·체크포인트로 구별한다.
  - 공식 래더 전 로컬 서버(8000)에서 무작위 상대와 1판: 39턴 승, 41결정 모두 fp1 항목 포함, 판단 p50 1.91초·최대 2.65초.
  - 판 경계에서 v11rtc 루프를 SIGKILL로 멈추고 v11rtc 서빙(pid 2752044)을 내린 뒤 같은 루프 사본 `runtime/ladder_fp1e2_cpu.sh`를 띄운다(`runtime/swap_to_fp1e2.sh`).
  - 10:29 KST 교체 완료. v11rtc는 11-19 run 160~182에서 `t9f05bb6c11`로 18판 8승 10패, 레이팅 합 −57이었다. fp1e2는 run 183부터(루프 pid 2906011, 서빙 pid 2876653). 첫 판(Step-to-Far, 47턴 패)은 53결정 모두 fp1 항목이 붙었고 판단 p50 1.99초였다.
  - 10:39 KST 사용자 지시("판단이 이상한 점이 많다")로 fp1e2 래더를 멈췄다. 루프(pid 2906011)를 SIGKILL로 멈춰 새 검색을 막고, 진행 중인 run 184는 기권 없이 끝까지 둔 뒤 fp1e2 서빙을 내린다(`runtime/stop_fp1e2_after_game.sh`). 래더는 그 뒤 쉰다.
  - 사용자가 짚은 판단 확인(run 183, 대 Step-to-Far): Dragonite가 공격 +6(턴 21)에 이른 뒤에도 Dragon Dance를 턴 23·25·28·30·37에 골랐고(확률 0.31~0.79), 턴 38~40에 Corviknight(비행)에게 Earthquake를 세 번 골라 기절했다(0.38~0.54). 입력은 맞았다: fp1 상태에 `atk+6 spe+6`이 정확히 찍혔고, 후보 설명에서 최대치 Dragon Dance는 `me atk+1` 효과 표시가 빠지고, Earthquake는 피해(`solo opp …`) 표시가 빠졌다. "효과 없음·면역"을 표시 부재로만 나타내는 입력을 epoch-2 모델이 쓰지 못한 정책 쪽 문제로 본다. run 184의 Clodsire Earthquake(대 Gholdengo, 피해 41~62%)와 +0·+1 Dragon Dance는 정상 판단이다.
- 2026-11-19 — 사용자 지시로 [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md)를 채택했다. 이후 laya 배틀 정책 계획은 foul-play 상대 점수를 개발 목표로, 공식 래더 대전을 최종 실험으로 둔다. 이 계획의 EX-179·EX-180 조건은 바꾸지 않는다.
- 2026-11-19 10:59 KST — 사용자 지시("v10t 모델 레더 대전", 팀 `t95bfb45561`, 18:00 KST까지)로 공식 래더를 v10t로 돌린다. 옛날 모델 래더 성능 확인용이다(D-214의 foul-play 선행 없이 사용자 지시로 실행). 서빙은 laya-play 등록 경로 그대로 `integration.laya_v10.serve_v10`(`models/v10t`, EX-161 selected, sha256 `d440b0f1…`, CPU 스레드 8, `runtime/serving-v10t.ready.json`, pid 2957061), argmax·guard 없음·usage extension 없음. 루프는 `runtime/ladder_fp1e2_cpu.sh`(READY·LABEL 인자)를 `LABEL=v10t`로 띄웠고 run 185부터다. v10rt의 같은 팀 기록(11-17, 79판 42승 37패)과 비교한다.

- 2026-11-18 — EX-177 완료(06:38Z 렌더 끝, Greninja 별칭 수정·138판 재렌더, 제외 0.023%, qualification 7 518/518). EX-178 DDP 검사·사전 측정 통과, 07:2xZ 3 epoch 학습 시작(약 24.4시간).

## 결과 및 증거

아직 없다.
