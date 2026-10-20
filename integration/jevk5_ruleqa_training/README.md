# JevK5 규칙 선택형 LoRA

EX-113 전용 실행기다. 조건과 승인 범위는
[EX113](../../project_context/experiments/EX-113-jevk5-ruleqa-lora.md)에 둔다.
기존 EX107의 DDP/체크포인트 구조를 분리 계승하고 JevK5 공식 prompt를 사용한다.

```bash
scripts/jevk5-ruleqa-train prepare
scripts/jevk5-ruleqa-train preflight
scripts/jevk5-ruleqa-train train
scripts/jevk5-ruleqa-train calibrate
scripts/jevk5-ruleqa-train evaluate
scripts/jevk5-ruleqa-train export
scripts/jevk5-ruleqa-train status
```

출력은 보존루트 `runs/model-training/EX-113`으로 고정한다. status는 저장 JSON만 읽는다.
preflight는3GPU1업데이트를 폐기한다. train은 새 초기화·step0완전저장·기반validation부터 시작한다.
중단 시 `train --resume <동일EX의 checkpoints/step-NNNN>`은 완료표식·모든파일·설정/소스/자료를
검증한 checkpoint만 받는다. 불완전 평가/test는 자동 재실행하지 않는다.
자료를 자르거나 실패행을 제외하지 않으며 환경 패키지도 설치/갱신하지 않는다.

GPU1·2·3 공용잠금/UUID·44GiB 및 소유process합산RSS64GiB를 감시한다. rank별 순차·동기 모델적재로
host staging 중첩을 피한다. 최초시계와 실패receipt를 보존한다. 학습 모듈의 forward를 DDP로 감싸며
24문항 평균을 만들고 마지막위치 유효선택지 logits의 CE만 계산한다. 평가 생성토큰은0이다.

validation만으로 epoch·온도를 선택하고 test각1회 뒤 저장logits로 보정전후 지표를 계산한다.
export는 비병합adapter·24validation 새프로세스재로딩·보고·봉인/종결을 수행한다.
원문prompt의 라이선스/출처는 `integration/jevk5_battle/NOTICE`와 `LICENSE`를 따른다.
