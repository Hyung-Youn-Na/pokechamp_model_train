# D-038 — 수정 완료본 A/B32판 새 실행

- 상태: Accepted
- 날짜: 2026-09-11

## 승인·고정 조건

2026-09-11 사용자가 제공한 새 세션 계획의 구현·유료 A16/B16 새 실행·전수 검토·보고를 명시적 승인으로 기록한다.
Weather Ball 수정 완료 EP-025 source171개를 기준으로 EX-032를 새로 실행한다.
Abyssal/OneStep × b01–b04 × 양쪽 × A/B=32판, EX-028 봉인 팀 원문·진영·게임/actor seed·실행 순서를 유지한다.
A upstream IO/fallback, B 수정 계산기+calculator-input-v2+battle-v1.2.0+mechanics-v2다.
glm-5.3-flash/low/temperature0/seed100, 출력131072/provider 기본 context,
배틀·계정·모델 동시성 각각 최대10, 요청300초/watchdog1200초다.
요약·통합·메모리 주입·provider retry·보충·재수집0, 전체 비용·시간·행동 요청 상한 없음.
경로 .pokechamp-data/battle-guide-movefix32/ex032, 형제 ex032-prepared,
benchmark ex032-c0-compare32, cohort c0를 사용한다.

## 범위·검증

parent integration 정책과 실행 연결·테스트·새 증거·control plane만 변경한다.
새 battle-guide-movefix32-v1 및 calculator-move-name-independent-regression-v1을 추가한다.
EP-025의593회귀·독립28조건×16roll·81입력 재생은 반복하지 않고 봉인·기준 source 일치를 확인한다.
새 qualification은 기준 검증과 변경분 검사를 분리해 연결하며 최종 source 전체 재검사로 표시하지 않는다.
정책 hash 보존, 새 identity의 준비→실행→actor→실제 B요청 전달,
변조·구버전·source 불일치 거부,32 slot·설정·격리·과거 자체 사용량 중복 없는 연결,
변경파일 정적 검사·최종 source/config/manifest 무결성을 검사한다.
예상 밖 source 차이는 영향 확인 후 필요한 검사만 추가한다.
계산기·입력 생성·프롬프트·prior·설치/submodule은 유지한다.
필수 연결 검사·봉인 뒤 별도 fake32/Cloud90/유료smoke8 없이 compare32에 진입한다.
생략 단계 통과 receipt는 만들지 않으며 같은 승인 조건을 재확인하지 않는다.

## 실행·중단·해석

32 slot 각각1회, 수집 중 source/prompt/config 고정. B 정상 계약 뒤 유일 합법 JSON→첫 합법 후보,
원출력·복구·전송을 구분한다. 추가 호출0. 출력·설명 오류는 기록하고 계속한다.
provider/timeout/watchdog/경기별 환경 실패는 해당 경기만 종료한다.
공유 입력/계산/설정/무결성 결함은 영향 범위를 중지하고 불명확하면 잠재 영향 전체를 중지한다.
C-018/RESEARCH_DESIGN §11.1을 적용하며 수집 결함은 경기·의존대응 무효, 자동수정 후 재수집/보충0이다.
증거·영향·중단 사유는 evidence/ep026 및 ex032/defects에 보존한다. 기존6개 Blocked와 과거 원자료/보고/원장/시계/halt는 보존한다.
B 수집 설명 전체를 실제 전달 입력·계산·공개 로그에 직접 대조하며 사실/진영/시점/계산/입력유발 오류를 분리한다.
추가 모델 심사0.32경기 목록·actor viewer에 상태/문제 턴/원출력·복구·전송·근거를 제공한다.
상대별(승+0.5×무)/유효완료, 동일가중 평균,완료대응 B−A와 예정/시도/유효완료/실패/무효/미실행/미확정/누락을 보고한다.
호출/token/시간/실제동시성과 EX-028/029/031 각각 자체 사용량+EX-032 누적을 보고하며 기존 미확정1건을 유지한다.
과거 무효 성능을 합산하거나 계산기 단독 효과/L1–L5 효능으로 해석하지 않는다.

## 완료 기준

- [x] 기준 source·과거 증거 일치, 변경분 검사·새 qualification·실행 manifest 봉인.
- [x] 32 slot 각1회 실행 또는 중단·미실행 사유 보존.
- [x] 수집분 전수 검토·viewer·실제분모 보고·source/원자료 보존·프로세스/포트/permit/원장 lock 정리·문서 갱신.
성능 비교 완료는 유효32판·16대응에만 표시한다. 중단 처리 완료와 비교 완료를 구분한다.

## 실행 근거와 한계

EX-032는 공유 permit 반환 실패로16시도에서 중단됐고 수집분 검토·보고·정리를 마쳤다.
유효6판/1대응이므로 성능 비교 완료로 표시하지 않는다. 기존 permit 코드는 변경하지 않았다.
원인·영향과 검증 범위는 [EP-026](../exec-plans/completed/EP-026-battle-guide-movefix32.md),
[최종 보고서](../exec-plans/evidence/ep026/report.md)를 따른다. 본 기록은 실패 처리나 완료 기준을 완화하지 않는다.
