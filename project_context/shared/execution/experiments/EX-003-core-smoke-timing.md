# EX-003 — 128K·300초 핵심 8판 시간 재측정

- 상태 (Status): Completed
- 완료일: 2026-09-07
- 생성일: 2026-09-06
- 관련 plan: [EP-006](../plans/EP-006-repeat-benchmark-profiles.md)
- 관련 decision: [D-015](../decisions/D-015-repeat-benchmark-profiles.md)
- Experiment ID: `core-smoke-128k-300s-v1`

## 질문과 사전 조건

RQ-B0의 운영 측정: 현재 출력/timeout 조건의 핵심 8판 시간·신뢰성은 얼마이며
32판 반복의 4시간 예산이 타당한가? 방향성 효능 가설은 없다.

Gen9 OU, pinned minimax(K=2 optimized), IO 각각 Abyssal/OneStep 상대.
[core-smoke.json](../../../../integration/pokechamp/configs/core-smoke.json): seed 20260906,
4대진 × 공통 1 team/seed block × 팀·진영 교환 2판 = 예정 8 slot.
개발 팀 [1,2,5,6,9,11,12,13], 확증 팀 [3,4,7,8,10] 제외. 일정/source/team checksum,
actual seed와 호출 조건은 plan/actor seal에 기록한다. 각 경기 server와 각 actor는 새 process다.

Ollama Cloud glm-5.3-flash, low effort, 131072 output, provider 기본 context,
요청 300초, 경기 watchdog 1200초, Showdown timer off. 원본 temperature와 선택 정책 보존.
Minimax depth 오류는 수정하지 않는다. EX-002의 결과와 합치지 않는다.

## 분모·중단·해석

예정 slot, 처리 slot, 모든 attempt, 유효 완료를 별도 보고한다. Transient transport/rate-limit/
timeout만 동일 slot에 1회 재시도한다. 출력/알고리즘/watchdog는 패배가 아니며 추가 slot은 없다.
Auth/model/configuration/integrity는 batch 중단이다. 모든 source를 보존한다.

IO/minimax 완료 조건부 핵심 점수는 Abyssal/OneStep (W+0.5D)/N의 동일 가중 평균이며
한 상대의 유효 완료가 없으면 null이다. 유효 완료율, 자체 출력/timeout 오류와 peer 중단,
유효 완료 minimax choose 분모의 fallback 분율, 실패 포함 시간·호출/token을 함께 보고한다.
공통 block 1개여서 분산/CI/우월성 claim은 없다. 확증 trace와 자동 memory write는 사용하지 않는다.

4대진 예정 slot이 모두 처리되면 각 대진의 전체 attempt 시간/처리 slot × 8을 합쳐
32판 시간을 추정한다. 여유 50% 포함 4시간 이하 여부는 운영 평가이며 통계적 상한이 아니다.
8판만 실행하고 32판은 추정한다. 오류 없는 minimax 성능은 수정 조건에서 다시 측정해야 한다.

## Evidence 및 결과

2026-09-07: 8-slot plan을 seal하고 실행을 시작했다. 원자료 위치: `.pokechamp-data/benchmarks/core-smoke-128k-300s-v1/`와
`.pokechamp-data/experiments/core-smoke-128k-300s-v1/battles/`.

Plan SHA256: `36482812a63b512c5593d0217e2075c59d1a2df30407d1811270a8b3fc75ba12`.

실행 순서: minimax-one_step-b01-s0, io-abyssal-b01-s0, minimax-abyssal-b01-s0, io-one_step-b01-s0, io-abyssal-b01-s1, io-one_step-b01-s1, minimax-abyssal-b01-s1, minimax-one_step-b01-s1.


### 결과

