# EP-117 — EX-072 오프라인 뷰어 검증·최종화 복구

- 상태: Completed
- 생성일: 2026-10-02
- 완료일: 2026-10-02
- 책임자: Codex
- 승인 근거: 사용자의 EX-072 전체 구현·실행·완료 지시, D-114, EX-072의 RD11.1/C-018 동일 조건 복구
- 관련: [EP-116](EP-116-selfplay-rlcd.md), [EX-072](../experiments/EX-072-selfplay-rlcd.md)

## 목표·범위

584경기·학습·test 완료 후 발견한 최종 브라우저의 `httpx` 의존성 누락과 큰 정수 표시 손실을
교정하고, 원 실패 보고·봉인을 보존한 별도 정정 identity에서 전수 오프라인 검증·최종 보고를 완료한다.
INDEX/CHARTER·RD11.1/C-018·EP-116 및 별도 GPU1 실행과 기존 중단 범위를 확인했다.
최초 실패는 브라우저 시작 전 import 오류이며 `final/viewer-check.log`에 보존됐다.
이 시점 test 추정치와 구간은 이미 확인했다. 평가 지표·표본·선택 기준은 변경하지 않는다.

원 runtime·source freeze·원자료·모델·시계·`final/`·`completed.json`·기존 EX-072 export는
덮어쓰거나 삭제하지 않는다. 새 `scripts/pokechamp-selfplay-finalization-recovery.py`는 CPU 최종화 전용이며 원 봉인,
필수 artifact, 전체 분모와 원 시계를 확인한 뒤에만 정정 산출물을 만든다. 브라우저 검증기는
원 source 그대로 실행하고 CPU 검증 때 사용한 의존성 검색 경로만 명시적으로 전달한다.
새 학습·대국·모델 호출·재수집0, 추가 GPU 사용0. EX-072의 최초24시간 한도를 유지한다.

## 완료 기준

- [x] 누락 import 독립 재현·의존성 교정·관련 CPU 회귀 통과
- [x] 원자료/가중치/원 보고·원 봉인 불변과 전체584경기 영향 없음 확인
- [x] 명시적 정정 경로의 실패/시간/무결성 gate 검증과 독립 코드 검토
- [x] 전584경기의 이동 후 오프라인 Chromium 검사 통과
- [x] 별도 정정 보고·완료 receipt·C-047 export·전후 identity 연결·상태 갱신

## 검증·진행

- 2026-10-02 — 원 브라우저 Python3.11 환경에서 `httpx` 부재를 확인했다. 동일 환경에서
  CPU viewer suite와 같은 의존성 경로를 추가하면 원 검증기 import가 성공했다.
  원 최종화는 실패를 감추지 않고 `experiment_complete=false`로 봉인했다.
- 독립 검토는 prepare 에이전트에 읽기 전용으로 위임하고 구현·문서 통합은 주 에이전트가 맡는다.

## 중단·복구·증거

상세 조건은 EX-072·RD11.1/C-018을 따른다. 원 자료 무결성 또는 영향 범위를 입증할 수 없으면
해당 완료 판단을 보류한다. `completed.json`의 닫힘을 삭제해 원 실행을 재개하지 않고,
본 plan에서 검증한 별도 CPU 최종화 기능만 사용한다.
원 증거: `.pokechamp-data/experiments/ex072-selfplay-rlcd/final/`.
실패한 v2 증거: 같은 실험의 `corrections/finalization-v2.failure.json`과
`corrections/.finalization-v2-staging/`. 완료본으로 게시하지 않았다.

## 후속 표시 결함과 v3 범위

의존성 교정 후 실제 브라우저가 시작됐지만 원 verifier가 응답 불일치를 발견했다. 독립 DOM 대조에서
`rng_seed`·`sampling_seed`·`rng.seed`의 원 정수 `12032933256718738492`가 JavaScript 숫자
직렬화로 `12032933256718740000`으로 바뀐 것을 재현했다. raw JSON·학습·정책·통계는 영향이 없고
브라우저의 원문 패널·복사·결정 다운로드가 영향 범위다. 검사 기준을 완화하지 않는다.

v2 도구·회귀·검토 receipt·실패·미게시 staging은 그대로 보존한다. 새
`scripts/pokechamp-selfplay-finalization-v3.py`와 `scripts/selfplay_viewer_exact_json.py`에서
원 Python JSON 문자열을 별도 안전하게 내장하고 표시·복사·다운로드에 사용한다. 새 사본의 경기
HTML과 출처만 교정하며 원 source·원 export·그 밖의 데이터 바이트는 보존한다. 원 verifier를
그대로 실행한다. 독립 큰 정수·중첩·script 종료문자·브라우저 다운로드 회귀를 추가한다.
v3 결과는 `corrections/finalization-v3/`, 내보내기는 `exports/battle_viewers/ex072-finalization-v3/`다.

- v3 최종화의 원본 보존·시간 한도·통계 일치·전수 브라우저 gate·두 봉인 완료 전 게시 금지
  18검사가 통과했다. 큰 양/음의 정수·중첩·JSON 타입·script 종료문자·실제 clipboard/download·
  원 검증기의 실패 재현/교정 통과 5검사와 기존 viewer 7검사도 모두 통과했다.
  증거: `verification/finalization-v3/recovery-tests.json`, `renderer-tests.json`,
  `renderer-regression.log`. 동결 원 verifier는 수정하지 않았다.
- 독립 검토는 원584페이지·21,899결정의131,394개 패널/다운로드 payload를 메모리에서 전수
  대조했다. 정수·float·boolean을 포함한 모든 값·타입과 원 embedded data가 일치했다.
  원 runtime394파일·보존 소스394파일·필수26artifact·raw9,928파일 및 원본/v2 봉인 불변을 확인했다.
  증거: `verification/finalization-v3/independent-review.json`.
- v3 실제 실행이 정상 종료했다. 전584페이지·대표1,032결정과 다음/이전/타이머/마지막 턴 재생을
  이동 사본에서 검사했고 JavaScript 오류0·외부 요청0·원본/사본 해시 불변을 통과했다.
  모든 통계는 원 보고와 같으며 완료 bookkeeping만 정정했다. 두 봉인을 검사한 뒤 게시했고,
  원 시계부터42,309.66초에 `experiment_complete=true`, `performance_improved=false`로 닫았다.
- 최종 게시590링크·584경기 링크·최종 모델/완전 checkpoint·원 완료 판정/시계 보존과 소유
  프로세스 종료/GPU3 반환·GPU1 유지도 확인했다. `publication-check.json`이 통과했다.
  실제 정정·renderer·회귀 소스 복사본은 같은 검증 폴더의 `source/`와 `source-manifest.json`에 보존한다.

## 완료 증거

[정정 최종 보고](../../../../.pokechamp-data/experiments/ex072-selfplay-rlcd/corrections/finalization-v3/report.md) ·
[완료 receipt](../../../../.pokechamp-data/experiments/ex072-selfplay-rlcd/corrections/finalization-v3/completed.json) ·
[전수 브라우저 검증](../../../../.pokechamp-data/experiments/ex072-selfplay-rlcd/corrections/finalization-v3/viewer-check.json) ·
[독립 검토](../../../../.pokechamp-data/experiments/ex072-selfplay-rlcd/verification/finalization-v3/independent-review.json) ·
[최종 게시/자원 확인](../../../../.pokechamp-data/experiments/ex072-selfplay-rlcd/verification/finalization-v3/publication-check.json) ·
[584경기 뷰어](../../../../exports/battle_viewers/ex072-finalization-v3/index.html).
