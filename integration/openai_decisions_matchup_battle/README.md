# 후보별 요약 OpenAI 32경기

[EX112](../../project_context/research/input-and-memory/experiments/EX-112-openai-candidate-matchup-battle.md)의 독립 실행기다.
기반 jev-choice-v6에 candidate-matchup-v1만 추가하며 EX110의 일정·통신 재시도를 유지한다.

`scripts/openai-decisions-matchup-battle mock`은 API 없이 모의2경기·전수감사·뷰어를 만든다.
`prepare`는 모의/오프라인 검증 이후 source·규칙·protocol·일정을 동결한다.
`execute`는 새32경기를 순차 실행한다. `status`는 저장기록만 조회하며 `export`는 오프라인뷰어를 만든다.
기존출력 덮어쓰기·자동재개·보충경기는 지원하지 않는다. 새유료 preflight는 없다.
입력/감사/자료 정체성은 명시 프로필을 따르며 과거실험의 기본값은 유지한다.

## EX-112 UI v1 재내보내기

[EP-188](../../project_context/shared/viewers/plans/EP-188-ex112-viewer-ui-v1.md)의 별도 표시 생성기는
[battle-viewer-ui-v1](../../project_context/shared/viewers/CONTRACTS.md#battle-viewer-ui-v1)을 적용한다.
기본5탭 뒤 요약 제거 원본·후보별 상성 요약·선택/전송을 둔다. 턴·결정 선택은 영상을
일시정지하고 턴 시작으로 이동하며 영상·탭 조작은 정보 선택을 바꾸지 않는다.
[EP-189](../../project_context/shared/viewers/plans/EP-189-ex112-response-action-names.md)의 렌더러 v2는
응답 choice·확률 후보에 실제 이름을 함께 표시하고 원문·복사·다운로드 값은 보존한다.

```bash
pokechamp/.venv/bin/python -m integration.openai_decisions_matchup_battle.viewer_v1 \
  --previous exports/battle_viewers/ex112-ui-v1 \
  --output exports/battle_viewers/ex112-ui-v1-names
```

출력 경로가 이미 있으면 실패한다. 이 명령은 이전 뷰어·원자료 봉인을 확인하고 모든 결정과
공개 로그를 원자료에 대조한 뒤 별도 판본만 쓴다. 원자료·기존 판본·실험 결과를 수정하거나
모델/API/배틀을 호출하지 않는다. 기존 `export` 명령의 동작은 변경하지 않았다.
소스 사본·판본·이전 봉인과 변경된 renderer 파일은 새 provenance에 연결한다.

[새 뷰어](../../exports/battle_viewers/ex112-ui-v1-names/index.html) ·
[이름 표시 전 UI v1](../../exports/battle_viewers/ex112-ui-v1/index.html) ·
[수집 당시 뷰어](../../exports/battle_viewers/ex112/index.html) ·
[변경 이력](../../project_context/shared/viewers/CHANGELOG.md#ex112-response-names).
기존 EX-112 Stopped·EP-183 Blocked와 유효31/32·실패1·15/16쌍은 유지한다.
