# EP-049 — 공급자 오류 재시도 확대·정상 경기 viewer

- 상태: Completed
- 완료일: 2026-09-16
- 생성일: 2026-09-16
- 승인: 현재 사용자의 계획 구현 지시, [D-060](../decisions/D-060-provider-retry-viewer.md)

## 목표·범위

새 provider-retry-v2(연결/timeout/5xx/429, 1/2/4초·최대3재시도)와 최종429 전체 중단을 구현한다.
EX-042 유효26경기·52개 기존 actor viewer를 별도 목록으로 연결한다.
관련 active EP-048/045/044/041/035/032/030/020/018/015/013/012/011의 중단·원자료·과거 정책을 보존한다.
외부 모델 호출·재수집·재개·COURT_CHANGE 수정·설명 annotation은0이다.

## 완료 기준

- [x] 새 정책·과거 v1/legacy 호환·원장/재시도/gate/429 중단 검증
- [x] 공급자별 모의 HTTP 로컬 Showdown 경기·permit/자원 정리
- [x] 유효26행·52개 viewer·필터·목록 복귀·좁은 화면 확인
- [x] 기존 봉인 보존·보고·manifest·문서/색인/STATUS 동기화

## 검증·복구

두 공급자의 오류별 성공/소진·고정 대기·입력 불변·취소/기한·최종429·모의 원장 및 관련 회귀를 수행한다.
새 viewer는 봉인 summary/matches와 기존 source/derived 파일을 읽기만 하고 새 index만 작성한다.
비실험 구현 검증으로 추가 유료 예산/시계는 없다. INDEX 공통 기준과 C-018의 보존 경계를 따른다.
증거: `../evidence/ep049/`.

## 완료 근거

[최종 보고](../../../exec-plans/evidence/ep049/report.md)·[manifest](../../../exec-plans/evidence/ep049/manifest.json)를 참조한다.
전체 회귀와 영향 모듈 재검사를 합쳐 최종1,176건의 통과 근거를 확인했고,
두 공급자의 로컬 경기2개·실제1/2/4초 대기·동일 전송·원장/permit 검증을 통과했다.
기존56,917파일과 EX-042 manifest554항목 변경0, source245파일 일치·자원 정리를 확인했다.
외부 모델 호출·기존 실험 재개0이다.
