# EP-225 — laya 상대 노력치 보정·최악 피해 표시 렌더러 v9 학습·배틀(GPU3)

- 상태: Completed
- 생성일: 2026-11-02
- 책임자: Claude Code
- 승인 근거·범위: 사용자 지시(2026-11-02, "GPU3번을 이용해 해당 문제를 해결할 수 있는 렌더러 학습 계획을 세우고 자동 진행")와 [D-202](../decisions/D-202-laya-opponent-threat-v9.md). 오프라인 결과로 배틀을 거르지 않는다([D-191](../decisions/D-191-no-offline-battle-gate.md)).
- 관련 contract / decision / experiment: [C-055](../CONTRACTS.md#c-055-imitation), [EX-157](../experiments/EX-157-laya-v9-opponent-threat-training.md), [EX-158](../experiments/EX-158-laya-v7t-v9t-battle256.md), [EX-149](../experiments/EX-149-laya-v7-opponent-sets-training.md), [EX-150](../experiments/EX-150-laya-v6st-v7t-battle256.md), [EP-224](EP-224-laya-engine-judge-v8.md)
- 기준 연구선: `research/model-training`
- 작업 checkout과 interpreter/launcher: `/workspace`(미커밋: EP-224 세션의 laya_imitation 변경 포함, 이 계획은 `integration/laya_threat/`만 새로 만든다), laya venv(`/workspace/.tools/laya-0.4.13/worktrees/pokemon-training/.venv`), `pokechamp/.venv`, node. 연결 실행 `scripts/laya-imitation-ep225 gpu3`
- 새 산출물과 검증 출력 위치:
  - `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/laya-compact-imitation/v9-all`
  - `.../runs/model-training/EX-157`, `EX-158`, 연결 실행 로그 `.../runs/model-training/EP-225-gpu3.log`
  - 뷰어 `/workspace/exports/battle_viewers/ex158/`
- 참조 원자료(읽기 전용): EX-071 `prepared/`, `laya-item-state/v1`, `laya-compact-features/v5`(v7 비교용), `usage_sets_v3.json`, EX-149 산출물, laya-v7test 사람 대전 기록(`/workspace/.artifacts/laya-v7test/games/`)

## 목표와 맥락

사람 대전에서 Choice Specs Kyurem·썰렁개그 연계의 피해를 모델이 낮게 보고 반감 교체로 손해를 본 원인(가정 세트 노력치 모순, 미공개 기술·도구·테라 미반영)을 입력에서 고치고, 그 입력으로 학습한 v9가 v7보다 성적이 떨어지지 않는지 본다(D-202).

## 범위와 불변 조건

- **포함**: `integration/laya_threat/` 새 코드와 단위 검사, `scripts/laya-imitation-ep225`, 기록
- **보존**:
  - `integration/laya_imitation`, 파서, `scripts/laya-imitation`, 기존 자료·봉인을 바꾸지 않는다. laya_imitation 함수는 import해서 쓰고, 서빙·배틀용 확장은 이 계획의 프로세스 안에서만 한다(`serve.register`, `battle_v9.register`).
  - EP-224 레인(GPU1·GPU2, 8108·8109)과 산출물은 건드리지 않는다.
- **자원**: GPU3(`GPU-fd337c1e-b087-b26d-4dc0-a195c2b3a8d6`)·포트 8106만 쓴다. 외부 프로세스 종료와 장치 reset은 금지한다.
- **배틀 표시**: prepare 직전 `.pokechamp-data/battle-window/EX-158`을 만들고 export 뒤 지운다. 실행 중인 bash 연결 스크립트는 고치지 않는다.
- **외부 호출**: 없다.

## 완료 기준

- [x] D-202, EP-225, EX-157·158 등록, catalog build/check
- [x] v9 렌더러·단위 검사, 사전 측정(초과 1/512, v7과 같음)
- [x] `v9-all` 생성 → parity → EX-158 mock(CPU)
- [x] EX-157 학습 → 평가
- [x] EX-158 배틀·보고·뷰어
- [x] 결과를 EX 문서, STATUS, catalog에 기록

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| Kyurem 장면 재현 | `tests/test_threat.py`(사람 대전 2결정, 노력치 보정 규칙) | 단위 검사 | 6 통과: Kingambit `hit` 45~53% → 60~71%(실전 60%), 막 들어온 Kyurem에 Iron Crown `risk`, v7 렌더 비누출, 토큰 한도 |
| 길이 | validation 512 사전 측정 | `EX-157/diagnostics/measure/` | 511/512(v7 511/512), 선택지 최대 48 |
| 노력치 보정 범위 | val+test 행에서 바뀐 상대 세트 | 이 문서 진행 기록 | Kyurem(Specs·공개 특수기), Hoopa-U Specs, 공개 기술과 맞지 않는 Lando-T·Dragapult·Blaziken·Araquanid만 |
| 오프라인·서빙 일치 | `parity` validation 512행 + generator-source 해시 | `EX-157/diagnostics/parity.json` | 511행 불일치 0, generator 일치 |
| 배틀 경로 | mock(초기 체크포인트, CPU, 2경기) | `EX-158/mock/result.json` | 2/2 completed·감사 통과, 서빙 identity render `laya-compact-v9[…,threat]` |

## 진행

- 2026-11-02 08:35Z — 사용자 지시로 시작. nvidia-smi: GPU1·2 EP-224 학습 중, GPU0·3 비어 있음. battle-window 표시 파일 없음. laya-v7test 4판에서 Kyurem 장면을 재렌더링해 원인 확인(D-202 맥락).
- 2026-11-02 — `integration/laya_threat/` 작성. 첫 사전 측정은 한도 내 442/512, 노력치 보정 행 177이었다. 렌더러가 laya 토크나이저로 한도를 지키게 하고(511/512), 노력치 보정을 명백한 모순으로 좁혔다(usage 다수결 제외, 보조·고정 피해 기술 제외, 24행). 단위 검사 6 통과.

- 2026-11-02 — `v9-all` 생성(135초): train 129,964 · validation 511 · test 1,018, 제외 454행(0.344%, v7과 같은 행 수). train 표시: 노력치 보정 5,459행(보정만으로 글이 바뀐 행 4,642), threat 줄 94,250, risk 선택지 276,158(행 87,906), 사람이 risk 선택지를 고른 행 25,983. parity 511행 불일치 0. EX-158 mock 2/2 정상(CPU, 84초).
- 2026-11-02 08:54Z — `scripts/laya-imitation-ep225 gpu3` 시작(앞 단계는 완료 표시로 건너뜀). 사전검사 loss 2.1692 → 2.0568, 학습 시작(GPU3 사용률 100%). 예상: 학습 약 11시간(EX-149 기준) → 평가 → EX-158 약 3시간(EX-150 2.7시간). 로그 `runs/model-training/EP-225-gpu3.log`.
- 2026-11-02 20:19Z — 학습 완료(40,960초, 선택 epoch 2). 평가 20:19~20:22Z.
- 2026-11-02 20:22Z — battle-window 표시 생성, EX-158 prepare/execute(22:41Z)/export, 22:43Z 표시 삭제, 뷰어 확인 통과. 레인 22:43:50Z 정상 종료. 이 세션의 감시 명령은 `pgrep -f`가 자기 명령줄과 맞아 종료를 알리지 못했다(레인에는 영향 없음).

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 자동 재실행은 없다. 연결 실행은 실패한 단계에서 멈춘다. 학습 결함(재로딩·parity·해시 불일치, 학습 중단)이나 mock 실패만 배틀 전에 멈출 수 있다(D-191).

## 결과 및 증거

- [EX-157](../experiments/EX-157-laya-v9-opponent-threat-training.md): 잠긴 test NLL 1.4332 → 1.4109(−0.0223, 95% [−0.0506, +0.0052]), 일치율 45.78 → 47.64%. 최악 100% 이상 risk 교체 선택지 확률 합 0.1798 → 0.1542(95% [−0.0324, −0.0188]). 자발 교체·사람이 risk 선택지를 고른 행은 나빠졌다(NLL +0.1055, +0.1033). 테라 지식 A3 93.7 → 70.0%.
- [EX-158](../experiments/EX-158-laya-v7t-v9t-battle256.md): v7t 112-16, v9t 110-18, 차이 −0.0156 [−0.1016, +0.0703] → 퇴보를 배제하지 못함. 기술 실패율 5.17 → 4.41%, 테라 사용 경기 28 → 12.
- 결론: v9 표시는 위험한 교체를 덜 고르게 만들었지만 Abyssal 성적은 v7과 구별되지 않는다. 사용자 장면의 효과는 사람 대전으로 확인한다.
