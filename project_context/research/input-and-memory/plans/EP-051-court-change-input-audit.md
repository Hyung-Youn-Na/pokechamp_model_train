# EP-051 — Court Change 입력 교정·EX-042 전체 감사

- 상태: Completed
- 완료일: 2026-09-16
- 생성일: 2026-09-16
- 승인 근거: 현재 사용자가 제공한 본실험 전 입력 오류 수정·EX-042 전체 감사 계획의 구현·검증 지시.
- 관련: [D-062](../decisions/D-062-court-change-input-audit.md), [C-023](../CONTRACTS.md#c-023--계산기-입력-로컬-조사수정-경계), [EX-042](../../lead-policy/experiments/EX-042-distributed-lead.md)

## 목표·범위·불변 조건

본실험 계획은 보류하고 Court Change 실행 알림의 효과 잔존 및 진영 이력 교환 누락을 교정한다.
EX-042의32경기·64 actor·2213결정 시작·2179 snapshot 전부를 원자료 cutoff에서 감사한다.
자기 제출과 당시 공개 prefix만 입력 생성에 전달한다. 상대 비공개 세팅·미래 기록은 차단한다.
parser_effects·기존 CLI/schema/calculator-input-v2·선봉 전략/Dex·모델/전송·pinned upstream을 보존한다.
과거 실험·source·봉인·보고·승패·Blocked는 변경하지 않고 정정 분석을 별도 연결한다.
유료 호출·새 배틀 실험·과거 실험 재개0. 독립 simulator 사례는 오프라인 단위 검증이다.
겹치는 EP-030/032/035/041/044/045/048 및 해당 계약·연구설계11.1을 확인했다.

## 완료 기준

- [x] 원자료·source·봉인 checksum 확보 및 작업 종료 후 보존 대조
- [x] 공개 근거에 한정한 실행 알림 정규화·교환 대상 진영 이력 이동, 원발생 양 actor 재현/교정
- [x] 모든 결정·snapshot·wire·원장·계산 연결, 없는 snapshot 분류 및 차이의 위치/원인/영향 기록
- [x] 고정 Showdown 독립 사례(양쪽 설치/중첩/스크린/Tailwind/반복/없음/종료/제거/교대 피해·상태), prefix/창/패킷/미래 불변 검증
- [x] 선봉32×네 조합·모의 양 공급자 HTTP·관련 회귀·전체 integration 검증
- [x] 오류 목록·전후 차이·검사별 분모·미지원 범위·manifest·별도 정정 보고 및 상태 동기화

## 검증·진행

2026-09-16 — 구현 전 등록. 기존 구현의 공개 이력은 -swapsideconditions를 처리하지 않으며 pinned Showdown은 명시된 진영 효과만 교환하고 Court Change를 -activate 실행 알림으로 출력한다.
증거 위치: ../evidence/ep051/. 원source 재현과 수정source를 분리하고 같은 코드 재생 일치를 독립 규칙 검증으로 주장하지 않는다.

## 차단·중단

INDEX 공통 기준·RD11.1을 따른다. 비실험 수정/감사이므로 신규 수집·복구 시계·재수집은 해당 없음.
추가 결함은 기존 입력 계약을 복구하는 범위에서 재현·수정·재검증한다. 설명되지 않은 입력 차이나 본실험 경로의 미해결 오류가 남으면 Completed로 표시하지 않는다.

- 전수 독립 공개 사실 감사에서 Static 발동의 명시적 [of] 보유자 누락과 상대 기절 후 effective_types 테라 잔존을 확인했다. 원문·영향 분모와 독립 사례를 기록하고 같은 입력 계약 복구 범위에서 수정·재검증했다. 원본 판정은 보존하며 별도 정정 분석을 연결한다. 감사 v1의 자기 기절 테라 잔존 지적은 Showdown faint 시 terastallized 삭제를 누락한 감사 구현 오류였고, 원자료를 보존한 v2에서 바로잡았다.

## 최종 결과·증거

[최종 보고](../../../exec-plans/evidence/ep051/report.md)·[검증 판정](../../../exec-plans/evidence/ep051/final-verification.json)·[manifest](../../../exec-plans/evidence/ep051/manifest.json).
2,213결정 전부 검사·수정본 재생 성공, 기존2,179 snapshot 중507차이 원인 설명 완료, snapshot 전 실패2복구.
독립 Showdown·선봉32×4·양 공급자 모의 HTTP·전체 integration 범위 검증을 완료했다.
전체 최초1,263통과/1 source 변경 감지 실패를 보존하고 동결 후 해당1개 및 최종 영향82개를 통과했다.
중복 제외 고유1,264검사를 충족하며 단일 연속 실행 all-pass로 표현하지 않는다.
원자료14,382파일 변경0·64 actor 봉인 일치·최종 source262 일치를 확인했다.

[별도 사후 정정](../../../exec-plans/evidence/ep051/impact.md): 당시 유효26경기 중21경기 입력 무효, 오류 미발견 정상 완료5경기,
정정 후 정상 완료쌍0. 기존 원자료·승패·보고·Blocked는 보존했다. 선봉 품질/승률·Gen9 전체 정확성 claim은 없다.
유료 호출·신규 배틀 실험·과거 재개·재수집0이며 본실험 계획은 계속 보류한다.
