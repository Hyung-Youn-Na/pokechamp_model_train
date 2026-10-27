# EP-174 — Smogon OU 포켓몬·전략 링크 목록

- 상태: Completed
- 생성일: 2026-10-19
- 승인: 사용자의 OU 페이지 포켓몬–전략 링크 데이터 생성 지시
- 연구선/checkout: research/model-training, /workspace
- 시작 commit: a4659bf298c7935714f9fbd25246db2d831c5926; 기존 미커밋 변경 보존
- 환경: 기존 /tmp/ep037/tools/bin/python·Playwright, GPU 사용 없음

## 범위·완료 기준

https://www.smogon.com/dex/sv/formats/ou/ 의 실제 포켓몬 링크를 수집하여
사용자가 지정한 data/smogon-dex에 이름/전략 URL의 JSON·CSV와 출처 정보를 만든다.
기존 raw/normalized 보관본을 유지한다. 전략 본문 수집·학습·실험·방법 변경은 범위에 없다.
INDEX/CHARTER·매뉴얼·STATUS·plan색인을 확인했다. 링크 목록 생성과 겹치는 active plan은 없으며
EP-173 GPU1–3 학습과 기존 중단 작업은 변경하지 않는다.

- [x] 실제 페이지 목록에서 포켓몬 이름과 링크 추출, 목록 자체 링크 제외·중복 제거
- [x] JSON/CSV 일치·빈 값·도메인/경로·중복 및 원 DOM 전수 대조
- [x] 출처·수집시각·범위/한계 기록, 파일 링크 제공·색인/상태 갱신

## 검증·중단

목록 페이지 렌더링 실패·중복 이름 충돌·지원하지 않는 링크는 임의 추정하지 않는다.
기존 데이터 덮어쓰기 없이 새 파일로 저장한다. 비실험 자료 색인 작업이므로 실험 시계·
재수집·모델/배틀 gate는 해당 없음. INDEX 공통 기준을 따른다.

## 결과·증거

완료. 데이터는 data/smogon-dex/gen9ou_strategy_links.{json,csv}, 출처는 같은 이름의
manifest.json과 link-index-evidence/ 아래 페이지 snapshot/원링크에서 확인한다.

- 실제 목록111개 앵커 중 일반 Pokemon 탐색 링크1개를 제외하고110항목을 저장했다.
  일반 전략 URL38개·OU 전용 URL72개이며 별도 폼 항목을 유지했다.
- 최초 추출에서 /ou/ URL을 제외한 개발 오류를 발견했다. 최초 출력은 link-index-evidence/의
  initial.*로 보존하고 동일 수집 HTML/앵커에서 교정했다. 별도 HTMLParser로 원 DOM의110개
  이름/URL과 최종 JSON·CSV를 순서까지 전수 대조했다. 빈 이름·중복 이름/URL0.
- [검증](../../../exec-plans/evidence/ep174/validation.json) · [재현 스크립트](../../../exec-plans/evidence/ep174/collect.py) ·
  [JSON](../../../../data/smogon-dex/gen9ou_strategy_links.json) ·
  [CSV](../../../../data/smogon-dex/gen9ou_strategy_links.csv) ·
  [출처](../../../../data/smogon-dex/gen9ou_strategy_links.manifest.json).
