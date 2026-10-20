# EX-103 — Jev-Omni + GLM-5.3 low 동일 대진

- 상태: Completed
- 생성일: 2026-10-15
- 승인: 현재 사용자 제공 계획 / [D-156](../decisions/D-156-jev-omni-low.md)
- 계획: [EP-162](../exec-plans/completed/EP-162-jev-omni-low.md)
- 연구선/branch/checkout: research/model-training /workspace a4659bf; 기존 미커밋 변경 보존.

## 질문·처치·불변 조건

EX-102의 팀·대진·seed·공개 관측·계산·후보·전략/수행 지시문·사건 정책을 참조 편입한다.
수행 모델 패키지를 akhilaaa3/Jev-Omni revision fee89b076e2263bfa8bce8d34142caa4ca733a48로,
GLM reasoning_effort를 high→low로 변경한다. 모델별 formatter/backend/환경 차이를 명시한다.
멀티모달을 사용하지 않고 전체 state·계획·지시문·후보 객체·ID·순서를 보존한 텍스트를 전달한다.
공식 숫자 선택지/chat template·enable_thinking=False·BF16 적재/autocast·마지막 hidden-state·
256슬롯 head를 사용한다. 모델 카드 FP32 안내와 공식 코드/체크포인트 차이를 기록한다.
공식 선택 index를 후보 ID로 매핑하고 원확률은 재정규화하지 않는다. 확률 오류는 진단이다.
실제 입력 토큰·output_tokens:0을 기록하고 CPU guard와 추론은 같은 processor/tokenization을 쓴다.
최대32768토큰·16후보·절단0. NVFP4/Marlin 재사용0.

GLM glm-5.3/thinking enabled/low/temperature0/top_p0.95/max_tokens131072.
events:[faint,tera,forced_switch,active_change,form_change]·최초선봉·단일후보무호출·보류/중복제거 유지.
actor pokechamp/.venv/bin/python; 별도 .pokechamp-data/jev-omni-runtime/.venv/bin/python.
Torch2.13.0+cu129·torchvision0.28.0+cu129·Transformers5.17.0·Accelerate1.15.0 고정·의존성 봉인.

## 한도·중단·복구

GLM 물리HTTP128·수행모델 논리256(사전8포함)·경기1·GPU0단독/동시1·allocator40GiB/
GPU전체44GiB·소유host32GiB·경기/전체시간/disk:null. 사용량 기록·실제I/O 오류 처리 유지.
8109/18845 포트 점유시 미진입. 기존 사전요청8회는 새 단일서버에서 수행하고 같은 서버로 경기.
반복 선택 일치는 필수·확률차이는 probability_diagnostic. 별도 유료 probe0.
RD11.1/C-018·RD11.2/C-046 적용. source/조건 동결 후 불변. gate 실패 시 부분 기록/사유 보존·정리.
추가GPU·양자화·대체모델·재경기·재수집·자동재개0. 최초시계·누적상한 초기화0.

## 검증·출력·완료

CPU 공식입력 동치/토큰ID/후보순서/역매핑/head/출력0/확률진단/중복방지/identity·서버 회귀.
EX-101/102 저장입력과 사전8개 길이 전수검사. 불변 사건정책 검증은 차이를 확인해 재사용.
실제 low HTTP/재시도/usage·모든 호출/미호출 공개사건·Omni 원문/forward/원장/명령/자원 감사.
EX-102 전체 처치와 EX-101 low 비교: 승패·턴·호출·계획유지·지연·토큰·행동 사례.
단일경기로 일반성능/인과효과 주장0. 전략/설명 정확성 전수평가는 RD8.1 기본 제외.
정상1경기·필수감사·이동후 오프라인/복사/다운로드·기존봉인 보존·새 봉인·자원 반환이 완료 기준.
미충족은 정상 완료와 구분한다.

run: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-103
증거: project_context/exec-plans/evidence/ep162
viewer: exports/battle_viewers/ex103/index.html
condition: glm53-jev-omni-matchup-events-low

## 결과

정상1/1·실패0·player_lost·71턴. [최종 보고](../exec-plans/evidence/ep162/report.md). 추가실행0.
