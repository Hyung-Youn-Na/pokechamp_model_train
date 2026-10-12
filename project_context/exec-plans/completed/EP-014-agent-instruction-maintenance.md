# EP-014 — 승인·중단 지시와 현재 상태 정합화

- 상태 (Status): Completed
- 생성일: 2026-09-08
- 책임자: Codex
- 승인 근거: 현재 대화에서 사용자가 지시 감사 후 추천 조치의 적용을 명시적으로 요청했다.
- 관련 decision: [D-025](../../decisions/D-025-agent-instruction-boundaries.md)
- 관련 contract: C-015/C-016을 포함한 기존 계약을 변경 없이 보존한다.

## 목표와 범위

기존 승인의 중복 확인, 독립 작업까지 확대되는 중단, 보조 스킬 부재에 따른 미완료를 줄인다.
Root 및 Python subtree AGENTS, project_context의 routing·exec-plan 규칙과 현재 상태 요약,
현재 로컬 설치본의 OpenAI Docs·Imagegen 지시를 정합화하고 작은 상황별 판단으로 검증한다.
Career Centre는 로컬 config에서 이미 disabled임을 확인했으므로 그 설정을 유지한다.
사용자가 비활성화한 Notion과 다른 스킬의 활성화 상태는 변경하지 않는다.

## 비목표와 불변 조건

- CHARTER, runtime contract, research methodology, 실험별 gate·중단·예산·분모를 변경하지 않는다.
- EP-011/012/013 및 EX-020/021/022를 재개·완료 처리하거나 과거 봉인 자료를 수정하지 않는다.
- 정식 exec plan 면제, 실행 권한 확대, 외부 전송, Cloud 호출, 이미지 생성은 수행하지 않는다.
- 보조 스킬을 새로 설치하거나 모델·sandbox·승인 정책을 변경하지 않는다.
- 원래 worktree 변경 사항을 보존한다. 코드·submodule·runtime 자산은 수정 범위 밖이다.

## 완료 기준

- [x] 기존 승인 근거와 확인 질문·중단·완료의 범위가 연결된 지시에서 일관된다.
- [x] 연구 설계의 현재 상태 요약이 운영 실험·진단과 L1-L5 전체 효능 미정을 구별한다.
- [x] 사용 불가한 보조 스킬이 독립적인 승인 작업의 필수 선행조건이 되지 않는다.
- [x] OpenAI Docs 로컬 감사 경로와 Imagegen CLI 중단 범위가 수정되고 검증된다.
- [x] 대표 상황 판단과 문서·스킬 검증, 보호 문서 불변 확인을 기록한다.
- [x] 완료 후 plan·index·STATUS에 실제 결과와 로컬 설치본의 적용 범위를 기록한다.

## 검증

변경 diff와 Markdown link·공백을 확인하고 수정한 두 스킬의 quick_validate를 실행한다.
기존 승인, 읽기 전용 감사, 일부 의존성 부재, 실험 gate 실패와 승인 경계 상황을 검토한다.
독립 판단 검토에는 읽기 전용 작업만 부여하며 실제 Cloud·이미지·외부 쓰기는 하지 않는다.
변경 전 snapshot과 비교하여 Charter·Contract·기존 plan/ADR/experiment record 불변을 확인한다.

## 진행 상황

- 2026-09-08 — 관련 기준 문서와 active plan 3개를 확인했다. 이 정비는 중단된 실험을
  이어가는 작업이 아니다. 로컬 config에서 Career Centre disabled를 확인했다.
- 2026-09-08 — 공통 규칙과 상태 요약, 두 로컬 스킬을 수정했다. 독립 상황 판단에서 드러난
  짧은 구현의 plan 등록 문구도 기존 Charter 요건에 맞게 명확히 하고 재검토했다.

## 차단 및 중단 조건

권한·연구 경계를 바꾸는 수정이나 요청 범위 밖 행동은 수행하지 않는다. 상위 authority와
해결되지 않은 충돌이 있으면 기록·보고하고 그 해결에 의존하는 작업을 중단한다.

## 결과 및 증거

공통 규칙은 [project_context/INDEX](../../INDEX.md)에 두고 root/subtree AGENTS 및 plan
template에서 참조한다. 연구 설계의 변경은 초기 요약·상태 표의 범위와 evidence 연결에
한정한다. 기존 실험 plan 3개의 Blocked 상태와 Charter·Contract를 보존했다.

| 검증 | 결과와 한계 |
|---|---|
| OpenAI Docs 및 Imagegen `quick_validate.py` | 두 스킬 모두 `Skill is valid!` |
| 변경 전 snapshot 대조 | 보호 대상 67개 파일 불변. Charter·Contract·기존 plan/ADR/experiment record 및 로컬 config 포함 |
| 연구 설계의 보호 절 비교 | RQ·hypothesis·treatment·평가·중단·해석 및 개별 D-XXX 설계 절 등 16개 절 바이트 동일 |
| Python subtree 검사·security·hook 규칙 | 기존 `Agent Usage` 앞 본문 전체 바이트 동일 |
| Markdown link·공백, `git diff --check` | 수정 문서의 로컬 링크와 공백 검사 통과. Plan 이동 후 종료 검사도 수행 |
| 로컬 스킬 변경 패치 | 변경 전 스킬 snapshot에서 `git apply --check` 통과 |

독립 subagent는 실제 작업을 실행하지 않고 다음 8개 가상 상황의 다음 행동과
질문·중단·완료 범위를 읽기 전용으로 판단했다.

| 상황 | 확인한 판단 |
|---|---|
| 대화에서 승인했지만 plan 갱신 전인 코드 수정 | 승인 기록 후 구현·검증 계속, 동일 승인 재질문 없음 |
| 파일 수정 금지인 로컬 지시 감사와 웹 실패 | 로컬 근거로 설명 완료, 파일 수정·확인되지 않은 제품 사실 주장 없음 |
| 선택적 superpowers 부재 | 사용 가능한 동등 도구로 진행, 필수 절차·검사는 보존 |
| EX-022 입력/평가 무결성 오류 | 전체 비교·검토 중단, 규칙 안의 보존·정리·무효 보고만 수행 |
| 로컬 보고서 준비와 별도 게시 승인 | 초안·검증 완료, 미승인 게시 실행 없음 |
| CLI 기능 부족과 독립 alt-text 준비 | 독립 준비 계속, 모델 변경 부분만 승인 대기 |
| 필수 회귀 실패와 hook 차단 | 범위 내 수리·재검증, 실패 은폐·hook 우회·허위 완료 없음 |
| 짧은 구현이며 plan 미등록 | bounded plan 등록, 동일 목표 재승인 없음. Plan 면제 미도입 |

최종 등록·legacy·사용자 지정 절차 보존 문구 변경 후 관련 4개 상황을 재검토하여 모순이나
승인 경계 후퇴가 없음을 확인했다. 이는 지시 해석 검토이며 실제 코드 수정 시나리오 실행,
실험 재실행 또는 모든 향후 모델 행동의 보장을 의미하지 않는다.

로컬 변경 파일은 `/root/.codex/skills/.system/openai-docs/SKILL.md`,
`/root/.codex/skills/.system/imagegen/SKILL.md`, 해당 Imagegen `references/cli.md`다.
변경 전후 차이를 [로컬 스킬 패치](../evidence/ep014-local-skills.patch)로 보존한다. 패치의 경로
기준은 `.system/`이다. 이 환경의 설치본에만 적용했으며 시스템 스킬 갱신이나 다른 환경에
자동 전파되는 변경은 아니다. Career Centre의 기존 disabled 설정과 Notion 상태는 수정하지 않았다.
