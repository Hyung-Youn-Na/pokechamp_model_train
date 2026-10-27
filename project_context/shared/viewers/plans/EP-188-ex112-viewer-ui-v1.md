# EP-188 — EX-112 viewer UI v1 재구성

- 상태: Completed
- 생성일: 2026-10-20
- 책임자: Codex
- 승인: 사용자의 EX112에 확정 viewer 설계를 적용한 재구성 요청.
- 관련: D-172, EP-187, EP-177, EP-150, C-047, EX-112/EP-183.
- 연구선·checkout: research/model-training /workspace; 시작 commit feda62f733c1b470364868262c789ec857ef67f5.
- 기존 미커밋 변경 보존. interpreter는 기존 pokechamp/.venv/bin/python, 브라우저는 /tmp/ep037/tools/bin/python.
- 새 출력: exports/battle_viewers/ex112-ui-v1; 증거 project_context/exec-plans/evidence/ep188.
- 읽기 전용: 기존 exports/battle_viewers/ex112 및 provenance가 가리키는 EX-112 collection·보고·봉인.

## 범위·규격

현재 사용자의 명시적 재내보내기 요청에 따라 과거 EX-112의 새 열람 판본에만
[battle-viewer-ui-v1](../CONTRACTS.md#battle-viewer-ui-v1)을 적용한다.
생성기는 별도 integration/openai_decisions_matchup_battle/viewer_v1.py/html/js로 두며
기존 공유 생성기·실행기·동결 source·원자료·판정은 변경하지 않는다.
기본5탭 뒤 확장 순서는 요약 제거 원본, 후보별 상성 요약, 선택·전송이다.
렌더러 판본은 openai-matchup-researcher-v1, 소스 identity는 새 provenance에 기록한다.
기존 판본은 ex112에 보존하고 검증된 새 판본으로 상위 목록·EX의 현재 열람 링크를 연결한다.

INDEX/CHARTER/매뉴얼·STATUS·계획 색인 및 뷰어 계약/구성, EP-187/177/150,
Blocked EP-183/179/140/163/119와 Paused EP-126, Active EP-184의 보존 경계를 확인했다.
이번 범위는 표시 구현·검증이며 기존 연구 재개·보충 경기·API/GPU 호출·피해 재계산은 없다.
EX-112 Stopped·EP-183 Blocked와 유효31/32·실패1·15완료쌍을 유지한다.

## 완료 기준

- [x] 기본5탭·확장·탐색·원문·상태 요약·고정 리플레이·좁은 화면 구현
- [x] 선택 턴 pause/seek·동일 턴 복수결정·조작 독립·마지막 선택 유지
- [x] 원본/기존뷰어 봉인 확인, 전체32시도·913결정 원문/공개로그 대응 및 새 출처·봉인
- [x] 이동후 오프라인·키보드/탭·복사/다운로드·모바일 및 선봉/일반/강제교체/자동/실패/재시도 검사
- [x] 결정 없는 턴·자료 없음·악성문자 등 실제 없는 경계 합성 검사와 실제 animation 확인
- [x] 변경일지·EX 열람판본·목록·구성·등록 색인·보고/링크 갱신

## 검증·중단

C-047 identity와 원자료 보존을 확인하고 원문 연결은 전수 대조한다.
대표 브라우저 확인은 실제 종류별 결정과 실패/재시도를 포함하며 없는 사례는 합성으로 구분한다.
관련 변경·실패·미해결 우려가 없는 검사 반복은 하지 않는다.
원자료/기존 봉인 불일치는 내보내기를 중단한다. INDEX의 중단·승인 기준을 따른다.
비실험 표시 작업이므로 재수집·실험시계는 해당 없음. 설명 의미 평가는 별도 수행하지 않는다.

## 진행

- 2026-10-20 — 승인 범위 등록. 기존 보고→출처→원자료 구조와 913결정/32시도를 확인했다.
- 2026-10-20 — 전용 재내보내기·합성/실제 UI 검증을 완료했다. 같은 문서의 결정 링크
  갱신 결함을 교정하고 재검증했다. 원자료/이전 판본을 보존하고 새 판본·변경 이력을 연결했다.

## 결과·증거

[완료 보고](../../../exec-plans/evidence/ep188/report.md) ·
[새 뷰어](../../../../exports/battle_viewers/ex112-ui-v1/index.html).
승인 범위의 미충족 완료 기준은 없다. 이번 표시 작업 완료는 EX-112의 실험 목표 달성이나
EP-183의 Completed 전환을 의미하지 않는다. 기존 실험 재개·추가 추론·배틀0이다.
