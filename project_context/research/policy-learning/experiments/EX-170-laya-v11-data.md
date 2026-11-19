# EX-170 — laya 렌더러 v11 학습 자료(판정 재생성·재렌더, 가중·교정 행, CPU)

- 상태: Running
- 생성일: 2026-11-16
- 책임자: Claude Code
- 관련 exec plan: [EP-231](../plans/EP-231-laya-ladder-postmortem-v11.md)
- 관련 decision: [D-209](../decisions/D-209-laya-ladder-postmortem-v11.md), [D-210](../decisions/D-210-laya-v11rtc-policy-correction-values.md), [D-208](../decisions/D-208-laya-ladder-r1500-v10.md), [D-204](../decisions/D-204-laya-renderer-v10-all-info.md)
- 비교 대상: `laya-compact-imitation/v10-all`·`v10-ladder`·`v10-ladder-merged`([EX-161](EX-161-laya-v10-all-info-training.md), [EX-166](EX-166-laya-ladder-r1500-data.md))
- 기준 연구선: `research/model-training`

## 질문 및 목적

v10 자료와 같은 행·순서·분할·라벨에서 입력만 v11로 바꾸면 몇 행이 어떻게 바뀌는가? 그리고 D-209 결정 4의 규칙을 [EX-169](EX-169-laya-v10rt-ladder-loss-analysis.md) 결과에 적용하면 `v11rtc`에 어떤 제외·가중·교정 행이 들어가는가? 결과 자료는 [EX-171](EX-171-laya-v11rt-training.md)·[EX-172](EX-172-laya-v11rtc-training.md)가 쓴다.

## 가설 또는 qualification 목표

- **qualification**:
  - 보존: `laya_v10`·`laya_ladder`·`laya_engine`·`laya_imitation`·`laya_threat` 파일과 v10 자료·저장소의 해시와 봉인이 그대로다.
  - v11 행의 `sample_id` 순서와 라벨이 v10 행과 같다. 길이 초과 제외가 0.5% 이하다.
  - 서빙 렌더와 저장 행이 validation 512행에서 같다(`v10 parity`와 같은 검사).
  - 수정 판정기: 1차 분석에서 바뀐 4건과 Heatran 상대 Will-O-Wisp가 재현된다. 판정이 바뀌는 방향은 `works` → 그 밖뿐이다.
  - `duel` 회복: 래더 16:05 판(`20261116-070518`) 2~3턴이 `win`으로 나오지 않는다.
  - 가중 평균 1, 교정 행 목표 확률 합 1.
- **보고 지표**: 수정별 바뀐 행·선택지 수(판정 표시, `duel`, 형태 이름), 제외·가중 행 수와 범주, 교정 행 수(국면 종류별)와 반복 배수, `v11rtc` 총 학습 행 수.

## 조건 및 변수

| 단계 | 입력 | 규칙 |
|---|---|---|
| 판정 저장소 | EX-071·EX-166 원천과 v5 사실값 저장소 | `judge_fixed.cjs`로 다시 판정(`laya-engine-judge/v2`, `laya-ladder-engine-judge/v2`). item-state·v5 사실값·early-history 저장소는 그대로 쓴다 |
| v11 행 | 위 저장소 | D-209 결정 3의 수정을 실행 시점에 덧씌운 v10 렌더 경로. 예산 2,048 / 768 / 64 |
| 합치기 | `v11-all`, `v11-ladder` | `v10-ladder-merged` manifest의 래더 경기 목록 그대로 |
| 제외·가중 | v11 train, 원본 로그, `ladder-index` | D-209 결정 4(EX-169 결과 적용) |
| 교정 행 | 로컬 봇 대 봇 512경기(v10rt argmax 대 v10rt 샘플링, laya-play 팀 묶음 순환) | D-209 결정 4. 채택 규칙이 충족될 때만 만든다 |

