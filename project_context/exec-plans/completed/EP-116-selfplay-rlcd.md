# EP-116 — 자기대국과 RLCD 확률 보정

- 상태: Completed
- 생성일: 2026-10-02
- 완료일: 2026-10-02
- 책임자: Codex
- 승인 근거: 현재 사용자 제공 계획의 구현·검증·첫 실행 지시 / D-114
- 관련: C-055/C-056, EX-071/EX-072

## 목표·범위

`integration/pokechamp/selfplay/`와 `scripts/pokechamp-selfplay`에 별도 수집·PPO/WDL/BC 학습·
보정·선택·최종 평가·재개·보고를 구현하고 [EX-072](../../experiments/EX-072-selfplay-rlcd.md)의
동결 조건으로 실행한다. INDEX/CHARTER·관련 RD/C/ARCHITECTURE·EP-108/103/041을 확인했다.
기존 imitation·GPU1 실행·봉인·과거 Blocked는 유지한다. upstream·AgenticSTS는 수정하지 않는다.
독립 모델/학습, 팀 준비, 통계/뷰어를 서브에이전트에 분리 위임하고 주 에이전트가 통합·검증한다.

## 완료 기준

- [x] ADR/EP/EX·domain authority·설정·자료/팀/일정 동결
- [x] CPU 필수 검사·GPU32이하 사전검사·첫8경기 연결 감사
- [x] 한 개 이상의 dev 완료 학습 후보·정책 선택·보정 채택 판단
- [x] 원 시계를 보존한 실제 SIGTERM 재개·완전 checkpoint 검증
- [x] 잠긴 최종 test·대응 bootstrap·선택 행동 확률 평가·최종 보고
- [x] C-047 오프라인 이동 뷰어·원자료/모델 봉인·소유 자원 정리·상태 갱신

## 검증·진행

- 2026-10-02 — 별도 수집·정책 학습·head 보정·평가·완전 checkpoint·감독 실행기와 보고/뷰어를 구현했다.
  CPU 152검사가 통과했다. 실제 CPU SIGTERM 후 새 PID에서 가중치/AdamW/cursor/RNG의
  동일성, 모의 전체 4라운드·보정·평가, 원자료 누락/변조 gate와 이동 후 오프라인 Chromium을 포함한다.
  증거: `.pokechamp-data/experiments/ex072-selfplay-rlcd/verification/cpu.json` 및 연결된 세 suite 로그.
- 원 replay 9,201파일·역사 평가 구성을 제외한 새 92팀과 총 584slot의 조건/seed를 동결했다.
  BC는 EX-071 train의 결과와 무관한 hash 순서 3,072개다. 원자료 전수 확인과 split/합법성 검사는
  `prepared/manifest.json`에 있다. 이 시점 GPU forward·대국·update는0이며 실제 GPU 실행을 이어간다.
- 최초 GPU 시계·UUID를 고정하고 감독 실행기를 시작했다. `launch.json`, `resource.json`,
  `manifest.json`, `clock.json`과 `worker-*.log`에 실제 실행 조건을 보존한다.
- GPU preflight32개 통과·update0. 최대 할당 10,431,682,560bytes, 초기 EX-071 logits
  완전 일치·WDL 각1/3·train/inference 차이0·base/학습 가중치 불변·유한 gradient를 확인했다.
  증거: `verification/preflight.json`. 초기 sampling 기준선 dev24 수집에 진입했다.
- 초기 sampling dev24 전 경기 정상 종료·전송/결과 감사 통과 후 첫 train64 수집에 진입했다.
  슬롯별 `games/*/outcome.json`, `audit.json`, `decisions.jsonl`과 `battle-events.jsonl`을 보존한다.
- 첫8 학습 대국은 정상8·실패0·유효387결정이며 선택/기록/결과 연결 감사를 통과했다.
  증거: `verification/first-eight.json`. 이 경기들은 첫 라운드64 안에 포함한다.
- 첫 라운드64 시도는 정상64·실패0·유효2,783결정으로 학습 gate를 충족했다.
  최대1,536개 결정의 동결 old log probability/WDL 재검증 후 PPO/WDL/BC 학습에 진입한다.
