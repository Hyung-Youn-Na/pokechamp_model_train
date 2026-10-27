# EX-113 — JevK5-9B 규칙 선택형 추가 LoRA

- 상태: Completed
- 승인: 2026-10-20 현재 사용자 제공 계획 구현·실행 지시 / D-169 / EP-184
- 연구선·checkout·시작 commit: research/model-training /workspace a4659bf298c7935714f9fbd25246db2d831c5926. 기존 미커밋 변경 보존.

## 동결 protocol

alibiserikbay/JevK5-9B revision d6521a18a86999190e9d775c915af3d6d6772fc4.
기존 showdown-ruleqa/v1 state_mc만 train1536/validation192/test192, 기존 순서·분할·82 test 중복 연결 성분 유지.
state는 원 context.state, context.battle_actions, conditions의 객체. question.type=choice,
criteria는 원 QA ID→답변 문자열. instructions는 `Answer the Gen9 Pokémon rules question using the supplied evidence and explicit conditions. Do not choose a battle action.` 뒤 `\nQuestion: {원 질문}`.
expected는 answer_id one-hot이며 입력 제외. 정답·rationale·oracle·split·관리 metadata 입력 제외.
공식 native 비Thinking prompt·고정 tokenizer·최대6144, 절단/packing/행제외0.

attention projection은 공식 TARGETS만, r16/alpha32/dropout0.05/bias none, 학습 parameter18112512.
기반BF16 고정·LoRA/optimizer FP32·BF16 autocast, SDPA·Torch native Gated DeltaNet.
/ref/kev/.venv 환경 변경0. GPU1·2·3 UUID/공용lock, GPU0 사용0.
microbatch1×accumulation8×3=24, 64step/epoch×3=192step, 모든 문항 매epoch 정확히1회.
AdamW lr3e-5/betas(0.9,0.999)/eps1e-8/weight_decay0, warmup6후cosine, clip1,
seed20261020·epoch shuffle·rank dropout RNG, non-reentrant checkpointing/use_cache=False.
DDP는 선택지 판독 module forward를 감싸며 마지막 입력 위치의 유효 선택지 logits CE만 문항 동일가중 평균한다.

## 선택·평가·보정

기반validation 및 각epoch validation 후 정확도내림차순→T1 NLL오름차순→이른epoch로1~3중선택.
기반은 비교대상. 선택과 보정 확정 뒤 base/selected test 각각1회, 생성0·첫argmax.
각 문항 logits/확률/선택/정답/실패 보존. 각각 validation만으로 T를 로그간격0.1~10의401점+명시1에서
평균NLL 최소, 동률은1과 절대거리 최소로 선택한다. test 추가추론 없이 전후 NLL/Brier/10-bin ECE.
Brier는 다중클래스 제곱오차 합, ECE는 confidence [0,.1),…,[.9,1]의 표본가중 절대차.
주지표 test192 정확도차이, 24규칙 정확도·96묶음 양상황정답률·확률품질 보조.
82성분 paired bootstrap10000회 seed20261020 percentile95%차이구간의 하한>0만 개선근거.
기존 test 재사용·제어장면·동일템플릿 한계, 배틀/미지템플릿/학습방식 우월성 주장0.

## 검증·복구·완료

prepare→preflight→train→calibrate→evaluate→export; status 저장조회만.
CPU 대응/분할/성분/정답유일성/3·4선택지/누출/길이/공식prompt 동치 및 독립 CE/gradient/DDP24평균 검사.
긴 문항과3·4선택지24개의 GPU DDP1업데이트를 폐기하고 seed/초기화 복원.
유한 loss/gradient·기반고정·LoRA변화·장치배치·GPU<44GiB, 소유process합산host RSS≤64GiB.
실측 시간추정·최초시계/누적사용량 보존, 임의 시간상한0·추가학습0·test재생성0.
step0와매16step adapter/optimizer/scheduler/각rank RNG/데이터위치/정체성/완료표식 저장.
동일자료·설정·소스의 완전checkpoint만 재개. OOM/비유한/장치/누출/무결성은 의존단계 중지·증거보존.
RD11.1/C018 도구결함 CPU교정·독립검증·저장응답 재분석 허용, 학습/test 재수집0.
최종 새프로세스에서 규칙별 ID첫validation24개 선택동일·원확률 최대차≤1e-5.
비병합adapter·체크포인트·revision연결·tokenizer/판독/보정·로딩예시·학습곡선·문항별/규칙별결과·한국어보고·봉인/자원반환.
실험완료와 성능개선은 별도판정. 배틀viewer 해당없음.
출력 /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-113.

## 최종 결과

2026-10-20 3epoch/192step을 완료했다. validation정확도 우선으로 epoch3을 선택했다
(epoch1 171/192, epoch2 175/192, epoch3 176/192). 보정T는 기반2.065380156·선택1.412537545다.
잠긴test를 두모델 각192문항1회 평가해111/192(57.81%)→179/192(93.23%), 차이+35.42%p를 얻었다.
82중복연결성분 paired bootstrap10,000회의95%차이구간은+27.37~+43.69%p다.
하한>0이므로 동일템플릿 규칙QA에서 개선근거가 있다. 대조묶음 양상황정답은33/96→84/96이다.
보정 후 test NLL은 기반0.919374·선택0.183475, Brier0.507763·0.100082, ECE0.075160·0.020763이다.
보정전후 전체수치·24규칙 비교와 기존test재사용/제어장면 한계는 최종보고를 따른다.

최초 preflight는 동시적재 hostRSS초과로forward/update0에서 중단했고, 원증거를 보존한
순차·동기적재 교정 후 사전검사를 통과했다. 이후 본학습/평가실패0·test재추론0이다.
실패 포함 GPU단계 경과시간4.679시간, 성공단계 hostRSS최대54.418GiB·관측 물리GPU최대22.484GiB.
13완전checkpoint·선택adapter동일성·CPU복원·24문항재로딩(선택동일/원확률차이0)·봉인·자원반환을 완료했다.
실제GPU학습재개는 수행하지 않았다. 성능개선과 실험수행완료를 각각 판정했으며 배틀전이는 미평가다.

[최종 보고](../../../exec-plans/evidence/ep184/report.md) ·
[종결 검사](../../../exec-plans/evidence/ep184/completion-audit.json) ·
[비병합adapter](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-113/adapter/).
