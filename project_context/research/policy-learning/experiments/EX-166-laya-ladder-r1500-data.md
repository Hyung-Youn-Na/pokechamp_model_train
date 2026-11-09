# EX-166 — 최근 래더(레이팅 1500 이상) 리플레이의 v10 학습 자료(CPU)

- 상태: Completed
- 생성일: 2026-11-04
- 책임자: Claude Code
- 관련 exec plan: [EP-230](../plans/EP-230-laya-ladder-r1500-v10.md)
- 관련 decision: [D-208](../decisions/D-208-laya-ladder-r1500-v10.md), [D-207](../../../shared/datasets/decisions/D-207-lift-reviewed108-species-limit.md)
- 비교 대상: 탐색 표본(`ladder-sample/gen9ou-r1500-n1000-s20261104`)의 수율
- 기준 연구선: `research/model-training`

## 질문 및 목적

최근 래더 경기를 EX-071과 같은 규칙과 v10 입력으로 바꾸면 결정 행이 얼마나 나오고, 어디서 빠지는가? 결과 자료는 [EX-167](EX-167-laya-v10-ladder-training.md)이 쓴다.

## 가설 또는 qualification 목표

- **qualification**:
  - 특성 귀속 수정은 새 경로에서만 켜진다. 같은 경기를 수정 없이 복원하면 탐색 표본의 `recover-aug-v2.jsonl`과 같다.
  - 보강 세트는 시드가 같으면 같고, 모두 로컬 검증기를 통과한다.
  - v10 길이 초과 제외가 0.5% 이하다(EX-161과 같은 한도).
  - validation 512에서 오프라인 렌더와 서빙 렌더가 같다(`v10 parity`와 같은 검사).
- **보고 지표**:
  - 단계별 경기·시점·행 수와 탈락 이유(위반, 검토, 10턴 이하, 평가 팀, 세트 없음, 원래 증거 불명, 파서 실패, 선택지 불일치)
  - 보강 세트 수(바탕 세트·통계·실패)
  - 특성 귀속 수정으로 바뀐 시점 수
  - 월별 train 행 수, train에 들어간 가장 오래된 경기 날짜

## 조건 및 변수

| 단계 | 입력 | 규칙 |
|---|---|---|
| 원본 | 최신 25,000경기(D-208 결정 1) | 업로드 최신순 |
| 분류·필터 | EP-100 분류기, 마지막 턴, 평가 팀 구성 | D-208 결정 2 |
| 세트 | Metamon 25,192팀 + 보강 v2 | D-208 결정 3 |
| 행 | EX-071 `prepare` 규칙 | D-208 결정 4 |
| 저장소·렌더 | item-state, v5 사실값, early-history, 엔진 판정, v10 | 기존 코드에 경로만 바꿔 끼움 |
| 분할·예산 | 최신 150경기 test, 다음 60경기 validation, 나머지 train(최신순, EX-167 사전 측정이 정한 행 수) | D-208 결정 5~7 |

## 실행

- 실행기: `python -m integration.laya_ladder.cli`(하위 명령은 구현 때 확정). 산출물은 `runs/model-training/EX-166`과 EP-230의 자료 경로다.
- CPU만 쓴다.
- 중단: 제외 비율 > 0.005, parity 불일치, 보존 파일 해시 변경. 자동 재실행 없음.

## 결과

- 2026-11-04 05:59Z~12:32Z(CPU). 산출물 `runs/model-training/EX-166/`(classify, select, rows, diagnostics), 자료 `laya-ladder-source/v1`, `laya-compact-imitation/v10-ladder`·`v10-ladder-merged`. 진행 중 결함 두 건(5마리 팀 3경기, early-history 저장소 메모리 부족)과 복구는 [EP-230](../plans/EP-230-laya-ladder-r1500-v10.md) 진행 절에 있다.
- **qualification**: 모두 통과.
  - 특성 귀속 수정은 래더 경로에서만 켜진다. 탐색 표본 878경기에서 불가능한 특성 13 → 1, 바뀐 자리 34. 기술·도구는 바뀌지 않았다.
  - item-state·early-history 동일성 1,581,819/1,581,819.
  - v10 길이 초과 제외 0(train·validation·test 모두).
  - parity 512행 불일치 0, `generator_matches` 참(`diagnostics/parity.json`).
- 단계별 경기 수:

| 단계 | 경기 |
|---|---:|
| 받은 로그(최신 30,000, 25,000에서 늘림) | 30,000 |
| 분류: candidate / incompatible / needs_review | 26,901 / 1,263 / 1,836 |
| 제외: 10턴 이하 / 평가 팀 구성 / 6마리 아님 | 1,162 / 440 / 3 |
| 선별(test 150 · validation 60 · train 25,086) | 25,296 |

- 행(train 기준): 1,723,650행 중 eligible 1,580,283, 격리 33,464.
  - 많이 빠진 이유: 지원하지 않는 선택지 제한(Encore 7,436, Taunt 7,224, 구애 도구 교체 5,874, Heal Block 4,360), 자동 연속 기술(Meteor Beam 1,259, Outrage 1,209), 원래 증거 불명 930.
  - 파서 실패 7, 세트 없음 54.
  - validation 4,477, test 12,814 eligible에서 각 512·1,024행을 썼다.
- 세트 보강: Metamon 25,192팀(고유 세트 127,319, 평가 팀 1,411·불법 310 제외). train에서 맞는 세트가 없는 자리 13,720 중 보강 13,667(가장 가까운 corpus 세트 13,594, usage 보완 73), 합법 완성 실패 53.
- 월별 train eligible 행: 2026-08 895,537 · 09 315,725 · 10 364,188 · 11 4,833. 가장 오래된 업로드 2026-08-15T17:18Z.
- 합친 자료(EX-167 예산): 래더 최신 17,510경기 1,111,776행(가장 오래된 업로드 2026-08-23T22:47Z) + v10-all 130,411행. 래더 행 길이는 v10-all의 0.983배.

## 결론 및 후속 작업

- 래더 train eligible 행은 1,580,283으로 v10-all train(130,411)의 약 12배다. 학습에는 예산에 맞춰 최신 1,111,776행을 썼다. 길이 초과와 렌더 불일치는 없다.
- 탈락은 주로 아직 지원하지 않는 선택지 제한(Encore·Taunt·구애 도구 교체·Heal Block)이다. 이 장면들은 학습 자료에 빠져 있다.
- 미공개 세트는 Metamon 팀과 보강 세트로 채운 추정값이다. 자료는 [EX-167](EX-167-laya-v10-ladder-training.md)이 썼다.
