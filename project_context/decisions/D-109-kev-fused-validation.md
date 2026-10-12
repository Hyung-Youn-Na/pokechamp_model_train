# D-109 — Kev fused·merged 서빙의 추가 수락 검사

- 상태: Accepted
- 날짜: 2026-10-01
- 승인: 첫 unmerged 예측 gate 실패 보고 후, fused·merged 3관측 재검증과 통과 시1경기 제안에 대한 사용자의 “진행해주세요.”
- 관련: [D-108](D-108-kev-battle.md), [EX-068](../experiments/EX-068-kev-battle.md), [EP-111](../exec-plans/active/EP-111-kev-battle.md)

입력·질문·토큰열이 같은데도 unmerged 서버의 첫 예측이 dev 기준과 달랐다. 과거 dev는
bf16 원격 서빙 평가였으며 실제 merge/fused 옵션은 보존되지 않았다. 현재 코드의 기본
서빙 경로를 별도 검증하는 것이며 불일치의 원인을 사전에 확정하지 않는다.

새 `ex068-v3`에서는 `KEV_MERGE=1 KEV_FUSED=1`을 명시한다. 원 checkpoint·bf16/T1·GPU3,
문자열 state/질문·팀/seed·Tera 조건·동률/재검증·fallback0은 유지한다. 고정 validation3관측을
각1회 추가로 검증하고 모든 후보가 기존 dev p와 소수 넷째 자리까지 같을 때만 아직 시도하지
않은1경기 smoke를 실행한다. 추가 validation 최대3요청, 전체 배틀 최대1경기이며 새 불일치 시
의존 배틀을 다시 중지한다. HTTP 자동 재시도·추가 경기·학습 전용은 허용하지 않는다.

원 `ex068`/`ex068-v2`와 EP-111 첫 보고의 봉인·실패·시계·요청1건을 보존한다. 별도 추가
probe admission에 이 승인과 원 admission/hash를 연결하고, 원 배틀 admission은 공동으로
사용하여 이전 출력 폴더 변경으로 경기 상한을 늘리지 않는다. 원 전체 목표·판정은 유지하며
기존 unmerged 결과를 통과로 다시 표시하지 않는다. 직접 시작한 새 GPU3 서버는 종료 시 정리한다.
실행 조건의 원문은 EX-068의 추가 실행 절, runtime 범위는 C-054에서 명시한다.
