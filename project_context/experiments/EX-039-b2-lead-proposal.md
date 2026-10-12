# EX-039 — B2 seeded_random 대 llm_lead 선봉 정책 대응 비교

- 상태: Stopped / 비교 미완료 — 사용자 지시로 실행·감시 종료, 미실행12경기 보존
- 생성일: 2026-09-14
- 승인: [D-053](../decisions/D-053-b2-lead-comparison.md), [EP-041](../exec-plans/active/EP-041-b2-lead-comparison.md)
- 관련: [D-052](../decisions/D-052-llm-lead.md), [EP-040](../exec-plans/completed/EP-040-llm-lead.md), [C-033](../CONTRACTS.md#c-033-llm-lead)

## 목적·조건

같은 EP-036 교정 이후 source의 B2에서 선봉 정책만 바꿨을 때의 승패·운영 비용 차이를 탐색한다.
개선 방향을 미리 가정하지 않는다. EX-038은 A 대 B2 중단 비교이며 과거 B 성적과 비슷한 부분 성적으로
B/B2 동등성이나 압축 효과를 입증하지 않는다. 과거 응답·성적은 새 결과에 합치지 않는다.

| 조건 | 선봉 | 전투 중 구성 |
|---|---|---|
| B2+seeded_random | actor Python RNG의 기존 shuffle, LLM 호출0 | 두 조건에 동일한 B2 관측/prior/계산·battle-v1.2.0/출력복구 |
| B2+llm_lead | 동일 shuffle 후 LLM 선택 슬롯만 앞으로 이동, 최초 요청 최대1 | 왼쪽과 같음 |

Gen9 OU singles, 기존 6마리 팀·기술·도구·특성·테라 유지. 모델은 현재 B2의
glm-5.3-flash/low/temperature0/model seed100/출력131072/provider 기본 context다.
요약·외부 메모리·별도 계산기·모델 심사0. 선봉 전용 prompt 버전/hash는 등록 시 고정한다.

## 표본·대응·제출 순서 — 승인·동결

**32경기/16대응쌍**을 수행한다. b01 팀1/2, b02 팀6/2, b03 팀2/6, b04 팀6/12에
각4게임 seed를 두고 같은 팀 위치·게임 seed·진영별 actor seed에서 조건/진영을 교환한2경기를 대응시킨다.
`team_preview_study.schedule()`은 새로운 `SHA256(20260914:D052:<label>)` namespace에서
게임/actor seed와 제출 순서를 생성한다. EX-038의 팀/seed/결과를 재개하지 않는다.
준비 파일에 실제32행·팀 원본/hash·조건 배정·seed·순서를 봉인한다.

b02/b03은 같은 팀 조합의 방향 반전이며32개 독립 전략 표본으로 세지 않는다.
같은 게임 seed라도 선봉 변경 이후 난수 소비와 전개는 달라질 수 있다.
개발 팀 표본의 탐색적 비교이며 일반 Gen9 OU 모집단·L1–L5 효능으로 확대하지 않는다.
정밀도나 검정력 보장은 없고 자동 채택 승률 기준도 없다.

## 지표와 분모

- 조건별 승률은 승/유효 종료 경기, 무승부 반영 점수는 `(승 + 0.5×무)/유효 종료 경기`다.
  총계와 팀 block·실제 진영별 값을 함께 보고한다. 선봉 실패는 상대 승리·무승부·정상 선발로 집계하지 않는다.
- 완료 대응쌍은 양쪽 경기 모두 유효 종료한 쌍이다. 각 쌍의 LLM 조건 점수 평균을 구하고 완료쌍에 같은 가중을 준다.
  완료쌍 수/예정16쌍, 각 미완료쌍의 경기 상태·누락 이유, 개별 유효 결과를 함께 보존한다.
  실패를0점 대입하거나 미완료쌍의 정상 경기만으로 완료쌍을 구성하지 않는다.
- 예정/시도/유효/실패/무효/미실행을 경기·조건별로 보고한다. `예정=시도+미실행`,
  종료 후 `시도=유효+실패+무효`를 대조하고 미확정/진행 중은 별도 표시한다.
- 선봉은 요청예정/예약/HTTP시도/응답수신/출력유효/실제전송/선발실패/미실행을 별도로 센다.
  실패 종류는 입력·매핑/출력/timeout/provider/예산/취소/전송/증거무결성을 구분한다.
  중복 이벤트 수와 재호출0·재전송0도 검증한다.
- 선봉·self_action별 호출/token·확정 비용·미확정 사용량, permit 대기·HTTP 및 결정 전체 지연의
  중앙값/p95/최대, 전체 경기/배치 시간과 유효 완료율을 보고한다. 선봉 한 번 때문에 발생하는 추가 비용과
  이후 전개 변화에 따른 배틀 호출량 차이를 구분한다. 금액 상한은 사용자 후속 지시로 제외한다. provider 확정 과금과 추정 비용을 혼동하지 않는다.
- C-032에 따라 설명 오류 사후 annotation은 기본 제외이며 설명 정확성·전략적 최적성은 미평가다.
  본문·reasoning·기술 IO/정보 경계·실제 전송 검증과 보존은 계속 수행한다.

## 요청·시간 상한 — 승인·동결

양쪽 actor 합계 **8000요청**, 최초 유료 요청부터 신규 수집 **20700초**/정리 **21600초**,
경기 watchdog3600초, HTTP `min(300초, 남은 수집시간)`, 배틀·계정·모델 동시성8을 적용한다.
현재 사용자 지시 D-053이 실제 Cloud 수집을 승인한다.
사용자가 후속 메시지로 금액을 고려 대상에서 제외했으므로 **금액 상한 없음**이다. 요청/시간 중 먼저 도달하는 상한을 적용한다.
비용은 보고용이며 provider 확정 비용·token 기반 추정·미확정 사용량을 구분한다.

32경기가 각 한 번 시도되면 선봉 최초 호출은 최대32건이며 총8000 안에 포함된다.
행동 호출에7968을 미리 보장하는 것은 아니다. 실패·미확정·모든 HTTP 예약은 공통 상한을 소비하고
선봉이 최초 호출이면 그때 전체 시계가 시작한다. 별도 유료 smoke는0이다. 첫 제출 슬롯의 대응쌍2경기는 본32와 동일 원장·최초 시계·상한 및 분석에 포함한다.

## 실행 전 등록·진입 조건

1. 새 실험의 명시적 승인, EX identity·원장 위치·최초 시계의 영속 binding, 표본·금액 상한 제외/요청/시간 상한.
2. 최종 source 파일별 hash·두 submodule pin, runtime/계산기/B2/선봉 prompt identity, 실제 모델 설정.
3. 전체 일정·팀 파일 hash·조건/진영/게임/actor seed·실제 요청 role/ID 연결, 모든 경기/actor bundle 위치.
4. 로컬 evidence와 source 일치 검증. 첫 제출 슬롯 `b03-r3-s0`와 대응 슬롯 `b03-r3-s1`을 먼저 실행한다.
   두 경기 모두 유효 종료하고 정보 경계·엄격 선봉 출력·실제 /team·최초 출전·B2 입력/검증·원장/trace/viewer·permit 반환을 통과해야 한다.
   승패·설명 정확성·전략 판단은 gate 기준이 아니다. 기존 B2 전투 출력복구의 합법 결과는 허용한다.
   통과하면 나머지30행을 원래 상대 제출 순서로 진행한다. 실패하면 후속30은 미실행이며 유료 재시도0이다.
5. 실행기 one-shot 제출·중복 거부·양쪽 요청 원장·실패 분모·viewer·종료 정리 확인과 수집 승인 연결.
   EP-041의 `team_preview_run`이 단계 실행·보고를 제공한다. Cloud 준비 파일은
   `execution_authorized=false`로 준비 시점을 봉인한다. 명시적 후속 승인 후 `register_execution`은
   등록된 EX/승인 근거의 hash와 최종 source·예산을 별도 execution-registration 및 전역 study binding에 연결한다.
   등록 부재·변조·다른 폴더의 시계 초기화는 actor/원장에서 거부한다. 최종 검증 후 EP-041에서 등록한다.
   동일 backend·원장·actor 실행 경로를 후속 bounded 실행 plan에서 사용하며 승인 자체를 자동 생성하지 않는다.

## 중단·복구 — 승인·동결

[C-018](../CONTRACTS.md#c-018-recovery)과 [RD §11.1](../RESEARCH_DESIGN.md#defect-recovery)을 적용한다.
개별 선봉 출력/timeout/provider·전송 실패는 해당 경기 실패로 격리하고 보충/모델 재질의/대체 호출은0이다.
공유 입력·매핑·계산·설정·permit·원장·무결성 결함은 잠재 영향 범위의 신규 제출을 멈춘다.
영향 범위를 모르면 전체 수집을 중단한다. 이미 진행 중인 요청의 응답/미확정·원장·permit을 보존·정리한다.

유료 재시도/재수집 허용 한도는 **0**이다. 영향 실행과 의존하는 대응 비교를 무효 표시하고,
실험 도중 source/prompt/기준을 교체하거나 남은 예산으로 새 폴더에서 재개하지 않는다.
수정이 필요한 경우 당시 evidence/halt/최초 시계/누적 사용량을 보존하고 별도 로컬 재현·독립 검증·회귀 후
새 승인으로만 후속 수집을 등록한다. 향후 재수집을 허용한다면 복구 단위는 최소 영향 대응쌍 양쪽이며 공유 영향 전체를 포함한다.
현재 준비에는 선택적 유료 재수집/자동 복구가 없다. 평가 구현 결함은 온전한 양쪽 응답을 같은 사전 기준으로
재평가하고, 평가 기준 변경은 별도 사후 수정 분석으로 원문과 연결한다.

## 현재 결과 — 제출분 종료·후속 보류

사용자 후속 지시로 이미 제출된20경기는 모두 종료했고 미제출12경기는 실행하지 않은 채 사용자 지시로 실행·감시를 종료했다. **유효17·전투 ReadTimeout 실패3·무효0·미실행12**, 완료 대응쌍4/16이다. LLM 선봉3승0무14패(승률17.65%), 무작위 선봉14승0무3패(82.35%)이며 완료쌍 동일가중 LLM 점수0.25다. 전체 비교는 미완료다.

[부분 보고서](../exec-plans/evidence/ep041/held-report.md) · [정정 보고 연결](../exec-plans/evidence/ep041/held-report-correction.json) · [독립 대조 감사](../exec-plans/evidence/ep041/held-reconciliation-audit.json) · [부분 manifest](../exec-plans/evidence/ep041/held-manifest.json).

최초 평가기의 추출/실행 행동 비교 오류가 기존 B2의 합법 first_legal_fallback을 거부해3경기를 무효 표시했다. 당시 보고를 보존하고 사전 기준을 유지한 offline evaluator로 해당3경기·4복구 사례를 재검증했다. 정정 후 기술 오류0이며 live source·처치·평가 기준·원자료 변경 및 추가 Cloud 호출은0이다. [정정 근거](../exec-plans/evidence/ep041/output-recovery-evaluation-correction.json)를 참조한다.

총1478요청/1475응답·미수신3건은 모두 공통 원장에 남아 있다. 선봉20응답은 모두 엄격유효·전송 성공이며 두 조건40 actor의 선봉/최초 출전 일치를 확인했다. C-032 설명 annotation은 수행하지 않았고 설명 정확성·전략적 최적성은 미평가다. 과거 성적과 fake 결과를 합치지 않는다.

첫 b03-r3 대응쌍 기술 gate는 통과했고 본 분모에 포함한다. [gate](../../.pokechamp-data/b2-lead/ex039/first-pair-check.json), [실행 봉인](../exec-plans/evidence/ep041/execution-freeze.json), [승인 근거](../exec-plans/evidence/ep041/execution-approval.json), [최초 시계](../../.pokechamp-data/b2-lead/ex039/cloud-clock.json), [동결 protocol 사본](../exec-plans/evidence/ep041/EX-039-frozen-protocol.md)을 보존한다.

### 사용자 종료 지시·미완료 범위

계정 사용량 관측 후 신규 제출을 보류했고, 이후 사용자가 감시도 모두 종료하도록 지시했다. 이에 보류 coordinator·deadline guard·프로세스 observer를 모두 종료했다. 신규12경기 제출·추가 Cloud 요청·공급자 설정 변경은0이다. [종료 기록](../exec-plans/evidence/ep041/closure/report.md)과 [자원·증거 감사](../exec-plans/evidence/ep041/closure/shutdown-audit.json)를 참조한다.

원본 halt의 integrity 표기는 종료용 KeyboardInterrupt를 실행기의 공통 예외 처리기가 분류한 값이다. 연구 입력/계산 무결성 결함으로 새로 판정한 것이 아니며 원본 값은 변경하지 않았다. 실제 원인은 보존된 사용자 전체 종료 지시다. 제출 전 대기 중이던 dispatch는 실제 시도에 포함하지 않는다.

최초 시계·누적 원장과 기존 부분 보고서를 보존하며 자동 재개하지 않는다. 유효32/완료16 기준을 충족하지 못했으므로 EP-041은 Blocked이며 Completed가 아니다. 공급자 설정 조정은 아직 수행하지 않았다.
