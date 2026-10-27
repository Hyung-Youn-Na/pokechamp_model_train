# EP-155 — 확률 변동 진단을 유지하는 NVFP4 실제1경기

- 상태: Blocked
- 생성일: 2026-10-15
- 책임자: Codex
- 승인: 현재 사용자 실제 배틀 진행 재승인 / D-149
- 조건 원문: [EX-096](../experiments/EX-096-nvfp4-battle-probability-diagnostics.md)
- branch/checkout: research/model-training, /workspace, a4659bf·기존 변경 보존
- actor: pokechamp/.venv/bin/python; 모델: .pokechamp-data/jev35b-nvfp4-runtime/.venv/bin/python
- 새 출력: EX-096 run·evidence/ep155·exports/battle_viewers/ex096

## 범위·완료 기준

EX-095의 확률 변동만 진단으로 전환하는 명시 설정을 구현·검증하고 새로운 실제1경기를 수행한다.
모델/환경/캐시/양자화·원 입력·GPU/호출/시간 한도는 유지하며 기존 EX-095/EP-154와 과거자료를
재개하거나 덮어쓰지 않는다. INDEX/CHARTER·매뉴얼·RD/C-070 및 겹치는 Blocked EP-154/151/140/134의
보존 경계와 승인 근거를 확인했다. 상세 조건은 EX-096 원문을 따른다.

- [x] 정책/등록·기존 strict 보존 CPU검사·사전검토·새 source 동결
- [ ] 단일 적재·최대8사전추론·같은 서버 정상1경기
- [ ] 전수 기술감사·EX-094 기술비교·통합뷰어/대표 오프라인 검사
- [ ] run/뷰어/증거 봉인·자원반환·상태/색인 갱신

## 검증·중단

EX-096·RD11.1/C-018의 경계와 상한을 따른다. 기존 검증은 source/환경이 같은 범위만 재사용한다.
확률 변동만 차단에서 제외하며 선택/매핑·Marlin/rank/메모리·무결성/usage 검사와 경기 실패 경계는
유지한다. source/조건은 실제 수집 중 바꾸지 않는다. 재경기·자동재개0이다.

## 진행

- 2026-10-15 — 사용자 재승인을 D-149/EX-096으로 등록. 구현/새 적재 전.

- CPU211통과(브라우저 별도환경2skip), 이전 strict 차단·새 diagnostic 계속·선택불일치 차단을 검증했다.
  공식37파일·외부587자료·GPU0/3포트·자격증명 구성·source변경2파일을 대조했다.
  새 source/설정을 동결하고 단일 적재·8사전요청 후 같은 서버의 실제1경기를 시작한다.

## 실패 종결

7턴 GLM 스키마 오류로 정상0/1·실패1이다. 부분 기술감사·뷰어·오프라인·봉인·반환은 완료했다.
자원 감시기 오류1개도 보존하며 연속감시 완전통과를 주장하지 않는다.
[보고](../../../exec-plans/evidence/ep155/report.md). 자동재개0, 후속 새 승인은 D-150/EX-097에서 관리한다.
