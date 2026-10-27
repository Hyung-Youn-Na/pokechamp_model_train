# 공통 실행·운영 측정 — 기록 목록

<!-- generated: scripts/context-catalog build -->

원문은 한 곳에 두며 다른 주제의 관련 기록은 색인과 원문 링크로 연결한다.

| ID | 제목 | 상태 |
|---|---|---|
| [D-006](decisions/D-006-adopt-pokechamp-environment-boundary.md) | PokéChamp 연구 환경 및 외부 경계 채택 | [`D-007`](decisions/D-007-adopt-pokechamp-dotenv-credential.md)로 대체됨 (Superseded) |
| [D-007](decisions/D-007-adopt-pokechamp-dotenv-credential.md) | PokéChamp `.env` credential 정책을 포함한 연구 환경 경계 채택 | 채택 (Accepted) |
| [D-008](decisions/D-008-fail-closed-cloud-json-actions.md) | Ollama Cloud JSON action의 thinking 비활성화와 fail-closed 검증 | [`D-009`](decisions/D-009-adapt-always-on-reasoning-output.md)로 대체됨 (Superseded) |
| [D-009](decisions/D-009-adapt-always-on-reasoning-output.md) | Always-on reasoning model의 compact action output 경계 채택 | 채택 (Accepted) |
| [D-011](decisions/D-011-default-untimed-showdown-battles.md) | PokéChamp 실험의 Showdown battle timer 기본 비활성화 | 채택 (Accepted) |
| [D-012](decisions/D-012-adopt-pokechamp-baseline-pilot.md) | PokéChamp 기준선 pilot 채택 | Accepted |
| [D-013](decisions/D-013-remove-client-output-cap.md) | 사용자 지시에 따른 LLM 출력 상한 최대화 | Accepted |
| [D-014](decisions/D-014-increase-cloud-request-timeout.md) | Cloud 요청 timeout 300초 | Accepted |
| [D-015](decisions/D-015-repeat-benchmark-profiles.md) | 반복 연구용 8판·32판 benchmark 설정 | Accepted |
| [D-016](decisions/D-016-model-concurrency.md) | 계정·모델 요청 제한과 병렬 운영 측정 | Accepted |
| [D-017](decisions/D-017-battle-identity-action-candidates.md) | 배틀 식별과 요청별 행동 후보 통합 | Accepted |
| [D-018](decisions/D-018-upstream-fallback.md) | 원본 행동 생성과 출력 fallback 조건 | Accepted |
| [D-045](decisions/D-045-cloud-concurrency-default8.md) | 전체 Cloud 기본 동시성 8 | Accepted |
| [D-054](decisions/D-054-zai-provider.md) | Z.ai 배틀 공급자 선택 | Accepted |
| [D-058](decisions/D-058-transport-retry.md) | 응답 대기600초·연결 오류 재시도 | Accepted |
| [D-060](decisions/D-060-provider-retry-viewer.md) | 공급자 오류 재시도 확대·정상 경기 viewer | Accepted |
| [D-070](decisions/D-070-jev-client.md) | JEV 환경 설정과 독립 호출 기반 | Accepted |
| [D-074](decisions/D-074-provider-judgment-policy.md) | 공급자 판단 오류의 전체 실험 중단 제외 | Accepted |
| [D-084](decisions/D-084-provider-retry-three.md) | provider 오류 재시도3회 고정 | Accepted |
| [D-087](decisions/D-087-jev-retry-backoff.md) | JEV 재시도 대기 확대 | Accepted |
| [D-163](decisions/D-163-openai-decisions-environment.md) | 독립 OpenAI Decisions API 환경 | Accepted |
| [EP-001](plans/EP-001-pokechamp-reproducible-environment.md) | PokéChamp 재현 가능 연구 환경 구성 | Completed |
| [EP-003](plans/EP-003-default-untimed-showdown-battles.md) | PokéChamp Showdown battle timer 기본 비활성화 | Completed |
| [EP-004](plans/EP-004-pokechamp-baseline-pilot.md) | PokéChamp 기준선 도구와 pilot | Completed |
| [EP-005](plans/EP-005-remove-client-output-cap.md) | Cloud 출력 상한 최대화 | Completed |
| [EP-006](plans/EP-006-repeat-benchmark-profiles.md) | 반복 benchmark 설정과 시간 재측정 | Completed |
| [EP-007](plans/EP-007-model-concurrency.md) | 모델 동시성 측정과 병렬 배틀 | Completed |
| [EP-008](plans/EP-008-parallel-thirty-two-repeat.md) | 병렬 32판 추가 실행 | Completed |
| [EP-009](plans/EP-009-battle-identity-action-candidates.md) | 배틀 환경과 행동 출력 계약 수정 | Completed |
| [EP-010](plans/EP-010-upstream-fallback.md) | 원본 fallback 병렬32판 | Completed |
| [EP-033](plans/EP-033-cloud-concurrency-default8.md) | 전체 Cloud 기본 동시성 8 | Completed |
| [EP-042](plans/EP-042-zai-provider.md) | Z.ai 배틀 공급자 연결 및 환경 구성 | Completed |
| [EP-043](plans/EP-043-zai-connectivity-probe.md) | Z.ai 단일 연결 확인 | Completed |
| [EP-047](plans/EP-047-transport-retry.md) | 응답 대기600초·연결 오류 재시도 | Completed |
| [EP-049](plans/EP-049-provider-retry-viewer.md) | 공급자 오류 재시도 확대·정상 경기 viewer | Completed |
| [EP-061](plans/EP-061-jev-client.md) | JEV 환경 설정과 독립 호출 기반 | Completed |
| [EP-065](plans/EP-065-provider-judgment-policy.md) | 공급자 판단 오류의 전체 중단 제외 | Completed |
| [EP-076](plans/EP-076-provider-retry-three.md) | provider 오류 재시도3회 고정 | Completed |
| [EP-079](plans/EP-079-jev-retry-backoff.md) | JEV 재시도 대기10·30·60초 | Completed |
| [EP-096](plans/EP-096-laya-training-environment.md) | LAYA 전용 worktree 학습 환경 | Completed |
| [EP-097](plans/EP-097-eve-rlcd-environment.md) | EVE-RLCD 전용 worktree 환경 | Completed |
| [EP-098](plans/EP-098-rlcd-lite-environment.md) | RLCD-Lite 전용 worktree 환경 | Completed |
| [EP-178](plans/EP-178-openai-decisions-environment.md) | OpenAI Decisions API 환경 | Completed |
| [EP-207](plans/EP-207-laya-0413-environment.md) | laya 0.4.13 독립 학습·추론 환경 | Completed |
| [EX-001](experiments/EX-001-pokechamp-baseline-pilot.md) | PokéChamp 기준선 pilot | Stopped |
| [EX-002](experiments/EX-002-pokechamp-baseline-pilot.md) | 중단 처리 검증 후 PokéChamp 기준선 pilot | Completed |
| [EX-003](experiments/EX-003-core-smoke-timing.md) | 128K·300초 핵심 8판 시간 재측정 | Completed |
| [EX-004](experiments/EX-004-model-concurrency-calibration.md) | 모델별 요청 동시성 측정 | Completed |
| [EX-005](experiments/EX-005-sequential-eight.md) | 동일 수정 source의 순차 8판 (배틀1/요청1) | NotRun |
| [EX-006](experiments/EX-006-parallel-eight.md) | 동일 수정 source의 병렬 8판 (배틀 min(C*,8)/모델 요청 C*) | Stopped |
| [EX-007](experiments/EX-007-parallel-thirty-two.md) | C* 배틀/모델 요청의 조건부 32판 | NotRun |
| [EX-008](experiments/EX-008-parallel-eight-revised.md) | 수정된 coordinator의 병렬 8판 | Completed |
| [EX-009](experiments/EX-009-sequential-eight-revised.md) | 수정coordinator 순차8판 | Stopped |
| [EX-010](experiments/EX-010-parallel-thirty-two-revised.md) | 수정coordinator 조건부32판 | NotRun |
| [EX-011](experiments/EX-011-parallel-eight-final.md) | 포트 정리를 보완한 병렬 8판 | Completed |
| [EX-012](experiments/EX-012-sequential-eight-final.md) | 포트 정리를 보완한 순차 8판 | Completed |
| [EX-013](experiments/EX-013-parallel-thirty-two-final.md) | 선택 조건의 32판 | Completed |
| [EX-014](experiments/EX-014-parallel-thirty-two-repeat.md) | 동일 조건의 병렬 32판 반복 | Completed |
| [EX-015](experiments/EX-015-action-candidate-validation.md) | 식별 수정과 요청 후보 조건 검증 | Completed |
| [EX-016](experiments/EX-016-upstream-fallback.md) | 원본 fallback 병렬32판 | Completed |
