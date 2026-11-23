# EX-204 — EX-203 래더 고레이팅(1500 이상) 패배 원인 분석(CPU)

- 상태: Completed
- 생성일: 2026-11-23
- 책임자: Claude Code
- 관련 exec plan: [EP-239](../plans/EP-239-laya-engine-value-rerank-training.md)(완료 뒤 사용자 요청 분석)
- 관련 decision: [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-203](EX-203-laya-engine-value-ladder.md), [EX-169](EX-169-laya-v10rt-ladder-loss-analysis.md)(v10rt 래더 패배 분석)
- 기준 연구선: `research/model-training`

## 질문 및 목적

사용자 요청(2026-11-23, "전체적으로 고레이팅 대전에서 많이 패배했는데 패배 원인을 분석해주세요"): EX-203에서 상대 레이팅 1500 이상 35판 8승 27패였다. 왜 졌는가?

## 조건

- 자료: EX-203 104판 중 경기 기록(`exports/laya-play/games/<UTC 시각>-…/events.jsonl`)과 `ladder/replays.csv`가 맞는 103판. 남은 1판(gen9ou-2717839842, 상대 1357, 패)은 봇이 "Showdown rejected battle action" 오류로 멈춘 판이라 기록에 battle_tag가 없다.
- 방법: protocol 줄로 쓰러짐 순서, 쓰러뜨린 상대(직전 공격자)와 그때 상대의 능력치 상승 합(+2 이상이면 "강화된 KO"), 해저드, 테라, 무효(`-immune`) 기술, 교체 수를 경기마다 뽑았다. 집단은 상대 레이팅 1500 이상/미만 × 승/패로 나눴다. 이름에 "bot"이 들어간 상대는 봇으로 분류했다.
- 스크립트·산출물: `runs/model-training/EX-204/`(`ex204_games.py`, `ex204_agg.py`, `ex204_matchup.py`, `ex204-games.jsonl`, `aggregate.txt`).
- 한계: 직전 공격자로 KO를 귀속하므로 해저드·상태이상 KO는 마지막 공격자에게 돌아간다. 봇 분류는 이름 기준이다.

## 결과

| 집단 | 판 | 평균 턴 | 우리 쓰러짐 | 상대 쓰러짐 | 강화된 KO/판 | 해저드 받은 판 | 첫 쓰러짐 턴(중앙값) | 상대 기권 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1500 이상 패 | 27 | 44.9 | 6 | 3.26 | 1.89 | 25 | 18 | 0 |
| 1500 이상 승 | 8 | 53.4 | 3.12 | 5.12 | 1.38 | 6 | 17 | 4 |
| 1500 미만 패 | 23 | 41.2 | 6 | 3.35 | 2.48 | 14 | 8 | 0 |
| 1500 미만 승 | 45 | 34.9 | 1.42 | 3.64 | 0.44 | 28 | 15 | 31 |

1. **같은 두 봇의 고정 팀에 반복해서 졌다(15패).** nickgen6rbrlbot·MissingNo.ZeroBot(1620~1795)과 16판 1승이다. 두 봇은 같은 팀 묶음을 돌려 쓴다.
   - Zapdos·Kyurem·Ogerpon-W·Iron Treads·Pecharunt·Kingambit: Kyurem(테라 땅, Ice Beam·Freeze-Dry·Earth Power)이 한 판에 3~6마리를 강화 없이 쓰러뜨렸다. 이 국면에서 laya는 Corviknight Roost를 한 판에 7~8번 반복했다.
   - Kingambit·Iron Valiant·Great Tusk·Raging Bolt·Ting-Lu·Zamazenta: Ting-Lu Ruination·Spikes(최대 9회)로 깎고 Great Tusk·Zamazenta가 마무리했다.
   - Ogerpon-Wellspring(테라 물, Swords Dance) 묶음: Ogerpon이 2~4마리를 쓰러뜨렸다.
   - 봇에게 진 15판의 KO 90개 중 강화된 KO는 15개(17%)다. 봇은 능력치를 쌓기보다 정면 압박으로 이긴다.
2. **사람 고레이팅 상대에게는 능력치를 쌓은 포켓몬에게 휩쓸렸다(12패).** KO 72개 중 36개(50%)가 +2 이상 강화된 상대에게 당한 것이고, 12판 중 11판에 강화된 KO가 있다. Raging Bolt(Calm Mind, 테라 페어리) 한 마리에게 6마리, Hatterene(Calm Mind) 5마리, Garchomp(Swords Dance) 4마리, Lokix(Swords Dance) 3마리를 잃은 판이 있다. 팀의 Unaware Dondozo는 이런 판에서 Rest·Sleep Talk·Liquidation을 오래 반복했지만 막지 못했다.
3. **무효 기술 반복.** 한 판 안에서 같은 무효를 거듭했다.
   - typhlosi(1574): Dondozo Liquidation이 Volcanion(Water Absorb)에게 14번 무효였다(24~39턴 연속 구간 포함).
   - lost_pig(1379): Earthquake가 Mandibuzz에게 6턴 연속 무효였다.
   - bouvet island(1605): Draco Meteor가 Clefable에게 4번, Earthquake가 Gliscor·Landorus-T에게 7번 무효였다.
   - 1500 이상 판의 무효 상위: Liquidation→Volcanion 15, Draco Meteor→Clefable 5, Defog→Gholdengo 5, Earthquake→Gliscor·Moltres-G 각 4.
4. **선봉 고정.** 103판 중 96판 Raging Bolt 선봉이다(1500 이상에서 Raging Bolt 선봉 32판 7승). 반복해서 만나는 상대에게 읽히기 쉽다.
5. **해저드 압박.** 1500 이상 패배 27판 중 25판에서 해저드를 받았다(Stealth Rock 17, Spikes 6). 팀에는 Defog(Corviknight)·Court Change(Cinderace)뿐이고 해저드 설치기는 없다.
6. 소극적 기술 비율(Rest·Sleep Talk·Roost·Iron Defense·Curse·Defog 등)과 교체 빈도는 집단 사이 차이가 작다(0.38~0.47, 턴당 0.32~0.45). 이것만으로는 패배를 설명하지 못한다.
7. 1500 미만 승리 45판 중 31판은 상대 기권이었다. 레이팅이 오른 것의 상당 부분은 낮은 구간에서 상대가 일찍 포기한 판이다.

## 결론 및 후속 작업

- 고레이팅 패배는 두 갈래다. ① 고정 팀을 돌리는 상위 봇 두 개에게 같은 방식으로 진 것(Kyurem·Ting-Lu·Ogerpon 압박에 대한 답이 팀·정책에 없다). ② 사람 상위권의 능력치 강화 스위퍼에 대한 대응 실패. EX-169(v10rt)의 "능력치 쌓는 상대 대응 실패", "결정적 정책", "실패 표시 무시"와 같은 약점이 EX-200에도 남아 있다.
- 무효 기술 반복은 입력에 실패 기록이 있는데도 일어난다. EX-169·EX-170의 실패 표시 처리가 이 국면(특성 무효: Water Absorb, 비행·부유)을 충분히 덮지 못하는 것으로 보인다.
- 팀 하나(`t95bfb45561`)로 고정했으므로 원인의 일부는 팀 구성(해저드 설치 없음, 특수 Ice/Ground 압박에 약함)이다. 정책 문제와 팀 문제를 가르려면 다른 팀으로 같은 상대를 만나 봐야 한다.
- 판정 없음(보고 전용).