- 고정한 값(2026-11-16, 자료 생성 전. 코드는 `integration/laya_v11/render_v11.py`·`policy.py`):
  - **`duel`**: 기술 선택과 선후는 v10과 같다. 타수는 12턴 안에서 한 턴씩 센다. 맞는 쪽은 맞은 직후 자기 흡수기(Draining Kiss·Oblivion Wing 75%, Giga Drain 등 50%)로 준 피해만큼 회복하고, 턴 끝에 지속 회복(Leftovers, 독 타입의 Black Sludge, 독 상태의 Poison Heal 12.5%, 땅에 붙은 포켓몬의 Grassy Terrain)과 지속 피해(화상 6.25%, 독 12.5%, 맹독 누적, 모래바람)를 받는다. 미공개 도구는 usage 비중 0.5 이상일 때 Leftovers·Black Sludge로 센다. 12턴 안에 쓰러뜨리지 못하면 타수를 `-`로 쓴다. 양쪽 다 `-`면 `even`, 한쪽만 `-`면 그쪽이 진다. 판정이 `win`인데 상대에게 공개된 회복기(Recover·Roost 등 50% 회복)가 있고 내 최대 피해가 50% 미만이면 `even`으로 바꾼다(반대도 같다. 1타로 끝나는 경우는 제외).
  - **형태 이름**: `keldeoresolute`→`keldeo`, `ogerpontealtera`→`ogerpon`, `sinistchamasterpiece`→`sinistcha`, `mausholdfour`→`maushold`, `zarudedada`→`zarude`, `polteageistantique`→`polteageist`, `miniormeteor`→`minior`, `meloettapirouette`→`meloetta`, `cramorantgulping`·`cramorantgorging`→`cramorant`, `dudunsparcethreesegment`→`dudunsparce`, `tatsugiridroopy`·`tatsugiristretchy`→`tatsugiri`, `eiscuenoice`→`eiscue`, `morpekohangry`→`morpeko`, `palafinhero`→`palafin`. 그 형태가 usage에 없고 대상이 있을 때만 쓴다.
  - **특성 공개**: 스냅샷의 상대 액티브 특성이 비어 있고, 등장 이후 기록에 `-start|…|ability: X` 또는 Imposter의 `-transform`이 있으면 OPP 줄의 `ability ?`를 그 특성으로 쓴다. 글자만 바꾼다(판정·피해 계산은 그대로).
  - **Toxic Spikes 2층 판정**: 그대로 둔다(D-210).
  - **제외·가중·교정 행**: D-210의 값. 교정 행의 목표는 v10rt가 그 판에서 낸 확률에서 허용되지 않는 선택지(v11 입력의 확정 실패·x0 피해, 직전에 같은 상대에게 실패·무효였던 기술)를 0으로 두고 다시 정규화한 것이다. 넣는 국면: v10rt가 고른 수나 argmax가 허용되지 않는 선택지인 턴 결정, 직전 자기 기술이 실패·무효였던 턴 결정.
  - **로컬 대전**: laya-play의 봇·서버·환경을 그대로 쓰되 별도 포트(8210)와 Showdown 복사본에서 돈다. 쌍마다 한쪽은 argmax, 다른 쪽은 샘플링(min-p 0.3)이고 팀 묶음(smogon·blim·trained)을 돌려 쓴다. 서빙은 래더에 올린 구성(usage 확장 + 수정 판정기)이다.

## 실행

- 실행기: `python -m integration.laya_v11.cli`(하위 명령은 구현 때 확정), 모두 `scripts/mem-guard 100` 아래. 로컬 대전은 GPU 2·3 서빙, `.pokechamp-data/battle-window/EX-170` 표시.
- 중단: 제외 비율 > 0.005, parity 불일치, 보존 해시 변경, mem-guard 종료. 자동 재실행 없음.

## 결과

진행 중이다(로컬 대전과 교정 행이 남았다). 여기까지의 결과:

