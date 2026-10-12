# EP-102 — EX-060 기반 Qwen3.5-4B 첫 학습 검증

- 상태: Completed
- 생성일: 2026-09-28
- 책임자: Codex
- 승인: 현재 사용자 계획 구현 지시 / [D-098](../../decisions/D-098-qwen-action-value.md)
- 관련: [연구 설계](../../RESEARCH_DESIGN.md#qwen-action-value-first-run), [C-048](../../CONTRACTS.md#c-048-action-value-training), [EX-061](../../experiments/EX-061-qwen-action-value.md)

## 목표·범위

EVE worktree에 soft target 변환·독립 질문 forward·LoRA 학습·오프라인 q 평가를 추가하고
동결 EX-061을 실행한다. 원자료·기존 학습 경로·환경 lock 보존, AgenticSTS subtree 변경 없음.
겹치는 EP-062/064/075/077/080의 JEV 입력·대진 중단 조건을 읽었으며 재개하지 않는다.
sub-agent는 사용하지 않는다.

## 완료 기준·검증

- [x] 167레코드 변환·원자료 집계·입력/타깃 분리·무절단·명령 검증.
- [x] CPU 검사·RLCD 기대경사 검증·기존 EVE 회귀 통과.
- [x] 고정 로딩·최장 입력 forward/backward·기준선·3epoch·66update.
- [x] 기본 가중치 불변·LoRA 변경·새 프로세스 재로딩 차이≤1e-4.
- [x] 기술/개발 적합 별도 판정·provenance·보고·상태 갱신·자원 정리.

새 배틀이 없어 C-047 viewer는 해당 없음. 증거 `evidence/ep102/`, 실행 자료
`.pokechamp-data/training/ex061/`. 타깃/metadata 변경 후 동일 토큰·관측 가중을 포함해 검사한다.

## 진행·중단

- 2026-09-28 — 관련 원문·환경 확인, 승인 및 동결 protocol 등록. 변환·토큰 감사·구현 완료, GPU 실행 준비.

RD11.1/C-018 및 EX-061 중단·복구를 따른다. 입력/집계/명령/필수 가중치 불일치,
비유한 loss/gradient·CUDA OOM이면 의존 학습 중단·보존. 시간 중단 없음, 실패 후 GPU 학습 재시도0.
GPU 전 구현 결함은 교정·독립 회귀 가능. 평가 결함은 온전한 저장 예측 전부를 재평가한다.
중단 처리를 학습 완료로 표시하지 않는다.

## 결과

167레코드·입력 분리·무절단 감사 완료. 최종 토큰10,563~13,921, 원자료 전수 checksum 통과.
테스트 fixture의 JSON escaping/문장 내 counts 오판을 교정했다. 실제 입력/처치 영향 없음, GPU 실행 전이다.
16개 포켓몬 검사 통과. 전체 회귀239통과·1skip·5deselected. 물리 GPU1에서 실제 로딩·최장 입력 사전검사를 시작했다.

### 준비 실패 보존

2026-09-28 캐시 completeness 검사에서 `.gitattributes` 누락으로 모델 로딩 이전에 종료했다.
GPU model allocation/forward/backward/update 모두0, 처치·입력·모델 tensor 영향 없음.
`preparation-attempt-1/halt.json`·console을 보존하고 같은 revision의 metadata를 추가 다운로드한다.
RD11.1의 GPU 전 준비 의존성 교정이며 중단 조건의 CUDA OOM/가중치 불일치나 GPU 학습 재시도가 아니다.
원 실행 조건·source·누적 시계 근거를 유지한 채 완성 캐시에서 첫 GPU 사전검사를 진행한다.

### GPU 사전검사 통과

고정 text426tensor 모두 checkpoint와 정확히 일치, base4,205,751,296·LoRA16,232,448파라미터.
최장13,921토큰 forward/backward·유한 loss/gradient·update0·adapter 불변 확인.
CUDA event47.6978초, 최대 할당30,099,869,696byte·예약32,474,398,720byte.
후속 기준선·고정3epoch 진행. [사전검사](../../../.pokechamp-data/training/ex061/train/preflight.json).

### 제어 서버 재시작 복구

2026-09-28 약54분 경과 시 daemon restart로 parent shell·감시가 종료됐으나 원 학습 PID844273과
tee844274는 살아 있었다. 당시 후보66/501·update10/66·기준선167/167, halt 없음·GPU1 계속 실행.
학습·source·조건·시계 재시작0. 고아 tee의 stdout/stderr pipe를 읽는 detached supervisor를 붙여
BrokenPipe를 예방하고 원 프로세스 정상 종료 뒤 이미 승인된 새 프로세스 재로딩만 수행하도록 복구했다.
증거 `.pokechamp-data/training/ex061/control-plane-recovery.json`·`recovery-supervisor.py`.

복구 확인 중 tee는 종료됐으나 학습 update11과 원 PID는 계속 살아 있었다. 학습 stdout의
동일 pipe에 직접 detached reader PID900241을 연결했고 실제 read descriptor를 대조했다.
이후 로그는 `recovered-train-console.log`, 감시·후속 재로딩은 supervisor PID899261이 맡는다.
GPU 실행 재시작/중복 forward/update0, 제어 helper는 별도 `control-plane-recovery-v1/`에 보존한다.

### 첫 epoch 완료

22update·167학습 forward/backward와 기준선/epoch1의334평가 forward 완료, epoch2 진행.
전체 q MSE0.0896226→0.0834140, 비교 가능한11관측0.1790089→0.1662430,
11관측 평균 표본 regret0.2982955→0.1761364. 최종 판정은 고정3epoch·재로딩 뒤 수행한다.
최대 할당30,292,875,264byte·예약32,608,616,448byte, 중단 조건 발생 없음.

종료 progress에서 peak 항목이 덮어써지는 관측 기록의 공백을 확인했다. 후보243 확인 후
읽기 전용 resource sampler로0.25초마다 기존 timed progress의 누적 CUDA peak를 보존한다.
학습 source/설정/프로세스 변경 없음, 별도 helper/hash·resource-samples.jsonl을 보존한다.

### 두 번째 epoch 완료

44update·334학습 forward/backward·501평가 forward 완료, 마지막 epoch 진행.
전체 q MSE0.0682876·11관측0.1348839로 기준선 대비 각각23.8%·24.6% 감소,
11관측 regret0.1051136·표본 최고 선택7/11. 최종3epoch·재로딩 판정 전 중간 결과다.

### 고정 학습 완료·재로딩 시작

3epoch·66update·501학습/668평가 forward, base hash 불변·LoRA hash 변경 확인.
전체/11관측 MSE는 기준선 대비41.2%/43.4% 감소, 11관측 regret0.0681818·최고 선택7/11.
전체 MAE는6.7% 증가하여 모든 가치 지표의 개선으로 해석하지 않는다.
원 학습 정상 종료 뒤 supervisor가 새 PID1093080에서 승인된167예측 재로딩을 시작했다.

### 최종 완료

2026-09-28 — 재로딩167개 확률 차이0.0, 기술 성공·동결 MSE/Brier·regret 개발 적합 true.
모든66update 유한값·epoch별 전수 처리·110개 합법 선택·base 불변·LoRA496tensor 변경 확인.
전체 MAE 증가를 한계로 함께 보고한다. GPU1 해제·학습/재로딩/감시0, API/추가 배틀0.
원자료 전수 checksum 재확인·새 자료 봉인 완료. 실행 source-v1은 보존하고 종료 후 로그의
CUDA peak 보존만 source-v2로 교정했다. 학습/inference AST 동일·CPU 로그 검사·16회귀 통과,
GPU 재실행0. 캐시 환경 변수 없는 추가 CPU 호출2실패는 교정·원인을 별도 보존했다.
[최종 보고](../evidence/ep102/report.md) · [전수 검증](../evidence/ep102/final-verification.json) ·
[봉인·정리](../evidence/ep102/closure.json).
