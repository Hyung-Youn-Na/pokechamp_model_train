# EX-028 — 사전 검증 생략 32판 비교

- 상태: Completed — 32 slot 처리 완료, 16쌍 비교 미완료
- 생성일: 2026-09-09
- 관련: [EP-021](../plans/EP-021-battle-guide-direct32.md), [D-033](../decisions/D-033-battle-guide-direct32.md).

## 사전 등록

A는 EX-027의 upstream IO·fallback, B는 교정 관측·고정 prior·계산기·필드 설명서 v1.1.0이며 요약·통합·메모리 주입0이다.
모델 glm-5.3-flash, thinking low, temperature0, seed100, 출력131072, provider 기본 context,
요청 timeout300초·watchdog1200초·배틀/계정/모델 요청 최대10을 유지한다.
EX-027/EX-016 개발팀·게임 seed·Abyssal/OneStep×b01–b04×양쪽16대진의 A/B32판과 순서 seed20260908을 고정한다.

명시적 battle-guide-direct32-v1에서만 사전 회귀·15장면·fake32·Cloud90·smoke8을 skipped_by_user로 기록하고
설정·source·prompt·대진 봉인 후 compare32에 직접 진입한다. 생략한 gate 통과 receipt는 만들지 않는다.
전체 비용·시간·행동 요청 상한은 없고 provider retry·추가 재수집은0이다. 기존32 slot을 각1회 시도한다.
최초시계·원장·미확정과 사용량을 보존하며 수집 중 source/prompt를 수정하지 않는다.

B는 기존 출력 계약을 먼저 적용한다. 실패하면 원문에서 유일한 JSON 객체 행동을 중복 키 거부와
정확한 후보·강제교체·테라 조건으로 검사해 추출한다. JSON 없음/복수/중복 키/불법이면 봉인된 후보의
첫 행동을 사용한다. 원출력 판정·추출 행동·실제 실행 행동·선택 출처를 별도로 기록하며 재호출하지 않는다.
출력·설명 오류는 계속한다. Provider·timeout·watchdog·경기별 환경 실패는 해당 경기만 종료한다.
합법 후보 부재·공유 입력/계산 결함·설정 불일치·증거/격리 무결성 문제는 영향 범위를 중지한다.
범위 불명확은 잠재 영향 전체를 중지한다. C-018의 증거 보존·영향 분석을 적용하되 재수집0이며
기존 EX-027 및 다른 실험의 원자료·halt·시계·Blocked는 변경하지 않는다.

Viewer는 문제 턴 수·완료/실패·문제 목록·battle/actor/decision 링크를 제공한다.
출력 형식 오류/행동 추출/대체 행동/설명 오류/실행 실패를 텍스트와 색으로 구별하고 원문·오류·추출/전송 행동을 표시한다.
B 수집 설명은 원문·실제 입력·계산/공개 근거에 사후 전수 대조하고 사실·진영·시점·계산 오류를 별도 봉인 annotation으로 연결한다.
검토 전은 미검토다. 원자료를 수정하지 않는다.

자연 종료·실제 행동/입력/증거가 온전한 경기는 대체 행동·오류 표식을 포함해 성적에 포함한다.
정상 출력만 있었던 경기 수, 상대별 (승+0.5무)/유효완료, 두 상대 동일 가중 평균,
완료 대응 B−A·누락/실패/미확정·A/B fallback·호출/token/시간/동시성을 보고한다.
오류 처리 정책을 포함한 전체 구성의 개발 대진 탐색 비교이며 설명서 단독 효과나 L1–L5 효능으로 해석하지 않는다.

## 증거·결과

독립 `.pokechamp-data/battle-guide-direct32/ex028` 및 `ex028-c0-compare32` benchmark/actor 저장소에서 실행했다. 사전 테스트0이다.

2026-09-09: 준비/등록 후 본32판에 직접 진입했다. 사전 회귀·운영15/사후3·fake32·Cloud90·smoke8은 모두 skipped_by_user다.


## 최종 결과 — 2026-09-09

32개 slot을 각1회 시도했고31판이 자연 종료했다. B-io-abyssal-b04-s0는6번째 행동 요청의
300초 timeout으로 종료했으며 나머지 slot은 계속 처리했다. 미실행0·전체 중단0·재시도0·재수집0이다.
실패한 경기의 결과는 확정되어 있으나 해당 provider 요청의 실행·token·청구는 미확정1건으로 보존한다.
완료 기준인32 slot 처리·전수 검토·viewer·검증·정리는 충족했으며16쌍 성적 비교는15쌍으로 미완료다.

| 조건 | Abyssal 승/패/무 | OneStep 승/패/무 | 유효 완료 | 두 상대 동일 가중 점수 |
|---|---|---|---:|---:|
| A | 6/2/0 | 7/1/0 | 16 | 81.25% |
| B | 7/0/0 | 7/1/0 | 15 | 93.75% |

