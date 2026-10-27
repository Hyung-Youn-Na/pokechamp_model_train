# EP-031 — Protect 만료 정규화 교정

- 상태: Completed
- 생성일: 2026-09-11
- 승인: 현재 사용자의 Protect 효과 만료 오류 수정 계획 구현·오프라인 검증 지시
- 관련: D-043, C-014/C-018/C-023, EX-036(원자료 읽기 전용)

## 목표·범위

B 공개 prefix에서 만료가 입증된 PROTECT만 계산용 effects에서 제거하고 유효 Protect를 보존한다.
protocol.py의 별도 내부 수명 판정을 state.py 양쪽 개체에 전달한다. 실제 행 순서·turn·upkeep,
교대·기절·명시적 해제 및 재발동을 추적하며 parser 값0과 packet 메타데이터는 시계로 사용하지 않는다.
불충분·모순 근거는 제거 권한이 아니다. 공개 활성화의 parser 누락은 현재 효과에 보완한다.

## 불변 조건·비목표

A·공통 parser·pinned submodule·원자료·봉인·보고서·기존7개 Blocked plan은 보존한다.
CLI/JSON 구조/프롬프트/calculator-input-v2/계산식과 현재 PROTECT 거부는 유지한다.
다른 방어기술·Roost·Substitute·전략·연구 평가 기준 변경 및 유료 호출·재수집은0이다.
기존 source qualification을 새 수정본의 검증으로 재사용하지 않는다.

## 완료 기준

- [x] b01-r2-s0:p2:29 turn25 직전 원본 오류 재현 및 수정 후 계산·입력 검증
- [x] pinned Showdown 실제 volatile 기준 성공/실패/연속/차단/turn/upkeep/교대/기절/해제 검증
- [x] 같은 턴 중간 교대·표기2종·값0·여러 턴 packet·부족/모순 prefix·actor/개체 격리
- [x] 기존 B269 입력 재생·비Protect 불변 대조·수정 장면 fake backend 직렬화 전달
- [x] A/다른 효과 회귀·전체 integration·정적 검사·기존 자료 보존 및 source hash 봉인

## 검증·진행

2026-09-11 등록. evidence/ep031/protect-expiry-v1에 재현·수명 event/line·독립 정답·회귀·보존을 기록한다.
새 유료 실험이 아닌 결함 수정이며 C-018 원자료 보존·독립 재현·회귀를 적용한다.
EX-036 중단/시계/재수집0·EP-030 Blocked는 불변이다. 미해결 필수 검증은 완료로 표시하지 않는다.

- 독립 pinned simulator7조건·64경계/실제 장면 검사를 통과했다. 실제 실패는 event180 line5 발동·line10 upkeep 만료다.
- B269 최초 재생은 elapsed_ms 제외 전체 입력 동일이며 오류 장면만 effects.PROTECT와 state_id가 바뀐다.
- 재현 harness 초기 실행의 worker cwd 및 source-before prior 자산 누락을 교정했다. 실패 로그는 보존한다.
- 전체회귀의 기존 EX-033 대 현재 source 동일성 검사는 승인된 state.py 수정 때문에 실패했다.
  과거 EX-036 봉인 source 대 EX-033 전체 동일성으로 역사적 검사를 보존하고, 현재는 D-043 두 파일을
  새 Protect 검증에 연결한다. 다른 현재 파일·prompt 동일성은 계속 검사한다. 전체 최종 검증은 진행 중이다.

- 최초 전체회귀는730통과/2실패였다. 과거 source 동일성 검사 외1건은 테스트 도중
  test_ab_head_to_head.py가 변경되어 preparation/cohort source hash가 달라진 것으로
  두 봉인의 실제 차이를 확인했다. 운영 변경 없이 최종183 source를 고정한 뒤 전체 재검증 중이다.
- 최종 재생269/269 입력 동일, 양쪽 실패 장면 정규화·계산·EX-036 설정의 fake 직렬화1회 통과.

## 완료 결과 — 2026-09-11

- 실제 실패 재현·수정 후 계산/입력 검증·원시 효과 보존·양쪽 정규화·fake 전달1회 통과.
- pinned Showdown7조건·67시점/268개체와64직접 검사, B269/269 전체 입력 동일(계산 시간만 제외).
- 최종 고정183 source 전체732검사 통과(304.86초), Ruff E/F/I/W·compileall·Node syntax 통과.
- 기존120,148파일·7개 Blocked·두 submodule 및 simulator build 보존, 운영2파일과 관련 역사검사1파일만 변경.
- 유료 호출0·기존 qualification 재사용0. EX-036 중단·EP-030 Blocked와 A/B 비교 미완료 유지.

[보고서](../../../exec-plans/evidence/ep031/protect-expiry-v1/report.md),
[최종 검증](../../../exec-plans/evidence/ep031/protect-expiry-v1/verification.json),
[보존](../../../exec-plans/evidence/ep031/protect-expiry-v1/preservation-final.json),
[변경 검토](../../../exec-plans/evidence/ep031/protect-expiry-v1/changes.patch).
