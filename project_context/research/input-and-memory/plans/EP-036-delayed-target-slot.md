# EP-036 — 지연 기술 대상 슬롯 입력 교정

- 상태: Completed
- 생성일: 2026-09-14
- 관련: D-048, C-014/C-016/C-023/C-030/C-031, EX-038 (재개 아님)
- 승인 근거: 현재 사용자가 제공한 「지연 기술 대상 슬롯 입력 오류 수정」 계획의 구현·오프라인 검증 지시.

## 목표·범위·불변조건

Healing Wish 기절 뒤 Future Sight의 슬롯 없는 대상 입력을 공개 개체·슬롯 기록으로만 복구한다.
switch/drag/replace/faint 근거와 기절 직전 연결을 보존하며 유일한 슬롯만 허용한다.
명시적 슬롯 우선, 근거 부족·모호함은 기존 오류 유지, Doom Desire 실제 시작 표기를 지원한다.
시작 턴·교체 대상·해결·만료 규칙, 공개 JSON·프롬프트·B2·calculator-input-v2·계산식은 유지한다.
허용 변경은 parent integration parser/오프라인 검증 및 project_context 기록이다.
유료·외부 호출·실험 재개·설명 추가검토·과거 전체 계산 재생은 제외한다.
EX-038/EP-035 및 기존 Blocked·부분 결과·원자료·봉인은 보존한다.

## 완료 기준·검증

- [x] 별도 before source·실제 실패 prefix/요청 보존 및 수정 전 오류 재현.
- [x] 같은 실패 결정의 정규화→계산→입력검증→B2→실제 backend 가짜 전송.
- [x] 고정 Showdown Healing Wish/Future Sight/Doom Desire 양쪽 진영·교체 후 해결 검증.
- [x] 명시 슬롯·무근거/모호함·미연결 시작·중복·교체·면역·실패·조용한 만료·종료 회귀.
- [x] EX-037/038 모든 저장 결정의 공개 prefix에 before/after parser 비교. 기존 정상 상태 동일성 및 차이 설명.
- [x] 관련 정규화/계산/B2 회귀·정적 검사, 새 source hash·원자료 보존 확인.
- [x] 결과·plan index·STATUS 갱신, 기존 Blocked 유지.

## 중단 조건

비실험 오프라인 bugfix로 새 연구 실험 복구·예산 시계는 해당 없음. 유료 호출/재수집0.
상위 충돌 및 필수검증 실패는 해당 완료 판정을 중단하고 별도 evidence에 기록한다.
승인·질문·중단·완료는 project_context/INDEX.md를 따른다.

## 진행·증거

2026-09-14 구현 전 등록. evidence는 `../evidence/ep036/`에 별도 보존한다.

## 결과

2026-09-14 오프라인 수정·검증 완료. 실제 EX-038 결정20의 before 오류와 after 계산/B2/backend 가짜 전달을 확인했다.
고정 Showdown4시나리오/16시점, 신규35 포함 관련430회귀·Ruff/compileall/Node 검사 통과.
EX-037/038 저장 결정3996개 parser 비교에서 기존 정상3993개 동일, 동일 원인 오류3개 복구.
203 source 별도 봉인, 기존128,030파일 불변. 유료·재수집·추가 설명 검토0.
최초 diagnostic의 cwd 데이터 경로 실패와 별도 validation-v2 통과를 모두 보존했다.
기존 EX-038/EP-035 Blocked·부분 결과·전수 계산 재생 미완료와 미검토803건은 유지한다.

[검증 보고서](../../../exec-plans/evidence/ep036/report.md), [검사 receipt](../../../exec-plans/evidence/ep036/verification.json),
[source hash/보존](../../../exec-plans/evidence/ep036/source-preservation.json).
