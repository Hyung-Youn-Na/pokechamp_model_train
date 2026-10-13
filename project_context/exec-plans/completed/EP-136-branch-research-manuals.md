# EP-136 — 분리된 연구선의 매뉴얼 정비

- 상태: Completed
- 생성일: 2026-10-13
- 완료일: 2026-10-13
- 책임자: Codex
- 승인 근거·범위: 사용자의 연구 매뉴얼을 분리된 환경에 맞춰 정비하라는 명시적 요청
- 관련: [D-131](../../decisions/D-131-research-branch-preservation.md),
  [EP-135](../completed/EP-135-research-branch-preservation.md), [INDEX](../../INDEX.md#workflow)

## 목표와 범위

`research/model-training`과 `research/l1-l5-port`에서 현재 연구 목적에 맞는 문서 진입점,
checkout·환경·등록·출력·증거 열람·복원 순서를 따라갈 수 있도록 Git 추적 매뉴얼을 정비한다.
브랜치별 시작 매뉴얼, 공통 작업/보존 안내, INDEX·README·AGENTS의 연결, 새 EP/EX 템플릿,
PokéChamp 실행기 안내의 적용 범위가 대상이다. CLAUDE는 기존 AGENTS import를 사용한다.

기존 active 일반 plan 28개는 27 Blocked·1 Paused이고 EP-111/112/113은 완료 문서의 호환
링크다. 기존 연구 질문·방법·조건·분모·예산·판정·동결 protocol과 source/evidence는 유지한다.
색인의 분류만 현재 실행 여부에 맞추며 개별 기존 plan의 상태·본문·경로는 바꾸지 않는다.

코드/API/CLI·환경·의존성·submodule pin·자격증명은 변경하지 않는다. GPU·모델 API·배틀·
서버·설치·실험 준비/재개를 실행하지 않는다. `main`, `snapshot/pre-split`, 과거 보존본과
receipt를 유지한다. L1의 `.tools/.../docs` 등은 보존 링크이므로 편집하지 않는다.
기존 EP132 준비 경로 오류는 후속 항목으로 남긴다.

## 완료 기준

- [x] 연구선별 진입점·작업 위치·환경 유무·현재 범위가 명확하다.
- [x] 새 EP/EX의 연구선·Git identity·입출력·원자료 연결을 기록할 수 있다.
- [x] 실행기별 실제 출력 인자와 읽기/쓰기·서버/모델 호출 경계를 소스와 대조한다.
- [x] 현재 안내와 과거 EX 전용 명령을 구분하고 새 실험 자동 실행을 유도하지 않는다.
- [x] 문서 링크·anchor·템플릿 복사 경로·diff와 보존 invariant를 검증한다.
- [x] 각 브랜치 문서를 커밋하고 기존에 승인된 학습 원격에 반영·검증한다.

## 검증과 증거

문서만 변경한다. CLI와 shell wrapper를 정적으로 읽고, 문서 내 명령은 실행하지 않는다.
일부 `--help`도 실제 작업에 진입하므로 범용 도움말 실행을 검증으로 사용하지 않는다.
새 unit test나 runtime 회귀 대신 Markdown 링크/anchor·diff·Git tree·기존 규범 문서 해시를
대조한다. 검증 기록은 외부 보존 루트의 `validation/ep136-research-manuals/`에 둔다.
이 위치는 EP-135의 snapshot/manifest를 수정하지 않는다.

## 진행

- 2026-10-13 — EP-136 미사용과 두 checkout의 clean 상태를 확인하고 등록했다.
  기존 문서·규범·실행기 부작용·출력 인자를 읽기 전용으로 조사했다.
- 2026-10-13 — 연구선별 매뉴얼·공통 안내·새 EP/EX 기록 항목과 진입 링크를 정비했다.
  고정 대진의 EX-076 역사와 EX-077 기본 CLI를 구분하고, viewer 경로·CPU 검사 해석·
  EP-122 완료 링크·README 축약 후 라이선스 연결을 실제 원문에 맞췄다.
  독립 CLI/규범 검토와 정적 검증에서 새 링크 오류가 없고, 각 연구선의 기존 규범·개별 기록
  392개와 기존 plan 색인 135행·submodule pin·보존 ref/receipt가 유지됨을 확인했다.
  기존 상속 설치 문서의 README anchor 누락은 검증 기록에 별도로 남겼다.
- 2026-10-13 — 학습 매뉴얼 커밋 `aabd0dd`, L1 매뉴얼 커밋 `288f981`을 만들었다.
  학습 브랜치만 기존 `model-train` 원격에 게시하고 원격 SHA 일치·두 checkout의 clean 상태를
  확인했다. 상세 근거는 `manual-commits-push.json`에 기록하고 plan·색인·STATUS를 종결했다.

## 차단·중단

[INDEX 공통 기준](../../INDEX.md#workflow)을 따른다. 문서 설명과 실제 구현의 불일치는
기록하고 안내 범위를 한정하며 코드나 기존 실험 규범을 조용히 고치지 않는다.
비실험 문서 작업이므로 실험 시계·재수집·배틀 뷰어 생성은 해당 없음이다.

## 결과

두 연구선의 매뉴얼·등록 템플릿·실행기 기술 참조 정비와 정적 검증·커밋·학습 원격 게시를
완료했다. L1 브랜치는 로컬에 유지하며 새 실험·코드/환경 변경은 없다.
시작 branch/commit·보존 해시는 외부 검증 디렉터리의 `before.json`, 링크·template·shell 구문·
기존 기록 대조는 `document-validation.json`, 독립 검토는 `cli-review.json`과
`governance-review.json`에서 확인한다. 종결 후 Git 상태와 게시 검증은 `final-receipt.json`에 연결한다.
명령 예시는 실행하지 않았고 runtime 검사는 해당 없음이다. 기존 EP132 준비 경로 한계와
개별 실험의 미완료·Blocked/Paused는 그대로 유지한다.
