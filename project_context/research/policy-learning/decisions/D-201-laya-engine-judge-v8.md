# D-201 — laya 실패 표시를 고정 Showdown 엔진 판정기로 바꾼 렌더러 v8

- 상태: Accepted
- 날짜: 2026-11-02

## 맥락

- **실패 기술 조사**(EP-223 진행 기록, `exec-plans/evidence/ep223/fail-survey/`): EP-221~223 배틀의 모델 기술 68,414회 중 2,514회가 실패·무효였다. 현재 규칙(`effect_knowledge.option_outcomes`)이 미리 `fails`로 표시한 것은 678회다. 표시하지 못한 1,833회 중 448회는 스냅샷으로 판정 가능한데 규칙에 없는 경우다(마지막 한 마리에게 Roar·Whirlwind 176, Defog 무효 83, Wish 대기 중 재사용 67, 이미 행동한 First Impression·Fake Out 37, Future Sight 중복 34, Taunt 중복 20 등). Protean·Libero 행은 v4~v6에서 표시가 통째로 꺼진다(v7은 압정만 보정).
- **EX-150**: v7t는 비퇴보였지만 실패 기술이 86 → 171로 늘었다. 표시 없는 실패는 규칙 공백이었다.
- 고정 엔진 오라클(`effects_oracle.cjs`, 1대1)은 지식 카드 검증에만 쓰였다. 벤치와 기록 의존 상태가 없다.
- **사용자 지시**(2026-11-02): 엔진 판정기를 만들어 실전 기록으로 먼저 검증하고(정밀도 99% 이상), 통과하면 v8 학습·배틀까지 별도 승인 없이 진행한다. 학습 시간 상한은 없다.

## 결정

1. **엔진 판정기**(`integration/laya_engine/`, 새 디렉터리, laya_imitation 해시 범위 밖):
   - 입력은 serving과 같은 `ImitationInput`(item_state 반영 view)뿐이다. 파서는 바꾸지 않는다(4턴 `history`로 충분했다).
   - 고정 엔진(`/workspace/pokemon-showdown/dist/sim`, e64915c0e)에 6대6 국면을 세운다: 양 팀 전원의 종·HP·기절·상태이상(수면·맹독 카운터)·테라, 활성의 능력 랭크·휘발 상태, 진영 상태(층수), 날씨·필드, 기록에서 복원한 상태(등장 후 행동 여부, Protect 연속, 직전 Destiny Bond, Wish·Future Sight 대기, 상대 직전 기술, Protean·Libero 사용).
   - 숨은 정보: 상대 활성의 미공개 특성은 종의 모든 특성, 미공개 아이템은 없음·일반 아이템 1개·판정에 영향을 주는 usage 아이템(≥0.005)을 모두 대입한다. 관측 상태와 모순되는 특성(화상인데 Water Veil 등)은 뺀다.
   - 상대의 이번 턴 행동: 변화기(아무 효과 없음)와 공격(상대 선공)을 기본으로 하고, 공개된 상대 기술 전부(상대 선공), 미공개 칸이 남으면 usage상 그럴듯한(≥0.05) Roost(땅 기술)·압정 설치(Defog류)·압정·벽 제거(내 설치기)를 더한다. Sucker Punch·Counter·Encore 같은 반응형 기술은 물리·특수·선제 공격 × 두 속도 순서를 모두 본다. 상대 교체·교체 기술·강제 교체·자폭은 다루지 않는다. 상대의 같은 턴 테라도 다루지 않는다(교체와 같은 상대 선택).
   - 난수는 가장 유리하게 둔다: 명중·마비·혼란은 다른 시드로 재시도, 혼란은 다음 행동에 풀림, 얼음은 녹는 경우, 대타 HP 1, 수면은 계속 자는 경우와 깨는 경우. 기술이 실행되지 않는 경우는 판단에서 뺀다(실제 기록에도 `|move|`가 없다).
   - 모든 경우에 실패(`fails`·`immune`·`absorbed`·`reflected`)일 때만 확정 실패다. 피해가 들어가고 부가 효과만 막힌 경우는 표시하지 않는다.
   - 확률 실패(Protect 연속, 깨어날 확률 1/2 이상인 Sleep Talk·Snore)는 `likely fails`로 따로 기록만 한다.
