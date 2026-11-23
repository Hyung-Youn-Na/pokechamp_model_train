# EP-235 — laya v10rt 결정과 foul-play 탐색의 대조 진단(EX-174 기록, CPU)

- 상태: Completed
- 생성일: 2026-11-19
- 책임자: Claude Code
- 승인 근거·범위: 사용자 지시(2026-11-19 대화, foul-play 상대 승률 개선 논의 뒤 "추천해주는 싼 진단을 진행해주세요. 다만 현재 병행중인 작업에 영향이 없도록 주의해서 진행해주세요"). 구현 → [EX-181](../experiments/EX-181-laya-v10rt-foulplay-search-regret.md) 실행 → 보고까지 진행한다. 새 경기·학습·외부 호출은 없다.
- 관련 contract / decision / experiment: [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-211](../decisions/D-211-laya-foulplay-opponent.md), [D-206](../decisions/D-206-laya-opponent-model-search.md), [EX-174](../experiments/EX-174-laya-v10rt-vs-foulplay-blim128.md), [EX-165](../experiments/EX-165-laya-opponent-prediction-scenes.md)
- 겹치는 등록 plan:
  - [EP-234](EP-234-laya-fp1-foulplay-input.md)(Active): EX-180이 CPU에서 foul-play 경기를 돌고, EX-179가 EX-178 뒤에 같은 방식으로 돈다. foul-play 탐색은 시간 기반이라 CPU를 나눠 쓰면 그 경기들의 탐색량이 줄어든다. 그래서 이 계획의 탐색 단계는 foul-play 경기가 하나도 돌지 않을 때만 돈다(EX-181 자원 절). EP-234의 코드·자료·프로세스는 건드리지 않는다.
  - [EP-231](EP-231-laya-ladder-postmortem-v11.md)(Active): 공식 래더 CPU 서빙(v10t, 18:00 KST까지)과 감시 스크립트를 건드리지 않는다. 이 계획의 프로세스는 nice 19로 돈다.
  - [EP-229](EP-229-laya-opponent-model-search.md)(Active, 2단계 대기): 탐색으로 정책을 고친다는 개념이 겹친다. 이 계획은 진단만 하고 서빙 정책을 만들지 않는다. 2단계 등록 여부는 이 결과를 보고 사용자와 정한다.
- D-214와의 관계: 이 계획은 새 처치(입력·학습·서빙 정책)가 아닌 진단이라 foul-play 개발 실험·래더 최종 실험을 함께 등록하지 않는다.
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit·미커밋 변경: `research/model-training`, `ee13b70`. 시작 시 `data/` 아래 미추적 자료 외 미커밋 변경 없음.
- 작업 checkout과 interpreter/launcher: `/workspace`, foul-play venv(`/workspace/.tools/foul-play/.venv`, python 3.11, poke-engine 0.0.48), `PYTHONPATH=.:.tools/foul-play/src`.
- 새 산출물:
  - 코드: `integration/laya_regret/`(사후 분석 `posthoc.py` 포함), `scripts/laya-regret-ep235`
  - 실행 산출물: `runs/model-training/EX-181/`
- 참조 원자료(읽기 전용): `runs/model-training/EX-174/`(games·collection), foul-play 봉인 자료(`.tools/foul-play/data-SHA256SUMS`)

## 목표와 맥락

foul-play 상대 점수를 높이는 방법을 고르기 전에, v10rt가 foul-play에게 진 원인 중 탐색으로 고칠 수 있는 몫이 얼마나 되는지, 어디에 몰려 있는지 본다(2026-11-19 논의). EX-174의 v10rt 결정마다 foul-play와 같은 설정으로 탐색해 laya 선택과 비교한다.

## 범위와 불변 조건

- **포함**: `integration/laya_regret/`, `scripts/laya-regret-ep235`, 기록.
- **보존**: EX-174 산출물·봉인, `integration/foulplay`·`integration/laya_fp1`, `.tools/foul-play/src`는 바꾸지 않는다. foul-play 코드는 import만 한다.
- **자원**: CPU만. GPU를 쓰지 않는다. 세부 조건은 EX-181에 둔다.
- **외부 호출**: 없다.

## 완료 기준

