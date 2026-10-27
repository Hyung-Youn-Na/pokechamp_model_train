# EX-109 — OpenAI Decisions v6 상세32경기

- 상태: Stopped
- 생성일: 2026-10-20
- 승인: 사용자 v6 상세 입력 기반 OpenAI decision 모델32경기 실행 지시
- 관련: D-164 / EP-179 / C-067·C-046·C-047·C-079 / RD11.1·11.2
- 기준/실제 연구선: research/model-training; /workspace; 시작 commit a4659bf298c7935714f9fbd25246db2d831c5926

## 질문·조건

OpenAI gpt-6-luna가 v6 상세 관측·계산·합법 후보를 받아 기존 고정 대진32경기를 얼마나
완료하고 어떤 승무패·사용량·지연을 보이는지 탐색한다. 학습/튜닝·일반화 가설 검증은 아니다.
EX-089의 schedule/teams/게임·actor seed·제출순서·Abyssal·Gen9 OU·timer off를 채택한다.
고유32슬롯/16진영교환쌍이며 이전 결과 계승0, 양측 테라 허용, 경기/요청 동시성1이다.

입력은 현재 교정된 jev-choice-v6 Adapter(compact=False): 자기 벤치 상세, 상대 공개 이력,
최근3완료턴, 타입·효과·역할, 현재 대면 피해·스피드 계산과 v6 지시문을 그대로 유지한다.
planner off, names-v1 추가0, no-damage0, RuleQA 문구 교정0이다. 전송 형식만
state→input(JSON문자열), 질문 instructions→instructions, criteria 순서대로
후보ID→choices.value·후보객체→choices.description(JSON문자열)로 변환한다. 절단/요약0.
질문 이름 action, type choice, 모델 gpt-6-luna, POST https://api.openai.com/v1/decisions.
단일 후보는 API 미호출 자동선택. API choice 원값을 사용하며 argmax 재선택·재정규화0.
API seed/temperature/추론수준은 지원하지 않는 값을 보내지 않고 공급자 기본값이다.

## 범위·상한·실패

실 API는 사전 선봉/일반/강제교체 각1회 최대3요청 및 본32경기 단1회이며 총20,000요청 이내.
경기당600결정·300턴, 최초 API 요청부터12시간 누적, HTTP60초·재시도0·redirect0.
API가 보고하는 토큰/캐시와 지연·오류·미확정을 원장에 남긴다. 별도 monetary budget를
사용자가 지정한 것으로 간주하지 않으며32경기 범위 밖의 추가 요청은 실행하지 않는다.
GPU0, 디스크 용량 상한null, 호스트 프로세스와 소유 Showdown/Abyssal만 사용/정리한다.

실행 가능한 합법 choice는 보조 확률/confidence 이상에도 원형 전송하고 진단을 남긴다.
refusal/후보 밖/선택 누락은 해당 경기 output_failure이며 fallback/재질의0, 나머지 독립경기는 계속한다.
관측·계산·전송·수집·무결성 오류, API 인증/접근/요금/통신 실패는 신규 의존 수집 중단이다.
한도 도달은 incomplete로 기록하며 패배로 변환하지 않는다. 실패/무효/미실행 분모를 분리한다.

RD11.1/C-018: 사전 도구 결함은 원자료·최초시계/사용량 보존 후 독립 검증하여 고친다.
본수집 source변경·유료 재수집/재경기/보충은0이다. 감사 구현 결함은 원자료를 바꾸지 않고
별도 정정 분석한다. 중단/원자료/실패를 삭제하여 재개하지 않는다.

## 준비·검증·완료

1. 독립 어댑터/원장·후보 동치·오류/확률 진단·v6 기존 관련 회귀, 무유료 모의배틀 검사.
2. EX-089 저장 입력에서 대표3종 입력 재생성/원형 보존 후 최대3 API 연결 검사.
3. 소스·입력자료·대진·환경·지시문 동결, 본32슬롯 순차 수행. 경기별1회 공식cutoff·입력·후보·
   실제 HTTP/응답·합법 선택·전송·결과 감사와 종료 후 완전성/산술 검사.
4. 승무패·완료율·실패·16쌍 점수·요청/토큰/지연·전수 원자료·오프라인 뷰어·봉인·소유자원 반환.

정상 유효32/16쌍이 경기 목표이며 미달이면 미완료로 보고한다. 설명 정확성은 기본 미평가다.
과거 EX-089는 참고값으로만 제시하며 토크나이저·공급자·전송형식 차이로 인과/모델크기 효과를
주장하지 않는다. 개발에 사용한 고정 대진의 탐색 결과이며 외부 일반 성능으로 확대하지 않는다.

## 환경·출력·출처

actor /workspace/pokechamp/.venv/bin/python, 기존 official observation/계산기와 submodule pin.
실행기 scripts/openai-decisions-battle. root .env는 값/원문 보존 없이 읽고 소스 snapshot에 넣지 않는다.
run: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-109
viewer: /workspace/exports/battle_viewers/ex109/index.html; 상위 목록에도 연결한다.
protocol/source/manifest/원장/사전비용/본수집을 새 run 아래 분리 보존하고 덮어쓰기/자동 재개를 거부한다.
과거 EX-089 manifest/결과/저장 입력은 참조·사전검증만 하며 경기 결과를 신규 분모에 합치지 않는다.

## 결과

사전3요청·입력31,447토큰, 모의2경기/175결정과 기술 감사·오프라인 뷰어 검증을 통과했다.
동결된 조건으로 본32경기를 시작한다. 사전 비용은 경기 성적에 포함하지 않는다.

## 중단 결과

유효10/32·7승0무3패·실패1·미실행21·완료1/16쌍이다. 11번째 선봉 API 요청에서 약4초 뒤
HTTP 응답 없는 통신 오류가 발생하여 동결 retry0 정책으로 중단했다. 첫 실패의 세부 네트워크
exception class는 기록되지 않아 원인을 확정하지 않는다. 본324시도/323응답·사전3요청을
구분하고 미응답1의 사용량은 미확인이다. 경기별/최종 감사·오프라인뷰어·소유 반환을 완료했다.
[뷰어](../../../../exports/battle_viewers/ex109/index.html),
[보고서](../../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-109/evidence/report.md).
사용자의 후속 재실험 지시는 D-165/EX-110으로 분리하며 원결과/중단/봉인은 유지한다.
