# EX-158 — laya v7t 대 v9t(상대 위협 표시) 같은 실행 256경기(GPU3, EX-120 일정)

- 상태: Completed
- 생성일: 2026-11-02
- 책임자: Claude Code
- 관련 exec plan: [EP-225](../plans/EP-225-laya-opponent-threat-v9.md)
- 관련 decision: [D-202](../decisions/D-202-laya-opponent-threat-v9.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: `laya-v7t`(EX-149) 대 `laya-v9t`(EX-157), 같은 실행
- 기준 연구선: `research/model-training`

## 질문 및 목적

상대 노력치 보정과 최악 피해 표시(v9)가 Abyssal 상대 성적을 떨어뜨리지 않는가?

## 가설 또는 qualification 목표

- **판정**(동결, EX-150·EX-153과 같은 비퇴보 기준): 같은 슬롯 차이(v9t − v7t), 조합 클러스터 bootstrap 95%. 하한 > −0.05이면 "비퇴보", 아니면 "퇴보를 배제하지 못함". 상한·하한 모두 0보다 크면 "개선". 정상 종료 120/128 미만이면 판정 보류.
- **보고 지표**: 승무패, 실패 기술 수·비율, 3회 이상 연속 실패 루프, 테라 사용, 결정 지연
- 한계: Abyssal 한 상대다. 사용자가 본 장면(Specs Kyurem·썰렁개그 연계)은 이 일정에 드물다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 자원 |
|---|---|---|---|
| EX-120 일정 128슬롯 × 2모델 | 팀, 시드 20261053, Abyssal | 체크포인트·렌더(EX-149 v7 → EX-157 v9) | GPU3·8106 |

- 뷰어: battle-viewer-ui-v1, 생성기 `laya_imitation.viewer`(EX-153과 같은 판본, [변경일지](../../../shared/viewers/CHANGELOG.md#ex158-laya-v1)), 압축 입력 탭은 v7 경기는 `v7`, v9 경기는 `laya_threat` 실시간 v9 렌더러로 복원한다. 출력 `/workspace/exports/battle_viewers/ex158/`.

## 실행

- 실행기: `python -m integration.laya_threat.cli {mock,prepare,execute,export}`(laya venv), 연결 실행 `scripts/laya-imitation-ep225 gpu3`(EX-157 평가 뒤)
- mock은 EX-157 데이터 생성 직후(학습 전) CPU에서 먼저 돌린다. 배틀 판정 분모 밖이다.
- prepare 직전 `.pokechamp-data/battle-window/EX-158` 표시 파일 생성, export 뒤 삭제. prepare가 laya_threat 파일 해시를 동결하고 execute가 확인한다.
- 상한 10시간. 자동 재실행 없음.

## 결과

- 2026-11-02 20:22Z~22:41Z(GPU3·8106), 256/256 정상 종료·감사 통과. 보고 `runs/model-training/EX-158/report.md`, 뷰어 확인 통과(1440·390 폭, 256경기, 페이지 오류 0, `exec-plans/evidence/ep225/ex158-viewer-check.json`).
- **판정**: 같은 슬롯 차이(v9t − v7t) −0.0156, 95% [−0.1016, +0.0703] → **퇴보를 배제하지 못함**. v9t 우세 13, v7t 우세 15, 같음 100.

| 모델 | 승/무/패 | 평균 점수 | 95% | 기술 실패·무효 | 테라 사용 경기 | 지연 p50 |
|---|---|---:|---|---:|---:|---:|
| laya-v7t | 112/0/16 | 0.875 | [0.805, 0.938] | 171/3310 (5.17%) | 28/128 | 0.143초 |
| laya-v9t | 110/0/18 | 0.859 | [0.805, 0.906] | 157/3562 (4.41%) | 12/128 | 0.152초 |

- 3회 이상 연속 실패 루프 경기 v7t 5, v9t 4(둘 다 Whirlwind 30회 이상 루프가 남아 있다). 팀 유형별로는 수비형만 v9t가 높다(0.812 → 0.875).

## 결론 및 후속 작업

- 두 모델 차이는 2경기(1.6%p)이고 구간이 넓다. 비퇴보 하한 −0.05를 넘지 못해 "퇴보를 배제하지 못함"이다. Abyssal 상대로 v9가 낫다는 근거는 없다.
- 이 일정에는 사용자가 본 장면이 드물다. 그 장면의 효과는 사람 대전에서 v9t를 직접 두어 확인한다.
- 테라 사용이 28 → 12경기로 줄었다(EX-157 테라 지식 A3 하락과 같은 방향).
