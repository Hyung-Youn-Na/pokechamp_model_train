# 후보 행동가치 추정 — 실행 계약

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="c-048--ex-060-독립-분기-실행-경계"></a>
## C-048 — EX-060 독립 분기 실행 경계

[D-097](decisions/D-097-single-battle-branch-rollouts.md)과 [EX-060](experiments/EX-060-single-battle-branch-rollouts.md)의 신규 실행기는 원관측·후보·원명령 재현 gate를 거친 독립 snapshot만 사용한다. 정상 턴 제출 전 barrier와 턴중간 pending queue를 구별하고 양측 private stream·정책 mutable state·난수·후보 실행을 격리한다. simulator snapshot/상대세트/미래 seed는 학습 입력에서 제외한다. 과거 자료·canonical submodule·운영 기본값을 덮어쓰지 않으며 원재현 실패를 새 경기로 대체하지 않는다. 구현 API/산출물은 별도 README에 둔다.


<a id="c-048-action-value-training"></a>

<a id="c-048--포켓몬-후보별-soft-target-학습-경계"></a>
## C-048 — 포켓몬 후보별 soft target 학습 경계

D-098/EX-061의 `pokemon-action-value-v1`은 후보별 레코드다. `input_ref`로 원관측/합법 후보를
읽고 모델에는 관측 전문·후보·평가 행동·이진 질문만 펼친다. `target_probabilities`, counts,
provenance, 원선택 ID, values, snapshot, 미래 seed/trace/상대 첫 선택은 토큰 입력에서 제외한다.
원관측의 공개 정보와 추천 세트 계산 가정의 원표현을 유지한다. max_len 초과는 오류이며 절단하지 않는다.
각 후보 두 결과만 합이1이다. q_values는 후보별 독립 값이며 choice는 최대값·동률 원순서의 합법 ID,
command는 해당 원후보 명령이다. 학습 loader는 기존 정수 answer 경로와 분리한다.
원자료 봉인·기존 EX-060 export는 읽기 전용으로 보존한다.

<a id="c-049-qwen-local"></a>

<a id="c-049--qwen-로컬-행동가치-서빙"></a>
## C-049 — Qwen 로컬 행동가치 서빙

D-099의 새 `qwen-local-value-v1` 프로필은 EVE InputExample/render/ValuePolicy를 재사용한다.
GET /health는 ready/model/revision/adapter hash/max_len을, POST /evaluate는 원관측·순서 있는
합법 행동을 받아 후보별 q_values·최댓값 choice·command·token/prompt hash·처리 시간을 반환한다.
q는 독립 값이며 합계 검사는 없다. 동률은 원순서, 단일 후보도 forward한다.
FP32 base/adapter·BF16 forward·FP32 readout, eval/no_grad·업데이트0·직렬 GPU 처리다.
금지 필드·후보 매핑·유한 q·응답 coverage를 검사하고 길이 초과는 무절단 오류다.
전송 직전 rqid·합법 목록을 재확인하며 timeout/불완전/stale 응답은 전송하지 않는다.
소유 프로세스만 시작/종료한다. 조건·허용 자원·실패 격리 범위는 각 EX가 소유한다.
EX-062의 고정2경기와 D-100/EX-063의 학습 원대진1경기는 별도 schedule·probe·원장으로 연결한다.
원대진에서는 원세트/순서와 공개 preview 성별만 재구성하며 provenance/seed는 모델 입력 밖에 둔다.

<a id="c-050-qwen-candidate-state"></a>

<a id="c-050--qwen-후보-상태-입력과-개발-진단"></a>
## C-050 — Qwen 후보 상태 입력과 개발 진단

D-102의 `qwen-candidate-state-v1`은 명시 설정으로만 허용하는 새 입력 버전이다.
기존 JEV v4와 C-049의 요청/응답·독립 A/B q·동률·합법 명령·길이·최신 rqid 경계를 유지한다.
같은 후보 ID/명령/순서에서 직접 이름·사용자/교체 대상·테라, 계산 시점/대상/적용 조건,
지원되는 후보 후 상태·반격·교체 진입 및 일관된 가정 식별자를 제공한다.
미지원/조건부/확인된 부재를 구분하고 부분 계산을 전체 보장으로 표시하지 않는다.
관측 actor cutoff와 자기 제출 팀만 사용하며 숨은 실제 상대 세트/queue·미래를 추가하지 않는다.
공통 규칙을 한 번 유지하고 lead/turn_action/forced_switch 절차를 앞에 결합한다.

개발용 POST /diagnose는 별도 명시 설정에서만 제공한다. 동일 base+LoRA의 별도 prompt와
비사고 greedy 생성으로 검증 가능한 중간 상태 JSON을 출력하며 q·choice·command·전송을
제공하지 않는다. true/false 외 conditional/unknown을 허용하고 원출력/스키마 실패를 보존한다.
진단 결과는 q 입력에 재주입하지 않으며 GPU lock을 공유하지만 요청별 cache/config만 쓴다.
가중치/eval/설정 불변·진단 전후 q 대조를 검증한다. 토큰과 지연은 q/진단을 분리하여 기록한다.
구체적 호출 수·기한·복구·완료·해석은 EX-064가 소유한다. 기존 동결 버전은 변경하지 않는다.

<a id="c-051-joint-q"></a>

<a id="c-051--ex-065-공동-q-데이터"></a>
## C-051 — EX-065 공동 q 데이터

