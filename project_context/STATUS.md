# 프로젝트 상태 (Project Status)

현재 연구선은 `research/model-training`이며 목적은 **모델 학습·정책 개선·독립 평가**다.
[D-131](decisions/D-131-research-branch-preservation.md)에 따라 연구 목적을 분리하며, 현재 실행 중인 학습·평가·배틀 실험은 없다.
기존 Blocked/Paused와 동결 protocol·봉인은 유지한다.

- 기준일: 2026-10-13
- 현재 작업 위치: `/workspace`
- 목표 원문: [CHARTER](CHARTER.md) · [연구 설계](RESEARCH_DESIGN.md)
- 경로·출력·외부 보존본·복원: [연구선 작업·출력·복원 안내](RESEARCH_WORKFLOW.md)
- 진행·검증은 개별 plan, 실험 조건·결과·분모는 개별 EX와 보고서를 따른다.

<a id="current-objective"></a>

## 현재 연구 목표

포켓몬 관측·합법 행동에 맞춘 모델 학습과 정책 개선을 주 개발 목표로 관리한다.
개선 여부는 학습·모델 선택과 분리한 평가로 판단한다. 기존 세 RLCD 환경과 Qwen·Kev·
고정 대진 구현은 활용 가능한 기반이며, 다음 실험의 방법·초기 모델·데이터·평가·예산은
아직 새 실행 작업으로 등록하지 않았다. L1-L5 구조 이식은 별도 연구선에서 보존·후속 설계한다.

<a id="active-work"></a>

## 현재 실행 작업

[EP-136](exec-plans/active/EP-136-branch-research-manuals.md)에서 연구선별 매뉴얼을 정비 중이다.
실험·환경 변경은 포함하지 않는다. [EP-135](exec-plans/completed/EP-135-research-branch-preservation.md)의
브랜치 분리·공통 태그·외부 보존·검증을 완료했다. 기존 실행 코드와 환경은 유지했으며
과거 실험을 재개하거나 Blocked/Paused를 완료로 바꾸지 않았다.

## 분리 전 실험 상태와 보존 근거

아래 기록은 기존 실험·구현의 결과와 한계를 보존한 요약이다. 문단의 “현재” 또는 GPU·환경
참조는 해당 작업의 보고 시점을 포함하므로 현 시점 실행 목록으로 읽지 않는다.
각 EX·plan의 최종 상태가 원문이며 분리로 Blocked/Paused를 완료 또는 재개로 바꾸지 않는다.

[EP-134](exec-plans/active/EP-134-jev27b-ex058-reproduction.md) /
[EX-082](experiments/EX-082-jev27b-ex058-reproduction.md): 공개 JEV-27B를 추가 학습 없이
평가했으나 GPU0 사용량 상한 초과로 본 수집이 중단되어 **Blocked**다. 진입 검증과 부분
결과의 전수 감사·오프라인 뷰어·봉인·소유 GPU/프로세스 반환을 마쳤다. 전체32경기·16쌍
목표는 미달이며 자동재개하지 않는다. EX-080/GPU2·3은 본 작업에서 변경하지 않았다.
[중단 보고](exec-plans/evidence/ep134/report.md) · [부분 결과 뷰어](../exports/battle_viewers/ex082/index.html).

[EP-133](exec-plans/completed/EP-133-joint-q-battle.md) / [EX-081](experiments/EX-081-joint-q-battle.md):
EX066 epoch3의 GPU0 재qualification과 실제 test20 평가를 완료했다. 원 예측/프로세스 간
최대차이0,20경기 유효완료·0승20패이며 전수 감사·정정 비교·오프라인 뷰어·봉인을 마쳤다.
소유 실행/감시0·GPU0 반환이다. 원 EX066 실패/오프라인 test 미완료와 가중치를 보존하며,
과거 GPU1 불일치 원인은 미확정이다. [최종 보고](../.pokechamp-data/experiments/ex081-joint-q-battle/corrections/baseline-v2/final/report.md) ·
[20경기 뷰어](../exports/battle_viewers/ex081-baseline-v2/index.html) · [완료 검증](exec-plans/evidence/ep133/completion.json).

[EP-132](exec-plans/completed/EP-132-qwen-matrix-selfplay.md) / [EX-080](experiments/EX-080-qwen-matrix-selfplay.md): Qwen3.5-0.8B 행렬 탐색 자기대국을 완료했다. 시도 1·2는 benchmark Pool 정리 결함으로 학습 전에 중단·보존했고, 시도 3이 40라운드에서 둔화 종료해 round 36을 선택했다. 잠긴 test 640/640에서 P1 대 P0 직접 대결은 0.805였으나, 고정 abyssal 상대는 모든 조건 1~2승/128의 바닥 효과로 주판정 P1−P0 +0.008 [−0.016, +0.031], 즉 개선 미입증이다. 전수 감사·오프라인 뷰어·봉인·GPU2·3/lock 반환을 마쳤고 추가 실행은 없다. [최종 보고](exec-plans/evidence/ep132/report.md) · [뷰어](../exports/battle_viewers/ex080-45e558ad/index.html) · [종결 검증](exec-plans/evidence/ep132/completion-verification.json).

[EP-131](exec-plans/completed/EP-131-fixed-matchup-stopping.md): EX079는32라운드 상한에서 종료하고24라운드를 선택했다. 독립시험·감사/뷰어·봉인/자원 반환 완료. 초기모델 상대는 우세하지만 Abyssal 주평가 개선은 미입증이다. EX079 실행/알람은 종료됐으며 추가 주기는 없다. [최종 보고](exec-plans/evidence/ep131/report.md).

[EP-129](exec-plans/completed/EP-129-first-round-single-retry.md): 정상31 계승·실패1 재수집 후 첫라운드 학습·체크포인트/감사/뷰어·봉인·자원 반환을 완료했다. 현재 학습/알람 실행은 없다.

[EP-130](exec-plans/completed/EP-130-first-round-model-comparison.md): 초기/학습 모델의 동일 저장 관측 비교를 완료했다. 행동 분포 변화는 작고 학습 자료 내 가치 MSE는 감소했다. 독립 승률 개선은 미평가다. [비교 보고](exec-plans/evidence/ep130/report.md).

[EP-127](exec-plans/active/EP-127-fixed-matchup-first-round.md): 원실행31정상/1시간초과로 학습0·Blocked. 감사/뷰어/봉인·GPU 반환 완료. D124로 시간 규범/실행기를 변경했으며 재실행은 하지 않았다. dev/test·후속 라운드는 실행 범위 밖이다.

[EP-126](exec-plans/active/EP-126-fixed-matchup-day.md): 사용자 요청으로 Paused. GPU 검증·benchmark는 통과했으나 pilot 미완료로 하루 내 비용은 미확정이다. 학습/test0·보고/자료 보존·GPU 반환 완료; 사용자 결정 전 재개하지 않는다.

[EP-125](exec-plans/active/EP-125-fixed-matchup-run.md): 기절 분류 교정 후 GPU 검증·측정128을 통과했지만 사전 평가 비용 하한6.97시간이3시간을 초과해 학습/test를 보류했다. 정상32·중단16 감사/뷰어·봉인·GPU 반환 완료. 실험은 Incomplete이며 추가 실행은 없다. [최종 보고](exec-plans/evidence/ep125/budget-report.md).

