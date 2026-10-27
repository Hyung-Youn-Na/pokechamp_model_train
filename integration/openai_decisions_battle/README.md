# OpenAI Decisions v6 상세32경기

EX-109 전용 실행기다. 조건·예산·실패·복구·해석은
[실험 원문](../../project_context/research/model-evaluation/experiments/EX-109-openai-decisions-v6-battle32.md)을 따른다.

- 모델: gpt-6-luna, 공식 POST /v1/decisions, 단일 choice 질문.
- 입력: 교정 v6 상세 state·원 지시문·원 후보 ID/순서. 피해/스피드 포함, planner off, 테라 허용.
- 상대/일정: EX-089의 Abyssal32경기·16진영교환쌍·게임/actor seed·순서 유지.
- 키: 루트 .env의 OPENAI_API_KEY. 값/Authorization은 증거에 저장하지 않는다.
- 환경: pokechamp/.venv의 기존 httpx/dotenv와 관측/계산 의존성을 재사용하며 GPU는 쓰지 않는다.

```bash
scripts/openai-decisions-battle status
```

상태 명령은 저장 기록만 읽는다. mock은 CPU 모의2경기를 쓰고, gates는 저장 대표 입력으로
실제 API 검증을 수행한다. prepare는 source/대진/조건을 동결하며 execute는 본32경기를 실행한다.
모든 단계는 신규 고정 EX-109 출력에만 쓰며 이미 실행된 수집을 덮어쓰거나 자동 재개하지 않는다.
최초 선봉 연결 요청은 preflight/result.json에 이미 기록되어 있으므로 gates가 이를 재사용한다.

실제 HTTP request/response, 원 v6 input, 내부 호환 response를 각각 기록한다.
합법 choice 원값이 정책이며 보조 확률 이상은 진단이다. API 오류/입력/수집 결함은 의존 중단,
실행 불가능한 모델 선택은 해당 경기 실패다. API 재시도·fallback·재경기는 없다.

뷰어는 실제 API JSON, 전체 v6 입력, 선택/명령, 공개 턴 로그, 리플레이를 제공한다.
입력·응답·로그는 폴더 이동 후 오프라인에서 열리며 애니메이션은 외부 자산에 의존할 수 있다.

검증:
```bash
PYTHONPATH=/workspace:/workspace/pokechamp pokechamp/.venv/bin/python -m pytest integration/openai_decisions_battle/test_core.py integration/pokechamp/tests/test_jev_v6.py integration/jev27b/tests/test_battle.py integration/jev27b/tests/test_input_adapter.py -q
```

## EX-110 통신 재시도 새32경기

사용자의 후속 지시에 따라 `scripts/openai-decisions-retry-battle`을 사용한다.
원EX109 원자료/중단은 보존하고 새32경기를 별도 실행한다.

```bash
scripts/openai-decisions-retry-battle status
```

연결/timeout·408/429/5xx는 같은 요청으로 성공까지 재시도한다. 대기는
2/5/10/20/30/60초 후60초 반복이며 더 긴 Retry-After를 존중한다. 개별HTTP60초는
재시도 신호이고 전체/경기시간·요청수·턴/결정 상한은 없다. 명시적 취소는 계속 지원한다.
인증/권한/요청/무결성 오류는 일시적통신으로 처리하지 않는다. 미응답의 실제 공급자 실행/
비용은 미확정이며 모든 물리시도와 확인usage를 원장에 보존한다.

새조건은 [EX-110](../../project_context/research/model-evaluation/experiments/EX-110-openai-decisions-retry32.md),
진행은 [EP-180](../../project_context/research/model-evaluation/plans/EP-180-openai-decisions-retry32.md)에 둔다.

EX110은 정상32경기/16쌍·16승16패(50%)로 완료했다. 실패/무효/미실행0이며 실제 재시도0이다.
[결과 뷰어](../../exports/battle_viewers/ex110/index.html)와
[최종 보고서](../../../mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-110/evidence/report.md)를 참조한다.
