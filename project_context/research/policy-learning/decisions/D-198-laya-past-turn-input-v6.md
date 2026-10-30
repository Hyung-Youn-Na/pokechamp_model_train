# D-198 — laya 과거 턴 입력 두 가지(v6s 반복 표시·v6h 긴 기록 2048토큰) 동시 학습과 배틀

- 상태: Accepted
- 날짜: 2026-10-29

## 맥락

- **사람 대전**(`/workspace/data/NHJ-20261029`, v4t, 4경기 NHJ 3승 1패): 진 세 판의 공통 패턴은 상대가 회복하거나 내구를 쌓는 동안 같은 수를 3~7턴 반복한 것이다.
  - 126번 T13~19: Ting-Lu가 Body Press·Roost Corviknight에게 Ruination을 7턴 연속 썼고 쓰러졌다. 125번 T10~12도 같은 대면에서 3턴 연속이었다.
  - 124번 T18~20: Hydreigon이 Body Press에 매번 깨지는 Substitute를 3번 썼다. 123번 T28~30: Deoxys가 Slack Off Slowking에게 Knock Off를 3번 썼다.
  - v4 확정 실패 표시는 통했다. 실패·무효로 표시된 선택지가 있던 결정 34개 중 그 선택지를 고른 것은 0개다. 반복은 실패가 아니므로 이 표시로 잡히지 않는다.
- **시나리오 대전**(2026-10-29, `b126t13`): v5t도 같은 국면에서 Ruination을 골랐다(0.38). 사람 리플레이(gen9ou 약 6,200판 중 Ting-Lu 대 Corviknight 대면 104판·206회)에서 Ruination 3연속 이상은 2회뿐이고, 둘 다 예외적 상황이었다(HP 4~11%, Body Press 없는 Corviknight). Corviknight가 막 들어왔을 때 사람의 첫 수는 교체 41%, Ruination 18%였다.
- **입력 구조**: 스냅샷은 최근 4턴 기록만 담는다(`schema.py`). 렌더러는 그중 직전 1턴만 텍스트로 넣는다(`compact.py` `HISTORY_TURNS = 2`). 그래서 같은 수를 몇 번 썼는지, 그동안 상대 HP가 어떻게 오갔는지가 모델 입력에 없다.
- **길이**: v5 입력은 전체 1,024 중 validation 최대 945, 실전 175결정 최대 916토큰이다. 직전 1턴 기록은 평균 44, 최대 100토큰이다. 기록을 4턴으로 늘리면 최악 약 1,200토큰이 되어 1,024를 넘는다.
  - 인코더(ModernBERT-large)는 위치 8,192까지 지원한다. 1,024는 학습 설정값이다.
  - 선택지 한 줄 48토큰은 laya 라이브러리 내부 상수(`laya/common.py`)다.
- **사용자 지시**(2026-10-29):
  1. 1,024 안에서 반복을 요약해 넣는 방법과, 입력 한도를 늘려 기록을 넣는 방법을 GPU0·1·2로 동시에 실험한다.
  2. 학습 시간 제한은 없앤다.
  3. 2번 실험은 토큰 여유가 있으면 4턴보다 이전 기록도 넣는다.

## 결정

1. **v6s(EX-141, GPU0, 1,024토큰)**: v5 모듈 전부 + `streaks` 모듈.
   - ME·OPP 줄에 그 활성 포켓몬이 직전 n(≥2)턴 연속 같은 기술을 썼으면 ` | streak <기술> x<n>`을 붙인다. 이어서 그 턴들이 끝날 때의 상대 활성 HP를 붙인다. 예: `streak ruination x4+ (opp hp 33>23>18>40)`.
   - 4턴 기록에서만 센다. 연속이 기록 창 시작까지 이어지면 `+`를 붙인다. 새 입력 필드는 없다.
   - 내 팀 벤치 압축은 넣지 않는다. validation 최대 981토큰으로 이미 한도 안에 들어가고, 넣으면 변수가 둘이 된다.
2. **v6h(EX-142, GPU1, 2,048토큰)**: v5 모듈 전부 + `longhist` 모듈.
   - 기록 줄을 직전 1턴에서 "전체 2,048 안에 들어가는 만큼"으로 넓힌다. 직전 턴부터 거꾸로 채우고, 들어가지 않는 가장 오래된 턴부터 뺀다. T−1과 T는 항상 남긴다.
   - 4턴보다 이전 기록은 파서의 opt-in 선택 필드 `early_history`(T−4보다 앞선 이벤트)로 받는다.
     - `replay.Timeline(early_history=True)`, `serialize_state(..., early_history=True)`, bridge 요청에 `early_history: true`가 있을 때만 생긴다. 기본 출력은 바이트 단위로 그대로다.
     - 스키마는 이 필드를 받되 4턴 창과 겹치지 않는지 검사한다.
     - 학습 자료는 EX-071 리플레이를 다시 파싱한 `laya-early-history/v1`(기존 필드 131,947/131,947 일치)에서 가져온다.
     - 배틀 워커는 v6h 모델(`laya-v6ht`, `-initial`) 쪽만 이 필드를 요청한다. 다른 모델의 입력은 바뀌지 않는다.
   - 길이 맞춤은 학습 자료 생성과 서빙이 같은 함수(`data_v6.fitter`, 같은 토크나이저)를 쓴다.
