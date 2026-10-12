# 플레이어별 관측 추적 비교 (EP-055)

목표·실행 한도·완료 판단은 [EP-055](../../../project_context/exec-plans/completed/EP-055-observation-tracker-comparison.md),
결과는 [한국어 보고서](../../../project_context/exec-plans/evidence/ep055/report.md)를 따른다.
기존 parser·B2·에이전트 입력 인터페이스는 변경하지 않는다. 모델 호출은 없다.

## 명령

실행 환경은 기존 `pokechamp/.venv`와 Node를 쓴다. Python 명령은 `pokechamp/`에서 실행하고
`PYTHONPATH=/workspace:/workspace/pokechamp`를 지정한다. 아래 `/workspace`는 저장소 절대 경로다.

공식 클라이언트 checkout은 `.artifacts/ep055/client`에 있으며 커밋은
`f2faebd6892b314d785a0038f77309afed36970c`다. checkout 안에서
`npm ci --ignore-scripts --no-audit --no-fund`로 lockfile 의존성을 설치했다.
공식 `build`/`build full`/`build-indexes`는 실행하지 않는다. 서버 갱신 없이 TS를 변환한다.

```sh
# 저장소 root: OUTPUT은 존재하지 않는 디렉터리여야 한다.
node integration/pokechamp/diagnostics/observation_client.cjs build \
  .artifacts/ep055/client pokemon-showdown .artifacts/ep055/NEW-build

# pokechamp cwd: 보존된 플레이어 bundle을 읽기 전용으로 비교한다.
PYTHONPATH=/workspace:/workspace/pokechamp .venv/bin/python \
  -m integration.pokechamp.diagnostics.observation_compare \
  /ABS/PLAYER_BUNDLE /ABS/NEW_COMPARISON_OUTPUT \
  --build /workspace/.artifacts/ep055/build-v2 \
  --boundaries /workspace/.pokechamp-data/observation-comparison/ep055/p1.boundaries.jsonl
```

EX-044 bundle에는 `--boundaries`를 생략한다. 당시 `decision_start`와 request/preview trigger를
찾고 **당시 전체 상태 snapshot과 재생 상태가 같은지** 검사한다. 당시 LLM 선봉은 snapshot이
전체 상태가 아니므로 저장된 명시적 cutoff와 `team_preview.build_input`의 전체 재생 일치로 검증한다.
상태 비교와 선봉 입력 재생 검증은 `boundary_method`로 구분한다.

수집에 사용한 명령은 다음과 같다. EP-055의 승인된 **1회는 이미 실행 완료**했다.
이 명령 설명은 추가 경기 승인이 아니다. 존재하는 출력 경로는 거절한다.

```sh
PYTHONPATH=/workspace:/workspace/pokechamp .venv/bin/python \
  -m integration.pokechamp.diagnostics.observation_run run \
  /workspace/.pokechamp-data/observation-comparison/ep055 --port 8100
```

수집기는 기존 `benchmark.worker`, `BattleServer`, `BattleRecorder`를 재사용한다.
두 actor는 독립 프로세스·RNG·request를 갖는다. 진단용 list cursor는 upstream의 실제 메시지
순회 위치만 관찰하고 입력·선택·메시지 내용·난수 소비를 바꾸지 않는다.
부모가 서버 시작부터600초를 제한하며 오류/기한 시 기록·취소 표시를 남기고 소유 자원만 정리한다.
새 경기·자동 재시도는 없다.

## 공식 클라이언트 어댑터

공식 `Battle`, `BattleSceneStub`, `BattleChoiceBuilder`를 실행한다. 최신 브라우저 코드를
Node에서 쓰기 위해 Babel로 TS와 import/export를 제거하며, 상태 추적 알고리즘은 수정하지 않는다.
`battle-animations`는 공식 상태 animation 식별자 사전을 제공하고 화면은 생성하지 않는다.
초기화에 필요한 `$.easing` 저장소만 빈 객체로 제공한다. 네트워크·DOM·행동 선택은 없다.
`fixRequest`/`myPokemon`/`setViewpoint` 호출은 공식 `panel-battle.receiveRequest`의 데이터 경로와 같다.
행동 후보는 Gen9 singles UI 조건(기절·trapped·disabled·PP·테라)을 적용하고 공식 choice builder로
각 후보를 검증한다. doubles, 과거 세대 특수 선택, 모든 UI 분기의 대체 구현은 아니다.