- 실제 GPU에서 선택1,536결정의 old log probability/WDL 최대 오차가 모두0이었다.
  첫 update는 base 불변·LoRA/행동 head/WDL head 변경을 통과했다. 이어 실제 SIGTERM으로
  worker3791222를 종료하고 worker3893889가 같은 최초 시계·완료1step checkpoint·optimizer/RNG/cursor를
  복원한 뒤 2번째 update를 완료했다. 증거: `verification/first-update.json`,
  `verification/resume.json`, `restart-request.json`, `process-events.jsonl`, `updates.jsonl`.
- 첫 라운드는 적용77update 후 미적용 다음 batch의 KL 한도에 도달하여 사전 규칙대로 종료했다.
  `rounds/round-1-training.json`의 `status=kl_limit`, 완료 cursor와 `snapshots/round-1.pt`를
  보존하고 후보 dev24에 진입했다. 이 조기 종료는 설계된 학습 종료이며 기술 실패가 아니다.
- round-1 후보 dev24가 모두 정상 종료·감사를 통과하여 최소1개 dev 완료 학습 후보를 확보했다.
  최초 시계 안에서 동결 round-1 정책으로 두 번째 라운드64 수집을 시작했다.
- 두 번째 라운드64도 정상64·실패0·유효2,557결정으로 gate를 통과했다. 새 라운드 표본만
  old 분포 검증·PPO/WDL에 사용하고 기존 optimizer 상태와 누적77update를 이어간다.
- 두 번째 라운드도 선택1,536결정의 old log probability/WDL 최대 오차0을 확인했다.
  적용171update(누적248) 후 미적용 다음 batch의 KL 한도로 학습을 끝냈다.
  `rounds/round-2-training.json`, `snapshots/round-2.pt`를 보존하고 후보 dev24를 시작했다.
- round-2 후보 dev24도 정상24·실패0으로 완료했다. dev 완료 후보2개를 보존하고
  동결 round-2 정책의 세 번째 라운드64 수집에 진입했다. 후보 평가는 선택용이며
  성능 개선 판정은 잠긴 최종 test와 대응 bootstrap까지 보류한다.
- 세 번째 라운드64도 정상64·실패0·유효2,445결정으로 gate를 충족했다.
  `rounds/round-3-gate.json`을 보존하고 새 선택1,536결정의 old 분포 검증에 진입했다.
  이 시점 누적 정상264경기·정책248update이며 GPU3만 사용하고 GPU1의 별도 실행은 유지한다.
- 세 번째 라운드 선택1,536결정도 old log probability/WDL 최대 오차0으로 재검증을
  통과했다. 기존 optimizer 상태를 유지한 새 라운드 업데이트가 시작됐다.
- 세 번째 라운드는 적용20update(누적268) 후 미적용 다음 batch의 KL 한도로 종료했다.
  `rounds/round-3-training.json`, `snapshots/round-3.pt`를 보존하고 후보 dev24를 시작했다.
- round-3 후보 dev24도 모두 정상 종료·감사를 통과했다. dev 완료 후보3개를 보존하고
  마지막 네 번째 라운드64 수집을 시작했다. 이 시점 전체 정상288경기·실패0이다.
- 네 번째 라운드64도 정상64·실패0·유효2,446결정으로 gate를 충족했다.
  자기대국256경기를 모두 정상 완료하고 마지막 라운드의 선택1,536결정 재검증에 진입했다.
  증거: `rounds/round-4-gate.json`. 이 시점 전체 정상352경기·정책268update이다.
- 네 번째 라운드도 선택1,536결정의 old log probability/WDL 최대 오차0을 확인하고
  기존 optimizer 상태를 유지한 마지막 정책 업데이트를 시작했다.
- 네 번째 라운드는 적용7update 후 미적용 다음 batch의 KL 한도로 종료했다.
  네 라운드의 적용 update는77/171/20/7(총275)이며 모두 정해진 KL 종료 규칙을 따랐다.
  `rounds/round-4-training.json`, `snapshots/round-4.pt`를 보존하고 마지막 후보 dev24를 시작했다.
