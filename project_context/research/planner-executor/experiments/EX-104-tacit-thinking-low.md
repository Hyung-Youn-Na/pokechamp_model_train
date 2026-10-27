# EX-104 — Tacit-9B Thinking + GLM-5.3 Low 판단 비교

- 상태: Blocked
- 생성일: 2026-10-16
- 승인: 사용자 승인 계획 / [D-157](../decisions/D-157-tacit-thinking-low.md)
- 계획: [EP-163](../plans/EP-163-tacit-thinking-low.md)
- 연구선/branch/checkout: research/model-training /workspace a4659bf298c7935714f9fbd25246db2d831c5926; 기존 미커밋 변경 보존.

## 질문·처치·비교

Tacit thinking 경로가 같은 입력의 첫 판단과 비교하여 어떤 선택/분포 변화와 비용을 보이는가?
EX-103의 팀·대진·seed·공개 관측·피해 계산·후보·전략/수행 지시문·사건 호출 정책을 참조 편입한다.
수행 모델만 morriszjm/Tacit-9B revision 884838f1698d1fd746625b3c20c8ec2be077a183의 thinking
패키지로 교체한다. BF16·Transformers·SDPA/Torch 기본 GDN·GPU0 단독·동시1이다.
vLLM/top20 후보 누락·외부 커널·양자화·자동 backend 대체를 사용하지 않는다.
전용 .pokechamp-data/tacit9b-runtime/.venv와 Torch2.13.0+cu129/Transformers5.17.0/
Accelerate1.15.0 계열을 고정하고 전체 lock을 보존한다. actor는 pokechamp/.venv/bin/python이다.

GLM glm-5.3/thinking enabled/low/temperature0/top_p0.95/max_tokens131072,
events:[faint,tera,forced_switch,active_change,form_change]·최초선봉·단일후보 무호출·보류/중복제거 유지.
원 state·GLM 계획·지시문·후보 객체·ID/순서를 무손실 전달한다. 공식 first-pass와 thinking
프롬프트 각각32768토큰/16후보·절단0. 생성+공식 마감 후 readout 길이는 별도로 native 문맥한도 검사.

## Thinking·집계

매 다후보 요청: 첫 판단 기록 → 항상 thinking 생성 → 전체 후보 라벨 logits의 공식 분포/선택.
adaptive margin/quota는 적용하지 않으며 첫 판단/확률을 thinking 입력에 넣지 않는다.
실제 명령은 최종 선택이다. 공식 프롬프트·decode/reencode·마감·판독 의미를 유지한다.
cot_max_tokens8192·do_sample true·temperature0.6·top_p0.95·top_k20.
전송 model 필드를 포함하고 후보 순서를 보존한 JSON payload(ensure_ascii=False,separators=(",",":"),allow_nan=False)의
SHA256 앞8자리 uint32를 sampling seed로 기록·사용한다. 자연 </think> 종료, 토큰 소진,
EOS 강제 마감을 구분하고 공식 강제닫기/최종판독을 따른다. 추론 완결로 오기하거나 first-pass로 대체하지 않는다.
원 생성 token ID/텍스트·전후 선택/원분포·seed·단계별 지연/토큰·forward 수를 기록한다.
논리 요청은 중복 없이 pipeline1회이며 여러 실제 forward/생성량과 구분한다.
usage.input_tokens는 단계별 입력 처리량 합, output_tokens는 실제 생성량이다. 원입력 길이도 별도 기록한다.

## 평가·분모·해석

기존 사전8회 뒤 EX-103 2·5·6턴 고정 입력3회, 같은 서버 실제1경기다. 고정 입력은 당시 GLM
계획/공개 state를 그대로 사용하고 새 GLM 호출/미래 사실 추가0이다. 결과를 본 뒤 설정 조정0.
전후 선택 변경률/분포·단계별 지연/생성량·강제종료 비율을 고정3사례와 경기 다후보 분모로 분리한다.
이미 설치된 Stealth Rock 재선택/실제 실패, 현재 직접공격 최소피해>Ruination 최대피해인데
Ruination 선택한 빈도를 기회 수와 함께 보고한다. 교체·Tera·생존 등을 당시 공개 사실로 검토한다.
행동 필터/자동 오답/특정 선택 gate는 아니다. 고정3사례와 경기 관련 사례를 집중 검토하고
설명 정확성 전수 평가는 RD8.1 기본 제외다. EX-103과 승패/턴/호출/계획유지/지연/토큰/사례 비교.
전후 비교는 공식 프롬프트 차이를 포함한 thinking 경로 전체의 비교다. first-pass는 실행하지 않은
그림자 판단이며 별도Off 경기로 해석하지 않는다. 학습/튜닝0·독립holdout 주장0·단일경기 일반성능/인과효과 주장0.

## 검증·한도·중단

CPU 공식입력/토큰ID 동치·후보 역매핑·길이·identity·always route·first-pass 비주입·종료/강제마감·
usage/forward·중복방지 및 기존 모델/사건 회귀. EX-103 저장입력과 기존 사전8입력 길이 전수검사.
소스/조건 동결 뒤 최초1서버에서 사전8회 반복 선택 일치 필수, 확률차는 probability_diagnostic.
고정사례 선택/자연 종료 여부는 품질 gate가 아니다. GLM 물리HTTP128·수행모델 논리256(사전11포함)·
경기1·allocator40GiB·GPU전체44GiB·소유host32GiB·경기/전체시간/disk:null. 통신timeout/재시도 EX-103 유지.
포트8109/18845(18846 보존 점검) 점유시 미진입. 실제 I/O 오류/사용량은 기록한다.
RD11.1/C-018 및 RD11.2/C-046 적용. 적재/입력/반복선택/자원/무결성 gate 실패 시 의존 수집 중단·부분증거/사유 보존·정리.
source/조건 동결 후 수집중 변경0. 재경기/재수집/재적재/추가GPU/양자화/대체모델/자동재개0.
독립적인 CPU 도구 교정/보고는 가능하되 최초시계/누적한도 초기화0. 정상1경기 미달은 Completed 아님.

## 출력·완료

run: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-104
증거: project_context/exec-plans/evidence/ep163
viewer: exports/battle_viewers/ex104/index.html
condition: glm53-tacit-thinking-matchup-events-low

모든 호출/미호출·GLM low 실제요청/재시도·Tacit 단계/원응답/usage·최종선택→명령·자원 감사.
정상1경기·필수감사/비교·전후판단/원추론/종료상태 뷰어·이동후오프라인/복사/다운로드·기존봉인보존·
새산출물봉인·GPU/PID/잠금/포트반환·상태/색인 갱신이 완료 기준이다.

## 부분 결과

정상0/1·18턴 도중 프로세스 종료·승패 미확정. 완결20선택/미완결1요청, 전후 변경5/20. 부분 감사·비교·뷰어·봉인·반환 완료; 원인 미확정과 감시 공백을 [보고](../../../exec-plans/evidence/ep163/report.md)에 명시했다. Blocked 유지·자동재개0.
