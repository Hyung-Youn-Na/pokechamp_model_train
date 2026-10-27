# 공통 관측·뷰어 — 구성 설명

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.

<a id="viewer-ui-support"></a>

## 공통 UI 규격과 현재 생성기의 차이

[D-172](decisions/D-172-battle-viewer-ui-standard.md)의
[battle-viewer-ui-v1](CONTRACTS.md#battle-viewer-ui-v1)은 신규 적용 규격이다.
[EP-187](plans/EP-187-battle-viewer-ui-standard.md)은 문서·절차만 정비했으며
생성기 통합·기존 내보내기 재생성은 수행하지 않는다.

아래는 2026-10-21 기준 대표 생성기의 소스·검증 기록 대조다. 각 행에 명시한 판본·실험
범위만 다루며 전체 생성기를 일괄 인증하지 않는다. 새 실험은 사용할 정확한 판본을 별도로 확인한다.

| 생성기·참조 범위 | 이미 있는 기능·근거 | v1과의 차이·미확인 |
|---|---|---|
| `integration/tacit_ruleqa_battle/viewer.py/html/js` · EX-108 `tacit-ruleqa-researcher-v2` | 기본5탭·요청 첫 화면·결정/턴 탐색·옆 리플레이·공개 로그. [EP-177](plans/EP-177-ex108-viewer-layout.md) | 결정 이동은 공개 로그만 갱신하며 영상 자동 일시정지/턴 이동은 없음. v1 전체 지원 미완료. |
| `integration/jev_planner/viewer.html/js`, `replay.js` | 턴 시작으로 pause/seek, 정보 선택과 영상 조작 독립, 마지막 선택 유지·오프라인. [EP-150](plans/EP-150-planner-replay-viewer.md) | 계획 우선7탭으로 기본5탭·요청 첫 화면·확장 뒤 배치와 다름. v1 전체 지원 미완료. |
| `integration/openai_decisions_matchup_battle/viewer_v1.py/html/js` · `openai-matchup-researcher-v2` | 기본5탭·EX-112 확장3탭·결정/턴 탐색·고정 리플레이·pause/seek·선택 독립·마지막 선택·모바일/오프라인. [EP-188](plans/EP-188-ex112-viewer-ui-v1.md)의 UI v1에 [EP-189](plans/EP-189-ex112-response-action-names.md)의 응답 choice/확률 후보 실제 이름 표시를 추가. | EX-112 별도 판본 범위의 검증이다. 기존 공유 `export`와 다른 실험 생성기로 자동 전파되지 않는다. 애니메이션은 외부 자산 필요. |
| `integration/jevk5_ruleqa_battle/viewer.py/html/js` · `jevk5-ruleqa-researcher-v1` | EX114의 기본5탭·확장3탭·후보 실제이름·결정/턴 탐색·pause/seek·선택 독립·모바일/오프라인. [EP191](../../research/rule-learning/plans/EP-191-jevk5-ruleqa-battle32.md)의 합성·모의 및 본32경기 검증. | EX114 독립판본 범위. 원 HTTP와 정규화 선택확률을 구별하며 애니메이션은 외부 자산 필요. |
| `integration/candidate_action/viewer.py/html/js` · EX-115 `candidate-action-researcher-v1` | 기본5탭·재구성 전/후보적용/선택 확장, 재질의 전체 원문과 최종 선택, 원문 전수대조·합성6검사·모의2경기 이동후6종/3폭/실제 replay 동기화와 본32경기·1021결정 원문 전수대조/오프라인/실제 replay 검증. [EP-202](../../research/input-and-memory/plans/EP-202-candidate-action-v7.md) | EX-115 판본 범위. 공유 CSS·이름·replay bridge는 별도 renderer-manifest에 고정. 애니메이션은 외부 자산 필요. |
| 그 밖의 실험별 생성기 | 각 EP의 기존 범위 증거를 참조 | 이 문서 작업에서 v1 전체 지원을 검증하지 않음. 새 EX의 지원 확인 대상. |

현재 단일 공통 렌더러로 강제되는 구조는 아니다. 미지원 항목의 구현은 향후 해당 실험의
선행 EP 범위로 등록한다. EX-108의 배치와 planner 동기화 기능을 각각 확인한 사실을
조합된 v1 구현의 검증으로 간주하지 않는다. 적용 이력은 [변경일지](CHANGELOG.md)를 따른다.

EP-188의 EX-112 재내보내기는 이전 viewer·원자료를 읽기 전용으로 검증하고, 저장된 결정/
공개 로그는 그대로 복사해 새 화면을 생성한다. 기존 action-labels와 연구자용 CSS를 재사용하며,
리플레이는 기존 공식 renderer에 검증된 planner pause/seek bridge를 결합한다.
브리지는 sandbox iframe 안에서 부모의 선택만 수신하고 parent는 해당 iframe의 준비 메시지만
수신한다. 렌더러 소스 사본·이전 출처·원자료 identity·새 봉인은 새 폴더에 보존한다.

<a id="연구-관측봉인viewer"></a>
## 연구 관측·봉인·viewer

정상 종료 실험의 열람용 복사본은 [C-047](../../CONTRACTS.md#c-047-viewer-export)에 따라
`exports/battle_viewers/<실험ID>/index.html`에 둔다. 원본 봉인과 분리된 완료 산출물이며
상위 index에서 탐색한다. EX-050은 경기별 입력·응답과 고정 리플레이 패널을 제공한다.
기존 replay renderer로 actor protocol을 재생하며 애니메이션은 공식 외부 자산,
입력·응답·턴 탐색·protocol fallback은 로컬 파일을 사용한다.
`jev_viewer.py`는 봉인된 input.payload와 transport.model을 단일 요청 객체로 복원하고
실험자용 요청/응답·상태 요약·기술 기록 탭과 JSON 복사/다운로드를 생성한다.
API 미호출 결정은 관측/후보로 표시하며 원본 전체 기록을 별도로 유지한다.
jev-researcher-v2는 좌우 방향키 결정 탐색과 상대 HP의 공개 백분율 요약을 제공하며,
원래 요청 JSON과 자기 HP 절대값은 그대로 표시한다.

Decision [`D-010`](decisions/D-010-adopt-pokechamp-battle-observability.md)은 qualification과 분리된
opt-in logging path를 정의한다.

```text
scripts/pokechamp-env research run --experiment-id <tag>
  -> required POKECHAMP_DATA_ROOT + exclusive battle bundle open
  -> parent TraceablePlayerMixin
       inbound Showdown protocol -> protocol_in
       each request -> decision_start / decision_result
       actual transport send -> wire_action
  -> OllamaCloudBackend(trace_sink=...)
       effective prompt + reasoning/raw/parsed output + validation -> llm_call
  -> manifest.json + events.jsonl -> final manifest -> checksums.sha256
  -> derived showdown.log / replay.html / report.html
  -> experiment catalog.sqlite / index.html rebuild
```

Source evidence와 write authority는
`<POKECHAMP_DATA_ROOT>/experiments/<experiment_id>/battles/<battle_id>/`에만 있다. Qualification은
trace sink를 전달하지 않으므로 기존 `.artifacts/pokechamp/` content 최소화 동작을 유지한다.
Renderer와 catalog builder는 source를 read-only input으로 사용하며 derived output만 교체한다.
Showdown animation은 official network asset을 선택적으로 사용하지만 report의 decision card와 turn
timeline은 embedded static HTML이므로 offline에서도 동작한다. 이 경로는 자동 memory write나
efficacy 분석을 수행하지 않는다.
Report는 sandbox iframe으로 replay를 표시하고 CSS sticky 패널을 사용해 decision 스크롤 중에도
재생 화면을 유지한다. 넓은 화면은 오른쪽 패널, 좁은 화면은 상단 패널을 사용한다.
[D-049](decisions/D-049-viewer-turn-tabs.md) 당시 구현의 report는 기록된 `showdown_turn`으로
준비/턴/턴 미상 탭을 구성하고 같은 턴의 결정은 순서대로 함께 표시한다. 바로가기·이전/다음,
키보드 탭 이동과 기존 decision/issue fragment 및 URL history 복원을 내장 JavaScript로 제공한다.
각 LLM 호출의 reasoning/원문 답변은 항상 펼치고 입력·B2 원본·metadata와 전체 protocol은
별도 details로 열람한다. 스크립트는 CSP SHA-256으로 허용하며 비활성 시 모든 결정이 정적으로
표시된다. 기존 실험 viewer는 재생성하지 않았고 source schema/parser/계산 경로는 유지한다.

<a id="d-101-결정-이름-표시"></a>
## D-101 결정 이름 표시

Qwen/JEV viewer builder는 공통 `viewer_assets/action-labels.js`를 HTML 안에 포함한다.
후보의 move_ref와 해당 결정 self_team/current_move_slots에서 기술명을, 후보 설명에서
교체/선봉 대상명을 해석하고 테라 여부를 표시한다. 원 JSON/ID/명령/q와 실행 의미는 유지한다.
EX-063 현재 링크는 새 표시이며 이전 봉인 내보내기는 ex063-v1에 연결한다.
