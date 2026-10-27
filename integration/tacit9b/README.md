# Tacit-9B 수행 모델 연결

[EX-104](../../project_context/research/planner-executor/experiments/EX-104-tacit-thinking-low.md)의 고정 모델
`morriszjm/Tacit-9B@884838f1698d1fd746625b3c20c8ec2be077a183`을
공유 `jev-planner` 실행기에 연결한다. 실행 승인·한도·중단 기준은 EX-104가 소유한다.

`executor.model: tacit9b`는 `planner-ex104` 자원 프로필과
`.pokechamp-data/tacit9b-runtime/.venv/bin/python`을 사용한다. GPU0 단독·BF16·SDPA이며
GDN과 causal convolution은 설치된 Transformers의 Torch 원함수를 사용한다.
선택적 외부 커널 dispatch는 해제한다. 모델·tokenizer·공식 소스는 같은 runtime의 `model/`에
보관하며, `download.verify()`의 공식 파일 검증을 적재 전에 수행한다.

다후보 입력마다 공식 첫 판단을 기록한 뒤 항상 thinking을 생성하고 최종 라벨 분포를 읽는다.
첫 판단은 thinking 입력에 주입하지 않는다. 후보의 원 ID·순서·객체와 전체 상태·지시문을
보존하며 첫 판단/생성 프롬프트를 각각 32768토큰 이내로 검사한다. 생성은 최대8192토큰,
최종 판독은 공식 decode→마감→reencode 경로와 native 문맥한도262144를 따른다.
단일후보 무호출과 논리 pipeline 중복 방지는 공유 실행기·서버가 담당한다.

Seed는 `model`을 포함한 실제 wire payload를 키 정렬 없이
`json.dumps(..., ensure_ascii=False, separators=(',', ':'), allow_nan=False)`로 직렬화한
UTF-8 바이트의 SHA-256 앞8자리 정수다. 생성 조건은 temperature0.6/top_p0.95/top_k20이다.
`thinking`에는 원 token ID·텍스트·마감 텍스트·seed·자연/길이/EOS 종료를 보존한다.
`stages`는 첫 판단·생성·최종 판독의 프롬프트 길이·실제 forward 수·실제 처리토큰·지연을 담는다.
`usage.input_tokens`는 세 단계 프롬프트 길이의 합이고, `processed_input_tokens`는 cached decode를
포함한 실제 forward 입력토큰 합이다. `usage.output_tokens`는 실제 생성토큰 수다.
원 forward 증거는 serving 디렉터리의 `tacit-forward.jsonl`에 기록한다.

사전검사는 같은 서버에서 고정8회 반복 선택 gate를 먼저 적용한다. 통과 후 EX-103의
2·5·6턴 고정입력3회를 진단하며 `diagnostic-results.json`에 원입력·출처·응답을 남긴다.
11회 모두 공유 논리 호출 예산에 포함한다. 확률 차이는 진단이고 고정3사례의 선택·자연종료는
품질 gate가 아니다. 상세 조건은 EX-104와 준비된 설정 원문을 따른다.

아래 명령은 CPU tokenizer·mock 검증이며 GPU 모델을 적재하거나 외부 API를 호출하지 않는다.

```bash
.pokechamp-data/tacit9b-runtime/.venv/bin/python -m unittest integration.tacit9b.tests.test_tacit_adapter -v
```

검증 범위는 공식 프롬프트/token ID 동치·입력/후보 보존·길이 거부·자연/강제마감·높은 확신에서도
thinking 수행·첫 판단 비주입·최종 선택/계측·8회 gate와3회 진단의 순서·서버 중복 재사용이다.
실제 모델 선택의 품질이나 GPU 실행 성공을 이 CPU 검사로 주장하지 않는다.

준비된 입력 파일의 두 프롬프트 길이는 다음 CPU 명령으로 확인한다.
`requests.json`에는 원 `state/questions` 요청 또는 그 목록을 넣는다.

```bash
.pokechamp-data/tacit9b-runtime/.venv/bin/python -m integration.jev_planner.tokens --model tacit9b --requests requests.json
```
