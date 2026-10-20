# EX-111 — JevK5-9B v6 상세32경기

- 상태: Completed
- 생성일: 2026-10-20
- 승인: 현재 사용자 v6 입력·32경기 실행 지시 / D-166 / EP-181
- 연구선/checkout/시작 commit: research/model-training /workspace a4659bf298c7935714f9fbd25246db2d831c5926

## 질문·모델·처치

공개 JevK5-9B v0.3.3의 선택지 점수 판독을 v6 상세 입력과 연결했을 때 고정32경기의
완주·합법성·승무패·불확실성·지연을 탐색한다. 학습·튜닝·원본 Jev 구조 재현은 아니다.
모델 alibiserikbay/JevK5-9B revision d6521a18a86999190e9d775c915af3d6d6772fc4,
참고 /ref/jevk5 commit f26426d16f59e8bbe1470e5b162cc89329e29b29.
사용자 소유 http://127.0.0.1:18847/v1, served model jevk5-9b, GPU0 단독 BF16/TP1,
vLLM0.31.0+cu129, max_model_len32768, max_num_seqs1, raw_logprobs, prefix caching/mamba align.
서버 PID/startticks·명령·GPU UUID·모델 파일/토크나이저 정체성을 동결하고 외부 서버는 종료하지 않는다.

## 입력·판독

교정 jev-choice-v6 상세 Adapter(compact=False)의 state·원 instructions·criteria ID/순서를 보존한다.
피해·스피드·공개 이력·최근3완료턴·기존 메커니즘 지시문 포함. planner/names-v1/RuleQA 교정0.
JevK5 공식 prompt의 evidence=state, criterion=instructions,
options=A..P 순서의 `원ID: 후보객체 JSON`으로 가역 변환한다. Thinking off·무절단/요약.
Qwen native template/tokenizer와 고정 prompt의 토큰 동치를 사전 검사한다.
최대16후보를1요청으로 읽는다(Gen9 singles v6 최대13후보 범위). 초과는 입력 오류이며 임의 pruning0.
POST /completions, 전체 후보 단일 token ID를 logprob_token_ids로 지정, max_tokens1,
temperature0·raw_logprobs. 반환 원logprob에 softmax(z/1.316)을 적용하고 첫 argmax를 원ID로 매핑한다.
서버 생성 글자는 정책으로 쓰지 않는다. 이 정규화는 사전 정의한 결정 모델 readout이며
외부 공급자의 선택을 사후 수정하는 처리가 아니다. 생성1토큰을 실제 usage에 포함한다.
점수는 후보 선택 분포이며 배틀 승률이 아니다. 포켓몬 영역의 확률 보정 성능은 미검증이다.
단일후보는 무호출 자동선택. 매결정 서버 호출 전후 identity·후보/입력·최신rqid를 검증한다.

## 대진·분모·평가

EX089 collection manifest의 Gen9 OU·Abyssal32슬롯/16진영교환쌍·팀/게임seed/actor seed/제출순서를 채택한다.
양측 테라 허용·timer off·경기/요청 동시성1, 독립 Showdown 포트8108. 원결과 계승0.
주결과는 유효32경기의 승/무/패와 점수(승1/무0.5/패0), 완전쌍 평균 및 쌍 단위
bootstrap10000회(seed42) 탐색95%구간이다. 예정/시도/정상/실패/무효/미실행/완료쌍을 모두 보고한다.
최초 합법률·자동선택·모든 물리HTTP·확인토큰/미확정시도·지연·입력길이·자원을 보고한다.
EX089와 같은 고정 대진의 참고 비교만 제공한다. 훈련자료 오염 여부는 미확인이며
이미 개발에 사용한 대진이므로 일반 배틀 성능·학습효과·모델크기 인과효과를 주장하지 않는다.

## 사전 검증·상한·실패·복구

