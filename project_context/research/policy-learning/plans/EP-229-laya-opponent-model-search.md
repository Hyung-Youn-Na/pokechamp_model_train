# EP-229 — laya 상대 모델 + 한 턴 탐색(세트 표본 추정)

- 상태: Active
- 생성일: 2026-11-03
- 책임자: Claude Code
- 승인 근거·범위:
  - 사용자 지시(2026-11-03 대화): "세트 여러개 표본으로 추정하는 탐색으로 가보자." 설계는 [D-206](../decisions/D-206-laya-opponent-model-search.md)에 있다.
  - 1단계(EX-165, 오프라인 장면 검증)를 이어서 진행한다. 2·3단계는 1단계 결과를 보고한 뒤 등록한다.
- 관련 contract / decision / experiment: [D-206](../decisions/D-206-laya-opponent-model-search.md), [EX-165](../experiments/EX-165-laya-opponent-prediction-scenes.md), [EP-228](EP-228-laya-switch-read-and-mixing.md)
- 기준 연구선: `research/model-training`
- 작업 checkout과 interpreter/launcher: `/workspace`(미커밋 새 파일), laya venv(CPU 추론), Metamon bridge venv(`.tools/metamon-imitation`)
- 새 산출물: `runs/model-training/EX-165`
- 참조 원자료(읽기 전용): laya-play v7test 경기 기록(`/workspace/.artifacts/laya-v7test/games/`, Showdown 로그), EX-155 체크포인트, `usage_sets_v3.json`

## 목표와 맥락

봇이 상대(사람)의 다음 수를 예측하고, 그 예측으로 한 턴을 탐색해 읽기와 섞기를 상황에 맞게 하도록 만든다(D-206).

## 범위와 불변 조건

- **포함**: `integration/laya_search/`, 기록
- **보존**: 기존 패키지, 자료, 산출물, 봉인은 그대로 둔다. 1단계는 CPU만 쓰고 GPU를 쓰지 않는다.
- **외부 호출**: 없다.

## 완료 기준

- [x] D-206, EP-229, EX-165 등록
- [x] EX-165 장면 검증 결과 기록
- [ ] 2단계(이득 계산·선택) 등록과 구현
- [ ] 3단계(배틀) 등록과 실행

## 진행

- 2026-11-03 — 사용자와 설계했다(상대 시점 정보 숨김, 세트 표본). 시점 재구성은 같은 파서를 상대 시점으로 돌리는 방식으로 확인했다(244 T2: 봇 팀은 공개 정보만, 사용자 팀은 표본 세트).
- 2026-11-03 — EX-165 완료 후 결과를 보고했다. 2단계는 사용자 확인 뒤 등록한다.
- 2026-11-09 — 그 뒤 진행은 없다. 사용자가 EP-230(래더 자료 v10)을 먼저 진행했다. 2단계(이득 계산·선택)는 아직 등록하지 않았고 사용자 확인을 기다린다. 기반 모델을 v10t·v10rt로 바꿀지도 그때 정한다(D-206 결정 4).

## 결과 및 증거

- [EX-165](../experiments/EX-165-laya-opponent-prediction-scenes.md)(2026-11-03):
  - 상대 시점 예측은 99결정 중 1순위 일치 31%(표본), 33%(진짜 세트)다.
  - 읽기 장면 9개 중 5개에서 읽기 기술 확률이 0.05 이하였다. 모방 모델만으로는 읽는 상대를 예측하지 못한다.
