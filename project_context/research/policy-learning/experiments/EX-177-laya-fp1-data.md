# EX-177 — laya fp1 학습 자료(foul-play 추적·표본·poke-engine 재렌더, CPU)

- 상태: Completed
- 생성일: 2026-11-18
- 책임자: Claude Code
- 관련 exec plan: [EP-234](../plans/EP-234-laya-fp1-foulplay-input.md)
- 관련 decision: [D-213](../decisions/D-213-laya-fp1-foulplay-input.md), [D-211](../decisions/D-211-laya-foulplay-opponent.md)
- 비교 대상: [EX-170](EX-170-laya-v11-data.md)의 `v11-ladder-merged`·잠긴 test(같은 행)
- 기준 연구선: `research/model-training`

## 질문 및 목적

`v11-ladder-merged`와 잠긴 test의 같은 행을, foul-play 추적·표본과 poke-engine 계산만으로 2,048토큰 안에 다시 렌더할 수 있는가? 무엇이 얼마나 바뀌는가?

## 가설 또는 qualification 목표

자료 생성 전에 모두 통과해야 한다.

1. **추적 일치**: 512행 표본에서 foul-play 추적 결과가 laya 스냅샷과 같아야 한다(활성 종·HP·상태·랭크·진영·날씨). 불일치는 0이어야 하고, 있으면 원인을 기록한다.
2. **선택지 대응**: laya 선택지 id ↔ poke-engine 이름이 전 행에서 1:1로 대응해야 한다.
3. **기본값 검사**: 모든 엔진 상태에서 체중 0, 테라 `typeless`, 엔진이 모르는 특성·도구 이름이 0이어야 한다(목록 대조).
4. **교체 계산**: `generate_instructions`가 `switch …`를 받지 않는 문제(2026-11-18 확인)를 해결해야 한다. 안 되면 교체 줄은 데미지와 해저드만 적고 그 사실을 기록한다.
5. **데미지 대조(보고 전용)**: 200장면에서 poke-engine 일반 데미지를 @smogon/calc와 비교해 차이 분포를 적는다.
6. **토큰**: 2,048토큰 초과로 빠지는 행 비율이 0.005 이하여야 한다.
7. **서빙 일치**: 서빙 렌더와 저장 행이 512/512 같아야 한다.
8. **세트 소진(보고 전용)**: 모든 세트가 지워져 Smogon 통계로 넘어간 비율을 적는다.

## 조건 및 변수

| 묶음 | 내용 | 출처 |
|---|---|---|
| 전장 | 턴, 결정 종류, 양측 테라 가능 여부, 날씨·남은 턴, 필드·남은 턴, Trick Room·남은 턴, Gravity | `Battle` |
| 사이드 | 양측 진영 상태(층수·턴), Wish·Future Sight 대기, 갇힘 | `Battler` |
| 내 포켓몬(6) | 종, 현재 타입, HP 실수, 상태이상(수면·Rest 턴), 랭크, 휘발 상태·턴, 도구, 특성, 테라 타입·여부, 실수치, 기술·PP·disabled | `Battle.user`(내 세트로 합성한 request) |
| 상대 활성 | 종, 타입, HP%, 상태, 랭크, 휘발, 공개된 도구·제거·Knock Off, 공개 특성, 테라, 공개 기술, `speed_range` min–max, 판정에 영향이 있는 불가능 도구·특성, Choice 가능 여부 | `Battle.opponent`, `inference.py` |
| 상대 세트 | 활성 표본 32개, 벤치 표본 8개(`_sample_pokemon`, 행마다 결정적 시드). 상위 3개 세트를 빈도와 함께 적는다(성격·노력치 요약, 도구, 특성, 테라, 기술 4개). 출처(`teamdatasets-full`/`partial`/`smogonsets`)도 적는다 | `standard_battles.py` |
| 기술 선택지(테라 포함) | 상대 상위 세트 3개 각각에 대한 데미지 %(`calculate_damage`, 일반·급소). 상대 유력 기술 2개와 맞붙인 한 턴 결과: 내가 먼저 움직일 확률, 상대 KO 확률, 내가 KO될 확률, 효과 없음 | `generate_instructions` |
| 교체 선택지 | 들어갈 때 해저드 피해, 상대 유력 기술 2개에 맞는 데미지 %, 한 턴 결과 | poke-engine |

- **빼는 것**: `streak`·이전 턴 기록, `duel`·`out`·`risk`·`opp threat`·전략, `lock`, usage_sets_v3, laya 엔진 판정기, @smogon/calc, 테라 지식 행.
- 행·순서·라벨·분할은 `v11-ladder-merged`(train 1,242,187, validation 1,024)와 잠긴 test 두 개(EX-071 1,024, EX-166 1,024)와 같다.

## 실행

- 실행기: `scripts/laya-fp1-ep234 data`(하위 명령은 구현 때 확정). 추적·엔진 단계는 foul-play venv 작업 프로세스, `scripts/mem-guard 40` 아래.
- 중단: 제외 비율 > 0.01, 서빙 일치 실패, 기본값 검사 실패, mem-guard 종료. 자동 재실행 없음.

## 결과

완료(2026-11-18). 자료 생성 전 qualification:

