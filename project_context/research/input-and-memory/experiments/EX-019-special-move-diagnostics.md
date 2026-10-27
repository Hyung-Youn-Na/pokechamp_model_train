# EX-019 — 특수 기술 피해 계산 진단

- Status: Completed — 진단·보고 범위만 완료, 계산기 전체 통과 아님
- 날짜: 2026-09-08
- 관련: [D-021](../decisions/D-021-special-move-diagnostics.md), [EP-011](../plans/EP-011-improved-io.md)
- `offline_gate_passed=false`, `calculator_all_passed=false`; Cloud·서버 배틀·승률 비교0.

## 현재 팀과 prior에 대한 결과

현재 팀1·2·6·12의 **61개 고유 기술에서 이번 fixture의 수치 불일치는 없었다**.
그러나 다음 5개 기술의 입력 표현 부족이 있어 해당 기술군 전체를 통과로 해석하지 않는다.
시험은 합성 fixture이며 각 원래 팀 세트의 모든 상황을 검증한 것이 아니다.

| 현재 팀 기술 | 팀 | 원인·의미 |
|---|---|---|
| First Impression | 1 | 등장 후 행동 횟수를 wrapper가 받지 않는다. |
| Sucker Punch | 1, 6 | 상대 선택 행동과 실제 실행 순서를 받지 않는다. |
| Future Sight | 2, 6 | 예약/착탄 턴을 표현하지 않는다. 직접 사용 턴의 피해와 미래 피해를 혼동할 수 있다. |
| Gigaton Hammer | 2 | 직전 사용/실패 이력이 없다. 수치 계산과 사용 가능성은 별개다. |
| Solar Blade | 12 | 충전 턴과 즉시 발동 상태를 표현하지 않는다. Sun 조건도 따로 보존했다. |

**기본 prior에 직접 관련된 수치 문제는 Endeavor다.** Araquanid·Klawf의 관측 기술이
없을 때 선택되는 앞4개에 포함된다. 전체 prior에는 6종에 수록되어 있으며 실제 기본 선택과
구별한다. 사용자 HP100·대상 HP201에서 Showdown101, raw0, Python/Node wrapper0으로
사전 관측을 재현했다. 사용자 HP가 대상보다 같거나 높으면 Showdown 실패0은 정상이다.

Mirror Coat는 기본 prior의 Alomomola·Blastoise·Milotic·Tatsugiri·Tentacruel에 포함된다.
특수 피해51을 실제로 받은 fixture에서 Showdown102 / raw0 / wrapper0이다. 다만 피격
이력을 wrapper에 전달할 방법이 없으므로 수치 불일치 분모에 섞지 않고 **입력 표현 부족**으로
분류했다. 반사 기술4종은 피격 없음/물리/특수/연속 공격/직전 턴/선행 행동 조건을 구별했다.
피격 없는 경우의0 자체는 오류가 아니다. 정보 부족 상태의 정상0 응답38건을 별도 표시했으며
정상 타입 면역0 또는 실패0를 곧바로 계산 오류라고 주장하지 않는다.

Pain Split은 Rotom·Rotom-Heat·Rotom-Wash·Weezing-Galar의 기본 prior에 포함된다.
HP100/201은150/150으로 재분배되지만 직접 피해 기록은0이다. wrapper는 Status 기술을
명시적으로 제외한다. 미지원 효과를 직접 피해0으로 통과 처리하지 않았다.

Ditto prior의 `Nothing`은 원본에도 존재하며 기본 앞4개 선택 위치에 있다. 후보에서 제거하지
않고 이름·출처·제외 사유를 봉인했다. `state.py`의 앞4개 선택과 worker의 unknown move 거부를
연결하면 운영 입력 실패 가능성이 있다(소스에 근거한 추론이며 실제 Ditto 배틀은 미실행).
이번 작업에서 prior를 정정하지 않았다.

## 분모와 방법

| 항목 | 수 |
|---|---:|
| 후보 전체(placeholder 포함) | 343 |
| prior 전체 수록 후보 / 기본 앞4개 후보 | 332 / 269 |
| 현재 팀1·2·6·12 고유 기술 | 61 |
| 범위 제외(일반 Status90 + Nothing1) | 91 |
| 실행 기술 / fixture | 252 / 1,010 |
| fixture별 명시적 피해 난수 | 16 (85–100) |
| Showdown 실행 / 실제 wrapper 응답 | 각각16,160 |
| 일치 | 685 |
| 수치 불일치 | 73 |
| 입력 표현 부족 | 234 |
| 명시적 미지원(Pain Split) | 18 |
| 별도 미검증 범위 기록 | 64 |
| 명시적 타수의 raw 타격별 대조 | 28/28 일치(조기 기절은 관측 prefix만) |

