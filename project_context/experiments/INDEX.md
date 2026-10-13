# 실험 색인 (Experiment Index)

이 directory는 qualification, benchmark, ablation, experiment run의 control record를 보관한다.
각 record에는 존재 이유, condition, provenance, result, evidence를 기록한다. Raw trajectory나
mutable store 자체를 복제하지 않는다.

이 파일은 navigation과 운영 규칙을 제공한다. Question, procedure, status, result에 대한 source
of truth는 개별 experiment record다.

새 기록의 연구선·branch/commit·실행 환경·입출력은 [EX 템플릿](TEMPLATE.md)에 남긴다.
현재 연구선의 작업 순서는 [연구 매뉴얼](../RESEARCH_MANUAL.md)을 따른다.

## Experiment 목록

아래는 실행 지시가 아닌 기록 탐색용 목록이다. 상태값은 각 기록의 기존 값을 유지한다.
`Completed`가 모든 경기의 유효 완료나 성능 비교 성공을 뜻하지 않는 기록도 있다.
조건·분모·실패/무효·정정·검토·증거는 각 기록에서 확인하며, 새 작업은
[실행 계획 색인](../exec-plans/INDEX.md)의 승인된 범위에서 찾는다.

| ID | Record | Status | 읽을 때 주의할 범위 |
|---|---|---|---|
| EX-082 | [JEV-27B 개선 입력 동일32](EX-082-jev27b-ex058-reproduction.md) | Blocked | GPU 자원 한도 중단·부분 종결 · [메모리 후속 교훈](../exec-plans/evidence/ep134-lessons/report.md) |
| EX-081 | [공동 q 모델 배틀20](EX-081-joint-q-battle.md) | Completed | GPU0 재현·유효20경기·정정/뷰어/봉인 완료,0승20패 |
| EX-080 | [Qwen0.8B 행렬 탐색 자기대국](EX-080-qwen-matrix-selfplay.md) | Completed | 시도3 40라운드 둔화·36 선택·시험/감사/뷰어/봉인 완료; P0 직접 0.805·Abyssal 개선 미입증 |
| EX-079 | [종료조건 추가 학습](EX-079-fixed-matchup-stopping.md) | Completed | 32라운드 상한·최고24 시험 완료; 초기상대 우세·Abyssal 개선 미입증 |
| EX-078 | [첫1라운드 학습](EX-078-fixed-matchup-first-round.md) | Completed | D125 복구·첫라운드 체크포인트 진단 완료; 효능 미평가 |
| EX-077 | [하루 내 고정 대진](EX-077-fixed-matchup-day.md) | Incomplete | 사용자 중지·학습/test0·보고/정리 완료 |
| EX-076 | [고정 대진 공개 상태 MCTS](EX-076-fixed-matchup-mcts.md) | Incomplete | 교정/측정 통과, 예산 gate 초과·학습/test0·정리 완료 |
| EX-075 | [82라운드 계승 추가 학습](EX-075-abyssal-rl-next.md) | Completed | 검증·뷰어·정리 완료·개선 미입증·목표 미달 |
| EX-074 | [57라운드 계승 추가 학습](EX-074-abyssal-rl-continue.md) | Completed | 출발 대비 통계적 개선·목표 미달·검증/뷰어/봉인/정리 완료 |
| EX-073 | [Abyssal 우선4GPU 학습](EX-073-abyssal-rl.md) | Incomplete | test 개선 기준 충족·목표 미달·최종 뷰어 timeout |
| EX-072 | [자기대국·RLCD 확률 보정](EX-072-selfplay-rlcd.md) | Completed | 결합 학습·잠긴 sampling 평가·정정 최종화 완료; 개선 미입증 |
| EX-071 | [Qwen 리플레이 모방 학습](EX-071-qwen-replay-imitation.md) | Completed | 첫 학습·잠긴 test·40경기/뷰어 완료; 배틀 개선 불확실 |
| EX-070 | [Kev 후속 질문](EX-070-kev-continuation-question.md) | Completed | 후속 질문·동일1경기 진단/비교·감사/뷰어·정리 완료 |
| EX-069 | [Kev 기존 test20](EX-069-kev-test-battles.md) | Completed | 고정 test20 본 평가·감사/뷰어·정리 완료 |
| EX-068 | [Kev-4B 연결](EX-068-kev-battle.md) | Completed | 원 실패 보존·승인된 fused 수락 검사/1경기 감사·뷰어·정리 완료 |
| EX-067 | [Abyssal Tera 보완 q](EX-067-abyssal-tera-joint-q.md) | Completed | 80경기·공개 Tera 상태 교정본·전수 감사/뷰어·봉인/복사 완료 |
| EX-066 | [Base 공동 q 학습](EX-066-joint-q-training.md) | Blocked | 새 프로세스 재로딩 gate 실패·자료 보존·GPU 점유0 |
| EX-065 | [공동 q 데이터](EX-065-joint-q-data.md) | Completed | 80경기 공동 q 수집·감사/봉인·학습 자료 복사 완료 |
| EX-064 | [Qwen 후보 상태 3조건](EX-064-qwen-candidate-state.md) | Completed | 저장3조건·별도 진단/보존 완료·판단 개선 미입증 |
| EX-063 | [Qwen 학습 원대진](EX-063-qwen-training-matchup.md) | Completed | 원대진 정상1/1·12턴 패배·정정 전수 감사/뷰어/정리 완료 |
| EX-062 | [Qwen 로컬 배틀 연결](EX-062-qwen-local-battle.md) | Blocked | GPU167후보 대조 완료·배틀 입력 전 중단·정상0/2·교정/정리 완료 |
| EX-061 | [Qwen3.5-4B 행동가치 학습](EX-061-qwen-action-value.md) | Completed | 기술/개발 MSE 기준 충족·전체 MAE 증가·독립 배틀 미평가 |
| EX-060 | [한 경기 분기 데이터](EX-060-single-battle-branch-rollouts.md) | Completed | 22상태·167행동·5,344분기 정상 종료·학습 통계·뷰어·봉인 |
| EX-059 | [자기 벤치 축약 동일32](EX-059-jev-compact32.md) | Completed | 유효32/32경기·완료16/16쌍, JEV 8승0무24패·감사/뷰어/정리 |
| EX-058 | [개선 JEV 동일32](EX-058-jev-improved32.md) | Completed | 유효32/32경기·완료16/16쌍, JEV 11승0무21패·감사/뷰어/정리 |
| EX-057 | [JEV v3 동일32·v2 전후 비교](EX-057-jev-pinned32.md) | Completed | 유효32/32경기·완료16/16쌍, JEV 7승0무25패·전후 비교/감사/뷰어/정리 |
| EX-056 | [JEV v3 동일32·v2 전후 비교](EX-056-jev-direct32.md) | Incomplete | 유효21/32경기·완료7/16쌍, JEV 1승0무20패·전후 비교/감사/뷰어/정리 |
| EX-055 | [실패 입력 현재 응답 확인](EX-055-jev-failed-input-probe.md) | Completed | 동일 입력 첫 시도 HTTP200·실측10,515토큰 |
| EX-054 | [JEV v3 동일32·v2 전후 비교](EX-054-jev-v3-retry32.md) | Incomplete | 유효0/32경기·완료0/16쌍, JEV 0승0무0패·전후 비교/감사/뷰어/정리 |
| EX-053 | [JEV v3 동일32·v2 전후 비교](EX-053-jev-v3-abyssal32.md) | Incomplete | HTTP503 중단·유효0/32·완료0/16쌍·성적 비교 미완료/보고/뷰어/정리 |
| EX-052 | [JEV 대 Abyssal32](EX-052-jev-abyssal32.md) | Completed | 유효32/32경기·완료16/16쌍, JEV 7승0무25패·감사/뷰어/정리 |
| EX-051 | [JEV 교정 입력2경기](EX-051-jev-v2-battle.md) | Completed | v2 입력2/2·JEV1승1패·전수 감사/뷰어/정리 |
| EX-050 | [JEV 준비 경로 교정2경기](EX-050-jev-judgment-recovery.md) | Completed | 정상완료2/2·JEV1승1패·전수 감사/보고/봉인/정리 |
| EX-049 | [JEV 판단 오류 비중단2경기](EX-049-jev-judgment-repeat.md) | Incomplete | cwd 준비 실패·API0·EX-050으로 연결 |
| EX-048 | [JEV 수정본2경기](EX-048-jev-repeat.md) | Incomplete | 첫 경기 승리·두 번째 최댓값 검사 중단·정상완료1/2 |
| EX-047 | [JEV Choice 배틀 진단](EX-047-jev-battle.md) | Incomplete | 확률합 검증 중단·정상완료0/2 |
| EX-046 | [비동기 교정본 공식 관측 선봉 비교](EX-046-async-official-lead.md) | Completed | 32경기·16쌍 유효완료·공급자별 탐색 결과 |
| EX-045 | [공식 관측 B2 선봉 비교](EX-045-official-lead.md) | Incomplete | 공식 추적기 오류 중단·비교 미완료 |
| EX-044 | [교정 선봉 직접 본실험](EX-044-direct-corrected-lead.md) | Incomplete | 반사 기술 입력 결함 중단·부분 결과 |
| EX-043 | [교정 B2 개선 선봉 비교](EX-043-corrected-lead.md) | Incomplete | 실행 설정 오류로 중단·정정 감사/보고 보존 |
| EX-042 | [공급자4+4 B2 선봉 비교](EX-042-distributed-lead.md) | Incomplete | 공급자 오류·계산 미지원 중단·보고/정리 완료 |
| EX-041 | [Z.ai 동시성4 B2 선봉 정책](EX-041-b2-lead-zai4.md) | Incomplete | 통신 실패·비교 기준 미달·보고/정리 완료 |
| EX-040 | [Z.ai B2 선봉 정책32](EX-040-b2-lead-zai.md) | Stopped | 첫429 중단·비교 미완료 |
| EX-039 | [B2 선봉 정책 비교](EX-039-b2-lead-proposal.md) | Stopped | 사용자 지시로 실행·감시 종료·비교 미완료 |
| EX-038 | [A/B2 직접대결32](EX-038-ab-head-to-head32-b2.md) | Blocked | 입력 오류 중단·설명 검토 조기 종료 |
| EX-037 | [Protect 수정본 A/B32](EX-037-ab-head-to-head32-protectfix.md) | Blocked | 유효·완료쌍 기준 미달 |
| EX-036 | [A/B 직접대결32](EX-036-ab-head-to-head32.md) | Stopped | 계산 실패 중단·비교 미완료 |
| EX-035 | [원본 A64 진단](EX-035-a-diagnostic64.md) | Completed | 진단 완료·효능 확증 아님 |
| EX-034 | [Smogon 원본 A 진단 설계](EX-034-smogon-diagnostic-design.md) | Prepared | 평가 명세 준비·대전 미실행 |
| EX-033 | [외부 메모리 장애 후 동일32판](EX-033-external-memory-repeat32.md) | Completed | 반복 비교 완료·효능 확증 아님 |
| EX-032 | [수정 완료본 A/B32판](EX-032-battle-guide-movefix32.md) | Completed | 중단 처리 완료·성능 비교 미완료 |
| EX-031 | [교정 입력·계산기 동일32판](EX-031-calculator-inputfix32.md) | Completed | 중단 처리 완료·성능 비교 미완료 |
| EX-030 | [계산기 입력 전체 로컬 감사](EX-030-calculator-input-audit.md) | Completed | 입력 감사·교정·별도 영향 분석 |
| EX-029 | [계산기 교정 동일 조건 A/B32판](EX-029-calculator-entry-calcfix32.md) | Completed | 중단 처리 완료·성능 비교 미완료 |
| EX-028 | [사전 검증 생략 A/B32판](EX-028-battle-guide-direct32.md) | Completed | slot 처리 완료·비교 미완료·정정은 기록 참조 |
| EX-027 | [필드 설명서 실제 Cloud 비교](EX-027-battle-guide-live.md) | Stopped | Cloud gate 실패·배틀 미실행 |
| EX-026 | [요약 없는 A/B 비교](EX-026-io-battle-only.md) | Blocked | Cloud gate 실패·배틀 미실행 |
| EX-025 | [요약 thinking low/max 진단](EX-025-summary-max-diagnostic.md) | Invalidated | 입력·평가 불일치로 전체 무효·검토 미완료 |
| EX-024 | [low 요약 지시 개선 후 IO 재실험](EX-024-low-summary-prompt-reexperiment.md) | Blocked | 요약 gate 실패·비교 미실행 |
| EX-023 | [상태 교정 후 IO 재개](EX-023-continue-io.md) | Blocked | 사실·입력 오류 중단 |
| EX-022 | [상태 처리 정비 후 요약 thinking 비교](EX-022-state-summary-thinking.md) | Blocked | 입력 누락으로 비교 무효 |
| EX-021 | [요약 오류의 harness 기여도 비교](EX-021-summary-harness-diagnostics.md) | Blocked | weather 변환·기준 오류로 비교 무효 |
| EX-020 | [개선 IO 재실험](EX-020-resume-io.md) | Blocked | 요약 사실 오류 중단·후속 미실행 |
| EX-019 | [특수 기술 피해 계산 진단](EX-019-special-move-diagnostics.md) | Completed | 수치 불일치 재현·전체 offline gate 미통과 |
| EX-018 | [Ruination 패치 재검증](EX-018-ruination-offline-revalidation.md) | Completed | 패치 재검증·전체 offline gate 미통과 |
| EX-017 | [개선 IO 오프라인](EX-017-improved-io-offline.md) | Stopped | 계산 불일치·Cloud 미실행 |
| EX-016 | [원본 fallback 병렬32판](EX-016-upstream-fallback.md) | Completed | 상세 조건·결과는 기록 참조 |
| EX-015 | [식별 수정과 요청 후보 조건 검증](EX-015-action-candidate-validation.md) | Completed | Cloud 출력 오류·후속 미실행 |
| EX-014 | [동일 조건의 병렬 32판 반복](EX-014-parallel-thirty-two-repeat.md) | Completed | slot 처리 완료·불완전 실행은 기록 참조 |
| EX-013 | [선택 조건의 32판](EX-013-parallel-thirty-two-final.md) | Completed | slot 처리 완료·불완전 실행은 기록 참조 |
| EX-012 | [포트 정리를 보완한 순차 8판](EX-012-sequential-eight-final.md) | Completed | 상세 조건·결과는 기록 참조 |
| EX-011 | [포트 정리를 보완한 병렬 8판](EX-011-parallel-eight-final.md) | Completed | 상세 조건·결과는 기록 참조 |
| EX-010 | [수정coordinator 조건부32판](EX-010-parallel-thirty-two-revised.md) | NotRun | 상세 조건·결과는 기록 참조 |
| EX-009 | [수정coordinator 순차8판](EX-009-sequential-eight-revised.md) | Stopped | 상세 조건·결과는 기록 참조 |
| EX-008 | [수정된 coordinator의 병렬 8판](EX-008-parallel-eight-revised.md) | Completed | 상세 조건·결과는 기록 참조 |
| EX-007 | [C* 배틀/모델 요청의 조건부 32판](EX-007-parallel-thirty-two.md) | NotRun | 상세 조건·결과는 기록 참조 |
| EX-006 | [동일 수정 source의 병렬 8판 (배틀 min(C*,8)/모델 요청 C*)](EX-006-parallel-eight.md) | Stopped | 상세 조건·결과는 기록 참조 |
| EX-005 | [동일 수정 source의 순차 8판 (배틀1/요청1)](EX-005-sequential-eight.md) | NotRun | 상세 조건·결과는 기록 참조 |
| EX-004 | [모델별 요청 동시성 측정](EX-004-model-concurrency-calibration.md) | Completed | 상세 조건·결과는 기록 참조 |
| EX-003 | [핵심 8판 시간 재측정](EX-003-core-smoke-timing.md) | Completed | 시간 재측정·후속예산 평가 |
| EX-002 | [수정 후 기준선 pilot](EX-002-pokechamp-baseline-pilot.md) | Completed | 기준선 운영 측정·실패 포함 |
| EX-001 | [기준선 pilot](EX-001-pokechamp-baseline-pilot.md) | Stopped | 중단 pilot 원형 보존 |

