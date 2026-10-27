# EX-116 — JevK5 전체 System One 학습

- 상태: Completed
- 생성일: 2026-10-21
- 승인: 현재 사용자 제공 전체 학습 계획 구현·검증·실행 지시 / D-180 / EP-203
- 기준·실제 연구선: research/model-training; checkout /workspace; 시작 commit feda62f733c1b470364868262c789ec857ef67f5. 기존 미커밋 변경 보존.
- 환경: /ref/kev/.venv; 새 integration/jevk5_system1_training 및 scripts/jevk5-system1-train.
- 출력: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-116

## 질문·처치

원본 alibiserikbay/JevK5-9B revision d6521a18a86999190e9d775c915af3d6d6772fc4에 새 LoRA를 붙인 전체 자료 3epoch 학습이 새 규칙 조합의 선택 정확도를 개선하는가?
기존 EX113 adapter를 이어받지 않는다. 원본과 선택 adapter를 비교하며 학습 완료와 개선 근거를 별도 판정한다. 배틀·서버 교체·외부 게시·추가 다운로드는 범위 밖이다.

## 데이터·입력

EP193 타입 기본+확장64980(10%), EP195 상태22423(10%), EP196 우선도10160(10%), EP197 날씨/필드12178(10%), EP198 관측KO3981(5%), EP199 조건부KO8582(10%), EP200 역할3717(5%), EP201 규칙4128(40%)를 사용한다.
규칙 세부 비중은 priority1~5 각각12/10/8/6/4%. 합계130149문항, 각epoch 정확히1회, 총390447노출. CSV/NPZ/부분파일/기존5760 SFT를 중복 합산하지 않는다.
문항별 그룹크기 역제곱근을 분야 내 정규화하여 분야 총비중을 맞춘다. 그룹은 타입 semantic_group, 상태/우선도/날씨·규칙 rule_id, 리플레이 replay_group, 조건부 profile_group, 역할 queried_role_id×정답 의미 클래스이다. 후보 위치가 역할 클래스를 바꾸지 않는다.
input.state/question만 공식 비Thinking template와 고정 tokenizer로 입력한다. 기존 토큰과 전수 대조, 후보순서/유일정답/metadata 변조 입력불변 확인, 최대6144 무절단·packing0. 원관측KO와 역할 근거미확인의 의미는 원자료 계약대로 보존한다.

## 학습·실행

BF16 기반 고정, FP32 LoRA/optimizer. EX113 attention projection 목록 r16/alpha32/dropout0.05, 18112512 trainable. AdamW lr3e-5, betas(.9,.999), eps1e-8, weight_decay0, warmup123 이후 cosine, clip1. seed20261021.
3epoch×1356update=4068; 전역96, 마지막69; 물리GPU1·2·3 세rank에 균등분배. rank 내부 길이순 microbatch≤8 및 padding포함4096토큰; 더 긴 문항은 단독. 오른쪽padding/mask, 문항별 마지막 실제 입력의2~11 유효후보 CE. DDP 전역 가중 분자/분모, rank별 누적 횟수 차이 허용.
메모리맵 token/offset, SDPA·Torch native Gated DeltaNet, 순차·동기 모델적재. UUID·공용잠금·유휴검사; 외부프로세스 종료0. GPU각44GiB미만/소유hostRSS합산64GiB이하.
사전검사 microbatch8→4→2→1 최초 자원/수치동등성 통과값을 동결한다. 배치/단독 확률 최대차≤0.002·argmax동일, dropout 비활성 gradient 상대L2≤0.02, checkpoint 복원 후 동일update LoRA 최대차≤1e-7을 사용한다. 최종 재로딩은 원평가와 같은 배치 형상을 재현한다. 실패 사전시도와 자원사용 보존. 본학습 중 자동조건변경0.
step0/매128/epoch종료 완전checkpoint(adapter/optimizer/scheduler/각rank RNG/데이터위치/설정/자료·소스 정체성). 동일조건의 완전checkpoint만 재개. 사전업데이트는 폐기하고 원초기화로 시작한다.

## 독립 평가·선택

학습 전에 별도 평가 자료·정답·기준과 분할을 동결한다. 학습자료 재분할로 독립평가를 만들지 않는다.
7영역(타입·Tera×특성, 상태×면역·치료, 우선도×실행조건, 날씨·필드×진입·잔여, KO방지×다단·후속, 정보충분성, 조건부KO경계)에 각 validation64/test128 대조묶음×2문항:896/1792.
고정 Showdown e64915c0eab066db1d3e732b1280386468dd7415와 독립 예상규칙 대조. 이름/문장/선택순서만 바꾼 복제 불허. 정규화 상태·효과·질문사건/원천프로필과 분할 중복 검사, 동일장면 변형은 같은 묶음.
로컬 원자료 새384경기(validation128/test256), 경기당KO/비KO 각1:256/512문항. 경기ID/로그/양팀서명 및 파생조건부KO 원천 연결까지 학습·분할간 분리. 합계validation1152/test2304. 균형표집 성능이며 자연KO확률로 확대하지 않는다.
타입 의미그룹 대표와 역할3717 재현·후보순서변화는 진단 전용이며 독립지표/선택에 사용하지 않는다.
기반 및 epoch1~3 validation 후 7영역 macro정확도 내림→macroNLL 오름→이른epoch로 선택. 선택 확정 후 원본/선택 test각1회. T=1, 첫argmax. 정확도/NLL/Brier(후보별제곱오차합)/10-bin ECE([0,.1),…,[.9,1])·영역별 결과와 문항별 예측 보존.
주지표7영역 macro정확도차이. 영역별 대조묶음을 복원추출하는 stratified paired bootstrap10000, seed20261021, percentile95% CI 하한>0만 해당평가 개선근거. 리플레이 별도 보조지표, 배틀승률 주장0.

