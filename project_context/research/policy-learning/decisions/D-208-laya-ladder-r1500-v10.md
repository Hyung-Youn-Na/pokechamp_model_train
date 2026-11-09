# D-208 — 최근 래더(레이팅 1500 이상) 리플레이를 더한 v10 학습(GPU 4장 DDP, 24시간)

- 상태: Accepted
- 날짜: 2026-11-04

## 맥락

- [D-207](../../../shared/datasets/decisions/D-207-lift-reviewed108-species-limit.md)로 108종 제한을 풀었다.
- 2026-11-04 탐색 검사(등록 EX 아님, `/workspace/data/showdown-replays/ladder-sample/gen9ou-r1500-n1000-s20261104/README.md`):
  - 공개 리플레이 목록 6개월(2026-05-04 ~ 11-04): 388,515경기, 레이팅 1500 이상 76,346경기(`ladder-index/gen9ou-20260504-20261104`).
  - `rating`은 두 선수의 경기 후 레이팅 중 낮은 값이다(표본 1,000/1,000). 모두 싱글(`|gametype|singles`)이다.
  - 표본 1,000경기: EP-100 분류기 후보 878 · 위반 63 · 검토 59. 위반은 모두 로컬 Showdown(`e64915c0e`, 2025-10-27)과 현재 공식 규칙의 차이(Regieleki, Roaring Moon, Revival Blessing, Zoroark, 5월 시험 허용 Volcarona)다.
  - 복원 남은 시점: 108종 모음 59% → 전체 모음 76% → 보강 v2 97%. 사람 선택 결정 51,890행(표본 경기당 약 52행).
  - `impute.revealed_original_sets`가 흡수 회복(`-heal … [from] ability: Water Absorb|[of] 공격자`), Pickpocket·Magician(`-item … [of] 피해자`), Skill Swap 특성을 `[of]`(또는 교환받은 쪽)에 붙인다. 표본에서 불가능한 특성 18건(시점 탈락), 가능한데 틀린 특성 1건(Araquanid Water Absorb).
  - EX-071의 그룹 분할(같은 6마리 팀 공유)은 래더에서 표본 1,000경기 중 565경기가 한 그룹이 되어 쓸 수 없다.
- **사용자 결정(2026-11-04 대화)**:
  - "그냥 위반 팀만 빼는게 편하겠다."
  - "학습 시간에 맞춰 레이팅 1500 이상 최근 경기 순으로 분할", "학습 시간 예상시간 24시간에 맞춰서 데이터 양 조절", "기존 대회 자료와 합칠지 (합침)", "필터: 10턴 이하 경기, 선수당 상한 없음, 봇 이름 기준 제외", "상대 세트 추정표 (고정 유지)"
  - GPU 4장 DDP, 3 epoch, 최근 경기 test + 기존 test, 학습 뒤 v10t와 Abyssal 256경기("4장 3poch 로 가자")
  - "입력은 v10t와 동일한 렌더러 기준으로 학습해줘"

## 결정

1. **원천**: 위 목록에서 ID가 `gen9ou-`(메인 서버)이고 `rating` ≥ 1500인 경기를 업로드 최신순으로 쓴다.
   - 봇 이름 제외: 선수 이름에서 `bottom`·`bother`·`botter`·`robotnik`을 지운 뒤 `bot` 또는 `gpt`(대소문자 무시)가 남으면 그 경기를 뺀다. 해당 이름 목록은 수집 디렉터리의 `excluded-bot-names.json`이다.
   - 선수당 상한은 두지 않는다.
2. **필터**:
   - EP-100 분류기(로컬 Showdown 규칙)의 `candidate`만 쓴다. `incompatible`·`needs_review`는 뺀다. 로컬 Showdown은 갱신하지 않는다.
   - 마지막 `|turn|`이 10 이하인 경기를 뺀다.
   - 팀 미리보기가 서로 다른 6마리가 아닌 경기(래더는 5마리 이하 팀이 합법)를 뺀다. EX-071 경로(`signature`·복원)가 6마리를 전제한다. 30,000경기 후보 26,901 중 3경기(모두 5마리)였다.
   - EX-071 규칙과 같이, 어느 한쪽 팀이라도 평가 팀과 6마리 구성이 같으면 뺀다. 평가 팀은 EX-071 `existing_teams()`의 기존 팀과 EX-120 일정(EX-162·EX-168 배틀) 팀이다.
3. **세트 채우기**:
   - EX-071의 `SetCorpus`로 고르되 모음은 Metamon `modern_replays` gen9ou 25,192팀 전부(D-207)다. EX-071처럼 평가 팀과 6마리 구성이 같은 팀 파일은 모음에서 뺀다(EX-120 일정 팀은 이 모음에서 다시 만든 팀이다).
   - 맞는 세트가 없는 자리에는 보강 v2 세트를 더한다. 같은 종 기존 세트 중 공개 정보와 가장 많이 겹치는 세트에 공개 필드만 바꿔 끼우고, 나머지 기술·도구·특성·테라·성격·노력치는 그 세트 것을 쓴다. 바탕 세트로 합법 결과가 없을 때만 그 경기 달의 Smogon `gen9ou-1500` 통계(없는 달은 가장 최근 달)에서 채운다. 로컬 검증기를 통과한 세트만 쓴다. count는 1이다. 보강 세트는 분할 묶음(test·validation·train)별로 만들고, 한 묶음의 경기는 자기 묶음의 보강 세트만 본다.
   - 특성 귀속 수정(새 경로에서만): 흡수 회복과 Pickpocket·Magician은 앞쪽 대상이 특성 주인이다. Skill Swap·Role Play·Entrainment·Doodle 등 특성 교환 뒤의 특성은 원래 특성으로 보지 않는다. EX-071 파서 파일은 바꾸지 않는다.
