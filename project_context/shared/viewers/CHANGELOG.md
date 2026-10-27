# 배틀 viewer UI 변경일지

규격 원문은 [CONTRACTS](CONTRACTS.md#battle-viewer-ui-v1), 등록·확인 절차는
[연구 매뉴얼](../../RESEARCH_MANUAL.md#battle-viewer-workflow)에 둔다.
이 문서는 변경의 경위·적용 판본·근거를 누적하며 규범을 중복 정의하지 않는다.
과거 항목을 새 상태로 덮어쓰지 않고 정정/후속 항목에서 원항목을 연결한다.
변경 없이 같은 UI를 사용하는 새 EX는 적용 항목을 참조하면 되며 변경 사실을 만들지 않는다.

## 항목 형식

- 날짜·변경 ID/제목:
- 구분: 규격 변경 | 규격 내 확장 | 표시 교정 | 정정
- 변경 전 → 후·이유:
- UI 규격 전 → 후:
- 렌더러 식별자/판본·소스 전 → 후: (문서만이면 미변경)
- 적용 EX/범위·출력 판본/이전 판본 연결:
- 관련 D·EP·승인 근거:
- 검증 결과·근거 또는 미실행/미지원 한계:
- 정정/후속 대상: (없으면 없음)

<a id="ui-v1-adoption"></a>

## 2026-10-20 — UI v1 채택

- 구분: 규격 변경
- 변경 전 → 후·이유: C-047과 실험별 UI 계약에 분산된 표시 기준에서 공통 버전·확장·변경
  기록 체계로 전환한다. 실험마다 기본 화면이 달라지는 문제를 방지하려는 사용자 요청이다.
- UI 규격 전 → 후: 공통 UI 버전 없음 → `battle-viewer-ui-v1`.
- 렌더러 식별자/판본·소스 전 → 후: 미변경. 이번 작업은 문서·절차 정비이며 자동 적용은 없다.
- 화면 기준: [EP-177 검증 화면](../../exec-plans/evidence/ep177/viewer.png),
  [검증 기록](../../exec-plans/evidence/ep177/check.json),
  [EX-108 provenance](../../../exports/battle_viewers/ex108/provenance.json)의
  `tacit-ruleqa-researcher-v2` 및 `renderer_files` 참조.
  이 화면은 배치·기본5탭 기준이며 **자동 영상 이동은 기존 EX-108에 없는 추가 요구사항**이다.
- 동작 기준: [EP-150](plans/EP-150-planner-replay-viewer.md)의 동기화·선택 독립성.
  해당 생성기의 계획 우선7탭을 새 기본 화면으로 채택하지 않는다.
- 적용 EX/범위: D-172 채택 이후 이 연구선에 신규 등록하는 배틀 실험.
  이번에 적용 완료한 EX·새 출력 판본은 없음. 기존 실험·내보내기·봉인에 소급하지 않는다.
- 관련 D·EP·승인 근거: [D-172](decisions/D-172-battle-viewer-ui-standard.md),
  [EP-187](plans/EP-187-battle-viewer-ui-standard.md); 사용자의 기준 선택 및 계획 구현 지시.
- 검증: [문서 검증 보고](../../exec-plans/evidence/ep187/report.md).
  기존 EP-177/150의 증거는 각 당시 범위이며 새 v1 전체 구현 검증을 뜻하지 않는다.
  생성기별 차이는 [지원 현황](ARCHITECTURE.md#viewer-ui-support)에 기록한다.
- 정정/후속 대상: 없음.

<a id="ex112-ui-v1"></a>

## 2026-10-20 — EX-112의 UI v1 별도 판본

- 구분: 규격 내 확장
- 변경 전 → 후·이유: 실험별 API 탭·독립 턴 로그 화면을 공통 기본5탭·결정/턴 탐색·
  고정 리플레이와 선택 턴 자동 이동으로 재구성했다. 사용자 요청으로 EX-112에 명시 적용했다.
- UI 규격 전 → 후: 공통 버전 미선언 → `battle-viewer-ui-v1`.
- 렌더러 전 → 후: 기존 `openai_decisions_battle/viewer.py/html` →
  `openai-matchup-researcher-v1` (`openai_decisions_matchup_battle/viewer_v1.py/html/js`).
  정확한 소스 해시와 사본은 [새 provenance](../../../exports/battle_viewers/ex112-ui-v1/provenance.json)의
  `renderer_files` 및 내보내기 폴더의 `renderer-source/`에 둔다.
- 확장 탭 순서: 기본5탭 뒤 **요약 제거 원본 → 후보별 상성 요약 → 선택·전송**.
  전체 상태 원문·원 API 응답·내부 호환 응답·재시도·거부/미전송을 구별해 보존했다.
- 적용 EX/출력: [EX-112](../../research/input-and-memory/experiments/EX-112-openai-candidate-matchup-battle.md)의
  [새 열람 판본](../../../exports/battle_viewers/ex112-ui-v1/index.html).
  [이전 봉인 판본](../../../exports/battle_viewers/ex112/index.html)은 그대로 유지한다.
  EX-112 Stopped·EP-183 Blocked와 원자료·성적·분모는 변경하지 않았다.
- 관련 D·EP·승인 근거: D-172 및 [EP-188](plans/EP-188-ex112-viewer-ui-v1.md);
  사용자의 EX112 재구성 지시. 새 실험 실행·다른 EX 재내보내기는 포함하지 않는다.
- 검증: [완료 보고](../../exec-plans/evidence/ep188/report.md),
  [원자료/이전/새 판본 봉인](../../exec-plans/evidence/ep188/preservation.json),
  [이동 후 오프라인·실제 영상 검사](../../exec-plans/evidence/ep188/browser.json).
  원문 연결 전수 대조와 대표 UI·합성 경계 검사를 구분한다.
- 정정/후속 대상: [v1 채택](#ui-v1-adoption)의 EX-112 구현 후속이다.
  EX-108과 기존 planner 생성기의 미지원 항목을 함께 해결한 것으로 해석하지 않는다.

<a id="ex112-response-names"></a>

## 2026-10-20 — EX-112 응답 choice의 실제 이름 표시

- 구분: 표시 교정
- 변경 전 → 후·이유: 응답 탭에서 move/switch ID만 읽어야 했던 화면에 원 ID와 실제
  기술명·테라 여부·교체/선봉 포켓몬명을 함께 표시한다. 확률 목록에도 같은 이름을 표시한다.
- UI 규격: `battle-viewer-ui-v1` 유지. 렌더러: `openai-matchup-researcher-v1` →
  `openai-matchup-researcher-v2`. 기본 탭·확장 순서는 유지한다.
- 연결 기준: raw 응답의 `answers[].choice`·`probabilities[].value`를 해당 결정 관측 후보로
  해석한다. 실제 전송 선택이나 다른 결정의 팀으로 대신 해석하지 않는다. 정보 부재는 미확인이다.
  이름은 표시용 요약이며 펼친 HTTP 원문과 복사·다운로드 JSON에 필드를 추가하지 않는다.
- 적용 EX/출력: [EX-112 새 판본](../../../exports/battle_viewers/ex112-ui-v1-names/index.html).
  [이름 표시 전 UI v1](../../../exports/battle_viewers/ex112-ui-v1/index.html)과
  [수집 당시 판본](../../../exports/battle_viewers/ex112/index.html)은 보존한다.
- 소스/판본 근거: [provenance](../../../exports/battle_viewers/ex112-ui-v1-names/provenance.json)의
  `renderer_files`와 `renderer-source/` 사본.
- 관련 D·EP·승인: D-172/D-101, [EP-189](plans/EP-189-ex112-response-action-names.md),
  현재 사용자의 응답 탭 실제 이름 표시 요청.
- 검증: [보고](../../exec-plans/evidence/ep189/report.md) ·
  [실제 오프라인 사례](../../exec-plans/evidence/ep189/browser.json) ·
  [보존/동일 replay](../../exec-plans/evidence/ep189/preservation.json).
- 후속 대상: [EX-112 UI v1](#ex112-ui-v1). 실험 결과·원자료·분모·Stopped/Blocked는 유지한다.


<a id="ex114-ruleqa-v1"></a>

## 2026-10-21 — EX114 JevK5 규칙 LoRA UI v1

- 구분: 규격 내 확장. UI 규격은 battle-viewer-ui-v1 유지.
- 생성기: EX111 원문export와 EP188/189 UI/리플레이브리지를 독립복사한 `jevk5-ruleqa-researcher-v1`.
- 기본5탭 뒤 실제프롬프트·선택지확률·선택/전송. HTTP원문과 별도의 후보점수판독을 구분하고 실제행동이름을 연결한다.
- 적용: EX114 신규내보내기만. 기존EX111/112 원자료/뷰어/생성기는 변경하지 않는다.
- 승인·범위: [D173](../../research/rule-learning/decisions/D-173-jevk5-ruleqa-battle32.md) / [EP191](../../research/rule-learning/plans/EP-191-jevk5-ruleqa-battle32.md).
- 검증: 합성UI4검사(기본탭/원문/무자료/악성문자/최신선택·pause/seek·독립성/모바일) 통과.
  [로그](../../exec-plans/evidence/ep191/viewer-tests.log). 모의자료 이동후오프라인 확인과 본출력 검증은 EP191에서 이어서 기록한다.
- 소스: integration/jevk5_ruleqa_battle/viewer.py, viewer_ui.py, viewer.html, viewer.js. 수집전manifest에서 hash를 동결한다.

EX114 선행 모의내보내기의5대표/이동후오프라인/복사·다운로드/모바일과 실제리플레이pause/seek 확인을 완료했다.
[모의검증](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-114/mock-browser.json). 모의이미지는 mock-ui에 별도보존한다.

EX114 본32페이지/1,072결정의 전수내보내기·봉인과 5대표상태·이동후오프라인·복사/다운로드·1440/768/390 화면·실제리플레이pause/seek를 통과했다.
[본검증](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-114/browser.json) · [완료보고](../../exec-plans/evidence/ep191/report.md).

## EX115 후보 중심 v7 — 2026-10-21

D-179/EP-202/EX-115 승인으로 `candidate-action-researcher-v1`을 추가한다.
UI 규격은 battle-viewer-ui-v1이다. 기존 openai-matchup-researcher-v2의 배치/동기화 코드를
별도 판본에 보존하고 확장을 재구성 전 입력 → 후보별 적용 결과 → 선택·전송으로 바꾼다.
응답 탭에 모든 HTTP 응답/응답 시도와 최종 선택을 구별한다. 이전 판본은 유지한다.
합성 UI5검사는 통과했으며 실제 내보내기·이동후 오프라인·리플레이 검증은 EP202 근거로 연결한다.

EX115 실행 전 지원 확인: 합성6검사와 최종 모의2경기/113결정 전수 원문대조, 이동후6종·3화면폭·실제1턴 pause/seek 통과. 브라우저 checker의 동일 hash 재열기 가정은 교정했으며 수집/UI 결함과 구분해 EP202 증거에 보존했다.

EX115 최종 내보내기: 32경기·1021결정 원문/공개로그 전수 대조, 이동후 선봉/일반/강제교체/자동4종·3폭·복사/다운로드·실제리플레이 동기화 통과. 본수집 재질의0이며 재질의/실패 표시는 합성/모의 근거와 구분한다. [뷰어](../../../exports/battle_viewers/ex115/index.html) · [검증](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-115/evidence/live-browser/receipt.json) · [완료 보고](../../exec-plans/evidence/ep202/report.md).

## EX117 생존·교체 비용 v7 — 2026-10-21

D182/EP206 승인으로 candidate-action-researcher-v2를 EX117에 적용한다.
UI는 battle-viewer-ui-v1 및 기존8탭을 유지하며 실험 ID·목록·리플레이·출처 표시를 manifest에 연결한다.
EX115 동결 렌더러/출력은 유지한다. 새 검증은 EP206에 기록하며 현재 본경기는 미실행이다.

EX117 실행 전 검증: 관련46검사와 모의2경기/113결정 전수대조, 이동후6종·3화면폭·
복사/다운로드·실제리플레이1턴 pause/seek 통과. 정확한 renderer source는 EX117/renderer-manifest.json에 동결했다.

EX117 최종 내보내기: 32경기 페이지·1209결정 원문/공개로그 전수대조, 이동후6종(실패/응답복구 포함)·
3폭·실제리플레이1턴 pause/seek 통과. [뷰어](../../../exports/battle_viewers/ex117/index.html).
경기 유효분모는30이며 뷰어 검증 완료를 실험 목표달성으로 해석하지 않는다.

<a id="ex134-laya-h2h-v1"></a>

## 2026-10-26 — EX-134·EX-135 laya 직접 대결 UI v1 확장(비교 진영 페이지)

- 구분: 규격 내 확장
- D-194/EP-217 승인으로 `laya-imitation-researcher-v1` 경기 페이지를 경기마다 두 개 만든다(`headtohead.export_viewer`).
  - `battle-NNN`: 기준 모델 진영. 기존과 같은 8탭이다.
  - `battle-NNNb`: 비교 모델 진영. `opponent/events.jsonl`에서 만들고, 압축 입력은 그 모델의 렌더러로 복원한다. 결과는 그 진영 기준으로 표시한다.
- 목록은 경기당 한 행이다. 열은 비교 모델, 조합, 기준 진영, 기준 결과, 턴이고, 링크가 두 개다.
- **실행 전 지원 확인**: mock 4경기로 임시 뷰어를 만들어 확인했다. 폴더 이동 후 오프라인 1440px·390px에서 두 진영 페이지 모두 8탭, 페이지 오류 0이었다([검사](../../exec-plans/evidence/ep217/mock-viewer-check.json)). 검사 도구는 `browser_check.py h2h`다.

<a id="ex127-laya-v1"></a>

## 2026-10-26 — EX-127 laya v2+테라·v2+테라+효과 지식 같은 실행 UI v1

D-188/EP-213 승인으로 `laya-imitation-researcher-v1`(EX-125와 같은 생성기와 인자)을 적용했다. 두 모델 모두 v2 렌더러로 압축 입력을 복원한다.

- **본 내보내기 확인**(256경기):
  - 폴더 이동 후 오프라인 1440px·390px 통과, 8탭 확인, 페이지 오류 0([검사](../../exec-plans/evidence/ep213/viewer-check.json))
  - 리플레이 턴 이동 검사는 이번 세션에서 해당 검사 도구를 찾지 못해 수행하지 않았다(생성기·인자는 EX-125와 같다).
  - 상위 목록에 연결했다.

<a id="ex125-laya-v1"></a>

## 2026-10-23 — EX-125 laya v2·v2+테라 같은 실행 UI v1

D-187/EP-212 승인으로 `laya-imitation-researcher-v1`(EX-122와 같은 생성기와 인자)을 적용했다. 두 모델 모두 v2 렌더러로 압축 입력을 복원한다.

- **본 내보내기 확인**(256경기, 11,380결정):
  - 폴더 이동 후 오프라인 1440px·390px 통과, 페이지 오류 0([검사](../../exec-plans/evidence/ep212/viewer-check.json))
  - 리플레이 턴 이동: 온라인과 오프라인 모두 통과([검사](../../exec-plans/evidence/ep212/viewer-replay-check.json))
  - 상위 목록에 연결했다.

<a id="ex122-laya-v1"></a>

## 2026-10-23 — EX-122 laya v1·v2 같은 실행 UI v1

D-185/EP-210 승인으로 `laya-imitation-researcher-v1` 생성기를 EX-122에 적용했다.

- **생성기 변경**: `viewer.export`에 선택 인자 `renderer_for(row)`를 더했다. 슬롯 모델에 맞는 렌더러(v1 또는 v2)로 압축 입력 탭을 복원한다. 기본값은 v1이다.
- **목록 열**: 모델, 조합, 시드, laya 팀 유형
- **본 내보내기 확인**(256경기, 11,027결정):
  - 폴더 이동 후 오프라인 1440px·390px 통과, 페이지 오류 0([검사](../../exec-plans/evidence/ep210/viewer-check.json))
  - 리플레이 턴 이동: 온라인과 오프라인 모두 통과([검사](../../exec-plans/evidence/ep210/viewer-replay-check.json))
  - v2 128경기의 압축 입력에 v2 속도 줄이 있고, v1 128경기에는 없음을 확인했다.
  - 상위 목록에 연결했다.

<a id="ex120-laya-v1"></a>

## 2026-10-22 — EX-120 laya 새 팀 일반화 UI v1

D-184/EP-209 승인으로 `laya-imitation-researcher-v1` 생성기를 EX-120에 적용했다.

- **생성기 변경**: `integration/laya_imitation/viewer.export`에 선택 인자 `meta`(실험, 계획, 제목, 소개, 쌍 수, 변경일지)와 `columns`(목록 추가 열)를 더했다. 기본값은 EX-119와 같다. EX-119를 다시 내보내 renderer-source 해시 외 모든 파일이 같음을 확인했다.
- **EX-120 목록**: 조합, 시드, laya 팀 유형, 상대 팀 유형 열을 추가했다. 경기 화면의 8탭과 확장 탭은 EX-119와 같다.
- **실행 전 지원 확인**: 같은 생성기로 EX-120 mock 2경기를 수행했다. 생성기 지원은 EX-119 확인을 승계한다.
- **본 내보내기 확인**(128경기, 5,623결정):
  - 폴더 이동 후 오프라인 1440px·390px에서 목록 128행, 8탭 순서, 방향키와 턴 이동, 압축 입력 표시, 페이지 오류 0으로 통과했다([검사](../../exec-plans/evidence/ep209/viewer-check.json), [화면](../../exec-plans/evidence/ep209/viewer-check.png)).
  - 리플레이 턴 이동은 온라인에서 영상으로, 오프라인에서 공개 로그로 표시했고 오류는 0이다([검사](../../exec-plans/evidence/ep209/viewer-replay-check.json)).
  - 상위 목록에 연결했다.

<a id="ex119-laya-v1"></a>

## 2026-10-22 — EX-119 laya 압축 입력 UI v1

D-183/EP-208 승인으로 `laya-imitation-researcher-v1`(`integration/laya_imitation/viewer.py/html/js`)을 추가한다.

- **기반**: battle-viewer-ui-v1. 배치, 탐색, 리플레이 bridge, 스타일은 EX-114 `jevk5-ruleqa-researcher-v1`의 html·`viewer_ui`(`style`, `render_replay`)를 재사용한다.
- **viewer.js 변경**: EX-071 이벤트 형식(입력 본문, 스냅샷, 원 HTTP)에 맞췄다.
- **확장 탭**: 기본 5탭 뒤에 `압축 입력` → `선택지 확률` → `선택·전송`을 둔다.
- **압축 입력 탭**: 저장된 요청에서 같은 렌더러로 결정적으로 복원한 모델 입력을 보여준다.
- **EX-114 판본**: 변경하지 않는다.

**실행 전 지원 확인**:
- 대상: CPU 모의 2경기(89결정)를 내보낸 뒤 폴더를 옮겨 오프라인으로 열었다.
- 결과: 1440px·390px에서 8탭 순서 확인, 요청 탭 첫 화면, 방향키 결정 이동, 턴 이동, 압축 입력 표시, 페이지 오류 0으로 통과했다.
- 증거: [검사](../../exec-plans/evidence/ep208/viewer-mock-check.json), [화면](../../exec-plans/evidence/ep208/viewer-mock.png)
- 한계: 애니메이션은 외부 자산이 필요하다. 실제 리플레이 pause/seek는 본 내보내기에서 확인한다.

**본 내보내기 확인** (2026-10-22, EX-119 32경기·1,433결정):
- 폴더 이동 후 오프라인: 1440px·390px에서 목록 32행, 8탭 순서, 요청 탭 첫 화면, 방향키 결정 이동, 턴 이동, 압축 입력 표시, 페이지 오류 0으로 통과했다([검사](../../exec-plans/evidence/ep208/viewer-final-check.json), [화면](../../exec-plans/evidence/ep208/viewer-final-check.png)).
- 리플레이: 온라인에서 영상 준비 후 턴 이동(seek)이 동작했다. 오프라인에서는 공개 로그로 대체 표시했다. 두 경우 모두 페이지 오류는 0이다([검사](../../exec-plans/evidence/ep208/viewer-replay-check.json)).
- 상위 목록 `exports/battle_viewers/index.html`에 연결했다.

<a id="ex123-ruleqa-v1"></a>

## EX123 System One 연구자 뷰어 v1

- 적용: D186/EP211/EX123, battle-viewer-ui-v1, jevk5-system1-researcher-v1.
- EX114의8탭·원문·리플레이연결을독립복사하고GPU별봉인원문을유지한전역32슬롯목록을추가했다. 기존출력은수정하지않았다.
- 사전 CPU/UI검사·모의6경기·3shard오프라인/이동/반응형/실제영상pause/seek·전역6링크검증통과. 실제32경기와사후검증은아직미실행이다. 소스는EX123의각shard manifest/source에동결한다.

- EX123 사후검증 완료: 실제32페이지·1169결정의원문/요청/응답, 3shard의오프라인·이동·반응형·리플레이와전역32고유링크를검증했다. 원실행7521파일·뷰어1347파일의봉인대조를통과했다. [종결](../../exec-plans/evidence/ep211/closure.json) · [뷰어](../../../exports/battle_viewers/ex123/index.html).

<a id="ex137-laya-v1"></a>

## 2026-10-27 — EX-137·EX-138 laya v5 렌더러 압축 입력 탭

- 구분: 규격 내 확장. UI 규격은 battle-viewer-ui-v1과 `laya-imitation-researcher-v1` 그대로다.
- D-195/EP-218 승인으로 압축 입력 탭이 `laya-v5t` 경기를 v5 렌더러(`compact_v5`, 상대 아이템 상태·상태 카운터)로 복원한다. 다른 모델은 각자의 렌더러를 그대로 쓴다.
- 실전 입력에는 D-195 파서 선택 필드(`item_state`, `status_counter`, `status_source`, `weather_turn`)가 들어 있다. 요청 JSON 탭에 그대로 보이며 v1~v4 렌더 결과는 바뀌지 않는다.
- 적용: EX-137(`comparison.export`), EX-138(`headtohead.export_viewer`, 경기당 두 페이지는 EX-134 확장 그대로).

<a id="ex139-laya-v1"></a>

## 2026-10-27 — EX-139 laya v2+테라 보정 입력(fix·info) 압축 입력 탭

- 구분: 규격 내 확장. UI 규격은 battle-viewer-ui-v1과 `laya-imitation-researcher-v1` 그대로다.
- D-196/EP-219 승인으로 압축 입력 탭이 조건별 실전 렌더러로 복원한다(`comparison.RENDER` → `input_variants.renderer`). `laya-v2t-fix` 경기는 `v2fix`(v2 형식, `features_v5` 값), `laya-v2t-info` 경기는 `v2info`(v2 모듈 + v5 `items`·`counters`)다. 두 조건 모두 EX-124 체크포인트다.
- 서빙 identity의 `render`는 실제 렌더(`laya-compact-v5[...]`)이고, `trained_render`는 학습 렌더(v2)다. 요청 JSON 탭의 D-195 선택 필드는 EX-137과 같다.
- 적용: EX-139(`variant_battle.export`). 사전 점검으로 mock 2경기 사본 뷰어의 Playwright 검사(1440·390, 페이지 오류 0)를 통과했다.

<a id="ex140-laya-v1"></a>

## 2026-10-27 — EX-140 laya v2+테라 테라 합산 결정·테라 방어 문구 압축 입력·확률 탭

- 구분: 규격 내 확장. UI 규격은 battle-viewer-ui-v1과 `laya-imitation-researcher-v1` 그대로다.
- D-197/EP-220 승인으로 압축 입력 탭이 조건별 실전 렌더러로 복원한다. `laya-v2t-fix-tp1`·`-tp3` 경기는 `v2fix`, `laya-v2t-fix-tdef` 경기는 `v2fixtd`(테라 선택지에 `; takes …; worst xN`)다. 세 조건 모두 EX-124 체크포인트다.
- tp 경기의 선택지 확률 탭은 테라 합산 결정 분포(k=1·3)다. 모델 분포는 응답 원문 탭의 `model_probabilities`에 있다. 서빙 identity에 `decision`(규칙·k)이 있다.
- 적용: EX-140(`tera_battle.export`).

<a id="nhj-20261027-laya-v1"></a>

## 2026-10-27 — NHJ-20261027 사람 대 LayaBot 4경기 뷰어

- 구분: 규격 내 적용(새 실험 아님). UI 규격은 battle-viewer-ui-v1과 `laya-imitation-researcher-v1` 그대로다.
- 원본 `/workspace/data/NHJ-20261027/NHJ-20261027`(경기별 `events.jsonl` 해시를 원본 manifest와 대조)을 뷰어 run 구조로 옮겨 `viewer.export`로 생성했다. 압축 입력 탭은 서빙 때와 같은 v2 렌더러다(`laya-v2t`, EX-124 `12519d98…`).
- 기록은 LayaBot 쪽뿐이며 사람의 선택 요청은 없다. 출력 `/workspace/exports/battle_viewers/nhj-20261027/`(4경기, 132결정), Playwright 1440·390 페이지 오류 0.
