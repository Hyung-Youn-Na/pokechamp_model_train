# EX-021 독립 요약 harness 진단

D-023/C-015와 EP-012에서 승인한12장면×4조건×3반복을 위한 독립 진단 도구다.
현재 EX-021은144응답 수집 후 입력/기준 오류로 Blocked다. 아래 명령은 인터페이스 설명이며
실행된 디렉터리를 재제출할 수 없다. 새 Cloud 진단은 별도 결정이 필요하다.
운영 improved_io 경로, EX-020 halt/receipt/clock은 변경하지 않는다.

```bash
cd /workspace/pokechamp
PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.summary_diagnostics prepare /workspace/.pokechamp-data/summary-diagnostics/ex021
PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.summary_diagnostics run /workspace/.pokechamp-data/summary-diagnostics/ex021
PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.summary_diagnostics report /workspace/.pokechamp-data/summary-diagnostics/ex021
PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.summary_diagnostics report /workspace/.pokechamp-data/summary-diagnostics/ex021 --review /path/to/sealed-review.json
```

- `prepare`: EX-020 offline-v8 archive를 별도 subprocess에서 import한다. workspace resource
  위치만 원래 경로로 연결하며 현재 입력 생성 코드는 사용하지 않는다. 기존4쌍 prompt의
  UTF-8 byte 일치, 추가8경기의 기존 준비 자료 배제, actor seal 및 첫10행동 경계를 검증한다.
  원본 protocol, 독립 수기 `truth.json`과 `rubric.json`,48입력,144일정, source를 봉인한다.
- `run`: `verification.json`의 `passed=true` 및 동일 `manifest_sha256`가 있어야 Cloud에
  진입한다. 이 receipt는 regression/정적검사/fake 결과를 연결한 사전 검증 기록이다.
  실제 통과 확인 없이 발급하지 않는다. 테스트만 `--fake`로 별도 준비 디렉터리에서 실행한다.
  전체 runtime lock과 permit broker10/10을 공유하며 호출마다 새 process/backend/context를
  만든다. 계정 credential은 해당 worker에서만 읽는다. 출력 오류만 예정 표본 수집을 계속한다.
- `report`: 최초 호출은 조건명·비용·변환을 뺀 `blind.json`을 만든다. 검토자는 원본 protocol과
  별도 사실 기준을 읽고 각 응답의 사실 보존/오류/인용/주장 수를 기록한다. JSON은 기존
  `benchmark.seal_json`으로 봉인하고 `--review`로 연결한다. 별도 Cloud judge는 없다.
  형식검사와 근거/응답 hash를 확인한 뒤3반복 장면 평균과 완전 대응을 집계한다.
  입력/기준 실패 halt가 있으면 비용·실패 근거·미완료 분모만 보고하며 --review를 거부한다.

`STOP` 파일 또는 SIGINT/SIGTERM은 신규 admission을 중지한다. 진행 중 요청은 응답을
worker에서 먼저 봉인한 후 종료하며1시간 cleanup deadline에 소유 process만 kill한다.
45분/60분 시계는 영속적이다. coordinator가 유실된 실행을 다시 열면 재제출 없이 미확정
분모만 보존한다. 임의 실패 보충이나 출력 repair는 없다. 응답·검토·완료 collection을 덮어쓰지 않는다.

`truth.json`은 원본 이벤트/자기 request를 직접 읽어 작성한 평가 기준이다. `transforms.py`는
이를 import하거나 입력에 포함하지 않는다. 같은 전처리 오류를 정답으로 되풀이하지 않도록
테스트가 원본 행에서 턴/HP를 독립 대조한다. numeric state 주석은 pinned poke-env에서
설치 턴/겹 수/마지막 weather 이벤트 턴/경과 counter/존재 marker를 구별한다. `|request_delta|`는 원래 위치에서
initial/typed-path set/delete로 JSON 값을 복원한다. 원본 JSON의 lexical whitespace만
복원 동등성 검사에서 제외하며 비요청 protocol byte와 순서는 그대로 유지한다.


EX-021의 봉인된 과거 source는 weather 숫자를 activation_turn으로 잘못 해석한다.
실제 parser는 upkeep에도 self.turn을 저장한다. 로컬 교정은
last_weather_protocol_turn을 사용하며 실제 시작은 원본 weather 행의 턴에서 확인한다.
독립 수기 기준의 scene3 시작도 다음4턴 마커 이전3턴으로 교정했다. 과거 입력/기준/응답을
덮어쓰지 않으며 이 교정으로 EX-021을 유효 비교로 바꾸지 않는다.

수기 검토의 facts는 retained/incorrect/omitted status와 retained bool을 함께 기록한다.
incorrect는 해당 fact_ids를 연결한 원본 근거 오류를 요구하며 omission에는 포함하지 않는다.
retention은 incorrect와 omitted 모두에서 감소한다. 이는 사전 기준의 오류/누락 구분을
구현한 분석 집계 교정이며, invalidated EX-021의 효과를 다시 계산하지 않는다.


## EX-022 summary-thinking-v1

D-024/C-016 승인으로 상태 처리 정비 후 동일12장면·첫 요약의 low/high72호출을 지원한다.

```bash
cd /workspace/pokechamp
PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.summary_diagnostics prepare /workspace/.pokechamp-data/summary-diagnostics/ex022 --profile summary-thinking-v1
PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.summary_diagnostics run /workspace/.pokechamp-data/summary-diagnostics/ex022
PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.summary_diagnostics report /workspace/.pokechamp-data/summary-diagnostics/ex022 --review /path/to/sealed-review.json
```

새 profile은 운영 memory.summary_context를 사용한 장면당 하나의 원본 request 입력을
봉인한다. low/high는 같은 파일의 system/user byte를 전송한다. truth-thinking-v1.json과
rubric-thinking-v1.json은 원본에서 독립 작성하며 oracle이 원본 행/턴/actor/HP에 대조한다.
기존 profile의144 가정은 새 일정/분모/시계에 적용하지 않는다. 기본 prepare는 과거
summary-harness-v1 호환 경로다. 기존 EX-021의 봉인 manifest/보고서와 halt 차단을 유지한다.
FixedBackend(summary_thinking_effort="high")는 summary/summary_rollup만 high로 요청하며
기본 및 self_action은low다. 잘못된 값은 client 생성/네트워크 전에 거부한다.