기존 raw/frozen artifact는
[`AgenticSTS-Data/experiments/`](../../AgenticSTS-Data/experiments/)와
[`AgenticSTS-Data/runs/`](../../AgenticSTS-Data/runs/)에 남아 있다. 기존 historical protocol과
report는 [`AgenticSTS/docs/experiments/`](../../AgenticSTS/docs/experiments/)에 남아 있다. 이곳의
새 record는 가능한 경우 해당 artifact를 path, tag, commit/SHA, checksum으로 link한다.

이 historical experiment는 새 연구 backlog가 아니며 default hypothesis, baseline, metric,
denominator 또는 follow-up을 제공하지 않는다. 새 experiment는 새로운 질문에서 시작한다.
Legacy artifact를 사용할 때는 새 record에서 그 사용을 명시적으로 정당화해야 한다.

## Experiment 기록 방법

1. [`TEMPLATE.md`](TEMPLATE.md)를 `EX-XXX-short-title.md`로 복사한다. Evidence file이 여러 개
   필요하면 experiment directory의 `README.md`로 복사할 수 있다. Stable ID를 부여하고 위
   table에도 한 행을 추가한다.
2. Run 전에 질문, condition, denominator, stopping rule, isolation policy, version, model
   setting, seed/run order, invalidation criterion을 기록한다.
   D-029 채택 후 새 실험은 [공통 복구 절차](../RESEARCH_DESIGN.md#defect-recovery)와
   [C-018](../CONTRACTS.md#c-018-recovery)를 확인하고 전체 중단 예외의 사유·범위,
   재수집 허용 여부·단위·한도(금지이면 0), 최초 시계·누적 승인/예산/호출 상한 및 실행기
   지원 여부를 함께 등록한다. 기존 실험의 규칙·판정·halt는 이 등록 절차로 소급 변경하지 않는다.
3. Code, harness, store 또는 operational work가 필요하면 대응하는
   [`active exec plan`](../exec-plans/active/)을 link한다.
4. 실행 중 모든 attempt를 보존하거나 audit trail을 명시적으로 설명한다. Condition을 조용히
   relabel, discard 또는 merge하지 않는다.
5. Evidence가 생긴 뒤에만 result를 기록한다. 빈 field에는 `TBD` 또는 `Not run`을 사용하며,
   측정값처럼 보이는 placeholder number를 만들지 않는다.
6. Status 또는 탐색용 요지가 바뀌면 개별 record와 해당 index row를 갱신한다. 핵심 evidence의
   상세 갱신은 개별 record에 기록하고 이 색인에는 복제하지 않는다. 종결할 때 observation과
   interpretation을 구분하고 limitation 또는 invalidation을 개별 record에 나열한다.

Experiment note는 authority hierarchy에서 implementation보다 아래에 있는 evidence다. Decision
또는 Contract 변경의 동기가 될 수 있지만 그 자체로 변경을 일으킬 수는 없다.