2. **검증(EX-151)**: 9개 실행의 모든 모델 기술 사용, EX-071 사람 리플레이 전체. 정밀도 99% 미만이면 3단계로 가지 않는다.
3. **렌더러 v8(EX-152)**: v7 모듈 전부. 선택지의 `; fails`/`; bounced` 표시만 판정기 확정 실패로 바꾼다. 판정기가 국면을 재현하지 못한 선택지(엔진 오류)는 기존 규칙 표시를 쓴다. `likely fails`는 표시하지 않는다(EX-151에서 실제 실패 132/176, 75%). 시작 모델·설정·분할·테라 지식 행은 EX-149와 같다. GPU1, 학습 시간 상한 없음.
4. **배틀**: D-191에 따라 오프라인 결과와 관계없이 둔다.
   - EX-153: v7t 대 v8t, EX-120 일정 256경기 대 Abyssal(GPU1·8109). EX-150과 같은 비퇴보 기준(margin 0.05).
   - EX-154: v8t 대 v7t 직접 대결 128경기(GPU2·8108, headtohead 방식, 0.5 비교).
   - 둘 다 mock을 먼저 돌린다. 리포트에 실패 기술 수를 v7t와 비교한다.
5. **보존**: `serving.V7_RENDER_FILES` 전체를 바이트 단위로 유지한다. v8 렌더 파일(`V8_RENDER_FILES`)은 laya_imitation의 v7 파일과 판정기 파일(`judge.cjs`·`judge.py`·`state.py`·`render_v8.py`·`data_v8.py`)이다. laya_imitation·파서·`scripts/laya-imitation` 수정은 `.pokechamp-data/battle-window/`에 다른 세션의 표시 파일이 없을 때만 한다.

## 추가 결정(2026-11-02, 사용자 지시)

- `likely fails`까지 `; likely fails`로 표시한 변형 v8l을 따로 학습한다([EX-155](../experiments/EX-155-laya-v8l-likely-fails-training.md), GPU2). v8(EX-152)의 표시·파일은 그대로다. GPU2는 EX-155 학습을 먼저 하고 EX-154는 그 뒤에 둔다. 이어진 사용자 지시로 v8t 대 v8lt Abyssal 256경기([EX-156](../experiments/EX-156-laya-v8t-v8lt-battle256.md), GPU1·8109, EX-153 뒤)를 예약했다.

## 거절한 대안

- **effect_knowledge 규칙 추가**: 규칙이 늘수록 엔진과 어긋날 곳이 늘고, 바이트 동일성 때문에 v4~v7 서빙이 거부된다. 엔진 자체를 판정 근거로 쓴다.
- **상대 행동을 변화기·공격 두 가지만**: 첫 검증에서 정밀도 92.6%였다. 틀린 사례는 거의 모두 상대 선공(압정 설치 뒤 Defog 성공, 피격 뒤 만피 회복기 성공, Protect)이었다.
- **상대 테라 고려**: 같은 턴 테라로 틀린 경우는 배틀 2건, 사람 4건이다. 고려하면 타입 무효 판정 대부분이 사라진다. 상대 교체처럼 선택 문제로 둔다.
- **`early_history` 요청(파서 opt-in)**: 4턴 밖 정보가 필요한 오판이 없었다. 서빙 요청을 바꾸지 않는다.

## 근거와 한계

- 사람 리플레이의 자기 세트는 추정값이라 판정 입력이 틀릴 수 있다(EX-151: Liquid Voice·Infiltrator·Eject Button 9건). 실전 서빙은 자기 세트가 정확하다.
- 상대가 usage에 없거나 확률이 낮은 기술로 국면을 바꾸면 틀릴 수 있다.
- 단일 시드 학습이다.

## 영향

- 새 코드: `integration/laya_engine/`(`judge.cjs`, `state.py`, `judge.py`, `validate.py`, `store.py`, `render_v8.py`, `data_v8.py`, `evaluation_v8.py`, `tests/`), `scripts/laya-imitation-ep224`
- 수정: `integration/laya_imitation/`의 `config.py`, `serving.py`(모델·렌더러), `training.py`(Spec), `cli.py`, `comparison.py`(Study·렌더러), `headtohead.py`(Study·뷰어 렌더러)
- 자료: `laya-engine-judge/v1`, `laya-compact-imitation/v8-all`
