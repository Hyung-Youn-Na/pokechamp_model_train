# EP-190 — JevK5 추가 LoRA vLLM 서빙 확인

- 상태: Completed
- 생성일: 2026-10-21
- 승인: 사용자 “서빙완료했는데 작동을을 확인해주세요.”
- 기준 연구선/checkout: research/model-training /workspace; 기존 변경 보존.
- 관련: EX113/EP184의 완료 산출물, C083; 기존 실험 재개와 test 재평가가 아닌 기술 확인.
- 환경: 표준 Python HTTP 클라이언트, 사용자 소유 vLLM0.31.0+cu129 /127.0.0.1:18848/GPU1.
- 출력: project_context/exec-plans/evidence/ep190. EX113 봉인 산출물은 읽기만 한다.

## 범위와 기준

INDEX/CHARTER/매뉴얼/STATUS/catalog와 rule-learning 계약을 확인했다. 겹치는 실행중 plan은 없다.
health와 models, 실제 서버 명령/모델/revision/어댑터/GPU 정체성을 확인한다.
EX113 validation에서 규칙별 ID순 첫 문항24개를 선택해 학습어댑터를1회씩 판독한다.
첫2규칙의 같은 문항을 기반모델로도1회씩 판독하여 실제 LoRA 효과를 대조한다.
총completion요청26회 이내, 각max_tokens1/timeout120초/재시도0. 생성글자는 판단에 사용하지 않는다.
기존 input_ids와 label_ids를 그대로 전달하고 모든 선택지 raw logprob·token echo·usage·유한확률을 검사한다.
T1 및 기존 선택모델 T1.4125375446227548 보정값을 클라이언트에서 적용한다.
동일24문항의 저장 Transformers 선택·원확률과 차이를 보고한다. 다른backend/LoRA BF16 적재이므로
과거동일runtime 재로딩의1e-5 기준을 새판정에 소급하지 않고 실제 차이와 한계를 명시한다.
운영통과는26응답의 기술적유효성 및 등록된adapter의 실제점수변화를 확인한 경우다.
정확도/선택일치/확률차이는 소표본진단이며 새효능평가 또는 전체test재현으로 주장하지 않는다.
서버 재시작/종료·패키지수정·가중치병합·추가학습·test추론·배틀0. 사용자 서버와 잠금을 유지한다.

## 완료 기준

- [x] 서버·모델·어댑터 정체성 및 실제 판독 확인
- [x] 24문항 비교·기반대조·한계·증거 보고, 사용자서버 유지

## 중단·복구

HTTP/누락logprob/비유한수치/정체성 오류는 의존호출을 중지하고 원요청·응답·실패를 보존한다.
클라이언트 CPU 교정은 가능하나 자동 재호출은 없다. 데이터/모델오답은 기술오류로 재시도하지 않는다.
비배틀 기술 확인으로 viewer·실험 시계/효능 bootstrap은 해당없다.

## 결과 및 증거

26실제 요청을 정상 처리했고 등록된 어댑터의 실제점수변화를 확인했다.
24validation의 선택은 기존 Transformers와24/24일치(정답23/24)했으며, 원확률 최대차는0.046300375다.
다른runtime 수치동일성이나 전체test재현으로 주장하지 않는다. 사용자서버는 그대로 유지했다.
[확인 보고](../../../exec-plans/evidence/ep190/report.md) · [요약](../../../exec-plans/evidence/ep190/summary.json).
