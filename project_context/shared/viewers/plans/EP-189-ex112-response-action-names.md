# EP-189 — EX-112 응답 탭의 실제 행동 이름

- 상태: Completed
- 생성일: 2026-10-20
- 승인: 사용자 “응답원문 탭에 choice의 move와 switch에 실제 기술명과 포켓몬명 포함” 요청.
- 관련: D-172, D-101, C-047, EP-188, EX-112/EP-183.
- 연구선·checkout: research/model-training /workspace; 기존 미커밋 변경 보존.
- 환경: 기존 pokechamp/.venv/bin/python, 브라우저 /tmp/ep037/tools/bin/python.
- 새 출력: exports/battle_viewers/ex112-ui-v1-names; 기존 ex112-ui-v1·ex112 보존.
- 검증 근거: project_context/exec-plans/evidence/ep189.

## 범위

UI 규격 battle-viewer-ui-v1을 유지하며 렌더러를 openai-matchup-researcher-v2로 구분한다.
응답 탭에 raw answers의 choice 및 probabilities.value를 결정 당시 후보와 연결한 이름을
표시한다. 실제 기술명·테라 여부·교체/선봉 포켓몬명은 기존 actionLabel을 사용한다.
이름 요약과 펼친 원문을 함께 두며 JSON/응답/복사·다운로드 원값은 변경하지 않는다.
이름 부재는 미확인으로 표시한다. 실제 전송 선택 대신 원응답의 choice를 해석한다.
이전 판본·원자료·실험 Stopped/EP183 Blocked·분모·봉인은 보존한다.
새 모델/API/GPU/배틀·연구방법/평가·다른 실험 수정은 없다.

INDEX/CHARTER/매뉴얼·뷰어 계약·계획 색인과 EP-188/187/105, 관련 EP-183/179의
중단 보존 및 EP-184의 별도 작업 범위를 확인했다. 과거 실험을 재개하지 않는다.

## 완료 기준

- [x] 응답 choice·확률 후보에 실제 이름·원ID·확률을 함께 표시
- [x] move/switch/테라·이름 부재·자동/거부를 구분하며 원응답/복사/다운로드 보존
- [x] 새 판본 내보내기·기존/새 봉인·데이터 대응·관련 브라우저 검사
- [x] 변경일지·현재 링크·판본/출처·등록 색인·완료 보고

## 검증·중단

변경한 응답 영역을 실제/합성 사례로 검사한다. EP-188의 동일 replay/배치 근거는
변경 없는 범위에 한해 참조한다. 내보내기 identity·원문 대조는 C-047을 따른다.
비실험 표시 교정으로 재수집/시계는 해당 없음. 원자료/기존 봉인 불일치는 내보내기를 중단한다.

## 진행

- 2026-10-20 — 사용자 요청·범위 등록.
- 2026-10-20 — 이름 요약·원문 동시 표시, 관련4검사·실제6종류 오프라인 검증과
  새 판본/기존 보존 확인을 완료했다. 현재 열람 링크와 변경 이력을 연결했다.

## 결과·증거

[완료 보고](../../../exec-plans/evidence/ep189/report.md) ·
[현재 뷰어](../../../../exports/battle_viewers/ex112-ui-v1-names/index.html).
승인 범위의 미충족 기준은 없다. 실험 재개·추가 수집·원자료/성적/판정 변경은 없다.
