# Tacit-9B 외부 vLLM 연결

[EX-105](../../project_context/research/planner-executor/experiments/EX-105-tacit-vllm-low.md)의 `executor.model: tacit9b-vllm`은
사용자가 기동한 `http://127.0.0.1:18847/v1`의 `tacit9b`에 연결하는 CPU 프런트다.
외부 GPU1 서버를 적재·재시작·종료하지 않는다. 원 실행 EX-104의 소스·산출물은 보존한다.

`config.model_spec()`은 `planner-ex105` 프로필과 기존 Tacit tokenizer 환경을 연결한다.
적재 전 부모가 저장한 `serving/external-identity.json`의 PID/startticks·명령·model/revision·
49152 문맥한도·GPU1 및 실제 서버 응답을 검사한다. 각 외부 요청 전후에도 프로세스 identity를
확인한다. 공유 실행기는 외부 process tree/GPU 사용량을 감시하며 소유 CPU 자원만 반환한다.

공식 첫 판단 → 항상 thinking → 최종 후보 판독을 원순서로 수행한다. EX-104의 공식 프롬프트,
후보 ID/객체 무손실 보존, 두 초기 프롬프트32768 한도, decode→마감→reencode를 재사용한다.
HTTP prompt는 token ID 목록이며 서버가 반환한 prompt token ID도 원입력과 일치해야 한다.
모든 후보 label token ID를 `logprob_token_ids`로 명시하고 후보 누락을 거부한 뒤 후보 간 정규화한다.
상위 후보 근사나 임의 선택 보정은 없다. 첫 판단을 thinking 입력에 주입하지 않는다.

각 pipeline은 외부 HTTP3회다. 두 판독은 `max_tokens: 1`·`logprobs: 1`·전체 후보 ID를 사용하며
실제 생성한 판독 token2개도 `usage.output_tokens`에 포함한다. thinking은8192토큰 한도와
0.6/0.95/20 sampling, `</think>` stop 포함 반환, special token 보존을 사용한다.
Seed는 model을 포함한 canonical wire payload의 SHA-256 앞8자리 정수이며 세 단계에 기록한다.
외부 POST 자동 재시도는0회, 전체 외부 POST 한도는768회다. 공유 프런트의 같은 request ID
재조회는 완료된 pipeline 응답을 반환하므로 외부 추론을 반복하지 않는다.

`tacit-http.jsonl`은 POST 전에 요청을, 파싱·검증·매핑 전에 raw HTTP 응답을 fsync한다.
응답 `stages`에는 prompt/output token ID·전체 후보 logprob·usage·지연·HTTP 수를 담는다.
`thinking.token_ids`는 thinking 생성만, `usage.output_tokens`는 판독2개를 포함한 총출력이다.
`physical_forward_calls`, `processed_input_tokens`, allocator는 직접 관측 불가이므로 null이며
`measurement_unavailable_reason`에 이유를 남긴다. HTTP3회를 physical forward3회라고 표시하지 않는다.

사전8회 반복 선택 gate를 통과한 뒤 고정3사례를 진단하고 같은 서버를 실제1경기에 사용한다.
사전11회도 공유 논리 요청 예산에 포함한다. 조건·중단·해석의 원문은 EX-105다.

다음 검증은 CPU tokenizer와 mock HTTP만 사용한다. 외부 서버 추론·GPU 연산을 수행하지 않는다.

```bash
PYTHONDONTWRITEBYTECODE=1 .pokechamp-data/tacit9b-runtime/.venv/bin/python -m unittest integration.tacit9b_vllm.tests.test_adapter -v
```

공식 양쪽 프롬프트/token ID/label 동치, 전체16후보 정규화, 높은 확신에서도 thinking 진행,
첫 판단 비주입·최종 선택, 자연/길이/EOS 마감, 판독 출력량 포함 usage, null 계측,
누락 후보/변조 prompt 거부·오류 raw 보존·재시도0, 예산/문맥한도와 프런트 중복 재사용을 검사한다.
실제 모델 판단의 품질과 외부 서버 실행 성공을 CPU 검사로 주장하지 않는다.
