# EX-114 — 학습 JevK5 선택형 LoRA 실전32

- 상태: Completed
- 생성일: 2026-10-21
- 승인: 사용자 “해당 서빙 모델을 활용해서32경기 테스트를 진행해주세요.” / D173 / EP191
- 연구선/checkout: research/model-training /workspace; 기존 변경·EX111/113 봉인 보존.

## 질문·모델·입력

EX113의 규칙QA LoRA가 실제6대6 행동선택에서 보이는 완주·합법성·승무패를 탐색한다.
기반 alibiserikbay/JevK5-9B revision d6521a18a86999190e9d775c915af3d6d6772fc4,
선택epoch3/step192의 비병합adapter와 tokenizer를 EX113 봉인에 대조한다.
사용자GPU1/18848 서버는6144토큰으로, 기존대표배틀11934/13373/12341토큰을 수용할 수 없다.
원입력을 유지하려고 유휴GPU2에 같은모델·adapter의 임시vLLM0.31.0+cu129 서버를18849로 구동한다.
GPU UUID/공용잠금, BF16기반/LoRA·TP1·max_model_len32768·max_num_seqs1·eager·prefix cache off,
임시서버 기동대기 최대600초. GPU memory utilization0.80·raw_logprobs·max_logprobs256·generation_config vllm.
기존 사용자서버/잠금은 유지하고 이 실험 소유의 임시서버만 종료한다.

EX111과 같은 jev-choice-v6 상세(compact=False), 피해/속도·공개이력·최근3완료턴·원지시문·원후보순서를 사용한다.
planner/후보요약overlay/QA행동선택금지문구/입력절단·요약·후보제거0. 공식JevK5 비Thinking
state/instructions/criteria→evidence/criterion/lettered options를 가역변환한다.
매결정 후보별 단일토큰logprob을 요청하고 max_tokens1/temperature0·첫argmax를 원후보ID로 연결한다.
표시확률은 EX113의 T1.4125375446227548을 고정 적용한다. 이는 QA보정값의 단순이용이며
배틀확률 보정성능이나 승률을 뜻하지 않는다. 양의T는argmax를 바꾸지 않는다.
생성글자는 정책이 아니며1출력토큰usage를 기록한다. 단일후보는 무호출 자동선택.

## 대진·평가·해석

EX111/EX089와 같은 Gen9OU Abyssal32슬롯·16진영교환쌍의 팀/게임seed/actor seed/제출순서.
양측테라 허용·timer off·동시성1, 독립Showdown8109. 새32경기1회, 과거결과 계승0·추가baseline32경기0.
예정/시도/정상/실패/무효/미실행/완료쌍을 구분한다. 주결과 승무패·점수(1/.5/0),
완전쌍 평균 및 쌍 bootstrap10000(seed42)의 탐색95%구간. 합법성·자동선택·입력길이·HTTP/토큰·지연·자원 보고.
EX111 기반JevK5의2승30패 및 EX089의6승26패와 저장된 공통대진의 참고비교를 제공한다.
과거runtime/cache/eager/GPU·LoRA정밀도 등이 다르므로 추가LoRA만의 인과효과로 단정하지 않는다.
이미개발에사용한 고정대진·훈련자료오염미확인·QA최대6144를넘는길이의 전이 한계를 명시한다.

## 사전검사·상한·복구

기존 EX111의 변환/정책/합법/감사구조를 분리계승하고 변경경계의 CPU검사를 수행한다.
모의2경기 전수감사와 UIv1 이동후오프라인 검증을 실제수집보다 먼저 통과시킨다.
같은본서버로 선봉/일반/강제교체 대표각2회 총6요청; native template/tokenizer 동치·가역성·모든후보·유한성·정체성 gate.
반복/확률변동은 진단이며 수치동일성 기준을 사후추가하지 않는다.
물리요청20000/최초사전요청부터12시간, 경기300턴/600결정, HTTP120초.
연결/timeout·408/429/5xx만 같은본문 최대3추가재시도(2/5/10초), 그외자동재질의0.
본경기 재경기/보충0. 합법적인 나쁜선택은 진행, 판독불가모델출력은 해당경기 output_failure·대체0·독립경기계속.
입력/정체성/수집감사/자원/통신소진 오류는 의존수집을 중지한다. GPU2<44GiB, 소유process합산host32GiB,
디스크상한null·사용량기록. RD11.1/C018 사전도구교정·저장원문 재분석 허용, 원증거/최초시계/누적사용량 보존.
학습·튜닝·병합·testQA재추론·외부모델API0.

## 출력·뷰어·완료

실행기 integration/jevk5_ruleqa_battle 및 scripts/jevk5-ruleqa-battle, actor pokechamp/.venv/bin/python.
출력 /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-114.
viewer /workspace/exports/battle_viewers/ex114/index.html 및 상위목록.
UI는 battle-viewer-ui-v1, 생성기 jevk5-ruleqa-researcher-v1. 기본5탭 뒤 실제프롬프트→선택지확률→선택·전송.
EP188/189 UI/리플레이브리지와 EX111 원문export를 분리결합하며 기존렌더러/출력은 변경하지 않는다.
선행지원구현은 EP191의 CPU/모의단계이며 소스판본/hash를 수집전 동결한다.
결정/턴 이동·pause/seek·선택독립·최신선택·실제이름·HP·자동/실패/무자료·원문복사/다운로드·모바일·오프라인을 검증한다.
변경일지에 새판본과검증근거를 연결한다. 기존출력·봉인 재생성0.
정상32/16쌍, 경기별/최종감사·보고·뷰어·봉인·소유서버/포트/GPU잠금 반환까지 완료해야 Completed.
부족하면 미완료분모/원인/증거를 보존한다. 사용자GPU1서버는 계속유지한다.

## 결과

2026-10-21 예정/시도/정상32, 실패/무효/미실행0, 완전16쌍. 4승0무28패(12.5%).
쌍 bootstrap 탐색95%구간0~28.125%. EX111 대비 점수차+6.25%p의 구간은 −9.375~25%p로 0을 포함한다.
기반모델 대비 승수가 늘었으나 개선을 확정할 수 없으며 LoRA만의 인과효과를 뜻하지 않는다.
본수집1,040요청/자동32/전송1,072, 재시도0, 입력11,934~17,936토큰(전부학습최대6144초과).
전수감사·UIv1·봉인·소유자원반환을 완료했다.
[최종 보고](../../../exec-plans/evidence/ep191/report.md) · [뷰어](../../../../exports/battle_viewers/ex114/index.html).