D-103의 pokemon-joint-q-input-v1은 공식 actor 관측·공개 cutoff·자기 제출 팀만 받아
공통 상태/규칙/계산 가정/결정 지침과 이름 있는 actions[]를 관측당 한 번 렌더링한다.
저장 학습 레코드와 모델 입력 타입을 분리하며 타깃·원선택·seed·private snapshot/상대 세트는
renderer에 허용하지 않는다. 후보 결과 배열/참조를 펼치고 unknown/단위/대상/조건을 유지한다.
타깃은 실제 숨은 상태·고정 후속 정책 조건의 독립 q, 후보 간 정규화0이다.
원재현/모든 snapshot의 복원·다음 경계 일치 후 분기하며 논리 rollout과 시도 ID를 구별한다.
트랜잭션·원자 저장·원본 불변·RNG checkpoint 재개를 요구한다. 후보별32완료가 하나라도
빠지면 관측 전체 미완료다. 로더는 ID 정렬·관측 단위 배치·마스크 손실/argmax를 사용한다.
세부 수집·자원·gate·복구는 EX-065가 소유하며 C-048/049/050의 과거 버전은 유지한다.

<a id="c-052-joint-q-training"></a>

<a id="c-052--base-공동-q-모델학습-경계"></a>
## C-052 — Base 공동 q 모델·학습 경계

D-104의 새 공동 readout은 C-051 JointInput만 받아 관측당 backbone forward 한 번으로
원순서 모든 후보의 독립 sigmoid q를 반환한다. 각 ACTION_ID의 Q_VALUE= 위치를 명시적으로
ID에 연결하며 저장 레코드·타깃·seed·private는 입력 밖이다. 새 renderer 버전과 Base tokenizer를
사용하고 토큰 추가0·무절단32768 한도·범위 초과 실패를 적용한다.
microbatch1의 전체 유효 prefix는 보존하고 마스크된 오른쪽 token-padding만 backbone 전에
제거하여 padding에 따른 readout 변화가 없도록 한다. 원 입력 토큰 절단은 허용하지 않는다.
text backbone LoRA와 별도 공유 value head만 학습하고 frozen base를 보존한다.
입력/타깃/위치의 ID 정합성·관측 평균 마스크 손실·원순서 동률·동일 학습/평가 경로를 검증한다.
checkpoint는 adapter/head/optimizer/RNG/cursor와 base/tokenizer/renderer/data/source 해시를
보존한다. test 진입은 선택 모델 재로딩 대조와 설정 잠금 뒤 모델별1회다.
정밀도·학습량·선택·평가·자원·복구의 실행 원문은 EX-066이며 기존 경로는 유지한다.

<a id="c-053-abyssal-tera"></a>

<a id="c-053--abyssal-tera-정책보완-수집"></a>
## C-053 — Abyssal Tera 정책·보완 수집

D-107/EX-067의 `abyssal-tera-v1`은 자기 요청·상대 공개 관측만 읽는 별도 정책이다.
기존 Abyssal을 결정마다 한 번 호출하고 추가 RNG 소비 없이 고정 규칙으로 주문을 바꾼다.
정책 ID·설정 해시는 생성/재현/snapshot/checkpoint에 보존하며 과거 필드 없는 snapshot은
기존 Abyssal로 복원한다. 첫 평가 후보 전 자기 후속 정책 호출은 금지한다.
정책 사유·실제 상대 세트·미래 RNG는 감사/private에만 저장하고 C-051 JointInput/로더를 유지한다.
공통 instructions에는 새 후속 정책의 q라는 전역 설명만 추가하며 개별 판단 사유는 포함하지 않는다.
EX-067의 `public-tera-v2` 입력은 공개 prefix에서 팀별 소모 여부를
`state.terastallization_used.{self,opponent}`로 기록한다. 기절 후 공식 관측기가 해제하는
현재 개체의 Tera 표시와 역사적 팀 소모를 구분하며, JointInput class와 공개 로더는 유지한다.
Tera 상성/피해는 정책 내부 독립 투영으로 계산하고 미지원 근사는 발동 근거로 쓰지 않는다.
수집/자원/검증/복구·봉인/복사·뷰어 규범은 EX-067이다. EX-066 봉인 소스/환경/입력은 보존한다.

<a id="c-062-joint-q-battle"></a>

<a id="c-062--ex066-공동-q-체크포인트-실제-배틀-경계"></a>
## C-062 — EX066 공동 q 체크포인트 실제 배틀 경계

D-129/EX081은 C-052 모델·renderer를 읽기 전용 재사용하는 별도 로컬 서빙/배틀 경로다.
새 `/health`는 checkpoint/source/GPU identity를, `/evaluate`는 C-051 JointInput에 대한
원순서 독립 q·최대 q 선택·입력/token hash를 제공한다. 타깃/private/seed는 요청 밖이다.
배틀 player는 공식 관측·원 JointInput 생성·동률 원순서·전송 전 rqid/합법성 검증을 적용한다.
요청600초·무절단32768·fallback/재시도0과 경기별 실패 격리·공유 기술 결함 중지를 검증한다.
실험별 모델/검증 gate·GPU/시계/admission·분모·재수집/복구·봉인은 EX081이 소유한다.
원 EX066 config의 GPU1은 학습 provenance이며 새 자원 GPU0으로 metadata를 덮어쓰지 않는다.
기존 learning·Kev·Qwen 경로의 schema와 기본값, 환경·가중치·STOP은 유지한다.