3. **공통 학습 설정**: EX-136과 같다(시작 모델 `e929ae5c`, 3 epoch, soft-CE, lr, seed 0, head 512, 테라 지식 train 57,143행, EX-071 분할). `max_len`만 v6h에서 2,048이다. **학습 시간 상한은 없다**(사용자 지시). 그 밖의 중단 조건(제외 비율 > 0.005, GPU 오류, parity 불일치)은 그대로다.
4. **평가와 배틀**(D-191, 오프라인 결과로 배틀을 거르지 않는다):
   - 잠긴 test로 EX-136과 같은 행을 비교한다. 핵심 보고 지표는 반복 표시가 있는 행에서 같은 기술을 또 고르는 확률이고, 사람이 다른 수를 고른 행과 또 쓴 행을 나눠 본다.
   - EX-143(GPU0·8107): v5t 대 v6st Abyssal 256경기. EX-144(GPU1·8109): v5t 대 v6ht 256경기. 판정은 EX-137과 같은 비퇴보 기준이다.
   - GPU2는 이번 연결 실행에서 쓰지 않는다. 두 학습이 끝난 뒤 직접 대결 등에 쓸 여유로 남긴다.

## 거절한 대안

- **v6s에 내 팀 벤치 압축 포함**: 반복 표시만으로 최대 981토큰이라 공간이 필요 없다. 넣으면 배틀 차이를 한쪽 효과로 나눌 수 없다.
- **1,024에서 원시 4턴 기록**: 최악 약 1,200토큰으로 한도를 넘는다. 상태 뒷부분이 조용히 잘린다.
- **laya `predict_long`(창 나눠 채점)**: 정책 결정은 현재 상태와 기록을 함께 읽어야 한다.
- **선택지 48토큰 상수 변경**: 라이브러리 계약 변경이다. 이번 질문과 무관하다.
- **v6h에 고정 턴 수(예: 8턴)**: 사용자 지시는 "여유가 있으면 더 이전도"다. 고정 턴 수는 짧은 경기에서 공간을 남기고 긴 경기에서 넘친다.

## 근거와 한계

- 두 변형은 같은 질문(과거 턴 정보가 반복을 줄이는가)에 다른 비용으로 답한다. 둘 다 v5t와 변수 하나 차이다(v6h는 한도와 기록 창이 함께 바뀌지만, 기록이 짧은 행은 한도만 다르고 출력이 v5와 같다).
- 반복 표시는 4턴 창에서 세므로 그보다 긴 연속은 `x4+`로만 보인다.
- v6h 학습은 입력이 평균 약 1.8배 길어 EX-136(약 9.4시간)보다 오래 걸린다.
- 단일 시드다.

## 영향

- 코드: `replay.py`·`schema.py`·`metamon_bridge.py`(opt-in 필드), `early_history.py`, `compact_v6.py`, `data_v6.py`, `evaluation_v6.py`, `training.py`(Spec `max_len`, `hours=None`), `policy.py`(체크포인트별 토큰 한도), `serving.py`·`comparison.py`·`battle.py`·`cli.py`, `tests/test_compact_v6.py`
- 자료: `laya-early-history/v1`, `laya-compact-imitation/v6s-all`, `v6h-all`
- 계획·실험: [EP-221](../plans/EP-221-laya-past-turn-input-v6.md), [EX-141](../experiments/EX-141-laya-v6s-streaks-training.md), [EX-142](../experiments/EX-142-laya-v6h-long-history-training.md), [EX-143](../experiments/EX-143-laya-v5t-v6st-battle256.md), [EX-144](../experiments/EX-144-laya-v5t-v6ht-battle256.md)

## 증거

- 사람 대전 분석과 시나리오: `/workspace/data/NHJ-20261029`, `/workspace/data/laya-scenarios.md`(`b126t13`, `b126t37`)
- 사람 리플레이 대면 집계: `/workspace/data/showdown-replays/raw` gen9ou(Ting-Lu 대 Corviknight 104판, 206회)
- 재파싱 일치: `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/laya-early-history/v1/parity.json`
- 사전 측정: `runs/model-training/EX-141/diagnostics/measure`, `EX-142/diagnostics/measure`(v6s 최대 981, v6h p50 1,220·최대 2,047, 기록 p50 15턴·최대 51턴)
