# EP-156 — GLM 형식 재시도·temperature0 실제1경기

- 상태: Completed
- 생성일: 2026-10-15
- 승인: 사용자 현재 지시 / D-150
- 조건 원문: [EX-097](../experiments/EX-097-planner-format-temperature-zero.md)
- branch/checkout: research/model-training /workspace a4659bf·기존 미커밋 변경 보존
- actor: pokechamp/.venv/bin/python; model: .pokechamp-data/jev35b-nvfp4-runtime/.venv/bin/python

## 범위·검증·완료

GLM 새 기본온도0과 형식 오류 전체 재시도를 구현하고 새 실제1경기를 수행한다.
관련 INDEX/CHARTER/매뉴얼·RD/C-070/073·EP-155/154/151/140/134의 보존·중단 경계를 확인했다.
기존 실패와 봉인은 유지하며 새 EX의 한도/중단 규칙을 적용한다. source/조건은 경기 중 불변이다.

- [x] 기본/legacy·형식/통신 분리·최초+5회·같은 입력·예산/취소·원문/usage CPU 검증
- [x] 새 조건/source 동결·단일 적재/8사전추론·같은 서버 정상1경기
- [x] 실패 포함 전수감사·EX-094/096 기술비교·통합뷰어·이동후 오프라인/복사/다운로드
- [x] run/viewer/evidence 봉인·자원 반환·상태/색인 갱신

## 진행

CPU216통과·별도형식15통과·브라우저2통과(중복 포함). EX-096 실패 원문의 무과금 재생에서
형식 오류→동일 temperature0 요청→유효 계획 복구를 확인했다. 공식37파일/587입력자료·
원스케줄/프롬프트/상한·GPU0/포트·기존 봉인 검토 후 source4파일/설정을 동결하고 실제 실행을 시작했다.

## 최종 판정

Completed: 정상1/1·실패0·결과player_lost·턴35.
전수감사·부분/전체 통합뷰어·오프라인 검사·자원 반환·봉인을 수행했다.
[보고](../../../exec-plans/evidence/ep156/report.md). 단일 경기의 일반 성능 효과는 미평가다.
