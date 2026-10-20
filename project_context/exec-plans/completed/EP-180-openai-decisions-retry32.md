# EP-180 — OpenAI 통신 재시도 새32경기

- 상태: Completed
- 완료일: 2026-10-20
- 생성일: 2026-10-20
- 승인: 사용자 연결 실패/시간초과로 제한하지 말고 실험 완수하도록 재설정·재실험 지시
- 관련: D-165 / EX-110 / C-080 / RD11.1·11.2·C-046·C-047
- 연구선/실제branch: research/model-training; /workspace; 시작commit a4659bf298c7935714f9fbd25246db2d831c5926
- interpreter: /workspace/pokechamp/.venv/bin/python; 기존 미커밋 변경/원실험 보존.
- 새 출력: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-110
- 참조: EX-109 source/사전3요청/모의2경기/94+신규10검사와 sealed 보고서, EX-089 대진.

## 범위·불변 조건

기존 실행기에 별도 unlimited retry/time 프로필과 EX110 진입/원장/뷰어를 추가한다.
입력·대진·모델·선택 정책은 유지하고 기존 EX109 실행/봉인·Blocked를 재개하지 않는다.
INDEX/CHARTER·RD/계약과 EP179 및 그 문서에 연결한 겹치는 active 범위를 확인했다.
새32경기와 요청 재시도는 현재 사용자 지시로 승인됐으며 새 모델/학습/입력 튜닝은 없다.

## 완료 기준

- [x] transient 무제한재시도/시간무상한·동일본문·취소·permanent 오류·사용량 검사
- [x] 새source/protocol/대진 동결·32경기/16쌍·경기별/최종감사
- [x] 정상/자동/실패 또는재시도 표시·전수 원문·오프라인뷰어·봉인/소유반환·문서 갱신

## 검증·중단

EX110의 명시적 통신 정책을 따른다. 통신 재시도와 실제 입력/수집 결함의 RD11.1 복구를 구분한다.
후자는 영향 범위 중지·원자료/최초시계/사용량 보존·독립검증을 요구한다. 무결성 검사를 완화하지 않는다.

## 진행

- EX109 부분종결을 보존하고 새사용자 지시를 등록했다. EX110 실제요청/본경기0.

- 기존/신규17검사와 보강한retry8검사 통과. 연속5실패→6번째성공, 같은본문/논리ID·물리시도번호,
  Retry-After45초·취소·400/401/403/404 비재시도·30일경과에도 시간무상한을 확인했다.
- 첫실패 후 성공한 요청의 재생성/선택/명령 감사 통과와 두 번째 시도의 본문변경 거부를 검증했다.
  실패시도5의 사용량을 미확정으로 분리하며 확인99토큰을 전체비용으로 확정하지 않는 검사도 통과했다.
- 새유료 사전호출0. 기존3종API성공·v6/공식cutoff·모의2경기는 입력/행동경로 검증으로만 재사용한다.

## 결과·증거

- 신규32경기/16쌍·16승0무16패(50%), 실패/무효/미실행0으로 완료했다.
- 실제952API/976명령·자동24, 재시도0. 모델응답/입력·실제전송을 경기별 감사하고 최종 산술을 통과했다.
- 976뷰어 결정의 원문 전수대조와 폴더 이동/오프라인5대표(합성재시도1 포함) 검증을 통과했다.
- 원자료/뷰어/전체run 봉인·소유프로세스/8109포트 반환을 완료했으며 새GPU사용·추가경기0이다.
- [보고서](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-110/evidence/report.md), [종결](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-110/evidence/completion.json),
  [32경기 뷰어](../../../exports/battle_viewers/ex110/index.html). 과거EX109 중단/원자료/봉인은 보존한다.
