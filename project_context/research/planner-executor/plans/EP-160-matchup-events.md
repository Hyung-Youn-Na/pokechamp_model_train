# EP-160 — 매치업 변화 기반 GLM 계획 갱신

- 상태: Completed
- 생성일: 2026-10-15
- 책임자: Codex
- 승인: 현재 사용자 EX-101 계획 구현·실행 지시 / D-154
- 조건 원문: [EX-101](../experiments/EX-101-matchup-events.md)
- branch/checkout: research/model-training /workspace a4659bf·기존 미커밋 변경 보존
- actor: pokechamp/.venv/bin/python; model: .pokechamp-data/jev35b-nvfp4-runtime/.venv/bin/python
- 새 출력: EX-101 run·evidence/ep160·exports/battle_viewers/ex101

## 범위·완료 기준

INDEX/CHARTER·매뉴얼·STATUS/색인·RD11.1/11.2·C-070/073 및 중첩EP-157/155/154/151/140/134
보존 경계를 확인했다. 상세 조건·한도·중단/복구·해석은 EX-101 원문을 따른다.
공개행 사건 검출·명시 설정만 확장하며 기존 기본값/입력/과거실행은 유지한다.
독립 저장궤적 분석과 실행/감사 경로 조사를 서브에이전트에 분리 위임하고 통합은 주 에이전트가 담당한다.

- [x] 등록·사건 구현/CPU검증·저장궤적28결정 독립대조
- [x] 설정차이/환경/source동결·새단일서버8사전추론·같은서버 정상1경기
- [x] 모든 호출/미호출 공개행·원문/재시도/usage/명령/자원감사·EX-100비교
- [x] 이동후 오프라인/복사/다운로드 뷰어·봉인·반환·문서갱신

## 진행·검증

- 2026-10-15 — 사용자 범위 등록. 실제 모델/API/배틀 전. 과거 자료는 읽기전용.

## 차단·중단

INDEX/EX-101의 경계를 따른다. 실패 시 부분보존·봉인·반환하되 정상목표와 구분한다.
재경기·대체모델·자동재개0이다.

- CPU136통과. 최초111검사 중 off 최소설정의 events 생략 호환회귀1건을 발견·교정하고
  초기 로그를 보존했다. 새 사건25검사 및 관련 회귀를 통과했다. 실제 수집 전 교정이다.
- EX-100 저장60결정의 독립 공개행 분석과 실제controller 무호출 재생이 모두28호출·사유/
  계획나이/보류좌표에서 일치했다. 실제 EX-101 호출수를 예측하지 않는다.
- EX-100 대비 trigger만 변경·환경freeze동일·공식37/외부587자료·GPU0/세포트 유휴를 확인했다.
  source 변경은 config/core/events 세파일이며 새 source/조건을 동결했다.
  새 단일적재·8사전추론/같은서버 본1경기에 진입한다. 수집source/조건 불변.

## 최종 판정

Completed: 정상1/1·실패0·player_won·82턴.
[최종 보고](../../../exec-plans/evidence/ep160/report.md)에 감사/비교/뷰어/봉인/반환을 연결했다. 자동재개0.
