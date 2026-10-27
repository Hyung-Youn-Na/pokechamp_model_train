# EP-028 — Smogon 기반 원본 A 진단 평가 준비

- 상태: Completed — 평가 준비 구현·로컬 검증 완료, 대전 미실행
- 생성일: 2026-09-11
- 책임자: Codex
- 승인 근거: 현재 사용자가 전달한 팀 선별·대진·평가·자원 산정 계획의 구현 및 검증 지시.
- 관련: EX-033, C-008/C-009/C-018/C-021, 신규 D-040 및 EX-034 설계 기록.

## 목표·범위

Smogon Sample Teams와 Tournament Team’s Bazaar에서 과제별3개 후보(총12), 선정8팀(탐색4/후속확인4),
탐색64 slot 및 행동 검토·자원 산정·실행기 gap을 재현 가능하게 문서화한다.
허용 변경은 project_context의 새 문서·원본 팀 data·로컬 검증 evidence 및 관련 index/상태다.
공개 API·실행 코드·prompt·모델·기존 팀·submodule 변경, 유료 호출·대전은 제외한다.

## 맥락·불변 조건

CHARTER/INDEX/RESEARCH_DESIGN/CONTRACTS와 active EP-020/018을 확인했다.
다른 active EP-011/012/013/015는 IO/요약 gate 진단으로 이번 A 단독 팀 평가 준비와 실행 범위가 다르다.
기존6개 Blocked는 유지한다. EX-033 A upstream IO/fallback과 고정 환경을 기준으로 사용한다.
전략 해설은 모델 입력에 주입하지 않는다. 패배나 선정자의 난이도 추정으로 한계를 확정하지 않는다.

## 완료 기준

- [x] 12팀 비교 및 선정8팀의 출처/작성자/수집일/원본/hash/운용 근거/불확실성.
- [x] 고정 Gen9 OU 합법성, 완전성, 동일/유사 변형 및 기존 팀 차별성 검증.
- [x] 64 slot의 두 정책·양쪽 팀 배정·반복별 게임 seed/진영·고정 순서/seed 검증.
- [x] 모든 A 행동 전수검토와 분모·실패/복구·후속 가설 기준.
- [x] EX-033 A만의 요청/token/시간 추정과 장기전 민감도, 실행기 지원 차이.
- [x] 설계/decision/experiment 등록·검증 evidence·상태 갱신.

## 검증

팀 원본 및 canonical set hash, pinned Showdown TeamValidator, 독립 matrix 집계,
EX-033 actor별 사용량 대조, baseline/source 보존 hash, 문서 link 검사를 사용한다.
검증 도구는 evidence 안의 로컬 전용이며 실행기 기능을 추가하지 않는다.

## 중단·복구

이번 단계는 비실험 문서/로컬 검증 작업으로 Cloud/대전0, 재수집0이며 유료 시계는 시작하지 않는다.
후속64경기 기본안은 slot당1회, provider retry/보충0, C-018 영향 범위 중단/불명확시 잠재전체 중단이다.
후속 실행 승인·누적 예산 및 실행기 지원은 별도 확정 대상이며 EX-033의 무상한 승인을 상속하지 않는다.
충돌·누락은 INDEX 승인 절차에 따라 영향 범위만 보류하고 원자료를 보존한다.

## 진행·증거

- 2026-09-11 — 사용자 지시로 신규 등록. 기존 실행 코드/6개Blocked/EX-033 evidence 해시 보존.


## 결과 및 증거

후보12팀(과제별3), 선정8팀(탐색S1/H1/R1/W1·후속확인S2/H2/R2/W2)의 원형과 provenance를
[EX-034](../experiments/EX-034-smogon-diagnostic-design.md)에 기록했다. 원본12팀 모두6마리/24기술의
pinned Gen9 OU 합법 구성이다. 선택8팀과 기존13팀의 동일 canonical 팀0·5마리 이상 공통 변형0,
선정8 내부 최대 공통3마리를 확인했다. Community 평가·연구자 판단·미확정 근거를 구분했다.

