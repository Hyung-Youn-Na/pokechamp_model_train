# EX-126 — laya v2 + 테라 + 효과 지식 데이터 학습(GPU2)

- 상태: Completed
- 생성일: 2026-10-23
- 책임자: Claude Code
- 관련 exec plan: [EP-213](../plans/EP-213-laya-effect-knowledge.md)
- 관련 decision: [D-188](../decisions/D-188-laya-effect-knowledge.md)
- 비교 대상: [EX-124](EX-124-laya-v2-tera-knowledge-training.md) selected(v2+테라, 효과 지식 없음)
- 기준 연구선: `research/model-training`

## 질문 및 목적

EX-124의 학습 행(v2-all 모방 + 테라 지식)에 기술·도구·특성 효과 지식 행을 더하면 다음이 성립하는가?
- 실패·무효가 정해진 선택지에 주는 확률이 줄어든다.
- 일반 재현은 유지된다.
- 효과 지식 자체를 습득한다.

## 가설 또는 qualification 목표

- **qualification**:
  - A 지식 행 정답이 모두 고정 엔진 재현과 일치한다(불일치 0).
  - 길이 초과로 제외된 학습 행이 0.5% 이하다.
  - selected의 효과 held-out 정답률(A, B, C 각각)이 initial보다 높다.
- **판정**(실행 전 동결, 잠긴 test 1,024, v2-all 행):
  - **주 지표 F**: 공개 정보만으로 결과가 실패·무효·흡수·반사로 정해지는 선택지(`effect_knowledge.option_outcomes`)를 1개 이상 가진 test 행이 대상이다(234행, 리플레이 131개). 그 선택지 확률 합의 차이(EX-126 selected − EX-124 selected)를 리플레이 클러스터 bootstrap 95%(10,000회, 시드 20261026)로 본다.
  - **비열등 N**: 전체 행 NLL 차이(EX-126 − EX-124)의 같은 방식 95% 상한 ≤ +0.02
  - **판정 문구**:
    - F 상한 < 0이고 N 충족 → "실패 선택지 확률 감소, 일반 재현 유지"
    - F 상한 < 0이고 N 불충족 → "실패 선택지 확률 감소, 일반 재현 저하"
    - F 상한 ≥ 0이고 N 충족 → "실패 선택지 차이 불분명, 일반 재현 유지"
    - 그 외 → "개선 없음"
- **보조 지표**(판정 외):
  - 실패 선택지가 1순위인 test 행 수(EX-124 대 EX-126)
  - 사람이 실패 선택지를 고른 행 수(사전 집계 8/234)
  - 효과 held-out 유형별 정답률: initial, EX-124 selected, EX-126 selected
  - 테라 held-out 유형별 정답률(망각 확인): EX-124 저장값 대 EX-126 selected
  - 잠긴 test NLL, 일치율, ECE
- EX-124 쪽 test 값은 EX-124의 저장된 `evaluation/test-selected.jsonl`과 `report.json`을 쓴다. 다시 추론하지 않는다. 효과 held-out만 EX-124 selected로 1회 평가한다.
- 평가 선행 조건: EX-124가 완료·봉인되어 있어야 한다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| EX-126 selected | EX-124와 같은 시작 모델 `e929ae5c`, 설정, `v2-all` 모방 행(train, validation, test 그대로), 테라 지식 train 57,143행, head 512 | 학습 행에 효과 지식 train 행 추가 | `runs/model-training/EX-126/checkpoints/selected/` |

### 효과 규칙표 (`integration/laya_imitation/effect_rules.md`, `effect_rules.json`)

1차이자 유일한 근거는 Showdown `e64915c0e` 엔진이다. 판정 순서는 엔진 `hitStep*` 순서를 따른다.

1. 기술 자체 조건:
   - Aurora Veil 눈 요구, 같은 벽 중복
   - Sleep Talk·Snore는 잠듦 요구
   - Rest 조건
   - Substitute는 HP 1/4 이하이거나 이미 있으면 실패
   - Fake Out·First Impression 첫 행동
   - Future Sight 중복
   - Sucker Punch·Thunderclap은 상대가 공격기를 고르지 않으면 실패
   - Counter·Mirror Coat는 그 턴에 실제로 맞은 분류가 맞아야 함
   - 압정 최대 층수
2. 상대 쪽 차단:
   - 우선도 차단(Dazzling 계열, Psychic Terrain)
   - Magic Bounce
   - 흡수 특성
   - Good as Gold, Soundproof, Bulletproof, Overcoat
