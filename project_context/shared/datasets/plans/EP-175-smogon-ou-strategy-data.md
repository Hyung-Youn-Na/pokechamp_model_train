# EP-175 — Smogon OU 전략 전수 수집

- 상태: Completed
- 생성일: 2026-10-19
- 승인: 사용자의 EP-174 링크 기반 누락 없는 전략 데이터 구성 지시
- 연구선/checkout: research/model-training, /workspace
- 시작 commit: a4659bf298c7935714f9fbd25246db2d831c5926; 기존 변경 보존
- 환경: Python 표준 라이브러리·기존 Playwright/pyarrow, GPU 사용 없음

## 범위

입력은 data/smogon-dex/gen9ou_strategy_links.json의110항목이다.
각 링크의 영어 Gen9 OU 전략을 원문 HTML/서버 삽입 JSON으로 보존하고, 개요·세트별 구성·
설명·추가 설명·기여자·수정 정보·폼 관계를 원 필드까지 유지하여 JSON/JSONL/Parquet으로 구성한다.
모든 입력 링크에 성공/원문 빈 설명/전략 없음/오류 상태를 부여하며 조용히 건너뛰지 않는다.
원사이트가 비워 둔 설명을 생성하거나 다른 포맷/폼으로 추정 대체하지 않는다.
기존 raw/normalized·EP-174 목록은 보존하고 strategies/ 아래 새 수집본에 쓴다.

INDEX/CHARTER·매뉴얼·STATUS·plan색인을 확인했다. 겹치는 active 전략 수집 plan은 없다.
EP-173의 모델 학습·평가·GPU1–3 작업과 기존 중단 작업은 변경하지 않는다.
설명 해석·SFT 변환·훈련·실험 변경은 범위 밖이다.

## 완료 기준

- [x]110개 입력 URL 모두에 수집 기록·원문·관계/상태 연결
- [x] OU 원문 전략/세트/본문/구성 필드 전수 대조, HTML→텍스트 및 폼/빈 본문 검사
- [x] 실제 브라우저 표시와 전략/본문 연결 검증, 전체 JSON/JSONL/Parquet 대조
- [x] 원문 빈 항목과 수집 실패 구분·출처/통계/검증/사용 안내·완료 보고

## 중단·검증

HTTP 오류는 원인/시도를 남겨 한정 재시도하고 해결되지 않은 URL을 명시한다.
스키마/폼 연결 불명확성은 원문·브라우저 표시로 확인한다. 소스에 없는 내용을 보충하지 않는다.
비실험 자료 수집으로 실험 시계/모델 재수집은 해당 없음. 검증은 전체 입력/출력 대조와
독립 DOM 대조에 집중하며 INDEX 공통 기준을 따른다.

## 최종 결과

110/110링크 수집·108실제 페이지·115개 OU 분석·215세트 구성 완료.
현행208세트와 오래된7세트를 구분한다. 본문 있는183세트·원문 빈 설명32세트이며
빈 설명을 수집 실패로 혼동하거나 임의 보충하지 않는다. Gholdengo4세트 모두 본문 확보.
입력/원 필드·110페이지 공식 UI 본문·JSON/JSONL/Parquet 전수 대조와 파일 봉인을 완료했다.
기존 raw/normalized·링크 원본·GPU 작업은 보존했다.

[완료 보고](../../../exec-plans/evidence/ep175/report.md) · [통계](../../../exec-plans/evidence/ep175/statistics.json) ·
[종결](../../../exec-plans/evidence/ep175/completion.json) ·
[데이터 사용 안내](../../../../data/smogon-dex/strategies/gen9ou-20261019/README.txt).
