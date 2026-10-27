# EP-033 — 전체 Cloud 기본 동시성 8

- 상태: Completed
- 생성일: 2026-09-13
- 완료일: 2026-09-14
- 승인 근거: 현재 사용자의 계획 구현 지시. 적용 범위는 전체 Cloud 경로, 기본값만 8이며 명시적인 9·10은 허용한다.
- 관련: D-045, C-029. 새 유료 experiment 등록·실행은 없다.

## 목표·범위

새 Cloud 병렬 실행의 배틀·계정·모델 요청 기본값을 각각 8로 일치시킨다.
A/B 직접대결, A 진단, 일반 비교, Cloud gate와 요청 검증의 설정 생성·실행·검증·보고·시간 추정을 포함한다.
공통 기본값과 `execution.evidence.concurrency_policy=cloud-default8-v1`을 사용한다.
명시적인 execution 값(1–10)을 우선하며 순차1과 별도 동시성 측정의 명시적인1–10 조건은 유지한다.
worker·포트·permit은 봉인된 execution을 따른다. 기존 정책 identity/hash와 과거 설정의 읽기·검증·보고를 보존한다.

## 불변 조건·중단 범위

기존 실험 원자료·봉인·시계·원장·Blocked plan을 변경하거나 재개하지 않는다.
첫10 gate의 표본 수, 경기 수, timeout·retry·예산·모델·입력·출력 규칙은 유지한다.
공통 실행정책은 새 실행의 동시성 항목에만 우선한다. 과거 등록의 고정10은 historical 조건으로 남긴다.
유료 호출·실험·재수집0. 비실험 구현이므로 C-018의 유료 복구는 해당하지 않는다.
timeout의 인과 원인이나 개선 효과를 주장하지 않는다. 보존/호환 결함은 해당 경로를 수정·검증한 뒤 완료한다.

## 완료 기준·검증

- [x] 공통 기본8, 명시10/낮은 값/순차1 및 기존10 설정의 호환성
- [x] 각 준비 경로, 실제 coordinator worker·permit·port 및 선언값 변조 검증
- [x] gate 집계·시간 추정·사후 검사와 동시성 측정 조건 보존
- [x] 관련 로컬 회귀, 가짜 요청으로 기본8 및 연속 투입 확인
- [x] 기존 자료 보존·문서·source 변경분·검증 결과 기록

## 진행

- 2026-09-13: 관련 active plan과 계약을 확인했다. 기존 Blocked의 실험은 재개하지 않는다. 구현 전 등록.

## 결과 및 증거

- 기본8·명시1–10·과거10을 구분하는 설정과 실행·검증·집계를 구현했다.
- 전체764회귀, 실제 가짜 coordinator/permit3·8·10, gate1/8·과거1/10과 회복 시 중복 요청 방지,
  EX-035/036/037 및 EX-021/022/025의 과거 설정·봉인 호환성을 확인했다.
- 변경 Python Ruff/compileall 통과. 최종source184파일 봉인·변경28파일 전후차이 기록.
- 보호130,771파일 변경/누락0·새 실험 원자료0·두 submodule clean·8100–8109 해제·유료0.
- [검증 보고서](../../../exec-plans/evidence/ep033/report.md), [최종 검증](../../../exec-plans/evidence/ep033/verification.json),
  [전체 회귀](../../../exec-plans/evidence/ep033/regression-final.log), [source 차이](../../../exec-plans/evidence/ep033/source.patch).
- 기존8개 Blocked plan과 과거 실험 상태는 유지한다. Cloud 개선 효과의 실측은 수행하지 않았다.