공개 Dex 데이터는 기존 고정 서버의 `dist/sim/dex`에서 JSON으로 추출한다. 서버 경기 상태나
상대 세트는 포함하지 않는다. `provenance.json`에 클라이언트/서버 commit, Node/Babel, npm 의존성
트리·lockfile hash, 사용한 TS hash, 변환 결과·데이터 hash를 기록한다. 재생 전에 build hash를 검사한다.
upstream 라이선스는 checkout에 보존하며 생성된 upstream 코드/데이터는 무시되는 `.artifacts/`에만 둔다.

## 비교 JSONL과 판정

각 `comparisons.jsonl` 행은 `ep055-observation-v1`이다.

| 필드 | 의미 |
|---|---|
| actor / decision_seq / turn / request_id | 플레이어·결정 순번·표시 턴·자기 request ID |
| boundary | protocol event_seq와 0부터 시작하는 행 번호, 경계 검증 방법 |
| prefix_sha256 / alignment_verified | 두 추적기에 공통 제공한 prefix 및 경계 검증 |
| poke_env / official | 해당 prefix의 현재 parser와 실제 공식 클라이언트 상태 |
| b2_observation_projection | 현 `state.normalize`와 B2 exclusion으로 만든 관측·행동 후보·별도 prior |
| delivery_evidence | 새 경기의 미전송 투영 또는 EX-044 실제 전송 문자열과 관측/request/prior 일치 근거 |
| comparisons | 필드별 원값·정규화값·원문 판단·지식 출처·분류 |
| first_transition_difference | parser→B2, B2→공식 각각의 최초 의미 차이 |
| evidence | `received.jsonl`의 event/행·원문 hash·발췌 참조 |

수신 원문은 플레이어별 `received.jsonl`에 독립 보존한다. 자기 제출 세트와 그 플레이어가 받은
prefix만 B2 생성에 전달하며, 공식 클라이언트에는 그 prefix만 전달한다. 상대 private request는
두 재생 경계 모두에서 거절한다. manifest에 있는 상대 세트는 관측 생성에 사용하지 않는다.
예측용 `opponent_hypotheses`는 확인된 상대 정보와 별도로 출력한다.

B2 **관측 부분**의 투영이다. 계산기 실행·전체 damage prompt·전송·행동 선택은 수행하지 않는다.
원문의 `current_observation`, `request`, `opponent_hypotheses`는 실제 B2에서 계산 bundle 압축과
독립적이다. EX-044에서는 보존 `llm_call.user_prompt`의 이 세 필드와 일치를 추가로 확인한다.
선봉 시점에는 B2 battle 관측이 정의되지 않으므로 public preview를 두 tracker로 비교하고 B2를
`지원되지 않음`으로 기록한다. 자연 경기 기본 선봉이 자기 request보다 먼저 결정되는 사실을 유지한다.

- `일치`: 값·의미가 일치한다. 그 자체로 일반 정확성을 확정하지 않는다.
- `표현 차이`: 대소문자/이름, HP condition, stage 기본0, 기절 후 남은 slot/stage,
  Future Sight의 Pokemon effect/target history/side condition 등 의미를 정렬할 수 있는 차이다.
- `의미 불일치`: 세 경로 중 의미값 또는 원문 근거가 다르다. parser 차이가 B2에서 보완된
  경우도 포함하므로 전체 건수를 B2 입력 오류 건수로 해석하지 않는다.
- `지원되지 않음`: preview의 B2 battle 표현, 효과 시작 턴과 남은 기간 범위의 완전 동등성 등이다.

기절 후 `active`/boost는 원값을 보존하되 **현재 살아 있는 슬롯/적용되는 stage**로 정규화한다.
순서 없는 상대 preview 집합만 식별자로 직렬화 순서를 고정하며 자기 제출·request·행동 순서는 유지한다.
지연 공격은 caster 진영으로 연결하여 별도 비교한다. 자기 HP는 정확 request, 상대 HP는 공개된
분수 그대로이며 실제 분모를 복원하지 않는다. 단일 종 특성은 Dex 추론으로 표시하며 공개 확인과
같게 취급하지 않는다. 공식 tracker의 미확인 값과 B2 `ability_known`의 차이는 출처/확신도 차이이고
추론된 특성의 사실값이 틀렸다는 단정은 아니다.

## 검사

```sh
EP055_CLIENT_BUILD=/workspace/.artifacts/ep055/build-v2 \
PYTHONPATH=/workspace:/workspace/pokechamp .venv/bin/python -m pytest \
  /workspace/integration/pokechamp/tests/test_observation_comparison.py -q
```

공식 build가 없는 환경의 관련 통합 검사는 skip이며 통과로 세지 않는다.
본 작업은 실제 build로 모든 전용 검사를 실행했고 전체100개 결정의 반복 재생도 별도로 대조했다.
적용 사건·미검증 범위·초기 어댑터 및 판정기 수정 내역은 최종 보고서에 남긴다.
