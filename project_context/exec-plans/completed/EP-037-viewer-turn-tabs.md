# EP-037 — Viewer 턴 탭과 LLM 응답 기본 표시

- 상태 (Status): Completed
- 생성일: 2026-09-14
- 책임자: Codex
- 관련 contract: [C-009](../../CONTRACTS.md#c-009--pokéchamp-research-battle-observability)
- 관련 decision: [D-049](../../decisions/D-049-viewer-turn-tabs.md)
- 관련 experiment: 없음; EX-038/EP-035 및 기존 Blocked는 보존한다.
- 승인 근거: 현재 사용자 제공 「Viewer 턴 탭과 LLM 응답 기본 표시」 계획의 구현·검증 지시.

## 목표·맥락

공통 viewer에서 원하는 턴으로 직접 이동하고 해당 턴의 모든 LLM 응답과 reasoning을 펼쳐 읽는다.
기존 renderer의 호출 전체 details와 결정 일렬 나열을 개선한다. D-010의 source/derived 경계를 유지한다.

## 범위·비목표·불변 조건

- render.py HTML/CSS/내장 JavaScript, 관련 회귀·브라우저 검사, 현재 구조·상태 문서만 변경한다.
- 앞으로 생성할 viewer에 적용한다. 화면 검증은 임시 fixture만 사용한다.
- 기록 schema/parser/계산 경로/연구 방법론/실험 상태/원자료/봉인/기존 viewer는 변경하지 않는다.
- 외부 UI 의존성 추가0, 유료 호출0, 배틀 실행0, 기존 실험 재개·재생성0.
- decision/issue anchor, 상태·행동·검증·후속 protocol·replay를 보존한다.
- 모든 비신뢰 텍스트 escaping, 스크립트 CSP hash, JavaScript 비활성 시 정적 열람을 유지한다.

## 완료 기준

- [x] showdown_turn 기준 준비/턴/턴 미상 그룹, 같은 턴 복수 결정 순서 및 첫 그룹 기본 선택.
- [x] 탭·바로가기·이전/다음·키보드 접근성·문제/결정 링크·직접 URL·새로고침·뒤로/앞으로 복원.
- [x] 각 호출 reasoning/원문 답변 항상 표시, 무호출/복수/실패/빈 응답 구분, 입력/B2 원본/metadata 접힘 열람.
- [x] 전체 protocol 접힘 및 무결정 기록 정적 열람, 중복 ID 없음, 기존 표시 회귀 통과.
- [x] 실제 브라우저 긴 경기/좁은 화면/네트워크 차단/JavaScript 비활성/악성 문자열/CSP 검증.
- [x] 기존 산출물 보존 확인 및 plan/index/STATUS 갱신.

## 검증

| 검사 | 방법 | 결과 |
|---|---|---|
| Renderer/B2 회귀 | 관련 pytest 및 정적 검사 | 64통과·최종5통과·Ruff/compileall 통과 |
| 실제 브라우저 | 임시 fixture Chromium 자동화 및 화면 확인 | 8시나리오 통과·page error0·150턴/390px/1600px |
| 보존 | 기존 viewer·원자료·봉인·active plan SHA-256 전후 대조 | 139,452개 불변(viewer관련4,025·source/봉인6,057) |

## 진행

- 2026-09-14 INDEX/CHARTER/C-009/D-010/ARCHITECTURE와 겹치는 EP-030/032/035 확인. 기존 Blocked와 분리해 등록, 구현 전.

- 2026-09-14 구현·필수 검사·보존 확인 완료. 개별 plan을 Completed로 이동하고 index/STATUS/ARCHITECTURE를 갱신했다.

## 차단 및 중단 조건

비실험 UI 작업으로 C-018 실험 복구·재수집·시계는 해당 없음. 추가 수집0.
INDEX의 승인·확인 질문·중단·완료를 따르며 충돌이 있으면 의존 범위를 중단하고 기록한다.

## 결과 및 증거

[검증 보고서](../evidence/ep037/report.md), [브라우저 결과](../evidence/ep037/browser-results.json),
[보존 결과](../evidence/ep037/preservation-result.json)에 구현·검사·화면·한계를 기록했다.
2026-09-14 완료: 공통 renderer 표시만 변경했고 기존 viewer 재생성0·유료0·실험재개0이다.
마지막 좁은 화면 스크롤 보정 후 브라우저 전체 및 관련 renderer 검사를 다시 통과했다.