완료 대응15쌍의 평균 B−A는+0.133333(+13.33%p)이다. 누락은io-abyssal-b04-s0 한 쌍이다.
개발 대진·실패 제외·전체 구성 및 오류 처리 정책을 포함한 탐색 비교이므로 설명서 단독 효과나
일반적인 우월성·L1–L5 효능의 증거로 해석하지 않는다.

### 출력·행동·설명

- 정상 출력만 있었던 유효 경기: A16/16, B0/15. 출력 오류가 있는 자연 종료 경기도 성적에 포함했다.
- A 실제 fallback0/367전송 결정, 추가 모델 호출0. 364회 Cloud 호출 외3회는 upstream의 직접 결정이다.
- B 출력 원문434건: 원계약 정상389, 형식 오류45. 오류45건 모두 유일한 합법 JSON을 추출해
  같은 결정을 실행했다. 첫 합법 후보 fallback0. 실제 전송은정상389+추출45이며 원계약 실패는 보존했다.
- B 원문434건을 전수 수동 검토했다. timeout1건은 무응답으로 검토 기록하되 설명 오류율에서 제외했다.
  하나 이상 설명 오류181/434(41.71%); 사실58·진영3·시점38·계산114건이며 차원은 중복된다.
  최대 피해가 현재HP보다 작은데 확정 KO라고 하는 계산, 우선도 기술보다 먼저 움직인다는 주장,
  Future Sight 진영·해결 시점, Snow·혼란·타입 상성 규칙 오류 등이 포함된다.
- 판정은 해당 원문의 명시적 주장과 그 요청의 입력·가설 계산·공개 사건·고정 Gen9 규칙을 대조했다.
  기술 선택의 최적성, 주장하지 않은 조건의 누락, 나중 경기 결과로 거슬러 올라간 정답은 평가하지 않았다.
  각 행에 event·decision·원문 hash·요청/응답 hash와 근거를 기록하고16개 actor annotation을 봉인했다.

### 자원

| 조건 | 요청/원문 응답 | 확정 입력 token | 확정 출력 token | HTTP 누적 초 |
|---|---:|---:|---:|---:|
| A | 364/364 | 721,518 | 39,064 | 2,216.633 |
| B | 435/434 | 33,635,021 | 169,800 | 5,903.528 |

수집 벽시계1,029.107초(17.15분), 배틀·계정 HTTP·모델 HTTP 실측 최대 동시성은 모두10이다.
전체799요청·798응답, 확정 입력34,356,539/output208,864 token이다. 미확정 timeout의 사용량은
0으로 채우지 않았다. Provider 청구 금액 근거가 없어 금액은 산출하지 않는다.

### 검증·보존

- 수집 후 기존+신규442개 test 사례 검증: 처음433통과/9실패는 upstream static 상대 경로를
  `/workspace`에서 실행한 영향이었다. `/workspace/pokechamp`에서 같은9개가 모두 통과했다.
- 보고 집계/새 파일 style 정리 후 관련69개 test 통과. 최종 보고서는 실제64 bundle·435입력·
  434합법 행동/실제 전송·799요청 원장과 독립 대조했다. HTML66개·로컬 링크594개 검증 통과.
- 새4개 파일 Ruff E/F/I/W 및 compileall 통과. 초기 패키지 전체 Ruff에서 기존 파일 포함955개
  지적을 발견했고 전부 정리하지 않았으므로 전체 lint 통과로 보고하지 않는다. 원래 실패 로그와 작업 경로 교정 로그를 보존했다.
- 수집 종료 직후 current/source 일치를 확인하고 이후 보고 집계·style만 변경했다.
  수집 당시 source·prompt archive·원자료·실패는 그대로이며 재수집하지 않았다.
- 사전 hash47,970파일 중 기존 개별 원자료/plan47,969개 불변. 새 실험 등록을 위해 허용한
  `project_context/experiments/INDEX.md`만 변경됐다. 기존 EX-027 및 Blocked plan은 불변이다.
- B16 runtime의 계산기 종료·메모리 archive/요약0,64 actor 봉인, owned PID 종료,
  8000/8100–8109 port 해제, permit directory 제거와 ledger lock 해제를 확인했다.
  Submodule clean이며 새 산출물4,412파일에서 실제 credential 비노출을 검사했다.

### 산출물

- [32경기 목록 및 actor viewer](../../../../.pokechamp-data/battle-guide-direct32/ex028/report-final/matches.html)
- [최종 보고서](../../../../.pokechamp-data/battle-guide-direct32/ex028/report-final/report.md) · [기계 판독 지표](../../../../.pokechamp-data/battle-guide-direct32/ex028/report-final/report.json)
- [봉인 전수 검토](../../../../.pokechamp-data/battle-guide-direct32/ex028/manual-review.json)
- [실행 결과](../../../../.pokechamp-data/battle-guide-direct32/ex028/compare32/result.json) · [실행 source](../../../../.pokechamp-data/benchmarks/ex028-c0-compare32/source)
- [독립 종료 검증](../../../exec-plans/evidence/ep021/verification.json) · [검증 로그](../../../exec-plans/evidence/ep021/closure-v3.log)
