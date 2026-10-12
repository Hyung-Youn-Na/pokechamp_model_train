# 공식 클라이언트 관측

Gen9 OU singles의 새 B/B2 준비는 `official-client-v1`을 명시적으로 봉인한다.
과거 설정의 `observation_backend` 부재는 `legacy-poke-env`이며, 과거 EX 지정과
명시적 legacy 선택은 기존 의미를 유지한다. 준비 기본값의 원문은
`observation.PREPARATION_DEFAULT`다. 낮은 수준의 범용 `battle_prompts.DEFAULT_VERSION`은
legacy 호출 호환을 위해 v1.3.0이며 공식 준비는 v1.4.0을 명시적으로 선택한다.

`runtime.OfficialClient`는 actor별 Node 프로세스, battle별 증분 상태를 가진다.
공통 수신기의 실제 행 순회가 결정 경계를 갱신한다. `normalize`는 공식 공개 상태와
같은 경계의 자기 request/제출 세트·명시적 원문 이력만 받으며 `poke_env.Battle`은 받지 않는다.
이 단일 관측에서 prior·계산·B/B2를 만든다. 공식 후보의 숫자 슬롯이 실제 제출까지 유지된다.
`observation_snapshot` → `input_snapshot` → `llm_call` → `wire_action`이 경계와 원문을 연결한다.

설명서 v1.4.0과 B2 `b2-official-v1`은 관측 출처·미확인 값·효과 presence/배열/기간을 정의한다.
최근10결정 창의 첫 프레임이 행 중간에서 잘리면 `line_offset`으로 원래 행 좌표를 보존한다.
계산 의미 `calculator-input-v2`와 계산 수식·지원 범위는 유지한다. 미지원 Transform·효과,
외국 request, 누락/변경/역행한 경계, 빌드 불일치, Node 종료/기한 초과는 입력을 중단한다.
legacy 자동 대체는 없다.

## 빌드와 검증

공식 client commit은 `f2faebd6892b314d785a0038f77309afed36970c`, 서버 commit은
`e64915c0eab066db1d3e732b1280386468dd7415`다. `.artifacts/ep055/client`의 고정 checkout과
설치 의존성, 현재 서버 dist의 공개 Dex를 사용한다. upstream 갱신 스크립트는 실행하지 않는다.
로컬 빌드 기본 위치는 `.artifacts/official-observation/v1`이다. 빌드 산출물·TS 원문·lockfile·
설치 의존성·서버 dist를 `build-identity.json`과 대조하며 검사를 건너뛰는 운영 옵션은 없다.
클라이언트의 라이선스 원문과 각 source header는 해당 checkout/생성 client.js에 보존한다.

저장소 루트에서:

```bash
PYTHONPATH=/workspace:/workspace/pokechamp pokechamp/.venv/bin/python -m integration.pokechamp.observation.build verify
PYTHONPATH=/workspace:/workspace/pokechamp pokechamp/.venv/bin/python -m integration.pokechamp.team_preview_study prepare --directory /tmp/new-official-b2 --transport fake
```

새 디렉터리로 빌드하려면 `observation.build build <새 경로>`를 사용한다. 기존 산출물은 덮어쓰지
않는다. 환경/빌드 불일치를 통과시키려고 identity를 자동 갱신하지 않는다.
`python -m integration.pokechamp.observation.schema`는 보존된 v1.3 catalog로부터 이번 설명서만
재생성한다. 기존 버전 자산은 수정하지 않는다.

## 검증 기록

[EP-056 한국어 보고서](../../../project_context/exec-plans/evidence/ep056/report.md)에
100개 보존 결정 재생, 독립 원문/실패 회귀, 두 실제 로컬 경기, 전송/제출 감사와 viewer를 연결한다.
`diagnostics.official_observation`은 별도 출력 디렉터리로 보존 자료를 재생한다.
`diagnostics.official_local`은 두 경기를 만드는 실행기다. EP-056의 승인된 두 경기는 이미 소진했으며
검증을 다시 보기 위해 재실행하지 않는다. 보존된 결과와 source 봉인을 읽는다.
지연·메모리는 기능 계측이며 승률·모델 판단·L1–L5 효능의 증거가 아니다.

## 비동기 완료 경계

D-068/EP-058 연결부는 공식 `atqueueend`와 queue 위치가 일치할 때까지 정상 타이머 실행을
기다린다. headless stub의 `interruptionCount=NaN`을 실제 scene과 같은 초기 카운터1로
설정하여 공식 타이머가 취소된 것으로 오인하지 않게 한다. upstream/build·공식 시계는 유지한다.
자기 request 정규화 전에 앞선 로그를 완료하며 마지막 행 종료 처리도 기다린다.
Node 명령은 직렬이고 타이머 예외/기한 초과는 실패 응답·부분 상태 폐기·프로세스 종료다.
Python snapshot은 동기식이며 요청 전체30초 한도를 유지한다. 실패 계측은 성공 지연과 분리한다.

`diagnostics.official_async_delay.cjs`는 독립 오프라인 검증용 preload다. 실제 wall-clock 지연을
주어 공식 타이머를 유도하며 운영 기본 실행에는 연결되지 않는다.
`diagnostics.official_async_local --output <새 경로>`는 EP-058에서 승인된 별도
`ep058-local-eight` identity의 실제 coordinator/worker·공식 관측·계산·모의 HTTP 검증이다.
후속 공급자별 첫4행(총8경기)을 한 번씩 실행하며 경기1200초·전체1800초 중 마지막60초를
정리에 남긴다. cloud에서 거부하고 본실험 첫4 gate receipt를 만들지 않는다.
EP-058 검증 결과는 [보고서](../../../project_context/exec-plans/evidence/ep058/report.md)를 따른다.
