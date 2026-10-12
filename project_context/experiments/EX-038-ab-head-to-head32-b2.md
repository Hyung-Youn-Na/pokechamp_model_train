# EX-038 — 원본 A 대 B2 직접대결32

- 상태: Blocked
- 등록일: 2026-09-14
- 관련: D-047, EP-035, C-031

## 사전 protocol

2026-09-14 사용자가 EX-037 직접대결 재사용, 코드 버그만 확인한 뒤 바로 본실험 진입을 선택하고 제시된 계획의 구현을 명시적으로 지시했다.
새 EX-038은 A 원본과 EP-034의 동결 B2 전달 표현을 비교한다. 기존 Blocked는 재개하지 않는다.
EX-037 봉인 팀·32행·16쌍·게임/actor seed·배치·제출순서를 복사한다. Gen9 OU singles,
glm-5.3-flash/low/temperature0/model seed100/출력131072/provider 기본 context, 동시성8이다.
A 입력/IO 재질의/fallback과 B 관측/prior/Protect 수정/계산식/calculator-input-v2/mechanics-v2/출력복구는 유지한다.
요약·외부 메모리·추가 모델 심사0. B2의 추가 압축·설명서 조정0이다.
변경 경로 로컬 회귀·무네트워크 실제 요청 포착·실행 정책 검사를 통과한 source receipt 후 연속32를 실행한다.
fake32·Cloud gate·smoke·첫10 gate는 skipped_by_user이며 통과 증거를 만들지 않는다.
양측 합계8000요청(실패·미확정·A 내부 재질의 포함), 첫 유료 호출부터 수집20700초/정리21600초,
경기 watchdog3600초, HTTP min(300초,잔여 허용시간). slot1회, provider retry/대체/보충/재수집0.
독립 ab-head-to-head32-b2-v1 정책, ex038-cloud identity, .pokechamp-data/ab-head-to-head32/ex038 및 새 원장·시계·study link를 사용한다.
같은 실험의 새 폴더/재시작으로 시계·상한 초기화 금지. 과거 원장·시계·자료를 보존한다.
개별 provider/timeout/환경 실패는 경기 실패이며 상대 승리로 계산하지 않는다.
공유 입력/계산/설정/무결성/permit 결함은 영향범위 중단, 불명확하면 전체 중단한다.
C-018/연구설계11.1의 보존·영향조사를 적용하고 수집 중 source/평가기준 변경 및 유료 복구는 하지 않는다.
실행기는 기존 one-shot coordinator를 확장하며 선택 재수집은 지원·허용하지 않는다.
모든 생성 입력·응답(실패 경기 포함)을 원본/실제 전달/계산/행동/원장·공개prefix에 연결해 검토한다.
B 승률·무승부보정점수·완료쌍 B점수평균·block/배치별 성적, 예정/시도/유효/실패/무효/미실행,
A/B 호출/token/문자/byte/지연/fallback/오류와 양측 viewer를 보고한다.
같은 B결정 원본의 B0 표현을 오프라인 생성해 입력량을 비교하며 추가 유료 호출0이다.
A–B2 개발대진 전체 구성 비교이고 자동 채택 승률 기준은 없다. 과거 EX-037과는 동시성 및 경기 전개가 달라
차이를 압축의 인과적 효과나 L1–L5 효능으로 해석하지 않는다.
유효32·완료쌍16·전수검토·봉인·기존자료 보존·정리 전부 충족해야 Completed다.
미달이면 부분 결과와 원인을 보존하고 Blocked로 남긴다. 중단처리 완료는 비교완료가 아니다.

## 진행·결과

B2 실제 전송 연결 및175코드검사 후 실행했다.26시도·정상종료17·실패/취소9·미실행6, 완료8/16쌍이다. 정상 종료분 B13승4패(76.47%), 완료쌍 B평균0.75. 전체32 비교는 미완료다.

기존 관측 parser의 `unsupported delayed effect destination`으로 전체 수집 중단. Healing Wish 직후 Future Sight 대상이 `p2:` 형식이 되어 B2 생성 전에 실패한 사례를 공개 prefix로 재현했다. 별도 A provider timeout1도 보존했다. runtime 수정·재시도·재수집0이다.

사용자의 후속 지시로 설명오류 기입은902/1705응답에서 조기 종료했으며803응답은 미검토다. 전수 공개 prefix 재계산도 중단했고 통과로 주장하지 않는다. 완료된 기술 무결성 검사와 B2 원본/실제전달 검증839건은 오류0이다. 동일 원본 B0 대비 전체 문자31.03% 감소; provider 토큰 절감의 대조실험은 아니다.

기존120,182파일/source200 보존 및 소유 process/포트/작업트리/잠금/permit 정리를 확인했다. [최종 결과·양측 viewer·검토 범위](../exec-plans/evidence/ep035/final-report.md).