## 검증·중단·완료

전수자료대응/양수가중치/epoch1회/후보·토큰·누출. CPU 가변후보·padding·재매핑·가중CE/gradient/DDP전역평균·마지막69. GPU최장/후보경계 유한loss/gradient·기반불변·LoRA변화·단독/배치동등·저장/재개 검증.
NaN/OOM/누출/장치/무결성 오류는 해당단계와 의존단계를 중지하고 증거보존. 본학습 조건·test 재생성 자동변경0. RD11.1/C018 CPU도구교정/저장응답 재분석 허용; 실패 학습/test 재수집0, 동일조건 완전checkpoint 재개만 허용. GPU사전검사의 명시microbatch 순차탐색은 예외이며 학습처치 변경이 아니다. 실험 최초시계/누적비용 보존, 별도시간상한 없음. 공급자 배틀판단 오류/C047 viewer 해당없음.
처리량 기반 시간추정은 사전검사 실측 후 보고한다. 선택/최종epoch adapter, 완전checkpoint, revision/tokenizer/판독코드, 곡선·문항예측·영역비교·한국어보고, 새프로세스 재로딩(선택동일·확률최대차1e-5 이하)과 봉인/자원반환이 완료기준이다.

## 본학습 전 v1 검사와 v2 교정

본학습·모델 validation/test 호출은 아직0인 상태에서 다음 결함과 교정을 기록했다. v1 prepared/source/protocol/평가자료는 `EX-116/preparation-v1`에, 원시도 로그·체크포인트·실패/자원 receipt는 원위치에 보존한다. 최초 시계와 누적 사용량은 유지한다.

- v1 microbatch8/4/2는 단독판독 확률차이 기준을 통과하지 못했다. 1의 단독판독/gradient·기반고정·LoRA변화는 통과했으나, 같은 checkpoint에서 이어지는 업데이트의 최대차7.8647e-7이1e-7 기준을 넘었다.
- 별도3rank 대조에서 시작 parameters·optimizer 전tensor·scheduler·CPU/CUDA RNG가 모두 정확히 같고 loss도 같지만, 디스크를 쓰지 않은 메모리복원에서도8.3208e-7의 차이가 났다. 직렬화 문제를 원인으로 단정하지 않는다.
- 결정적 GPU 연산 대조에서는 gradient norm이 같고 최대차9.3133e-10으로 같은 기준을 통과했다. v2부터 `torch.use_deterministic_algorithms(True)`, `cudnn.deterministic=True`, `cudnn.benchmark=False`, `CUBLAS_WORKSPACE_CONFIG=:4096:8`을 학습/평가/재로딩에 동일 적용한다. Torch native Gated DeltaNet·SDPA·기존 패키지·모델·자료·학습률/학습량은 유지한다. 허용치를 완화하지 않고 새 source/config로8→4→2→1을 재검사한다.
- 별도로 HP 평가768문항의 보기 패턴에서 정답 추측 가능성을 발견해 보기만 교정했다. 전체2688문항의 상태/질문/묶음/분할/정답 의미/엔진근거는 같고 새test 표본 추출0이다. 원본·학습 모델의 평가 전에 함께 적용한다. [의미 검토](../../../exec-plans/evidence/ep203/evaluation-review.md) 참조.

위 단계는 RD11.1/C018의 사전 도구 교정·독립 대조이며 폐기하는 사전 업데이트다. main train/test 재수집은0이고 v1 임시어댑터를 본학습 초기값으로 사용하지 않는다.

## 본실행 진입

v2 사전검사 통과 후 microbatch1·전역96으로 고정했다. 원본새LoRA의 step0을 저장하고 baseline validation→3epoch 본학습에 진입한다. 사전adapter 계승0. 학습/최종평가/내보내기 완료는 아직 아니다.


## 실행 결과

3epoch/4068update/390447노출 및 원본·선택 test각2304문항1회를 완료했다. 선택 epoch 2. 7영역 macro정확도 차이는 +6.808%p, 95%구간은 [4.353, 9.263]%p이다. 해당 평가에서 개선 근거가 있다. 실제배틀·서버교체는 수행하지 않았다.

[최종 보고](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-116/report.md) · [완료 검사](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-116/completion.json) · [선택 adapter](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-116/adapter-selected/) · [마지막 adapter](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-116/adapter-last/).
