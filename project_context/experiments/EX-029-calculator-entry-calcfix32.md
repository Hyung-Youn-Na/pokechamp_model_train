# EX-029 — 계산기 교정 동일 조건 A/B32판

- 상태: Completed — 승인된 중단 포함 작업 완료; 32판 성능 비교 미완료
- 생성일: 2026-09-10
- 관련: D-034, EP-022, C-022

## 승인·범위

2026-09-10 사용자가 제공한 계획의 구현·필수 검증·검증 직후 추가 확인 없는 유료 A/B32판·전수 검토·보고를 승인했다.
계산기 인스턴스의 ability와 종 fallback을 함께 비워 clone 재적용을 막는다. 공유 종 데이터/설치 라이브러리,
@smogon/calc0.11.0+ruination-v1, EV/IV/prior/prompt/응답 schema는 유지하고 연결 source hash를 봉인한다.
원자료·주석·봉인 보고서·기존 Blocked는 보존한다.

## 검증·실행 조건

지정4턴의81–96/84–100 재현과120–142/126–148 교정, 공격186의132 roll 포함,
pinned Showdown16난수·관측+1/0/추가하락·최초등장·무특성/일반/기존억제특성·불변성과 실제 worker를 검증한다.
EX-028 B435입력을 재계산해 최초오염·변경입력·의존결과를 별도 정정 분석으로 무효화한다.
범위 입증 불가 시 기존 비교 전체의 유효성을 보류/무효 처리한다. pokechamp cwd 전체 integration 회귀,
변경 파일 정적 검사·Node문법·source/설정 검사를 통과해야 유료 진입한다.

새 정책 battle-guide-calcfix32-v1만 EX-029로 사용한다. 기존 정책 identity/hash/재수집 금지는 보존한다.
EX-028 원 manifest와 팀원문·진영·게임/actor seed·순서를 대조해32 slot 각1회 실행한다.
glm-5.3-flash/low/temperature0/seed100/출력131072/provider기본context,
요청300초/watchdog1200초/배틀·계정·모델최대10. A upstream IO/fallback,
B 필드설명서v1.1.0+교정계산기, 요약/통합/메모리주입0. Provider retry0/보충·추가재수집0,
전체 비용·시간·행동요청 상한 없음. Cloud90/smoke8/fake32/기존15장면gate는 skipped_by_user로 기록한다.
source/설정/prompt/대진·필수검증을 봉인한 뒤 즉시 본32판에 진입하고 수집 중 source/prompt 불변이다.

## 중단·복구·해석

C-018/RESEARCH_DESIGN §11.1을 적용한다. 합법JSON추출/첫합법후보 정책을 유지하고
provider/timeout/watchdog/경기별환경 실패는 해당경기만 종료한다. 공유입력/계산/설정/무결성 결함은 영향범위 중지,
불명확하면 잠재영향전체 중지한다. 새 실행에서 추가재수집0이며 이전 halt/시계/원장을 수정하지 않는다.
EX-028 원본실험/최초시계/원장을 참조로 연결하고 미확정1건 및 전후 누적사용량을 보존한다.

Codex가 B 수집설명 전부를 실제입력/교정계산/공개로그와 직접 대조한다. 별도 GLM 심사0.
사실·진영·시점·계산 오류 annotation,32경기목록/actor viewer의 출력오류·추출/fallback·전송·설명오류·실패를 제공한다.
자연종료/정상출력경기/상대별점수/동일가중평균/완료대응B−A/실패·누락·미확정/호출·token·시간·동시성을 보고한다.
전후 결과는 별도로 비교하며 독립 표본으로 합산하거나 B 우월성·L1–L5 효능으로 해석하지 않는다.

## 결과·완료 판정

**승인된 bounded 작업은 Completed, 32판 성능 비교는 미완료**다. 사용자가 완료 기준에
명시한 “32 slot 처리 또는 중단 사유 보존”과 수정·독립 검증·수집분 전수 검토·viewer·보고·정리를 충족했다.
이는 추가로 발견한 재등장 결함의 수정이나16쌍 비교 달성을 뜻하지 않는다.

clone fallback 오류는 worker 인스턴스에 국한해 수정했다. 지정4턴81–96/84–100은120–142/126–148로
교정됐고 실제 공격186의16 rolls에132가 포함된다. 독립 pinned Showdown 대조·반복 clone 및 입력/공유 데이터
불변 검증을 통과했다. EX-028 B435입력 모두 재현했고64입력/12경기 및 의존 비교를 별도 정정 분석으로 무효화했다.
원본 집계 성능 추정치를 유효한 결과로 사용하지 않으며 원자료·주석·봉인 보고서는 보존했다.

필수453회귀(189.78초), Ruff/Node15/compileall/source156/대진·설정 검증 뒤 추가 확인 없이 즉시 유료 실행했다.
수집 중 source/prompt를 변경하지 않았다. 별도15장면/fake32/Cloud90/smoke8은 skipped_by_user다.
실제 봉인 benchmark/experiment ID는 `ex-029-c0-compare32`이고 study는 `ex029`다.
중단 후 기본 ID 생성의 하이픈을 제거해 기존 DIRECT의 `ex028` 경로 동작을 복원했으며 실제 수집 identity는 보존했다.
사후 보고·기본 경로·정책 관련98회귀(66.40초)와 정적 검사를 통과했다.

