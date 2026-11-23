# EP-241 — laya v13 입력 교정(무재학습 EX-200) 대 foul-play Blim 128경기(시간 제한 없음)

- 상태: Completed
- 생성일: 2026-11-23
- 책임자: Antigravity (Gemini)
- 승인 근거·범위: 사용자 지시(2026-11-23 대화, 선택지 1 "무재학습 v13 + EX-200 배틀 평가 — foul-play Blim 128경기, EX-201과 같은 슬롯 비교"에 대해 "1. 을 진행해주세요."), [D-218](../decisions/D-218-laya-v13-input-bugfixes.md), [D-217](../decisions/D-217-laya-engine-value-rerank-training.md), [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-191](../decisions/D-191-no-offline-battle-gate.md). 구현(`battle_v13.py`, 실행기) → mock 2/2 → prepare → execute 128 → export(보고·뷰어·봉인)까지 진행한다. 외부 호출은 없다.
- 관련 contract / decision / experiment: [C-047](../../../CONTRACTS.md#c-047-viewer-export), [D-218](../decisions/D-218-laya-v13-input-bugfixes.md), [EP-240](EP-240-laya-v13-input-bugfixes.md), [EP-239](EP-239-laya-engine-value-rerank-training.md), [EX-201](../experiments/EX-201-laya-engine-value-vs-foulplay-unlimited.md), [EX-205](../experiments/EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md)
- 겹치는 등록 plan:
  - [EP-240](EP-240-laya-v13-input-bugfixes.md)(Completed): `integration/laya_v13/{render_v13,serve_v13}.py`를 그대로 사용하며 수정하지 않는다.
  - [EP-239](EP-239-laya-engine-value-rerank-training.md)(Completed): `EX-200` 체크포인트와 `EX-201` 봉인 결과를 읽기 전용으로 참조한다.
  - [EP-229](EP-229-laya-opponent-model-search.md)·[EP-231](EP-231-laya-ladder-postmortem-v11.md)·[EP-234](EP-234-laya-fp1-foulplay-input.md)·[EP-237](EP-237-laya-observed-public-info-input.md)(Active): 실행 중인 프로세스 및 포트 충돌 없음.
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit·미커밋 변경: `research/model-training`, `ee13b70`(EP-234~240 미커밋 변경 위)
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv(`.tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python`), foul-play venv(`.tools/foul-play/.venv`, `actor_unlimited`), `scripts/laya-v13-battle-ep241`
- 새 산출물:
  - 코드: `integration/laya_v13/battle_v13.py`, `scripts/laya-v13-battle-ep241`
  - 실행 산출물: `runs/model-training/EX-205`, 뷰어 `exports/battle_viewers/ex205/`
- 참조 원자료(읽기 전용): `runs/model-training/EX-200/checkpoints/selected`, `runs/model-training/EX-201`(같은 슬롯 기준선), `runs/model-training/EX-174`(봉인 Blim 128슬롯·기준선), foul-play 봉인 자료(`.tools/foul-play/data-SHA256SUMS`)

## 목표와 맥락

재학습 없이 `EX-200` 체크포인트의 서빙 입력만 `v12`에서 `v13`([D-218](../decisions/D-218-laya-v13-input-bugfixes.md): `formespec`, `teradefence`, `roostground`, `ivycudgel`)으로 교체했을 때, 시간 제한 없는 foul-play Blim 128경기 성적이 [EX-201](../experiments/EX-201-laya-engine-value-vs-foulplay-unlimited.md)(48승 80패, 0.375) 대비 얼마나 달라지는지 같은 슬롯에서 측정한다.

## 범위와 불변 조건

- **포함**: `integration/laya_v13/battle_v13.py`, `scripts/laya-v13-battle-ep241`, `EX-205` 실행·보고·뷰어·봉인, 기록.
- **보존**: `laya_imitation`·`laya_threat`·`laya_v10`·`laya_v11`·`laya_v12`·`laya_value`·`foulplay`·`laya_v13/{render_v13,serve_v13}.py` 및 기존 자료·산출물·봉인은 바이트 단위로 유지한다.
- **자원**: CPU 전용(GPU 미사용), 포트 `8100-8103`, `scripts/mem-guard 25` 아래 실행(시작 전 `free -g` 114 GB 가용 확인, 포트 비어 있음 확인).
- **외부 호출**: 없다.

## 완료 기준

- [x] EP-241·EX-205 등록, catalog build/check
- [x] `integration/laya_v13/battle_v13.py`·`scripts/laya-v13-battle-ep241` 구현
- [x] EX-205 mock 2/2 완료·감사 통과 → prepare(동결) → execute 128 → export(보고·뷰어 `exports/battle_viewers/ex205`·봉인)
- [x] 결과를 EX-205·EP-241·STATUS·catalog에 기록하고 보고(뷰어 열람 링크 포함, C-047)

## 절차

1. `integration/laya_v13/battle_v13.py`와 `scripts/laya-v13-battle-ep241`을 작성한다.
2. `scripts/laya-v13-battle-ep241 EX-205`로 `mock` → `prepare` → `execute` → `export`를 순차 실행한다.
3. 완료 후 보고서·뷰어·봉인을 검증하고 EX-205·EP-241·STATUS·catalog를 갱신한다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. mock 실패/감사 불일치, `v12` 기반 렌더러 불일치, `phase_error`, `mem-guard` 종료 시 즉시 멈추고 보고한다. foul-play 엔진 panic은 `actor_unlimited`가 해당 경기만 `incomplete`(`engine_panic`)로 격리한다(EX-201·202와 동일).

## 진행

- 2026-11-23 — 사용자 지시로 등록 및 `battle_v13.py`·실행기 작성.
- 2026-11-23T00:38Z — EX-205 mock 2/2 통과(`fp-b24-s2-a` 68턴·`fp-b24-s2-b` 27턴, 감사 통과, 오류 0) 및 prepare 완료(128슬롯 동결, checkpoint sha256 `22531f2f…`, EX-201과 동일). 본 실행(`execute` 128 → `export`, CPU·포트 8100~8103·`mem-guard 25`) 시작.
- 2026-11-23T04:58Z — EX-205 완료 및 export·봉인 완료: 정상 종료 127/128(40승 0무 87패, `0.315 [0.236, 0.394]`, 실패 1건 `fp-b20-s2-a` 500턴 Showdown auto-tie 경고 오인). 같은 슬롯 EX-201 대비 `-0.055 [-0.157, +0.039]`, EX-174 대비 `-0.016 [-0.111, +0.078]`. 뷰어 `exports/battle_viewers/ex205/index.html`(128경기, 7,843결정) 및 `checksums.sha256` 봉인 완료.

## 결과 및 증거

[EX-205](../experiments/EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md) 및 `runs/model-training/EX-205/report.md`, `exports/battle_viewers/ex205/index.html` 참조.
