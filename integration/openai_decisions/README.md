# OpenAI Decisions API 실행 환경

`gpt-6-luna`의 `POST https://api.openai.com/v1/decisions`를 호출하는 독립 Python 환경이다.
[공식 문서](https://developers.openai.com/api/docs/guides/decisions)의 HTTP 형식을 사용한다.
OpenAI SDK 버전에 의존하지 않고 `httpx`로 직접 요청한다. 기존 배틀 환경과 분리되어 있다.

## 키 입력과 실행

루트 `/workspace/.env`에 다음 항목의 값을 입력한다. 기존 다른 항목은 유지한다.

```dotenv
OPENAI_API_KEY=여기에_실제_API_키
```

`.env`는 Git에서 제외되며 권한은 `600`이어야 한다. 프로세스의 `OPENAI_API_KEY`가
파일보다 우선하며 명시적 빈 값도 우선한다. 파일의 변수 확장과 shell 실행은 하지 않는다.

```bash
cd /workspace
# 키 없이 요청 형식 확인 (외부 호출 없음)
scripts/openai-decisions --dry-run
# 기본 predicate 예제 실제 호출 1회 (API 요금 발생 가능)
scripts/openai-decisions
# 다른 질문 형식
scripts/openai-decisions --request integration/openai_decisions/examples/choice.json
scripts/openai-decisions --request integration/openai_decisions/examples/score.json
```

사용자 JSON은 예제를 복사해 `input`, `questions`를 편집하고 `--request`에 전달한다.
텍스트 외에 공식 API의 이미지 메시지 배열도 전달 가능하다. 로컬에서는 필수 형식만 확인하며
세부 스키마 유효성은 서버가 판정한다. 결과 JSON 전체(`answers`, 확률, `usage` 등)는 stdout에
출력하므로 필요하면 `> result.json`으로 저장한다. `refusal`은 원형 그대로 반환한다.

## 환경 재설치와 검증

```bash
bash integration/openai_decisions/setup.sh
.tools/openai-decisions/.venv/bin/python -m unittest integration.openai_decisions.test_client -v
```

설치 위치는 `.tools/openai-decisions/.venv`, 의존성은 `requirements.txt`에 고정한다.
HTTP timeout은 60초, 자동 재시도와 redirect는 없다. 오류 시 종료 코드1이며 응답 오류 본문과
키는 출력하지 않는다. 401은 키, 403/404는 모델/API 접근 권한, 429는 사용 한도·결제를 확인한다.
실제 API/계정 권한은 키 입력 후 첫 호출로 확인해야 한다. 이번 환경 구성에서는 실 API를
호출하지 않았으며 배틀 평가·학습·모델 성능은 검증하지 않았다.

근거: [EP-178](../../project_context/exec-plans/completed/EP-178-openai-decisions-environment.md).
