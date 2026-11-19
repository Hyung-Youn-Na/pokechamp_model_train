# D-209 — laya v10rt 공식 래더 패배 원인 추가 분석과 재학습 v11(입력 수정·정책 교정) 설계

- 상태: Accepted
- 날짜: 2026-11-16

## 맥락

- 2026-11-15~16에 등록 봇 계정으로 v10rt([EX-167](../experiments/EX-167-laya-v10-ladder-training.md))를 공식 Pokémon Showdown gen9ou 래더에 올렸다. 83판 48승 35패(팀 미리보기 기권패 4 포함), 레이팅 1042 → 1288(최고 1341), 팀은 `tcd9f36174b` 고정, 서빙은 CPU다. 상대 레이팅은 대부분 1000~1400대이고 학습 자료는 1500 이상 경기다([D-208](D-208-laya-ladder-r1500-v10.md)).
- 1차 분석(등록 EX 아님, `/workspace/exports/laya-play/docs/analysis/2026-11-16-ladder-analysis.md`, 67판·결정 2,342개):
  - 알 수 있는 이유로 실패한 선택 108건 중 55건은 입력에 실패 표시가 있는데도 고른 것이다(Toxic 33, Toxic Spikes 15, `x0` Earthquake 5, Will-O-Wisp 2).
  - 능력치를 쌓는 상대(Hatterene Calm Mind 5번)에게 `boosts`, `opp threat`, `duel … -> lose`, `streak earthquake x4+`가 모두 입력에 있는데도 Earthquake를 7번 골랐다(확률 .42 → .72).
  - 입력 오류·누락: 엔진 판정의 Protect 처리(상대가 Protect를 쓰는 경우 막힌 기술을 `works`로 셈), 형태 이름이 usage와 연결되지 않음(`ogerpontealtera` 등), 특성 공개 인식 누락(`-start … ability:`, Imposter), Ditto 변신 미추적, `duel` 줄의 회복 무시([D-204](D-204-laya-renderer-v10-all-info.md) #34), Toxic Spikes 2층 판정.
  - 결정적 정책: 결정이 모두 argmax이고 선봉이 31/34판 같았다. 같은 사람 상대에게 4승 뒤 5연패했다.
- 1차 분석 문서에 적힌 사용자 결정: v10rt(EX-167 selected)에서 1 epoch, `duel` 회복 반영, GPU 2·3, 메모리 100 GB 상한(`scripts/mem-guard`), 평가는 잠긴 test 2종과 공식 래더 대전, Abyssal 배틀은 포화라 생략.
- **사용자 결정(2026-11-16 대화)**:
  1. 범위: "학습까지 이어서". 추가 원인 분석 → 설계 → 자료 재생성 → GPU 학습 → 오프라인 평가까지 중간 확인 없이 진행한다. 공식 래더 비교는 따로 지시받는다.
  2. 재학습에서 검토할 수단: "입력 수정 묶음, 라벨 정제·가중, 새 학습 행 추가, 결정 단계 규칙 비교군".
  3. 모델: "두 개 병렬". 입력 수정만 넣은 모델과, 입력 수정에 정책 교정을 더한 모델.
  4. 래더 평가: "모델당 200판". 애매하면 400판까지 늘리는 규칙을 미리 정한다.
  5. "학습시 메모리가 100GB가 넘지 않도록 주의해주세요."
- 중간 확인이 없으므로, 분석 결과를 설계로 옮기는 규칙을 분석 전에 이 결정에 적는다. 규칙을 적용한 결과값은 [EX-169](../experiments/EX-169-laya-v10rt-ladder-loss-analysis.md) 결론과 [EX-170](../experiments/EX-170-laya-v11-data.md) 조건에 적는다.

## 결정

### 1. 추가 원인 분석(EX-169)

1차 분석은 어떤 선택이 실패했는지까지 봤다. 추가 분석은 (가) 어떤 원인이 실제로 판을 지게 했는지, (나) 정책이 표시를 무시하는 이유가 자료에 있는지 봇이 스스로 만든 국면에 있는지를 가른다. 가설 H1~H6과 분석 A1~A6은 EX-169가 소유한다.

### 2. 공통 학습 조건

- 시작점은 EX-167 `checkpoints/selected`이고 1 epoch다. 나머지 설정은 EX-167과 같다(soft-CE, 선택지 섞기, 전체 배치 64, encoder lr 2.5e-5 · head lr 1e-4 → 1e-6 cosine, `act_head` 고정, seed 0, 2,048 / head 768 / 선택지 64).
- epoch의 25·50·75·100% 지점에서 validation(v11 렌더 1,024행)을 재고 체크포인트를 남긴다. validation 원 NLL이 가장 낮은 지점을 고른다(같으면 앞 지점). 온도는 EX-167과 같은 보정 행으로 다시 맞춘다.
- 행·순서·분할·라벨은 `v10-ladder-merged`와 같다(같은 래더 17,510경기 목록). `usage_sets_v3.json`은 그대로 둔다(D-208 결정 4).
- 모델 이름: `v11rt`(입력 수정만), `v11rtc`(입력 수정 + 정책 교정).

### 3. 입력 수정 = 렌더러 v11 (두 모델 공통)

| 수정 | 층 | 학습 자료 처리 |
|---|---|---|
| `duel` 회복 반영: 지속 회복(Leftovers·Black Sludge·Poison Heal·Grassy Terrain), 흡수기, 상태 이상 지속 피해를 턴당 순피해에 넣는다. 공개된 회복기로 내 피해가 상쇄되면 이긴다고 표시하지 않는다. 식은 EX-170이 적는다 | `strategy.duel` | 재렌더 |
| 엔진 판정 Protect 수정(`judge_fixed.cjs`): 상대 Protect류에 막힌 경우를 판단 불가로 처리 | 엔진 판정 저장소 | 대회·래더 전 행 재판정 후 재렌더 |
| 형태 이름 연결(`ogerpontealtera`, `mausholdfour`, `polteageistantique` 등 → usage 키) | `features_v3.species_key` | 재렌더 |
| 특성 공개 인식(`-start … ability:`, Imposter) | 관측 | 렌더 단계에서 기록으로 덧씌울 수 있으면 포함한다. 스냅샷을 바꿔야 하면 서빙만 고치고 학습 자료에서는 뺀다(전 저장소 재생성이 필요해 범위 밖) |
| Toxic Spikes 2층 판정 | 엔진 판정 | A4에서 2층 상태의 Toxic Spikes 사람 선택률이 2% 이하면 `fails`로 바꾼다. 아니면 그대로 둔다 |
| Ditto 변신 추적 | 관측 | 범위 밖 |

- usage 확장(2026-10, 39종)은 서빙에만 쓴다. 그 종들은 로컬 Showdown 규칙 위반 경기로 학습 자료에서 빠져 있어 재렌더에 영향이 없다.

### 4. 정책 교정 (`v11rtc`에만)

| 수단 | 채택 규칙 | 내용 |
|---|---|---|
| 라벨 정제 | 항상 | 사람이 수정 판정기 기준 확정 실패 선택지를 골랐고 로그에서 실제로 실패·무효였던 train 행을 뺀다. 상대가 교체해 빗나간 경우는 남긴다 |
| 가중 | A2에서 사람 라벨보다 v10rt(사람 국면)의 반응률이 낮고(차이의 95% 구간이 0 아래) 그 범주 train 행이 2,000 이상일 때 | 후보 범주: 정체 streak 탈출, `duel lose`에서 교체, 상대 능력치 +2 이상 대응. ×4, 평균 1로 정규화([EX-146](../experiments/EX-146-laya-v6sl-loop-weighted-training.md) 방식). 해당 범주가 없으면 가중하지 않는다 |
| 봇 국면 교정 행 | A2·A3에서 H1이 확인될 때(봇 자기 국면의 비율이 사람 라벨과 v10rt 사람 국면 비율보다 높음) | 로컬 봇 대 봇 512경기에서 확정 실패를 고른 국면과, 직전 자기 기술이 실패한 다음 결정 국면을 모은다. 목표는 v10rt 분포에서 확정 실패 선택지와 직전에 실패한 같은 기술을 0으로 두고 다시 정규화한 것이다. 학습 행의 약 2%가 되게 반복한다. 래더 83판은 평가 전용이라 쓰지 않는다 |
| 테라 지식 비중 | A1에서 테라 오판이 주원인인 패배가 3판 이상일 때 | 테라 지식 57,143행을 3번 넣는다. 아니면 그대로 둔다 |
| 상위 레이팅 가중 | A4에서 문제 행동률이 레이팅 구간에 따라 단조로 줄고 최상·최하 구간 차의 95% 구간이 0을 제외할 때 | 구간 가중(1700 이상 1.5). 승패 가중은 [EX-133](../experiments/EX-133-laya-v2t-v2tw-battle256.md)에서 악화했으므로 쓰지 않는다 |

- `v11rtc`의 총 학습 행 수는 `v11rt`의 ±5% 안에 둔다.

### 5. 결정 단계 규칙(재학습 없음, 래더 비교군)

- 확정 실패 제외: `fails`·`bounced`·`x0; dmg 0-0%` 선택지를 뺀다. `likely fails`는 남긴다. 전부 빠지면 원래대로 둔다.
- 직전 실패 반복 제외: 직전 턴에 같은 상대에게 실패·무효였던 기술을 뺀다.
- 최종 문구는 A5 모의 결과로 정한다. laya-play `bot.py`의 `--guard`(기본 꺼짐)로 넣고, 걸린 결정을 `events.jsonl`에 남긴다.

### 6. 자원과 메모리

- GPU 2·3번만 쓴다. GPU 0·1은 다른 컨테이너가 쓰고 있다. 외부 프로세스 종료와 장치 reset은 하지 않는다.
- 모든 무거운 단계(판정·렌더, 로컬 대전, 학습, 평가)는 `scripts/mem-guard 100` 아래에서 돈다. 두 학습을 동시에 돌릴 때는 하나의 mem-guard 아래에 두어 상한이 합계에 걸리게 한다.
- 학습 전에 표본으로 모델당 적재 최대치를 외삽한다. 합계 예상이 80 GB 이하이고 호스트 여유(`free -g`)가 예상 최대 + 15 GB 이상이면 GPU 한 장씩 동시에 학습한다. 아니면 모델 하나씩 GPU 2장 DDP로 순차 학습한다(총 시간은 같다).
- 자료 재생성과 로컬 대전은 학습과 겹치지 않게 먼저 끝낸다.

### 7. 평가

- 오프라인(보고 전용, [D-191](D-191-no-offline-battle-gate.md)): 잠긴 test 2종에서 v10rt와 같은 행 차이(입력이 바뀐 행은 따로), 표시 선택지 확률 합, 테라 지식 held-out, 래더 재현 장면 세트(EX-169 A6).
- 공식 래더 비교(지시 후 등록·실행):
  - 같은 계정·같은 팀·CPU 서빙, 한 판마다 모델을 바꾸고 순서는 묶음 안에서 무작위다.
  - 1차: v10rt 대 v10rt + 결정 단계 규칙, 각 200판. 2차: v10rt · v11rt · v11rtc, 각 200판(규칙 없음).
  - 주 지표는 승률 차이와 95% 구간(상대 이름 클러스터 bootstrap)이다. 미리보기 기권패는 분모에서 빼고 따로 센다.
  - 차이의 95% 구간이 0과 +10%p를 모두 포함하면 그 쌍만 400판까지 늘린다.
- Abyssal 배틀은 하지 않는다(v7t 이후 포화, 1차 분석 문서의 사용자 결정).

## 거절한 대안

- **입력 수정만으로 재학습**: 실패 선택 108건 중 55건은 표시가 있는데도 고른 것이라 입력 수정으로 줄지 않는다. 입력 수정만 넣은 `v11rt`를 비교용으로 따로 둔다.
- **모든 수정을 합친 모델 하나**: 입력 수정 효과와 정책 교정 효과를 나눌 수 없다(사용자 결정 3).
- **승패 가중**: EX-133에서 Abyssal 성적이 나빠졌다.
- **래더 83판을 교정 행으로 사용**: 같은 판으로 만든 재현 장면 세트의 평가가 오염된다.
- **처음(`laya-typed-decisions`)부터 3 epoch**: GPU 2장으로 약 48시간이다. 사용자가 v10rt에서 1 epoch를 정했다.

## 근거와 한계

- 래더 83판, 팀 하나의 관찰 자료다. 원인 귀속은 인과를 확정하지 못한다. 개입 실험은 A3(입력 한 줄씩 바꾸기)뿐이다.
- `v11rtc`는 여러 수단의 묶음이라 수단끼리는 나눌 수 없다. `v11rt` 대 `v11rtc`로 입력 수정과 정책 교정만 나뉜다.
- 래더 200판에서 구별되는 승률 차이는 약 14%p 이상이다(기준 승률 0.6). 그보다 작은 효과는 "구별되지 않음"으로 남는다.
- 1 epoch 이어 학습은 lr을 처음 값에서 다시 시작한다. 중간 validation 4지점으로 퇴보를 확인한다.
- 미리보기 기권패(6마리 미만 팀, 83판 중 4판)는 모델과 무관하다. 서빙 수정은 이 결정의 범위 밖이고 EX-169 보고에서 따로 제안한다.

## 영향

- 새 코드 `integration/laya_v11/`, 실행 스크립트 `scripts/laya-v11-ep231`. `laya_v10`·`laya_ladder`·`laya_engine`·`laya_imitation`·`laya_threat` 파일과 기존 자료·봉인은 바꾸지 않는다.
- 새 자료 `datasets/generated/laya-engine-judge/v2`, `laya-ladder-engine-judge/v2`, `laya-compact-imitation/v11-all`·`v11-ladder`·`v11-ladder-merged`, 가중·교정 행
- 실행: [EP-231](../plans/EP-231-laya-ladder-postmortem-v11.md), [EX-169](../experiments/EX-169-laya-v10rt-ladder-loss-analysis.md), [EX-170](../experiments/EX-170-laya-v11-data.md), [EX-171](../experiments/EX-171-laya-v11rt-training.md), [EX-172](../experiments/EX-172-laya-v11rtc-training.md)
- 겹치는 Active 계획: [EP-229](../plans/EP-229-laya-opponent-model-search.md)(상대 모델 + 한 턴 탐색). 결정 단계 규칙이 같은 층에 닿지만 EP-229의 탐색은 건드리지 않는다.

## 증거

- 대화(2026-11-16) 사용자 지시와 승인된 계획
- 1차 분석 문서와 스크립트: `/workspace/exports/laya-play/docs/analysis/2026-11-16-ladder-analysis.md`, `2026-11-16-scripts/`, 판 목록 `/workspace/exports/laya-play/ladder/replays.md`
- [D-208](D-208-laya-ladder-r1500-v10.md), [D-204](D-204-laya-renderer-v10-all-info.md), [D-200](D-200-laya-loop-break-opponent-sets.md), [D-193](D-193-laya-outcome-weighted-imitation.md), [D-191](D-191-no-offline-battle-gate.md), [EX-167](../experiments/EX-167-laya-v10-ladder-training.md), [EX-168](../experiments/EX-168-laya-v10t-v10rt-battle256.md)
