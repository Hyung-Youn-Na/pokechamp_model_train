# EX-192 — laya v12 처음부터 학습(GPU 4장 DDP, 3 epoch, 약 24시간)

- 상태: Completed
- 생성일: 2026-11-20
- 책임자: Claude Code
- 관련 exec plan: [EP-237](../plans/EP-237-laya-observed-public-info-input.md)
- 비교 대상: [EX-167](EX-167-laya-v10-ladder-training.md)(v10rt, 같은 시작·설정), [EX-172](EX-172-laya-v11rtc-training.md)(v11rtc), [EX-178](EX-178-laya-fp1-training.md)(fp1, 같은 경로)
- 기준 연구선: `research/model-training`

## 질문 및 목적

렌더러 v12(foul-play의 경기 중 추론 반영) 입력으로 처음부터 학습하면 사람 선택 재현이 v10rt·v11rtc와 비교해 어떻게 되는가? 배틀 효과는 [EX-193](EX-193-laya-v12-vs-foulplay-blim128.md)이 본다. 사용자 지시(2026-11-20, 이어 학습·같은 방식 1 epoch·처음부터 3 epoch 비교 뒤 "3번 방식으로 해주세요").

## 조건

| 항목 | 조건 |
|---|---|
| 시작 모델 | `laya-typed-decisions@e929ae5c`(EX-167·EX-178과 같음) |
| 자료 | `v12-ladder-merged`([EX-191](EX-191-laya-v12-data.md), v11-ladder-merged와 같은 행·라벨) + 테라 지식 57,143행(EX-167과 같음). EX-172의 가중·교정 행은 쓰지 않는다(EX-167 조건) |
| 학습 | `laya_ladder.train_ddp` 그대로: 3 epoch, soft-CE, 선택지 섞기, lr(encoder 2.5e-5 · head 1e-4 → 1e-6 cosine), seed 0, 전체 배치 64(장당 micro 8 × 누적 2 × 4장), 2,048 / head 768 / 선택지 64, `act_head` 고정 |
| 선택 | epoch별 validation NLL 최저, 온도는 EX-167 방식으로 다시 맞춘다 |
| 자원 | GPU 0~3, checkpointing 0, `scripts/mem-guard 100` |

## 실행

- 실행기: `scripts/laya-v12-ep237 train`(EX-191 자료 → `integration.laya_v12.train_v12` check → measure → train). EX-191이 끝나면 자동으로 시작한다.
- qualification: DDP 검사 통과(loss 차이 < 1e-4, gradient 상대 차이 < 1e-3, 다시 읽은 logit 차이 < 1e-3).
- 중단: GPU 오류, DDP 검사 불일치, loss NaN. 자동 재실행 없음.
- 평가(학습 뒤): 잠긴 test(v12로 다시 렌더한 대회·래더 test, EX-167과 같은 sample id)를 EX-167·EX-172와 같은 행으로 비교한다.

## 결과

- 실행: check 2026-11-20T08:59Z 통과(loss 차이 0, grad 상대 차이 1.5e-6) → measure → train 09:05Z~2026-11-21T08:29Z(약 23.4시간, GPU 0~3, 최고 23.1 GiB). split은 EX-167과 같다(train 1,298,928 = 모방 1,241,785 + 테라 지식 57,143). 설정 파일은 자료 경로만 다르다.
- validation NLL(원 logit): epoch 1 1.342 → 2 1.285 → 3 1.334. 최저인 epoch 2를 골랐고 온도는 1.011이다. EX-167은 epoch 3에서 1.368로 최저였다. v12는 더 낮게 내려가지만 더 일찍 과적합한다.
- 평가: `python -m integration.laya_v12.evaluation_v12 score` → `report`. 보고서는 `runs/model-training/EX-192/evaluation/report.md`에 있다.
- 잠긴 test(같은 sample id, replay 클러스터 95%, 시드 20261192):

| test | 기준 | 기준 NLL | EX-192 NLL | 차이 [95%] | 일치율 |
|---|---|---:|---:|---|---|
| 대회 1,024 | EX-167 | 1.3305 | 1.2531 | -0.0775 [-0.107, -0.048] | 49.6% → 53.1% |
| 대회 1,024 | EX-172 | 1.3444 | 1.2531 | -0.0914 [-0.123, -0.060] | 49.3% → 53.1% |
| 래더 1,024 | EX-167 | 1.3284 | 1.2304 | -0.0980 [-0.136, -0.060] | 53.1% → 55.5% |
| 래더 1,024 | EX-172 | 1.3448 | 1.2304 | -0.1144 [-0.151, -0.078] | 51.3% → 55.5% |

- 개선은 기술 라벨과 turn_action에서 컸다. 래더 기술 라벨은 EX-167 대비 -0.133이다. 교체 라벨은 신뢰구간이 0을 포함한다. 래더 pivot_switch(34행)는 나빠졌다(+0.183 [+0.020, +0.346]).
- 입력이 v11과 같은 행에서도 EX-172(v11 입력) 대비 나아졌다. 대회 43행은 -0.229 [-0.340, -0.098]이고, 래더 50행은 +0.030으로 구간이 0을 포함한다. 대회 쪽은 입력 정보만이 아니라 학습 결과 전반도 달라졌다는 뜻이다(EX-172는 v10rt에서 이어 학습했다).
- 테라 지식 held-out: A 전체 79.3% → 91.4%(A4 37.3% → 98.3%), B 전체 86.9% → 95.0%. 지식 행과 설정이 EX-167과 같은데도 크게 올랐다. 원인은 확인하지 않았다.

## 결론 및 후속 작업

- 사람 선택 재현은 v10rt·v11rtc보다 분명히 나았다(두 test, 두 기준 모두 95% 구간이 0 아래). 승률 판단은 EX-193이 한다(D-191).
- 해석 전 확인할 것:
  1. ~~미래 정보 누수 점검~~ 2026-11-21에 마쳤다. test 600행에서 누수를 찾지 못했다(EP-237 진행 기록).
  2. 테라 지식 정답률이 오른 원인.
- 다음: EX-193(v12 서빙 → mock → foul-play Blim 128경기).