후보·fixture·제외·미검증 범위·중단 규칙을 실행 전 manifest에 저장했다. 원본 팀 파일과
고정 prior를 읽으며 관측 기술이 없을 때 기본 선택은 빈도 재정렬 없이 현재 배열의 앞4개다.
기술 합법성 검사를 생략한 테스트 전용 Gen9 `Format`을 메모리에서 만들고 `runMove` 및
필요한 `beforeTurnCallback`을 실행한다. registry/submodule 파일은 바꾸지 않는다.
명중만 강제하고 일반 critical은 끄되 기술 고유의 확정 critical은 유지한다. 다른 확률 분기는
고정 seed `[1,2,3,4]`이며 별도 효과 확률을 추정하지 않는다.

레벨·종족·IV/EV·능력치·HP·랭크·특성·도구·상태·테라·날씨·필드를 동일한 명시적 입력에서
생성하고 실제 적용 상태를 assertion으로 대조한다. 피격 이력 fixture는 선행 기술 실행 후의
실제 HP를 raw와 wrapper에도 전달한다. 피격 이력 자체는 표현 불가능 사실을 보존한다.
직접 피해는 `Damage` event 이후 `Pokemon.damage`의 HP cap 전 인자와 실제 HP 차감으로
구별한다. 반동·자가 기절·회복·잔여 피해를 더하지 않으며 Pain Split의 `sethp`는 별도다.

각 단타는16개 난수를 대조한다. 연속 공격은 타수와 타격별 수치를 보존하며 동일 난수를
모든 타격에 적용한 조건부 경로만 시험한다. 독립16^n 난수의 전체 분포·KO 확률이 아니다.
최소/최대/고정 타수, 조기 기절, Skill Link·Technician·Loaded Dice 조건을 포함했다.
HP1·2·201·202, 공격 강화/테라, Protect·타입·Wonder Guard/Mold Breaker, 사용자 HP 관계,
상태·도구·날씨·지형 on/off, HP/랭크·속도비의 경계 일부를 포함한다.

**64개 미검증 기록**은 공통 fixture만으로 모든 개별 mechanics의 분기 경계까지 검증한 것으로
읽지 않도록 봉인한 범위 제한이다. 특히 모든 무게 경계 전후, 전용 종족/도구/특성 조합,
전체 확률 분기, 미래 턴과 scheduler/행동 실행 가능성, 연속 공격 도중의 모든 효과는 미검증이다.
원래 팀 세트의 전면 재생이나 전체 의미 rubric도 이번 범위 밖이다.

## 수치 불일치 원인과 경계

73건은9개 기술의 fixture이며 전부 **Showdown→raw calculator** 경계에서 발생했다.
동일한 표현 가능 입력에서 raw→wrapper만의 추가 수치 차이는 없었다. 각73건을 새 Node
프로세스·새 Battle·새 Pokemon에서 재생성하고 실제 Python wrapper도 새 프로세스로
최소 첫 난수를 재확인했다. protocol의 wall-clock `|t:|`만 재현 비교에서 제외한다.

| 기술 | 불일치 fixture | 원인·대표 관측 |
|---|---:|---|
| Endeavor | 5 | Showdown의 HP 차이 callback을 calc가 구현하지 않아 BP0 조기 반환. HP100/201에서101/0/0. |
| Super Fang | 8 | 현재 half-HP 분기는 Nature’s Madness/Ruination만 포함한다. 대상 HP201에서100/0/0. 현재 팀/prior에는 없고 고위험 필수로 선정했다. |
| Fissure, Guillotine, Horn Drill, Sheer Cold | 각9 | 성공한 Showdown 일격기는 maxHP를 피해로 전달(Blissey651), 실제201 차감. calc는0. 실패하는 레벨·타입·Sturdy 조건은 별도다. 현재 팀/prior에는 없다. |
| Aura Wheel, Double Shock, Hyperspace Fury | 각8 | Mew 및 부적합 조건에서 Showdown은 종족/현재 타입 제한으로 실패하지만 calc는 피해 수치를 반환. Morpeko·Pawmot·Hoopa-Unbound의 유효 종족 대조는 일치. 실제 전용 종족 prior의 수치 오류로 일반화하지 않는다. |

