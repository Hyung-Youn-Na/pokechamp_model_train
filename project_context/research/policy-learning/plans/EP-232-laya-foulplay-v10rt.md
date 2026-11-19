# EP-232 — foul-play(탐색 봇) 대 laya v10rt 128경기(CPU; EX-173 EX-120 팀 → 중지, EX-174 Blim 팀)

- 상태: Completed
- 생성일: 2026-11-17
- 책임자: Claude Code
- 승인 근거·범위: 사용자 지시와 승인된 계획(2026-11-17 대화), [D-211](../decisions/D-211-laya-foulplay-opponent.md), [D-212](../decisions/D-212-laya-foulplay-blim-teams.md)(Blim 팀으로 교체). 환경 준비 → 구현 → mock → prepare → execute → export까지 중간 확인 없이 진행한다. 외부 다운로드는 환경 준비 단계에서 1회만 한다.
- 관련 contract / decision / experiment: [C-047](../../../CONTRACTS.md#c-047-viewer-export), [D-211](../decisions/D-211-laya-foulplay-opponent.md), [EX-173](../experiments/EX-173-laya-v10rt-vs-foulplay128.md), [EX-174](../experiments/EX-174-laya-v10rt-vs-foulplay-blim128.md), [EX-168](../experiments/EX-168-laya-v10t-v10rt-battle256.md), [EX-167](../experiments/EX-167-laya-v10-ladder-training.md)
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit·미커밋 변경: `research/model-training`, `a4e5964`, EP-231의 미커밋 기록·catalog 변경이 있다(건드리지 않음).
- 작업 checkout과 interpreter/launcher: `/workspace`. 오케스트레이터는 laya venv(EP-230과 같음), laya 진영 워커는 `pokechamp/.venv`, foul-play 진영은 `/workspace/.tools/foul-play/.venv`(python 3.11, poke-engine 0.0.48). Rust는 `/workspace/.tools/rust`.
- 새 산출물: `runs/model-training/EX-173/`(중지), `runs/model-training/EX-174/`(collection·mock 포함), 뷰어 `/workspace/exports/battle_viewers/ex174/`, 메모리 기록 `runs/model-training/EX-173-memory.log`, 연결 실행 스크립트 `scripts/foulplay-ep232`
- 참조 원자료(읽기 전용): laya-play `teams_blim.json`, EX-120 `collection/`, EX-167 `checkpoints/selected`, EX-168 `result.json`, `/ref/foul-play`

## 목표와 맥락

v10rt를 Abyssal보다 강한 것으로 알려진 탐색 봇과 붙여, 더 어려운 고정 상대에서의 수준과 판본 구별용 상대로서의 쓸모를 본다(D-211).

## 범위와 불변 조건

- **포함**: `integration/foulplay/`, `scripts/foulplay-ep232`, 기록.
- **보존**: `laya_imitation`·`laya_ladder`·`laya_v10`·`pokechamp/imitation` 파일과 기존 산출물·봉인은 바이트 단위로 같다. `/ref/foul-play`는 읽기만 한다.
- **자원**: CPU만. 포트 8100~8103. GPU와 EP-231 프로세스는 건드리지 않는다. 메모리 상한 25 GB(EP-231 학습 상한 50 GB와 합해 80 GB 이하), 시작 전 `free -g` 확인.
- **외부 호출**: 환경 준비 때 1회(rustup, PyPI, D-211 결정 3의 자료). 배틀 중에는 없다(actor가 차단).

## 완료 기준

- [x] Rust·poke-engine 빌드, foul-play 사본, 추론 자료 봉인
- [x] `integration/foulplay` 구현, 단위 검사, 시험 1판(임시 디렉터리)
- [x] D-211, EP-232, EX-173 등록, catalog build/check
- [x] EX-173 mock 2/2 정상·감사 통과 → 사용자 지시로 EX-173 중지(D-212)
- [x] EX-174 Blim 일정 생성·봉인
- [x] EX-174 mock 2/2 정상·감사 통과
- [x] EX-174 prepare → execute 128슬롯 → export(뷰어, report.md, 봉인), 뷰어 브라우저 확인
- [x] 결과를 EX-174, STATUS, catalog에 기록

## 절차

1. `scripts/foulplay-ep232 run EX-174`: mock → prepare → execute → export → 뷰어 확인. 각 단계는 산출물이 있으면 건너뛰고, 실패하면 멈춘다.
2. 결과를 기록하고 사용자에게 보고한다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 자동 재실행은 없다. phase 실패(감사 실패, actor 결과 없음, 서빙 오류), 보존 해시 변경, mem-guard 종료(137)에서 멈추고 보고한다.

## 진행

- 2026-11-17 — 등록. 환경 준비: rustc 1.100.0, poke-engine 0.0.48(`terastallization` feature), 자료 4개 봉인(16:11 KST). 단위 검사 4개 통과. 임시 디렉터리 시험 1판: 첫 시도는 foul-play `create()`가 하위 클래스를 무시해 로컬 로그인 대체가 적용되지 않아 실패했고, 고친 뒤 정상 종료(foul-play 승 10턴, 감사 통과, 94초, 결정당 약 7초).

- 2026-11-17 — EX-173 mock 2/2 정상(16:27 KST), prepare·execute 시작(16:28 KST). 16:30 KST에 사용자 지시("blimAI 팀으로 테스트", 중지·교체 선택)로 EX-173을 중지했다. 끝난 슬롯 0. 정리할 때 첫 `pkill` 패턴이 정리하던 셸 자신과 맞아 셸이 먼저 끝났고, 연결 실행기만 종료되고 execute는 남았다. PID 목록으로 다시 종료해 EX-173 프로세스 68개를 모두 정리했다(laya-play 서빙은 건드리지 않음). D-212·EX-174 등록, Blim 일정 생성(유효 64팀, 1팀은 서명 중복, 학습 자료 서명 15팀).

- 2026-11-17 — EX-174 mock 2/2(16:37 KST), execute 16:37~20:11 KST, export·뷰어 확인 20:20 KST. 같은 시간대에 사용자 지시로 laya-play 공식 래더 루프(v10rt, Blim 팀 `t95bfb45561`)를 16:37~23:00 KST로 따로 돌렸다(이 plan 범위 밖, CPU만 공유).

## 결과 및 증거

- [EX-174](../experiments/EX-174-laya-v10rt-vs-foulplay-blim128.md): v10rt 42/0/85(정상 127, 미완료 1), 평균 점수 0.331 [0.250, 0.414]. 보고 `runs/model-training/EX-174/report.md`(foul-play 테라 집계는 EX-174 결과 절의 정정 참조), 뷰어 `/workspace/exports/battle_viewers/ex174/`.
- [EX-173](../experiments/EX-173-laya-v10rt-vs-foulplay128.md): 사용자 지시로 중지, 끝난 경기 0.
