# EX-157 — laya 렌더러 v9(v7 + 상대 노력치 보정·최악 피해 표시) 학습(GPU3)

- 상태: Completed
- 생성일: 2026-11-02
- 책임자: Claude Code
- 관련 exec plan: [EP-225](../plans/EP-225-laya-opponent-threat-v9.md)
- 관련 decision: [D-202](../decisions/D-202-laya-opponent-threat-v9.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-149](EX-149-laya-v7-opponent-sets-training.md) selected
- 기준 연구선: `research/model-training`

## 질문 및 목적

상대 가정 세트의 노력치를 도구·공개 기술과 맞추고, 미공개 기술·도구·테라까지 넣은 최악 피해를 교체 선택지와 현재 포켓몬에 보여 주면, 사람 선택 재현과 위험한 교체에 주는 확률이 어떻게 바뀌는가? 배틀 효과는 [EX-158](EX-158-laya-v7t-v9t-battle256.md)이 본다.

## 가설 또는 qualification 목표

- **qualification**:
  - validation 512 사전 측정에서 길이 초과 0.5% 이하, `v9-all` 제외 0.5% 이하
  - validation 512에서 오프라인 렌더와 서빙 렌더가 같다(`parity`, 계산기 재계산 포함), `generator-source`가 현재 파일과 같다
  - 단위 검사(`integration/laya_threat/tests`) 통과, 사전검사 loss 감소, 재로딩 logit 일치
- **판정 없음(보고 전용)**: D-191.
- **보고 지표**: 잠긴 test 1,024행에서 EX-157 − EX-149 같은 행 차이(replay 클러스터 bootstrap 95%, 10,000회, 시드 20261052)
  - 전체 NLL·일치율, 교체 행, 변화 묶음(노력치 보정·위협 표시·둘 다·없음), 사람이 고른 선택지에 risk 표시가 있는지
  - 최악 100% 이상 risk 교체 선택지가 있는 행: 그 선택지들의 확률 합과 argmax 수(EX-157 대 EX-149), 사람이 고른 수
  - 테라 지식 held-out A/B 정답률
  - 자료 표시 집계(분할별): 노력치 보정 행, 보정만으로 글이 바뀐 행, threat 줄, risk 선택지·행

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| EX-157 selected | EX-149와 같다: 시작 모델 `e929ae5c`, 설정, EX-071 분할, 테라 지식 train 행, `max_len=1024`, head 512, 선택지당 48, v7 모듈 전부 | 렌더러 v7 → v9(`spreads.py` 노력치 보정, `threat.py` 최악 피해 `risk`·`opp threat`) | `runs/model-training/EX-157/checkpoints/selected/` |

### 렌더러 v9 (`integration/laya_threat/render_v9.py`)

규칙의 원문은 [D-202](../decisions/D-202-laya-opponent-threat-v9.md#결정)와 모듈 docstring이다. 사전 측정(validation 512): 한도 내 511(v7 511), 노력치 보정 행 24, 보정만으로 글이 바뀐 행 18, threat 줄 377, risk 선택지 1,143(행 380), 사람이 risk 선택지를 고른 행 106.

## 실행

- 실행기: `python -m integration.laya_threat.cli {measure,data,parity,train,evaluate}`(laya venv), 연결 실행 `scripts/laya-imitation-ep225 gpu3`
- GPU3(`GPU-fd337c1e…`). 학습 시간 상한 없음. 중단: 제외 비율 > 0.005, GPU 오류, parity 불일치
- 자동 재실행 없음.

## 결과

- 2026-11-02 자료: `v9-all` train 129,964 · validation 511 · test 1,018(제외 454행, 0.344%, EX-149와 같은 수). parity 511행 불일치 0.
- 2026-11-02 학습 08:54Z~20:19Z(GPU3, 40,960초, 최대 7.9 GiB). validation 원 NLL 2.1191 → 1.5248 / **1.4635** / 1.4730(epoch 1/2/3), 선택 epoch 2(온도 1.2748, 보정 NLL 1.4503·일치율 45.6%). 보고 `runs/model-training/EX-157/report.md`.
- 잠긴 test 1,018행(EX-157 − EX-149, 같은 행, replay 클러스터 95%):

| 구분 | n | NLL 차이 | 95% | 일치율 차이 |
|---|---:|---:|---|---:|
| 전체 | 1018 | −0.0223 (1.4332 → 1.4109) | [−0.0506, +0.0052] | +1.87%p (45.78 → 47.64%) |
| 교체 행 | 364 | +0.0380 | [−0.0096, +0.0861] | −2.47%p |
| 자발 교체 라벨 | 202 | +0.1055 | [+0.0319, +0.1797] | −6.93%p |
| 강제 교체 | 116 | −0.0824 | [−0.1369, −0.0239] | +7.76%p |
| 기술 라벨 | 623 | −0.0553 | [−0.0875, −0.0237] | +4.98%p |
| 사람이 risk 선택지를 고른 행 | 209 | +0.1033 | [+0.0432, +0.1638] | −3.83%p |
| 사람이 risk 없는 선택지를 고른 행 | 809 | −0.0547 | [−0.0848, −0.0250] | +3.34%p |

- 최악 100% 이상 risk 교체 선택지가 있는 test 443행: 그 선택지 확률 합 0.1798 → 0.1542(차이 95% [−0.0324, −0.0188]), argmax 63 → 47행. 사람은 63행에서 그런 선택지를 골랐다.
- 테라 지식 held-out: A 전체 96.9 → 93.1%(A3 93.7 → 70.0%, A5 84.7 → 81.7%), B 전체 95.9 → 95.6%. ECE 0.0302 → 0.0398.

## 결론 및 후속 작업

- 표시는 의도한 방향으로 작동했다. 최악 피해가 큰 교체에 주는 확률과 argmax가 줄었고, 기술·강제 교체 행 재현은 좋아졌다.
- 대가도 있다. 사람이 위험한 교체를 감수한 행(자발 교체, risk 선택지)은 재현이 나빠졌다. 위험 표시를 "피하라"로 배운 경향이다. 테라 지식 A3도 떨어졌다.
- 배틀 결과는 [EX-158](EX-158-laya-v7t-v9t-battle256.md)에 있다. 사용자가 본 장면(Specs Kyurem·썰렁개그)은 사람 대전으로 직접 확인해야 한다. v9t 서빙은 `integration.laya_threat.serve`다.
