# EX-182 — 사람 학습 국면의 foul-play 탐색 교사 라벨(CPU)

- 상태: Completed
- 생성일: 2026-11-19
- 책임자: Claude Code
- 관련 exec plan: [EP-236](../plans/EP-236-laya-v11rtc-foulplay-distill-rl.md)
- 관련 decision: [D-215](../decisions/D-215-laya-foulplay-distill-then-rl.md)
- 비교 대상: [EX-181](EX-181-laya-v10rt-foulplay-search-regret.md)(같은 탐색 설정, EX-174 봇 국면)
- 기준 연구선: `research/model-training`

## 질문 및 목적

`v11-ladder-merged` train의 사람 결정 국면에서 foul-play 탐색 분포를 laya 선택지 id 위의 확률로 만들 수 있는가? 사람 선택과 얼마나 다른가?

## 가설 또는 qualification 목표

- **qualification**(본 생성 전, 시험 50경기):
  1. 대응: 탐색 선택지(기술·`-tera`·교체 id)가 laya 선택지 id에 대응하지 않는 탐색 몫이 결정 평균 0.01 이하, 0.1을 넘는 결정 1% 이하.
  2. 재현: 같은 국면의 반복 탐색(새 표본) 1순위 일치가 EX-181 잡음 기준(86.9%) ±10%p 안.
  3. 시간: 표본당 탐색 p50이 EX-181(3.94초)의 1.5배 이하.
- **보고 지표**: 교사 1순위와 사람 선택의 일치율, 사람 선택의 교사 몫, 교사 분포 엔트로피, 결정 종류·선택 유형(기술/교체/테라)별.

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 국면 | `v11-ladder-merged` train sample id의 원 경기에서 경기 단위로 무작위(seed 20261182) 1,800경기 → 교사 train, 다른 80경기 → 교사 validation. 선봉 결정과 선택지가 하나뿐인 결정은 뺀다. 경기당 최대 30결정을 무작위로 고른다 |
| 재구성 | EX-177 `tracker.Tracker`(내 팀 스냅샷 request, 상대 HP `x/100`, 라벨 없는 결정은 `helpinghand`), `view()` |
| 탐색 | EX-181 `search.sample_states`(foul-play `search_params`·`prepare_battles`, 결정마다 sha256 seed) → 표본마다 `monte_carlo_tree_search(iterations=814,000, threads=1)` → `search.aggregate` |
| 대응 | 각 laya 선택지 id를 `render_fp1.engine_choice`로 엔진 선택지로 바꿔 교사 몫을 붙인다. 대응 없는 탐색 몫은 버리고 다시 정규화한다 |
| 교사 행 | v11 train 행(같은 sample id)의 `state`·`questions`에 `gold.action.probabilities`(교사 분포)를 붙인다. 사람 라벨은 메타로만 남긴다 |
| 자원 | foul-play venv, 작업자 96, nice 19, `scripts/mem-guard 40`. foul-play 경기가 도는 동안은 시작하지 않는다 |

## 실행

- 실행기: `scripts/laya-distill-ep236 teacher`(`integration/laya_distill/data_distill.py`).
- 예상: 약 5만 결정 × 표본 4~8 × 약 4초 ≈ 120만 코어초, 작업자 96에서 약 3.5~4시간.
- 중단: qualification 미달, 대응 실패 결정 1% 초과, mem-guard 종료. 자동 재실행 없음.

## 결과

- qualification(50경기 1,482국면, 국면마다 2회): 1차 미달(대응 없는 몫 > 0.1인 결정 1.55%, 기술 고정 국면 23결정; `qualification-attempt1-unrestricted/`). `restrict`(laya 선택지 밖 기술 사용 불가·테라·교체 막기) 뒤 2차 통과: 대응 없는 몫 평균 0.0·행 비율 0.0, 반복 1순위 일치 0.820, 표본당 p50 3.91초, 사람 선택 일치 0.437, 사람 선택의 교사 몫 평균 0.346.
- label: 1,879/1,880경기, 오류 0. 2026-11-19 15:52Z mem-guard 40 GB로 한 번 중단(7시간에 36→40 GB 증가) → 남은 경기 재개. `gen9ou-2669985156`(train)은 poke-engine 0.0.48 `monte_carlo_tree_search`가 segfault를 내어(단독 재현) 작업자가 죽고 풀이 멈췄다. 이 경기(30국면)는 `paths.EXCLUDED_GAMES`로 뺐다.
- build(`datasets/generated/laya-distill/v1/manifest.json`): staged 55,842, 대응 없는 몫 > 0.1로 버린 행 16, 교사 train 53,462행·validation 2,364행. 사람 행 1,242,187 중 가중 > 0 유지 307,283(25%, validation 경기 제외).

## 결론 및 후속 작업

교사 자료가 준비되었다. EX-183 학습과 EX-184 경기를 시작한다(2026-11-20 00:23Z).
