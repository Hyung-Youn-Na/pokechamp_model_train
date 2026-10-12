# D-020 — 프로젝트 소유 Ruination 계산 패치

- Status: Accepted
- 날짜: 2026-09-08
- 근거: 사용자가 전달한 「Ruination 계산기 패치 및 오프라인 재검증」의 구현·검증 지시.

## 결정과 승인 범위

`@smogon/calc 0.11.0`과 npm lockfile을 유지하고 프로젝트 JSON 패치 `ruination-v1`을
관리한다. Gen 7–9 공용 Nature’s Madness 분기에 Ruination을 추가하고 두 기술에
`Math.max(1, Math.floor(defender.curHP() / 2))`를 적용한다. 기존 무효 판정과 Protect의
0 피해, 기술 이름·타입·분류·속성을 유지한다. 외부 결과 덮어쓰기나 다른 기술 지원은 제외한다.

패치는 정확한 변경 전후 내용과 파일 SHA-256을 포함한다. Node 기본 기능으로 원본/적용본
해시와 버전을 검사하며 미확인 상태를 거부한다. `npm ci --ignore-scripts` 후 명시적으로
`npm run patch:calc`를 실행한다. actor는 파일을 수정하지 않고 모듈 로드 전에 검증한다.
누락·변조·버전/identity 불일치는 원인이 있는 CalculationError로 종료하며 LLM을 호출하지 않는다.
응답의 engine_patch는 patch ID, JSON 파일 해시, 적용 파일 해시를 포함한다. Python 수신부와
입력 검증기가 비교하며 trace와 오프라인 evidence에도 보존한다. 패치·적용/검증 코드는
source seal에 포함하고 node_modules/빌드는 제외한다.

## 검증과 해석

이번 범위는 패치 회귀, 기존 integration 회귀, 기존 개발15장면 결정시점 재생과 분리된
사후 정답3건 대조다. 기대 Ruination은 Tinkaton373→피해186→잔여187→공개51/100이다.
피해는 명중·적용 조건부이며 실행·명중·KO·생존 확률을 추론하지 않는다. 공개 HP 범위와
prior는 유지하고 상대 정답/미래 이벤트는 사후 검증에만 사용한다.
EX-017 및 실패 receipt/source를 보존하고 EX-018과 새 출력 경로를 사용한다. 새 불일치나
미지원 효과 발견 시 해당 검증을 중단한다. 패치 검증과 전체 offline gate는 구별하며
의미 rubric 등이 미검증이면 offline_gate_passed=false다. EP-011 전체 완료나 병렬·Cloud·48판
승인 gate 통과로 해석하지 않는다.
