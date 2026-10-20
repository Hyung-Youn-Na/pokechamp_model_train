Smogon Gen9 OU 전략 데이터 — 2026-10-19 수집본

시작 파일
- pokemon_strategies.json / .jsonl: 입력110링크별 전체 전략·세트·설명·원 필드.
- sets.json / .jsonl / .parquet: 공유 폼 중복을 제거한215세트. 분석/집계의 기본 파일.
- strategies.json / .jsonl / .parquet:115개 OU 분석의 개요·추가 설명·기여자·날짜.
- pokemon.json / .jsonl / .parquet:110개 입력 이름/URL과 실제 페이지·전략 ID 연결.
- sections.json / .jsonl / .parquet:개요·추가 설명·오래된 분석 안내·세트 설명560행.
- coverage.csv:포켓몬별 수집 상태·전략/세트 수·빈 설명 수.
- issues.json / .jsonl / .parquet:원문에 세트 설명이 없는32개 항목과 출처.
- manifest.json / statistics.json:범위·출처·수집 시점·집계·파일 정체성.
- validation.json / browser-validation.json / parquet-validation.json:전수 검증.
- pages/:각 URL의 원 HTML·삽입 JSON gzip 원본, route, HTTP/시도 기록.
- browser-assets/:브라우저 대조에 사용한 공식 UI 자산과 해시.
- tools/:수집·구조화·브라우저/Parquet 검증 재현 스크립트.

범위
입력은 gen9ou_strategy_links.json의110개 링크이며 별도 input-links.json으로 고정했다.
영어 SV/Gen9 OU 분석만 구조화한다. 다른 포맷은 원 HTML/JSON에 남아 있지만 OU 테이블에 섞지 않는다.
108개 실제 페이지에서 현행108분석/208세트, 오래된7분석/7세트를 확보했다.
현행은 사이트의 outdated 안내가 없는 분석이라는 뜻이며 독립적인 최신 메타 판정이 아니다.

무손실과 원문 빈 값
115개 분석과215세트의 원 필드는 source_strategy / source_set에 그대로 보존한다.
description_html, overview_html, comments_html, outdated_html은 원 HTML이며 대응 *_text는
읽기용 텍스트다. 원문의 링크·서식은 HTML에서 확인한다. 기술 선택지와 EV/IV의 여러 구성을 유지했다.
added/edited는 사이트가 제공한 원 문자열이며 retrieved_at_utc와 구분한다.
215세트 중183개에 설명이 있고32개는 원 description이 비어 있다. 현행만 보면177/208개에
설명이 있고31개가 비어 있다. 빈 설명은 empty_in_source로 표시하며 생성하거나 다른 세트의
설명으로 채우지 않는다. 해당 포켓몬의 개요·추가 설명이 있으면 별도 필드에 보존되어 있다.
수집 실패·OU 전략 없는 링크·원문 필드 유실은0이다. 이 보장은 수집 snapshot 범위에 한정된다.

폼과 중복
Ogerpon-Teal-Tera 링크는 ogerpon 페이지, Ogerpon-Wellspring-Tera 링크는
ogerpon-wellspring 페이지의 분석으로 연결된다. 실제 사이트 route로 확인한 관계이며 임의
전략 대체가 아니다.110개 입력 행은 유지하고 전략/세트 ID를 공유한다.
pokemon_strategies 파일에서는 요청 링크별로 같은 전략이 반복될 수 있으므로 집계에는
중복 제거된 sets/strategies 파일을 사용한다.

현행 세트만 읽는 예
import json
with open('sets.jsonl', encoding='utf-8') as f:
    current = [x for x in map(json.loads, f) if not x['strategy_outdated']]

Parquet
중첩 배열/객체는 *_json 문자열 컬럼으로 보존한다. JSON 원 필드와 Parquet 컬럼의 대응은
parquet-schema.json에 있으며 모든 원 필드의 왕복 대조를 통과했다.

출처: Smogon Strategy Dex. 각 분석의 작성·검수자는 credits에 보존했다.
기존 data/smogon-dex/raw 및 normalized의2026-08-11 보관본은 변경하지 않았다.
