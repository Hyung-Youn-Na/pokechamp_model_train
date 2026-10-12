# EP-125 — 고정 A/B 공개 상태 GPU 실험

- 상태: Blocked — 교정 후 기술 검증 통과, 평가 예산 gate 초과로 학습/test 보류
- 생성일: 2026-10-07
- 책임자: Codex
- 승인: 사용자 GPU 학습·실제 고정 A/B 실험 실행 지시 / D-120
- 원문: EX-076, C-060, RD11.1/C-018

## 목표·범위

EP-124 구현으로 EX-076의 단일 GPU·12시간1회 실험을 실행한다. 준비·GPU 검증·pilot·학습·
잠긴 test640·원자료 감사·오프라인 뷰어·봉인·정리를 수행한다. 효과 없음과 gate 실패도 보존한다.
INDEX/CHARTER/RD/CONTRACTS 및 겹치는 EP-119/108/103의 보존 경계를 확인했다.
기존 dirty 작업·이전 자료/모델·Blocked plan은 보존하며 해당 실험은 재개하지 않는다.

## 완료 기준

- [x] 소스/환경/팀/스케줄 동결·GPU 기술 gate
- [ ] pilot/처리량 gate·승인된 범위 학습·dev 선택
- [ ] 잠긴 test640·독립 점수/대응 bootstrap 판정
- [ ] 원자료 감사·C-047 전수 export/최대12 브라우저 표본·봉인·자원 반환·보고

## 중단·복구

EX-076의 원12시간/단계 상한·재수집/대체0을 유지한다. 공유 경계/비유한/무결성 결함은
의존 단계를 중지한다. 중단 증거와 분모를 보존하고 조건 완화로 통과시키지 않는다.
완료 단위만 같은 소스·원 시계로 재개하며 소스 교정은 원본 보존·독립 검증·명시적 판단을 요구한다.
중단 처리 완료는 학습/test 목표 달성이나 plan Completed가 아니다.

## 진행

- 2026-10-07 — 실행 등록. RTX A6000 4장 모두 유휴 확인; 실행기는 하나만 소유한다.

- 준비 identity `7512b2cd85e519c37baf94d99c5b46c11e32189f50e3b1d5675b9e07bc1f64cf`를 동결했다.
  GPU0(UUID `GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`) 소유. 최초 시계는 실행 디렉터리 `clock.json`이다.
- GPU 수치/reload/최대256토큰·13후보 및 브라우저 gate 통과. batch 오차5.96e-8.
  실제 고정 A/B uniform pilot에 진입했다. [GPU 검증](../../../.pokechamp-data/experiments/ex076-fixed-matchup-mcts/verification.json).

- uniform32 정상 종료 후 첫 benchmark에서 status:fnt/effect:fnt 누락으로 중단했다. 학습/test0.
  정상32경기 전수 감사/export·브라우저2표본·봉인·GPU 반환 완료.
  관측 교정·CPU40검사·수정본 독립 GPU 검증 통과; 실패8probe는 재실행하지 않았다.
  [중단·교정 보고](../evidence/ep125/report.md).

- 사용자 “수정후 이어서 진행해주세요.”로 실패8probe 재측정·원한도 재개를 승인했다(D-121).
  원본을 보존하며 새 identity에 uniform32/P0/최초시계와 단계 사용량을 연결한다.

- 복구 검사22개 통과. 새 identity `bc5038be863cccabd8d3d6b79f1e7dc161c97fccd147489dbf6d2c53251788b6`로
  `ex076-fixed-matchup-mcts-fnt-v2`에서 재개했다. recovery.json이 원32경기/P0/실패8probe/최초시계/단계소비를 연결한다.
  전체 종료는 원14:45:32 UTC이며 갱신하지 않는다. [복구 검사](../evidence/ep125/tests-recovery.log).

- 수정본 GPU 검증·benchmark128 모두 통과, worker16/batch64 선택. 첫 P0 pilot16 진행시간만으로
  고정 예측식의 test 비용 하한6.97시간이3시간을 초과함을 증명하여 수집을 중단했다.
  P0미완료16·미실행16, 학습/test0. 정상32·미완료16 감사/export·브라우저2표본·봉인·GPU 반환 완료.
  [예산 중단 최종 보고](../evidence/ep125/budget-report.md). 실험 미완료와 중단 처리 완료를 구분한다.
