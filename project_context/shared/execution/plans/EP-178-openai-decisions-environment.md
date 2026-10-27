# EP-178 — OpenAI Decisions API 환경

- 상태: Completed
- 생성일: 2026-10-20
- 승인 근거: 사용자의 Decisions 모델 API 환경 구성 요청. 키는 사용자가 `.env`에 입력한다.
- 관련: [D-163](../decisions/D-163-openai-decisions-environment.md), [INDEX 절차](../../../INDEX.md#workflow)
- 기준/실제 연구선: `research/model-training`, 시작 commit `a4659bf298c7935714f9fbd25246db2d831c5926`
- checkout: `/workspace`; 기존 다수 미커밋 변경 보존.
- interpreter: `.tools/openai-decisions/.venv/bin/python`; 새 코드 `integration/openai_decisions`, 실행기 `scripts/openai-decisions`.
- 검증: CPU 모의 HTTP·CLI 검사, 실 API 호출0. 기존 실험/평가 자료 열람·변경 없음.

## 목표·범위

루트 `.env`의 OPENAI_API_KEY로 gpt-6-luna의 POST /v1/decisions를 호출하는 독립 환경.
설치·예제·dry-run·오류 처리·문서 제공. 배틀 연결·평가·학습·유료 호출은 포함하지 않는다.
Active 색인의 기존 plan은 모두 배틀/학습/기존 공급자 범위이며 이번 독립 클라이언트와 겹치지 않는다.
기존 설정·환경·봉인과 Blocked/Paused 상태를 유지한다. `.env`의 기존 값은 출력하거나 덮어쓰지 않는다.

## 완료 기준·검증

- [x] 분리 환경 설치와 CLI 실행.
- [x] predicate/choice/score 예제와 사용자 JSON 입력 지원.
- [x] 환경 우선순위·파일 권한·키 누락·모의 성공/HTTP 오류 검사 통과.
- [x] 사용법·상태·색인 갱신. 실제 계정/모델 접근 권한은 미검증으로 명시.

## 진행

- 2026-10-20 — 승인 범위 등록. 비실험 작업이므로 실험 복구/시계/뷰어 요건 해당 없음.

## 결과 및 증거

- 2026-10-20 — 독립 환경 설치 완료. Python3.11, httpx0.28.1, python-dotenv1.2.1; pip check 통과.
- `python -m unittest integration.openai_decisions.test_client -v`: 7개 통과. 모의 전송으로
  공식 URL·Bearer·JSON·refusal 보존, 302/400/401/403/404/429/500 단일 시도, timeout,
  비JSON/answers 누락, 잘못된 모델 차단, 파일 권한/프로세스 우선순위/빈 키를 검사했다.
- CLI의 predicate/choice/score dry-run, 다른 cwd 실행, 빈 키 exit1, shell 문법 검사 통과.
- `.env`의 기존 값을 보존하면서 누락된 키 자리만 추가했다. Git 제외·권한600 확인.
- 실 API 호출0. API 키 유효성·계정 접근 권한·실제 모델 응답/성능은 미검증이다.
- [사용법](../../../../integration/openai_decisions/README.md). 환경 준비 완료이며 기존 실험 재개 없음.
