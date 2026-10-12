# EX-076 — 고정 A/B 공개 상태 MCTS 정책 학습

- 상태: Incomplete — 교정 후 기술 검증/측정 통과, 평가 예산 gate 초과로 학습/test 보류
- 결정: [D-119](../decisions/D-119-fixed-matchup-mcts.md), 실행 [D-120](../decisions/D-120-fixed-matchup-run.md)
- 구현: [EP-124](../exec-plans/completed/EP-124-fixed-matchup-mcts.md), C-060

## 질문·조건·해석

고정 두 팀, 양측 세트·현재 상태 공개에서 작은 정책/상태가치 모델의 자기대국·MCTS 학습이
탐색 없는 초기 정책보다 개선되는지 검증한다. 일반 비공개 Gen9 OU·Qwen·L1-L5 효능은 평가하지 않는다.
6대6·선봉·교체·Tera·도구·특성·원래 확률 효과를 포함한다. 실제 상대 선택/미실행 행동/미래 RNG는 비공개다.
정확한 HP/PP/능력치/현재 효과 카운터는 명시적인 추가 공개다.

| 팀 | 원본 파일 | SHA-256 |
|---|---|---|
| A | team_2559.gen9ou_team | 663d9af22c71aa7fdaf2957c5f691c96462bc0b6b53137bc68ede6222e27a979 |
| B | team_27147.gen9ou_team | 6b79e8aa8b43170b234d2ac91fc0fe30dc7bfc572bccdec2004153889190826d |

원본은 `/tmp/metamon_cache/teams/modern_replays/gen9ou`에 있으며 검토108종 목록과 해시를 확인한다.
로컬 gen9ou validator 통과만 확인했고 대진 균형·길이·학습 가능성은 미측정이다.

## 동결 학습·탐색

4층 Transformer, hidden128/head4/FFN512/dropout0. typed 구조화 상태·후보 정책과 tanh 상태가치.
초기 무작위 P0, 과거 자료/가중치/상대 혼합0. 라운드32경기·최대32라운드, 같은 snapshot 양측·진영 절반 교대.
최근8라운드/100000결정 replay, CE(주변 방문 분포)+MSE(정상 종료 ±1/0).
AdamW lr3e-4/weight_decay1e-4/clip1/batch256, 라운드당 최대2epoch/64step.
4라운드마다 별도 dev64경기 P0 대결, 탐색 없는 평균 점수 최대(동률 앞 checkpoint)로 선택.

양측 Exp3 prior 초기화, gamma0.1/eta0.05, 실제 양측 이번 선택을 보기 전에 독립 표본화.
공동 행동 이후 확률 전이, 새 탐색 RNG. 최대32결정 깊이/64simulations, 루트 재사용0.
가치는 양측 예측 차이/2로 반대칭화, 주변 방문 분포를 타깃·temperature1 실제 선택에 사용.
자동 행동의 정책 손실0. 실패/검열 경기 결과 타깃0. 중간 보상/PPO/BC/별도 보정0.

## 평가·판정

P0/P0+S/P1/P1+S 각128경기(32seed블록×A/B×p1/p2), 동결 abyssal-tera-v1 상대, 총512경기.
상대는 학습/pilot/dev에 사용하지 않는다. 기존 관측 경계를 유지하며 공개 상태 정책과 정보량이 다름을 보고한다.
P1 대 P0 직접128경기 추가, test640경기. 모든 sampling T1, S는64simulations 고정.
모델·상대·탐색량·규칙·sampling과 seed 목록은 test 전에 잠근다.
train/pilot/dev/test 및 경기/행동/탐색 RNG namespace 격리. 평가로 설정을 변경하지 않는다.
주지표는 고정 상대 P1−P0 점수차(승1/무0.5/패0), A/B·진영 같은 비중.
seed블록 대응 bootstrap10000회, 95% 구간 하한>0과 점추정>0이 정책 개선 성공.
P1+S−P1·P0+S−P0·P1+S−P0+S와 직접 대결은 별도 보고한다. 자기대국50%는 지표가 아니다.
한 학습 seed이며 일반 학습 재현성·팀 전력 동등성은 주장하지 않는다.

## 예산·단계·gate

