# EP-040 — B2 LLM 선봉 선택

- 상태: Completed
- 완료일: 2026-09-14
- 생성일: 2026-09-14
- 승인 근거: 현재 사용자 첨부 지침의 구현·무유료 로컬 검증·문서·후속 실험 초안 지시.
- 관련: [D-052](../../decisions/D-052-llm-lead.md), [C-033](../../CONTRACTS.md#c-033-llm-lead).

## 목표·범위·불변 조건

EP-036 교정 source에서 Gen9 OU singles B2의 선봉 한 마리만 LLM으로 선택할 수 있게 한다.
parent `integration/pokechamp`만 구현하며 pinned submodule, 기존 Blocked 9개 plan과 과거 정책 hash를 보존한다.
팀 선택/생성/세트 변경, B2 배틀 prompt/압축/계산식/전투 정책 개선, 추가 모델·메모리·심사는 제외한다.
현재 승인은 로컬 fake/Showdown 검증까지다. Cloud·유료 smoke·실험 수집·과거 재개는 실행하지 않는다.
설명 오류 사후 annotation은 C-032 기본 제외이며 미평가로 남긴다.

## 완료 기준

- [x] 별도 정책·actor 설정·prompt 버전/hash·정보 및 엄격 출력 계약.
- [x] 기존 RNG/무호출 호환, 슬롯 매핑, 비동기 전송·중복 억제·실패 처리.
- [x] 기존 모델·permit·timeout·취소·공통 원장/최초 시계/상한 및 trace/manifest/viewer 연결.
- [x] 6슬롯/양쪽 진영 실제 Showdown 최초 출전, 정보 경계, 병렬·실패·EP-036/B2 회귀와 정적 검사.
- [x] 무유료 준비/검증 예시, 기술 제한, 대응 B2 random/LLM 후속 실험 초안과 미승인 예산.
- [x] evidence·문서/색인/STATUS/ARCHITECTURE 갱신 및 요건별 완료 감사.

## 검증

필수 범위는 사용자 지침의 로컬 검증 항목 전체다. 검사 명령·결과·생략/미검증은
[보고서](../evidence/ep040/report.md)에 기록한다. 로컬 성공은 provider 자격이나 전략적 성능 향상을 입증하지 않는다.

## 진행

- 2026-09-14 — INDEX/CHARTER/STATUS/설계/계약/architecture, 겹치는 active 9개와 D-047/048/050, EX-038 확인.
  RNG→preview→player→backend→원장→transport/viewer 경로 조사. 기존 source/Blocked/submodule 상태를 before.json에 기록했다.

## 중단·복구

비실험 구현이므로 유료 복구·수집 시계는 시작하지 않는다. 로컬 결함은 재현·교정·검증한다.
후속 실험은 C-018 복구·분모·누적 예산·시계 등록을 요구하며 표본/비용 제안은 미승인이다.

- 구현 및 초기 검증: 선봉 입력·엄격 출력·공통 backend·actor·원장/manifest/viewer 연결을 구현했다.
  초기74검사 통과. 실제 로컬2경기/4 actor에서 선봉2·전투 B2 117요청의 원장/실제전송 연결과 최초 출전을 확인했다.
  이 수치는 번호 정정 전 개발 evidence다. 유료 요청0.
- 새 ADR 번호는 기존 문서 정리 D-051과 충돌하지 않도록 D-052로 정정한다. 개발 source/검증 기록은 보존한다.

- 최종 검증 완료: 전체925검사 후 D-052 번호/seed namespace 정정, 최종121검사·로컬2경기/4 actor·204 fake요청 확인.
  EP-036 실제 실패 입력 전 경로 및 정상3993 prefix 보존, 정책/Blocked/pin 보존과 자원 정리를 확인했다.
  요건별 완료 감사·source 봉인·검증 명령·제한은 [최종 보고서](../evidence/ep040/report.md)에 기록했다.
  [EX-039](../../experiments/EX-039-b2-lead-proposal.md)는 Draft이며 실제 수집/예산 미승인, 전략적 성능 미평가다.
