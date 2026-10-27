# EP-172 — Strategist 소형 모델 첫 배틀

- 상태: Completed
- 생성일: 2026-10-19
- 책임자: Codex
- 승인: 현재 사용자 계획 구현·검증·실행 지시 / D-160
- 조건 원문: [EX-106](../experiments/EX-106-strategist-first-battle.md)
- branch/checkout: research/model-training, /workspace
- 시작 commit: a4659bf298c7935714f9fbd25246db2d831c5926; 기존 변경 보존

## 범위

integration/strategist_eval·scripts/strategist-eval 및 관련 연구 문서/증거를 추가한다.
공식 관측·request 경계·Showdown 수명 관리 재사용, JEV 입력/계산/확률 규격 제외.
환경·원자료·출력은 EX-106/연구 매뉴얼을 따른다. 기존 중단 실험은 재개하지 않는다.
INDEX/CHARTER/매뉴얼/RD/C와 겹치는 EP-013/057/062/064/075/077/080/103/134/140의
실패·관측·서빙 보존 경계를 확인했다. AgenticSTS subtree 수정 없음.

## 완료 기준

- [x] 새 EP/EX/Decision 및 domain 연결
- [x] 전용 CLI·입력/파서/대체/한도/감사/뷰어 구현과 CPU 필수 검사
- [x] 기반 다운로드/검증·같은 모델 서버6회 연결 검사·동결
- [x] 정상32경기/16쌍
- [x] 전수 감사·보고·오프라인 뷰어·봉인·자원 반환·문서 갱신

## 진행·검증

- 2026-10-19 — 번호 충돌 없음 확인, 승인 범위 등록. 구현/GPU/배틀 전.
- 증거: `project_context/exec-plans/evidence/ep172/` 및 EX-106 보존 출력.

## 중단

INDEX 공통 기준·RD11.1/C-018 및 EX-106을 따른다. 재경기/보충0, 공유 결함 영향 수집 중단.
미달은 실제 완료 범위·원인을 보고하며 중단 처리를 목표 달성으로 바꾸지 않는다.

- 전용27검사와 재사용 경계2검사 총29통과. 모델 오류 대체와 기술 오류 무전송, 선봉/강제/단일/테라·비공개·stale 경계를 확인했다.
- 저장1139관측의 새 입력317–487토큰(512초과0). 초기 길이 검사가 BatchEncoding 필드 수를 센 개발 결함을 발견해 실제 input_ids 길이로 교정했다. GPU/수집 전이며 초기/교정 로그 보존.
- 기반 고정revision10파일 원격 검증 완료. CLI metadata23개는 원격 원본 외 파일이다. 기존 runtime 버전5.17.0/0.21.0 확인. GPU0만 사용한다.

- 최종 소스/기반·adapter identity를 고정하고 GPU0 단일서버의6회 gate 및 같은 서버 본수집 실행기에 진입했다. 모델 판단 오류로 조건을 바꾸지 않는다.

## 최종 결과·증거

32/32경기·16/16쌍 정상 완료,1승0무31패.1550결정·1470본추론과 사전6추론의 전수 감사,
이동 후 오프라인 뷰어·최종1389파일 봉인·GPU0/소유 PID/잠금/8108포트 반환을 완료했다.
선봉/강제교체의 최초 합법 출력은0이며 모든 경기에서 등록된 대체 정책을 사용했다.
낮은 성적을 완료 기준 실패로 바꾸지 않으며 과거 JEV와 직접 비교하지 않는다.

[최종 보고](../../../exec-plans/evidence/ep172/report.md) · [지표](../../../exec-plans/evidence/ep172/report.json) ·
[감사](../../../exec-plans/evidence/ep172/audit.json) · [오프라인 검사](../../../exec-plans/evidence/ep172/browser-check.json) ·
[종결/봉인](../../../exec-plans/evidence/ep172/completion.json) · [32경기 뷰어](../../../../exports/battle_viewers/ex106/index.html).
