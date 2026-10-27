# EX-107 — Tacit-9B 규칙 Q&A LoRA

- 상태: Completed
- 생성일: 2026-10-19
- 책임자: Codex
- 승인: 현재 사용자 계획 구현·실행 지시, [D-161](../decisions/D-161-tacit-ruleqa-lora.md)
- 작업: [EP-173](../plans/EP-173-tacit-ruleqa-lora.md)
- 연구선/checkout/시작 commit: research/model-training /workspace a4659bf298c7935714f9fbd25246db2d831c5926. 기존 미커밋 변경 보존.

## 질문·범위

생성한 규칙 자료의 정답·짧은 근거 SFT가 동일 템플릿 계열의 규칙 정답률과 State 적용을 개선하는지 탐색한다.
학습1회·오프라인 평가·비병합 어댑터·한국어 보고까지 수행한다. 실제 배틀·긴 Thinking·미지 형식 일반화는 평가하지 않는다.

## 동결 조건

로컬 morriszjm/Tacit-9B revision 884838f1698d1fd746625b3c20c8ec2be077a183.
기반 `.pokechamp-data/tacit9b-runtime/model`, interpreter `/ref/kev/.venv/bin/python`.
Torch2.8.0/Transformers5.17.0/PEFT0.21.0, SDPA·Torch native Gated DeltaNet. 다운로드/환경 갱신0.
자료는 보존루트 datasets/generated/showdown-ruleqa/v1의 검증된 messages와 canonical이다.
train4608/validation576/test576, short_qa/state_qa/state_mc=1:1:1. split·중복 연결 성분 유지.
metadata/evidence/oracle는 모델 입력 제외. assistant 정답·근거·종료 토큰만 손실, 빈 Thinking prefix 마스킹.
native template enable_thinking=False, 전체 토큰의 생성 prefix 일치 필수. 절단/packing0, 최대5120.
문항별 target-token 평균을 문항 간 평균한다. 정답 예측 위치만 logits 생성, 일반 masked loss와 fixture 동치 검사.

물리GPU1·2·3 UUID만 노출하고 공용 잠금 사용. GPU0 사용0. DDP 프로세스3, GPU당 batch1·accumulation8=24.
기반 BF16 고정, LoRA/optimizer FP32, BF16 autocast. 텍스트 all-linear(embedding/LM head 제외),
r16/alpha32/dropout0.05/bias none, 학습 parameter43,278,336.
3epoch·192step/epoch·총576step. AdamW lr1e-4/betas(0.9,0.95)/weight_decay0.01,
cosine/warmup18/clip1.0/seed20261019. non-reentrant checkpointing, 학습 use_cache=False.
매48step 완전 checkpoint(optimizer/scheduler/각 rank RNG/데이터 위치). 동일 설정 완전 checkpoint만 재개.

## 절차·평가

1. CPU 전수 행 대응·길이·분할·마스킹·집계·모델/자료/소스 판본 기록.
2. train 긴 문항과 세 형식24문항 DDP1업데이트. 유한 loss/gradient, LoRA변화, 기반고정, GPU별 최대44GiB 미만. 폐기 후 초기화.
3. 기반 validation576 생성/NLL.
4. 매epoch validation576; State MC 정확도 내림차순→assistant NLL 오름차순→이른 epoch 선택.
5. 선택 기록 확정 후 기반/선택모델 test576 각각1회. greedy/max_new_tokens192/Thinking off 동일.

주지표 State MC192 생성 정확도. 첫 비어있지 않은 답변 줄의 시작에 명시된 단일 option ID를 채점한다.
ID 단독 또는 ID 뒤 점/괄호/콜론과 답변을 허용하며 다른 단일 option ID가 함께 제시되면 형식 오류다.
후보밖/형식오류는 오답. 자유 QA는 첫 답변 줄 Unicode NFKC·casefold·공백정규화 문자열 일치율이며 의미 정확도로 주장하지 않는다.
24규칙별·대조묶음 두 상황 모두 정답·형식오류·192토큰 상한·문항 평균 assistant NLL을 보고한다.
규칙마다 사전 ID정렬 첫 test대조쌍 State QA 총48상황을 모델명 블라인드로 의미/적용/수치·상태/미공개추정 검토한다.
검토자가 에이전트임을 명시한다. test 중복연결성분82개 단위 paired bootstrap10000회(seed20261019),
State MC 정확도 차이95% percentile 구간. 세 표현을 독립 표본으로 세지 않는다.

## 자원·중단·복구

출력 `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-107`.
시간은 사전검사 실측 추정·누적 기록하며 임의 시간상한을 추가하지 않는다. 학습량은576step으로 제한한다.
OOM·비정상 수치·누출·GPU배정 오류는 영향 단계 중단·증거 보존. 조건을 자동 완화하지 않는다.
RD11.1/C-018의 도구결함 복구 적용: CPU/fixture 교정·저장응답 재채점 허용, 본학습 추가 주기와 test 재생성0.
중단 후 온전한 동일설정 checkpoint만 재개하며 누적진행을 초기화하지 않는다. 사전검사 실패는 원인/수정/독립검증을 보존하고 판단한다.
모델 오답/형식 오류는 측정 결과이며 도구결함 재시도 사유가 아니다. 외부 API·배틀0, C-047 viewer 해당없음.

## 완료·증거

선택 비병합 PEFT adapter, 기반 연결/revision, tokenizer/config, 완전 checkpoint, 학습곡선,
문항별 원응답·실패, 규칙별 비교표·bootstrap·블라인드 검토·한국어 보고·로딩예시·저장후 재로딩 검사.
성능 향상 여부와 완료 여부를 구분한다. 실행 전이며 성능 미측정.

## 최종 결과

2026-10-19 3epoch/576step·28,491,045 train토큰, validation으로3epoch를 선택했다.
잠긴test 두모델 각576문항을1회 평가했다. StateMC114/192→184/192(+36.458%p),
82연결성분 bootstrap95%차이구간+28.92~+44.15%p다. 개선71/악화1/둘다정답113/둘다오답7이다.
48상황 블라인드 정답의미검토21/48→44/48이며 비확률표본·단일 에이전트 검토 한계를 유지한다.
선택adapter동일성·3rank재로딩·12완전checkpoint·CPU복원상태검사·최종감사를 통과했다.
GPU단계총8.95시간·물리GPU최대22.59GiB, 실패0. 소유worker종료·반환 및201파일 봉인을 완료했다.
실제checkpoint학습재개·추가학습·test재생성0이다. GPU1의 후속EX108 배틀은 별도소유·범위다.

[완료 보고](../../../exec-plans/evidence/ep173/report.md) ·
[최종 감사](../../../exec-plans/evidence/ep173/final-audit.json) ·
[종결](../../../exec-plans/evidence/ep173/completion.json).
