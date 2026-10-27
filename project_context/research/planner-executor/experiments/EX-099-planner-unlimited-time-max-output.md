# EX-099 — 시간 상한 없는 GLM 최대 출력 NVFP4 샘플1경기

- 상태: Completed
- 생성일: 2026-10-15
- 승인: 현재 사용자 지시 / D-152
- 계획: [EP-158](../plans/EP-158-planner-unlimited-time-max-output.md)
- branch/checkout: research/model-training /workspace a4659bf·기존 미커밋 변경 보존

## 질문·처치·고정 조건

[EX-098](EX-098-planner-high-effort-sample.md)은19턴 사용자 요청 중단·승패 미확정으로 보존한다.
새 경기에서 계획을 생성하며 다음만 바꾼다.

- evaluation.limits.battle_seconds:3600→null, total_seconds:4200→null
- planner.max_tokens:8192→131072(공식 API 최대)

경기/전체 경과시간으로 중단하지 않으며 양쪽 actor·예산·세션/로딩·전송 전 검사에 동일하게
적용한다. 상대 request watchdog도null로 기록하며 내부 무한대는 JSON에 쓰지 않는다.
시간 및 출력 한도 변화가 결합된 단일 기술/행동 사례로 해석하고 일반 성능/인과효과는 주장하지 않는다.
EX-098과 GLM 지연/usage·length/형식/HTTP 재시도·Ruination 선택 사례와 승패/분모를 비교한다.

나머지는 EX-098 원문의 조건을 유지한다. GLM glm-5.3-flash thinking enabled/high·temperature0·
top_p0.95·세프롬프트·피해 포함교정v6/names-v1·최초/3턴/기절/Tera/강제교체 호출·
response_format 최초+최대5회 재생성·provider-retry-v2/개별 통신 timeout·최종429 중단은 같다.
모델 autotrust/JEV-35B-NVFP4 revision10c2c62610e315e31a75baca849ad79d526e4658,
GPU0 TP1/동시1 Marlin W4A16/BF16 eager0.80·rank320/System1·공식 head/calibration·
기존 고정환경/37파일·prefixcache·32768입력/32769엔진/readout1·16후보·8사전추론을 유지한다.
반복 선택 일치·원ID/분포/usage·Marlin/메모리 검사와 확률차이의 probability_diagnostic을 유지한다.
첫슬롯b01-r3-s1·자기p1/Abyssal p2·팀/battle seed20892,520,39040,28395·
actor seed3890316613/3478776278을 그대로 사용한다. 과거 계획/미래/상대 숨은 세트를 넣지 않는다.

## 한도·검증·중단·출력

GLM 물리HTTP128·JEV논리256(사전8포함)·경기1·GPUallocator40GiB/전체44GiB·소유host32GiB·
disk null/사용량 기록·포트18845/18846/8109 점유 시 미진입은 같다. 호출 상한을 해제하지 않는다.
시간/출력 이외 조건을 바꾸지 않고 새 단일 적재·사전8추론 통과 서버의 본1경기로 수행한다.
개별 통신 오류/timeout은 기존 HTTP 정책을 따른다. 출력복구 소진/실행 불가 응답·호출 상한·
메모리/무결성 실패는 원자료를 보존해 해당 격리 범위에서 중단한다. 재경기/보충/자동재개0이다.
사용자 취소·자식/서버 실패 감시·자원 정리는 시간 무상한에서도 유지한다.

RD11.1/C-018·RD11.2/C-046·C-070/073을 따른다. 새 null 시간 구현은 CPU에서 검증하고,
불변 모델/formatter/무손실/head/환경 검증은 EP-154/157의 source/환경 일치 범위에서 재사용한다.
실제 max_tokens/high/temperature·watchdog null·한도·분모·원문/usage·선택→명령을 전수 감사한다.
수집 중 source/조건 변경0이다. 전수 전략/설명 정확성 평가는 기본 제외다.

run: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-099
증거: project_context/exec-plans/evidence/ep158
viewer: exports/battle_viewers/ex099/index.html

정상1경기·실패 포함 분모/모든 모델/엔진/원장/사용량·자원 감사·EX-098 기술비교·
통합뷰어/대표 이동후 오프라인/복사/다운로드·run/viewer/evidence 봉인·자원반환이 완료 기준이다.
미충족 시 부분 기록과 차단 이유를 보존한다. 기존EX-093~098 원자료/상태/봉인은 불변이다.

## 결과

정상1/1·실패0·player_won·종료턴47·마지막관측47턴.
[최종 보고](../../../exec-plans/evidence/ep158/report.md)에 실제 분모/감사/비교/뷰어/자원/봉인을 연결했다.
