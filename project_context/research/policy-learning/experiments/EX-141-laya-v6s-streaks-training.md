# EX-141 — laya 렌더러 v6s(같은 기술 반복 표시) + 테라 지식 학습(GPU0)

- 상태: Completed
- 생성일: 2026-10-29
- 책임자: Claude Code
- 관련 exec plan: [EP-221](../plans/EP-221-laya-past-turn-input-v6.md)
- 관련 decision: [D-198](../decisions/D-198-laya-past-turn-input-v6.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-136](EX-136-laya-v5-tera-training.md) selected(v5 + 테라, 변수 하나 차이)
- 기준 연구선: `research/model-training`

## 질문 및 목적

활성 포켓몬이 직전 몇 턴 연속 같은 기술을 썼는지와 그동안 상대 HP를 표시한 입력(v6s)이, 사람 선택 재현과 같은 기술 반복을 어떻게 바꾸는가? 배틀 효과는 [EX-143](EX-143-laya-v5t-v6st-battle256.md)이 본다.

## 가설 또는 qualification 목표

- **qualification**:
  - `v6s-all` 길이 초과 제외가 0.5% 이하다.
  - validation 512에서 오프라인 렌더와 서빙 렌더가 같다(`v6 parity --variant v6s`).
  - 사전검사 loss가 줄고, 저장 후 재로딩 logit이 같다.
- **판정 없음(보고 전용)**: D-191에 따라 이 결과는 EX-143 실행 여부를 정하지 않는다.
- **보고 지표**: 잠긴 test 1,024행에서 EX-141 − EX-136 같은 행 차이. 구간은 replay 클러스터 bootstrap 95%(10,000회, 시드 20261036)다.
  - 전체 NLL과 일치율, 교체 행
  - 내 활성 반복 표시별(`none`, `x2`, `x3`, `x4+`)
  - **같은 기술 반복 확률**: 내 활성이 직전 2턴 이상 같은 기술을 쓴 행에서 그 기술(일반·테라)의 확률 합 평균과 1위 횟수. 사람이 다른 수를 고른 행과 또 쓴 행을 나눈다.
  - 테라 지식 held-out A/B 정답률, 사람 테라 행의 테라 확률 합
- EX-136 쪽 값은 저장된 test 예측을 쓴다. 다시 추론하지 않는다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| EX-141 selected | EX-136과 같다: 시작 모델 `e929ae5c`, 설정, EX-071 분할, 테라 지식 train 57,143행, `max_len=1024`, head 512, v5 모듈 전부, 사실값(`laya-compact-features/v5`) | 렌더러 v5 → v6s(`streaks` 모듈 추가) | `runs/model-training/EX-141/checkpoints/selected/` |

### 렌더러 v6s (`compact_v6.py`)

- ME·OPP 줄 끝에 ` | streak <기술 id> x<n>`(n ≥ 2)을 붙인다. 직전 완료 턴부터 거꾸로, 그 쪽 활성 포켓몬의 같은 기술 사용이 이어지는 턴 수다.
  - 행동 불가(`cant`), 다른 기술, 교체 등장에서 끊는다. 호출된 기술(`[from]`)은 세지 않는다.
  - 연속이 4턴 기록 창의 시작(T−4)까지 이어지면 `+`를 붙인다.
- 이어서 그 턴들이 끝날 때 상대 쪽 활성의 HP를 `(opp hp a>b>…)`(OPP 줄은 `my hp`)로 붙인다. 그 사이 상대가 교체했거나 HP를 모르면 생략한다.
- 모듈이 없으면 v5와 바이트 단위로 같다.

### 자료 (`data_v6.py`)

- `laya-compact-imitation/v6s-all`: EX-071 `prepared` + `laya-item-state/v1`, 사실값은 v5 정보 캐시를 그대로 쓴다(v5 입력 해시로 대조). 한도 1,024 / 512 / 48, 초과 행은 `exclusions.jsonl`.
- 학습 시 테라 지식 train 행을 더한다. 보정 400행은 모방 행에서만 뗀다.

### 학습 설정

