# EX-123 — System One JevK5 선택 어댑터 실전32

- 상태: Completed
- 생성일: 2026-10-23
- 승인: 현재 사용자 “GPU 1,2,3번을 이용해32경기 테스트” / D-186 / EP-211
- 기준·실제 branch/checkout: research/model-training /workspace feda62f733c1b470364868262c789ec857ef67f5. 기존 미커밋 변경 보존.

## 질문·모델·입력

EX116의 선택 epoch2/step2712 새 LoRA를 Gen9OU Abyssal32경기에서 평가한다. 기반 alibiserikbay/JevK5-9B revision d6521a18a86999190e9d775c915af3d6d6772fc4, adapter는 EX116/adapter-selected이며 완료/선택/봉인에 대조한다. 마지막epoch3이나EX113 adapter를 사용하지 않는다.
기존 EX114와 같은 상세 jev-choice-v6(compact=False)·공개이력·피해/속도·원지시문·원후보순서를 유지한다. Planner/요약overlay/QA행동금지문구/입력절단/후보제거0. 공식 native 비Thinking template와 후보단일토큰logprob을 사용하며 max_tokens1/temperature0·원후보 첫argmax, 표시확률 T=1이다.
물리GPU1/2/3 각각 독립 TP1 vLLM0.31.0+cu129 replica를 사용한다. 기반/LoRA BF16, max_model_len32768, max_num_seqs1, eager, prefix cache off, gpu_memory_utilization0.80, raw_logprobs/max_logprobs256이다. 기존 vLLM CLI는 LoRA FP32를 지원하지 않아 FP32 저장adapter를 서빙시BF16로 적재하며 원본은 수정하지 않는다. 학습시 Transformers/FP32 LoRA와의 수치동일성은 주장하지 않는다.

## 대진·분할·자원

EX089/111/114와 같은32슬롯·16진영교환쌍, 팀/게임seed/actor seed/제출순서를 유지한다. 16쌍을순서대로GPU1/2/3에round-robin배정(6/5/5쌍=12/10/10경기). 각shard내순차·전체최대3경기동시. 한쌍은한GPU에유지하며 추가원본32경기/재경기0.
GPU당44GiB미만, 전체소유hostRSS64GiB이하 및 shard당32GiB이하. UUID/공용잠금/유휴검사 후 서버를 순차적재하고 첫서버준비후다음서버를 시작한다. GPU0 및다른EP210의8107사용0. 신규Showdown8104/8105/8106, 모델HTTP18851/18852/18853. 외부프로세스종료·장치reset·기존서버교체0.
12시간은 최초사전모델요청부터 전체동일시계로 적용한다. 모델물리요청상한 shard1=7500/shard2=6250/shard3=6250(사전요청포함 총20000), 경기300턴/600결정. HTTP120초, 연결/timeout·408/429/5xx만같은본문최대3추가(2/5/10초). 서버기동대기600초. 디스크상한없음, 사용량기록.

## 검증·중단·복구

EX114 실행기/감사/UI를새패키지로분리계승한다. CPU판독/격리/분할합집합·중복0·쌍보존·집계검사를실행한다. 각shard의모의2경기(합계6, 실제모델0)와UIv1오프라인/이동/리플레이검사를사전수행한다.
실제서버마다선봉/일반/강제교체각2회=6요청, 전체18요청. 무절단native/tokenizer/원후보가역성·모든후보유한성·모델/adapter정체성 확인. 세replica의같은입력선택/확률차이는진단이며 성적이나사후통과기준으로사용하지않는다. GPU사전검사를통과한동일서버로본경기를실행한다.
합법적인나쁜선택은그대로진행한다. 판독불가모델출력은해당경기실패·대체0, 나머지독립경기는계속한다(RD11.2/C046). 입력/정체성/무결성/감사·공유source오류는전체의존수집중지; 단일서버장치/통신소진은해당shard를중지하고독립shard는완료/증거보존한다. 전체host상한은전체중지한다. 실패분모를삭제하거나패배로치환하지않는다.
RD11.1/C018 사전도구교정·독립검증·저장원문재분석허용. 본경기재수집/재경기/보충0. 원본/교정본과최초시계·누적한도유지. 수집중source/처치변경0. 종료시자신의서버/actor/Showdown과잠금만반환한다.

## 지표·해석·완료

예정/시도/정상/실패/무효/미실행, 완전쌍, 승무패와점수1/.5/0. 완전쌍평균·paired bootstrap10000(seed42)95%구간. 합법성·자동선택·입력길이·요청/토큰·지연/자원을보고한다. EX111원본2승30패, EX114기존QA LoRA4승28패와공통고정대진의참고쌍비교를한다. 과거runtime/GPU/동시성/어댑터정밀도및학습조건이달라이번학습만의인과효과로주장하지않는다. 개발에쓴고정대진/훈련오염미확인·학습6144보다긴배틀입력의전이한계를유지한다. 설명평가·추가학습·QA test재추론0.
새구현 integration/jevk5_system1_battle 및 scripts/jevk5-system1-battle, actor pokechamp/.venv, 모델 jev35b-nvfp4-runtime/.venv, 브라우저 /tmp/ep037/tools.
출력 /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-123/shards/gpu{1,2,3}. 각shard원자료는독립봉인하고전역집계는slot_id/pair_id로연결한다. 원시event seq를합치거나고쳐쓰지않는다.
viewer exports/battle_viewers/ex123/index.html은전역32경기목록, gpu1/2/3하위는각shard UIv1이다. 생성기 jevk5-system1-researcher-v1, 기본5탭 뒤 실제프롬프트→선택지확률→선택·전송. 사전/사후UI오프라인·원문대조·반응형·리플레이pause/seek검증과상위목록/변경일지등록을한다(C047).
정상32/완전16쌍·경기별/최종감사·한국어보고·전체뷰어·봉인·소유자원반환까지완료해야Completed다. 미달은미완료로보고하며부족한경기를추가하지않는다.

## 실행 결과

정상 32/32, 5승0무27패, 완전16/16쌍. 실패0·무효0·미실행0. [최종 보고](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-123/evidence/report.md) · [뷰어](/workspace/exports/battle_viewers/ex123/index.html). 과거 비교와 전이 한계는 보고서를 따른다.