CPU 후보/JSON 역변환·native prompt·softmax 별도계산·누락/비유한 logprob·원토큰/usage·retry/취소 검사,
독립 모의2경기의 공식cutoff/계산/전송 전수감사 후 저장 선봉/일반/강제교체 각2회(총6요청)를 검증한다.
반복 선택/확률 차이는 진단으로 보존하며 기술 gate는 완전후보/정체성/유한성/무절단/합법성이다.
본32경기는 단1회, 재경기/보충0. 누적 물리요청20000, 최초 사전요청부터12시간,
경기300턴/600결정, 개별HTTP120초. 연결/timeout·408/429/5xx만 동일본문 최대3회 추가,
대기2/5/10초, 그 외 오류는 자동재질의0. 본수집 source/처치 변경0.
GPU0 NVML44GiB·외부서버+소유프로세스 합산host32GiB, 디스크 상한null·사용량 기록.
자원/정체성/입력/통신소진/수집·감사 오류는 의존수집중단이며 사용자 서버를 종료하지 않는다.
합법적인 나쁜 선택은 그대로 진행한다. 후보 점수 누락/비유한 등 판독 불가능한 모델 출력은
해당 경기 output_failure이며 fallback0·독립경기 계속. 응답 model/토큰/usage 불일치는 기술 오류다.
RD11.1/C-018의 사전 도구 복구·저장결과 감사 정정은 원문과 최초시계/사용량 보존 후 독립검증한다.
본경기 재수집 허용0, 공급자 재시도와 도구 복구를 구분한다.

## 출력·완료

actor /workspace/pokechamp/.venv/bin/python, scripts/jevk5-battle.
run /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-111.
viewer /workspace/exports/battle_viewers/ex111/index.html 및 상위목록.
원 v6 입력·실제 prompt/HTTP·원 logprob·보정확률·선택/전송·공개로그·반복검사·manifest/source/
protocol·사용량 원장·경기별/최종감사·한국어 보고·이동후 오프라인뷰어·봉인을 제공한다.
소유 Showdown/Abyssal/controller만 정리하고 사용자 vLLM/GPU0 유지 사실을 명시한다.
정상32/16쌍 및 후처리가 모두 완료돼야 Completed다. 부족하면 미완료 분모와 원인을 보존한다.

## 사전 검증 결과

CPU105·모의2경기175결정/173모의요청·변조거부3·오프라인뷰어4대표 통과.
실제 대표3종 각2회 총6요청, 입력11934/13373/12341토큰·무절단·native토큰동치.
모든 반복 선택/확률 동일. 외부 가중치는 고정revision 공식 LFS SHA256과 일치한다.
첫 capture의 CAS파일명/LFS구별 검사와 모의 첫 포트범위 오류를 보존·교정했고 실제경기0 상태에서 재검증했다.


## 최종 결과

정상32/32·완전16/16진영교환쌍, **2승0무30패(6.25%)**다. 실패·무효·미실행0이며
쌍 bootstrap10,000회(seed42) 탐색95% 점수구간은0~15.625%다.
총1,143결정에서1,110모델호출·33단일후보 자동선택·1,143명령을 기록했다.
재시도·미확정사용량·대체선택0, 모든 입력·원점수/정규화·선택·전송과 종료 산술 감사를 통과했다.
본입력17,094,352·출력1,110토큰; 사전6요청 입력75,296·출력6은 별도다.
입력11,934~17,801토큰·무절단이며142요청이공식runtime16,384제한을 넘었다.
이번vLLM32,768조건과 공식runtime기본값을 구별한다.
HTTP 지연 중앙2.445초/p95 2.654초, 최초사전부터수집최종집계79.21분,
GPU0 최고36.69GiB·외부서버/소유process tree 합산host 최고8.81GiB다.

EX089의6승26패(18.75%) 대비 공통완료16쌍 점수차는-12.50%p,
탐색95%차이구간은-25.000~-3.125%p다. 대진·팀·v6지시문·입력자료는 같지만
모델·tokenizer·전달형식·서빙/readout이 다른 결합 조건의 고정대진 참고 비교다.
외부 일반 성능·학습효과·모델크기만의 인과효과로 확대하지 않는다.

32경기·1,143결정 내보내기 전수 대조와 이동후오프라인5대표(선봉/일반/강제/자동/테라)를 통과했다.
수집후 뷰어 표시명만 보완하고 동결수집소스/처치/원자료/봉인은 유지했다.
run2,705파일·viewer1,279파일 봉인을 검증했다. 소유controller/Showdown/Abyssal·8108·GPU0사용잠금을
반환했고 사용자vLLM18847/GPU0은 유지했다. 추가경기·재학습·추가모델추론0이다.

[완료 보고](../exec-plans/evidence/ep181/report.md) ·
[상세 결과](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-111/evidence/summary.json) ·
[32경기 뷰어](../../exports/battle_viewers/ex111/index.html) ·
[봉인 검증](../exec-plans/evidence/ep181/seal-receipt.json).
