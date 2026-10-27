# EP-176 — 학습 Tacit 실전32 예약

- 상태: Completed
- 완료일: 2026-10-20 (KST)
- 생성일: 2026-10-19
- 승인: 현재 사용자 취침 중32경기 예약 요청 / D-162
- 조건 원문: [EX-108](../experiments/EX-108-tacit-ruleqa-battle32.md)
- 연구선/checkout/시작commit: research/model-training /workspace a4659bf298c7935714f9fbd25246db2d831c5926

## 범위

integration/tacit_ruleqa_battle·scripts/tacit-ruleqa-battle 및 별도예약/완료감지·문서·증거.
기존 EX-106 실행·관측·합법전송·감사·뷰어 경로를 새실험 모듈에 분리 계승한다.
INDEX/CHARTER/매뉴얼/RD·C018/046/047/067/076, EP173/163/140과 완료EP172/EX106을 확인했다.
기존 중단·봉인·원자료·EX107 동결학습소스를 보존한다. AgenticSTS 수정없음.

## 완료 기준

- [x] 새 EP/ADR/EX 등록과 사용자 승인 연결
- [x] 별도실행기·CPU 입력/파서/전송/예약 검사
- [x] EX107 완료 후1회 실행 예약·감지 연결
- [x] 단일서버6gate·정상32경기
- [x] 감사·보고·C047뷰어·봉인·자원반환·문서종결

## 진행·중단

조건/예산/복구/산출물은 EX108 원문을 따른다. 예약 성공과 실험목표 완료를 구분한다.
- 2026-10-19 — 사용자32경기 예약 승인에 따라 등록. 신규 배틀/GPU호출 전.

- CPU17검사 통과. 선봉/일반/강제·양진영 대표18입력8496–13130토큰,32768초과0. 전용 메시지의 공개경계·ID/명령 대응·대체재현·stale거부·선행실패/누락재로딩 거부 확인.
- 사용자 모든권장값 승인 반영, 비Thinking/외부API0/GPU1 확정. reservation.json의 단일대기프로세스와 같은대화 완료감지기를 등록했다. EX107은 현재 test평가 중이며 새배틀0.
- 원본 EX106 격리계승, 현재 v6 계산/세트/role/text 자료 identity를 input-data-identity.json에 보존했다. 실제 수집 후 전수입력 재구성과 함께 대조한다.

- EX107 완료 감지 뒤 자동 준비·모델 적재·6회 반복 gate 통과. GPU1의 같은서버에서32경기 수집을 시작했다. 원 EX107은 완료/봉인했으며 추가 학습·QA test 재생성0이다.

## 완료

예약→선행검증→동일서버6gate→정상32경기·16쌍→감사/뷰어/봉인/반환을 완료했다.
전수 모델요청/원응답·914전송·일정/seed/종료·소스/입력자료/선택adapter identity를 확인했다.
원 run/viewer 봉인을 전수 검증했고 소유모델·예약·완료감지PID·GPU1잠금·8108포트 반환을 확인했다.
공통뷰어목록의 닫는body태그 미존재로 링크삽입이 누락된 것을 발견해 목록 링크1개만 교정했다.
원실험/뷰어/조건/성적 영향0이며 추가추론/배틀0이다. 이동후 기존914결정 브라우저검사는 보존하고
변경된 목록 연결만 별도 오프라인 검사했다. EX107은 앞서 완료/봉인했으며 반복하지 않았다.
[최종보고](../../../exec-plans/evidence/ep176/report.md) · [무결성](../../../exec-plans/evidence/ep176/final-integrity.json) ·
[목록 교정](../../../exec-plans/evidence/ep176/navigation-repair.json) · [목록 검사](../../../exec-plans/evidence/ep176/navigation-check.json) ·
[종결](../../../exec-plans/evidence/ep176/completion.json).