3. 타입·면역:
   - 타입표 0배(Scrappy·Mind's Eye 예외), 땅 기술과 비행·Levitate·Air Balloon
   - Thunder Wave의 땅 무효, powder와 풀·Safety Goggles, Prankster와 악 타입
   - 상대 Substitute(Infiltrator 예외)
   - Encore(휘발 상태 부여 시점)
4. 상태이상:
   - 이미 상태이상이면 실패
   - 타입 면역(Corrosion 예외)
   - 특성 면역
   - Misty/Electric Terrain
5. 공통:
   - Mold Breaker 계열과 Neutralizing Gas는 상대 특성을 무시한다.
   - Gale Wings·Triage는 우선도를 올린다.
6. 선택: Taunt, Assault Vest, Choice 고정, Encore

### 지식 행 (`effect_knowledge.py`, `datasets/generated/laya-effect-knowledge/v1`)

모든 행은 laya choice 행이다. 결과 질문의 보기는 고정 5개: works, fails, immune, absorbed, reflected. 선택 질문은 yes/no다.

- **A 개념 카드**(합성 상황):
  - 군당 2,000행이며 12군이다.
  - 종족 분리: gen9 합법 종족을 digest로 약 10% held-out한다. 특성 보유 종족이 한쪽에 없으면 반대쪽에서 빌린다.
  - 모든 행을 엔진 1:1 배틀로 재현해 규칙 정답과 대조한다(빗나감은 시드 재시도). 행동 불가·조기 종료 시나리오는 버린다.

  | 군 | 내용 |
  |---|---|
  | A01 | 날씨·벽 |
  | A02 | Sleep Talk·Snore·Rest |
  | A03 | Substitute |
  | A04 | 압정·Magic Bounce |
  | A05 | Fake Out·First Impression |
  | A06 | Future Sight |
  | A07 | Encore |
  | A08 | Sucker Punch·Thunderclap·Counter·Mirror Coat(상대 행동 가정) |
  | A09 | 타입 무효 |
  | A10 | 상태이상기 |
  | A11 | 특성(흡수·반사·차단·Prankster·우선도) |
  | A12 | 선택 가능 여부 |

- **B 실제 상태**(EX-071, `v2-all` 상태 텍스트 그대로):
  - 내 기술 선택지 중 공개 정보로 결과가 정해지는 것만 쓴다.
  - 비-works 라벨은 각 상한 1/4, works는 비-works 합의 2배까지(상한 15,000)다.
  - held-out은 EX-071 validation과 test 상태에서 각 최대 1,000행이다.
- **C 설명**(기술 685, 도구 223, 특성 310):
  - 정방향: 4지선다, 정답 문자 무작위
  - 역방향: 설명이 같은 항목은 뺀다.
  - 항목당 정방향·역방향 각 8개다. EX-071 train에서 쓰인 항목은 8개씩 더한다.
  - held-out은 같은 항목을 다른 시드로 묻는다(기억 재현 측정).
- **길이**: 전체 1,024, head 512, 선택지 48을 넘는 행은 생성 시 버리고 집계한다.
- **생성 결과**(2026-10-23, 학습 전, CPU 105초, 봉인):
  - train 64,396행:
    - A 23,572: 군별 1,750~2,000
    - B 15,000: works 7,401, fails 3,750, immune 3,750, absorbed 99
    - C 25,824: 기술 15,320, 특성 6,120, 도구 4,384
  - held-out: A 2,365, B 1,245, C 2,321
  - 길이 초과 0
  - 엔진 대조 26,400건: 불일치 0, 시나리오 오류 463(버림, `oracle-errors.jsonl`)
  - 개발 중 첫 전체 생성은 불일치 20건으로 멈췄다. 원인(Protean 타입 변화, 면역 상태이상 부여, Infiltrator, Future Sight 상대의 Mirror Coat)을 고친 뒤 다시 생성했고, 기록은 `diagnostics/data-v1`에 보존한다.
  - A 라벨 분포: works 10,263, fails 8,899, immune 1,817, reflected 491, absorbed 252, no 1,137, yes 713
- **결합**: 학습 시 `v2-all` train 뒤에 테라 지식 train, 효과 지식 train을 차례로 더한다(`training.EX126.extra_train`).
  - 보정 400행은 모방 행에서만 뗀다.
  - validation과 선택은 `v2-all` validation 512다.

### 학습 설정

- EX-121/EX-124와 같다(3 epoch, soft-CE, 선택지 순서 섞기, lr, seed 0, `max_len=1024`, `head_max_len=512`).
- 학습 행은 약 251,550(모방 130,011 + 테라 57,143 + 효과 64,396)이다.
- 상한은 최초 GPU 시계부터 18시간이다(EX-124 속도 기준 epoch당 약 4.2시간).

## 환경 및 출처

- branch, commit: `research/model-training` `feda62f7…`. 소스 identity는 run `source/`에 둔다.
- 장치: GPU2(`GPU-c79ce3fd-81e7-454b-75ce-e63fad63baa4`, `gpu2.lock`, UUID와 유휴 확인)
- 실행기: `scripts/laya-imitation effects {data,train,evaluate}`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-126`

## 격리 및 오염 통제

- B 지식 행은 train 상태에서만 학습 행을 만든다. validation·test 상태로 만든 행은 평가 전용이다.
- 잠긴 test(`v2-all` test 1,024)는 학습과 선택에 쓰지 않는다. 실패 선택지 판정은 test 상태의 공개 정보만 쓴다.
- 웹 문서 텍스트는 쓰지 않는다.
- **viewer**: 비배틀이므로 해당 없다.
- **재개**: 지원하지 않는다. 자동 재실행은 없다.

## 절차

1. 효과 원자료 고정, 규칙표, 생성기, 엔진 오라클, 단위 검사
2. 지식 자료 생성, 엔진 대조, 감사, 봉인(완료)
3. GPU2 사전검사 → 본학습 → 선택과 보정
4. 효과 held-out 평가(initial, EX-124 selected, EX-126 selected), 테라 held-out(EX-126 selected)
5. 잠긴 test(EX-126 selected 1회) → EX-124 쌍비교와 실패 선택지 지표
6. 보고, 봉인, GPU2 반환

## 승인·무효화·중단 조건

- **승인**: 1~6 완료와 봉인
- **무효**: 엔진 대조 불일치, 자료 해시 불일치, 재로딩 불일치
- **중단**: 18시간 상한, GPU 오류

## 테스트·평가 도구 결함 복구

C-018과 EX-118 절차를 적용한다. 원본을 `diagnostics/<단계>-vN`에 보존하고, 수정과 독립 검증 뒤 해당 단계만 1회 재시도한다. 판정 기준은 바꾸지 않는다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 지식 자료 | `/mnt/.../datasets/generated/laya-effect-knowledge/v1` | `checksums.sha256` | Produced(봉인) |
| 학습 run | `/mnt/.../runs/model-training/EX-126` | `checksums.sha256` | Produced(봉인) |

## 결과

- 2026-10-23 — GPU2 사전검사 통과(loss 2.160 → 1.979, 재로딩 logit 차이 0.0, 최대 7.79 GiB). 본학습 시작.
- 학습 11.8시간, 학습 행 251,550. validation NLL은 epoch 1 1.5798, epoch 2 1.4889, epoch 3 1.4942로 epoch 2를 선택했다.
- **판정: 개선 없음.**
  - 실패 선택지 확률 합 차이 F는 +0.0011, 95% [−0.0059, +0.0078]이다. EX-124 5.63%, EX-126 5.74%로 상한이 0보다 크다.
  - NLL 차이 N은 −0.0011, 95% [−0.0256, +0.0235]로 상한 +0.0235가 비열등 여유 +0.02를 넘는다. 그래서 문구가 "실패 선택지 차이 불분명, 일반 재현 유지"가 아니라 "개선 없음"이다.
- 잠긴 test: EX-126 NLL 1.4495, 일치율 46.88%, ECE 0.0408. EX-124는 1.4506, 47.85%, 0.0365이다.
- 실패 선택지가 1순위인 행: EX-124 6, EX-126 8(대상 234행)
- qualification 충족: 효과 held-out 정답률이 initial보다 높다.
  - A: 44.2% → 96.0%
  - B: 18.2% → 95.8%
  - C: 28.7% → 98.6%
  - EX-124는 A 48.5%, B 51.5%, C 26.7%였다.
- 테라 held-out 망각 없음: A 96.9% → 97.1%, B 95.8% → 96.1%
- 산출물: `runs/model-training/EX-126/report.md`, `evaluation/report.json`(봉인)

## 분석 및 한계

- 지식 행을 더하면 학습 행 수도 함께 늘어난다. 지식 효과와 학습량 효과를 분리하지 않는다.
- 주 지표는 공개 정보로 결과가 정해지는 선택지만 센다. 상대 미공개 특성에 달린 실패(예: 미확인 Volt Absorb)는 포함하지 않는다.
- 사람도 실패 선택지를 고른다(8/234). 사람 모방 목표와 실패 회피가 부분적으로 충돌할 수 있다.
- A 카드는 실제 상태보다 짧다(팀·속도 줄 없음).

## 결론 및 후속 작업

- 효과 지식 자체는 거의 완전히 익혔다(held-out 96~99%). 하지만 사람 선택을 재현하는 데서 실패 선택지 확률은 줄지 않았다.
- 지식 질문과 행동 선택 질문이 같은 모델 안에서 연결되지 않은 것으로 보인다. EX-124의 테라 결과와 같은 양상이다.
- 배틀에서의 실패율 변화는 EX-127에서 본다.
- 후속 후보(별도 승인 필요):
  - 렌더러가 선택지에 실패 사실을 직접 표시
  - 선택 질문 형식의 지식 행(행동 선택지 위에서 실패 선택지를 낮추는 라벨)
