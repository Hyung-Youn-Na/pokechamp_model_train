# EP-060 — EX-046 다운로드용 단일 폴더 뷰어

- 상태: Completed
- 생성일: 2026-09-17
- 책임자: Codex
- 승인: 사용자의 뷰어·경기를 한 폴더로 다운로드하는 요청.
- 원문: [ARCHITECTURE](../ARCHITECTURE.md#연구-관측봉인viewer), [C-032](../../../CONTRACTS.md#c-032-io-explanation-review), [D-049](../decisions/D-049-viewer-turn-tabs.md), [EX-046](../../../research/lead-policy/experiments/EX-046-async-official-lead.md).

## 목표·범위

EX-046 목록과 양측64개 report/replay/protocol을 exports/ex046-viewer 폴더와 ZIP으로 제공한다.
복사본 링크만 상대경로로 연결하고 원자료·기존 뷰어·실험 소스·판정·봉인은 보존한다.
active 색인과 EP-057 범위를 확인했다. 기존 중단 실험과 공유 runtime 변경은 없으며 재개하지 않는다.
설명 검토는 요청 범위 밖이다. 비실험 자료 포장으로 유료 호출·복구·재수집·실험 시계는 해당 없다.
애니메이션은 기존 외부 공식 asset 의존성을 유지하고 오프라인 입력·응답 열람과 구분한다.

## 완료 기준

- [x] 단일 폴더와 ZIP에 목록·64관점·리플레이·로그·사용법 포함
- [x] 폴더 밖 로컬 링크 없음·압축 무결성·원본 보존 검증
- [x] 다른 경로에 압축 해제 후 file URL 목록 필터·턴 이동·복귀 확인

## 검증·진행

- 2026-09-17: 구현 전 등록. 검증은 ../evidence/ep060/에 기록한다.
- 링크·브라우저·ZIP 검사가 완료 기준이며 runtime 변경/재실험은 없다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 기존 결과를 재봉인하지 않는다.

## 결과 및 증거

- 2026-09-17: 단일 폴더·ZIP 제공, 이동/해제·전수 파일과 링크·오프라인 브라우저·원본 보존 검사 통과. [보고](../../../exec-plans/evidence/ep060/report.md)·[검증](../../../exec-plans/evidence/ep060/verification.json).
