# 고정 A/B 공개 상태 MCTS

## 분리된 연구선에서 읽는 방법

현재 checkout의 작업·환경 선택은 [연구 매뉴얼](../../../project_context/RESEARCH_MANUAL.md), 실행 여부는
[STATUS](../../../project_context/STATUS.md#active-work)를 먼저 확인한다. 아래 실행 명령은 `/workspace`의 기존 환경을
기준으로 한 기술 참조다. L1–L5 worktree는 보존·설계용이며 실행용 환경이 구성되어 있지 않다.
D/EX가 지정된 조건·경로·재개 명령은 해당 실험의 범위로 읽고, 공통 규칙은 기존 적용 범위를
유지한다. 새 실험의 입력·출력·실행 범위는 등록된 작업에서 정한다.

## 보존된 실험별 실행 경로

D-126/EX-079의 실행기는 완료된 round1에서 종료조건을 적용해 추가 학습하는 별도 경로다.
`stopping-prepare --parent .pokechamp-data/experiments/ex078-fixed-matchup-first-round-untimed` 후
`stopping-run`을 실행한다. 기본 출력은 `.pokechamp-data/experiments/ex079-fixed-matchup-stopping`이다.
원 모델/optimizer/RNG/replay·시계를 검증 계승하고 최대32라운드 안에서 정기 개발 평가로
목표/정체를 판정한다. 실제 최고 후보를 잠근 뒤 별도test640을1회 실행한다.
종료 조건 전문과 승인 범위는 [EX-079](../../../project_context/research/fixed-matchup-learning/experiments/EX-079-fixed-matchup-stopping.md)를 따른다.
벽시계 상한은 없고 단계별 알람을 사용한다. 기존pilot gate를 통과한 것으로 소급 표시하지 않는다.
`stopping-finalize --directory <실행 경로>`는 새 배틀 없이 전수 감사·뷰어/보고를 수행한다.
이전 실행 파일은 보존하며 완료/기술중단 receipt가 있는 경로는 자동 재실행하지 않는다.

D-125 승인 복구는 `first-round-recover-prepare --parent .pokechamp-data/experiments/ex078-fixed-matchup-first-round`로
정상31·원checkpoint0를 별도 `ex078-fixed-matchup-first-round-untimed`에 계승한 뒤,
`first-round-run --directory .pokechamp-data/experiments/ex078-fixed-matchup-first-round-untimed`으로
실패1경기만1회 수집·첫라운드 학습을 수행한다. 원경기/실패는 덮어쓰지 않는다.

D-123/EX-078의 첫 체크포인트 진단은 별도 명령이다.
`first-round-prepare --parent .pokechamp-data/experiments/ex077-fixed-matchup-day` 다음
`first-round-run`으로 같은P0의 자기대국32경기·1라운드 학습·검증/뷰어 후 종료한다.
D-124 이후 경기·단계·전체 벽시계 상한은 없다. 경과시간은 기록만 한다.
원8시간 실행은31정상/1시간초과·학습0으로 보존하며, 기존 실행 폴더는 그대로 재개하지 않는다. dev/test/후속 라운드는 실행하지 않는다.

D-122/EX-077 경로는 전체 예상24시간 이하일 때만 학습을 시작하며,
새24시간 시계·test15시간 상한 외 모델/탐색/학습 조건을 유지한다.
`day-prepare --parent .pokechamp-data/experiments/ex076-fixed-matchup-mcts-fnt-v2`는
보존된 정상uniform32/P0만 계승한다. 이전 실행은 재개하지 않는다.

## EX-076에서 이어진 공통 구현

[EX-076](../../../project_context/research/fixed-matchup-learning/experiments/EX-076-fixed-matchup-mcts.md)에서 시작해 후속 실험으로
확장된 실행기다. 현재 일반 `prepare`·`run`은 `config.py`의
[EX-077](../../../project_context/research/fixed-matchup-learning/experiments/EX-077-fixed-matchup-day.md) 기본 조건을 사용하며,
EX-076을 선택하는 범용 CLI 인자는 없다. D-121의 기절 분류 교정 복구는 별도 `recover-prepare` 경로다.
실험 조건·판정은 각 EX, 정보 경계는 [C-060](../../../project_context/research/fixed-matchup-learning/CONTRACTS.md#c-060-fixed-matchup)을 따른다.

## 모델과 데이터 흐름

새 PyTorch TransformerEncoder를 무작위 초기화한다. Qwen 가중치·과거 학습 자료·증류는 사용하지 않는다.
4층, hidden128, head4, FFN512, dropout0이며 현재 Dex vocabulary 기준1,500,674파라미터다.

1. `simulator.cjs`의 실제 경기 인스턴스가 양측 합법 후보와 공개 상태를 반환한다.
2. `public_state.cjs`는 허용 필드만 직렬화한다. 실제 PRNG·이번 선택·미실행 행동 queue·
   로그는 전달하지 않으며 알 수 없는 필드는 중단한다. Gen9에서 필요 없는 과거 미공개 선택도 제거한다.
3. `observation.cjs`는 관점/종류 범주와 정규화 숫자32개로 전역 상태, 포켓몬, 기술, 효과,
   합법 후보를 표현한다. HP/PP/능력치/boost/도구/특성/Tera/효과 카운터를 포함한다.
   이는 공개 상태의 학습용 특징이며 원 직렬화 전체의 무손실 표현은 아니다. 원래 팀/기술 슬롯
   숫자를 쓰고 위치 embedding은 사용하지 않는다. 최대256토큰/13후보를 넘으면 절단하지 않고 중단한다.
4. 범주 embedding 평균과 숫자 projection을 더해 Transformer에 넣는다. 유효 상태 토큰 평균과
   후보 embedding을 연결한 MLP가 정책 logits를, 상태 MLP+tanh가 관점별 상태가치를 낸다.
5. `search.py`는 새 탐색 RNG로 상태를 복원한다. 양측 Exp3가 상대의 이번 표본을 보기 전에
   독립 선택하고 공동 행동 이후 확률 전이를 표본화한다. 양측 가치 차이/2로 반대칭화한다.
   실제 선택과 정책 타깃은 루트 주변 방문 분포다. 실제 경기와 탐색은 별도 Node 프로세스다.
6. 정상 종료 경기만 최근 replay에 들어간다. CE+상태가치 MSE로 학습하며 자동 단일 후보의
   정책 손실은0이다. 실패/검열 경기에 승패 라벨을 만들지 않는다.

`pool.py`의 CPU worker는 GPU를 사용하지 않는다. 주 프로세스 추론 스레드가 요청을 모아
하나의 소유 GPU에서 실행한다. 평가 상대는 별도 poke-env Python 프로세스이며 자신의 요청과
기존 공개 protocol만 받는다. 공개 상태 정책과 상대의 정보량 차이는 실험 보고에 명시한다.

## 현재 기본 CLI — EX-077 (기술 참조)

프로젝트 루트에서 실행한다. wrapper는 `/ref/kev/.venv/bin/python`, 평가 상대는
`pokechamp/.venv/bin/python`, 브라우저 검증은 `/tmp/ep037/tools/bin/python`을 사용한다.
Node와 빌드된 로컬 Showdown, psutil·torch·pytest 및 해당 브라우저 환경의 Playwright/Chromium이 필요하다.

```bash
# CPU 합성 검사: 실제 고정 A/B 대진·GPU를 사용하지 않는다.
scripts/pokechamp-fixed-matchup verify

# CPU 준비: 두 팀 검증, 소스/환경/후보 사전/전체 schedule을 새 디렉터리에 동결한다.
scripts/pokechamp-fixed-matchup prepare --directory /path/to/new-run

# EX-077 실행 지시가 있을 때 사용하는 명령. 첫 검증 시점부터 원24시간 시계가 시작된다.
scripts/pokechamp-fixed-matchup run --directory /path/to/new-run
scripts/pokechamp-fixed-matchup status --directory /path/to/new-run

# 이미 시작한 실행의 원 시계·최종화 상한 안에서 감사/뷰어를 재개한다.
scripts/pokechamp-fixed-matchup finalize --directory /path/to/new-run
```

`prepare`는 기존 경로를 덮어쓰지 않는다. 실행·재개 전 live source와 동결 복사본,
Python package 버전·Node·팀·schedule/catalog 해시를 대조한다. 실행 중 문서를 포함한
동결 대상이 바뀌면 재개를 거부한다. 개발 수정은 준비 전에 끝낸다.
GPU 수치·reload·합성 시뮬레이터·브라우저 gate 후 pilot과 처리량 측정을 수행한다.
worker/batch 후보는 측정으로 선택하며 측정 전 등록된 상한 내 완주나 개선을 보장하지 않는다.

## 중단·재개와 결과

같은 `run` 명령은 완료 라운드에서 이어간다. checkpoint는 모델·optimizer·Python/torch/CUDA
난수·셔플 generator·replay ID·최초 시계를 저장하고 별도 commit receipt로 확정한다.
commit 후 모델 export/dev 직전에 종료되어도 누락 단계를 이어간다. 업데이트 도중 종료된
미확정 가중치는 채택하지 않는다. 예약된 미완료 경기는 다시 돌리지 않는다.
부분 artifact와 중단 원장을 보존하며 공유 결함·source 변경은 자동 복구하지 않는다.
benchmark 중 예약만 남은 probe도 재실행하지 않으므로 해당 단계가 중단될 수 있다.

SIGTERM/SIGINT는 소유 worker·Node·상대 프로세스를 정리하고 마지막 완료 checkpoint를 보존한다.
재개해도 단계/전체 시계가 늘어나지 않는다. 취소 직후에는 추가 배틀·최종화를 시작하지 않는다.
완료된 dev 후보가 없으면 test를 잠근 채 중단한다. 기술 gate나 예산 실패를 효능 실패와 구분한다.

`games/<slot>/`에 결과, 압축 결정 기록, 감사 전용 private evidence, 초기 공개 root 표본을 보존한다.
private evidence는 탐색/모델 입력이 아니다. `final/result.json`·`report.md`는 고정 test 분모와
seed블록 대응 bootstrap 결과, 기술 gate·절차 완료·정책 개선을 구분한다.
`evidence.sha256`은 source/팀/모델/경기/checkpoint/최종 결과와 manifest·schedule·catalog·
평가 잠금을 봉인한다. 계속 기록되는 자원·중단·시계 원장은 이 봉인의 대상이 아니다.

정상 경기 전수 입력·타깃·실제 제출 명령을 감사하고
`exports/battle_viewers/<실험 ID 소문자·하이픈 제거>-<identity 앞8자리>-<result_key>/`에 내보낸다.
입력/응답/protocol은 오프라인이다. 선택적 Showdown 애니메이션만 외부 자산을 사용한다.
브라우저 표본은 단계·조건별 첫 경기로 각 층을 먼저 덮고 마지막 경기를 추가해 최대12개로 제한한다.
층 정렬은 `(stage, condition)`, 경기 정렬은 `slot_id`이며 중복은 제외한다. 브라우저 전수 검증은 아니다.

## 개발 검증

```bash
PYTHONPATH=/workspace /ref/kev/.venv/bin/python -m pytest -q \
  integration/pokechamp/tests/test_fixed_matchup_simulator.py \
  integration/pokechamp/tests/test_fixed_matchup_pipeline.py
```

검사는 합성 팀/행렬 게임을 사용한다. 정보 경계·RNG 격리·기계적 전이, 학습/reload,
checkpoint·SIGTERM·예약 중복, 통계, 프로세스 배치 추론, Abyssal 연결, 실제 명령 감사와
이동 후 오프라인 브라우저를 검사한다. 준비 검사는 고정 팀 파일의 hash/합법성만 확인한다.
이 CPU 개발 검사는 GPU 정확성/메모리/처리량, 실제 A/B pilot 균형·검열,
학습 효과·test640 결과를 평가하지 않는다. 이후 실험의 결과·판정은 각 EX와
[STATUS](../../../project_context/STATUS.md#active-work)를 따른다.

D-121 전용 복구 준비는 `recover-prepare --parent <원 실행> --directory <새 sibling 경로>`다.
원본을 덮어쓰지 않고 완료uniform32·P0·원12시간 시계·소비한 단계 예산을 연결한다.
원 실패8probe의1회 재시도만 명시적으로 승인됐으며 일반 자동 재시도는 허용하지 않는다.
