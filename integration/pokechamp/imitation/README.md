# Qwen 리플레이 모방 학습

[EX-071](../../../project_context/experiments/EX-071-qwen-replay-imitation.md)의 첫 학습·평가
실행 경로다. 조건과 해석은 EX-071, 입력·Choice 의미는
[C-055](../../../project_context/CONTRACTS.md#c-055-imitation), 작업 상태는
[EP-115](../../../project_context/exec-plans/completed/EP-115-qwen-replay-imitation.md)가 소유한다.

## 구성

`dataset.py`가 원본·평가팀 제외·연결 그룹 분할·세트 통계·배틀 대진을 먼저 동결한다.
`metamon_bridge.py`는 `.tools/metamon-imitation/.venv`의 고정 Metamon parser와 JSONL로
통신한다. `impute.py`가 공개 원래 세트와 일치하는 합법 세트를 빈도로 보완하고,
`replay.py`는 각 결정 직전의 공개 로그까지만 복원한다. 미지원 메뉴·원래 세트 부재·
불명확한 선택은 사유와 함께 격리 또는 마스킹한다. 원본은 수정하지 않는다.

`schema.py`의 같은 직렬화 함수가 복원과 실배틀 입력을 만든다. Choice 후보는 안정된
기술/Tera·아군 슬롯 ID를 사용한다. 최대8,192 상태 토큰 초과는 자르지 않고 제외한다.
준비 시 tokenizer만 사용하며 모델 추론은 없다. `verification.py`는 실제 CPU 환경·
Showdown validator/Dex와 검사 증거를 보존하고 전수 자료 감사에 묶는다.

`model.py`는 고정 Qwen Base와 Kev readout을 사용하며 새 FP32 LoRA·head를 만든다.
`learning.py`는 GPU 사전검사, 고정 업데이트 예산, 부분 accumulation까지 보존하는 재개,
validation 선택과 잠긴 test를 담당한다. `serving.py`는 같은 unmerged 경로를 loopback으로
제공한다. checkpoint에는 Base를 중복 저장하지 않고 고정 Base revision·hash를 연결한다.

`player.py`는 공식 요청의 합법 후보를 안정된 ID와 연결하며 전송 직전 rqid·명령을 다시
확인한다. `battle.py`는 두 모델의 고정40경기와 소유 서버·CPU actor·최초 시계를 관리한다.
단일 후보는 추론 없이 제출한다. 재질의·fallback·재경기는 없다. `reporting.py`와
`viewer.py`는 원장 전체의 분모, 대응 bootstrap과 행동 선택 확률을 표시한다.

## 실행과 보존

각 단계는 저장된 이전 gate를 확인한다. 다음 명령은 이미 실행된 단계를 반복하는 허가가
아니며, 현재 산출물·EP 상태를 먼저 확인해야 한다.

```bash
scripts/pokechamp-imitation status
scripts/pokechamp-imitation prepare
scripts/pokechamp-imitation audit
scripts/pokechamp-imitation preflight
scripts/pokechamp-imitation train
scripts/pokechamp-imitation evaluate
scripts/pokechamp-imitation battle
scripts/pokechamp-imitation export
```

산출물 기본 위치는 `.pokechamp-data/experiments/ex071-qwen-replay-imitation/`이다.
동결 문서·자료·실행 소스·CPU 환경 복사본과 stage event를 보존한다. GPU는 직전 유휴 상태를
3→2→0 순서로 확인해 한 장의 UUID를 고정하며 GPU1은 사용하지 않는다. 기존 학습·환경·
봉인은 수정하지 않는다. 실행기 lock을 우회해 병렬 단계를 실행하면 안 된다.

실제 GPU 사전검사부터 학습·validation의 최초24시간 시계가 시작된다. 기술 중단 후
처치·입력·수치 경로가 변하지 않고 완전한 checkpoint가 있을 때만
`scripts/pokechamp-imitation train --resume`으로 같은 시계에서 재개할 수 있다.
학습 소스·설정·자료를 바꾼 재학습과 test/배틀 재수집은 이번 승인 범위에 없다.
CPU 준비 교정도 원본과 실패 증거를 별도 버전으로 보존해야 한다.

## 결과 열람

- `prepared/manifest.json`, `audit.json`, `audit-gate.json`: 자료 분모와 출처·필수 검사
- `preflight/report.json`, `training/`: 예정/실제 학습량·validation·checkpoint·재개 상태
- `reload/serving-parity.json`, `evaluation-lock.json`, `evaluation/`: 재로딩/HTTP 대조·잠긴 test
- `battle/`: 예정40 slot 전체 원장·원문 요청/응답·전송 감사·결과
- `final/report.md`: 한국어 통합 보고
- `exports/battle_viewers/ex071/index.html`: 완료된40경기의 오프라인 뷰어

첫 실행은2026-10-02에 완료했다. [통합 보고](../../../.pokechamp-data/experiments/ex071-qwen-replay-imitation/final/report.md)와
[해석·표현 보충](../../../project_context/experiments/EX-071-qwen-replay-imitation.md#final-results),
[뷰어](../../../exports/battle_viewers/ex071/index.html)를 열람할 수 있다. 추가 학습·평가를 시작하는
명령으로 위 완료 단계를 반복하지 않는다.

뷰어의 확률은 행동 선택 확률이다. 오프라인 NLL·일치율은 인간 선택 재현 지표이며 배틀
승률과 다르다. 성능 개선이 불확실하거나 실패한 경우도 원래 분모와 함께 보고한다.
