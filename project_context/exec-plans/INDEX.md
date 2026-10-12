# 실행 계획 색인 (Execution Plan Index)

Exec plan은 하나의 bounded implementation 또는 experiment 목표를 관리한다. 무엇을 변경할 수
있는지, 무엇이 계속 참이어야 하는지, 완료를 어떻게 판단하는지, 어떤 evidence로 작업을
종결하는지를 설명한다.

Decision [`D-002`](../decisions/D-002-reset-research-direction.md)보다 앞선 plan과 이 directory
밖의 모든 plan은 legacy evidence이며 자동 migration 또는 continuation 대상이 아니다. 새 연구
plan은 새 ID와 사용자가 명시적으로 승인한 목표로 시작한다.

이 파일의 표는 navigation용 summary다. Plan의 scope, status, acceptance criterion,
verification에 대한 source of truth는 각 개별 plan이다. `active/` 안의 index가 아닌
`EP-XXX-*.md` 파일만 active EXEC PLAN authority를 가질 수 있다.

## Active plan 목록

아래 구분은 탐색용이다. 중단 plan의 status·파일 위치·authority·완료 기준은 바꾸지 않는다.
`active/`의 scope가 겹치는 plan 확인 요건은 [상위 INDEX](../INDEX.md#active-work)를 따른다.

<a id="running-plans"></a>

### 실행 중

| ID | Plan | Status | 현재 objective | 최종 갱신일 |
|---|---|---|---|---|
| [EP-134](active/EP-134-jev27b-ex058-reproduction.md) | JEV-27B 동일32 재현 | Blocked | GPU 한도 중단·목표 미달 · [후속 교훈](evidence/ep134-lessons/report.md) | 2026-10-08 |
| [EP-127](active/EP-127-fixed-matchup-first-round.md) | 첫1라운드 학습 | Blocked | 원실행 시간초과·학습0·후속 시간상한 해제 | 2026-10-07 |
| [EP-126](active/EP-126-fixed-matchup-day.md) | 하루 내 고정 대진 실행 | Paused | 사용자 중지·학습/test0·자료 보존/정리 완료 | 2026-10-07 |
| [EP-041](active/EP-041-b2-lead-comparison.md) | B2 선봉 정책 비교 | Blocked | 사용자 지시로 실행·감시 종료·비교 미완료 | 2026-09-14 |

<a id="blocked-plans"></a>

### 중단 보존

실험 재개 지시가 아니다. 보고·보존·정리 완료를 실험 목표 달성으로 바꾸지 않는다.

| ID | Plan | Status | 현재 objective | 최종 갱신일 |
|---|---|---|---|---|
| [EP-125](active/EP-125-fixed-matchup-run.md) | 고정 대진 GPU 실험 | Blocked | 교정·측정 통과, 예산 gate 초과·학습/test0·보고/뷰어/자원 정리 완료 | 2026-10-07 |
| [EP-119](active/EP-119-abyssal-rl.md) | Abyssal 4GPU 학습 | Blocked | test·감사 종료, 최종 뷰어 timeout·실험 미완료·자원 해제 | 2026-10-04 |
| [EP-108](active/EP-108-joint-q-training.md) | Base 공동 q 학습 | Blocked | 재로딩 q 차이 gate 실패·자료 보존·GPU 점유0 | 2026-10-03 |
| [EP-103](active/EP-103-qwen-local-battle.md) | Qwen 로컬 서빙·배틀 | Blocked | GPU 대조 완료·배틀 입력 전 cwd 오류 중단·교정/정리 완료 | 2026-09-28 |
| [EP-075](active/EP-075-jev-v3-abyssal32.md) | JEV v3 동일32 | Blocked | 실험 미완료·보고/정리 보존 | 2026-09-21 |
| [EP-077](active/EP-077-jev-v3-retry32.md) | JEV v3 동일32 | Blocked | 실험 미완료·보고/정리 보존 | 2026-09-21 |
| [EP-080](active/EP-080-jev-direct32.md) | JEV v3 동일32 | Blocked | 실험 미완료·보고/정리 보존 | 2026-09-21 |
| [EP-064](active/EP-064-jev-repeat.md) | JEV 수정본2경기 | Blocked | 첫 경기 승리·두 번째 최댓값 검사 중단·보고/정리 완료 | 2026-09-21 |
| [EP-062](active/EP-062-jev-battle.md) | JEV Choice 배틀 진단 | Blocked | 확률합 검증 중단·완주 미완료·보고/정리 완료 | 2026-09-21 |
| [EP-057](active/EP-057-official-lead.md) | 공식 관측 B2 선봉 본실험 | Blocked | 추적기 처리 오류 중단·보고/정리 완료·비교 미완료 | 2026-09-17 |
| [EP-054](active/EP-054-direct-corrected-lead.md) | 교정 선봉 직접 본실험 | Blocked | 입력 결함 중단·비교 미완료·보고 보존 | 2026-09-16 |
| [EP-053](active/EP-053-corrected-lead.md) | 교정 B2 개선 선봉 비교 | Blocked | 실행 설정 오류로 중단·비교 미완료·보고 보존 완료 | 2026-09-16 |
| [EP-048](active/EP-048-distributed-lead.md) | 공급자4+4 선봉 비교 | Blocked | 구현·보고/정리 완료·비교 기준 미달 | 2026-09-16 |
| [EP-045](active/EP-045-zai-concurrency4.md) | Z.ai 기본4·재실험 | Blocked | 기본4 구현·보고/정리 완료·비교 기준 미달 | 2026-09-15 |
| [EP-044](active/EP-044-b2-lead-zai.md) | Z.ai B2 선봉 정책32 | Blocked | 첫429 중단·보고/정리 완료·비교 미완료 | 2026-09-15 |
| [EP-035](active/EP-035-ab-head-to-head32-b2.md) | B2 직접대결32 | Blocked | 입력 parser 중단·설명검토 조기종료; 비교 미완료 | 2026-09-14 |
| [EP-032](active/EP-032-ab-head-to-head32-protectfix.md) | Protect 수정본 A/B32 | Blocked | provider timeout·유효/완료쌍 기준 미달; 비교 미완료 | 2026-09-11 |
| [EP-030](active/EP-030-ab-head-to-head32.md) | A/B 직접대결32 | Blocked | PROTECT 계산 실패·수집 중단; 직접비교 미완료 | 2026-09-11 |
| [EP-020](active/EP-020-battle-guide-live.md) | 필드 설명서 실제 Cloud 병렬 배틀 | Blocked | Cloud 기술 gate 실패; 배틀 미실행 | 2026-09-09 |
| [EP-018](active/EP-018-io-battle-only.md) | 요약 없는 improved_io A/B 비교 | Blocked | Cloud 출력/의미 gate 실패; 배틀 미실행 | 2026-09-09 |
| [EP-011](active/EP-011-improved-io.md) | IO 개선 및 병렬 3조건 비교 | Blocked | 요약 gate 실패·승인된 버전 소진; 비교 미실행 | 2026-09-08 |
| [EP-012](active/EP-012-summary-harness-diagnostics.md) | 요약 harness 기여도 진단 | Blocked | weather 입력/기준 오류·전체 비교 무효; 검토 미완료 | 2026-09-08 |
| [EP-013](active/EP-013-state-summary-thinking.md) | 상태 정비와 요약 thinking 비교 | Blocked | 공개 특성 입력 모순·비교 무효; 검토 미완료 | 2026-09-08 |
| [EP-015](active/EP-015-summary-max-diagnostic.md) | 요약 thinking low/max 진단 | Blocked | 입력/평가 불일치·전체 무효; 검토 미완료 | 2026-09-08 |

## Completed plan 목록

상태는 모두 `Completed`이며 이는 각 plan의 승인된 완료 기준에 대한 판정이다.
중단 포함 완료·성능 비교 미완료는 아래 결과에 그대로 표시한다. 검사·봉인·보존 통계와
상세 결과는 각 plan의 검증·증거를 읽고, 색인에서 반복 갱신하지 않는다.

| ID / 개별 검증 근거 | 완료일 | Outcome |
|---|---|---|
| [EP-135](completed/EP-135-research-branch-preservation.md) | 2026-10-12 | 동일 코드 두 연구선·고정 태그·외부 자산 복사/검증·기존 환경 유지 |
| [EP-132](completed/EP-132-qwen-matrix-selfplay.md) | 2026-10-09 | 시도3 40라운드 둔화 종료·36 선택·시험640/감사/뷰어/봉인·정리 완료; 주효능 미입증(직접 0.805) |
| [EP-133](completed/EP-133-joint-q-battle.md) | 2026-10-08 | GPU0 재현·실제20경기·감사/정정/뷰어/봉인·자원 정리 완료 |
| [EP-131](completed/EP-131-fixed-matchup-stopping.md) | 2026-10-07 | 32라운드 종료·최고24 선택·시험/감사/뷰어/봉인·정리 완료; 주효능 미달 |
| [EP-130](completed/EP-130-first-round-model-comparison.md) | 2026-10-07 | 첫라운드 전후 동일5436관측 분석·행동/가치 변화 확인·승률 미평가 |
| [EP-129](completed/EP-129-first-round-single-retry.md) | 2026-10-07 | 정상31 계승·실패1 정상 재수집·첫라운드 학습/감사/뷰어/봉인·정리 완료 |
| [EP-128](completed/EP-128-fixed-matchup-no-time-limit.md) | 2026-10-07 | 현재1라운드 시간 상한 해제·CPU94검사·원실행 보존, 새 실행0 |
| [EP-124](completed/EP-124-fixed-matchup-mcts.md) | 2026-10-07 | 고정 공개 상태 MCTS·전용 모델·실행/재개·감사/뷰어 구현·CPU 검증 완료; 실험 미실행 |
| [EP-123](completed/EP-123-life-orb-input.md) | 2026-10-07 | Life Orb 반동 공개 입력 교정·CPU 회귀·원본 보존 검증 |
| [EP-122](completed/EP-122-abyssal-rl-next.md) | 2026-10-06 | EX-075 추가 학습·평가·감사·뷰어·봉인·정리 완료; 개선 미입증·목표 미달 |
| [EP-121](completed/EP-121-abyssal-rl-continue.md) | 2026-10-06 | EX-074 추가 학습·평가·감사·뷰어·봉인·정리 완료; 출발 대비 개선·목표 미달 |
| [EP-120](completed/EP-120-abyssal-preflight-recovery.md) | 2026-10-03 | EX-073 결정적 backend 독립 검증·원 시계/source 보존 복구 도구 |
| [EP-118](completed/EP-118-abyssal-first-objective.md) | 2026-10-03 | Abyssal 효율적 승리 우선 목표·미정 조건·문서 정합성 검증 |
| [EP-117](completed/EP-117-selfplay-finalization-recovery.md) | 2026-10-02 | 원본 보존·의존성/정수 표시 교정·전수 오프라인 뷰어·정정 최종화 완료 |
| [EP-116](completed/EP-116-selfplay-rlcd.md) | 2026-10-02 | 단일 GPU 자기대국·보정 판단·잠긴 test·보고/뷰어/봉인·자원 정리 완료; 개선 미입증 |
| [EP-115](completed/EP-115-qwen-replay-imitation.md) | 2026-10-02 | 첫 모방 학습·잠긴 test·40경기·전수 감사/뷰어·소유 자원 정리 완료; 배틀 개선 불확실 |
| [EP-114](completed/EP-114-imitation-self-play-objectives.md) | 2026-10-01 | Qwen 모방 학습·자기대국 단기 목표·문서 정합성 검증 완료 |
| [EP-113](completed/EP-113-kev-continuation-question.md) | 2026-10-01 | 후속 질문 프로필·CPU 검증·동일1경기 진단/감사·뷰어·봉인/정리 완료 |
| [EP-112](completed/EP-112-kev-test-battles.md) | 2026-10-01 | 기존 test20 본 평가·전수 감사/독립 집계·뷰어·봉인·GPU3 정리 완료 |
| [EP-111](completed/EP-111-kev-battle.md) | 2026-10-01 | Kev 입력·dev 재현·1경기 전수 감사/뷰어/봉인·GPU3 정리 완료·성능 미평가 |
| [EP-110](completed/EP-110-abyssal-tera-joint-q.md) | 2026-10-01 | Tera 정책·80경기 보완 수집·감사/뷰어·봉인/학습 자료 복사 검증 완료 |
| [EP-109](completed/EP-109-astra-subagent-guidance.md) | 2026-09-30 | Astra 위임 조건·파일 조율·통합 검증 책임 명시 |
| [EP-107](completed/EP-107-joint-q-data.md) | 2026-09-30 | 80경기 공동 q 수집·전수 감사·봉인·학습 자료 복사/검증 완료 |
| [EP-106](completed/EP-106-qwen-candidate-state.md) | 2026-09-29 | 후보 상태·결정별 지침·3조건 개발 비교/보존 완료·판단 개선 미입증 |
| [EP-105](completed/EP-105-viewer-action-names.md) | 2026-09-29 | 현재/향후 뷰어 실제 행동 이름·오프라인 검증·원자료/버전 보존 완료 |
| [EP-104](completed/EP-104-qwen-training-matchup.md) | 2026-09-29 | 학습 원대진 정상1/1·12턴 패배·정정 전수 감사/뷰어/정리 완료 |
| [EP-102](completed/EP-102-qwen-action-value.md) | 2026-09-28 | Qwen3.5-4B LoRA·재로딩 검증 완료·개발 MSE 기준 충족·독립 배틀 미평가 |
| [EP-101](completed/EP-101-single-battle-branch-rollouts.md) | 2026-09-28 | EX-058 한 경기22상태·167행동·5,344분기 수집·감사·뷰어·봉인 완료 |
| [EP-100](completed/EP-100-replay-rule-eligibility.md) | 2026-09-28 | 로컬 Gen9 OU 리플레이 규칙 분류·108종 독립 판정·전수 감사 완료 |
| [EP-099](completed/EP-099-pokemon-training-objective.md) | 2026-09-28 | 세 RLCD 환경 기반 포켓몬 전용 학습 당면 목표 문서화 |
| [EP-098](completed/EP-098-rlcd-lite-environment.md) | 2026-09-28 | RLCD-Lite 독립 명명 환경·CUDA 호환 설치·모델 검증 완료 |
| [EP-097](completed/EP-097-eve-rlcd-environment.md) | 2026-09-28 | EVE-RLCD 독립 worktree·명명 환경·GPU/모델 검증 완료 |
| [EP-096](completed/EP-096-laya-training-environment.md) | 2026-09-27 | LAYA 독립 worktree·설치·GPU/모델 검증 완료 |
| [EP-095](completed/EP-095-jev-compact32.md) | 2026-09-23 | 자기 벤치 축약 동일32·EX-058 비교·감사/뷰어/정리 완료 |
| [EP-094](completed/EP-094-jev-improved32.md) | 2026-09-23 | 개선 입력 동일32·EX-057 비교·감사/뷰어/정리 완료 |
| [EP-093](completed/EP-093-jev-offline-input.md) | 2026-09-23 | JEV 오프라인 입력·세트별 스피드 불확실성·검증 완료 |
| [EP-092](completed/EP-092-reviewed-species-team-list.md) | 2026-09-22 | 검토108종 팀 후보 목록·전수 대조/재현 검증 |
| [EP-091](completed/EP-091-team-corpus-role-expansion.md) | 2026-09-22 | 409종 역할 DB 확장·전수 커버리지/재현 검증 |
| [EP-090](completed/EP-090-team-pool-role-coverage.md) | 2026-09-22 | 13팀78슬롯 역할 전수 검사·미부여4세트 확인 |
| [EP-089](completed/EP-089-ex057-role-assessment.md) | 2026-09-22 | EX-057 제출24슬롯 역할 조건 대조·149후보 검증 |
| [EP-088](completed/EP-088-remove-empty-roles.md) | 2026-09-22 | 두 역할·세트 참조 제거 및 데이터 보존 검증 |
| [EP-087](completed/EP-087-role-evidence-restore.md) | 2026-09-22 | 노력치 외 조건 복원·열람 의미/보존 검증 |
| [EP-086](completed/EP-086-role-export-field-guide.md) | 2026-09-22 | 열람본 필드 설명서·실제 값/링크 검증 |
| [EP-085](completed/EP-085-role-export-no-ev.md) | 2026-09-22 | 노력치 정보 제거·44종/역할/통계 보존 검증 |
| [EP-084](completed/EP-084-role-export-readable.md) | 2026-09-22 | 역할 열람본 출처 제거·비율 반올림/정렬 검증 |
| [EP-083](completed/EP-083-team-role-export.md) | 2026-09-22 | 팀 풀44종 역할 DB JSON·원본 일치 검증 완료 |
| [EP-082](completed/EP-082-jev-damage-samples.md) | 2026-09-22 | 기술 피해량 오프라인 샘플·원시 계산/전후 비교·검증 완료 |
| [EP-079](completed/EP-079-jev-retry-backoff.md) | 2026-09-21 | JEV 대기10·30·60초·과거 호환/검증 |
| [EP-078](completed/EP-078-jev-failed-input-probe.md) | 2026-09-21 | 동일 실패 입력 독립 호출·HTTP200·보고/정리 |
| [EP-081](completed/EP-081-jev-pinned32.md) | 2026-09-21 | JEV v3 동일32·v2 전후 비교·감사/뷰어/정리 완료 |
| [EP-076](completed/EP-076-provider-retry-three.md) | 2026-09-21 | provider 재시도3회·모의 HTTP/회귀·과거 보존 완료 |
| [EP-074](completed/EP-074-jev-v3-effects.md) | 2026-09-21 | JEV v3 지식·효과 사전·EX-052 오프라인 검증 완료 |
| [EP-073](completed/EP-073-jev-abyssal32.md) | 2026-09-21 | JEV 대 Abyssal32·전수 감사/뷰어/보존/정리 완료 |
| [EP-072](completed/EP-072-viewer-navigation-hp.md) | 2026-09-21 | 뷰어 방향키 탐색·상대 HP 백분율·오프라인 검증 |
| [EP-071](completed/EP-071-jev-v2-battle.md) | 2026-09-21 | 교정 JEV 입력 실제2경기·전수 감사·뷰어·보존/정리 완료 |
| [EP-070](completed/EP-070-jev-lead-input.md) | 2026-09-21 | JEV 선봉 입력 v2·175입력 대조·오프라인 회귀·과거 보존 완료 |
| [EP-069](completed/EP-069-researcher-viewer.md) | 2026-09-21 | 요청/응답 JSON·탐색/요약·복사/다운로드·전수/브라우저 검증 |
| [EP-068](completed/EP-068-jev-replay-viewer.md) | 2026-09-21 | EX-050 경기별 입력·응답+리플레이·오프라인/온라인 검증 |
| [EP-067](completed/EP-067-viewer-export-location.md) | 2026-09-21 | 정상 종료 뷰어 고정 경로·EX-050 내보내기/오프라인 검증 완료 |
| [EP-066](completed/EP-066-jev-judgment-repeat.md) | 2026-09-21 | 판단 오류 비중단·경기 격리 적용·실제2경기/전수 감사·보고/봉인/정리 완료 |
| [EP-065](completed/EP-065-provider-judgment-policy.md) | 2026-09-21 | 판단 오류 비중단·경기 실패 격리 규칙/매뉴얼·코드 지원 한계 명시 |
| [EP-063](completed/EP-063-jev-probability-validation.md) | 2026-09-21 | JEV 합계 검사 제거·저장17응답/과거 판정 보존 검증 |
| [EP-061](completed/EP-061-jev-client.md) | 2026-09-21 | JEV 환경·독립 클라이언트·모의 HTTP/회귀 검증 |
| [EP-060](completed/EP-060-portable-viewer.md) | 2026-09-17 | EX-046 단일 폴더/ZIP·이동 후 오프라인 뷰어 검증 |
| [EP-059](completed/EP-059-async-official-lead.md) | 2026-09-17 | 공식 관측 선봉32경기·16쌍 유효완료·전수 감사·보고/봉인/정리 |
| [EP-058](completed/EP-058-official-async.md) | 2026-09-17 | 공식 관측 비동기 교정·전수/로컬 동시 검증·봉인 완료 |
| [EP-056](completed/EP-056-official-observation.md) | 2026-09-17 | 공식 관측 B/B2 통합·전수/로컬 검증·새 준비 기본값·과거 호환 완료 |
| [EP-055](completed/EP-055-observation-tracker-comparison.md) | 2026-09-17 | Abyssal 관측 추적·공식 클라이언트 비교·보존 로그 재생 완료 |
| [EP-052](completed/EP-052-intermediate-research-objectives.md) | 2026-09-16 | 중간 목표·RQ2/3·완료 기준·정보와 구조 효과 구분 문서화 |
| [EP-051](completed/EP-051-court-change-input-audit.md) | 2026-09-16 | Court Change·추가 입력 오류 교정·EX-042 전수 감사·별도 정정 완료 |
| [EP-050](completed/EP-050-lead-matchup-rules.md) | 2026-09-16 | 선봉 전략·Dex 규칙 독립 개선·오프라인 검증·과거 보존 완료 |
| [EP-049](completed/EP-049-provider-retry-viewer.md) | 2026-09-16 | 새 공급자 오류 재시도·과거 호환·로컬 검증·EX-042 정상 경기 목록 완료 |
| [EP-047](completed/EP-047-transport-retry.md) | 2026-09-15 | 새 응답 대기600초·연결 재시도·과거 호환·로컬/전체 회귀 완료 |
| [EP-046](completed/EP-046-effect-reference.md) | 2026-09-15 | 배틀·선봉 구조/상세 효과 사전 새 기본값·전수/로컬 검증 완료, 효능 미평가 |
| [EP-043](completed/EP-043-zai-connectivity-probe.md) | 2026-09-14 | 사용자 주소·키로 Z.ai 단일 probe 성공 |
| [EP-042](completed/EP-042-zai-provider.md) | 2026-09-14 | Z.ai 공급자 구현·환경 구성·무API 로컬 검증 완료 |
| [EP-040](completed/EP-040-llm-lead.md) | 2026-09-14 | B2 선봉 선택 구현·로컬 검증 완료, 유료/효능 미평가 |
| [EP-039](completed/EP-039-context-document-maintenance.md) | 2026-09-14 | 현재 문서 축약·원문 참조·읽기 경로·증거 연결 정리 |
| [EP-038](completed/EP-038-io-explanation-review-opt-in.md) | 2026-09-14 | 기본 IO 설명 검토 적용 범위 정비 |
| [EP-037](completed/EP-037-viewer-turn-tabs.md) | 2026-09-14 | 새 viewer 턴 탐색·응답/reasoning 기본 표시 |
| [EP-036](completed/EP-036-delayed-target-slot.md) | 2026-09-14 | 지연 기술 대상 슬롯 교정·오프라인 검증 완료 |
| [EP-034](completed/EP-034-b-prompt-optimization.md) | 2026-09-14 | B 전달 표현 오프라인 최적화 완료·효능 미평가 |
| [EP-033](completed/EP-033-cloud-concurrency-default8.md) | 2026-09-14 | Cloud 기본 동시성·과거 설정 호환 정비 |
| [EP-031](completed/EP-031-protect-expiry.md) | 2026-09-11 | Protect 만료 교정·오프라인 검증 완료 |
| [EP-029](completed/EP-029-a-diagnostic64.md) | 2026-09-11 | 원본 A 진단 유효완료·검토·보고 완료 |
| [EP-028](completed/EP-028-smogon-diagnostic-design.md) | 2026-09-11 | Smogon 기반 평가 준비 완료·대전 미실행 |
| [EP-027](completed/EP-027-external-memory-repeat32.md) | 2026-09-11 | 동일 조건 반복 비교 완료·관측 대응차 없음 |
| [EP-026](completed/EP-026-battle-guide-movefix32.md) | 2026-09-11 | 공유 permit 실패 중단 처리 완료·성능 비교 미완료 |
| [EP-025](completed/EP-025-calculator-move-names.md) | 2026-09-10 | Weather Ball 및 동일 원인 기술명 처리 교정 |
| [EP-024](completed/EP-024-calculator-inputfix32.md) | 2026-09-10 | 계산 결함 중단 처리 완료·성능 비교 미완료 |
| [EP-023](completed/EP-023-calculator-input-audit.md) | 2026-09-10 | 입력 전체 감사·확정 결함 교정·별도 영향 분석 |
| [EP-022](completed/EP-022-calculator-entry-calcfix32.md) | 2026-09-10 | 계산 결함 중단 처리 완료·성능 비교 미완료 |
| [EP-021](completed/EP-021-battle-guide-direct32.md) | 2026-09-09 | 직접 비교 slot 처리·검토 완료; 비교 미완료·정정은 원문 참조 |
| [EP-019](completed/EP-019-battle-field-guide.md) | 2026-09-09 | B 행동 필드 설명서·버전/hash·경로 검사 |
| [EP-017](completed/EP-017-experiment-defect-recovery.md) | 2026-09-09 | 새 실험 테스트·평가 결함 복구 규정·매뉴얼·등록 항목 정비 |
| [EP-016](completed/EP-016-input-summary-documentation.md) | 2026-09-09 | 현재 입력·요약 구조와 prompt 원문 부록 문서화 |
| [EP-014](completed/EP-014-agent-instruction-maintenance.md) | 2026-09-08 | 승인·중단 지시 및 현재 상태 정합화, 로컬 스킬 수정 |
| [EP-010](completed/EP-010-upstream-fallback.md) | 2026-09-07 | 원본 fallback 병렬 반복 유효완료 |
| [EP-009](completed/EP-009-battle-identity-action-candidates.md) | 2026-09-07 | 식별·후보 통합 완료; Cloud 출력 오류로 후속 미실행 |
| [EP-008](completed/EP-008-parallel-thirty-two-repeat.md) | 2026-09-07 | 병렬 반복 slot 처리 완료; 유효 완료 기준 미달 |
| [EP-007](completed/EP-007-model-concurrency.md) | 2026-09-07 | 동시성 실측·운영 비교 및 slot 처리 완료; 불완전 수집 |
| [EP-006](completed/EP-006-repeat-benchmark-profiles.md) | 2026-09-07 | 반복 profile 지원·시간 재측정 완료; 본 비교 예산 초과 추정 |
| [EP-005](completed/EP-005-remove-client-output-cap.md) | 2026-09-07 | Cloud 출력 예산·기본 최대 context 적용 |
| [EP-004](completed/EP-004-pokechamp-baseline-pilot.md) | 2026-09-07 | 기준선 pilot 분석·보고 완료; 불완전 수집 |
| [EP-001](completed/EP-001-pokechamp-reproducible-environment.md) | 2026-09-04 | Pinned PokéChamp 환경과 valid Ollama Cloud action one-battle qualification 완료 |
| [EP-002](completed/EP-002-pokechamp-battle-observability.md) | 2026-09-04 | Opt-in full-fidelity battle source bundle, trace hook, static viewer와 catalog 완료 |
| [EP-003](completed/EP-003-default-untimed-showdown-battles.md) | 2026-09-04 | Parent-owned Showdown timer-off 기본값과 manual/metadata 정합화 완료 |

Completed table은 [`completed/`](completed/)의 검증 완료 plan만 나열한다. 상세 progress와
evidence는 index에 복사하지 않고 개별 plan에 보존한다.

EP-002의 2026-09-06 viewer 후속 개선과 demo 재생성 검증은 개별 plan의 결과 및 증거에 기록한다.

## 생명주기 (Lifecycle)

1. 겹치는 작업이 있는지 [`active/`](active/)와 위 Active plan 목록을 확인한다. Competing
   implementation을 열기보다 기존 plan을 확장한다.
2. [`TEMPLATE.md`](TEMPLATE.md)를 `active/EP-XXX-short-title.md`로 복사한다. Stable ID를
   부여하고 목표가 승인되었을 때만 status를 `Active`로 지정한다. 현재 대화의 명시적 지시를
   포함한 승인 근거를 plan에 기록하며, 동일 승인에 대한 재확인은
   [`../INDEX.md`](../INDEX.md)의 `승인·확인 질문·중단·완료` 절을 따른다. 이 index에도 한 행을 추가한다.
3. 작업 중 Progress, decision, blocker, verification evidence를 개별 plan에 최신으로 유지한다.
   새 실험을 포함하는 plan은 [공통 복구 절차](../RESEARCH_DESIGN.md#defect-recovery)와
   [C-018](../CONTRACTS.md#c-018-recovery)의 적용, 별도 전체 중단 사유·범위, 재수집 허용·단위·한도,
   승인·누적 예산·시계 및 실행기 지원 여부를 experiment와 함께 등록한다. 문서 작업 등
   비실험 plan은 해당 없음을 기록한다. 기존 plan/실험의 중단 규칙을 자동 변경하지 않는다.
4. Higher-authority document와 충돌하면 기록·보고하고 공통 규칙에 따라 그 해결에 의존하는
   작업을 중단한다. 명시적인 전체 중단 규칙은 그대로 적용한다. Plan은 Charter, domain authority
   또는 유효한 Accepted Decision의 제약을 면제할 수 없다.
5. 모든 acceptance criterion을 해결하고 verification을 기록한 뒤에만 동일한 identity의
   파일을 [`completed/`](completed/)로 옮긴다. 미완료 또는 포기한 작업은 사실대로 표시하며,
   검증된 것처럼 `completed/`에 두지 않는다.
6. 이동과 동시에 이 파일의 Active/Completed table을 갱신한다. Plan이 현재 operational
   picture를 변경하면 [`../STATUS.md`](../STATUS.md)도 갱신한다.

File 이동은 lifecycle을, Git history는 edit을 기록한다. Plan ID를 재사용하지 않는다.
