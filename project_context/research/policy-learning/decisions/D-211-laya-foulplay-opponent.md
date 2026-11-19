# D-211 — foul-play(탐색 봇)를 laya의 고정 상대로 도입하고 v10rt와 EX-120 일정으로 대전

- 상태: Accepted
- 날짜: 2026-11-17

## 맥락

- Abyssal 상대 점수는 v7t 이후 0.86~0.88에 모여 판본을 구별하지 못한다([EX-162](../experiments/EX-162-laya-v7t-v10t-battle256.md), [EX-168](../experiments/EX-168-laya-v10t-v10rt-battle256.md)).
- `/ref/foul-play`(pmariglia, commit `8f541f8`)는 poke-engine MCTS로 수를 고르는 공개 Showdown 봇이다. 같은 상태를 상대 세트 표본 여러 개로 나눠 탐색하고, 상대 세트는 Smogon 사용 통계와 공개 세트 자료로 추론한다.
- 사용자 지시(2026-11-17 대화): v10rt와 foul-play를 대전한다. 탐색 예산은 "강한 설정 1개", v10rt 서빙은 "지금 CPU"를 골랐다. 계획 승인으로 1회 외부 다운로드(Rust 도구, poke-engine 빌드, foul-play 추론 자료)를 허용했다.

## 결정

1. foul-play를 수정 없이 쓴다. `git archive 8f541f8` 사본(`/workspace/.tools/foul-play/src`)과 전용 venv에서 돈다. 실행 때 바꾸는 것은 네 가지뿐이다: 로컬 서버 로그인(`/trn name,0,`), 외부 호출 차단(모든 `requests` 호출이 실패), Smogon 통계 달을 2026-10으로 고정, 채팅(`hf`·`gg`)과 `/timer on` 전송 생략(EX-168과 같이 타이머 없음).
2. 탐색 설정: `search_time_ms` 3000, `search_parallelism` 4, `search_threads` 1. foul-play는 국면에 따라 상태 4~16개를 샘플해 각각 3초(초반 일부는 1.5초)씩 탐색하므로 결정당 실제 시간은 약 7초다.
3. 상대 추론 자료는 2026-11-17에 한 번 받아 봉인한다: `smogon.com/stats/2026-10/chaos/gen9ou-0.json`, `data.foulplay.cc/gen9ou/{pokemon_full_sets,replay_moves}.json`, `play.pokemonshowdown.com/data/sets/gen9ou.json`. 해시는 `.tools/foul-play/data-SHA256SUMS`에 있고, 매 경기 시작 전에 actor가 확인한다.
4. 일정은 봉인된 EX-120 128슬롯이다. 팀·진영·시뮬레이터 시드·300턴/600결정 상한은 EX-168과 같다. 슬롯마다 EX-168의 v10rt 대 Abyssal 경기와 짝을 지어 비교한다.
5. v10rt(EX-167 selected)는 CPU에서 `laya_ladder.serve` 하나로 서빙한다(8스레드). EP-231 GPU 학습과 병행한다. 동시 4경기(포트 8100~8103)이고 전체 `scripts/mem-guard 25` 아래에서 돈다.
6. 판정은 하지 않는다(보고 전용). 정상 종료가 120/128 미만이면 보고에 "판정 보류"를 적는다. 자동 재실행은 없다.

## 거절한 대안

- **foul-play 기본값(100ms·병렬 1)**: 빠르지만 foul-play의 성능을 대표하지 않는다.
- **예산 두 단계 비교**: 경기 수와 시간이 두 배다. 사용자가 강한 설정 1개를 골랐다.
- **EP-231이 끝난 뒤 GPU 서빙**: EX-168과 서빙 조건이 같아지지만 하루를 기다려야 한다. 승패에는 서빙 장치가 영향을 주지 않으므로(같은 체크포인트·렌더러) CPU를 쓴다.
- **공식 래더에서 foul-play 대전**: 외부 서버 접속이고 상대를 고를 수 없다.

## 근거와 한계

- foul-play의 탐색은 시간 기반이라 같은 시드로도 수가 재현되지 않는다. 같은 슬롯 비교는 팀·진영·시뮬레이터 시드만 같다.
- 상대 추론 통계는 2026-10 한 달 치로 고정했다. 실제 foul-play 래더 운용(매달 갱신)과 다를 수 있다.
- foul-play는 테라를 쓴다(poke-engine `terastallization` 빌드). Abyssal은 쓰지 않는다.

## 영향

- 새 코드: `integration/foulplay/`(`actor.py`, `battle.py`, `paths.py`, `tests/`), `scripts/foulplay-ep232`
- [EP-232](../plans/EP-232-laya-foulplay-v10rt.md), [EX-173](../experiments/EX-173-laya-v10rt-vs-foulplay128.md)

## 증거

- 대화(2026-11-17)의 선택, `/workspace/.tools/foul-play/logs/setup.log`(rustc 1.100.0, poke-engine 0.0.48 `terastallization`), `data-fetched.txt`
