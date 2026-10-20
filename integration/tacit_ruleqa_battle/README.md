# 학습 Tacit 실전32 예약

[EX-108](../../project_context/experiments/EX-108-tacit-ruleqa-battle32.md)의 전용 실행기다.
사용자의 취침 중32경기 예약 및 모든 미정 조건을 권장값으로 정하라는 지시에 따른다.

```bash
scripts/tacit-ruleqa-battle schedule
scripts/tacit-ruleqa-battle status
```

schedule은 EX107의 test/선택 어댑터 내보내기/3rank 재로딩 성공까지 CPU로 대기한다.
이후 준비·동일 본서버6gate·Abyssal32경기·감사·오프라인뷰어·자원반환을1회 수행한다.
reservation.json과 배타잠금은 중복예약을 막고 execution.json은 재경기를 막는다.
선행실패·기술결함·자원한도는 중단/원문보존하며 자동 조건변경·재시작하지 않는다.

권장값은 Thinking off·greedy192token·GPU1 UUID단독·외부LLM/API0·양측테라금지다.
기존 EX089/106의 팀·seed·16진영교환쌍을 사용한다. 기반모델32경기는 추가하지 않는다.
입력은 검증된 v6공개State/피해·속도와 RuleQA confusion 설명 교정이며 선택지 ID와 짧은 근거를 요청한다.
학습QA의 행동선택금지 문구를 사용하지 않는다. 실제6대6 행동선택으로의 전이 탐색이다.
잘못된 ID/복수/빈응답은 등록된 독립seed 합법대체로 분리 기록한다. 성적은 모델+대체정책의 결과다.

EX106의 battle/serving/storage/report/browser_check 경계를 별도 모듈로 분리 계승했다.
원본 EX106 코드·기록·봉인과 EX107 학습소스를 변경하지 않는다. v6와 공개정보/후보검증은 기존 구현을 재사용한다.
전체 입력이 학습 길이5120을 넘는 비율을 report.json의 over5120에 별도로 기록한다.

출력은 보존루트 runs/model-training/EX-108, 뷰어는 exports/battle_viewers/ex108/index.html이다.
예약은 실행 완료가 아니다. 결과의 실제 완료/실패/미실행 분모와 resource/cleanup/browser 증거로 종결한다.

CPU 검증:

```bash
/workspace/pokechamp/.venv/bin/python -m pytest integration/tacit_ruleqa_battle/tests -q
```

생성된 CPU gate fixture는 project_context/exec-plans/evidence/ep176에서 읽는다.

reservation-state.json은 실행 중 갱신되는 예약 상태이므로 run 봉인에서 제외한다. 원조건 reservation.json과 실제 실행/결과/자원/뷰어 증거는 봉인한다.

## 뷰어 구성 교정 (EP-177)

현재 ex108은 결정/턴 탐색·요청/응답/상태/턴로그/기술 기록 탭과 리플레이 병렬 화면이다.
초기 export의 전체 펼침 판본은 ex108-v1에 원래 봉인 그대로 보존했다.
봉인된 실험을 다시 감사·export하는 report.export 대신 아래 읽기 전용 생성기를 사용한다.
출력은 존재하지 않는 새 폴더여야 하며 검증 후 열람 경로에 배치한다.

```bash
python -m integration.tacit_ruleqa_battle.viewer --output /tmp/ex108-viewer --previous /workspace/exports/battle_viewers/ex108-v1
```

이 명령은 원 run·기존 뷰어를 쓰지 않으며 모델/API/GPU를 호출하지 않는다.
검증: project_context/exec-plans/evidence/ep177/check.json.
