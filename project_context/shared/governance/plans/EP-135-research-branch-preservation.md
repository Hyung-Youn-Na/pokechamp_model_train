# EP-135 — 연구 브랜치 분리와 검증된 보존본

- 상태: Completed
- 생성일: 2026-10-12
- 책임자: Codex
- 승인 근거: 사용자 제공 계획의 구현·검증 지시, [D-131](../decisions/D-131-research-branch-preservation.md)
- 관련: [INDEX 절차](../../../INDEX.md#workflow), [CHARTER](../../../CHARTER.md),
  [연구 설계](../../../RESEARCH_DESIGN.md), [C-005/006/007/008](../../../research/l1-l5-port/CONTRACTS.md#c-005--persistent-state-및-provenance)

## 목표와 범위

동일 코드 기준선에서 모델 학습과 L1–L5 이식 연구를 분기하고, 외부 자산의 복사·검증·복구
경로를 확보한다. Git 기준선·브랜치별 목적 문서·worktree·대형 자산 보존까지 수행한다.
세부 배치와 제외 범위는 D-131을 따른다. 실행 코드 제거·공통화는 수행하지 않는다.

모든 기존 active 일반 plan 28개와 completed를 가리키는 EP-111/112/113 호환 링크를
확인했다. 기존 plan은 Blocked 또는 Paused이며 해당 상태·protocol·원자료·봉인을 유지한다.
분리 작업은 중단 실험의 재개·완료나 새 실험 실행 승인이 아니다.

## 단계와 완료 기준

- [x] 초기 HEAD·index·diff·미추적 소스·submodule pin·환경·외부 자산·쓰기 작업·용량 기록
- [x] 원본 삭제/이동 없이 복사하고 파일 목록·종류·크기·해시·link target 전수 대조
- [x] 명시적 소스 목록으로 공통 기준 커밋과 고정 태그 생성, main·기존 원격 refs 불변
- [x] 별도 L1–L5 worktree와 동일 pin의 로컬 submodule checkout, 필요한 보존 열람 링크
- [x] 각 브랜치 목적·현재 작업·출력/복원 안내 분리, 실행 코드 차이 없음
- [x] 기존 환경 유지와 dotenv·런처·CPU 합성 저장/복원 검사의 전후 비교
- [x] 내부/외부 링크·최종 Git bundle·표본 복원·manifest/Git 연결 receipt 검증

## 검증과 증거

보존 루트 아래 `manifests/`, `repositories/`, `validation/`에 초기/단계별 결과를 기록한다.
자산 manifest는 소스와 복사본의 사실만 기록하며 최종 Git 연결은 별도 receipt다.
CPU 회귀 출력은 `validation/`의 새 임시 경로를 사용하고 GPU·모델 API·실험 수집은 하지 않는다.
기존 봉인 오류는 원상태와 기록을 보존하며 복사 불일치와 구분한다. 새로운 실패는 해당 단계에서
멈추고 이번 변경만 대상으로 복구한다. 실행 중인 쓰기 작업은 임의 종료하지 않는다.

비실험 작업이므로 실험 재수집·시계·C-047 배틀 뷰어 완료 기준은 해당 없음.
기존 API/알고리즘을 바꾸지 않으므로 새 동작 단위 테스트 대신 보존 도구의 표본 검증과
승인된 기존 CPU 회귀를 수행한다.

## 진행

- 2026-10-12 — D-131·EP-135 미사용 확인 후 등록. main/원격 e93a7b1, 원래 index·diff와
  control-plane 사전 사본을 외부 보존 루트에 기록했다. 자산 목록·용량과 회귀 기준선 조사 중.

- 2026-10-12 — 일반 파일 3,320,231개의 복사·SHA-256 대조와 원본 목록/metadata 불변 검사가 통과했다. 독립 사본 전수 경로·권한·링크 대조도 누락/추가/오류0으로 통과했다. 공통 기준선 문서를 준비한다.

- 2026-10-12 — 동일 코드 기준선·목적 문서·worktree/보존 링크를 구성하고 전후 CPU·환경·문서·bundle/표본 복원을 검증했다. 실행 실험을 재개하지 않고 분리 작업을 종결한다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. ID 충돌, 복사 대상의 활성 쓰기,
복사 불일치 또는 신규 검사 실패가 발견되면 의존 단계를 보류하고 원본/사본과 증거를 보존한다.

## 결과

두 연구 브랜치·공통 보존 태그·외부 사본·브랜치별 목적과 작업 안내를 구성했다.
`main`과 기존 원격 참조는 `e93a7b166b0c4b8721bd802d1e9d6731eecbffcf`에 유지했고
공통 기준 커밋은 `a2e7d6e4852a39266bc05895d69e5a6e419a6e76`이다.
최종 브랜치 커밋·bundle·자산 manifest 해시의 연결은 외부 `manifests/git-receipt.json`에 둔다.
태그는 이동하지 않으며 원본 삭제·이동, 원격 push, 새 실험·GPU·모델 API 실행은 없다.

| 검증 | 결과 | 외부 보존 루트 기준 evidence |
|---|---|---|
| 전수 복사·원본 불변 | 일반 파일 3,320,231개, 고유 파일 내용 812,502,949,406 bytes; SHA-256 대조·원본 목록/metadata 불변 | `manifests/copy-verification.json` |
| 독립 사본 대조 | 3,494,244항목; 누락·추가·오류0, 권한·link/hardlink·실제 blob 확인 | `validation/destination-verification.json` |
| source·Git 경계 | 명시 목록 2,935경로의 내용·실행 권한·pin 일치; 코드 차이0 | `validation/common-index-verification.json`, `validation/branch-verification.json` |
| CPU·환경 | dotenv·런처·합성 저장/복원 10검사 전후 모두 통과; 환경8개 차이0 | `validation/pytest-before.xml`, `validation/pytest-after.xml`, `validation/environment-after.json` |
| 독립 검토·링크 | 기존 규범/판정 보존; 목적 문서 분리; 자료 링크188·코드 실제 checkout | `validation/final-review.json`, `validation/artifact-links-created.json` |
| 복구·Git bundle | bundle 단독 clone·소스/환경/checkpoint 표본·별도 repo 변경/미추적 소스 복원 통과 | `validation/asset-restore-verification.json`, `validation/purpose-bundle-verification.json`, `validation/final-bundle-verification.json` |

원래 끊겨 있던 symlink 5개는 원형을 보존하고 `validation/symlink-closure-review.json`에
기록했다. 새 누락이나 과거 봉인·실험 유효성의 재판정이 아니다. 자격증명은 제외하며
복사 환경의 원경로/의존성을 복원하지 않고 바로 실행 가능하다고 간주하지 않는다.
알려진 Qwen EP132 준비 경로 불일치는 수정하지 않았고 후속 항목으로 남긴다.
미충족 완료 기준은 없다. 과거 Blocked/Paused 및 실험 미완료는 그대로 유지한다.

보존본 접근과 복원은 [작업 안내](../../../RESEARCH_WORKFLOW.md), 고정 자산 연결은
[manifest 포인터](../../../preservation/pre-split.json)를 따른다.
