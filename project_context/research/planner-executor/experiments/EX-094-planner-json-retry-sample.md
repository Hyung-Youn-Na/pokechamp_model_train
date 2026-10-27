# EX-094 — GLM JSON 구문 재시도 적용 샘플

- 상태: Completed
- 완료일: 2026-10-15
- 생성일: 2026-10-15
- 승인: 사용자 최대5회 JSON 구문 재시도 설정 후 다시 실행 / D-146
- 계획: [EP-152](../plans/EP-152-planner-json-retry-sample.md)
- 연구선/branch·checkout: research/model-training, /workspace; 시작 commit a4659bf·기존 미커밋 변경 보존

## 목적·고정 조건

EX-093의 실패 뒤 명시적으로 승인된 출력복구 처치의 새1경기다. 정상1경기 및 계획/선택·
재시도/usage·원문 연결을 확인한다. EX-093과 같은 모델/입력/수행 지시문·대진·호출정책을 쓰며
추가되는 차이는 planner.json_retries=5와 그 기록/표시다. 일반 승률/인과효과를 검정하지 않는다.

대진/팀/시드·GLM/JEV9B 모델 revision·4GPU 배치·세 프롬프트/생성옵션·기본3턴/사건 호출은
[EX-093 고정 조건](EX-093-planner-goal-completion-sample.md)의 원문과 동일하다.
첫슬롯 b01-r3-s1, p1 대 Abyssal p2·팀1/2·battle_seed20892,520,39040,28395,
actor_seeds3890316613/3478776278. 원 일정/팀을 그대로 복사해 동결하고 해시/의미를 대조한다.

## 출력복구·한도·분모

[ D-146](../decisions/D-146-planner-json-retries.md)의 content JSONDecodeError에만 최초+5회를
허용한다. 같은 messages/관측/옵션을 유지하고 별도 오류 수정 프롬프트·원문 교정·fallback0이다.
정상JSON의 스키마 위반·중복키·지원하지 않는 envelope/출력 오류는 재시도 대상이 아니다.
유효 응답은 재시도를 멈추고 최종검증 후 JEV를 호출한다. 소진되면 해당 경기 실패다.
JSON 생성차수별 기존 HTTP최초+3 재시도 정책은 유지하되 모든 물리 시도가 하나의 전체 예산에
포함된다. 처음부터 planner HTTP128·JEV논리256·경기1·경기3600초·전체4200초다.
새 실행의 최초시계/누적사용량을 보존하며 추가경기·probe·GPU재로딩 반복·재경기0이다.

자원/credential/실행 interpreter·Z.ai HTTP/로컬 JEV 전송정책은 EX-093과 같고 GPU0–3,
allocator40GiB/GPU44GiB·소유host32GiB·전체공유/참조/새출력/임시자료disk100GiB를 지킨다.
자격증명 값은 기록하지 않는다. 외부 추가자원 감시를 유지한다.

## 검증·중단·복구

RD11.1/C-018·RD11.2/C-046·C-070/073과 D-146을 적용한다. 모든 실패/usage·원문과
JSON재시도/HTTP시도를 구분한다. 순수 구문 오류를 회복할 뿐 합법 선택/전략 의미를 고치지 않는다.
입력/전송/무결성/자원 오류는 의존 수집 중단이며 수집 source를 중간에 바꾸지 않는다.
출력복구 소진·그 밖의 사용불가 응답은 경기 실패다. 재경기/보충/자동재개0이다.
배틀 진입 전 도구 결함은 기존과 같은 원본 보존·CPU교정/독립검증만 허용하며 시도/한도를 늘리지 않는다.
설명 정확성은 미평가(기본 제외)다.

## 출력·완료 기준

scripts/jev-planner prepare/run --mode live를 새 디렉터리에서 사용한다.
run: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-094
stdout/감사/보고: project_context/exec-plans/evidence/ep152
viewer: exports/battle_viewers/ex094/index.html

정상1경기·전수 기술감사·원문/재시도/피해 통합뷰어·대표 이동후 오프라인·봉인·자원 반환이
완료 기준이다. 실패하면 정상/실패/미실행·미확정usage·부분기록/뷰어와 목표 미달을 보고한다.
EX-093·EP-151의 Blocked·원자료·뷰어·봉인은 보존한다.


## 최종 결과

예정1/시도1/완료1·실패0/미실행0이며64턴 p1 패배로 정상 종료했다.74관측/결정/전송,
JEV 실제69추론·자동5회, GLM28논리/생성/HTTP를 기록했다. JSON 구문 재시도/HTTP재시도0이다.
이번 경기에는 구문 오류가 없었고 최초+5회 복구는 합성/EX-093 원문 재생 검사에서 검증했다.
GLM입력411,454/출력23,989토큰, JEV입력1,187,808/출력0토큰,
실행 경과989.557초(약16분30초)다. 대응쌍0이며 일반 성능 향상은 주장하지 않는다.

전수 기술감사·74결정 통합뷰어/원자료 대조·대표3 이동후 오프라인/복사/다운로드 검사와
봉인·GPU/프로세스/잠금/포트 반환을 완료했다. 실제 로컬 GPU0–3 최대MiB는
22,656/22,218/22,234/22,488이며 종료 뒤0MiB를 확인했다. 과거 EX-093 실패·봉인은 보존했다.

[완료 보고](../../../exec-plans/evidence/ep152/report.md) · [감사](../../../exec-plans/evidence/ep152/audit.json) ·
[자원](../../../exec-plans/evidence/ep152/resources.json) · [통합뷰어](../../../../exports/battle_viewers/ex094/index.html).