4. **행과 입력**:
   - 결정 행은 EX-071 `prepare`와 같은 규칙(라벨, 후보, `eligible`, 상태 토큰 검사)으로 만든다.
   - 입력은 v10t(EX-161)와 같은 렌더러 v10(2,048 / head 768 / 선택지 64)이다. `laya_v10`·`laya_imitation`·`laya_engine`·`laya_threat` 파일을 바꾸지 않고, 같은 중간 저장소(item-state, v5 사실값, early-history, 엔진 판정)를 새 경로에 만들어 쓴다. 상대 세트 추정표 `usage_sets_v3.json`은 그대로다.
5. **분할(기간)**: 결정 1·2를 통과한 경기를 최신순으로 놓고 test, validation, train 순으로 나눈다.
   - test: 가장 최근 150경기의 eligible 행에서 EX-071 방식(`balanced`)으로 1,024행
   - validation: 그다음 60경기에서 512행
   - train: 그보다 앞선 경기를 최신순으로, 결정 7의 예산까지
6. **합치기**: train = EX-071 v10 train(130,411) + 테라 지식(57,143) + 래더 train. 모델 선택 validation = EX-071 validation 512 + 래더 validation 512. test는 EX-071 잠긴 test와 래더 test를 따로 보고한다.
7. **학습 예산**:
   - EX-161과 같은 시작 모델·설정(3 epoch, soft-CE, 선택지 섞기, lr, seed 0)이다. GPU 4장 DDP이고, 전체 배치 64(장당 micro 8 × 누적 2 × 4장)는 EX-161과 같다.
   - 래더 train 행 수는 사전 측정(4장 DDP 처리량)으로 3 epoch가 약 24시간이 되게 정한다. 학습 시간 상한은 두지 않는다.
   - 구현상 EX-161과 다른 점(계산식은 같음):
     - gradient checkpointing을 끈다(메모리를 계산으로 바꾸는 설정일 뿐이고, 4장 처리량이 0.0269 → 0.0216초/행).
     - 선택형 질문이 닿지 않는 가치 헤드(`act_head`)를 고정한다. GPU 1장에서도 기울기가 없어 AdamW가 건너뛰던 파라미터이고, DDP는 기울기가 오지 않는 파라미터가 있으면 동기화가 막힌다.
     - 보정 400행은 합친 모방 행(EX-071 + 래더)에서 laya `split_calibration`으로 뽑는다.
8. **배틀**: EX-162와 같은 방식으로 v10t(EX-161) 대 새 모델(`laya-v10rt`)을 EX-120 일정 Abyssal 256경기로 비교한다. 오프라인 결과로 배틀을 거르지 않는다([D-191](D-191-no-offline-battle-gate.md)).

## 거절한 대안

- **로컬 Showdown을 현재 규칙으로 갱신**: 봇 대전 환경까지 바뀐다. 사용자가 위반 경기 제외를 골랐다.
- **EX-071 그룹 분할**: 래더에서는 거의 전부가 한 그룹이 된다.
- **선수당 상한**: 상위 10명이 선수 자리의 4.2%로 쏠림이 크지 않다. 사용자가 두지 않기로 했다.
- **통계에서 각 필드를 따로 뽑는 보강(v1)**: 기술과 노력치가 어울리지 않는 세트가 나왔다.
- **GPU 1장**: 같은 24시간에 넣을 수 있는 래더 자료가 약 3.5분의 1이다.

## 영향

- 새 코드: `integration/laya_ladder/`
- 새 자료: `/workspace/data/showdown-replays/ladder-recent/`, `datasets/generated/laya-ladder-*`, `laya-compact-imitation/v10-ladder*`
- 실행: [EP-230](../plans/EP-230-laya-ladder-r1500-v10.md), [EX-166](../experiments/EX-166-laya-ladder-r1500-data.md), [EX-167](../experiments/EX-167-laya-v10-ladder-training.md), [EX-168](../experiments/EX-168-laya-v10t-v10rt-battle256.md)

## 증거

- 대화(2026-11-04) 사용자 지시, [D-207](../../../shared/datasets/decisions/D-207-lift-reviewed108-species-limit.md), [D-204](D-204-laya-renderer-v10-all-info.md), [D-191](D-191-no-offline-battle-gate.md), [EX-161](../experiments/EX-161-laya-v10-all-info-training.md), [EX-162](../experiments/EX-162-laya-v7t-v10t-battle256.md)
- 탐색 검사: `/workspace/data/showdown-replays/ladder-sample/gen9ou-r1500-n1000-s20261104/`, 규칙 비교 스크립트 출력(공식 `smogon/pokemon-showdown` master 2026-11-03, 커밋 #11989·`2e0a95137`·`d3c0b4cf3`)
