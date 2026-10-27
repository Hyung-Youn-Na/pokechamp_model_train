# 후보 행동가치 추정 — 구성 설명

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="d-097-ex-060-한-경기-분기-수집"></a>
## D-097 EX-060 한 경기 분기 수집

`integration/pokechamp/branch_rollouts`는 EX-058의 원관측·명령을 읽어 pinned local
simulator에서 원경기를 재현하고 결정별 simulator/actor snapshot을 별도 보존한다.
normal decision은 양측 제출 전, 턴 중간 교체는 이미 확정된 choice와 queue를 유지한다.
원경기 각 suffix 재생 검증을 통과한 root만 후속 분기의 출발점이 된다.

Node simulator는 `pokemon-showdown/dist/sim`을 사용하며 public/actor 채널을 분리한다.
오프라인 Python Actor는 기존 Abyssal의 관측·정책·Python/NumPy RNG를 독립 보존한다.
분기마다 미래 simulator/actor RNG를 교체하고 자기 후보를 강제한 다음 양측 Abyssal로
진행한다. 신규 JEV/API 호출은 없다. parent 원장은 시도·누적 시계·4 worker 제출을 소유한다.

원자료·private snapshot·후보/반복별 trace와 학습용 export는 저장 경계를 구분한다.
`training.jsonl`은 당시 실전 관측·행동·조건부 통계만 전달하고 비공개 상태와 미래 난수를
포함하지 않는다. 보고/뷰어는 후보별 분모·검열·오류·미실행·대체 기록을 보존한다.
구체적인 조건과 결과는 [EX-060](experiments/EX-060-single-battle-branch-rollouts.md)을 따른다.


<a id="d-098-ex-061-후보별-행동가치-학습"></a>
## D-098 EX-061 후보별 행동가치 학습

EVE 독립 worktree의 `rlcd/pokemon_data.py`는 EX-060 봉인 통계/anchors/rollouts를
읽기 전용 대조하고 `inputs.jsonl`과167개 soft target `records.jsonl`을 분리한다.
`rlcd/pokemon_value.py`는 Qwen 비사고 chat template으로 무절단 토큰을 준비하고,
공식 text-only backbone 마지막 hidden에서 A/B 두 LM head 행만 읽는다.
기존 EVE 정수 answer loader·bandit training은 변경하지 않는다.
LoRA gradient를 후보 평균·관측별 update로 계산하고 baseline/epoch/reload 예측을 별도 보존한다.
EX-061 학습 자체에는 실제 배틀이 없었으며 실시간 연결은 아래 D-099 경로가 담당한다. 독립 배틀 성능은 미평가다.
[코드 안내](../../../.tools/eve-rlcd/worktrees/pokemon-training/docs/POKEMON_ACTION_VALUE.md) ·
[동결 protocol](experiments/EX-061-qwen-action-value.md).

<a id="d-099-ex-062-실시간-후보별-행동가치"></a>
## D-099 EX-062 실시간 후보별 행동가치

