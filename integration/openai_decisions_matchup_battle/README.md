# 후보별 요약 OpenAI 32경기

[EX112](../../project_context/experiments/EX-112-openai-candidate-matchup-battle.md)의 독립 실행기다.
기반 jev-choice-v6에 candidate-matchup-v1만 추가하며 EX110의 일정·통신 재시도를 유지한다.

`scripts/openai-decisions-matchup-battle mock`은 API 없이 모의2경기·전수감사·뷰어를 만든다.
`prepare`는 모의/오프라인 검증 이후 source·규칙·protocol·일정을 동결한다.
`execute`는 새32경기를 순차 실행한다. `status`는 저장기록만 조회하며 `export`는 오프라인뷰어를 만든다.
기존출력 덮어쓰기·자동재개·보충경기는 지원하지 않는다. 새유료 preflight는 없다.
입력/감사/자료 정체성은 명시 프로필을 따르며 과거실험의 기본값은 유지한다.
