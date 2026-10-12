# EP-046 — 배틀·선봉 구조 설명과 상세 효과 사전

- 상태: Completed
- 생성일: 2026-09-15
- 완료일: 2026-09-15
- 책임자: Codex
- 승인: 현재 사용자가 제공한 계획의 구현·로컬 검증 지시
- 관련: [D-057](../../decisions/D-057-effect-reference.md), [C-037](../../CONTRACTS.md#c-037-effect-reference)

## 목표·범위·불변 조건

B/B2 및 LLM 선봉에 JSON 구조 설명과 요청당 중복 없는 Gen9 Dex 상세 효과 사전을 제공한다.
검증 후 EX 미지정 새 준비 기본값을 봉인한다. parent integration/문서만 변경하고 과거 실험,
봉인 자산과 canonical submodule을 보존한다. 기존 active의 Blocked 실험은 재개하지 않는다.
설명 사전은 일반 게임 지식 추가이며 원본 관측·prior·계산 입력·출력복구·평가 기준은 유지한다.
유료 호출·새 성능 비교0. 비실험 구현으로 실험 복구·시계·재수집은 해당 없음.
C-032에 따라 모델 설명 사후 annotation은 제외하고 입력 설명·효과 원문 정확성은 검증한다.

## 완료 기준

- [x] 고정 Showdown Gen9 desc 자산·commit/hash/생성법/라이선스
- [x] B/B2·선봉 구조 설명·경로/자료형 검사·정보 경계·중복 제거·미해석 참조 사전 차단
- [x] 버전 선택·새 준비 기본값·과거 EX 호환·원본 보존·전송 직전 재생성 검증·trace/viewer 연결
- [x] 모의 공급자·로컬 Showdown 대응2경기·출력 검증/복구
- [x] EX-041 선봉32·전투2283 요청 전수 오프라인 생성·원본 불변·크기/중복/누락 감사
- [x] 대표 전후 prompt·사전·검증 보고·봉인 목록·관련 문서 갱신

## 검증 및 진행

- 2026-09-15: INDEX/CHARTER/RD/CONTRACTS/ARCHITECTURE 및 겹치는 active plan 확인.
  사용자 계획이 설계 논의를 제공하므로 추가 승인 질문 없이 계획 등록·행동 중심 검사·구현·자체 검토를 수행한다.
- 증거: `../evidence/ep046/`. 로컬 통과는 승률·판단력·지연 개선의 증거가 아니다.

## 차단·중단

[INDEX](../../INDEX.md#workflow)를 따른다. 새 사전 참조/자료형 오류는 전송 전에 실패한다.

## 최종 검증·산출물

[최종 보고서](../evidence/ep046/report.md)에 변경·버전·정확성·크기·전후 원문·해석 한계를 기록했다.

- 고정 Dex 1,787항목 전체 재추출·원문/라이선스 바이트 일치. 넓은 회귀277 및 후속 변경 관련
  58/46/37검사 통과. 서로 겹치는 검사이며 합산하지 않는다. [검증 범위](../evidence/ep046/report.md#검증-결과).
- 최종 소스 [로컬 대응2경기](../evidence/ep046/mock-pair-complete/verification.json),
  [178모의HTTP·복구4·원본/trace/viewer 일치](../evidence/ep046/wire-audit-final.json).
  새 B 기본 [15장면 준비/재생성](../evidence/ep046/b-prepare-audit.json) 통과.
- [최종 전수 감사](../evidence/ep046/offline-complete/report.json): 선봉32·B2 2,283·오류0.
  구조 전체 검사 뒤 최종 수집기로 모두 재검사했고 사전 내용 변화0·원본 trace64파일 불변.
- [보존 검사](../evidence/ep046/preservation.json): EX-041 manifest 10,466파일 및
  EX-039/040 보존 목록 8,024파일 hash 일치. 기존 Blocked 상태 유지.
- [정리](../evidence/ep046/cleanup.json)·[봉인 목록](../evidence/ep046/manifest.json).
  외부 API0. 입력량 증가는 보고했으며 승률·판단력·지연 효능은 평가하지 않았다.