`integration/pokechamp/qwen_server.py`는 EVE 가상환경에서 EX-061의 InputExample/render/ValuePolicy를
재사용하고 GPU1의 고정 base+LoRA를 한 번 로딩한다. 표준 HTTP 서버의 loopback8765에서
health와 후보별 evaluate를 제공한다. GPU lock·무절단 입력·eval/no_grad·전후 fingerprint를 유지한다.
`qwen_player.py`는 기존 JEV 플레이어의 공식 관측·cursor·actor 경계를 상속하고 JEV v4 전문을
HTTP 입력으로 전송한다. 후보별 q 최댓값과 원순서 동률로 선택하며 새 rqid를 lock 앞에서 감지한다.
`qwen_battle.py`는 고정 Metamon2팀/seed의 진영교환2경기를 순차 실행하고 Qwen/Abyssal actor를
각각 독립 프로세스로 분리한다. 소유8109 worktree·타이머 off·재시도0·전체 시간 상한 없음을 적용한다.
`scripts/pokechamp-qwen`은 start/status/stop/probe/battle을 제공한다. 전수 감사는 `qwen_audit.py`,
오프라인 후보별 q+리플레이 내보내기는 `qwen_viewer.py`가 담당한다.
조건·완료/중단과 해석 원문은 [EX-062](experiments/EX-062-qwen-local-battle.md), runtime은
[C-049](CONTRACTS.md#c-049-qwen-local)이다. 기존 JEV 프로필·봉인·Blocked 실험은 보존한다.

D-102의 명시 입력 `qwen-candidate-state-v1`은 `qwen_temporal.Adapter`가 기존 JEV v4
생성기와 계산기를 재사용하고 결정별 instructions, 공개 교체 맥락, 동일 세트별 후보 전이를
추가한다. `diagnostics/candidate_state.py`가 정수 HP·능력치·테라·지원되는 진입 효과를
시간순으로 적용하고 미지원 전이는 사유와 unknown으로 남긴다. 큰 후보 결과는
`state.candidate_evaluations`에 한 번 두고 action ID로 참조한다. 공통 열과 수치 행 및 원문
설명 참조는 무손실 투영이며 원 구조·정수 roll·세트 가정은 외부 계산 감사에 보존한다.
`decision_instructions.compose`는 해당 결정 절차＋새 공통 규칙＋원 instructions 전문을
결합한다. 기존 q renderer와 A/B readout은 변경하지 않는다.

서버는 `--candidate-state`에서만 새 버전을 허용하고 `--diagnostics`에서만 별도
`/diagnose`를 제공한다. `qwen_diagnostics.py`의 짧은 JSON 예측은 같은 base＋LoRA의
별도 생성 결과이며 q 입력·선택·전송으로 되먹이지 않는다. `qwen_state_study.py`는
EX-063 actor cutoff의 원입력·지침만 변경·입력도 보완한 세 조건을 무전송 재생하고,
`qwen_state_run.py`가 동결 파일 검사·소유 서버·누적 기한·진단 전후 q 대조·정리·봉인을
관리한다. 계산 지원·진단 정확성·후보 순위·비용의 실행 원문은
[EX-064](experiments/EX-064-qwen-candidate-state.md), 계약은
[C-050](CONTRACTS.md#c-050-qwen-candidate-state)이다.

<a id="d-100-ex-063-학습-원대진-실전-진단"></a>
## D-100 EX-063 학습 원대진 실전 진단

Qwen runner는 EX별 schedule/probe/출력 원장을 선택한다. EX-063은 봉인된 원 battle-19와
공개 preview를 대조하여 원 team6/team2의 성별만 완성하고 원seed/진영으로 한 경기를 실행한다.
서빙·JEV v4·감사/뷰어 경로는 C-049를 재사용하며 기존 EX-062 source snapshot은 유지한다.

<a id="d-103-ex-065-공동-q-데이터-경로"></a>
## D-103 EX-065 공동 q 데이터 경로

`integration/pokechamp/joint_q/`는 reviewed108의 고정20상대·p2 고정 팀/80seed manifest,
공식 관측 root·별도 관측 추적 후속 actor, 원경기 전체/모든 root 다음 경계 재현을 제공한다.
프로세스 재사용·불변 root 캐시·내용 해시 정적 blob·RNG 결정 경계 checkpoint와 SQLite WAL
원장은 논리 rollout과 기술 시도를 구분한다. `serializer.JointInput`만 렌더링하고 `data.TrainingRecord`의
타깃은 분리한다. 입력/타깃/후보별 export·CPU tokenizer·감사/파일럿 gate는 동일 EX 루트에 보존한다.
계약은 [C-051](CONTRACTS.md#c-051-joint-q), 실제 검증·수집 상태는 EP-107/EX-065를 따른다.

<a id="d-104-ex-066-base-공동-q-학습-경로"></a>
## D-104 EX-066 Base 공동 q 학습 경로

`integration/pokechamp/joint_q/learning/`은 EX-065 공개 로더와 JointInput을 재사용하는 별도
학습·오프라인 평가 경로다. 새 renderer는 공식 Base chat template 뒤 후보별 ACTION_ID/Q_VALUE=
위치를 추가하고 명시 token position을 ID에 연결한다. `JointValuePolicy`는 공식 text backbone의
한 forward 결과에서 모든 후보 hidden state를 읽어 공유 FP32 head의 독립 sigmoid q를 반환한다.
text LoRA/head와 frozen BF16 base를 분리하며 기존 A/B 서빙 모델과 수집 코드는 유지한다.

`scripts/pokechamp-joint-q`는 EVE Python/물리 GPU1에서 prepare/preflight/train/evaluate/verify를 제공한다.
GPU2 사용 중 유휴 GPU 대체라는 D-106 지시에 따라 실행 자원을 고정했다.
준비 토큰/소스·데이터·Base/tokenizer 해시, 완전 optimizer/RNG/cursor checkpoint, validation
선택·새 프로세스 재로딩, test 잠금/모델별1회 예약과 저장 예측 분석을 연결한다.
조건·분모·복구·해석은 EX-066, runtime은 C-052, 실제 검증·실행 상태는 EP-108이 소유한다.

<a id="d-129-ex081-공동-q-체크포인트-배틀-경로"></a>
### D-129 EX081 공동 q 체크포인트 배틀 경로

`joint_q/battle_eval/`은 원 epoch3·학습 renderer를 읽기 전용으로 재사용한다. EVE GPU0 서버는
관측당 공동 q를 직렬 평가하며 독립 health endpoint로 모델/프로세스/소스 식별자를 제공한다.
두 별도 프로세스의 전체 validation 재현 후 마지막 프로세스를 유지하여 native CPU player와
loopback으로 연결한다. 원 test20 manifest·공식 JointInput 생성·전송 직전 rqid/합법성 검증을
재사용하고 별도 admission/누적 시계·모든 raw I/O·독립 감사/뷰어를 새 실험에 보존한다.
조건 원문은 EX081, runtime은 C-062, 진행은 EP-133이다. 기존 learning/Kev 경로는 유지한다.
`outputs.correct_baseline`은 원 보고/입력 감사의 해시를 보존한 상태에서 같은 역사 실험 계보의
version-sealed capture 링크를 읽어 비교만 정정한다. 뷰어는 선택한 final receipt에 원자료를
결합하고, 이동 후 DOM 준비를 기다려 모든 입력/q/전송을 오프라인 검증한다.

<a id="d-107-ex-067-abyssal-tera-보완-수집"></a>
## D-107 EX-067 Abyssal Tera 보완 수집

`abyssal_tera.py`의 관측 전용 정책은 기존 선택1회 뒤 고정 공격·방어 규칙으로 주문을 바꾼다.
`joint_q.Actor`는 opt-in policy ID/config와 공개 기술 추적을 원경기·후속·snapshot·재개에 유지한다.
과거 metadata 없는 actor는 기존 Abyssal이다. 강제 첫 후보의 p2 정책 호출은0이다.
`tera_config.py`는 별도 seed namespace를 제공하고 `tera.py` CPU 실행기는 단계별 gate를 강제한다.
판단 사유/원자료와 JointInput을 분리하며 기존 EX-066 봉인 소스/로더/환경은 보존한다.
`tera_inputs.py`는 공개 prefix의 팀별 Tera 소모를 현재 개체 표시와 구분하여 입력에 보존한다.
`tera_recovery.py`는 첫 파일럿 입력 결함의 원자료·소스·최초 시계를 보존하고,
정책/seed 불변과 독립 검증 receipt를 확인한 `public-tera-v2`만 준비한다.
감사·뷰어/복사 경로는 `tera_verify.py`·`tera_outputs.py`, 상세 실행은 [전용 안내](../../../integration/pokechamp/joint_q/TERA.md)를 따른다.
