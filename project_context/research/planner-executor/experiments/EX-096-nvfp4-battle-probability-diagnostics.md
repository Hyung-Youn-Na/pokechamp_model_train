# EX-096 — 확률 변동 진단을 유지하는 NVFP4 실제 샘플1경기

- 상태: Blocked
- 생성일: 2026-10-15
- 승인: 현재 사용자 명시적 실제 배틀 진행 지시 / D-149
- 계획: [EP-155](../plans/EP-155-nvfp4-battle-probability-diagnostics.md)
- branch/checkout: research/model-training, /workspace, 시작a4659bf·기존 미커밋 변경 보존

## 질문·고정 조건

[EX-095](EX-095-jev35b-nvfp4-sample.md)의 반복 확률 gate 실패를 보존하고 새1경기를 수집한다.
성공/실패·실제 계획/선택·사용량을 관찰하는 단일 샘플이며 일반 성능·인과 효과를 주장하지 않는다.
모델·고정 revision·공식37파일·264-slot head/temperature·환경·입력 표현·대진·프롬프트·
전송·한도·기술검증의 원문은 EX-095의 질문/조건과 한도/검증 중 아래 명시한 변경 이외를 계승한다.

모델 autotrust/JEV-35B-NVFP4 revision10c2c62610e315e31a75baca849ad79d526e4658,
GPU0·TP1·동시1·Marlin W4A16/BF16·eager·메모리비율0.80·rank320·System1만 사용한다.
공식 vLLM0.31.0+cu129/torch2.13.0+cu129/Transformers5.17.0의 기존 전용환경을 그대로 사용한다.
prefix caching·mamba align·chunked prefill을 바꾸지 않고 batch-invariant/다른 양자화를 추가하지 않는다.
엔진32769·입력32768토큰·최대16후보·readout1 usage를 보존한다.

EX-094/095 첫슬롯 b01-r3-s1·자기p1/Abyssal p2·팀/시드·계산기v6/names-v1·세프롬프트·
GLM5.3-Flash enabled/low/temperature1/top_p0.95/max_tokens8192 및 최초/3턴/기절/Tera/강제교체
정책을 유지한다. GLM은 새 경기에서 새 계획을 만들며 content JSON 구문만 최초+5회 재생성한다.
HTTP 재시도와 영속 장부의 동일 요청ID 중복 추론 방지도 유지한다.

## 변경된 진입 판정·한도

새 설정 `evaluation.executor_repeat_policy=probability_diagnostic`를 동결한다. 최초/마지막 동일
입력의 선택 일치는 요구하되 확률 최대 차이는1e-4 초과 여부와 원문을 **진단으로 기록**하며
그 값만으로 본경기를 막지 않는다. 과거 필드 부재/strict는 EX-095의 기존 차단 동작을 유지한다.
probability_diagnostic에서도 선택 불일치·잘못된 분포/매핑/usage·입력/토큰 오류·Marlin/rank320/
드라이버·자원 실패는 그대로 진입 차단이다. 확률 재현성을 통과했다고 표시하지 않는다.

새 실행의 단일 적재·최대8사전추론을 같은 서버로 수행하고 통과하면1경기만 실행한다.
GPU 실행/호환성·69입력 CPU 검증은 바뀌지 않은 모델/환경/formatter의 EP-154 근거를 재사용하고,
새 repeat 판정 코드·설정·기존 strict의 보존을 CPU 검증한다. 사전8요청·모델/환경/포트/자원은
다시 동결·확인한다. 환경 재설치/가중치 다운로드·추가 모델 probe는 하지 않는다.

경기1·GLM HTTP128·JEV논리256(이번 사전추론 포함)·경기3600초·전체4200초다.
이번 실행의 최초 적재부터 시계를 시작한다. GPUallocator40GiB/전체44GiB·소유host32GiB·
disk null과 사용량 기록을 유지하며 앞단18845·엔진18846·Showdown8109 점유 시 진입하지 않는다.
자격증명 값은 기록하지 않는다.

## 중단·복구·출력·완료

RD11.1/C-018·RD11.2/C-046·C-070/073을 적용한다. 실제 수집 source/조건은 진입 후 바꾸지
않는다. 출력 복구 소진/실행 불가 응답은 경기 실패로 보존하고 재경기/보충/자동재개0이다.
진입 전 도구 결함은 원본보존·CPU교정/독립검증만 허용하며 적재/호출/시간 상한을 늘리지 않는다.
EX-095는 재개하지 않고 원자료·당시 판정·viewer/evidence 봉인을 그대로 보존한다.

run: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-096
증거: project_context/exec-plans/evidence/ep155
viewer: exports/battle_viewers/ex096/index.html

정상1경기·실패포함 분모/GLM생성·재시도/JEV·엔진/선택→명령/usage·자원 전수감사·EX-094
기술비교·원문/피해 통합뷰어·대표 이동후 오프라인/복사/다운로드·봉인·자원 반환이 완료 기준이다.
미충족 시 부분 기록과 이유를 보존한다. 설명 정확성은 기본 제외다.

## 결과

7턴 GLM contingency 추가 note 필드로 정상0/1·실패1. 당시 스키마 오류 재시도0이다.
사전8/본8 JEV·GLM4·8명령·9관측을 감사/부분뷰어/봉인/반환했다. 자원 감시 오류1개를 별도 보존했다.
[실패 종결](../../../exec-plans/evidence/ep155/report.md). 새 사용자 지시는 EX-097에서 수행한다.
