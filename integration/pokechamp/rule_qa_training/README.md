# Tacit 규칙 Q&A 학습

[D-161](../../../project_context/research/rule-learning/decisions/D-161-tacit-ruleqa-lora.md) /
[EX-107](../../../project_context/research/rule-learning/experiments/EX-107-tacit-ruleqa-lora.md)의 로컬 오프라인 실행기다.
물리 GPU1·2·3만 사용하고 GPU0의 별도 작업과 기존 실험 산출물을 보존한다.

```bash
scripts/pokechamp-ruleqa-train prepare
scripts/pokechamp-ruleqa-train preflight
scripts/pokechamp-ruleqa-train train
scripts/pokechamp-ruleqa-train evaluate
scripts/pokechamp-ruleqa-train export
scripts/pokechamp-ruleqa-train status
```

기본 출력은 보존루트 `runs/model-training/EX-107`이다. `--output`으로 새 경로를 명시할 수 있지만
새 실험 조건·승인 등록을 대신하지 않는다. prepare는 CPU 토큰화·파일 identity 기록만 수행한다.
preflight/train/evaluate/export는 세 GPU를 잠그고 별도 torchrun 프로세스를 시작한다.
export는 선택 adapter 복사와 재로딩 검증·비교 보고/블라인드 검토 입력 생성까지 수행한다.
status는 저장 기록만 읽는다. 블라인드 검토 결과를 자동 통과 처리하지 않는다.

학습 입력은 검증된 messages export의 system/user이며 assistant만 target이다.
모델에는 input_ids만 전달한다. canonical 관리 metadata는 별도 채점에만 사용한다.
HF5의 native template 반환 BatchEncoding에서 input_ids를 추출한다. 빈 Thinking prefix는 마스킹하고
assistant의 답·근거·im_end만 target에 넣는다. 응답 종료 뒤 template 개행은 학습하지 않는다.
정답 직전부터 마지막 정답 예측 위치까지 logits_to_keep tensor를 전달한다. 작은 GPT/Qwen fixture에서
일반 masked next-token loss와 gradient 동치를 검사한다. microbatch1이므로 padding/packing이 없다.

DDP의 rank별8문항 loss 평균을 DDP3rank에서 평균하여 유효24문항을 동일 가중한다.
각 epoch deterministic shuffle은 모든 train 문항을 정확히1회 사용한다. optimizer는 LoRA만 포함한다.
모든 frozen tensor의 전체 byte digest를 사전검사 업데이트 전후 비교하고 학습에서는 frozen gradient 없음과
유한 gradient/FP32 optimizer 상태를 검사한다. 모델·LoRA·실제 물리 GPU memory 한도를 감시한다.

매48step의 checkpoints/step-NNNN에는 adapter, optimizer/scheduler/진행 위치, 각 rank RNG와
완료 manifest가 있다. 중단 시 같은 prepared/source/config와 완전 checkpoint로만 다음처럼 재개한다.

```bash
scripts/pokechamp-ruleqa-train train --resume /absolute/EX-107/checkpoints/step-0048
```

완료된 평가 원문을 덮어쓰거나 부분 test 추론을 자동 재생성하지 않는다. selection.json이 있어야 test를
평가할 수 있다. 형식 오류와 오답은 실패 분모에 포함하며 조건 탐색·재생성 사유가 아니다.
OOM/비정상 수치/정보 누출/장치 오류는 해당 단계를 중단한다. CLI receipt·rank별 failure·원로그를 보존한다.

출력의 predictions/는 문항별 원응답·token ID·NLL·채점, epochs.json/selection.json은 선택 근거다.
bootstrap.json은 중복연결성분 기반 paired 구간이다. blind-review.jsonl은 모델명 없는48상황이고
blind-key.json은 별도 연결표다. 검토자는 모델명 연결표를 보기 전에 네 rubric 판정을 기록한다.
report.md/rules.csv와 별도 의미 검토를 함께 읽는다. 자유형 문자열 일치율은 의미 정확도가 아니다.

검증:

```bash
CUDA_VISIBLE_DEVICES='' /ref/kev/.venv/bin/python -m unittest discover -s integration/pokechamp/rule_qa_training/tests -v
```