| 항목 | 결과 |
|---|---|
| 예정/시도/미실행 | 32 / 20(모두1회) / 12 |
| 자연 종료/중단 | 10(A6·B4) / 10 |
| 재등장 입력 오염 | 38입력, B5경기와 대응 비교 무효; 자연 종료 B4 중2 영향 |
| 해당 결함 제외 유효 완료 | A6, B2; 유효 대응2/16, B−A0%p |
| A 상대별 유효 성적 | abyssal1승1패, one_step4승0패; 동일 가중0.75 |
| B 상대별 유효 성적 | abyssal0승1패, one_step1승0패; 동일 가중0.50 |
| 형식 오류 없는 자연 종료 | A6, B0; 입력 유효성과 별도 |
| B 설명 전수 검토 | 198/198, 오류128(64.65%); 무응답3 별도 |
| 설명 오류 차원(중복) | 사실41·진영2·시점26·계산99 |
| B 합법 선택/실제 전송 | 198 / 195; 중단 취소3 |
| 형식 처리 | 원형 정상177·합법 JSON 추출21·첫 합법 fallback0; A fallback0 |
| 새 HTTP 예약/응답/미확정 | 411 / 411 / 0; provider 장애·timeout0 |
| 새 확정 입력/출력 token | 14,845,383 / 94,677 |
| 수집 벽시계/HTTP 최대 동시성 | 536.138초 / 계정10·모델10 |
| 원본+후속 누적 예약/응답/미확정 | 1,210 / 1,209 / 1 |
| 누적 확정 입력/출력 token·수집 시간 | 49,201,922 / 303,541 / 1,565.245초 |
| 재시도/보충/GLM 심사 | 모두0 |

원본과 후속 결과를 독립 표본으로 합치지 않는다. A/B 유효 완료 집합도 달라 동일 가중 차이를
처치 효과로 해석하지 않는다. 유효 대응2쌍은 abyssal-b04-s0(양쪽 패), one_step-b02-s0(양쪽 승)뿐이다.
전체 비교는 미완료이며 L1–L5나 B 우월성 주장은 없다. 공급자 청구금액은 수집하지 않아 금액을 산출하지 않는다.
보고 시 원본 최초 Cloud부터 경과67,958.068초는 두 수집 사이의 공백과 사후 검토를 포함하므로 수집시간과 다르다.

## 새로 확인한 공유 결함과 중단

관측된 등장 특성의 clone 복구와 별개로, `own_spec`이 벤치 Pokémon의
`entry_effects_observed`를 false로 만들어 이미 소비한 Gen9 Dauntless Shield를
재등장 후보에서 다시 적용한다. 최초 등장+1, 교대 후 재등장0을 pinned Showdown16난수로 독립 확인했다.
B-one_step-b02-s1의10턴 설명 검토에서 발견해 `halt-c0.json`을 봉인하고 잠재 영향 cohort를 중단했다.
런타임의 이 재등장 결함은 **미수정**이며 재개·재시도·미실행12판 보충은 하지 않았다.
201입력을 로컬 재계산해 원본 수집 계산을 모두 재현하고, 소비된 특성만 분석용 사본에서 억제한 차이38건을 보존했다.

| 무효 B 경기 | 최초 오염(턴/결정/event) | 변경 입력 |
|---|---|---:|
| io-abyssal-b01-s0 | 4 / 5 / 34 | 9 |
| io-abyssal-b01-s1 | 5 / 6 / 41 | 13 |
| io-one_step-b01-s0 | 6 / 8 / 52 | 12 |
| io-one_step-b02-s1 | 9 / 12 / 81 | 2 |
| io-one_step-b03-s0 | 6 / 7 / 48 | 2 |

원기록의 provider3건은 cohort halt가 HTTP 전에 거절된 결과이며 실제 provider outage가 아니다.
interrupted7건과 미실행12판도 공유 중단의 파생 결과다. llm_call414건과 유료 HTTP411건을 구분한다.
응답을 받은 B3건도 경기 취소로 실제 wire에 보내지 않았으며 선택198과 전송195를 따로 보고한다.
`compare32/result.json`은 생성되지 않았고 실패 기록을 보존했다. 사후 `stop-outcome.json`은
중단·유효성 정정 artifact이며 통과 gate를 대신하지 않는다.

40 actor viewer와32경기 목록에 원출력 오류·추출/fallback·실제 전송·설명 오류·실행 실패를 표시하고,
중단 원인과 입력/대응 무효 banner를 추가했다. 원본 봉인 source·annotation은 변경하지 않았다.
40 actor seal·201입력·195합법 전송·원장/응답·52,353보호파일·기존6개 Blocked 불변,
소유 프로세스 종료·8000/8100–8109포트 반환·permit제거·원장 unlock·submodule clean·credential 비노출을 확인했다.

## 증거

- [최종 보고서](../../.pokechamp-data/battle-guide-calcfix32/ex029/report-final/report.md), [32경기 목록](../../.pokechamp-data/battle-guide-calcfix32/ex029/report-final/matches.html), [중단·유효성 정정](../../.pokechamp-data/battle-guide-calcfix32/ex029/report-final/stop-outcome.json)
- [필수 진입 검증](../exec-plans/evidence/ep022/qualification.json), [독립 Showdown](../exec-plans/evidence/ep022/independent-showdown.json), [EX-028 별도 정정](../exec-plans/evidence/ep022/ex028-correction.md)
- [새 결함 영향](../../.pokechamp-data/battle-guide-calcfix32/ex029/defects/reentry-impact.json), [재등장 독립 검증](../../.pokechamp-data/battle-guide-calcfix32/ex029/defects/reentry-independent.json), [전수 검토](../../.pokechamp-data/battle-guide-calcfix32/ex029/manual-review.json)
- [종료 검증](../exec-plans/evidence/ep022/final-verification.json), [최종 회귀](../exec-plans/evidence/ep022/regression-final.log), [사후98검사](../exec-plans/evidence/ep022/poststop-tests.log)
