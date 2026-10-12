# D-036 — 교정 입력·계산기 동일32판

- 상태: Accepted
- 날짜: 2026-09-10

사용자의 명시적 새 실행 지시로 EX-030 로컬 범위와 별도 EX-031을 승인·등록한다.
기존 정책과 과거 실험 상태는 보존한다. 상세 조건·승인·완료 기준은
[EP-024](../exec-plans/completed/EP-024-calculator-inputfix32.md)를 따른다.

## 승인·조건·범위

2026-09-10 사용자 제공 계획 전체의 구현·검증·유료 새 A16/B16·전수 검토·보고를 승인 근거로 한다.
EX-030 교정본의 calculator-input-v2 / battle-v1.2.0 / mechanics-v2를 B에 적용한다.
A upstream IO/fallback, EX-028 봉인 팀원문·진영·게임/actor seed·실행순서32 slot을 그대로 새 실행한다.
Abyssal/OneStep × b01–b04 × 양쪽 × A/B. 모델 glm-5.3-flash/low/temperature0/seed100,
출력131072/provider 기본 context, 배틀·계정·모델 최대10, 요청300초/watchdog1200초다.
요약·통합·메모리주입·provider retry·보충·추가재수집0. 전체 비용·시간·행동 요청 상한 없음.

새 정책 battle-guide-inputfix32-v1과 qualification calculator-input-audit-independent-regression-v1을 추가한다.
정책별 prompt 버전과 calculator_semantics_version/runtime_patch_identity를 준비→실행→actor→실제 요청에 봉인·검사한다.
새 최종 source 검증 receipt를 발급하며 과거 receipt/hash/정책/원자료/주석/보고서/halt/원장/6개 Blocked를 보존한다.
경로 .pokechamp-data/battle-guide-inputfix32/ex031 및 ex031-prepared, benchmark ex031-c0-compare32, cohort c0다.
EX-028/029의 사용량을 각각 한 번만 누적하고 최초시계·기존 미확정1건을 참조한다.
parent integration·테스트·control plane만 변경하며 canonical submodule/설치 라이브러리/prior는 보존한다.

## 검증·실행·해석

pokechamp cwd 기존519 integration 및 새 정책/버전/manifest/대진/보고 회귀를 실행한다.
로컬 fake 응답으로 v2 이력/계산/설명서 전달, p1/p2 격리·동시성·변조/구버전/source 거부를 검증한다.
EX-030 독립 검증/636재생을 해시 확인하고 관련 입력·계산 코드 변경 시 영향 독립검사와 전수재생을 다시 수행한다.
변경파일 정적검사·Node·source/설정/팀/seed/설치/submodule 검증 뒤 봉인하고 추가 확인 없이 본32판을 실행한다.
Cloud90·유료smoke8·별도fake32는 생략하며 통과 receipt를 만들지 않는다. 실제 로컬 검증만 evidence로 연결한다.
수집 중 source/prompt/prior/설정 불변. B 정상 계약 후 유일 합법 JSON 추출→첫 합법 후보를 사용하며 재호출0이다.
모델 원출력/복구/실제전송을 구분하고 B 모든 설명을 실제입력/교정계산/공개로그와 직접 검토한다. 추가 모델 심사0.
32경기 목록·actor viewer·오류 annotation과 근거를 제공한다. 상대별 (승+0.5무)/유효완료,
상대 동일가중 평균·완료대응B−A, 예정/시도/완료/실패/무효/미실행/미확정/누락대응·호출/token/시간/동시성을 보고한다.
과거 실험과는 별도 참고 비교만 하며 무효 결과를 합산하거나 계산기 단독/L1–L5 효능으로 해석하지 않는다.

## 중단·복구

C-018/RESEARCH_DESIGN §11.1 적용. 출력/설명 오류는 기록하며 계속한다.
provider/timeout/watchdog/경기별환경 실패는 해당 경기만 종료하고 남은 slot을 진행한다.
공유입력/계산/설정/무결성 결함은 영향범위를 중지하며 불명확하면 잠재영향전체를 중지한다.
테스트/평가만의 결함은 독립검증 후 모든 영향 자료를 동일 기준 재평가할 수 있다.
실제 수집 결함은 영향 경기·의존대응 무효, 자동재수집/보충0이다. 기존 halt/시계/원장은 변경하지 않는다.
결함/전후 source/기준/영향/독립검증은 evidence/ep024 및 ex031/defects에 기록한다.


## 실행으로 확인한 현재 제한

EX-031은 새 Weather Ball `originalName` 타입 계산 결함으로 중단했다. 수집81입력 중1입력,
B1경기·의존 대응을 무효화하고 전수검토·정리를 마쳤으나 유효32판/16대응은 확보하지 못했다.
기존 source와 EX-030 증거를 보존하며 이 결함은 미수정 상태다.
[실행 결과](../experiments/EX-031-calculator-inputfix32.md)를 근거로 STATUS·ARCHITECTURE의 현재 제한을 갱신한다.
