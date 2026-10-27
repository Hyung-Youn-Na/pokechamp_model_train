# EX-030 — 계산기 입력 전체 로컬 진단

- 상태: Completed
- 생성일: 2026-09-10
- 책임자: Codex
- 관련: D-035, EP-023, C-023

## 질문·조건·분모

현재 지원 Gen9 싱글 입력 경로가 자기 request와 공개 cutoff의 사실·시점·정보 경계를 유지하는지 조사한다.
탐색적 정확성 진단이며 승률/전략/prior 통계 효능 실험이 아니다.
변경 전 source를 고정하고 결함별 수정 후 source와 대조한다. pinned Showdown 실제 진행을 독립 기준으로 사용한다.
기존 EX-028 435건+EX-029 201건=636개 요청 전부(무응답 포함), 기존15장면, 추가 경계 fixture가 분모다.
입력 재구성 실패도 분모에서 제외하지 않는다. 정답은 production 변환이나 같은 계산기로 만들지 않는다.

## 환경·격리·절차

기존 pinned PokéChamp/Showdown 및 @smogon/calc0.11.0+ruination-v1를 사용한다.
source·lock·설정·prior·prompt·원자료 hash와 결과는 `project_context/exec-plans/evidence/ep023/`에 보존한다.
세 경계별 검사,16난수/특수 피해, 생명주기, 전수 재생/영향 분석, 최종 fake LLM·전체 회귀를 수행한다.
비공개 엔진 상태는 테스트 oracle에만 사용한다. 원자료/주석/봉인 보고서/원장/halt/기존 Blocked는 읽기 전용이다.

## 승인·복구·중단·해석

사용자의 명시적 계획으로 조사·수정·로컬 검증을 승인받았다. 유료 호출·Cloud 배틀·재수집0이다.
C-018·RESEARCH_DESIGN §11.1에 따라 실패 source/입력/기준/결과를 보존하고 수정·독립 재검증한다.
로컬 재실행은 허용하며 비용/Cloud 시계 초기화는 없다. 증거 무결성 실패의 의존 분석은 중지한다.
변경 입력/경기별 최초 오염/의존 비교는 별도 정정 분석이며 과거 모델 행동·승패를 복원하지 않는다.
모든 완료 기준이 충족돼야 Completed다. 미해결 정확성 결함은 명시하고 미완료로 유지한다.

## 결과

12개 결함 분류·19개 필드 조사 항목을 작성했다. 확정 지원 범위 결함은 수정됐고 독립62검사와
최종519 integration 회귀가 통과했다. 새 입력은 calculator-input-v2 / battle-v1.2.0이다.
636입력(응답632/무응답4) 모두 재구성·세 경계·최종 worker/직렬화/필드설명 검증 성공, 실패0이다.

| 실험 | 입력 | 기존 수치·피해 구조 변경 | 테라 방어 coverage 추가 | 메타데이터만 변경 |
|---|---:|---:|---:|---:|
| EX-028 | 435 | 202 | 261 | 93 |
| EX-029 | 201 | 79 | 118 | 47 |

수치 변경과 coverage 추가는 겹치며, 합집합으로 수집된26개 B경기·의존 대응에 영향이 있다.
기존 수치 최초 시점과 coverage 누락 최초 시점을 별도로 기록했다. 과거 주석·원자료는 수정하지
않았고 수정 입력에서의 모델 단독 설명 오류율·행동·승패는 복원하지 않았다.
15장면/사후3, 실제 FixedPlayer 로컬 fake31결정, Python/Node 검사·source168파일 archive,
55,063보호파일·설치 라이브러리/두 submodule/기존6개 Blocked 불변·자원 정리를 확인했다.
유료 호출/재실험/재수집0이며 현재 성능 효능 claim을 추가하지 않는다.

## 결과·증거 링크

[한국어 조사 보고서](../../../exec-plans/evidence/ep023/report.md),
[결함/수정/독립 검증 목록](../../../exec-plans/evidence/ep023/defects.json),
[필드 조사 표](../../../exec-plans/evidence/ep023/verification-matrix.json),
[전수 영향·수기 정정](../../../exec-plans/evidence/ep023/impact.md),
[완료 plan](../plans/EP-023-calculator-input-audit.md),
[최종 봉인·보존 검증](../../../exec-plans/evidence/ep023/final-verification.json).