[EP-124](exec-plans/completed/EP-124-fixed-matchup-mcts.md): 고정 공개 상태 MCTS·약150만 파라미터
정책/가치 모델·학습/평가·재개/감사/뷰어 구현과 CPU39검사를 완료했다.
[검증 보고](exec-plans/evidence/ep124/report.md). EX-076의 실제 실행은 EP-125에서 관리한다.

[EP-123](exec-plans/completed/EP-123-life-orb-input.md): Life Orb 반동으로 공개된 상대 도구가
입력에서 null로 가려지는 결함을 교정했다. CPU 회귀·실제 EX-075 입력1건 재구성 검증 완료.
향후 새 입력에 적용하며 과거 학습 artifact는 보존했다. 과거 전체 영향·성능 효과는 미측정이다.


[EP-122](exec-plans/completed/EP-122-abyssal-rl-next.md) /
[EX-075](experiments/EX-075-abyssal-rl-next.md)는 추가 학습·평가·감사·뷰어·봉인·자원 정리를
완료했다. 출발 대비 개선은 입증되지 않았고 성능 목표는 미달이다. 미완료 기준은 없으며
다음 학습 주기는 시작하지 않았다. 상세 성능·자원·증거는 EX-075를 따른다.

[EP-121](exec-plans/completed/EP-121-abyssal-rl-continue.md) /
[EX-074](experiments/EX-074-abyssal-rl-continue.md#final-results):
57라운드 계승 추가 학습·보정 판단·잠긴 test·독립 감사·뷰어 내보내기·표본 오프라인 확인·
봉인·자원 정리를 완료했다. 출발 대비 통계적 개선은 확인했으나 성능 목표는 미달이다.
EX-074 실행·알람 종료, GPU·전용 포트 반환을 확인했다. 해당 실행의 반복 모니터링은 없다.
[최종 보고](../.pokechamp-data/experiments/ex074-abyssal-rl-continue/final/report.md) ·
[뷰어](../exports/battle_viewers/ex074/index.html). EX-073의 미완료 판정은 보존한다.

[EP-119](exec-plans/active/EP-119-abyssal-rl.md) / [EX-073](experiments/EX-073-abyssal-rl.md#final-results):
4GPU 학습·보정·잠긴 test와 독립 감사는 종료했다. 초기 대비 성능 개선은 사전 정의 통계
기준을 충족했으나 목표 승률에는 미달했다. 최종 오프라인 뷰어 전수 검증이 원24시간 한도로
실패하여 실험은 Incomplete, plan은 Blocked로 보존한다. GPU·실행/브라우저·전용 포트는
해제됐고 반복 모니터링·추가 실행은 없다. 상세 분모와 실패·보고·뷰어는 EX-073을 참조한다.
기존 EX-066 재로딩 실패·자료는 보존하며 해당 실행을 재개하지 않는다.


[EP-116](exec-plans/completed/EP-116-selfplay-rlcd.md) / [EX-072](experiments/EX-072-selfplay-rlcd.md):
승인된 EX-071 출발 자기대국·PPO/WDL/BC·head 보정·sampling 평가의 별도 경로를 구현하고
필수 검증·실제 SIGTERM 재개·네 라운드 학습·선택·보정 판단·잠긴 test를 완료했다.
round-2와 보정 전 head를 채택했으며 test 점수차의 대응 구간이0을 포함해 개선은 미입증이다.
[EP-117](exec-plans/completed/EP-117-selfplay-finalization-recovery.md)의 별도 CPU 정정본에서
브라우저 의존성·큰 정수 표시를 교정하고 원 검증기의 전수 오프라인 검사·보고·봉인을 완료했다.
원 실패 판정·자료·가중치·시계는 보존하며 최초24시간 한도 안에 종료했다. 현재 EX-072 실행/감시0,
GPU3 반환·GPU1/EX-066 유지다. [최종 결과](experiments/EX-072-selfplay-rlcd.md#final-results),
[정정 보고](../.pokechamp-data/experiments/ex072-selfplay-rlcd/corrections/finalization-v3/report.md),
[584경기 뷰어](../exports/battle_viewers/ex072-finalization-v3/index.html)를 따른다.

[EP-115](exec-plans/completed/EP-115-qwen-replay-imitation.md) / [EX-071](experiments/EX-071-qwen-replay-imitation.md):
새 Base·Kev Choice 경로의 CPU 복원·전수 감사, GPU3 첫 학습·실제 부분 재개·validation 선택,
잠긴 test 각1회와 고정40경기를 완료했다. 전체 인간 선택 재현 지표는 개선됐으나 Tera 등
세부 지표는 악화됐고 배틀 개선은 불확실하다. 원 제어 종료는 원인 미확정으로 보존하고
독립 감사 후 미시도 단계만 같은 조건으로 완료했다. 원자료/뷰어 해시와 전 경기 감사·
이동 후 오프라인 Chromium 검사·소유 자원 정리가 통과했다. 현재 EX-071 실행·감시0,
GPU3 반환이며 별도 EX-066/GPU1은 유지했다. 조건·분모·해석은
[최종 결과](experiments/EX-071-qwen-replay-imitation.md#final-results),
[통합 보고](../.pokechamp-data/experiments/ex071-qwen-replay-imitation/final/report.md),
[40경기 뷰어](../exports/battle_viewers/ex071/index.html)를 따른다.

[EP-113](exec-plans/completed/EP-113-kev-continuation-question.md) / [EX-070](experiments/EX-070-kev-continuation-question.md):
명시적 새 후속 질문 프로필과 동일 첫 대진1경기 진단을 완료했다. 기존/새 조건·승패·동일 입력
비교의 한계는 [최종 보고](exec-plans/evidence/ep113/report.md)를 따른다. CPU 검증·전수 감사·
오프라인 뷰어·원/새 봉인·소유 자원 정리/GPU3 반환과 EX-066/GPU1 보존을 확인했다.
현재 Kev/배틀/감시 실행은 없으며 [1경기 뷰어](../exports/battle_viewers/ex070/index.html)를 제공한다.

[EP-112](exec-plans/completed/EP-112-kev-test-battles.md) / [EX-069](experiments/EX-069-kev-test-battles.md):
기존 test20 본 평가·전수 감사·독립 집계·C-047 뷰어·원 봉인 보존·소유 자원 정리를 완료했다.
추가 사전검사는 사용자 지시로 생략했으며 본 평가는 성능 개선을 보이지 않았다. 승패·분모와
역사 기준선 차이의 해석은 [최종 보고](exec-plans/evidence/ep112/report.md)를 따른다.
Kev/배틀/감시 실행은 종료·GPU3 반환이며 EX-066/GPU1은 유지했다.
[20경기 뷰어](../exports/battle_viewers/ex069/index.html)를 제공한다.

[EP-111](exec-plans/completed/EP-111-kev-battle.md) / [EX-068](experiments/EX-068-kev-battle.md):
Kev-4B 연결을 완료했다. D-109의 bf16/T1/fused·merged 조건에서 validation 입력·dev 예측을
재현하고,1경기·57결정의 전수 감사와 fallback0·오프라인 뷰어·봉인·소유 자원 정리를 확인했다.
원 unmerged gate 실패는 보존한다. 단일 smoke의 패배로 배틀 성능 효과를 판단하지 않는다.
EX-068의 Kev/배틀/감시는 종료·GPU3 반환을 확인했고 EX-066/GPU1 기존 실행을 유지했다.
[최종 보고](exec-plans/evidence/ep111-fused/report.md) · [뷰어](../exports/battle_viewers/ex068/index.html) ·
[실행 안내](../integration/pokechamp/KEV.md).

[EP-110](exec-plans/completed/EP-110-abyssal-tera-joint-q.md) / [EX-067](experiments/EX-067-abyssal-tera-joint-q.md):
`abyssal-tera-v1`과 새80경기·2,543관측·21,401후보·684,832분기의 수집·전수 감사·봉인·백업을 완료했다.
공개 Tera 소모 입력의 승인된1회 교정 복구와 원본 보존을 검증했고, 정책/seed/첫 시계는 유지했다.
필수 CPU175검사·80경기 뷰어의 오프라인 전수 검사·백업 체크섬/공개 로더가 통과했다.
EX-066의 봉인 소스/입력/환경과 실행은 보존하며 새 자료를 현재 학습에 병합하지 않았다.
EX-067 수집/검증 프로세스0이며 새 q는 새 후속 정책에 조건부다. 분모·비용·한계는
[최종 보고](../.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2/final/report.md),
[완료 검증](exec-plans/evidence/ep110/completion.json), [80경기 뷰어](../exports/battle_viewers/ex067/index.html)를 따른다.

[EP-108](exec-plans/active/EP-108-joint-q-training.md) / [EX-066](experiments/EX-066-joint-q-training.md):
새 프로세스 재로딩에서 q 최대차이0.0018912255764007568이 기존1e-4 gate를 초과했다.
원 가중치·검증/재로딩 로그·자료를 보존하며 현재 GPU 점유0이다. EX-073 준비를 이유로
기준을 완화하거나 EX-066을 재개하지 않는다. [원 재로딩 로그](../.pokechamp-data/experiments/ex066-joint-q-training/reload.log).

[EP-107](exec-plans/completed/EP-107-joint-q-data.md) / [EX-065](experiments/EX-065-joint-q-data.md):
`versions/collection-v5`의80경기·2,668관측·24,474후보·783,168유효 분기 수집,
전수 감사·로더·토큰/렌더링·봉인을 완료했다. 분모·중복·실패·비용·한계는
[최종 보고](../.pokechamp-data/experiments/ex065-joint-q/versions/collection-v5/final/report.md)를 따른다.
학습 파일과 관련 기록을 `/mnt/digicap/combined/hyna/backup/pokechamp/`에 복사하고
크기/SHA-256·관측/후보 ID·공개 로더를 검증했다.
[복사 검증](exec-plans/evidence/ep107/copy-training-verification.json) ·
[최종 용량·체크섬·종료 확인](exec-plans/evidence/ep107/copy-training-closure.json).
private/이전 버전·과거 봉인은 보존하며 본학습·모델 호출0, 뷰어 생략, 현재 수집/감시0이다.

[EP-106](exec-plans/completed/EP-106-qwen-candidate-state.md) / [EX-064](experiments/EX-064-qwen-candidate-state.md):
후보 실행 후 상태 입력·결정별 instructions·별도 진단과 저장3조건 비교를 완료했다.
상태 판단 개선은 미입증이며 동결 결과와 종료 후 코드 보정을 분리해 보존했다.
기존 q/원자료·가중치 유지·소유 서버/GPU1 반환·오프라인 비교 화면 검증 완료,
현재 실행0·새 배틀/학습/API0. [보고](exec-plans/evidence/ep106/report.md) ·
[비교 화면](../exports/qwen_candidate_state/ex064/index.html).

[EP-105](exec-plans/completed/EP-105-viewer-action-names.md): 현재 EX-063·향후 Qwen/JEV 뷰어의 실제 기술/교체/선봉 이름 표시를 적용했다. 오프라인 이름 대조·이전 버전/원자료 봉인 보존 완료, 새 배틀/GPU 실행0. [보고](exec-plans/evidence/ep105/report.md).

[EP-104](exec-plans/completed/EP-104-qwen-training-matchup.md) / [EX-063](experiments/EX-063-qwen-training-matchup.md):
학습 원대진 Qwen p2 대 Abyssal p1 정상1/1·12턴 패배. 자동 감사의 빈 줄 누락을 평가 코드만
교정하여18결정/121후보 전수 감사·토큰·뷰어 오프라인 검증/봉인/정리 완료. 현재 소유 서버/배틀/감시0·GPU1 반환.
학습 효과/독립 배틀 성능은 미평가다. [보고](exec-plans/evidence/ep104/report.md) · [뷰어](../exports/battle_viewers/ex063/index.html).

[EP-103](exec-plans/active/EP-103-qwen-local-battle.md) / [EX-062](experiments/EX-062-qwen-local-battle.md):
Qwen 최종 LoRA 로컬 서빙 구현·GPU 대조는 완료했다. 배틀은 입력 전 cwd 오류로 정상0/2·Blocked다.
교정/CPU 검증·부분 로그 뷰어·봉인·정리 완료, 현재 서버/배틀/감시0·GPU1 반환.
새2경기는 추가 승인 전 실행하지 않는다. [보고](exec-plans/evidence/ep103/report.md).


[EP-102](exec-plans/completed/EP-102-qwen-action-value.md): EX-060 변환·EVE soft target LoRA·오프라인 가치 검증을 완료했다. [실행 조건·결과](experiments/EX-061-qwen-action-value.md) · [보고](exec-plans/evidence/ep102/report.md). 새 배틀0·현재 실행0.

[EP-101](exec-plans/completed/EP-101-single-battle-branch-rollouts.md) / [EX-060](experiments/EX-060-single-battle-branch-rollouts.md): 22상태·167행동·5,344/5,344분기를 정상 수집하고 전수 감사·학습 통계·뷰어·봉인·정리를 완료했다. 실제 모델 학습0, 현재 수집/감시 프로세스0. [최종 보고](exec-plans/evidence/ep101/report.md) · [뷰어](../exports/battle_viewers/ex060/index.html) · [학습용 통계](../exports/battle_viewers/ex060/training.jsonl).

[EP-100](exec-plans/completed/EP-100-replay-rule-eligibility.md): 로컬 Gen9 OU 규칙으로 리플레이를 분류했다.
공개 위반 미발견 후보와108종 제한 충족 목록을 별도로 제공하며 완전한 세트 합법성을 보장하지 않는다.
[분류 보고·목록](../exports/replay-eligibility/gen9ou-local-v1/report.md) · [22개 검사·전수 감사](exec-plans/evidence/ep100/report.md).
학습 데이터 편입·holdout 확정·학습·새 배틀은 수행하지 않았으며 현재 분류 실행 없음.

[EP-099](exec-plans/completed/EP-099-pokemon-training-objective.md): 세 환경 기반 포켓몬 전용 학습을 당면 목표로 문서화했다. 목표·현재 단계·다음 단계와 D-096을 동기화했으며 실제 학습·새 배틀은 아직 수행하지 않았다. [검증 보고](exec-plans/evidence/ep099/report.md). 현재 문서 작업 실행 없음.

[EP-098](exec-plans/completed/EP-098-rlcd-lite-environment.md): RLCD-Lite 독립 worktree·Python3.11.11의 `.venv-rlcd-lite`·CUDA12.8 호환 lock 설치와 기본 테스트·GPU/공개 모델 검증을 완료했다. [환경 구분·재진입](../.tools/rlcd-lite/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md) · [검증 보고](exec-plans/evidence/ep098/report.md). 포켓몬 학습·성능은 미평가이며 현재 설치/검증 실행 없음.

[EP-097](exec-plans/completed/EP-097-eve-rlcd-environment.md): EVE-RLCD 독립 worktree·Python3.12.14의 `.venv-eve-rlcd`·upstream lock 설치와 CPU 테스트·GPU/공개 결정 모델 검증을 완료했다. [환경 구분·재진입 안내](../.tools/eve-rlcd/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md) · [검증 보고](exec-plans/evidence/ep097/report.md). 포켓몬 학습·성능은 미평가이며 현재 설치/검증 실행 없음.

[EP-096](exec-plans/completed/EP-096-laya-training-environment.md): LAYA-RLCD 전용 worktree·독립 CUDA 환경 설치, upstream Python20검사·GPU 연산/역전파·고정 공개 모델 로딩/최소 추론을 완료했다. 당면 학습 목표에 활용할 환경이며 포켓몬 학습·성능은 미평가다. [환경 안내](../.tools/laya-rlcd/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md) · [검증 보고](exec-plans/evidence/ep096/report.md). 현재 설치/검증 실행 없음.

[EP-095](exec-plans/completed/EP-095-jev-compact32.md) / [EX-059](experiments/EX-059-jev-compact32.md): 유효32/32경기·완료16/16쌍, JEV 8승0무24패. EX-058 대비 -9.38%p. Completed: 실험 완료. 감사·보고·뷰어·봉인·정리 완료. 현재 실행/감시 없음. [보고](exec-plans/evidence/ep095/report.md) · [뷰어](../exports/battle_viewers/ex059/index.html).

[EP-094](exec-plans/completed/EP-094-jev-improved32.md) / [EX-058](experiments/EX-058-jev-improved32.md): 유효32/32경기·완료16/16쌍, JEV 11승0무21패. EX-057 대비 +12.50%p. Completed: 실험 완료. 감사·보고·뷰어·봉인·정리 완료. 현재 실행/감시 없음. [보고](exec-plans/evidence/ep094/report.md) · [뷰어](../exports/battle_viewers/ex058/index.html).

[EP-093](exec-plans/completed/EP-093-jev-offline-input.md)의 JEV 별도 오프라인 입력 표현·공식 로그·
피해량/역할/상성·벤치 축약 비교 구현·오프라인 검증을 완료했다. [보고·전후 예시](exec-plans/evidence/ep093/report.md).
D-093 사용자 후속 지시에 따라 확률 대신 세트별 스피드 불확실성을 반영하고 전체 완료 기준을 충족했다. EP-093은 Completed다. 운영 v3·과거 자료를
유지하고 API·새 배틀·운영 전환0이다. 현재 프로세스/배틀/감시 작업 없음.

[D-091](decisions/D-091-reviewed-species-team-list.md)에 따라 현재 팀 후보를 원본 검토 완료108종만으로 구성된 Metamon 파일 목록으로 제한했다. [팀 목록·사용 기준](../export/teams/README.md) · [EP-092 검증](exec-plans/completed/EP-092-reviewed-species-team-list.md). 새 팀 선택은 이 목록을 사용하며 upstream 로더에는 자동 필터가 없다. 세트별 역할 매칭은 추가 필터가 아니다. API·새 배틀·현재 실행 없음.

[EP-091](exec-plans/completed/EP-091-team-corpus-role-expansion.md)의 팀 데이터409종 열람 역할 DB 확장·전수 커버리지·재현 검증을 완료했다. [확장본](../export/docs/gen9ou_team_pool_role_db.json) · [보고](exec-plans/evidence/ep091/report.md). 실제 세트 기반 추론이며 전략적 정확성/효능 미평가다. API·배틀·운영 변경 및 현재 실행 없음.

[EP-082](exec-plans/completed/EP-082-jev-damage-samples.md)의 기술별 피해량 범위 오프라인 샘플·전후 입력·계산 감사를 완료했다. [비교 보고·JSON](exec-plans/evidence/ep082/report.md)을 검토할 수 있다. 모델 적용·성능 평가는 미결정/미평가이며 API·새 배틀·운영 기본값 변경 및 현재 실행/감시 없음.

[EP-081](exec-plans/completed/EP-081-jev-pinned32.md) / [EX-057](experiments/EX-057-jev-pinned32.md):
유효32/32경기·완료16/16쌍, JEV 7승0무25패. v2 대비 공통 완료쌍 차이 +0.00%p. 상태 Completed: 실험 완료. 감사·보고·뷰어·봉인·정리 완료. 현재 실행·감시 없음.
[전후 비교 보고](exec-plans/evidence/ep081/report.md) · [경기별 뷰어](../exports/battle_viewers/ex057/index.html).

[EP-080](exec-plans/active/EP-080-jev-direct32.md) / [EX-056](experiments/EX-056-jev-direct32.md):
유효21/32경기·완료7/16쌍, JEV 1승0무20패. v2 대비 공통 완료쌍 차이 -7.14%p. 상태 Blocked: 실패1·미실행10·실험 미완료; 중단 원인: JEV request failed: http (HTTP 400). 감사·보고·뷰어·봉인·정리 완료. 현재 실행·감시 없음.
[전후 비교 보고](exec-plans/evidence/ep080/report.md) · [경기별 뷰어](../exports/battle_viewers/ex056/index.html).

[EP-079](exec-plans/completed/EP-079-jev-retry-backoff.md): 새 JEV 기본 대기10·30·60초·재시도3회·과거 정책 호환을 적용하고 관련146검사와 과거 감사를 완료했다. 실제 API0·현재 실행/감시 없음. [보고](exec-plans/evidence/ep079/report.md).

[EP-078](exec-plans/completed/EP-078-jev-failed-input-probe.md) / EX-055: EX-054 동일 실패 입력에 첫 시도 HTTP200·실측10,515토큰을 확인했다. 과거 실험은 보존하며 현재 실행·감시 없음. [보고](exec-plans/evidence/ep078/report.md).

[EP-077](exec-plans/active/EP-077-jev-v3-retry32.md) / [EX-054](experiments/EX-054-jev-v3-retry32.md):
유효0/32경기·완료0/16쌍, JEV 0승0무0패.v2 대비 공통 완료쌍 차이 미산출. 상태 Blocked: 실패1·미실행31·실험 미완료; 중단 원인: JEV request failed: http (HTTP 503). 감사·보고·뷰어·봉인·정리 완료. 현재 실행·감시 없음.
[전후 비교 보고](exec-plans/evidence/ep077/report.md) · [경기별 뷰어](../exports/battle_viewers/ex054/index.html).

[EP-076](exec-plans/completed/EP-076-provider-retry-three.md): 새 JEV provider 오류 재시도3회 고정·시도별 원장/기한/취소·관련 검증을 완료했다. 실제 API·새 배틀·과거 실험 재개0. [보고](exec-plans/evidence/ep076/report.md). 현재 실행·감시 없음.

[EP-075](exec-plans/active/EP-075-jev-v3-abyssal32.md) / [EX-053](experiments/EX-053-jev-v3-abyssal32.md):
첫 경기78턴·91번째 요청 HTTP503으로 중단했다. 유효0/32·완료0/16쌍·실패1·미실행31로 성적 비교 미완료(Blocked)다.
감사·보고·뷰어·봉인·정리 완료. 현재 실행·감시 없음.
[보고](exec-plans/evidence/ep075/report.md) · [뷰어](../exports/battle_viewers/ex053/index.html).

[EP-074](exec-plans/completed/EP-074-jev-v3-effects.md)에서 새 기본 `jev-choice-v3`에
사용자 Gen9 기본 지식 전문·요청별 상세 효과 사전을 추가하고 모델 입력의 current_pp_source를
제거했다. 오프라인 대조·관련 회귀·과거 자료 보존을 완료했다.
[보고·전후 예시](exec-plans/evidence/ep074/report.md). API·새 배틀0이며 성능은 미평가다.
현재 실행·감시 없음.

[EP-073](exec-plans/completed/EP-073-jev-abyssal32.md) / [EX-052](experiments/EX-052-jev-abyssal32.md):
유효32/32경기·완료16/16쌍, JEV 7승0무25패. 감사·한국어 보고·뷰어·봉인·정리 완료. 현재 실행·감시 없음.
[보고](exec-plans/evidence/ep073/report.md) · [경기별 뷰어](../exports/battle_viewers/ex052/index.html).

[EP-072](exec-plans/completed/EP-072-viewer-navigation-hp.md)에서 EX-051 뷰어의 방향키 결정 탐색과
상대 HP 공개 백분율 표시를 적용하고 오프라인 검증·원자료 보존을 완료했다.
[보고](exec-plans/evidence/ep072/report.md). 현재 실행·감시 없음.

[EP-071](exec-plans/completed/EP-071-jev-v2-battle.md) / [EX-051](experiments/EX-051-jev-v2-battle.md):
교정 JEV 입력을 EX-050과 동일 조건2경기로 검증했다. 정상완료2/2·JEV1승1패, 전수 감사·보고·봉인·정리 완료.
[보고](exec-plans/evidence/ep071/report.md) · [경기별 뷰어](../exports/battle_viewers/ex051/index.html). 현재 실행·감시 없음.

[EP-070](exec-plans/completed/EP-070-jev-lead-input.md)에서 EX-050 자기 선봉 입력을
별도 jev-choice-v2로 교정하고 저장 자료·단위 테스트 검증을 완료했다.
[교정 보고·전후 예시](exec-plans/evidence/ep070/report.md). 현재 실행·감시 없음.
API·새 배틀·과거 재개는 없으며 EX-050 봉인·판정·내보내기는 보존한다.

정상 종료 배틀 실험의 뷰어는 [C-047](CONTRACTS.md#c-047-viewer-export)에 따라
[exports/battle_viewers 목록](../exports/battle_viewers/index.html)에 제공한다.
현재 EX-050의 [경기별 입력·응답+리플레이](../exports/battle_viewers/ex050/index.html)를 제공한다.
실험자용 화면은 요청/응답 JSON·복사/다운로드·상태 요약·기술 기록을 분리한다.
입력·응답·로그는 오프라인 열람하며 애니메이션에는 인터넷 연결이 필요하다.

[EP-066](exec-plans/completed/EP-066-jev-judgment-repeat.md) / [EX-050](experiments/EX-050-jev-judgment-recovery.md)의
JEV2경기를 정상 완료했다. choice-action-v3의 합법 선택 수락·판단 진단·경기 실패 격리를 적용하고
JEV1승1패·전수 입력/전송 감사·보고/봉인/정리를 완료했다. 현재 실행·감시 없음.
EX-049 API0 준비 실패와 과거 EX-047/048 중단·봉인은 보존한다.
[한국어 보고·viewer](exec-plans/evidence/ep066/report.md), [C-046](CONTRACTS.md#c-046-provider-judgment).

[EP-064](exec-plans/active/EP-064-jev-repeat.md) / [EX-048](experiments/EX-048-jev-repeat.md)은 첫 경기86턴 JEV 승리, 두 번째42턴 선택/최댓값 불일치로 중단해 정상완료1/2·Blocked다. 전수 감사·보고/viewer·봉인·정리 완료, 현재 실행·감시 없음. [보고](exec-plans/evidence/ep064/report.md).

[EP-063](exec-plans/completed/EP-063-jev-probability-validation.md)에서 사용자 지적에 따라 JEV 확률 합계 검사를 제거했다. 개별 값·후보·최상위 선택 검사는 유지하며 저장17응답이 새 기준을 통과했다. 실제 추가 호출0이고 EX-047 미완료는 보존한다.

[EP-062](exec-plans/active/EP-062-jev-battle.md)의 JEV Choice 입력·선봉/배틀 연결·로컬2경기 검증을 완료했다. [EX-047](experiments/EX-047-jev-battle.md)은 실제17요청 후 확률합0.99 검증으로 중단해 정상완료0/2·Blocked다. 보고·viewer·감사·봉인·정리 완료, 현재 실행·감시 없음. [최종 보고](exec-plans/evidence/ep062/report.md).

[EP-061](exec-plans/completed/EP-061-jev-client.md)의 JEV 환경 설정·독립 호출 기반을 구현하고 모의 HTTP·기존 회귀 검증을 완료했다. 당시 범위는 독립 호출 기반이며 실제 연결·배틀 통합 후속은 EP-062를 따른다.

[EP-059](exec-plans/completed/EP-059-async-official-lead.md)의 비동기 교정본
[EX-046](experiments/EX-046-async-official-lead.md) 본실험을 완료했다. 유효32경기·16대응쌍,
전수 감사·한국어 보고·viewer·봉인·자원 정리를 확인했다. 공급자별 탐색 결과는
[최종 보고](exec-plans/evidence/ep059/final-report.md)를 따르며 선봉 개선·L1–L5 효과는 확정하지 않는다.
현재 EX-046 실행·감시는 없고 EX-045의 중단·봉인은 보존한다.
[EP-060](exec-plans/completed/EP-060-portable-viewer.md)의 [다운로드용 단일 폴더·ZIP](exec-plans/evidence/ep060/report.md)도 제공하며 이동 후 오프라인 열람을 검증했다.

[EP-058](exec-plans/completed/EP-058-official-async.md)의 공식 관측 비동기 처리 교정과
오프라인·무유료8경기 검증·보고/viewer·봉인·정리를 완료했다. 정상 타이머 양보를 기다리며
실제 오류는 입력 생성 전에 차단한다. [한국어 보고](exec-plans/evidence/ep058/report.md).
현재 실행·감시는 없고 EX-045 수집 source·원자료·Blocked는 보존한다.

[EP-057](exec-plans/active/EP-057-official-lead.md)의 [EX-045](experiments/EX-045-official-lead.md) 공식 관측 B2 선봉 비교는 사전 검증·본 첫4 gate를 통과했으나 후속 수집에서 공식 추적기 처리 오류로 중단했다. 보고·감사·viewer·보존·정리는 완료했고 유효 경기/완료쌍 기준 미달로 비교 미완료·Blocked다. [최종 보고](exec-plans/evidence/ep057/final-report.md)를 참조한다. 현재 실행·감시 및 자동 재개는 없으며 시간 의존 추적기 오류는 수집 소스에 그대로 보존했다.

[EP-056](exec-plans/completed/EP-056-official-observation.md)의 공식 관측 B/B2 통합·검증·새 준비 기본값 전환을 완료했다. [한국어 보고서와 viewer](exec-plans/evidence/ep056/report.md)에100개 보존 결정·로컬2경기·회귀·지연/메모리·과거 보존을 연결한다. 현재 EP-056 실행·감시는 없고 유료 호출·과거 실험 재개0이다.

[EP-055](exec-plans/completed/EP-055-observation-tracker-comparison.md)의 Abyssal 1경기·플레이어별 관측 추적 진단을 완료했다. [보고서와 양측 viewer](exec-plans/evidence/ep055/report.md)에 공식 클라이언트 비교·Magic Bounce 재생·정보 출처 차이·검증 한계를 연결한다. 당시 legacy parser의 반사 기술·특성 누락 기록은 보존한다. 새 공식 B/B2 경로의 통합·교정은 EP-056을 따른다. 현재 EP-055 실행·감시는 없고 유료 호출·과거 실험 재개0이다.

[EP-054](exec-plans/active/EP-054-direct-corrected-lead.md)의 [EX-044](experiments/EX-044-direct-corrected-lead.md)은 사전 검사 생략 후 본실험을 실행했으나 반사 기술의 상대 보유 기술 오분류로 전체 중단했다. 비교 미완료(`Blocked`)이며 [최종 보고](exec-plans/evidence/ep054/final-report.md)에 원인·부분 결과·보존 근거를 연결한다. 현재 수집·감시 작업은 없다. 당시 입력 결함·중단을 보존하며 새 공식 관측 경로의 교정은 EP-056을 따른다. 과거 EX-043 중단·원자료도 보존한다.

[EP-051](exec-plans/completed/EP-051-court-change-input-audit.md)의 Court Change·추가 입력 오류 교정과 EX-042 전체 오프라인 감사를 완료했다. [최종 보고](exec-plans/evidence/ep051/report.md)와 [별도 사후 정정](exec-plans/evidence/ep051/impact.md)을 참조한다. 과거 비교 집계는 정상 입력 결과로 사용할 수 없다. EP-051에서는 본실험 계획을 보류했고 유료 호출·새 배틀 실험·과거 재개를 수행하지 않았다. 현재 별도 승인된 비교는 위 EX-043을 따른다.

[EP-050](exec-plans/completed/EP-050-lead-matchup-rules.md)의 선봉 전략·규칙 독립 개선·오프라인 검증·봉인·보고를 완료했다. [검증 보고](exec-plans/evidence/ep050/report.md)를 참조한다. 유료 호출·새 배틀 실험0이며 선봉 품질·승률·지연은 미평가다. 현재 실행 중인 EP-050 작업은 없다.

[EP-049](exec-plans/completed/EP-049-provider-retry-viewer.md)의 공급자 재시도 확대·EX-042 정상 경기 목록·회귀/로컬 검증·보존 확인을 완료했다. [검증 보고](exec-plans/evidence/ep049/report.md)와 [정상 경기 목록](../.pokechamp-data/experiments/ex042-cloud/index.html)을 참조한다. 외부 호출·실험 재개0이며 현재 실행 중인 EP-049 작업은 없다.

[EP-048](exec-plans/active/EP-048-distributed-lead.md)의 EX-042 공급자4+4 구현·검증·실제 수집·보고·보존·정리를 완료했다. 공급자 오류 및 COURT_CHANGE 계산 미지원에 따른 전체 중단으로 비교 완료 기준에 미달해 Blocked로 보존한다. 현재 실행·감시 중인 EX-042 작업은 없다. [최종 보고](exec-plans/evidence/ep048/final-report.md)와 [EX-042](experiments/EX-042-distributed-lead.md)를 참조한다.

[EP-047](exec-plans/completed/EP-047-transport-retry.md)의 새 응답 대기600초·연결 오류 재시도 기본값 구현·전체 회귀·공급자별 로컬 검증·정리를 완료했다. [검증 보고서](exec-plans/evidence/ep047/report.md)를 참조한다. 외부 호출·과거 실험 재개는 수행하지 않았다.

[EP-046](exec-plans/completed/EP-046-effect-reference.md)의 배틀·선봉 구조 설명 및 상세 효과 사전 구현·무유료 로컬 검증을 완료하고 새 준비 기본값을 적용했다. [검증 보고서](exec-plans/evidence/ep046/report.md)를 참조한다. 기존 실험의 버전·중단 상태를 보존하며 현재 실행 중인 EP-046 작업은 없다.

[EP-045](exec-plans/active/EP-045-zai-concurrency4.md)의 Z.ai 기본 동시성4 구현·로컬 검증과 EX-041 수집·보고·보존·정리를 완료했다. 통신 실패로 비교 완료 기준은 미달이며 `Blocked`로 보존한다. [최종 보고서](exec-plans/evidence/ep045/final-report.md)를 참조한다. 현재 실행·감시 중인 EX-041 작업은 없다. [EP-044](exec-plans/active/EP-044-b2-lead-zai.md)의 EX-040은 첫HTTP429에서 신규 수집을 중단했고 보고·보존·정리를 완료했다. [최종 보고서](exec-plans/evidence/ep044/final-report.md)를 참조하며 비교 미완료로 보존한다. 현재 실행·감시 중인 EX-039 작업은 없다. [EP-041](exec-plans/active/EP-041-b2-lead-comparison.md)은 사용자 지시로 coordinator·감시를 종료했고 비교 미완료 상태로 보존한다. [종료 기록](exec-plans/evidence/ep041/closure/report.md)과 [부분 보고서](exec-plans/evidence/ep041/held-report.md)를 참조한다. Z.ai 연결·환경 구성은 [EP-042](exec-plans/completed/EP-042-zai-provider.md)에서 구현·무API 검증을 완료했다. 사용자가 입력한 주소·키로 [EP-043](exec-plans/completed/EP-043-zai-connectivity-probe.md)의 단일 Z.ai probe가 성공했다. 실제 Z.ai 배틀 연결은 EP-044 첫 대응쌍에서 기술 검증했으며 정책 비교는 중단으로 미완료다.

실행 작업 및 아래 중단 plan의 scope 확인은 [exec-plan 색인](exec-plans/INDEX.md)을 따른다.
아래 목록은 보존된 미완료 상태이며 실험 재개나 추가 검토의 지시가 아니다.

<a id="blocked-work"></a>

## 중단 상태와 해석 제한

모든 행의 plan 상태는 **Blocked**다. 중단 처리·보고·보존 완료와 실험 목표 달성을 구분한다.
원자료·실패/무효 판정·미검토 및 누락 분모는 각 기록에 보존한다.

| Plan / 실험 | 보존할 현재 판정·미충족 기준 |
|---|---|
| [EP-075](exec-plans/active/EP-075-jev-v3-abyssal32.md) / [EX-053](experiments/EX-053-jev-v3-abyssal32.md) | 첫 경기 HTTP503 중단·유효0/32·완료0/16쌍. 성적 비교 미완료, 감사·보고·뷰어·봉인·정리 완료. |
| [EP-064](exec-plans/active/EP-064-jev-repeat.md) / [EX-048](experiments/EX-048-jev-repeat.md) | 첫 경기 JEV 승리, 두 번째 선택/최댓값 검사 중단·정상완료1/2. 감사·보고·봉인·정리 완료. |
| [EP-062](exec-plans/active/EP-062-jev-battle.md) / [EX-047](experiments/EX-047-jev-battle.md) | 확률합0.99 검증 중단·정상완료0/2. 구현/로컬 검증·보고·원문/봉인·정리 완료. |
| [EP-057](exec-plans/active/EP-057-official-lead.md) / [EX-045](experiments/EX-045-official-lead.md) | 공식 추적기 처리 오류 전체 중단. 보고·감사·보존·정리 완료, 유효 경기/완료쌍 기준 미달·비교 미완료. |
| [EP-048](exec-plans/active/EP-048-distributed-lead.md) / [EX-042](experiments/EX-042-distributed-lead.md) | 공급자4+4 구현·검증·수집·보고·정리 완료. 공급자 오류 및 계산 미지원 중단으로 유효 경기·완료쌍 기준 미달·비교 미완료. |
| [EP-045](exec-plans/active/EP-045-zai-concurrency4.md) / [EX-041](experiments/EX-041-b2-lead-zai4.md) | Z.ai 기본4 구현·수집·보고·정리 완료. 통신 실패로 유효 경기·완료쌍 기준 미달·비교 미완료. |
| [EP-044](exec-plans/active/EP-044-b2-lead-zai.md) / [EX-040](experiments/EX-040-b2-lead-zai.md) | 첫HTTP429 중단·비교 미완료. 부분 보고·기존 자료 보존·정리 완료. |
| [EP-035](exec-plans/active/EP-035-ab-head-to-head32-b2.md) / [EX-038](experiments/EX-038-ab-head-to-head32-b2.md) | 입력 parser 결함으로 수집 중단·비교 미완료. 사용자 지시로 설명검토 조기 종료, 미검토 응답·전수 prefix 재계산 미완료 보존. 보고·보존·정리 완료. |
| [EP-032](exec-plans/active/EP-032-ab-head-to-head32-protectfix.md) / [EX-037](experiments/EX-037-ab-head-to-head32-protectfix.md) | provider timeout으로 유효 경기·완료쌍 기준 미충족. 수집분 검토·보고·보존·정리 완료, 비교 미완료. |
| [EP-030](exec-plans/active/EP-030-ab-head-to-head32.md) / [EX-036](experiments/EX-036-ab-head-to-head32.md) | PROTECT 계산 실패로 전체 수집 중단·직접비교 미완료. 수집분 검토·보고·보존·정리 완료. |
| [EP-020](exec-plans/active/EP-020-battle-guide-live.md) / [EX-027](experiments/EX-027-battle-guide-live.md) | Cloud 출력 계약 실패로 중단. smoke/본 비교 미실행. 중단 보고·정리 완료, 비교 미완료. |
| [EP-018](exec-plans/active/EP-018-io-battle-only.md) / [EX-026](experiments/EX-026-io-battle-only.md) | Cloud 출력·시점·계산 근거 gate 실패. 모델 오류이며 입력·처치·수집 무효 판정은 아님. 배틀 미실행, 중단 보고·정리 완료. |
| [EP-015](exec-plans/active/EP-015-summary-max-diagnostic.md) / [EX-025](experiments/EX-025-summary-max-diagnostic.md) | 통합 입력의 최초 HP 누락과 평가 요구 불일치로 전체 무효. 무효 검토 초안·미검토 응답 보존, 유효 비교 없음. |
| [EP-011](exec-plans/active/EP-011-improved-io.md) / [EX-024](experiments/EX-024-low-summary-prompt-reexperiment.md) | low 요약 지시 gate 실패·본 비교 미실행. EX-020/023/024 개별 halt·최초 시계와 EX-020 미확정 응답/token 보존. |
| [EP-013](exec-plans/active/EP-013-state-summary-thinking.md) / [EX-022](experiments/EX-022-state-summary-thinking.md) | 공개 특성 입력 모순으로 비교 무효·검토 미완료. 후속 교정이 과거 입력을 유효화하지 않음. |
| [EP-012](exec-plans/active/EP-012-summary-harness-diagnostics.md) / [EX-021](experiments/EX-021-summary-harness-diagnostics.md) | weather 입력/기준 오류로 전체 비교 무효·검토 미완료. |

<a id="current-capabilities"></a>

## 현재 기능과 검증 근거

검증은 각 보고서의 source·조건·범위에 한정된다. 코드 교정 완료가 과거 중단 실험의 재개,
유효화나 전체 효능 검증을 뜻하지 않는다. 상세 검사·명령·봉인 목록은 보고서에서 읽는다.

| 현재 기능·기본값 | 검증·범위 근거 |
|---|---|
| JEV 새 기본 v3·기본 지식 원문·요청별 효과 사전·PP 출처는 외부 감사 | [EP-074 보고](exec-plans/evidence/ep074/report.md), [C-045](CONTRACTS.md#c-045-jev-battle). 과거 v1/v2 재현·저장 입력 전수 대조·성능 미평가. |
| 공식 관측 비동기 완료 경계·요청 전체30초·실패 폐쇄 | [EP-058 보고](exec-plans/evidence/ep058/report.md), [D-068](decisions/D-068-official-async.md)/C-043. 실제 타이머·전수 재생·8경기/16actor·HTTP4+4 검증. EX-045 중단은 유지. |
| 새 B/B2 공식 관측 기본값·v1.4.0/B2 b2-official-v1 | [EP-056 보고](exec-plans/evidence/ep056/report.md), [C-043](CONTRACTS.md#c-043-official-observation). actor/행 경계·단일 관측→계산→전송/슬롯·빌드/오류 중단·과거 호환 검증. 효능 미평가. |
| Court Change 실행 알림·진영 이력, 공개 상태이상 특성 보유자·기절 후 타입 교정 | [EP-051 보고](exec-plans/evidence/ep051/report.md), [C-023](CONTRACTS.md#c-023--계산기-입력-로컬-조사수정-경계). EX-042 전수·지정 독립 사례 검증 완료. |
| 새 선봉 matchup-v2/dex-v2 기본값·네 조합 독립 선택 | [EP-050 보고](exec-plans/evidence/ep050/report.md), [C-040](CONTRACTS.md#c-040-lead-components). 공개 cutoff·자기 슬롯·RNG·후속 B2·과거 봉인 보존; 품질/효능 미평가. |
| EX-042 공급자4+4 큐·독립 permit·공유 무제한 원장/시계/중단 | [EP-048 구현](exec-plans/evidence/ep048/implementation-report.md)·[실제 감사](exec-plans/evidence/ep048/final-audit-v2.json), [C-039](CONTRACTS.md#c-039-distributed-lead). 실제 최대4+4 확인, 선봉 비교는 미완료. |
| 새 Z.ai/Ollama 읽기600초·연결/timeout/5xx/429 최대3재시도·1/2/4초 | [EP-049 보고](exec-plans/evidence/ep049/report.md), [C-038](CONTRACTS.md#c-038-transport-retry). 최종429 신규 수집 중단·원장/기한/permit·과거 v1/legacy 호환·로컬 검증 완료. |
| 새 B/B2·LLM 선봉 구조 설명·요청별 Gen9 상세 효과 사전 기본값 | [EP-046 보고](exec-plans/evidence/ep046/report.md), [C-037](CONTRACTS.md#c-037-effect-reference). 과거 EX/봉인 호환·전수 입력/로컬 검증 완료. 일반 게임 지식 추가이며 승률·지연 효능은 미평가. |
| 명시적 Ollama/Z.ai 선택, 로컬 Z.ai 기본값·공급자 설정 봉인 | [EP-042 보고](exec-plans/evidence/ep042/report.md), [C-034](CONTRACTS.md#c-034-provider). 구현 검증은 API0; 이후 [EP-043](exec-plans/completed/EP-043-zai-connectivity-probe.md) 단일 실제 연결 성공. [EX-040](experiments/EX-040-b2-lead-zai.md) 첫 대응쌍 배틀 기술 검증·비교 미완료. |
| Pinned 환경, loopback Showdown, 분리된 qualification/research bundle·source seal | [EP-001](exec-plans/completed/EP-001-pokechamp-reproducible-environment.md), [EP-002](exec-plans/completed/EP-002-pokechamp-battle-observability.md). Technical qualification은 efficacy evidence가 아님. |
| 새 B prepare 버전·과거 호환 | [현재 경로·버전 근거](ARCHITECTURE.md#battle-input). D-031/EP-019는 당시 설명서 구현 기록. |
| 계산기 입력·기술명·Protect 만료 교정 | [EP-023 보고](exec-plans/evidence/ep023/report.md)·[영향 분석](exec-plans/evidence/ep023/impact.md), [EP-025](exec-plans/evidence/ep025/report.md), [EP-031](exec-plans/evidence/ep031/protect-expiry-v1/report.md). |
| 지연 기술 대상 슬롯 교정 및 Doom Desire 시작 표기 | [EP-036 보고](exec-plans/evidence/ep036/report.md). 실패 재현·교정과 기존 정상 parser 상태 보존 검증. 전수 계산 재생 완료는 아님. |
| 새 Cloud 동시성: Z.ai 기본4·Ollama 기본8·과거 호환 | [EP-045 구현 검증](exec-plans/evidence/ep045/implementation-report.md)·[실제 최대 동시성4 감사](exec-plans/evidence/ep045/concurrency-audit.json), [C-036](CONTRACTS.md#c-036-zai4). 기존 정책 hash·과거 run 조건 유지. |
| B0 보존 및 B1–B3 오프라인 전달 표현; C-031/033의 별도 B2 전송 경로 | [EP-034 보고](exec-plans/evidence/ep034/report.md), [EX-038](experiments/EX-038-ab-head-to-head32-b2.md). 문자 감소는 판단력·승률·지연 개선의 검증이 아님. |
| B2 actor별 seeded_random 기본·llm_lead 선봉 opt-in, 무호출 준비/검증 | [EP-040 보고](exec-plans/evidence/ep040/report.md), [C-033](CONTRACTS.md#c-033-llm-lead). 로컬 fake/Showdown 및 [EX-041 실제 Z.ai 기술 검증](exec-plans/evidence/ep045/final-audit.json) 완료; 선봉 성능 비교는 완료 기준 미달. |
| 새 viewer 턴 탭·호출별 원문/reasoning 기본 표시 | [EP-037 보고](exec-plans/evidence/ep037/report.md). 기존 viewer 재생성 없음. |
| EX-042 당시 정상 완료26개·52 actor viewer 목록/필터 | [EP-049 보고](exec-plans/evidence/ep049/report.md). 기존 source/derived viewer 보존, 브라우저·모바일·목록 복귀 검증 완료. 당시 종료 기준 목록이며 [사후 입력 자격](exec-plans/evidence/ep051/impact.md)과 구분한다. |
| 새 기본 IO 테스트는 별도 사용자 지시 없으면 설명 오류 사후 검토·기입 제외 | [연구 설계 §8.1](RESEARCH_DESIGN.md#io-explanation-review), [C-032](CONTRACTS.md#c-032-io-explanation-review). 기술적 IO 검증·원문/reasoning 보존·표시 유지, 미검토는 미평가. |

<a id="open-limits"></a>

## 남은 제한과 확인 필요 사항

- 기존 Qwen 준비 코드의 EP132 경로 불일치는 알려진 후속 항목이다. 이번 분리에서
  고정 출력 상수·실행기를 수정하거나 해당 실행을 재개하지 않는다.

- EX-060은 단일 대진의 고유 관측22개이며 후보 간 q 차이가 관측된 상태는11개다.
  고정 숨은 상태·양측 Abyssal 후속 정책 조건의 자료로, 일반 성능·확정 최선·독립 자료의 학습 효과는
  미평가다. 동일 자료 개발 적합은 [EX-061 보고](exec-plans/evidence/ep102/report.md) 범위에서 확인했다.
  원대진은 개발용으로 독립 평가에서 제외한다. [수집 근거](exec-plans/evidence/ep101/report.md).
- Court Change 교정은 공개 protocol로 실행 알림이 입증된 경우에 한정된다. 근거 없는 효과 제거·미지원 활성 효과 허용은 하지 않는다. 지정 사례 밖 Gen9 OU 전체 정확성은 미검증이다. EX-042 입력 무효 및 의존 비교 제한은 [별도 정정](exec-plans/evidence/ep051/impact.md)을 따른다.
- L1-L5 효능 설계의 미정 항목은 [연구 설계](RESEARCH_DESIGN.md)의 open questions를 따른다.
  운영 결과를 전체 L1-L5 효능, 정상 minimax 성능, 계산기·압축의 단독 인과 효과로 확대하지 않는다.
- EX-032의 공유 permit 반환 실패는 미수정이며 실제 지연 원인은 미확정이다.
  [EX-032 조사](exec-plans/evidence/ep026/report.md), [현재 permit 경계](ARCHITECTURE.md#execution-boundaries).
  EX-033 정상 완료는 과거 외부 RAM 원인의 독립 입증이나 해당 ACK 경계 제거가 아니다.
- 기준선의 fallback·실패 제외와 엄격한 출력 정책에서의 불완전 수집은
  [EX-002](experiments/EX-002-pokechamp-baseline-pilot.md), [EX-003](experiments/EX-003-core-smoke-timing.md),
  [EX-015](experiments/EX-015-action-candidate-validation.md), [EX-016](experiments/EX-016-upstream-fallback.md)에 보존한다.
  서로 다른 source·정책의 정상 완료를 과거 조건의 자격으로 소급하지 않는다.
- 2026-09-04 `npm ci` audit의31 vulnerabilities는 당시 관측이다. 현재 dependency 재평가는 수행하지 않았다.
  외부 노출·production 사용 전 별도 dependency/security decision 필요성은 유지한다.
- 상시 Charter owner/approver 지정은 [CHARTER](CHARTER.md)의 TBD다.
  Legacy documentation 불일치는 새 backlog가 아니며 승인된 작업이 의존할 때만 조사한다.

<a id="next-steps"></a>

## 다음 단계

후속 연구는 기존 결과를 근거로 다음 학습·정책 개선·독립 평가의 범위를 정한다.
새 실험은 모델·자료/분할·방법·평가·예산·중단 조건과 새 ID를 먼저 명시하고 기존 CLI의
명시적 출력 인자로 보존 루트의 `runs/model-training/<새 실험 ID>`를 선택한다.
출력 선택이 없는 과거 실행기는 새 실험용으로 자동 재사용하지 않는다.
기존 평가 holdout·원자료·고정 절대경로를 유지하며 C-047 뷰어 완료 절차도 해당 실험에 적용한다.
구체적 사용·복원은 [공통 안내](RESEARCH_WORKFLOW.md)를 따른다.

중단 실험의 남은 예산은 재수집 허가가 아니다. 추가 실험·처치·방법 변경은 새 명시적
지시와 관련 authority/plan의 범위에서 다루며, 과거 실패·무효·미완료와 검토 종료 상태를 유지한다.
