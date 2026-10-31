# 후보 중심 v7·응답 복구

D-179 / EP-202 / EX-115의 명시적 `candidate-action-v1` 입력 프로필이다.
기존 v6·candidate-matchup-v1 기본값과 과거 봉인 자료는 변경하지 않는다.

개발용 `prompt.txt`는 [D-181](../../project_context/research/input-and-memory/decisions/D-181-v7-survival-switch-cost.md) /
[EP-205](../../project_context/research/input-and-memory/plans/EP-205-v7-survival-switch-cost.md)에서 개정했다.
상세 스피드 설명 뒤에 행동 전 생존 판단과 교체 기회비용 비교를 연결하며, 일반 교체·강제 교체·
피벗을 구분한다. 위험하면 무조건 교체하라는 지시가 아니다. 입력 필드·피해 계산·후보·실행 정책은
그대로이며 기존 `data_identity().prompt_sha256`으로 개정 전후를 식별한다.
EX-115의 동결 지시문·수집 결과 및 당시 길이 gate는 개발용 개정과 구분한다.
이번 개정 검증은 오프라인 전용이며 아래 EX-115 실행 명령의 새 실행을 승인하지 않는다.

- [입력 구조와 전후 예시](../../project_context/research/input-and-memory/input-structures/EX115_INPUT_STRUCTURE.md)
- [실험 protocol](../../project_context/research/input-and-memory/experiments/EX-115-candidate-action-v7.md)
- `transform.py`: 기술을 후보에 이동하고 피해 선택 분기/다른 가정을 분리한다. 모델에 전달된 v7만으로 EX112 입력을 복원한다.
- `adapter.py`: 기존 v6 + matchup 생성기를 합성한다. 관측·계산·후보 명령은 유지하며 이전 입력을 감사에도 보존한다.
- `session.py`: 실행 불가 응답 최대3회, 통신 무제한 재시도. 최초 합법 선택을 사용한다.
- `audit.py`, `metrics.py`: 응답/통신 시도·선택·재질의 경계 검증과 모든 확인 HTTP usage 집계.
- `offline.py`: EX112 저장913입력 보존 및 실제884논리 요청 텍스트의 UTF-8 길이 gate.
- `viewer.py/html/js`: UI v1과 재구성 전 입력/적용 결과/선택·전송 확장. 재질의 원문과 최종 선택 구분.

실행기는 `scripts/candidate-action-battle`이며 기존 `pokechamp/.venv/bin/python`을 쓴다.
출력은 `<BACKUP_ROOT>/pokechamp-research/runs/model-training/EX-115` 고정이다.
`mock`은 실제API0 모의2경기와 전수감사·뷰어, `prepare`는 gate 확인과 동결,
`execute`는 새 유료32슬롯과 감사, `status`는 저장파일 조회, `export`는 새 뷰어 출력이다.
기존 출력 덮어쓰기·본경기 자동재개·재수집·유료 사전호출은 없다.

통신은 동일 논리 결정·동일 본문·요청당60초, 2/5/10/20/30/60초 이후60초와 더 긴 Retry-After다.
`response_attempt`는 HTTP 성공 응답의 실행 가능성, `response_retry`는 재질의 연결을 기록한다.
`attempt`는 결정 안의 물리 HTTP 순서, `response_attempt`는 최대3 응답 순서,
`transport_attempt`는 현재 응답 시도 안의 통신 순서다. 원시 본문은 모든 HTTP 응답에 보존한다.
usage 집계는 최종 성공 전 거부 응답도 포함하며, 미응답/파싱불가/usage 미제공은 미확정으로 보고한다.

## EX-117 개정 지시문 32경기

D182/EP206/EX117에서 새 실행을 승인했다. `scripts/candidate-action-battle --experiment EX-117`의
`offline`은 저장1021입력/997요청 동치·길이 확인, `mock`은 모의2경기, `prepare`는 검증 후 동결이다.
`collect`는 새32슬롯 수집→비교·보고→뷰어/브라우저검증→봉인을 이어가며 재개/보충하지 않는다.
`status`는 저장 파일만 읽는다. 출력은 runs/model-training/EX-117, viewer는 exports/battle_viewers/ex117이다.
EX115의 기본 경로·기존 자료는 보존한다. 실험 조건의 원문은
[EX117](../../project_context/research/input-and-memory/experiments/EX-117-v7-survival-battle32.md)이다.
