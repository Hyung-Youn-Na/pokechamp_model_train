# EP-158 — 시간 상한 없는 GLM 최대 출력 실제1경기

- 상태: Completed
- 생성일: 2026-10-15
- 승인: 현재 사용자 지시 / D-152
- 조건 원문: [EX-099](../../experiments/EX-099-planner-unlimited-time-max-output.md)
- branch/checkout: research/model-training /workspace a4659bf·기존 미커밋 변경 보존
- actor: pokechamp/.venv/bin/python; model: .pokechamp-data/jev35b-nvfp4-runtime/.venv/bin/python

## 범위·완료 기준

선언적 null 시간 상한을 전역예산/세션/양쪽 actor/watchdog에 구현한다. 과거 유한 동작과
호출/메모리/형식복구·취소/자식종료 경계를 유지하고 실제 새1경기를 수행한다.
INDEX/CHARTER·매뉴얼·RD/C-070/073·중첩 EP-157/155/154/151/140/134를 확인했으며 재개하지 않는다.
source/조건은 새 수집 진입 후 불변이다. 세부 한도/중단·실패 분모는 EX-099 원문을 따른다.

- [x] 등록·null 시간/과거 유한/양쪽 actor/호출 제한/직렬화/취소 CPU 검증
- [x] 조건/source/자산 동결·단일 적재/사전8추론·같은 서버 정상1경기
- [x] 실제 max_tokens131072/high/temperature0·모든 시간 경로 null·전수 감사/EX-098 비교
- [x] 통합뷰어/대표 이동후 오프라인/복사/다운로드·봉인·자원반환·문서/색인 갱신

## 진행

CPU236통과(브라우저별도2skip), 최종 시간/배틀33통과(중복 포함), null 양쪽actor/과거 유한/
호출상한/취소·JSON직렬화를 확인했다. 초기 검사 시계 fixture 중단/교정은 별도 증거로 보존했다.
실제 API/GPU 무호출 설정검사에서 max_tokens131072/high/temperature0·시간2필드null만 변경됨을 확인했다.
공식37파일·v6외부587파일·환경 freeze --all 동일·GPU0/세포트/자격증명 무호출 검토 후
새 source3파일+시간helper1개/설정을 동결하고 단일 적재·8사전추론/같은 서버1경기를 시작했다.

## 최종 판정

Completed: 정상1/1·실패0·player_won·마지막관측47턴.
[최종 보고](../evidence/ep158/report.md)에 감사/비교/뷰어/봉인/반환을 연결했다. 자동재개0이다.
