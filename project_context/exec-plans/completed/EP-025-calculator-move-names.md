# EP-025 — 계산기 기술명 정규화 버그 수정

- 상태: Completed
- 생성일: 2026-09-10
- 책임자: Codex
- 관련: D-037, C-023, EX-031
- 승인 근거: 사용자의 “그러면 버그를 수정해주세요.” 명시적 후속 지시.

## 목표·범위

EX-031에서 확인한 Weather Ball 타입 변경 누락을 parent calculator worker에서 수정한다.
입력 기술 ID를 pinned generation의 canonical 이름으로 정규화하여 두 계산 경로의 Move 생성에 사용한다.
동일 originalName 분기의 Weather Ball/Techno Blast/Multi-Attack/Terrain Pulse/Revelation Dance,
날씨·필드·아이템·비활성 경계와 기존 입력/정책 source 검증을 로컬 회귀로 확인한다.
과거 EX-031 동일 scenario의 독립16roll과 수집81입력의 사전 정규화 영향 분석을 새 source와 대조한다.
허용 변경은 parent integration의 worker/테스트와 project_context 문서·새 evidence다.

## 불변·중단 경계

현재 bugfix는 기존 schema/semantics/평가 기준을 유지하며 source hash로 새 구현을 구분한다.
설치 라이브러리·pinned submodule·prompt·prior·기존 정책 hash는 보존한다.
과거 실험 원문·보고·주석·halt·원장·시계·qualification과 기존6개 Blocked는 불변이다.
유료 호출·재수집·EX-031 재개0. 새 local 검증은 과거 qualification을 덮어쓰거나 유효화하지 않는다.
별도 성능 실험을 포함하지 않는 bugfix다. C-018 증거 보존 원칙을 적용하며 새 충돌은 영향 범위에 기록한다.

## 완료 기준·검증

- [x] 수정 전 회귀 실패를 재현하고 Weather Ball 및 같은 원인의 기술 분기를 수정한다.
- [x] 실제 worker의 v1/v2 경로에서 pinned Showdown 독립16roll·조건 경계와 기존 회귀가 통과한다.
- [x] EX-031의81수집 입력을 새 source로 재계산하여 사전 canonical-name 영향 분석과 일치한다.
- [x] 정적/Node 검사·이전 증거/설치/Blocked 보존·자원 정리·source 및 현재 상태 문서를 갱신한다.

## 진행·증거

2026-09-10 권위 문서와 겹치는 EP-011/018/020을 확인했다. 새 bugfix만 등록하며 기존 작업을 재개하지 않는다.
증거는 ../evidence/ep025/에 보존한다. 별도 fake/live 배틀이나 Cloud receipt는 생성하지 않는다.

## 완료 결과

2026-09-10 canonical 기술명 전달로 worker 두 경로를 수정했다. 수정 전38실패를 재현했으며,
28조건×독립16roll·신규60개 포함 전체593회귀가 통과했다. EX-031의81입력/19,316시나리오에서
사전 교정 분석과 동일한1입력/12시나리오만 변경됐다. Weather Ball156–184는 독립16roll 전체와 일치한다.
Production worker1파일·새 테스트/fixture2파일 변경, 기존 정책/프롬프트/설치/submodule 및60,619기존파일 보존.
이전 qualification의 새 source 거부와 자원/credential 정리를 확인했다. 유료 호출·재수집0이다.

[수정 보고서](../evidence/ep025/report.md) · [최종 검증](../evidence/ep025/final-verification.json) ·
[81입력 재생](../evidence/ep025/replay81-final.json).
