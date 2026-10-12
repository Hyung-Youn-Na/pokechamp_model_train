# D-044 — Protect 수정본 직접32 연속 실행

- 상태: Accepted
- 날짜: 2026-09-11

현재 사용자 제공 실행 계획을 명시적 승인 근거로 EX-037/EP-032/D-044를 등록한다.
EX-036을 재개하지 않으며 EP-030 및 모든 기존 Blocked·원자료·봉인은 보존한다.
EX-036 봉인 plan.json의 팀·32행 schedule·16대응쌍·게임/진영 actor seed·A/B 배정·제출순서를 그대로 복사한다.
A 원본 입력/프롬프트/IO 재질의/fallback, B EP-031 Protect 수정 외 calculator-input-v2/battle-v1.2.0/
mechanics-v2/계산식/출력복구를 유지한다. 요약·외부 메모리·추가 모델 심사0.
glm-5.3-flash,thinking low,temperature0,model seed100,출력131072,provider 기본 context다.
새 ab-head-to-head32-protectfix-v1 정책에서만 로컬 회귀·Protect 재생·fake32·Cloud gate·smoke·첫10 게이트를
skipped_by_user로 기록한다. 생략 검사의 qualification/checkpoint 통과를 만들지 않는다.
EP-031의183파일 source hash 2bd51c7e103fa03cb2e22236b37908efbdb030210951543452ca64cf93c6de0a와
현재 일치를 확인하고 새 실행 연결 변경분·최종 source를 별도 봉인한다. 과거732검사를 새 source 결과로 주장하지 않는다.
등록·설정 확인·hash 대조·봉인 후 바로 본32를 실행한다. 최대 배틀/계정/모델 요청 각각10,
끝난 자리마다 즉시 다음 slot을 투입하며 첫10 후 장벽0이다. 기존 정책 정의/hash/기본 동작은 보존한다.
실행 경로 .pokechamp-data/ab-head-to-head32/ex037, bundle identity ex037-cloud, 새 원장/시계/study link/run claim이다.
양쪽 합계8000요청(실패/미확정/A 재질의 포함),최초 유료 요청부터 수집20700초/보존·정리21600초,
경기 watchdog3600초,HTTP min(300초,잔여 수집시간). 같은 EX-037의 재시작/새 폴더로 상한 초기화 금지.
EX-036 시계/원장/529요청은 별도 보존·연결하며 새 성적 분모에 합치지 않는다.
slot1회,provider retry/보충/재수집0. 개별 provider/timeout/환경 실패는 경기 실패로 기록하며 상대 승리로 계산하지 않는다.
공유 입력/계산/설정/무결성/permit 결함은 영향범위 중단,불명확하면 전체 중단한다.
C-018/연구설계11.1의 보존·영향조사 적용,수집중 source/평가기준 변경0,유료 복구0.
종료 후 전체 요청/응답/계산/선택/실제전송/actor격리/원장·공개prefix 연결을 전수검토한다.
사실·규칙 오류,입력 문제,출력복구,실행실패,전략미확정을 분리하고 양측 viewer를 제공한다.
B의 A상대 승률·무승부보정점수,완료쌍 B점수평균,블록/팀배정별 결과,예정/시도/유효/실패/무효/미실행,
A/B 요청/token/지연/fallback을 보고한다. 전체 구성의 개발 대진 비교이며 Protect 단독 효과나 L1–L5 효능으로 귀속하지 않는다.
유효32·완료쌍16·전수검토·봉인·기존자료 보존·자원정리 전부 충족해야 비교 완료다.
중단 시에도 수집분 검토/보고/보존/정리와 실제분모·미완료 사유를 기록하며 중단처리 완료를 비교완료로 표시하지 않는다.
