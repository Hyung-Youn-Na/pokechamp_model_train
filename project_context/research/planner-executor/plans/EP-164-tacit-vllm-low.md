# EP-164 — Tacit vLLM 서버 새 평가

- 상태: Completed
- 생성일: 2026-10-16
- 책임자: Codex
- 승인: 사용자 기존 vLLM 서버 재테스트 지시 / D-158
- 조건 원문: [EX-105](../experiments/EX-105-tacit-vllm-low.md)
- branch/checkout: research/model-training /workspace a4659bf·기존 미커밋 변경 보존
- actor: pokechamp/.venv/bin/python; tokenizer/front: .pokechamp-data/tacit9b-runtime/.venv/bin/python
- 새 출력: EX-105 run·evidence/ep164·exports/battle_viewers/ex105
- 읽기전용 기준: EX-103/104·EP-162/163 원자료·보고·봉인

## 범위·완료 기준

INDEX/CHARTER·매뉴얼·STATUS/색인·RD11.1/11.2·C-018/046/047/070/073,
중첩 EP-134/140/151/154/155/157/163의 보존 경계를 확인했다.
외부 vLLM 어댑터·소유권 분리·검증·사전11/실제1경기·감사/비교/뷰어/봉인/소유 CPU 반환.

- [x] 등록·어댑터/공유 wiring·CPU 회귀·길이/서버 identity 검사
- [x] 소스/조건 동결·동일서버 사전8+고정3·정상1경기
- [x] 전수 감사·비교·뷰어/이동후 오프라인/복사/다운로드
- [x] 봉인·소유자원 반환/외부서버 유지·최종보고·상태/색인

## 검증·진행

- 2026-10-16 — 승인 범위 등록. 외부 서버 /v1/models 확인; 새 추론0.
- 독립 어댑터/검사·감사/비교·뷰어를 위임하고 공유 wiring/실행/통합은 주 에이전트가 담당한다.

## 중단

INDEX 공통 기준과 EX-105 복구/재수집0/누적 한도를 따른다. 부분 정리 완료는 정상1경기 달성이 아니다.

- CPU90입력·공유회귀256·어댑터6·외부수명8·뷰어14 검사를 통과했다. 공식18파일·외부587자료·EX103/104 run/viewer/증거 봉인을 확인했다. 실물 vLLM0.31.0+cu129의 GPU1/PID/설정을 고정하고 새 source/조건 준비본을 동결했다.
- 분리 controller1239434와 단계감지기1239435를 시작했다. 사전11회/실제1경기 진입이며 단계 종료 알림 뒤 승인된 감사·비교·뷰어·봉인을 완료한다. 수집중 source/조건 변경0·사용자 외부서버 종료0.

## 완료

정상1/1·67턴 패배. 감사119245검사·실패0, 사건/재시도/자원·75결정 뷰어검증·고정3/관련행동사례·속도비교를 완료했다. 기존 EX103/104 봉인을 보존하고 새 run/viewer/evidence 봉인을 검증했다. 소유CPU·Showdown·포트/잠금은 반환했고 사용자 외부 vLLM은 같은identity로 유지했다. 추가추론/재경기0. [최종 보고](../../../exec-plans/evidence/ep164/report.md) · [종결](../../../exec-plans/evidence/ep164/completion.json).