- 초기 정책과 네 후보의 dev120경기를 모두 정상 완료했다. dev 점수가 가장 높은 round-2를
  선택하고 `selection.json`, `snapshots/selected-before.pt`에 고정했다. 새 train64경기의
  head 보정용 수집을 시작했다. 이 시점 정상376경기·실패0이며 최종 test는 아직 시작하지 않았다.
- 선택 정책의 head 보정용64경기도 모두 정상 종료·감사를 통과했다. 전체 정상440경기·실패0이며,
  동결 정책의 선택 행동 표현 추출에 진입했다. 이후 WDL head만 학습하고 별도 dev로 채택을 판단한다.
- 보정용 유효2,529결정 중 동결 hash 선택2,048개의 표현을 추출하고 WDL head만
  2epoch·256update 학습했다. 행동 정책 가중치 불변 검사가 통과했다.
  증거: `verification/calibration-policy.json`, `calibration-updates.jsonl`,
  `snapshots/selected-after.pt`. 별도 dev24의 같은 관측·선택 행동에서 보정 전후를 비교 중이다.
- 보정 채택용 dev24도 전 경기 정상 종료·감사 통과, 선택 행동701개의 전후 예측을 확보했다.
  가중 half-Brier가 0.2761709359→0.2871806507로 악화되어 사전 기준에 따라 보정 전 head를
  유지했다(NLL은 0.8903500381→0.7922144085). `calibration-decision.json`,
  `evaluation-lock.json`, `snapshots/final.pt`에 정책/head를 잠그고 최종 test에 진입했다.
  이 시점 정상464경기·실패0이며 최종 test 결과를 이용한 재선택·조정은 하지 않는다.
- 잠긴 최종 test의 초기 모델60경기를 전부 정상 완료했다. 선택 round-2/보정 전 head로
  대응60경기의 평가를 시작했다. 두 모델의 전체 test 완료 후 점수차·paired bootstrap을 집계한다.
- 예정584경기와 두 모델의 test120경기를 모두 정상 완료했다. GPU worker 정상 종료·GPU3 반환 후
  최종 브라우저 검증이 의존성 `httpx` 누락으로 시작 전 실패했다. 원 보고/완료 receipt/export는
  미완료 판정으로 보존하고 [EP-117](EP-117-selfplay-finalization-recovery.md)의 별도 CPU 복구를 진행한다.
- EP-117의 의존성·큰 정수 표시 교정을 별도 identity에서 검증하고, 원 검증기로584경기 전부의
  이동 후 오프라인 재생을 통과했다. 원자료·모델·원 보고/실패·원 시계는 보존했다.
  정정 `finalization-v3`는 모든 gate가 true이며 미완료 기준0이다. 최초 GPU부터11시간45분 안에
  완료했고 GPU3·소유 프로세스 종료, GPU1/EX-066 유지와 최종 게시 링크/checkpoint를 확인했다.
  실험은 완료했으나 잠긴 test의 대응 구간이0을 포함해 성능 개선은 미입증이다.

## 중단·복구

INDEX 공통 기준·RD11.1/C-018·RD11.2/C-046 및 EX-072의 원 시계·복구 규칙을 따른다.
기술 결함은 영향 단계 중지·증거 보존·독립 검증 후 같은 조건으로만 재개한다.
실패·중단 경기는 재경기하지 않는다. 실행 완료와 개선 입증은 분리하며 필수 기준 미달은 미완료다.

## 결과·증거

산출물: `.pokechamp-data/experiments/ex072-selfplay-rlcd/`.
[조건·최종 결과](../../experiments/EX-072-selfplay-rlcd.md#final-results) ·
[정정 최종 보고](../../../.pokechamp-data/experiments/ex072-selfplay-rlcd/corrections/finalization-v3/report.md) ·
[완료 receipt](../../../.pokechamp-data/experiments/ex072-selfplay-rlcd/corrections/finalization-v3/completed.json) ·
[584경기 뷰어](../../../exports/battle_viewers/ex072-finalization-v3/index.html).
