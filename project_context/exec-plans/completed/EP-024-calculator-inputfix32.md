# EP-024 — 교정 입력·계산기 동일 조건 A/B32판

- 상태: Completed
- 생성일: 2026-09-10
- 책임자: Codex
- 관련: D-036, EX-031, C-024

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

## 완료 기준

- [x] 새 정책·전달·독립 검증 연결·필수 회귀·봉인 통과.
- [x] 승인32 slot 각1회 처리 또는 중단/미실행 사유 보존.
- [x] 수집분 전수 검토·viewer·실제분모 보고·원자료/source 보존·자원/lock 정리·상태 갱신.
- 성능 비교 완료 표시는 유효32판·16대응에만 허용한다. 실패/중단이면 비교 미완료를 명시한다.

## 진행·증거

2026-09-10 권위 문서·겹치는 EP-020/018/011 및 EX-028/029/030을 확인하고 신규 등록했다.
보호 inventory: project_context/exec-plans/evidence/ep024/preservation.json. 구현 전 Cloud0.

2026-09-10 기존 source168 일치 확인 뒤 새 정책·정책별 버전·runtime identity·과거 원장 연결을 구현했다.
새 관련20검사와 최종533회귀(240.00초), v2 실제 FixedPlayer31결정/로컬 backend20요청 격리·동시성·변조 거부를 통과했다.
EX-030 증거4,012파일/독립636재생을 해시 검증했고, 새 정책 provider 전636입력 검증도 통과했다.
계산/입력/독립oracle 코드 불변·59,108보호파일·설치/submodule·정적/Node·설정/팀/seed 검사를 통과했다.
새 [qualification](../evidence/ep024/qualification.json)·169 source·원본32대진을 봉인했다.
본 EX-031 c0에 진입했으며 별도fake32/Cloud90/smoke8 receipt는 생성하지 않았다.

## 종료 결과와 미달 기준

2026-09-10 Weather Ball 공유 계산 결함으로 c0 전체 수집을 중단했다. Sun Ninetales 기술의
소문자 ID가 `Move.originalName` 비교를 통과하지 않아 turn5/decision7/event46에서69–82가 전달됐다.
동일 가설의 pinned Showdown 독립16roll과 canonical 이름만 적용한 계산은156–184로 일치했다.
81 B입력/19,316시나리오 원본 재현과 기술명 정규화 영향 분석에서1입력/12시나리오가 바뀌었다.
B1경기 및 의존 대응을 무효 처리했다. 계산기 결함은 미수정이며 자동 수정·재실행 작업을 상속하지 않는다.

32예정·12시도(A6/B6)·2유효완료(A OneStep2승)·10중단·20미실행이다.
중단10건 중 무효 B1을 별도 분리하면 A실패4/B실패5/무효1이다.
완료 대응0/16·누락16, 상대 동일가중 평균과 B−A는 산출 불가로 **성능 비교 미완료**다.
예정32 slot의 중단/미실행 사유 보존이라는 사전 완료 기준의 대안과 전수검토·정리를 충족하여
bounded 작업은 Completed로 종결한다. 이는 유효32판 확보나 실험 목표 달성을 뜻하지 않는다.

B78설명 전수 검토: 오류39/78(50%), 사실9·진영0·시점15·계산33(차원 중복).
입력 유발 계산 오류1건과 나머지38오류 설명을 구분했다. 추가 모델 심사0.
합법 선택78(정상69/추출9/fallback0), 실제 전송75(정상66/추출9), 중단 취소3이다.
새 HTTP185/응답185, 새 timeout/미확정0, HTTP 전 halt 거절3이다. A실제 fallback0.
입력10,606,539/출력39,528token, 수집492.647초, 배틀/계정/모델 최대동시성10이다.
이전 EX-028/029 자체 사용량을 각1회 연결하여 누적1,395예약/1,394응답/미확정1,
입력59,808,461/출력343,069token, 수집시간 합계2,057.892초다. 과거 무효 성능은 합치지 않았다.

533회귀·독립 증거와636전달·수집 source169개·24 actor 봉인·81 B입력·75전송을 검증했다.
기존59,108보호파일·6개 Blocked·두 pinned submodule은 불변이다.
actor/calculator·포트8000/8100–8109·permit·원장 lock 정리와 credential 검사를 완료했다.

[최종 보고서](../../../.pokechamp-data/battle-guide-inputfix32/ex031/report-final/report.md) ·
[32경기 목록](../../../.pokechamp-data/battle-guide-inputfix32/ex031/report-final/matches.html) ·
[최종 검증](../evidence/ep024/final-verification.json) ·
[qualification](../evidence/ep024/qualification.json).