- EX-136과 같다: 3 epoch, soft-CE, 선택지 순서 섞기, lr, seed 0, `max_len=1024`, `head_max_len=512`
- 선택은 validation 원 NLL 최소 epoch다.
- **시간 상한 없음**(사용자 지시 2026-10-29). EX-136은 같은 GPU0에서 약 9.4시간 걸렸다.

## 환경 및 출처

- 장치: GPU0(`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`, `gpu0.lock`, UUID와 유휴 확인)
- 실행기: `scripts/laya-imitation v6 {measure,data,parity,train,evaluate} --variant v6s`, 연결 실행 `scripts/laya-imitation-ep221`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-141`

## 격리 및 오염 통제

- 반복 표시는 공개 기록(4턴 창)만 쓴다. 사람 라벨, 승패, test를 보지 않는다.
- 잠긴 test는 학습과 선택에 쓰지 않는다.
- **viewer**: 비배틀이므로 해당 없다.
- **재개**: 지원하지 않는다. 자동 재실행은 없다.

## 절차

1. 사전 측정과 형식 동결, `v6s-all` 자료, 제외 비율, 봉인
2. `v6 parity --variant v6s`(validation 512)
3. GPU0 사전검사 → 본학습 → 선택과 보정
4. 테라 지식 held-out(1회), 잠긴 test(1회) → EX-136 쌍비교 → 보고, 봉인

## 승인·무효화·중단 조건

- **승인**: 1~4 완료와 봉인
- **무효**: parity 불일치, 자료 해시 불일치, 재로딩 불일치
- **중단**: 제외 비율 > 0.005, GPU 오류

## 테스트·평가 도구 결함 복구

C-018과 EX-118 절차를 적용한다. 원본을 `diagnostics/<단계>-vN`에 보존하고, 수정과 독립 검증 뒤 해당 단계만 1회 재시도한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| v6s 자료 | `/mnt/.../datasets/generated/laya-compact-imitation/v6s-all` | `checksums.sha256` | 예정 |
| 학습 run | `/mnt/.../runs/model-training/EX-141` | `checksums.sha256`, `report.md` | 예정 |

## 결과

- 학습: 3 epoch 33,812초(GPU0, 시간 상한 없음). validation 원 NLL 1.5993 → 1.5264 → 1.5394, 선택 epoch 2(EX-136과 같음). 최대 메모리 7.8GiB.
- 잠긴 test(1,023행): NLL 1.4286(EX-136 1.4358), 일치율 48.29%(46.14%), ECE 0.0281(0.0403).
  - 같은 행 차이 EX-141 − EX-136: NLL −0.0073 [−0.0286, +0.0140], 일치율 +2.15%p. NLL 구간이 0을 포함한다.
  - 강제 교체 행(116)만 NLL −0.0504 [−0.0964, −0.0061]로 구간이 0 아래다.
- **같은 기술 반복 확률**(내 활성이 직전 2턴 이상 같은 기술을 쓴 test 93행):
  - 사람이 다른 수를 고른 58행: 반복 확률 EX-136 0.288 → EX-141 0.306, 반복 1위 18 → 24
  - 사람이 또 쓴 35행: 0.670 → 0.678, 1위 29 → 31
  - 반복 표시가 반복을 줄이지 않았다. 오히려 조금 늘었다(행 수가 작아 구간은 내지 않았다).
- 테라 지식 held-out: A 96.4% → 95.0%, B 95.7% → 95.8%.
- 보고: `runs/model-training/EX-141/report.md`

## 분석 및 한계

- 4턴 창 밖의 연속은 `x4+`로만 보인다.
- 반복 표시는 "같은 기술"만 센다. 비슷한 효과의 다른 기술을 번갈아 쓰는 루프는 잡지 않는다.
- 단일 시드 학습이다.

## 결론 및 후속 작업

- 사람 선택 재현은 EX-136과 구별되지 않는다(일치율은 +2.15%p).
- 반복 표시만으로는 같은 기술을 또 고르는 확률이 줄지 않았다. 사람 자료에서도 반복 표시 행의 38%(35/93)는 같은 기술을 다시 쓰므로, 모델이 표시를 "계속 쓰는 상황" 신호로 배웠을 수 있다.
- 배틀은 [EX-143](EX-143-laya-v5t-v6st-battle256.md).
