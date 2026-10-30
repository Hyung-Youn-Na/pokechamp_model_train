# D-199 — laya-play 완성 팀(Smogon 샘플·Blim)으로 v5t·v6st·v6ht 대 Abyssal 비교

- 상태: Accepted
- 날짜: 2026-10-30

## 맥락

- EX-137·EX-143·EX-144는 모두 EX-120 일정(새 팀 32개, 128슬롯)으로 두었다. 이 팀들은 Metamon `modern_replays` 팀 모음(D-091 검토 108종)에서 고른 것으로, 리플레이에서 복원했기 때문에 드러나지 않은 기술·도구·노력치는 추정값이다.
- 그래서 사람이 직접 짠 완성 팀이나 실제 메타와는 다를 수 있다는 점을 사용자가 지적했다.
- laya-play 봇은 v1.3.0~v1.5.0부터 완성 팀을 쓴다. Smogon gen9ou 샘플 10팀과 직접 고른 1팀(`teams.json`), Blim 재생목록 pokepaste 65팀(`teams_blim.json`)이다. 둘 다 합법성 검사를 거쳤다.
- **사용자 지시**(2026-10-30): laya-play 봇 완성 팀으로 Abyssal 대전 시험을 한다.

## 결정

1. **팀**: laya-play v1.6.0의 `teams.json`(11)과 `teams_blim.json`(65)을 합친다.
   - 6종족 서명이 같은 팀은 처음 나온 하나만 남긴다. 그 결과 74팀이다.
   - 고정 로컬 Showdown `gen9ou` 검증기(`TeamValidatorClient`)를 다시 통과해야 한다.
   - 학습 리플레이에 같은 6종족 조합이 있는 팀(24팀)도 뺀다고 하지 않는다. 실전 팀 분포를 보려는 것이기 때문이다. 노출 여부로 나눠 보고한다.
2. **일정**: EX-120과 같은 구조다. 팀을 `digest` 순서로 원형 배열하고, 이웃 두 팀을 한 조합으로 묶는다. 조합마다 시드 2개와 팀 교환을 적용해 모델당 74 × 2 × 2 = 296슬롯이다. 상대는 Abyssal이고 조합의 다른 팀을 쓴다. 결과를 보기 전에 생성하고 봉인한다.
3. **모델**: v5t(EX-136), v6st(EX-141), v6ht(EX-142)를 같은 실행에서 같은 슬롯으로 둔다. 서빙 설정은 EX-137·EX-143·EX-144와 같다. v6ht 쪽만 `early_history`를 요청한다.
4. **판정**(실행 전 동결): v6st − v5t, v6ht − v5t를 각각 같은 슬롯 점수 차이로 보고, 조합(74) 클러스터 bootstrap 95%(10,000회)를 쓴다. 기준은 EX-143·EX-144와 같은 비퇴보 기준(margin 0.05)이다.
5. **자원**: GPU2·포트 8108을 쓴다. 단계 상한은 16시간이다(약 888판, 서빙 3개).

## 거절한 대안

- **학습 노출 팀 제외**: 실전에서 쓰는 팀 분포를 보려는 목적과 맞지 않는다. 노출 여부별 보고로 대신한다.
- **모델 쌍마다 따로 실행**: v5t를 두 번 두게 된다. 한 실행에서 세 모델을 같은 슬롯으로 두면 비교가 같은 조건이 된다.
- **사람 상대**: 이 실험은 자동 평가다. 사람 대전과 시나리오는 별도로 본다.

## 근거와 한계

- 상대는 여전히 Abyssal 하나다. 규칙 기반이라 회복·내구 루프를 사람처럼 유도하지 않는다.
- Smogon 샘플 팀은 대회·포럼 팀이라 일부는 학습 리플레이에 같은 조합이 있다(74팀 중 24팀).
- 팀 유형이 고르지 않다(balance 38, offense 20, weather 14, defense 4, 중복 제거 전 기준).

## 영향

- 코드: `integration/laya_imitation/teamset_battle.py`(수집·일정·mock·prepare·execute·export), `config.py`·`cli.py`(`teamset` 명령)
- 계획·실험: [EP-222](../plans/EP-222-laya-play-teams-abyssal-battle.md), [EX-145](../experiments/EX-145-laya-play-teams-v5t-v6st-v6ht-battle.md)

## 증거

- 팀 원자료: `/workspace/exports/laya-play/app/laya_play/teams.json`, `teams_blim.json`(v1.6.0, `provenance/build_teams.py`, `build_teams_blim.py`)
- EX-120 팀 출처: `/workspace/export/teams/README.md`(Metamon `modern_replays`, reviewed108)