근거는 pinned [Showdown moves.ts](../../../../pokemon-showdown/data/moves.ts)의 `damageCallback`,
`onTry`/`onTryImmunity`, [battle-actions.ts](../../../../pokemon-showdown/sim/battle-actions.ts)의
명중·일격기·전체 실행 경로와 봉인된 calc `dist/mechanics/gen789.js` 및 `util.js`다.
calc의 고정 피해 helper는 Seismic Toss/Night Shade/Dragon Rage/Sonic Boom을 처리하고,
Final Gambit 및 패치된 half-HP를 별도 처리한 뒤 BP0이면 기본0 결과를 반환한다.
worker는 성공 응답의 유한 범위인지 검사하지만 BP0 기술의 실행 의미나 이력 지원 여부를
판별하지 않는다. 기존 런타임에 이 진단 판정을 소급 적용하지 않았다.

Counter·Mirror Coat·Metal Burst·Comeuppance의 입력 부족은 별도 원인이다. 물리 피해10 뒤
Counter20, Metal Burst/Comeuppance15, 특수 피해51 뒤 Mirror Coat102를 관측했다.
Double Hit의9+9 피격 뒤 Counter는18로 마지막 타격만 반사한다. raw와 wrapper는 모두0이다.
Pain Split은 calc에도 Status 조기 반환 뒤 별도 이름 분기가 있어 현재 Gen9 경로에서는0이고,
wrapper는 명시적으로 Status 제외 응답을 반환한다. Showdown HP 재분배 효과는 독립 관측했다.

후속 수정 후보(이번에 미실행)는 ① Endeavor·Super Fang 등 명시적 지원/거부 정책,
② 피격·행동·충전·미래 턴 정보를 전달할 계약과 미지원 표시, ③ 타수/타격 및 HP 재분배의
별도 의미, ④ 종족·타입 제한, ⑤ prior Nothing 정제/검증이다. 패키지 업그레이드나 임의0 보정은
이번 결과의 일부가 아니다. 변경 전에 별도 승인 범위와 source identity를 정해야 한다.

## 검증과 실패 자료

- 신규 진단 회귀21개 및 전체 integration **202 passed**(47.34초). 외부 Pydantic deprecation 경고1.
- 기존 Ruination·Air Balloon·SpA−2·저HP·프로세스 장애/identity 실패 회귀 포함.
- Ruff E/F/I/W(100열), Node syntax, Python compileall 통과.
- 최종 source/build/입력776파일 봉인, 로드된 Showdown build source map51개와 pinned source 대조.
- EX-018 source manifest의 기존 파일과 현재 파일 차이0: 계산기·wrapper·운영 입력 불변.
- 개발 dev1은 날씨 source 누락으로 중단, dev2는 timestamp 비교로 중단했다.
  dev3은 사후 검증기 회귀에서 Snow ID 변환·Counter callback·최대 타수 fixture 오류를 발견해
  **무효**로 기록했다. dev3의 완료 플래그나 수치는 최종 evidence로 승계하지 않는다.
  기존 자료는 보존하며 최종 manifest의 `development_runs`에 무효 사유를 연결했다.

진단 완료는 모든 선정 시험에 결과/미검증 사유가 있다는 뜻이다. 계산기 전체 통과나
EP-011 전체 완료가 아니며 `offline_gate_passed=false` 및 Blocked 상태를 유지한다.

## 봉인 자료와 재실행

- [후보·fixture·source manifest](../../../../.pokechamp-data/io-improvement/ex019-special-moves-final/manifest.json)
- [전체 비교 결과](../../../../.pokechamp-data/io-improvement/ex019-special-moves-final/results.json)
- [기술별 수록/기본 선택과 문제 목록](../../../../.pokechamp-data/io-improvement/ex019-special-moves-final/report.md)
- [Showdown 관측·raw 응답](../../../../.pokechamp-data/io-improvement/ex019-special-moves-final/oracle.jsonl)
- [Python/Node wrapper 응답](../../../../.pokechamp-data/io-improvement/ex019-special-moves-final/wrapper.jsonl)
- [독립 재현](../../../../.pokechamp-data/io-improvement/ex019-special-moves-final/reproductions.jsonl)
- [source snapshot](../../../../.pokechamp-data/io-improvement/ex019-special-moves-final/sources.tar.gz)
- [출력 checksum](../../../../.pokechamp-data/io-improvement/ex019-special-moves-final/checksums.json)
- [원인 보고 및 종합 검증 봉인](../../../../.pokechamp-data/io-improvement/ex019-special-moves-review/verification.json)
- [도구 사용법](../../../../integration/pokechamp/diagnostics/README.md)

```sh
PYTHONPATH=. pokechamp/.venv/bin/python -m integration.pokechamp.diagnostics.special_moves \
  --output .pokechamp-data/io-improvement/ex019-special-moves-new
```
