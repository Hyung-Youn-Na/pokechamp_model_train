# EX-098 — GLM high 추론 강도 NVFP4 동일 대진1경기

- 상태: Blocked
- 생성일: 2026-10-15
- 승인: 사용자 현재 지시 / D-151
- 계획: [EP-157](../exec-plans/active/EP-157-planner-high-effort-sample.md)
- branch/checkout: research/model-training /workspace a4659bf·기존 미커밋 변경 보존

## 질문·고정 조건·해석

[EX-097](EX-097-planner-format-temperature-zero.md)의 reasoning_effort=low만 **high**로 바꾼
새 실제1경기를 수행한다. 계획은 새 경기에서 생성하며 저장 계획/상대의 숨은 세트/미래행을
입력하지 않는다. GLM의 Ruination KO 오판/반복 선택 사례·호출 지연·토큰·출력복구와 결과를
기술적으로 비교한다. 일반 승률/성능 향상·인과효과는 단일 표본으로 주장하지 않는다.
행동이 달라지면 이후 상태/입력도 달라지므로 같은 입력의 통제 실험으로 해석하지 않는다.
전략/설명 전수 정확성 평가는 기본 제외하며 특정 Ruination 사례만 관찰한다.

변경은 GLM glm-5.3-flash enabled/high/temperature0/top_p0.95/max_tokens8192 중 effort다.
공용 기본 low를 바꾸지 않고 이 EX에high를 명시한다. EX-097의 세프롬프트·피해 포함v6/names-v1·
호출정책·response_format 최초+추가5회·HTTP정책/최종429중단을 그대로 사용한다.

모델 autotrust/JEV-35B-NVFP4 revision10c2c62610e315e31a75baca849ad79d526e4658·
GPU0 TP1/동시1 Marlin W4A16/BF16 eager0.80·rank320/System1·공식37파일/head/calibration·
기존 고정환경·prefixcache·32768입력/32769엔진/readout1·16후보·8사전추론은 EX-097 원문을 유지한다.
반복 선택 일치는 요구하고 확률1e-4 초과는 probability_diagnostic으로 기록한다.
첫슬롯b01-r3-s1·자기p1/Abyssal p2·팀/battle seed20892,520,39040,28395·
actor seed3890316613/3478776278과 원래 생성정책을 유지한다.

## 한도·검증·중단·출력

새 단일적재·사전8추론 포함 JEV논리256·GLM물리HTTP128·경기1·경기3600초·최초적재부터전체4200초,
GPUallocator40GiB/전체44GiB·소유host32GiB·disk null/사용량 기록을 유지한다.
포트18845/18846/8109 점유 시 진입하지 않는다. 새 모델probe/추가 재적재/재경기0이다.
source/환경/formatter가 EX-097과 같음을 확인하고 기존 CPU/브라우저/무손실/호환성 검증을
재사용한다. 새 설정의 단일 차이와 실제 HTTP high/temperature0·입력/응답/finish_reason·토큰/
모든 생성/전송/원장/자원은 전수 확인한다. 자산 identity/봉인은 보존 검증한다.

RD11.1/C-018·RD11.2/C-046·C-070/073의 격리/원문보존·소유 자원 정리를 따른다.
출력복구 소진/실행 불가능 응답은 해당 경기 실패이며 원자료를 보존하고 재경기/자동재개하지 않는다.
합법 전략 판단은 의미 gate나 재시도로 교정하지 않는다. 수집 source/조건 변경0이며 한도 확대0이다.

run: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-098
증거: project_context/exec-plans/evidence/ep157
viewer: exports/battle_viewers/ex098/index.html

정상1경기·실패 포함 분모/원문/호출/토큰/선택→명령/자원 전수감사·EX-097 기술비교·
통합뷰어/대표 이동후 오프라인/복사/다운로드·run/viewer/evidence 봉인·자원반환이 완료 기준이다.
미충족 시 차단 이유와 부분 기록을 보존한다. 과거 EX-093~097의 원자료/판정/봉인은 불변이다.

## 후속 시간 연장 요청·적용 제약

사용자가 진행 중인 경기의 시간 상한 해제를 요청한 뒤 “안되면 억지로 하지마”라고 지시했다.
현재 실행기는 양쪽 actor/전체 예산의 메모리 고정 시계를 변경하는 제어 경로가 없고
프로세스 메모리 접근도 허용되지 않아 연장은 적용하지 못했다. 강제 수정/보안 변경/재시작/
새 경기는 수행하지 않는다. 원3600/4200초 한도를 유지한 실행의 실제 종료를 보존한다.

## 결과

정상0/1·중단1·사용자요청·마지막관측19턴.
GLM HTTP18·구문재시도7·기타형식재시도0.
[최종 보고](../exec-plans/evidence/ep157/report.md)에 감사/비교/뷰어/자원/봉인을 연결했다.
