# EX-097 — GLM 형식 재시도·temperature0 NVFP4 샘플1경기

- 상태: Completed
- 생성일: 2026-10-15
- 승인: 현재 사용자 지시 / D-150
- 계획: [EP-156](../exec-plans/completed/EP-156-planner-format-temperature-zero.md)
- branch/checkout: research/model-training /workspace a4659bf·기존 변경 보존

## 질문·조건·처치

[EX-096](EX-096-nvfp4-battle-probability-diagnostics.md)의 실패를 보존하고 같은 대진의 새1경기를
수집한다. 변경은 GLM temperature1→0, retry_scope=json_syntax→response_format 두 가지다.
새 기본값에도 적용하며 반복 확률은 probability_diagnostic을 유지한다. 비교는 결합 처치의
기술·행동 사례로 제한하고 단일 경기로 성능 향상/인과 효과를 주장하지 않는다.

모델/revision·GPU0 TP1 Marlin W4A16/BF16·공식 환경/head/calibration·prefix cache·8사전추론·
32768입력/32769엔진/readout1·16후보·세프롬프트·v6/names-v1·팀/seed/첫슬롯b01-r3-s1/p1/Abyssal p2·
최초/3턴/기절/Tera/강제교체·GLM enabled/low/top_p0.95/max_tokens8192는 EX-096 원문을 유지한다.
사전 선택 일치/매핑·메모리·Marlin/rank320 검증은 유지하고 확률차이만 진단한다.

## 재시도·한도·중단·출력

C-070/D-150의 response_format 정책으로 성공HTTP의 envelope·빈/잘린 응답·JSON 구문/중복키/
비유한값·6필드/if-then 스키마 실패를 같은 입력/옵션으로 최초+최대5회 생성한다.
전송 재시도는 기존 provider-retry-v2, 최종429는 수집 중단이다. 유효 전략의 의미 판단은 대상이 아니다.
모든 생성/HTTP 원문/usage·분모를 보존하며 전체 GLM HTTP128 안에 포함한다.

경기1·JEV논리256(사전8포함)·경기3600초·최초적재부터전체4200초·GPUallocator40GiB/전체44GiB·
소유host32GiB·disk null/사용량 기록. 포트18845/18846/8109 점유 시 진입하지 않는다.
모델/포맷 불변 CPU 검증은 EP-154를 재사용하며 정책 변경은 새 CPU검증한다.
RD11.1/C-018·RD11.2/C-046의 오류 격리와 원본보존을 따른다. 본 수집 뒤 source/조건 변경0,
출력복구 소진/실행 실패는 해당 경기 실패이며 재경기/자동재개0이다.

run: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-097
증거: project_context/exec-plans/evidence/ep156
viewer: exports/battle_viewers/ex097/index.html

정상1경기·실패 포함 분모/GLM 생성/재시도/usage·JEV/엔진·선택→명령·메모리/반환 전수감사·
통합뷰어/대표 이동후 오프라인/복사/다운로드·run/viewer/evidence 봉인이 완료 기준이다.
미충족 시 이유와 부분자료를 보존한다. 설명 정확성은 기본 제외다.

## 결과

정상1/1·실패0·player_lost·턴35. GLM HTTP20, 형식 재시도1, 구문 재시도1.
[최종 보고](../exec-plans/evidence/ep156/report.md)와 감사/뷰어/자원/봉인을 연결했다.
