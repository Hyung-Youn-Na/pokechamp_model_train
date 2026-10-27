# EX-060 원경기 분기 데이터

[EX-060](../../../project_context/research/action-value/experiments/EX-060-single-battle-branch-rollouts.md)의
원경기 재현·분기 수집·보고 실행기다. 기본 대상은 EX-058 battle-19 한 경기이며,
이후 양측 정책은 canonical Abyssal이다. 실제 수집은 등록된 예산과 승인 범위 안에서만 실행한다.

## 실행

canonical 데이터 로더가 상대경로를 사용하므로 `pokechamp/`에서 실행한다.

```bash
cd /workspace/pokechamp
export PYTHONPATH=/workspace:/workspace/pokechamp
export PYTHONHASHSEED=964798779
.venv/bin/python -m integration.pokechamp.branch_rollouts prepare
.venv/bin/python -m integration.pokechamp.branch_rollouts reconstruct
.venv/bin/python -m integration.pokechamp.branch_rollouts validate
.venv/bin/python -m integration.pokechamp.branch_rollouts collect
.venv/bin/python -m integration.pokechamp.branch_rollouts report
.venv/bin/python -m integration.pokechamp.branch_rollouts finalize
```

`prepare`는 원자료 봉인을 확인하고 관측·명령을 추출한다. `reconstruct`는 저장된 JEV
명령과 원래 Abyssal 난수를 사용해 원경기를 재현하고 각 관측·요청·후보·결과를 대조한다.
`validate`는 각 저장 root에서 원행동 suffix를 재생해 상태 복원과 실행 순서를 확인한다.
원경기 재현부터 누적 예산 원장이 시작된다. 재시작으로 시계나 시도 수가 초기화되지 않는다.

`collect`는 별도 Node simulator에서 상태를 복원하고 미래 난수만 바꾼다. 같은 root·반복의
모든 후보에 같은 simulator/actor seed를 배정한다. 자기 후보만 강제한 뒤 양측 Abyssal이
종료까지 선택한다. 4개 worker·분기120초·추가300턴을 제한하며 검열과 오류를 별도 보존한다.
오류 뒤 신규 제출을 멈추고 이미 예약한 결과를 모두 기록한다. 자동 재시도는 없다.
`finalize`는 출처·root·trace·난수·원장·학습 입력을 감사하고 source 복사본과 checksum을 남긴다.

## 산출물과 해석

기본 저장 경로는 `.pokechamp-data/rollouts/ex058-b19-rollout-v1/`이다.
`private/`의 simulator·actor snapshot과 trace/seed는 감사·재현 전용이다. 신뢰할 수 없는
pickle snapshot은 읽지 않는다. 모델에는 `training.jsonl`의 관측·허용 행동·통계만 사용한다.
원자료 자체에는 자기 private request가 있어 원자료 전체를 학습 입력으로 복사하면 안 된다.

통계는 실제 숨은 상태와 Abyssal 후속 정책에 조건부다. 후보32회가 모두 정상 종료했을 때만
승률·Wilson95%·q를 산출하고, 원행동과 대응 반복으로 차이를 계산한다. 최고 표본평균이
확정 최선이라는 의미는 아니다. 기존 Abyssal은 일반 선택 경로에서 테라를 사용하지 않는다.
이 대진과 분기 자료는 개발용으로 취급하며 독립 평가에 재사용하지 않는다.

뷰어는 `exports/battle_viewers/ex060/`에 결정별 관측·후보 통계·분기 리플레이를 제공한다.
공개 로그는 오프라인으로 읽을 수 있으며 애니메이션은 Showdown 외부 자산이 필요하다.
