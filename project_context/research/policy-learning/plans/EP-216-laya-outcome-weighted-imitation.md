# EP-216 — laya v2+테라 승패 가중 모방 학습과 배틀 비교(GPU0)

- 상태: Completed
- 생성일: 2026-10-26
- 책임자: Claude Code
- 승인 근거·범위: 현재 사용자 지시와 승인된 계획(GPU0·GPU2 활용 개선 방향) / [D-193](../decisions/D-193-laya-outcome-weighted-imitation.md).
  - 계획 승인으로 GPU0 학습과 배틀을 별도 승인 없이 이어서 진행한다.
  - 오프라인 결과로 배틀을 거르지 않는다([D-191](../decisions/D-191-no-offline-battle-gate.md)).
- 관련 contract / decision / experiment: [C-055](../CONTRACTS.md#c-055-imitation), [EX-132](../experiments/EX-132-laya-v2t-outcome-weighted-training.md), [EX-133](../experiments/EX-133-laya-v2t-v2tw-battle256.md), [EX-124](../experiments/EX-124-laya-v2-tera-knowledge-training.md), [EX-125](../experiments/EX-125-laya-v2-tera-battle256.md)
- 기준 연구선: `research/model-training`
- 실제 작업 branch, 시작 commit, 미커밋 변경: `research/model-training` `feda62f733c1b470364868262c789ec857ef67f5`. 기존 미커밋 변경은 보존한다.
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv, `pokechamp/.venv`.
  - 실행기는 `scripts/laya-imitation weighted|compare6`이다.
  - 연결 실행은 `scripts/laya-imitation-ep216`이다.
- 새 산출물과 검증 출력 위치:
  - `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/laya-outcome-weights/v1`
  - `.../runs/model-training/EX-132`, `.../runs/model-training/EX-133`
  - 연결 실행 로그 `.../runs/model-training/EP-216-chain.log`
  - 뷰어 `/workspace/exports/battle_viewers/ex133/`
- 참조 원자료(읽기 전용): EX-071 `preparation/replays.jsonl`과 원본 리플레이, `laya-compact-imitation/v2-all`, 테라 지식 `v1`, EX-124 산출물, EX-120 `collection/`

## 목표와 맥락

모방 학습 행에 리플레이 승패 가중치를 줬을 때 배틀 성적이 나아지는지 측정한다. 조건과 판정은 EX-132와 EX-133이 소유한다.

## 범위와 불변 조건

- **포함**:
  - `outcome_weights.py`, `evaluation_v2tw.py`, `tests/test_outcome_weights.py`
  - `training.Spec`의 `weights`·`same_split_as`, Spec `EX132`
  - 설정, 서빙 이름 `laya-v2tw`, CLI `weighted`·`compare6`, 비교 배틀 `EX133`, 실행기 경로
- **보존**:
  - EX-118~131 Spec, Study, 산출물, 봉인, 동작
  - laya 라이브러리(`/ref/laya`)는 수정하지 않는다.
- **자원**: GPU0과 포트 8107만 쓴다. GPU1·8109(EP-215)와 GPU2·8108은 쓰지 않는다. 외부 프로세스 종료와 장치 reset은 금지한다.
- **외부 호출**: 없다.

## 완료 기준

- [x] 가중치 생성과 봉인(매칭 실패 0)
- [x] EX-132 학습(GPU0), 선택, 테라 지식 held-out, 잠긴 test, EX-124 쌍비교(승패별), 보고, 봉인
- [x] EX-133 mock 후 256경기, 보고, 뷰어, 봉인, 자원 반환
- [x] STATUS, catalog build/check (뷰어 변경일지는 미기록)

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| 승패 매칭 | 로그 파싱(이름 Showdown id 정규화, 무승부, 결과 없음) | `test_outcome_weights` | 통과 |
| 가중치 | 평균 1, 승/패 비율 유지, 매칭 실패 시 중단 | `test_outcome_weights`, `laya-outcome-weights/v1/manifest.json` | 통과. 130,411행 전부 매칭 |
| 손실 적용 | target × w일 때 laya `soft_ce_loss`가 정확히 w배가 됨 | `test_outcome_weights` | 통과 |
| EX-124와 같은 설정 | Spec 필드 동일(가중치만 다름), 분할 크기 일치 검사(`same_split_as`) | `test_outcome_weights`, `EX-132/split.json` | 단위 통과, 분할은 학습 시 |
| 기존 동작 보존 | `pytest integration/laya_imitation/tests`, ruff, compileall | — | 66 통과, ruff·compileall 통과 |

## 진행

- 2026-10-26 — 승인과 등록, 구현과 단위 검사, 가중치 생성을 마쳤다.
  - 학습 행: 승 65,360, 패 64,434, 무 617
  - 정규화 배율 1.3302
- 2026-10-26 05:05Z — `scripts/laya-imitation-ep216` EX-132 학습 시작(GPU0). 14:10Z 학습 완료(선택 epoch 2), 평가 14:10~14:14Z.
- 2026-10-26 14:15Z — EX-133 mock 2/2 정상, prepare(14:18Z), execute 14:19~17:38Z, export 17:38~17:39Z. 256/256 정상·감사 통과. 연결 실행 17:40:03Z 정상 종료. 연결 실행에 뷰어 확인 단계가 없어 확인 기록은 없다.

## 차단·중단

- [INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 결함 복구와 중단은 EX-132와 EX-133을 참조한다.
- 자동 재실행은 없다. 연결 실행 스크립트는 단계가 실패하면 그 자리에서 멈춘다.

## 결과 및 증거

- [EX-132](../experiments/EX-132-laya-v2t-outcome-weighted-training.md): 잠긴 test NLL 1.4506 → 1.4509(+0.0003, 95% [−0.0247, +0.0246]), 일치율 47.85 → 46.78%. 이긴 쪽 행 NLL +0.0031, 진 쪽 행 −0.0021로 이긴 쪽이 더 나아지지 않았다. 실패로 정해진 선택지 확률 합 0.0562 → 0.0638.
- [EX-133](../experiments/EX-133-laya-v2t-v2tw-battle256.md): v2t 111-17, v2tw 99-29, 차이 −0.0938 [−0.1797, −0.0078] → 악화. 기술 실패율 5.75 → 9.84%.
- 결론: 승패 가중은 사람 선택 재현을 바꾸지 않았고 Abyssal 성적은 나빠졌다. 직접 대결([EX-135](../experiments/EX-135-laya-head-to-head-v2tw-v4t.md))에서는 v2t 0.523 [0.469, 0.578]로 구별되지 않는다.
