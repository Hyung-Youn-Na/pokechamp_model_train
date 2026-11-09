# EX-165 — laya 상대 시점 예측(세트 표본) 장면 검증: 사람 test 4경기, v8lt(CPU)

- 상태: Completed
- 생성일: 2026-11-03
- 책임자: Claude Code
- 관련 exec plan: [EP-229](../plans/EP-229-laya-opponent-model-search.md)
- 관련 decision: [D-206](../decisions/D-206-laya-opponent-model-search.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

봇의 공개 기록만으로 사람 쪽 결정 입력을 다시 만들고 세트를 표본으로 채웠을 때, laya가 사람의 실제 수를 얼마나 예측하는가? 특히 사람이 교체를 읽은 장면에서 그 읽기 기술에 확률을 주는가?

## 가설 또는 qualification 목표

탐색적이다. 판정은 없다. 보고하는 지표는 다음과 같다.
- 사람 실제 수의 평균 음의 로그우도(NLL)와 1순위 일치율: 진짜 세트(oracle)와 표본 8개 평균을 비교한다.
- 장면 9개: 읽기 8개와 빗나간 읽기 1개(265 T25). 실제 수 확률, 표본별 확률, 상위 3개 예측을 본다.

## 조건 및 변수

| Condition | 입력 | 변경 | 자원 |
|---|---|---|---|
| oracle | 봇 공개 기록 + 사람의 진짜 세트 | — | CPU |
| sampled | 봇 공개 기록 + usage 표본 세트 8개(시드: 경기·턴 해시) | 세트 | CPU |

- 경기: 244·255·265(11/02 KST, 상대 봇 v7t)와 276(11/03 KST, v9t). 사람은 p1 `test`다.
- 대상 결정: 사람이 그 턴에 기술을 쓰거나 스스로 교체한 턴 중, 봇 쪽 일반 턴 행동 입력이 있는 턴
- 정책: EX-155 selected(v8lt), v8l 렌더러, CPU 추론

## 실행

- `python -m integration.laya_search.scenes`(laya venv), 출력 `runs/model-training/EX-165/result.json`

## 결과

2026-11-03 08:24Z~08:33Z, CPU 538초. 오류 0. 결과는 `runs/model-training/EX-165/result.json`, 로그는 `run.log`이다.

- **전체 99결정**(사람이 기술을 쓰거나 스스로 교체한 턴):

| 세트 | 실제 수 NLL | 1순위 일치 | 실제 수 평균 확률 |
|---|---:|---:|---:|
| 진짜 세트(oracle) | 1.796 | 33.3% | 0.254 |
| 표본 8개 평균 | 2.018 | 31.3% | 0.222 |

- **읽기 장면**(실제 수의 확률, 진짜 세트 / 표본 평균):

| 장면 | 실제 수 | oracle | 표본 | 표본 1순위 |
|---|---|---:|---:|---|
| 244 T2 | Ice Spinner → Zapdos | 0.076 | 0.052 | Stealth Rock 0.235 |
| 244 T34 | Ice Spinner → Great Tusk | 0.028 | 0.024 | Headlong Rush 0.296 |
| 244 T36 | Ice Spinner → Zapdos | 0.026 | 0.019 | Headlong Rush 0.520 |
| 244 T39 | Freeze-Dry → Slowking | 0.206 | 0.291 | Freeze-Dry 0.291 |
| 255 T5 | Ice Spinner → Garchomp | 0.162 | 0.090 | Headlong Rush 0.269 |
| 255 T15 | Earth Power → Tyranitar | 0.047 | 0.029 | Ice Beam 0.712 |
| 265 T21 | Ice Spinner → Gliscor | 0.235 | 0.234 | Headlong Rush 0.285 |
| 265 T25(빗나감) | Ice Spinner, 교체 없음 | 0.042 | 0.033 | Headlong Rush 0.470 |
| 276 T9 | U-turn → Great Tusk | 0.345 | 0.248 | Pyro Ball 0.401 |

- 표본 사이 차이는 미공개 기술에서 생긴다. 예를 들어 244 T2에서 Ice Spinner가 아직 공개되지 않아 표본 8개 중 2개에는 그 기술이 없었다(확률 0).

## 결론 및 후속 작업

- **시점 재구성과 표본 채우기는 동작한다.** 표본으로 채워도 예측 손실은 작다(NLL +0.22, 1순위 −2%p).
- **laya를 상대 모델로 그대로 쓰면 읽기를 거의 예측하지 못한다.**
  - 읽기 장면 9개 중 5개에서 읽기 기술 확률이 0.05 이하였다.
  - 244 T36은 같은 경기에서 두 번 읽힌 뒤인데도 0.02다. T34는 4턴 기록 창 안에 있었는데도 그렇다.
  - 모방 모델은 평균적인 사람(읽기가 드묾)을 예측하고, 이 사람이 읽는 성향을 경기 중에 반영하지 못한다. EX-071 집계(읽힌 뒤 바뀐 행 1,147)와도 맞는다.
- **함의**: 이 예측으로 한 턴 탐색을 하면 교체를 피할 이유가 거의 생기지 않는다(읽기 확률 2~5%). 2단계의 상대 모델에는 "읽는 상대" 성분이 필요하다.
  - 제안: 사람다운 예측(laya)과, 내 정책을 보고 최선으로 받아치는 상대(best response)를 섞는다. 섞는 비율은 그 상대가 실제로 읽었는지를 보고 경기 중에 갱신한다.
  - 2단계는 사용자 확인 뒤 등록한다.