예정 8/처리 8/attempt 8, 유효 완료 6(75%). 추가 slot·재시도·provider timeout·watchdog는
각각 0이다. 자체 종료 오류는 minimax의 opponent_action 출력 검증 2건이다. 모두
json_valid=true, done_reason=stop이어서 128K 출력 길이 제한에 의한 절단이 아니다.
Abyssal/OneStep은 각 1건씩 상대 오류로 중단됐다. Source integrity 실패와 분류 불일치는 없다.

| 방법 | 예정 | 유효 완료 | 자체 출력 오류 | 완료 조건부 핵심 점수 | 호출 | 입력 token | 출력 token |
|---|---:|---:|---:|---:|---:|---:|---:|
| IO | 4 | 4 | 0 | 0.75 | 172 | 392883 | 13098 |
| minimax | 4 | 2 | 2 | 0.0 | 647 | 1280732 | 42814 |

IO는 Abyssal 1승/2경기, OneStep 2승/2경기다. Minimax는 각 상대 0승/1경기다.
호출 합계 819회, 사용량 누락 0회다. 비용은 실패 attempt를 포함하며 청구 금액은 산출하지 않는다.
Decision 지연 중앙값/p95는 IO 2.241/3.804초, minimax 14.060/25.895초다.

Minimax 유효 완료 2경기의 choose 전송 88회 중 outer search 예외 fallback은
74회(84.1%), 정상 damage-calculator 선택은 12회(13.6%)다. 보조 로그에서 이 74회의
`name 'depth' is not defined`를 확인했다. 실패한 2경기에도 같은 로그가 각각 21/26회
있지만 완료 조건부 fallback 분모에는 넣지 않았다. 이는 오류를 포함한 구현의 운영 결과다.

### 4시간 예산 평가

8판 전체 attempt 시간 합은 2668.752초, **44.5분**이다. Server 기동·종료와 실패 시간을
포함한다. 각 핵심 대진 2 slot의 평균을 8 slot으로 확장한 **32판 추정은 177.9분**,
**여유 50% 포함 266.9분(약 4시간 27분)**이다. 따라서 사전 지정한 4시간 예산 기준을
충족하지 않는다. 기존 EX-002 기반 139분/여유 포함 209분을 현재 조건의 시간으로 사용하면 안 된다.

새 8판의 50% 여유 포함 값은 약 66.7분이다. 이 수치도 다음 실행의 상한이 아니다.
팀/seed block 1개와 대진당 2 slot뿐이며, 출력 오류의 조기 중단을 포함한다. 요청 정리·retry,
경기 길이와 provider 변동으로 초과할 수 있고 정상 완료 32경기를 확보하는 시간은 아니다.
32판 설정 구현은 완료했지만 실제 32판은 실행하지 않았다. 4시간 내 안정적 반복 규모나
오류 수정 minimax 기준선은 이 실험으로 확정할 수 없다.

### 검증과 evidence

- 전체 integration 91 tests 및 변경 파일 Ruff E/F/I/W 통과.
- 새 plan, 8 match/16 actor source seal, 분석 코드 hash 검증 통과. 16개 viewer/replay 생성.
- 새 artifact 221개 credential 값 검사 통과. 기존 EX-002 40 match/80 actor seal은 불변이다.
- [보고서](../../../../.pokechamp-data/benchmarks/core-smoke-128k-300s-v1/report.md),
  [기계 판독 결과](../../../../.pokechamp-data/benchmarks/core-smoke-128k-300s-v1/report.json),
  [actor trace/replay 색인](../../../../.pokechamp-data/experiments/core-smoke-128k-300s-v1/index.html).
- 분석 source SHA256: `8a57ee955e5d31a61be918999510dd92d0c8a5925805ed89eff8fc66df469938`.
- 확증 팀은 사용하지 않았고 EX-002와 결과를 합치지 않았다. IO 완전 anchor block 1개,
  minimax 0개여서 분산 추정/CI/우월성·효능 claim은 없다.

- 최종 확인: 두 pinned submodule은 clean이며 port 8000 listener와 소유 server process가 없다.
