# EX-066 공동 q 학습

## 분리된 연구선에서 읽는 방법

현재 checkout의 작업·환경 선택은 [연구 매뉴얼](../../../../project_context/RESEARCH_MANUAL.md), 실행 여부는
[STATUS](../../../../project_context/STATUS.md#active-work)를 먼저 확인한다. 아래 실행 명령은 `/workspace`의 기존 환경을
기준으로 한 기술 참조다. L1–L5 worktree는 보존·설계용이며 실행용 환경이 구성되어 있지 않다.
D/EX가 지정된 조건·경로·재개 명령은 해당 실험의 범위로 읽고, 공통 규칙은 기존 적용 범위를
유지한다. 새 실험의 입력·출력·실행 범위는 등록된 작업에서 정한다.


EX-065의 공개 `JointInput`/로더와 Qwen3.5-4B-Base 고정 revision을 사용하는 별도 학습 경로다.
전체 타깃 MSE이며 bandit RLCD와 구분한다. 실행 조건·해석의 원문은
[EX-066](../../../../project_context/experiments/EX-066-joint-q-training.md), 진행은 EP-108이다.
한 backbone forward의 후보별 `Q_VALUE=` hidden state에서 독립 sigmoid q를 반환한다.
입력은 원 관측과 전체 후보이며 타깃/private/seed를 허용하지 않는다.

```bash
cd /workspace
scripts/pokechamp-joint-q verify --phase unit
scripts/pokechamp-joint-q prepare --download
scripts/pokechamp-joint-q preflight
scripts/pokechamp-joint-q train
scripts/pokechamp-joint-q verify --phase reload
scripts/pokechamp-joint-q evaluate
scripts/pokechamp-joint-q verify --phase final
```

기본 데이터는 `/mnt/digicap/combined/hyna/backup/pokechamp/`, 산출물은
`.pokechamp-data/experiments/ex066-joint-q-training/`다. 새 재실행은 `--out`의 빈 경로로 구분한다.
wrapper는 기존 EVE Python·물리 GPU1·native threads1을 지정한다. GPU2 사용 중 유휴 GPU로
대체하라는 사용자 지시(D-106)에 따라 이번 실행을 GPU1로 고정했다. 수집 로더의 기존 회귀 검사는
PokéChamp 환경에서, 새 학습 검사는 EVE에서 수행한다. 환경 의존성을 섞어 설치하지 않는다.

`prepared/manifest.json`은 원본·Base/tokenizer·renderer·source/package·준비 토큰의 해시와
train/validation/3epoch 무절단 전수 검사를 보존한다. test 토큰은 최종 잠금 전 만들지 않는다.
`training/initial`, `epoch-1`…`epoch-3`는 영구 checkpoint이며 `latest.json`은 마지막 완전
optimizer update를 가리킨다. transient update는 최근2개를 원자적으로 유지한다.
각 checkpoint는 `adapter/`, `value_head.pt`, `state.pt`(optimizer/RNG/cursor), `metadata.json`,
파일별 `files.json`을 포함한다. 기술 중단은 `train --resume`으로 같은 설정·순서·RNG에서 재개한다.

길이 초과·OOM·누출·비유한 경사·무결성 위반은 `STOP.json`과 실패 증거를 남기고 의존 실행을
차단한다. 절단/제외/설정 완화는 없다. 성공한 test 모델은 재호출하지 않으며 실패한 test의
자동 재시도도 없다. 분석은 저장 예측에서 수행한다. 보고·봉인·명령·부분 실패의 원자료를 보존한다.

최초 preflight의 token-padding 경계 결함은 `versions/preflight-v1/`에 원본을 보존했다.
microbatch1에서는 전체 유효 토큰 prefix를 유지하고 마스크된 padding만 backbone 앞에서 제거한다.
학습 미시작 상태의 이 결함만 독립 GPU/회귀·동일 token/hash와 학습 조건을 입증한 recovery receipt로
preflight 재검사를 허용한다. D-105의 명시적 GPU2 변경은 준비 중단 원문·승인 해시로 대조한다.
D-106의 유휴 GPU1 대체도 같은 원문·승인 해시로 확인한다.
`--recovery-receipt`는 다른 STOP이나 학습/test 재실행을 허용하지 않는다.

전q0/1의 MSE0은 유한한0경사를 허용한다. 누락·NaN·Inf 경사는 계속 중지한다.
이 검증 경계 교정은 `versions/zero-gradient-v1/`에 원본을 보존하고 update0의 초기 checkpoint,
설정/환경/토큰/Base 불변·독립 회귀를 receipt로 확인한다. 검증기가 해당 거부2행 제거만
허용하여 source를 다시 동결한 뒤 GPU preflight와 `train --resume`을 수행한다.
