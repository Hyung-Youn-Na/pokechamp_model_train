# EX-102 — 매치업 사건 기반 GLM high 동일 대진

- 상태: Completed
- 생성일: 2026-10-15
- 승인: 현재 사용자 명시 지시 / [D-155](../decisions/D-155-matchup-events-high.md)
- 계획: [EP-161](../plans/EP-161-matchup-events-high.md)
- branch/checkout: research/model-training /workspace a4659bf·기존 미커밋 변경 보존

## 질문·처치·고정 조건

[EX-101](EX-101-matchup-events.md)의 모든 동결 조건을 참조 편입하고
`planner.reasoning_effort: low→high` 하나만 변경한다. 식별자/출력 경로만 새 EX로 분리한다.
같은 대진의 새 실제1경기에서 호출·계획 유지기간·지연·토큰·행동 사례·결과를 비교한다.
단일 경기의 서로 다른 궤적 비교이며 일반 성능이나 인과효과를 주장하지 않는다.

GLM-5.3/thinking enabled/high/temperature0/top_p0.95/max_tokens131072·경기/전체시간null.
trigger.policy:events, events:[faint,tera,forced_switch,active_change,form_change]이며
interval_turns:3은 사용하지 않는다. 최초 선봉·등장 후 재계획·단일후보 보류·공개행 cutoff/중복제거는
C-070/EX-101과 같다. 입력 구조·프롬프트·피해계산·후보·팀·seed·응답복구/HTTP 정책은 불변이다.
JEV autotrust/JEV-35B-NVFP4 revision10c2c62610e315e31a75baca849ad79d526e4658·GPU0 Marlin,
actor pokechamp/.venv/bin/python·model .pokechamp-data/jev35b-nvfp4-runtime/.venv/bin/python,
기존37파일·고정환경·TP1/동시1·단일서버·8사전추론과 probability_diagnostic을 유지한다.

## 한도·중단·복구

GLM 물리HTTP128·JEV논리256(사전8포함)·경기1·GPUallocator40GiB/전체44GiB·소유host32GiB·
disk null/사용량기록·8109/18845/18846 포트 점유시 미진입. 별도 유료GLM probe0.
새 단일서버의 사전8추론 통과 후 같은 서버로 본경기를 수행한다. 환경 재설치0.
RD11.1/C-018·RD11.2/C-046·C-070/073과 EX-101의 격리/복구/사용자 취소·자원정리를 유지한다.
재수집/재경기/보충/대체모델/자동재개0. 최초시계·누적예산은 초기화하지 않는다.
수집 진입 후 source/조건 불변. 실패 시 원문·부분자료·사유를 보존하고 봉인/자원반환한다.
전수 전략/설명 정확성 검토는 RD8.1/C-032 기본 제외다.

## 검증·출력·완료

EX-101 대비 설정차이가 reasoning_effort 하나임을 전수 대조하고 모의wire의 high·온도0·
131072와 같은 요청바이트 형식재생성을 검증한다. 동일source의 EP-160 CPU136/사건25/
저장궤적28대조와 불변 JEV/환경 검증은 일치 근거로 재사용한다.
새 사전추론·실제 high wire·모든 호출/미호출 공개사건·원문/usage/재시도/선택→명령·자원은
새 자료로 전수 감사한다. EX-101 low와 기술/행동 비교 후 정상1경기·필수감사·이동후 오프라인
뷰어/복사/다운로드·원자료/뷰어/증거 봉인·소유자원 반환을 완료한다.

run: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-102
증거: project_context/exec-plans/evidence/ep161
viewer: exports/battle_viewers/ex102/index.html
condition: glm53-jev35b-nvfp4-matchup-events-high

## 결과

정상1/1·실패0·player_won·39턴.
[최종 보고](../../../exec-plans/evidence/ep161/report.md)에 실제 분모와 비교를 연결했다.
