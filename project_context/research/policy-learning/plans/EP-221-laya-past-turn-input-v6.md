# EP-221 — laya 과거 턴 입력 v6s·v6h 동시 학습과 배틀 비교(GPU0·GPU1)

- 상태: Completed
- 생성일: 2026-10-29
- 책임자: Claude Code
- 승인 근거·범위: 사용자 지시(2026-10-29, 두 방법을 GPU0·1·2로 동시에 실험, 학습 시간 제한 해제, 2번은 여유가 있으면 4턴 이전 기록도 입력)와 [D-198](../decisions/D-198-laya-past-turn-input-v6.md). 구현, GPU 학습, 배틀을 별도 승인 없이 이어서 진행한다. 오프라인 결과로 배틀을 거르지 않는다([D-191](../decisions/D-191-no-offline-battle-gate.md)).
- 관련 contract / decision / experiment: [C-055](../CONTRACTS.md#c-055-imitation), [EX-141](../experiments/EX-141-laya-v6s-streaks-training.md), [EX-142](../experiments/EX-142-laya-v6h-long-history-training.md), [EX-143](../experiments/EX-143-laya-v5t-v6st-battle256.md), [EX-144](../experiments/EX-144-laya-v5t-v6ht-battle256.md), [EX-136](../experiments/EX-136-laya-v5-tera-training.md)
- 기준 연구선: `research/model-training`
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv, `pokechamp/.venv`, Metamon CPU env, node. 실행기 `scripts/laya-imitation v6|compare10|compare11`, 연결 실행 `scripts/laya-imitation-ep221`
- 새 산출물과 검증 출력 위치:
  - `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/laya-early-history/v1`
  - `.../laya-compact-imitation/v6s-all`, `v6h-all`
  - `.../runs/model-training/EX-141`~`EX-144`, 연결 실행 로그 `.../runs/model-training/EP-221-v6s.log`, `EP-221-v6h.log`
  - 뷰어 `/workspace/exports/battle_viewers/ex143/`, `ex144/`
- 참조 원자료(읽기 전용): EX-071 `prepared/`·`preparation/`·원본 리플레이, `laya-item-state/v1`, `laya-compact-features/v5`, 테라 지식 `v1`, EX-136 산출물, EX-120 `collection/`, 사람 대전 `/workspace/data/NHJ-20261029`

## 목표와 맥락

과거 턴 정보를 모델 입력에 넣었을 때 같은 수 반복이 줄고 사람 선택 재현과 배틀 성적이 어떻게 달라지는지, 두 방법을 동시에 측정한다. 두 방법은 1,024 안의 요약(v6s)과 2,048로 늘린 긴 기록(v6h)이다. 조건과 판정은 EX-141~144가 소유한다.

## 범위와 불변 조건

- **포함**:
  - 파서 opt-in 선택 필드 `early_history`(`replay.py`, `schema.py`, `metamon_bridge.py`)
  - `early_history.py`(재파싱과 전수 비교), `compact_v6.py`(`streaks`, `longhist`), `data_v6.py`, `evaluation_v6.py`, `tests/test_compact_v6.py`
  - `training.py` Spec `max_len`·`hours=None`, `policy.py` 체크포인트별 토큰 한도, 서빙 `--render v6s|v6h`, 배틀 워커의 v6h 전용 `early_history` 요청, CLI `v6`·`compare10`·`compare11`
- **보존**:
  - `early_history`를 요청하지 않는 모든 스냅샷·입력은 바이트 단위로 같다. v1~v5 렌더러 출력, laya-play·시나리오 봇 입력도 같다.
  - EX-071 `prepared`, `laya-item-state/v1`, `laya-compact-features/v5` 등 기존 자료와 EX-118~140 산출물·봉인·동작은 그대로 둔다.
  - 사람 라벨과 분할은 바꾸지 않는다.
- **자원**:
  - GPU0·포트 8107: EX-141 학습·평가, EX-143
  - GPU1·포트 8109: EX-142 학습·평가, EX-144
  - GPU2는 이번 연결 실행에서 쓰지 않는다(여유). GPU3은 쓰지 않는다. 외부 프로세스 종료와 장치 reset은 금지한다.
- **외부 호출**: 없다.

## 완료 기준

- [x] 파서 opt-in 필드, 기본 출력 불변 확인(EX-071 10리플레이 527결정), 기존 imitation 파서 검사 40건 통과
- [x] EX-071 재파싱 `laya-early-history/v1`: 기존 필드 131,947/131,947 일치, 봉인
- [x] v6 렌더러와 단위 검사(126번 T13·T15·T18 반복 표시, T37 긴 기록·길이 맞춤·T−1/T 보존, 스키마 겹침 거부), v5 동일성
- [x] 사전 측정(validation 512): v6s 512/512(최대 981), v6h 512/512(최대 2,047, 기록 p50 15턴)
- [x] `v6s-all`·`v6h-all` 자료(각각 제외 85행, 0.064%), parity 512/512, 봉인
- [x] EX-143·EX-144 mock(2경기씩 정상·감사 통과, v6ht 입력 28/28에 `early_history`, v6st 입력 0/25)
- [x] EX-141 학습(GPU0) → 평가 → EX-143 256경기, 보고, 뷰어, 봉인
- [x] EX-142 학습(GPU1) → 평가 → EX-144 256경기, 보고, 뷰어, 봉인, 자원 반환
- [x] STATUS, catalog build/check (POKEMON_EXPERIMENTS·뷰어 변경일지는 미기록)

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| 파서 기본 출력 불변 | EX-071 10리플레이를 `early_history` 끔·켬으로 재생, 켬 쪽에서 새 필드를 뺀 스냅샷 비교 | 작업 로그 | 527/527 같음, 새 필드는 모두 T−4 이전 |
| 재파싱 의미 보존 | EX-071 전 행 재파싱, 선택 필드 외 스냅샷 필드 비교 | `laya-early-history/v1/parity.json` | 131,947/131,947 일치(198초) |
| 렌더러 규칙 | 사람 대전 126번 입력과 그 경기 기록으로 만든 `early_history` | `tests/test_compact_v6.py` 8건 | 통과 |
| 길이 | validation 512 실측 | `EX-141/diagnostics/measure`, `EX-142/diagnostics/measure` | v6s 최대 981 / v6h 최대 2,047. 형식 동결 |
| 오프라인·서빙 일치 | `v6 parity` 512행(각 변형) | `EX-141/diagnostics/parity.json`, `EX-142/diagnostics/parity.json` | 둘 다 512/512 일치 |
| 실전 입력 | EX-143·EX-144 mock | `EX-143/mock`, `EX-144/mock` | 4/4 정상·감사 통과. v6ht만 `early_history`(최대 163이벤트, 마지막 결정 기록 21턴), 서빙 한도 v6st 1,024·v6ht 2,048 |
| 기존 검사 | `pytest integration/laya_imitation/tests`, imitation 파서 검사 | — | 107 통과·4 건너뜀, 40 통과 |

## 진행

- 2026-10-29 — 계획 등록. 파서 opt-in 필드·재파싱·렌더러·사전 측정 완료.
- 2026-10-29 — 자료 생성(v6s 약 1분, v6h 약 3분, CPU 32). v6h 학습 자료 전체 토큰 p50 1,359·p95 2,040, 기록 턴 p50 19·최대 76.
- 2026-10-29 — 첫 mock이 시작 전 자격 검사에서 멈췄다(`pokemon-showdown worktree is dirty`). 원인은 시나리오 서버 실행 때 Showdown이 다시 쓴 채팅 플러그인 상태 파일 2개(`config/chat-plugins/mafia-logs.json`, `seasons.json`, 월 변경)였다. 커밋된 내용으로 되돌리고, 실패 기록은 `EX-143/diagnostics/mock-v1`, `EX-144/diagnostics/mock-v1`에 보존한 뒤 mock을 다시 돌려 통과했다. 연결 실행은 배틀 준비 직전에 이 두 파일만 바뀐 경우 되돌리고, 다른 변경이 있으면 멈춘다.
- 2026-10-29 — 연결 실행 `scripts/laya-imitation-ep221` 시작(GPU0 v6s 레인, GPU1 v6h 레인). 로그 `runs/model-training/EP-221-chain.log`, `EP-221-v6s.log`, `EP-221-v6h.log`.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 결함 복구와 중단은 EX-141~144를 참조한다. 자동 재실행은 없다. 연결 실행 스크립트는 단계가 실패하면 그 자리에서 멈춘다. 두 연결 실행이 같은 코드를 쓰므로, 실행 중에는 `integration/laya_imitation`과 worker가 import하는 코드를 수정하지 않는다(배틀 `execute`는 `prepare` 때의 소스 해시를 확인한다).

## 결과 및 증거

- 2026-10-30 — 연결 실행 완료(두 레인 모두 status 0).

| 실험 | 결과 |
|---|---|
| EX-141 v6s 학습 | 33,812초, 선택 epoch 2. 잠긴 test NLL 1.4286(EX-136 1.4358), 차이 −0.0073 [−0.0286, +0.0140], 일치율 +2.15%p |
| EX-142 v6h 학습 | 95,024초(26.4시간), 선택 epoch 3. NLL 1.4186, 차이 −0.0173 [−0.0443, +0.0096]. 교체 행 −0.0683 [−0.1185, −0.0186] |
| 반복 확률(두 학습) | 사람이 다른 수를 고른 행에서 같은 기술 확률 v5t 0.288 → v6s 0.306, v6h 0.311. 줄지 않았다 |
| EX-143 v5t 대 v6st | 퇴보를 배제하지 못함, −0.023 [−0.102, +0.055], 109-19 대 106-22 |
| EX-144 v5t 대 v6ht | 퇴보를 배제하지 못함, −0.063 [−0.141, +0.016], 109-19 대 101-27, 5턴 이상 반복 56 → 109 |

- 결론: 과거 턴 정보(요약·긴 기록)는 같은 기술 반복을 줄이지 못했고 Abyssal 상대 성적도 개선하지 못했다. v6h는 교체 결정의 사람 선택 재현만 나아졌다.
- 실전 팀 비교는 [EP-222](EP-222-laya-play-teams-abyssal-battle.md)로 이어진다.