- [x] EP-235·EX-181 등록, catalog build/check
- [x] 재현기·탐색기·집계 구현, 단위 검사, 1경기 시험
- [x] EX-181 준비(재현·표본) → 탐색 → 반복 탐색 → 집계·보고
- [x] 결과를 EX·STATUS·catalog에 기록하고 보고

## 절차

1. 구현과 시험(1경기, 1프로세스, nice 19).
2. `scripts/laya-regret-ep235 prepare` — 재현과 표본 추출(1프로세스, nice 19). foul-play 경기 중에도 돌 수 있다.
3. `scripts/laya-regret-ep235 search` — foul-play 경기가 없을 때만 돈다.
4. `scripts/laya-regret-ep235 report`(등록 지표), `scripts/laya-regret-ep235 posthoc`(사후 분석).

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)과 EX-181 중단 조건을 따른다. 자동 재실행은 없다.

## 진행

- 2026-11-19 — 사용자 지시로 등록했다.
- 2026-11-19 — 구현(`integration/laya_regret/`: `replay.py`, `search.py`, `run.py`, `report.py`, `tests/test_regret.py` 4개 통과, `scripts/laya-regret-ep235`).
  - 재현: laya actor가 받은 websocket 메시지를 foul-play 처리 경로 그대로 흘린다. 기록에서도 그 턴 로그 뒤에 request가 와서, foul-play가 실제로 결정하던 시점과 같다.
  - poke-engine `monte_carlo_tree_search`가 정확한 반복 수(`iterations`)를 받는다. 그래서 탐색 예산을 시간 대신 EX-174 foul-play의 표본당 반복 수 중앙값 814,000으로 고정했다(기계 부하와 무관). EX-174 로그는 표본마다 반복 수를 두 줄 적는다(`fp-b01-s1-a` 568표본·1,136줄).
  - 시험(`fp-b01-s1-a`): 118결정 재현 오류 0, 선택지 대응 빠짐 0. 집계는 2경기·30결정·5,000 반복의 가짜 실행으로 끝까지 확인했다(scratchpad, EX-181 폴더 밖).
- 2026-11-19 12:01 KST(03:01Z) — `prepare` 시작(1프로세스, nice 19·ionice idle, `mem-guard 10`). EX-180이 도는 중이라 탐색은 그 뒤에 시작한다.
- 2026-11-19 12:23 KST — 준비 완료(7,160결정, 표본 48,508개, 오류 0, qualification 재현 검사 통과). 12:24 KST에 `search --wait --until 07:00Z`(16:00 KST)를 걸었다. EX-180 경기 프로세스가 모두 끝나면 시작한다(작업자 32, 약 75분 예상).
- 2026-11-19 14:16 KST(05:16Z) — 탐색 시작. 초당 약 8.1표본이라 약 100분이 걸린다. 회차 0은 15:50 KST 무렵, 반복은 16:00 KST 마감 직전에 끝날 것으로 본다.
- 2026-11-19 15:54 KST(06:54Z) — 탐색 완료(98분, 멈춤 없음, 최대 15.6 GB). `report`와 사후 분석을 돌리고 EX-181 결과·결론, STATUS, catalog를 갱신했다. 완료.

## 결과 및 증거

[EX-181 결과](../experiments/EX-181-laya-v10rt-foulplay-search-regret.md#결과). 원자료는 `runs/model-training/EX-181/`(`report.md`, `result.json`, `posthoc.json`)에 있다. 요지:

- 탐색 1순위와 일치 41.9%, 탐색끼리는 86.9%. 탐색 값의 경기 결과 AUC는 0.695다.
- 값 차이 ≥0.1은 7.8%다. laya 수가 탐색 방문 1% 이상인 결정만 보면 2.9%다. 다음 결정의 V 하락은 값 차이의 15~25%다.
- 결정당 값 차이는 진 경기에서 크지 않다(V를 맞추면 비슷하다). 진 경기에서 낮은 것은 일치율(−8.6%p)이다.
- 효과 없는 수(+6에서 Iron Defense·Bulk Up, 깨어 있을 때의 Sleep Talk 등) 3번 이상 연속: 진 경기 14/85, 이긴 경기 1/42(사후 분석).
- 불일치 값 차이 합의 69%가 laya 확률 상위 3 안에 있다.
