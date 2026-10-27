# 공통 관측·뷰어 — 실행 계약

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.

<a id="battle-viewer-ui-v1"></a>

## 배틀 viewer UI — battle-viewer-ui-v1

[D-172](decisions/D-172-battle-viewer-ui-standard.md) 채택 이후 `research/model-training`에
신규 등록하는 배틀 실험의 공통 UI 규격이다. 기존 실행·동결 protocol·과거 내보내기와
Blocked/Paused 판정에 소급하지 않는다. [C-047](../../CONTRACTS.md#c-047-viewer-export)의
완료·출처·원본 보존 요건을 함께 적용한다. 운영 순서는
[연구 매뉴얼](../../RESEARCH_MANUAL.md#battle-viewer-workflow)을 따른다.

### 화면과 탐색

| 영역 | 고정 규격 |
|---|---|
| 목록·식별 | 실험 목록 → 경기 목록 → 경기 화면으로 연결한다. 경기·관점(actor)·결정의 식별과 결과/완료 여부를 저장 기록에 맞게 표시한다. |
| 배치 | EX-108 복원형처럼 왼쪽에 결정 정보, 오른쪽에 스크롤 중 유지되는 리플레이를 둔다. 좁은 화면은 리플레이를 상단에 두고 정보 영역과 세로 배치한다. |
| 탐색 | 결정과 턴 각각 이전/다음·직접 선택을 제공한다. 같은 턴의 복수 결정은 기록 순서와 개별 identity를 유지한다. 턴 선택은 그 턴의 첫 결정, 결정 없는 턴은 명시적인 빈 상태를 표시한다. |
| 키보드 | 좌우 방향키로 이전/다음 결정을 탐색한다. 폼 입력·탭의 키보드 조작을 가로채지 않는다. |
| 기본 탭 | `요청 JSON` → `응답 원문` → `상태·후보 요약` → `턴 로그` → `기술 기록` 순서다. 최초 진입은 첫 결정의 요청 탭이며 명시적 결정 링크가 있으면 해당 결정을 연다. |
| 확장 | 기본 5개 탭 뒤에 EX에 선언한 확장 탭만 정해진 순서로 추가한다. 계획·피해 계산·선택 확률 등이 해당한다. 기본 탭을 제거·재정렬하거나 확장 탭을 첫 화면으로 삼지 않는다. |
| 원문 조작 | 요청·응답·기록의 복사/다운로드를 제공한다. JSON은 읽기 쉬운 들여쓰기·구문 강조를 사용하고 원값을 보존한다. |

기본 탭은 자료가 없다는 이유로 사라지지 않는다. 선언한 확장도 결정별 자료 부재를
별도로 표시한다. 원문 응답 형식은 공급자별 저장 형식을 보존하며 JSON 형태를 임의로
만들지 않는다. 요청을 기록에서 복원하면 출처·한계를 밝힌다. 자동 선택의 관측 메시지를
실제 전송 요청으로, 미호출을 모델 응답으로 표시하지 않는다.
자동 선택·실패·응답 미수신·자료 미수집·결정 없는 턴을 구분한다.
실제 행동 이름과 공개 HP/미확인 표시는 C-047을 유지한다.

### 리플레이와 정보의 연결

- 턴·결정 선택은 영상을 일시정지하고 해당 턴 시작으로 이동시킨다.
  같은 턴의 일반 행동·강제 교체는 같은 영상 위치를 사용하되 결정 정보는 각각 유지한다.
- 탭 전환·영상 재생·영상 수동 이동은 선택 결정을 바꾸지 않는다.
  영상의 진행 상태를 모델이 당시 본 정보로 해석하지 않는다.
- 영상 로딩 전이나 빠른 연속 선택 시 마지막 선택만 적용한다. 늦게 도착한 자료가 다른
  경기·actor·결정의 표시를 덮어쓰지 않게 한다.
- 준비 구간은 기록된 준비 위치로 연결한다. 턴 미상이나 재생 자료 부재는 한계를 표시하며
  임의의 턴·결정·배틀 상태를 합성하지 않는다.
- 리플레이는 해당 actor의 공개 기록을 사용한다. 요청·상태는 결정 당시 경계를 보존하고,
  전체 턴 로그에는 결정 이후 결과도 포함됨을 표시한다. 결정 전 범위를 제공할 때는
  저장 cutoff를 적용한다.
- 외부 애니메이션 자산 실패 시 공개 로그를 제공한다. 입력·응답·선택·공개 로그와
  복사/다운로드는 상대경로 로컬 자산으로 폴더 이동 후 `file://` 오프라인에서도 유지한다.
  애니메이션의 외부 연결 의존성을 명시한다.

원자료·계산을 다시 만들거나 값·실험 결과·분모를 바꾸는 규격이 아니다.
C-009의 안전한 표시와 무결성 경고, C-047의 원본/복사본 출처·봉인 경계를 유지한다.

<a id="viewer-versioning"></a>

### 판본 고정과 변경

- EX에는 UI 규격 버전, 생성기 식별자·렌더러 판본과 정확한 소스 참조
  (commit 및 미커밋 변경 보존본 또는 기존 renderer manifest), 확장 탭·순서, 출력 위치를
  기록한다. UI 규격과 렌더러 판본은 별개이며 같은 이름만으로 지원 완료를 주장하지 않는다.
- 새 실험의 실행 전 지원 여부를 확인한다. 미지원 항목은 선행 구현 EP에 연결하고
  해당 항목의 검증 후 실행한다. 문서 등록이나 일부 기능의 과거 검증은 v1 전체 지원
  확인을 대신하지 않는다.
- 기본 구조·동작 등 규격의 의미를 바꾸면 새 Decision과 다음 UI 규격 버전을 등록한다.
  기존 버전의 정의를 새 의미로 덮어쓰지 않는다. 허용된 확장·규격 내 표시 교정은
  렌더러 판본을 구분하고 [변경일지](CHANGELOG.md)에 기록한다.
- 변경일지에는 날짜, 변경 전후·이유, UI/렌더러 판본, 적용 EX, D·EP/승인 근거,
  검증 결과 또는 미실행 한계를 남긴다. 정정은 원기록을 지우지 않고 후속 항목으로 연결한다.
  승인·재승인 판단은 [INDEX](../../INDEX.md#workflow)를 따른다.
- 실행 중 선택한 규격·생성기 판본을 조용히 교체하지 않는다. 완료 후 표시 수정은
  승인된 범위에서 기존 판본을 보존하고 새 판본·이력을 연결한다. 기존 실험의 재내보내기는
  자동 승인되지 않으며 적용 규격과 변경 범위를 별도로 기록한다.

### 기준 근거와 적용 경계

화면 기준은 [EP-177](plans/EP-177-ex108-viewer-layout.md)의
[검증 화면](../../exec-plans/evidence/ep177/viewer.png)과
`tacit-ruleqa-researcher-v2`이다. 동기화 동작은 [EP-150](plans/EP-150-planner-replay-viewer.md)와
C-073을 참고한다. EX-108은 자동 영상 이동을 구현하지 않았으므로 v1 전체 준수 구현이 아니다.
생성기별 실제 지원 차이는 [구성 설명](ARCHITECTURE.md#viewer-ui-support)에 둔다.

신규 적용 범위에서 D-049의 응답 우선 노출·D-144/C-073의 계획 기본7탭은 위 기본5탭과
요청 첫 화면으로 대체한다. 원문 접근·계획 생성 결정 연결·계산 출처·공개 정보 경계 등
나머지 요건과 과거 적용 기록은 유지한다. 본 규격 채택은 생성기 코드의 자동 변경을 뜻하지 않는다.

<a id="c-073-planner-viewer"></a>

<a id="c-073--향후-glmjev-통합-뷰어"></a>
## C-073 — 향후 GLM·JEV 통합 뷰어

아래 기본7탭·계획 첫 화면은 D-144 당시 적용 규칙이다. D-172 이후 신규 등록 실험에는
[battle-viewer-ui-v1](#battle-viewer-ui-v1)의 기본5탭 뒤에 계획 등 확장을 두고 요청 탭으로
시작한다. 리플레이 동기화와 아래 출처·cutoff·재사용 계획·계산 관련 요건은 유지한다.

[D-144](decisions/D-144-planner-replay-viewer.md)/EP-150의 새 jev-planner export에 적용한다.
C-047·C-070/072와 실행 기록 형식을 유지하고 GLM 계획 기본7탭·리플레이를 함께 표시한다.
계획/선택/원문/계산은 같은 경기·actor·결정으로 연결하며 재사용 계획은 생성 결정을 명시한다.
턴/결정 선택만 재생을 정지하고 해당 턴 시작으로 이동한다. 같은 턴 다중결정도 같은 위치다.
리플레이 재생·수동이동·탭 전환은 정보 선택을 바꾸지 않으며 명시적 재정렬 버튼을 제공한다.
actor가 수신한 공개 행만 리플레이로 사용하고 결정 전 로그는 원래 cutoff를 적용한다.
결정 없는 턴·계획 없음·자동 선택·실패는 각각 구별한다.

큰 원문·피해 시나리오는 결정별 상대경로 로컬 스크립트로 지연 적재하고 늦은 자료의 덮어쓰기를
막는다. 피해는 observation의 감사 경로/해시와 표시명·계획 추가 전 입력 identity로 검증한다.
미제공·미계산·0을 구별하며 재계산하지 않는다. 외부 공식 Showdown 자산 실패 시 로컬 공개
로그를 제공하고 정보·복사/다운로드는 이동 후 file:// 오프라인에서도 유지한다.
원자료/복사본·renderer·공개로그 parser 출처를 기록하며 기존 EX-088/092 원자료·뷰어·봉인은 보존한다.
새 실행·모델·프롬프트·호출정책 변경을 포함하지 않는다.

<a id="c-009--pokéchamp-research-battle-observability"></a>
## C-009 — PokéChamp research battle observability

- Full-fidelity logging은 비어 있지 않은 명시적 `experiment_id`와 별도
  `POKECHAMP_DATA_ROOT`를 가진 research command에서만 활성화한다. Recorder가 없는 C-008
  qualification path는 prompt, response와 reasoning content를 계속 저장하지 않는다.
- Bundle identity와 위치는
  `<POKECHAMP_DATA_ROOT>/experiments/<experiment_id>/battles/<battle_id>/`다. ID는 path component로
  안전한 값이어야 하며 기존 directory와 충돌하면 실패한다. 완료 bundle을 자동 삭제하거나 source
  evidence를 덮어쓰지 않는다. Correction은 새 `battle_id`와 optional `replacement_for`를 사용한다.
- Schema version 1 source evidence는 다음 세 파일이다.
  - `manifest.json`: experiment/battle identity, source SHA, format, team, model configuration,
    UTC start/end, outcome, completeness, seal 상태.
  - `events.jsonl`: battle-global `event_seq` 순서의 `battle_start`, `protocol_in`,
    `decision_start`, `llm_call`, `decision_result`, `wire_action`, `battle_end`, `logging_error`.
  - `checksums.sha256`: seal된 `manifest.json`과 `events.jsonl`의 SHA-256.
- 모든 event는 `schema_version`, `experiment_id`, `battle_id`, `event_type`, `event_seq`, UTC
  timestamp와 battle-start 기준 monotonic offset을 가진다. 판단은 battle-global `decision_seq`,
  provider 호출은 battle-global `llm_call_seq`로 연결하며 `showdown_turn`은 표시용 값이다.
- Research `llm_call`은 provider에 실제 전달한 wire-level system/user prompt, provider reasoning,
  raw content, canonical parsed output, request/model/token/latency/stop metadata와 validation 결과를
  기록한다. Parent integration은 inbound battle protocol과 실제 outbound `/team`, `/choose`,
  `/forfeit` action을 player/transport 경계에서 기록한다.
- Research command는 player/challenge를 만들기 전에 data root, 새 bundle, manifest와 event stream을
  열어야 한다. 이 단계가 실패하면 battle을 시작하지 않는다. 시작 후 record failure는 gameplay
  control flow에서 격리하고 warning, 가능한 `logging_error`, final
  `evidence_complete=false`로 드러낸다.
- Seal 전 source file은 진행 중 evidence이며 partial일 수 있다. Seal은 source file을 닫고 final
  manifest를 기록한 뒤 checksum을 exclusive-create한다. `showdown.log`, `replay.html`,
  `report.html`, experiment별 `catalog.sqlite`와 `index.html`은 source에서 재생성 가능한 derived
  output이며 checksum 대상이 아니다.
- Renderer는 malformed/missing/tampered source를 성공 evidence로 만들지 않고 partial/integrity
  warning과 함께 가능한 내용을 표시한다. HTML은 모든 untrusted text를 escape하고 CSP를 적용한다.
  Network animation asset을 읽지 못해도 report의 정적 protocol timeline은 local에서 완전하게
  열려야 한다.
- Bundle은 `classification=research_observability`, `efficacy_evidence=false`다. 자동 L4/L5
  retrieval/write, hypothesis 평가, denominator 결정 또는 efficacy claim의 authority가 아니다.
- Credential 값은 qualification 및 research evidence 양쪽 모두에서 금지한다. Full-fidelity
  source는 prompt/reasoning, username과 protocol을 포함할 수 있으므로 local-only sensitive research
  data로 취급한다.

구현과 rationale: [`integration/pokechamp/README.md`](../../../integration/pokechamp/README.md),
[`D-010`](decisions/D-010-adopt-pokechamp-battle-observability.md).
