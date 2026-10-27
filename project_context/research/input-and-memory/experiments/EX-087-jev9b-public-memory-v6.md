# EX-087 — JEV-9B 공개 정보 v6 신규32경기

- 상태: Blocked
- 등록일: 2026-10-13
- 승인: 현재 사용자 계획 구현·검증·실행 지시 / D-135 / EP-140
- 기준 연구선·실제 branch: `research/model-training`, checkout `/workspace`
- 시작 commit: `a4659bf298c7935714f9fbd25246db2d831c5926`
- 시작 미커밋 변경: EX-084/085 코드·문서·실행기를 보존한다.

## 동결 조건과 차이

[EX-086 공통 protocol](EX-086-jev27b-public-memory-v6.md)의 질문·v6 처치·32슬롯·정책·
자원·시간·검증·실패/복구·감사·비교·완료 조건을 그대로 적용한다. EX-086 뒤GPU0–3을 독점해
신규32경기·16쌍을 실행한다. 수정 전 기준은 EX-08532경기이며 기존 결과는 신규 분모에 넣지 않는다.

공식 `autotrust/JEV-9B` revision `7ac669b8fb476ba926491e3d1c39f9330d68dbed`와
기존 `.pokechamp-data/jev9b-runtime/model`을 재사용한다. 공식 LoRA 병합·BF16 backbone·
FP32 `24×4096` head·bare-v1·Choice 보정값 `0.9840233476014968`은 EX-085와 같다.
GPU0 embedding/0–5층, GPU1 6–15층, GPU2 16–25층, GPU3 26–31층/norm/head다.
본서버1회 적재·최대8추론 gate 뒤 같은 서버로 수집하며27B와 선택/확률 일치를 요구하지 않는다.

명령은 `scripts/jev-eval {prepare|execute|status} --experiment EX-087`이다.
출력 `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-087`,
뷰어 `/workspace/exports/battle_viewers/ex087/index.html`로 분리한다.
모델/actor/브라우저 환경은 EX-086 공통 경로를 재사용한다.

## 현재 결과

CPU/환경·8사전입력의 무절단 길이 준비는 완료했다. 동일source의CPU231통과 근거를EX-086에
연결해 재사용했으며 최장17,271토큰이다. 그러나 EX-086에서 공유 입력 결함이 발생하여
**GPU 실행 전에 중단**했다. 예정32·시도0·유효0·실패0·미실행32·유효쌍0/16이며
모델 적재·사전/본수집 추론·HTTP POST·경기는 모두0이다.

EX-085/EX-086 공통 유효쌍 비교와 승무패 점수는 산출하지 않는다. 실제 경기원문이 없어
뷰어는 생성하지 않았다. 원준비·source와 의존중단 기록을 봉인하고 자동재개하지 않았다.
공유 입력 및 사후 집계 교정은 별도CPU 근거이며 이 평가를 실행한 것으로 취급하지 않는다.

[통합 중단 보고](../../../exec-plans/evidence/ep140/report.md) ·
[종결 연결](../../../exec-plans/evidence/ep140/completion.json).
