# EX-034 — 팀 선별 기록

수집일은 모두 **2026-09-11 (Asia/Seoul)**이다. 개별 UTC 수집 시각·paste 작성 계정·원본 응답
hash는 [candidates.json](candidates.json)에 있다. 팀 작성자와 paste 업로더, 운용 해설 작성자를
구분한다. Tournament Bazaar의 소개 글 작성자는 Shaymin Sky이며 builder 귀속은 본문을 따른다.

진입점은 [Sample Teams](https://www.smogon.com/forums/threads/sv-ou-sample-teams.3712513/)와
[Tournament Team’s Bazaar](https://www.smogon.com/forums/threads/sv-ou-tournament-teams-bazaar.3752863/)다.
이 표는 확률 표집이 아닌 목적 표집의 최종 후보12개이며 전체 Smogon 팀의 목록이 아니다.
Sample의 과거 팀 변경 이력도 **외부 팀 provenance**로 읽었으며 프로젝트의 legacy TODO/plan을 승계하지 않았다.

선정 우선순위는 (1) pinned `gen9ou` 합법성, (2) 유일하게 결정된6마리 구성,
(3) 운용 해설/리플레이 출처, (4) 기존 팀과 다른 판단 기회다. 승률이나 A의 오류 수를 보고
고르지 않았다. 수치 난이도 점수는 만들지 않았다. 아래 커뮤니티 근거와 연구자의 과제 적합성
판단은 별개다. Sample 등재·대회 소개를 A에 대한 난이도나 현재 환경의 강함으로 번역하지 않는다.

모든 후보는6마리, 각4기술, item/ability/nature/EV/Tera가 있는 원본이다. IV·level·happiness의
생략값은 Showdown 기본값으로 해석하며 연구자가 EV·기술·Tera를 바꾸지 않는다.
`teams/*.txt`는 PokePaste JSON의 `paste` 문자열을 UTF-8 바이트로 그대로 저장했다(CRLF/공백 포함).
`notes`와 RMT·연구자 해설은 별도 provenance이며 모델 팀 입력에 붙이지 않는다.

## 후보12 비교

| ID / 과제 | 팀 / 작성자 | 배정 | 커뮤니티 근거 | 연구자의 선정·미선정 이유 |
|---|---|---|---|---|
| S1 / setup | [CM Iron Crown Bulky Offense](https://pokepast.es/bad24fb628f8d364) / zioziotrip | 탐색 | [출처](https://www.smogon.com/forums/posts/10299291/): Tournament Bazaar 해설·작성자 직접 paste·OLT replay 연결 | CM Iron Crown/Raging Bolt와 Dragonite의 전개 순서를 비교하기 좋다. 단발 화력보다 셋업 자원 배분을 관찰한다. |
| S2 / setup | [DD Kyurem + Hatterene HO](https://pokepast.es/058f8c309ed8d12e) / oldspicemike | 후속확인 | [출처](https://www.smogon.com/forums/posts/10309430/): Tournament Bazaar 해설·작성자 직접 paste·SCL replay 연결 | Loaded Dice Kyurem, Healing Wish Hatterene, Iron Defense Zamazenta가 S1과 다른 재전개 선택을 제공한다. |
| S3 / setup | [Hawlucha + Gholdengo Grassy Terrain](https://pokepast.es/43eb8733a7cff75e) / Attribute | 미선정 | [출처](https://www.smogon.com/forums/posts/9432596/): 현 Sample 등재·작성자 표시·완전한 paste; 개별 장문 해설 없음 | Grassy Seed와 Unburden의 사용 시점을 볼 수 있으나 셋업 과제에 제한된 턴 효과도 함께 들어간다. 해설 근거가 더 충실한 S1/S2를 우선했다. |
| H1 / hazards | [Hydrapple + Scarf Clefable Balance](https://pokepast.es/39d77dcddc234ff6) / xavgb | 탐색 | [출처](https://www.smogon.com/forums/posts/10298368/): Tournament Bazaar 해설·xavgb 직접 paste라는 게시자 진술·OLT replay 연결 | Samurott/Weavile의 Knock Off, Ceaseless Edge, Gliscor U-turn, Clefable Trick이 누적 진척과 교체 타이밍을 만든다. |
| H2 / hazards | [Landorus + Samurott + Pecharunt BO](https://pokepast.es/425d21e8d00a9fe0) / hellom | 후속확인 | [출처](https://www.smogon.com/forums/posts/10300232/): Tournament Bazaar 해설·hellom 직접 paste·SCL replay 연결 | Stealth Rock/Spikes와 Parting Shot, Roar를 조합해 H1의 수비형 순환과 다른 누적·전개 경로를 확인한다. |
| H3 / hazards | [Expert Belt Zamazenta Offense](https://pokepast.es/162cd868b47319a7) / MAVERICK SHOOTERS | 미선정 | [출처](https://www.smogon.com/forums/posts/10298494/): Tournament Bazaar 해설·MAVERICK SHOOTERS 직접 paste·SCL/OLT replay 연결 | Volt Switch와 제거/재설치 선택은 있으나 누적 설치기보다 마비 지원과 공격 coverage가 중심이다. H1/H2가 목표 과제에 더 직접적이다. |
| R1 / preservation | [Ursaluna Semi-Stall](https://pokepast.es/2163011c55975aaf) / Ewin | 탐색 | [출처](https://www.smogon.com/forums/posts/10298246/): Tournament Bazaar 상세 운용 해설·Ewin set 확인; 직접 replay 링크 없음 | 특수 수비의 Blissey 의존과 Ursaluna의 진척 역할이 핵심 보존/회복 판단을 드러낼 기회를 준다. |
| R2 / preservation | [Slither Wing + Specs Gholdengo Balance](https://pokepast.es/490c1abfd97490f3) / Mada | 후속확인 | [출처](https://www.smogon.com/forums/posts/10300151/): Tournament Bazaar 해설·Mada 직접 paste·SCL replay 연결 | Alomomola Wish/Flip Turn으로 Gholdengo/Ogerpon을 회복시키는 선택을 관찰한다. R1의 전담 벽 보존과 다른 회복 전달 구조다. |
| R3 / preservation | [Samurott + Blissey + Ogerpon Fat](https://pokepast.es/dce51a40b1e57f2d) / ABR | 미선정 | [출처](https://pokepast.es/5c623ee360e9883e): 현 Sample·ABR paste·Fusien 별도 해설·승/패 replay 링크 | 회복과 수비 배분 후보로 충분하나 R1과 Blissey/Gliscor의 보존 문제가 겹친다. Wish 전달로 다른 과제를 주는 R2를 우선했다. |
| W1 / limited_turns | [The SSS Sun](https://pokepast.es/6a30608cd62cbb2e) / Srn | 탐색 | [출처](https://www.smogon.com/forums/threads/the-sss-srns-sun-squad.3749857/): Sample 변경 이력·Srn RMT 및 원본 paste·공개 replay 연결 | Torkoal 재투입/보존, Slither Wing 피벗, Venusaur/Walking Wake 공격을 쾌청 잔여 턴과 연결한다. 기존2/6의 Chilly Reception이 대응 상황을 제공할 수 있다. |
| W2 / limited_turns | [Eject Pack Hoopa Trick Room](https://pokepast.es/ec051e757ed6c770) / LudwigFrog | 후속확인 | [출처](https://www.smogon.com/forums/threads/eject-pack-hoopa-trick-room-peaked-2105-elo-4-5-ft-iron-hands.3723855/): Sample 변경 이력·LudwigFrog RMT·완전한 원본 paste | Trick Room 설정과 Eject Pack/Healing Wish/Lunar Dance를 통한 공격수 투입을 다룬다. Sun의 사소한 변형 대신 다른 턴 제한 기제를 확인한다. |
| W3 / limited_turns | [Zarude Sun](https://pokepast.es/973922f6b4b266e5) / Ewin | 미선정 | [출처](https://pokepast.es/973922f6b4b266e5): 현 Sample·Ewin 작성 paste의 선택지 해설 | Ninetales/Cresselia의 회복·재전개라는 대안이 있으나 W1과 Sun 기제가 겹친다. W2의 다른 제한 턴 기제를 우선했다. |

## 선정8의 원본·근거·불확실성

각 과제의1번 팀이 탐색,2번 팀이 후속확인이다. 아래 hash는 원본 팀 파일 전체의 SHA-256이다.
경쟁 구성 canonical hash 및 정규화된 set은
[팀 검증 결과](../../exec-plans/evidence/ep028/team-validation.json)에 별도로 남겼다.
Canonical은 팀/기술 순서를 정렬하고 별명·Shiny를 제외한다. 원문의 성별은 유지하며 생략은
`unspecified`로 표시한다. Validator가 임의로 채운 성별을 hash에 넣지 않는다.

### S1 — CM Iron Crown Bulky Offense (탐색)

작성자 **zioziotrip**; paste 작성 계정 `zioziotrip`. 수집일2026-09-11.
[발견 글](https://www.smogon.com/forums/posts/10299291/) · [운용 근거](https://www.smogon.com/forums/posts/10299291/) · [원본 paste](https://pokepast.es/bad24fb628f8d364) · [보존 구성](teams/S1.txt).

구성: Ogerpon-Wellspring, Dragonite, Raging Bolt, Great Tusk, Iron Crown, Ting-Lu.

CM Iron Crown/Raging Bolt와 Dragonite의 전개 순서를 비교하기 좋다. 단발 화력보다 셋업 자원 배분을 관찰한다.

불확실성: 해설의 Ogerpon U-turn 언급과 paste의 Encore가 다르다. 선택은 원본 paste이며 해설의 모든 기술 설명을 정답으로 취급하지 않는다.

[연결 replay](https://replay.pokemonshowdown.com/smogtours-gen9ou-795586)의 접근 상태는 [별도 기록](sources/replay-access.json)에 있다.

원본 SHA-256: `b5711d925403504f3be2068b5281a5cd0f34c5adc55ca19df322948f9bbf2627`

### S2 — DD Kyurem + Hatterene HO (후속확인)

작성자 **oldspicemike**; paste 작성 계정 `oldspicemike`. 수집일2026-09-11.
[발견 글](https://www.smogon.com/forums/posts/10309430/) · [운용 근거](https://www.smogon.com/forums/posts/10309430/) · [원본 paste](https://pokepast.es/058f8c309ed8d12e) · [보존 구성](teams/S2.txt).

구성: Kyurem, Landorus-Therian, Hatterene, Iron Moth, Kingambit, Zamazenta.

Loaded Dice Kyurem, Healing Wish Hatterene, Iron Defense Zamazenta가 S1과 다른 재전개 선택을 제공한다.

불확실성: 현행 공개 티어와 고정 환경이 다를 수 있다. Tera Blast를 지우지 않고 pinned validator가 통과한 원형을 사용한다.

[연결 replay](https://replay.pokemonshowdown.com/smogtours-gen9ou-799597)의 접근 상태는 [별도 기록](sources/replay-access.json)에 있다.

원본 SHA-256: `8d2224b2678c3a16961cf6b43baa2775634d76604b2f246d2888ea23e7ca0e2b`

### H1 — Hydrapple + Scarf Clefable Balance (탐색)

작성자 **xavgb**; paste 작성 계정 `Guest 5884090`. 수집일2026-09-11.
[발견 글](https://www.smogon.com/forums/posts/10298368/) · [운용 근거](https://www.smogon.com/forums/posts/10298368/) · [원본 paste](https://pokepast.es/39d77dcddc234ff6) · [보존 구성](teams/H1.txt).

구성: Samurott-Hisui, Hydrapple, Gliscor, Corviknight, Weavile, Clefable.

Samurott/Weavile의 Knock Off, Ceaseless Edge, Gliscor U-turn, Clefable Trick이 누적 진척과 교체 타이밍을 만든다.

불확실성: paste 계정은 Guest 5884090이며 팀 작성자 xavgb와 구분한다. 해설의 강함 평가는 게시자의 정성 평가다.

[연결 replay](https://replay.pokemonshowdown.com/smogtours-gen9ou-795968)의 접근 상태는 [별도 기록](sources/replay-access.json)에 있다.

원본 SHA-256: `840a4c18f5a8e0e295f70eeb6999e89110e808316ea9f3d09288b243a1107d40`

### H2 — Landorus + Samurott + Pecharunt BO (후속확인)

작성자 **hellom**; paste 작성 계정 `Guest 1280433`. 수집일2026-09-11.
[발견 글](https://www.smogon.com/forums/posts/10300232/) · [운용 근거](https://www.smogon.com/forums/posts/10300232/) · [원본 paste](https://pokepast.es/425d21e8d00a9fe0) · [보존 구성](teams/H2.txt).

구성: Landorus-Therian, Kingambit, Samurott-Hisui, Dragonite, Pecharunt, Zamazenta.

Stealth Rock/Spikes와 Parting Shot, Roar를 조합해 H1의 수비형 순환과 다른 누적·전개 경로를 확인한다.

불확실성: Dragonite Thunder Wave 목적은 게시자도 추정으로 제시한다. replay로 숨겨진 모든 set이 독립 확정된 것은 아니다.

[연결 replay](https://replay.pokemonshowdown.com/smogtours-gen9ou-795739)의 접근 상태는 [별도 기록](sources/replay-access.json)에 있다.

원본 SHA-256: `f50ed2a46ca12d6b9befd9fa18f632b811422e67b9497b5d08aa54cedff70eff`

### R1 — Ursaluna Semi-Stall (탐색)

작성자 **Ewin**; paste 작성 계정 `(공란)`. 수집일2026-09-11.
[발견 글](https://www.smogon.com/forums/posts/10298246/) · [운용 근거](https://www.smogon.com/forums/posts/10298246/) · [원본 paste](https://pokepast.es/2163011c55975aaf) · [보존 구성](teams/R1.txt).

구성: Blissey, Ursaluna, Toxapex, Gliscor, Dondozo, Corviknight.

특수 수비의 Blissey 의존과 Ursaluna의 진척 역할이 핵심 보존/회복 판단을 드러낼 기회를 준다.

불확실성: 게시자의 OLT 4-0 진술은 독립 재집계하지 않았다. 제안된 Facade/Iron Defense 변형은 채택하지 않는다. 장기전 watchdog 위험이 있다.

원본 SHA-256: `ece4ffede6eab029611d6b079133d99aba80de1d2cf76a9fe7c2cdea8ef1b335`

### R2 — Slither Wing + Specs Gholdengo Balance (후속확인)

작성자 **Mada**; paste 작성 계정 `Mada`. 수집일2026-09-11.
[발견 글](https://www.smogon.com/forums/posts/10300151/) · [운용 근거](https://www.smogon.com/forums/posts/10300151/) · [원본 paste](https://pokepast.es/490c1abfd97490f3) · [보존 구성](teams/R2.txt).

구성: Slither Wing, Garganacl, Alomomola, Gholdengo, Ogerpon-Wellspring, Gliscor.

Alomomola Wish/Flip Turn으로 Gholdengo/Ogerpon을 회복시키는 선택을 관찰한다. R1의 전담 벽 보존과 다른 회복 전달 구조다.

불확실성: 장기전에 대한 근거는 커뮤니티 운용 설명이다. 링크 로그는110턴이지만 새 봇 대전의 길이를 예측한 실측이 아니다.

[연결 replay](https://replay.pokemonshowdown.com/smogtours-gen9ou-795453)의 접근 상태는 [별도 기록](sources/replay-access.json)에 있다.

원본 SHA-256: `963b7f7f3a3dd9e225bb8acde7ff700044d065da9d2655994cdf9d98251e3b5b`

### W1 — The SSS Sun (탐색)

작성자 **Srn**; paste 작성 계정 `Srn`. 수집일2026-09-11.
[발견 글](https://www.smogon.com/forums/posts/9464352/) · [운용 근거](https://www.smogon.com/forums/threads/the-sss-srns-sun-squad.3749857/) · [원본 paste](https://pokepast.es/6a30608cd62cbb2e) · [보존 구성](teams/W1.txt).

구성: Torkoal, Great Tusk, Slither Wing, Venusaur, Walking Wake, Heatran.

Torkoal 재투입/보존, Slither Wing 피벗, Venusaur/Walking Wake 공격을 쾌청 잔여 턴과 연결한다. 기존2/6의 Chilly Reception이 대응 상황을 제공할 수 있다.

불확실성: 상대가 실제로 날씨를 바꾸는지는 정책 행동에 달렸다. RMT의 피해 계산과 ladder 평가는 별도 독립 검증하지 않았다.

[연결 replay](https://replay.pokemonshowdown.com/gen9ou-2187516554)의 접근 상태는 [별도 기록](sources/replay-access.json)에 있다.

원본 SHA-256: `082a9df28b8443d09339043f85c49277281f3f68653bd7817401bec713c37549`

### W2 — Eject Pack Hoopa Trick Room (후속확인)

작성자 **LudwigFrog**; paste 작성 계정 `LudwigFrog`. 수집일2026-09-11.
[발견 글](https://www.smogon.com/forums/posts/9463717/) · [운용 근거](https://www.smogon.com/forums/threads/eject-pack-hoopa-trick-room-peaked-2105-elo-4-5-ft-iron-hands.3723855/) · [원본 paste](https://pokepast.es/ec051e757ed6c770) · [보존 구성](teams/W2.txt).

구성: Hoopa-Unbound, Ursaluna, Hatterene, Cresselia, Iron Hands, Kingambit.

Trick Room 설정과 Eject Pack/Healing Wish/Lunar Dance를 통한 공격수 투입을 다룬다. Sun의 사소한 변형 대신 다른 턴 제한 기제를 확인한다.

불확실성: 2023년 해설의 metagame은 현재와 다르다. 확인한 첫 replay URL은404이며 전체 replay 검증으로 표시하지 않는다. 상세 RMT와 합법 원본을 근거로 선정했다.

[연결 replay](https://replay.pokemonshowdown.com/gen9ou-1892456641-0tokynwhraa9m3ps8xlgbnk9ei8obu7pw)의 접근 상태는 [별도 기록](sources/replay-access.json)에 있다.

원본 SHA-256: `47ba1a6fbe6a03fd978e4d100f6b785481b54baa8b1990077e8f7021b4f9685e`

## 중복·차별성과 수집 한계

고정 Showdown TeamValidator에서 후보12/12·선정8/8이 합법이며, 선택한 모든8팀을 서로 및
기존13팀 전체와 비교했다. 동일 canonical 팀0, 포켓몬5마리 이상 공통인 근접 변형0이다.
선정8팀 내부의 최대 공통 포켓몬은3마리다. 종 구성만으로 완전 독립성을 주장하지 않으며
선별 근거에 셋업/누적/회복 전달/턴 제한의 다른 경로를 함께 확인했다.

기존 팀2는 Zapdos/Hydrapple/Zamazenta/Slowking-Galar/Tinkaton/Ting-Lu,
팀6은 Kingambit/Cinderace/Landorus-Therian/Iron Valiant/Kyurem/Slowking-Galar다.
두 팀의 피벗·날씨 전환과 팀6의 Court Change는 새 팀과의 판단 상황을 제공할 수 있다.
대진에서 그 행동이 발생할지는 아직 모른다. 기존 팀에도 셋업·회복·설치기가 있으므로
이 과제들이 기존 평가에 전혀 없었다고 주장하지 않는다. 새 선택은 다른 조합과 의존 순서를 추가한다.

후보 밖 사전 탐색에서 현 Sample의 Removal Stall과 Band Zamazenta, Bazaar의 SOULWIND Fat은
slash로 복수 기술/Tera 선택지가 섞여 있었다. 연구자가 한 가지를 골라 원본으로 위장하지 않고
유일한 완전 구성 후보12 목록에 편입하지 않았다. 후보 목록을12개보다 많은 것으로 세지 않는다.

[포럼 metadata](sources/forum-metadata.json)는 방문 페이지/작성자/게시 시점과 수집 HTML hash를,
[sources/](sources/)는 원본 PokePaste JSON을 보존한다. 첫 연결 replay9개 중8개에서 공개 로그
형식만 확인했고 W2의1개는404였다. 전체 replay 전개·숨겨진 EV 일치·대회 승률을 검증한 것이
아니다. R1은 직접 replay 없이 상세 운용 해설을 사용한다. 이 불확실성들은 선정 후에도 유지한다.

PokePaste 수정이나 원본 URL 소멸에 대비해 원본 구성과 JSON hash를 고정했다. 후속 실행은
웹에서 다시 받아 팀을 바꾸지 않고 이 파일을 사용한다. 외부 페이지의 최근 수정은 자동 적용하지 않는다.