- 1 추적 일치: 표본 40판(대회 20·래더 20) 2,457결정. 처음에는 104결정이 불일치였고, 그중 78건은 smogtours 리플레이가 상대 HP를 실수로 적는 것이 원인이었다. 상대 실수 HP를 `x/100`으로 바꾼 뒤 26결정만 남았다. 26건은 모두 foul-play가 `healingwish`를 진영 효과로 남겨 두는 데서 나온다(laya 스냅샷은 추적하지 않음). 종·HP·랭크·상태이상·날씨 불일치는 0이다(`runs/model-training/EX-177/qualification-1.json`).
- 2 선택지 대응: 시험한 행 모두 1:1.
- 3 기본값 검사: **기준(0) 미달**. 사용자 지시(2026-11-18 대화, "1번으로 기록하고 진행")로 엔진 한계로 기록하고 진행한다. 입력 문장은 바꾸지 않는다(도구 이름은 그대로 보인다). 전체 자료의 발생 비율은 행별 `defaults` 집계로 보고한다. poke-engine이 구현하지 않은 도구는 "도구 없음"으로 읽힌다(Red Card, Eject Button·Eject Pack, Light Clay, Damp Rock, Icy Rock, Terrain Extender, Mental Herb, Quick Claw, Lagging Tail). 표본 350행에서 내 쪽 260건, 상대 쪽 167건이다. 테라 `typeless`는 상대 표본 세트에서만 153건 나온다. 체중 0과 모르는 특성은 0건이다.
- 4 교체 계산: 해결. 교체 명령은 포켓몬 id만 쓴다.
- 6 토큰: 처음에는 선택지 하나의 길이가 64토큰을 넘는 행이 29%였다. 압축 후 1,268행 중 1행(0.08%)이다.

자료 생성(2026-11-18 03:32Z~06:38Z 렌더, 작업자 96, `scripts/mem-guard 40`, 산출물 `runs/model-training/EX-177/`):

- 렌더 20,061판, 1,241,813행, 오류 138판. 131판은 Greninja-Bond 별칭(로그·스냅샷은 `Greninja`, 원 세트는 `greninjabond`)이었다. request의 종 이름을 항상 공개 이름 `Greninja`로 두도록 `tracker._request`를 고치고 138판만 새 part로 다시 렌더했다(`render --redo-errors`, `order`는 sample id마다 마지막 part의 행을 쓴다). 처음 시도한 반대 방향 수정(원 이름 유지)은 130판에서 활성 종 불일치를 내서 버렸다(`EX-177/redo/`에 보존).
  - 남은 오류 7판: Meloetta 폼 변화 5, Cramorant 1, `switchninetales` 1. 제외로 둔다.
  - 수정 뒤 오류 없던 20판(무작위, seed 234)을 다시 렌더하면 1,330행이 바이트 단위로 같다.
- `order`: train 1,241,896 / 1,242,187행(제외 291행, 0.023%, 모두 `no_fp1_row`), validation·잠긴 test(tour·ladder) 각 1,024/1,024. 중단 기준(0.01) 안이다. 출력 `fp1-ladder-merged/{train,validation}.jsonl`, `fp1-test/{tour,ladder}/test.jsonl`, `manifest.json`.
- 6 토큰(`EX-177/tokens.jsonl`): 2,048 초과 0행. 전체 p99 1,317~1,333, head p99 521~534. 선택지 64토큰 초과 행 비율 validation 0.10%, tour 0.10%, ladder 0.20%, train 표본 2만 행 0.06%(기준 0.005 안).
- 3 기본값 집계(보고, `EX-177/qualification-3-tally.json`): 엔진 기본값이 하나라도 든 행 53.5%(666,347/1,244,968). 상대 표본의 모르는 도구 556,039행, 상대 표본 테라 `typeless` 324,038행, 내 쪽 모르는 도구 220,175행, 상대 특성 NONE 302행, 내 테라 `typeless` 168행. 도구 상위: Eject Button, Red Card, Light Clay, Eject Pack, Heat Rock, Terrain Extender, Damp Rock, Sticky Barb, Mental Herb. 엔진 계산 오류가 든 행 2,456(0.2%).
- 5 데미지 대조(보고, 200장면, `EX-177/qualification-5.json`): poke-engine 일반 최대 데미지가 @smogon/calc와 1%p 안 68.5%, 5%p 안 73.9%, 절대 차이 중앙값 0.04%p. 큰 차이는 다단 히트(Tachyon Cutter 95 대 190), 체중 기술(Low Kick), Kowtow Cleave·Sucker Punch(도구 미해결 장면), Freeze-Dry 대 Water 테라 등이다.
- 7 서빙 일치(`EX-177/qualification-7.json`, `integration/laya_fp1/parity.py`): 잠긴 test 89판의 결정을 `render_worker`에 서빙처럼 하나씩 넣어 렌더하면 518/518행이 저장 행과 같다(통과).
- 8 세트 소진: 행별 진단에 남기지 않아 측정하지 않았다.

## 결론 및 후속 작업

- fp1 자료는 제외 0.023%, 토큰 한도 안, 서빙 일치로 학습·배틀에 쓸 수 있다. 엔진 기본값(모르는 도구·`typeless` 테라)이 행 절반에 들어 있다는 점이 fp1 입력의 알려진 한계다(D-213 qualification 3, 사용자 승인).
- 후속: [EX-178](EX-178-laya-fp1-training.md) 학습(2026-11-18 07:2xZ 시작).