탐색64행은32개 세부 셀×반복2이며 A p1/p2 각32, 각 셀 양진영·서로 다른 게임 seed,
게임 seed64/actor seed128개 유일·model seed100·worker root100×4다. 원본 팀 해시,
후속확인 미포함, CSV/JSON 동등성 및 생성 도구 바이트 재현을 검증했다.

A 사용량은 EX-03316 actor/457요청의 실제 입력 설정과 원장/응답/hash/token을 대조했다.
기본64 추정1,828요청·입력3,813,620/출력217,232token이며 시간/장기전 감도와 watchdog의
유효완료 제약을 분리했다. A476결정에서 유추한 검토량과 무호출 행동의 분모도 명시했다.
전수검토 기준은 실제 입력/출력/전송/public prefix, 판단/입력/실행 실패·미확정, 승리 실수,
노출 기회·반복 사건과 보류 팀의 후속 가설을 포함한다.

실행기는 고정1–13팀과 기존32표/A/B 조건에 연결되어 있어 외부 팀·A-only64 입력을 지원하지
않는다는 source 근거와 필요한 변경을 문서화했다. 공개 API·실행기 구현·유료 호출·배틀0이다.
원본 A source173개·기존6개 Blocked·기존 파일4,223개와 양 submodule pin/clean을 보존했다.

| 검사 | 재현 명령 / 근거 | 결과 |
|---|---|---|
| 합법성·완전성·중복 | `node project_context/exec-plans/evidence/ep028/validate_teams.cjs` | 후보12/선정8 합법; 기존13 대조; loaded32 compiled source map 일치 |
| A 사용량·실제 baseline | `python project_context/exec-plans/evidence/ep028/measure_a.py` | 16 actor·457 intent/response 대조; A 설정/원출력/token 일치·source173 보존 |
| 대진 data 생성 | `python project_context/exec-plans/evidence/ep028/build_schedule.py` | 64행·seed·제출순서·CSV/JSON 고정; 실행 기능 없음 |
| 최종 독립 검증 | `python project_context/exec-plans/evidence/ep028/verify.py` | 33개 준비 검사 통과, 문서 lifecycle/링크 확인 |

[팀 검증](../../../exec-plans/evidence/ep028/team-validation.json), [A 집계](../../../exec-plans/evidence/ep028/a-usage.json),
[최종 검증](../../../exec-plans/evidence/ep028/verification.json), [원본 보존 inventory](../../../exec-plans/evidence/ep028/preservation-before.json).
원본 `.txt`는 provenance 바이트 보존을 위해 CRLF·trailing space를 유지한다. 이 파일을 코드
format 검사로 재작성하지 않는다. 실행 코드 변경이 없으므로 배틀 회귀/Cloud gate를 새로 실행하지 않았다.

초기 독립 검증은 validator가 생략 성별을 `Math.random()`으로 채워 canonical hash가
변하는 결함을 발견했다. 원문 성별/미지정을 해시로 보존하도록 **검증 도구만** 교정했고,
원본팀/legality는 바꾸지 않았다. [초기 결과](../../../exec-plans/evidence/ep028/verification-initial.json)와
[교정 후](../../../exec-plans/evidence/ep028/verification-preclosure.json)를 보존했다. 최초 측정 도구의 원장 경로를
객체로 읽은 schema 가정도 실제 문자열 path/sidecar 방식으로 교정했으며 수집에 영향은 없다.
전체 bitwise 실행 재현은 provider·기존 성별 정규화의 별도 무작위성 때문에 주장하지 않는다.

확인한 replay9개 중8개는 공개 로그 형식에 접근했고 W2 링크1개는404다. W2는 상세 RMT/원형
구성으로 선정했으며 전체 replay 분석/숨겨진 EV 재현/새 성능 검증으로 표시하지 않았다.
이 완료는 재현 가능한 평가 준비의 완료다. 현재64경기의 예정/시도/유효/실패/무효/미실행은
64/0/0/0/0/64이며 이후 실행 승인·구현을 미완료 요구사항으로 이 plan에 상속하지 않는다.