- 판정 저장소: `laya-engine-judge/v2` 131,947행(145초), `laya-ladder-engine-judge/v2` 1,581,819행(1,941초).
- v11 행: `v11-all` 130,411 / 512 / 1,024, `v11-ladder` 1,580,283 / 512 / 1,024(train / validation / test). 길이 초과 제외 0. 서빙 렌더와 저장 행 512/512 일치, `generator_matches` 참(두 원천 모두, `runs/model-training/EX-170/{tour,ladder}/diagnostics/parity.json`).
- `v11-ladder-merged`: train 1,242,187, validation 1,024. 행 id·라벨·선택지 순서가 `v10-ladder-merged`와 줄마다 같다.
- v10 대비 바뀐 것(`runs/model-training/EX-170/diff-v10-v11.json`):

  | 자료 | 행 | 바뀐 행 | `duel` 줄 | `fails` 붙은 선택지 | `fails` 빠진 선택지 | 라벨이 새 `fails` 선택지 | 특성 표기 |
  |---|---:|---:|---:|---:|---:|---:|---:|
  | 래더 train | 1,580,283 | 456,432 (28.9%) | 411,788 | 33,748 | 88 | 1,022 | 715 |
  | 대회 train | 130,411 | 40,264 (30.9%) | 38,419 | 4,940 | 0 | 201 | 27 |
  | 래더 test | 1,024 | 361 | 301 | 36 | 0 | 2 | 0 |
  | 대회 test | 1,024 | 224 | 218 | 13 | 0 | 0 | 0 |

  - 래더 train의 `duel` 판정 변화: `win` → `even` 38,363, `win` → `lose` 15,004, `lose` → `even` 54,252, `lose` → `win` 18,760.
  - `fails`가 빠진 88개는 형태 이름 연결 때문이다. 예: 해저드가 이미 깔린 상태의 Stealth Rock은 상대 Maushold-Four의 usage가 연결되면서 "Tidy Up이 먼저 나가면 성공"하는 경우가 생겼다.
- 제외·가중(`laya-v11-policy-weights/v1`): 뺀 행 6,405(0.52%). 가중 행 126,838(`duel lose` 교체 113,190, 정체 streak 탈출 11,002, 상대 +2 이상 교체 10,224). 정규화 배수 0.9506.
- **qualification**:
  - 보존(기존 패키지·자료 해시): 새 파일만 만들었다. 기존 저장소와 자료의 봉인 검사는 생성 단계가 통과했다.
  - 행 순서·라벨: 통과. 길이 초과 0: 통과. 서빙 일치: 통과.
  - 수정 판정기: Heatran에게 Will-O-Wisp가 `fails`로 바뀜을 확인했다(15:03 판 13·14턴). "바뀌는 방향은 `works` → 그 밖뿐"은 판정기 수정에 대해서는 맞지만, 형태 이름 연결로 `fails`가 빠진 선택지 88개가 있다(위). 1차 분석의 4건은 따로 대조하지 않았다.
  - `duel` 회복: 16:05 판 3턴부터 `lose`다(`me - hits … vs opp 5 hits`). **2턴은 `win`으로 남는다**(9 대 9+). 그 결정 시점에는 상대 능력치 상승이 없어 회복을 넣어도 근소 우위다. 등록한 "2~3턴" 가운데 2턴은 미충족이다.
  - 가중 평균 1: 통과(`mean_kept` 1.0). 단위 검사 9개 통과(`integration/laya_v11/tests/test_v11.py`).
- 로컬 대전: 2026-11-16 21:54~23:15 KST에 GPU 서빙으로 166판(기록 332개)을 뒀다. 23:15에 메모리 상한 40 GB에 걸려 종료됐다(서빙 6개의 계산 캐시가 커짐). 2026-11-17 03:00 KST부터 CPU 서빙 3개·6쌍으로 60판씩 묶어 512판까지 채운다(GPU는 EX-171 학습이 쓴다). 끝난 판의 기록은 그대로 쓴다.

## 결론 및 후속 작업

아직 없다.