동결 실험 검증 첫 시각부터12시간/1GPU. 단계 상한1/1/6/3/1시간(정확성/pilot/학습/test/최종화),
남는 시간을 학습 연장에 전용하지 않는다. 개발/일반 합성 검사는 실험 밖이며 실행 승인과 구분한다.
RAM48GiB/GPU40GiB/새 디스크50GiB. worker8/16·batch16/32/64·대기5ms 후보를 측정해
상한 내 처리량 최대(동률 작은 조합)를 동결. 32/64/128simulations 비용 측정, 본실험64 유지.
pilot은 균등 무작위32+P0자기대국32 이내. 각 묶음 팀A 점수0.1~0.9 밖 또는300턴 검열>5%면 학습 보류.
2배 여유를 적용한 test640경기 예상시간>3시간이면 학습 보류. 비용·성공은 측정 전 확정하지 않는다.
학습은32경기×32라운드 상한과6시간 중 먼저 도달하는 조건으로 중단한다.

## 실패·복구·완료

RD11.1/C-018 적용. 영향 단계 중지·증거 보존·기술 교정은 허용하되 자동 재경기/대체/재수집0.
예약된 미완료 경기와 실패를 정상 결과로 변환하지 않는다. 같은 source/manifest/checkpoint/최초 시계의
완료 단위 재개만 허용하며 실행 도중 source를 바꾸면 새 검증/명시적 판단이 필요하다.
공급자 판단 오류는 경기 실패로 격리한다. 공유 정보 경계/비유한값/무결성 위반은 의존 단계 중단이다.
실험 전체 성공은 기술 gate·정책 개선·test640완료·원자료 감사·뷰어·봉인·자원 반환을 모두 요구한다.
정상경기 전수 export/원자료 연결 감사, 단계·조건별 첫/마지막 최대12경기 오프라인 브라우저 표본 검증.
층 `(stage, condition)`과 경기 `slot_id` 정렬로 각 층의 첫 경기를 먼저 선택하고,
각 층의 마지막 경기를 중복 없이 추가하여12개 상한을 지킨다.
이는 이번 명시적 표본 조건이며 브라우저 전수 검증으로 표시하지 않는다.
성공 후 관측 제한→비공개 belief→팀/상대 확대는 별도 설계이며 자동 실행하지 않는다.

## 실행·결과

[EP-125](../exec-plans/active/EP-125-fixed-matchup-run.md)에서 실행한다.
원자료는 `.pokechamp-data/experiments/ex076-fixed-matchup-mcts/`에 동결한다.
실행 중의 진행·검증은 EP-125, 최종 판정은 실행 디렉터리의 보고서에 연결한다.
개발 검사 통과는 실험 gate/효능 증거가 아니다.

[EP-125 중단·교정 보고](../exec-plans/evidence/ep125/report.md): uniform32 정상, benchmark8 미확정,
학습0/test0. CPU40·수정본 GPU 독립 검증 통과. 원32경기 감사/뷰어·봉인·GPU 반환 완료.
원source·실패를 보존하며 자동 재측정은 하지 않았다.

## 승인된 교정 재개

[D-121](../decisions/D-121-fixed-matchup-fnt-recovery.md)으로 수정본에서 실패8probe를1회 재측정한다.
원32경기/P0/실패와 최초12시간 시계를 유지한다. 단계 예산은 중단 전 집행량을 차감하며
검증에는 원 시작부터 수정본 GPU 검증 반환까지를 전부 차감한다. 대기·교정은 전체 벽시계에 포함한다.
이 예외는 해당 복구에만 적용하며 다른 자동 재시도/재수집은0이다.
새 경로는 `.pokechamp-data/experiments/ex076-fixed-matchup-mcts-fnt-v2/`이다.

## 교정 재개 최종 결과

수정본 GPU 검증과 benchmark128이 모두 통과했다. worker16/batch64를 선택했으나
P0 pilot16의 진행시간에서 사전 test 예측식의 하한6.97시간>3시간이 확정되어 중단했다.
P0 미완료16·미실행16, 학습/dev/test0. 정상uniform32(기존 계승)와 중단16을 구분해 감사/export,
브라우저2표본·봉인·GPU 반환을 완료했다. [최종 보고](../exec-plans/evidence/ep125/budget-report.md).
미완료 경기 승패·정책 개선은 미평가이며 자동 추가 실행하지 않는다.
