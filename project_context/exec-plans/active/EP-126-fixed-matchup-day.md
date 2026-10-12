# EP-126 — 하루 내 고정 대진 실험

- 상태: Paused — 사용자 요청 중지; 학습·test 미시작
- 생성일: 2026-10-07
- 승인: 사용자 “예상시간이 하루 안이면 실행해주세요.” / D-122
- 원문: EX-077, C-060, RD11.1/C-018

## 목표·범위

EX-076의 모델·정보 경계·학습·평가를 유지하고 전체 예상시간24시간 이하일 때 단일 GPU 실행을 수행한다.
완료 pilot으로 전체 비용을 판단하며 이전 하한7시간을 완주 예상으로 오인하지 않는다.
CPU 입력 packing 등 결과를 보존하는 성능 개선은 동일 tensor/출력·회귀·실측 근거를 요구한다.
INDEX/CHARTER/RD·겹치는 EP-125/119/108/103을 확인하고 원 실험·실패·자료·Blocked는 보존한다.

## 완료 기준

- [x] 성능 변경 시 입력/수치 동등성·회귀·새 source/출처 동결
- [ ] GPU 검증·완료 pilot·전체24시간 예상 gate
- [ ] 승인된 학습/dev·잠긴 test640·효능/불확실성 판정
- [ ] 감사·전수 export/최대12 브라우저·봉인·자원 반환·보고

## 중단·복구

EX-077 원문을 따른다. 예측이24시간을 넘거나 기술/균형 gate가 실패하면 학습을 보류한다.
정상 단위만 계승하며 과거 미완료를 정상/패배로 바꾸지 않는다. 이번 명시적 pilot 재시도 외
추가 재수집/자동 주기0. 중단 처리와 효능/실험 완료를 구분한다.

## 진행

- 2026-10-07 — 조건부24시간 실행 등록. 전체 예상에 필요한 완료 P0 pilot은 아직 없다.

- CPU 입력 packing을 행별 tensor 생성/쓰기에서 묶음 변환으로 교체했다. 저장된 공개65관측의
  예측값이 정확히 같고 batch1/16/32/64의24 tensor 쌍이 dtype/값까지 일치했다.
  packing 중앙시간은4.87~5.43배 개선이며 전체 경기 속도 개선으로 해석하지 않는다.
  [동등성](../evidence/ep126/packing-equivalence.json) · [프로파일](../evidence/ep126/packing-profile.txt).
- CPU 회귀41개 통과. 첫 검사에서 과거12시간/합성 manifest fixture2개가 새24시간/실험명
  표시와 불일치하여 fixture를 갱신했다. 실제 실험 실패가 아니다.
  [검사](../evidence/ep126/tests.log) · [첫 검사 보존](../evidence/ep126/tests-first.log).

- 계승 helper 새18검사와 실제 부모의 전수 봉인 검증 통과. 정상32/P0만 계승했고
  원 실패16은 출처로 연결했다. 새 identity는 `27c6f836f7974539ed79aa6f46a0a278ecca587f5125e8d2872b7e50ebe332e0`.
  [준비](../evidence/ep126/prepare.json), [계승 원문](../../../.pokechamp-data/experiments/ex077-fixed-matchup-day/day-inheritance.json).
- 단일 실행기를 시작했다. GPU 검증→새 benchmark128→P0 pilot32의 시간/균형 gate를 확인한다.
  전체 예상24시간 이하면 학습/dev·잠긴 test·최종화를 연속 수행하고 초과하면 의존 수집을 보류한다.

- 사용자가 학습과정 검토 후 결정하기 위해 중지를 요청했다. SIGTERM 후 소유 controller/worker
  종료·GPU0 반환을 확인했다. 기존uniform32와 새P0 정상2/미완료16/미시작14를 보존했다.
  실제 학습/update/dev/test0이며 하루 내 비용 gate는 미확정이다. 정상34/전체50 감사·export·
  오프라인 이동 브라우저4표본·원자료/closure 봉인 완료. 자동 재개하지 않는다.
  [중지 보고](../evidence/ep126/stop-report.md).
