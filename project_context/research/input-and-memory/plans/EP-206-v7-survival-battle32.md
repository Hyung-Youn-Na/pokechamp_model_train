# EP-206 — 개정 v7 GPT-6 Luna 32경기 시작·수집

- 상태: Blocked
- 생성일: 2026-10-21
- 책임자: Codex
- 승인: 현재 사용자 32경기 시작 지시 / D-182
- 조건 원문: [EX-117](../experiments/EX-117-v7-survival-battle32.md)
- 관련: D181/182, EP202/205, C006/018/046/047/067/081/082, RD8.1/11.1/11.2
- 연구선·실제 branch/checkout: research/model-training /workspace
- 시작 commit: feda62f733c1b470364868262c789ec857ef67f5; 기존 미커밋 변경 보존
- 환경: /workspace/pokechamp/.venv/bin/python; 브라우저 /tmp/ep037/tools/bin/python
- 새 출력: runs/model-training/EX-117 및 project_context/exec-plans/evidence/ep206
- 원자료: EX115 보고/manifest/동결 source/저장 입력, EX112 기준 설정; 읽기 전용

## 범위·확인

candidate_action 실행기의 명시적 EX117 경로·동결·모의/수집·후처리 연결과 뷰어의 실험 ID 표시.
INDEX/CHARTER/매뉴얼/STATUS/계획색인·공통/주제 설계·계약·뷰어 UI규격을 확인했다.
겹치는 EP202/204/205와 중단 EP140/179/183 및 병행 EP203을 확인했다.
입력/계산/후보/정책은 EP205 개정 지시문 외 그대로 유지한다. 기존 중단실험 재개0.

## 완료 기준

- [x] 새등록·1021입력 정보동치/길이·관련 검사·모의2경기/뷰어 검증
- [x] source/data/일정/protocol 동결 및 신규32슬롯 수집 시작 확인
- [ ] 유효32경기·16쌍·전수감사·비교/뷰어/봉인·소유자원반환

## 검증·중단

검증·분모·재시도·복구는 EX117 원문을 따른다. 실험 완료와 시작 확인을 구분한다.
기존 viewer의 합성/모의 지원 근거는 EP202이며 새 실험 ID·원문 전달을 새 모의로 확인한다.
진행 결과는 EX117/collection/progress.json 및 종료 receipt를 참조한다.

## 진행

- 2026-10-21 — 사용자 승인 등록. 실제 API/신규 본경기0, 준비 중.

- 저장1021입력/997요청 전수동치 통과, 요청당 UTF-8 +833바이트. 최종 CPU/UI/등록/정책 관련46검사 통과(기존 Pydantic 경고1).
- 첫 UI 검사 import 경로 누락은 기존 site-packages 경로 연결로 해결했으며 환경 설치/변경0.
- API0 모의2경기 진행 중. source/data 및 렌더러 공통 자산을 별도 동결하며 본수집은 아직0.

- 최종 소스 모의2경기·113결정/요청·실제API0의 경기별/최종감사와 원문 내보내기 통과.
- 모의 뷰어 이동후6종/3화면폭·원문/복사/다운로드·실제 리플레이1턴 pause/seek 통과.
  [모의 브라우저](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-117/evidence/mock-browser.json).
- 동일 source/data로 본수집 동결 후 시작한다. 렌더러 공통 자산은 별도 renderer-manifest/source에 보존했다.

- 2026-10-21 17:33 KST 동결 후 본32슬롯 수집 시작. 첫 실제 요청의 모델/개정 지시문 전달 확인.
  controller PID3879766, [시작 기록](../../../exec-plans/evidence/ep206/launch.json).
  수집→감사/비교/보고→뷰어/브라우저→봉인은 같은 controller가 이어간다. 재개/보충0.
  현재 시작 확인이며 최종 완료 기준은 아직 미충족이다.

## 수집 종결·미충족 기준

32슬롯을 모두 시도했으나 유효30/14쌍으로 목표32/16 미달이다. 슬롯4/11은 각3회 refusal로
응답복구 소진이며 다른 슬롯은 계속했다.12승0무18패, 실패2를 패배로 합산하지 않는다.
감사·비교·뷰어·봉인·소유자원반환은 완료했다. 보충/재수집0, 원계획의 유효분모 미달로 Blocked를 유지한다.
[종결 확인](../../../exec-plans/evidence/ep206/report.md) · [뷰어](../../../../exports/battle_viewers/ex117/index.html).
