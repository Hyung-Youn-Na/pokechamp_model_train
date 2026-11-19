# EX-180 — laya fp1 epoch-2 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기(CPU)

- 상태: Running
- 생성일: 2026-11-19
- 책임자: Claude Code
- 관련 exec plan: [EP-234](../plans/EP-234-laya-fp1-foulplay-input.md)
- 관련 decision: [D-213](../decisions/D-213-laya-fp1-foulplay-input.md), [D-212](../decisions/D-212-laya-foulplay-blim-teams.md), [D-211](../decisions/D-211-laya-foulplay-opponent.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md)의 v10rt(같은 슬롯, 42/0/85, 0.331). 뒤에 돌릴 [EX-179](EX-179-laya-fp1-vs-foulplay-blim128.md)(EX-178 selected)와도 같은 슬롯으로 비교한다.
- 기준 연구선: `research/model-training`

## 질문 및 목적

EX-178 학습이 epoch 3을 도는 동안, 이미 저장된 epoch-2 체크포인트의 fp1 모델은 같은 Blim 일정에서 foul-play에게 얼마나 이기는가? v10rt와 같은 슬롯에서 얼마나 다른가? 사용자 지시(2026-11-19 대화, "넵 시작해주세요")로 EX-179 조건에 체크포인트만 바꿔 돌린다.

## 가설 또는 qualification 목표

- **판정 없음(보고 전용)**. 정상 종료가 120/128 미만이면 "판정 보류"를 적는다.
- epoch-2는 선택 절차를 거친 체크포인트가 아니다. 결과는 EX-178 selected의 성능을 대신하지 않는다.
- **보고 지표**: EX-179와 같다(승/무/패, 평균 점수와 조합 클러스터 bootstrap 95%, EX-174 대비 같은 슬롯 차이, 교환 쌍 분포, 팀 유형별 점수, 실패 기술률, 테라, 결정 지연, 승리·패배 턴).

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 자원 |
|---|---|---|---|
| Blim 일정 128슬롯 × fp1 epoch-2 | EX-174·EX-179와 같다: collection, 시드, 진영 교환, foul-play `8f541f8`·3,000ms·병렬 4·스레드 1·2026-10 통계, 300턴/600결정, 경기당 1,200초, 서빙 `serve_fp1` | laya 쪽 체크포인트 EX-178 `checkpoints/epoch-2`(2026-11-18T14:01Z 저장)의 고정 복사본 | CPU만(GPU 0~3은 EX-178), 포트 8100~8103, 서빙 스레드 8 |

## 실행

- 체크포인트: `runs/model-training/EX-180/source-epoch2/checkpoints/selected`(원본과 파일 해시 동일, `source-epoch2/checkpoint.sha256`). `source-epoch2/status.json`의 `completed`는 복사본이 고정됐다는 뜻이고, EX-178 완료를 뜻하지 않는다.
- 실행기: `integration/laya_fp1/battle_fp1.py`의 `STUDIES['EX-180']`, 연결 실행 `scripts/mem-guard 25 … -- scripts/laya-fp1-ep234 battle EX-180`.
- 순서: mock(첫 쌍 2경기, 분모 밖) → prepare → execute → export. 상한 10시간, 자동 재실행 없음.
- 같은 시간에 공식 래더(v11rtc CPU 서빙, 스레드 8)가 돈다. 서로 다른 서버라 경기는 섞이지 않는다.

## 진행

- 2026-11-19 00:34Z~00:41Z — mock 1차(분모 밖 2경기): 경기는 둘 다 정상 종료(71턴 laya 승, 19턴 laya 패)했지만 감사가 모든 모델 결정에서 `input bytes/hash mismatch`로 실패해 invalid가 됐다. 원인은 실행기 결함이다. `Fp1Session`이 기록 입력 `body`와 HTTP `input`에 `fp1` 항목을 붙이는데(서빙은 해시 전에 뺀다), 공용 감사는 이 항목을 모른다. 서빙은 fp1 입력을 정상으로 받았다. foul-play 결정 p50 3.89초·최대 7.79초, 메모리 최대 8.1 GB.
- 수정: `battle_fp1._install_audit`가 fp1 경기에서 fp1 항목을 먼저 검사한 뒤(모든 입력에 있음, HTTP 항목과 같음, HTTP 바이트가 기록 body와 같음, game·side 일치) fp1을 뺀 사건으로 공용 감사를 그대로 돌린다. 1차 두 경기를 메모리에서 다시 감사해 둘 다 통과했다(입력 77·25, fp1 77·25). 1차 기록은 `mock-attempt1-audit-defect/`에 그대로 두고 mock을 다시 돌린다(D-029 공통 복구: 도구 결함, 분모 밖 mock 재실행).
- 2026-11-19 00:43Z~00:53Z — mock 2차 통과: 2/2 completed·감사 통과(107턴 laya 승, 19턴 laya 패). laya 결정 지연(CPU, fp1 추적기 포함) p50 1.98초·p95 3.15초·최대 4.29초(140회), foul-play p50 3.84초·최대 8.45초. 00:53Z prepare(128슬롯, 체크포인트 sha256 `d2dea189…`), 00:53:58Z execute 시작.

## 결과

아직 없다.

## 결론 및 후속 작업

아직 없다.
