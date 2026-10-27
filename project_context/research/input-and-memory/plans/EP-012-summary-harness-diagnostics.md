# EP-012 — 요약 harness 기여도 진단

- 상태 (Status): Blocked
- 생성일: 2026-09-08
- 책임자: Codex
- 관련: [D-023](../decisions/D-023-summary-harness-diagnostics.md), C-015,
  [EX-021](../experiments/EX-021-summary-harness-diagnostics.md)

## 목표와 범위

사용자가 승인한 D-023의 독립 prepare/run/report --review 경로를 parent integration에
구현하고 사전 검증 후144호출과 근거 연결 검토를 수행한다. EX-020/EP-011은 보존한다.

## 완료 기준

- [x] 봉인 코드로 H0 재구성·기존4 prompt 바이트 일치,12장면/48입력/144일정 봉인
- [ ] 의미·정답 검증의 완전성: 사전 통과 후 weather 의미/수기 기준 오류 발견으로 철회
- [x] fake144·취소/중단/선봉인/정리 및 기존214회귀·추가회귀·정적검사
- [x] 1시간 내 Cloud144 확보 및 중단 분모 기록 (검토 초안36/144, 나머지108 중단)
- [x] 중단·비용·한계 보고 및 context 갱신
- [ ] 유효한 근거 연결 검토·대응 비교 완료 (전체 무효화, 진단 미완료)

## 중단 조건

D-023의 provider·환경·무결성·입력 변환 오류나 상위 authority 충돌에 전체 중단한다.
모델 요약 오류는 진단 결과로 보존하며 재시도·보충하지 않는다.

## 진행 및 검증

2026-09-08: 상위 문서와 EP-011 확인. EX-020 offline-v8의89 source와7응답 보존 확인.

2026-09-08 사전 검증: 기존214+신규24=238 tests(67.12초), Ruff E/F/I/W 100자,
compileall과 Node10파일 통과. H0 system/user4쌍 byte 일치,12장면/48조건 정보 복원,
원본 행 기반 턴·HP 독립 대조, fake144와 중단·취소·정리·재시작 검증을 봉인했다.
독립 평가 사실122개와 rubric을 입력 변환과 분리했다. EX-020 및 EP-011 관련1,242파일
hash 불변, credential2,149파일/유출0, submodule clean/pinned, context457링크 통과.
[사전 검증](../../../../.pokechamp-data/summary-diagnostics/ex021/verification.json),
[입력·일정 봉인](../../../../.pokechamp-data/summary-diagnostics/ex021/manifest.json).

## 중단 결과와 후속 로컬 수정

Cloud144/144를166.6126초에 확보했다. Provider 실패0·미실행0·미확정0이며 실행기
output_contract 기록1은 수기 평가 완료율이 아니다. 기존 장면3개의 검토 초안36개 작성 후,
scene3 검토에서 weather 숫자를 시작 턴으로 단정한 H1/H3 변환 오류를 확인했다.
원본 parser는 upkeep마다 값을 갱신한다. 기존 scene1/3의4입력·12응답이 직접 영향을
받았고 수기 기준도 scene3의 실제 시작3턴을4턴으로 잘못 기록했다.

D-023 중단 규칙에 따라 전체 비교를 무효화했다. 초안36개는 invalid 자료로 봉인했고
108개 검토를 중단했다. 각 대비의 유효 장면 쌍은 기존0/4·추가0/8이다. 이 상태는
Completed가 아니며 unaffected scene 선택·재호출·보충을 하지 않는다.

중단 후 로컬 코드만 weather를 last_weather_protocol_turn으로 교정하고 수기 기준을
원본 행으로 교정했다. 실제 parser upkeep·강제 교체 턴 회귀와 halt 이후 제출/정상
보고서 차단을 추가했다. 오류 주장과 필수 사실 누락을 구분하는 분석 집계 수정도
보존했다. 어느 수정도 봉인된 EX-021 입력·기준·응답에 소급하지 않는다.

[중단 보고서](../../../../.pokechamp-data/summary-diagnostics/ex021/report.md),
[실패 근거](../../../../.pokechamp-data/summary-diagnostics/ex021/input-transform-failure.json),
[무효 검토 초안](../../../../.pokechamp-data/summary-diagnostics/ex021/review-partial-invalid.json).
새 진단·운영 적용·EX-020 재개는 별도 결정이며 현재 실행 범위가 아니다.


종료 검증: 기존214+추가30=244 tests(69.71초), Ruff E/F/I/W, compileall, Node10파일 통과.
사전238통과 기록과 별도로 중단 후 source/재현/검증을
[종료 검증 receipt](../../../../.pokechamp-data/summary-diagnostics/ex021/closure-verification.json)에
연결한다. 이 receipt는 도구 교정·증거 보존 검증이며 EX-021 비교 자격을 복구하지 않는다.
