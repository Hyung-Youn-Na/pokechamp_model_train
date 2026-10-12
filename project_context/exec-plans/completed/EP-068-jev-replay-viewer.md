# EP-068 — EX-050 배틀 리플레이 통합

- 상태: Completed
- 생성일: 2026-09-21
- 승인: 사용자 EX-046처럼 배틀 리플레이도 함께 열람 요청
- 관련: C-047, D-077, EX-050, EP-060/067

## 범위·보존

exports/battle_viewers/ex050에 경기별 입력/응답+고정 리플레이 패널·목록을 생성한다.
기존 공식 replay renderer를 사용하고 기록된 actor protocol에서 경기별 로그를 복원한다.
INDEX/CHARTER·계약/architecture·plan 색인·겹치는 EP-062/064를 확인했다.
원자료·수집 source·원본 뷰어·EX-046·봉인은 보존한다. 기존 내보내기 manifest는 evidence에 보존한다.
비실험 열람 개선이므로 유료 호출·재수집·실험 시계는 해당 없음.

## 완료 기준

- [x] 2경기 리플레이/로그·각 경기 결정 기록과 함께 표시
- [x] 원문 분리·승패/턴·링크·체크섬·오프라인 fallback·온라인 애니메이션 검증
- [x] 매뉴얼/지원 범위·보고·상태 갱신

## 결과·검증

2경기 리플레이/결정 통합·191링크·원본 보존·오프라인 fallback/모바일/온라인 Turn2 재생 검증 통과.
[보고](../evidence/ep068/report.md), [검증](../evidence/ep068/verification.json). 실험 재실행/API0.
