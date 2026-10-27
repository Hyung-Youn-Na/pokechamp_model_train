# EX-018 — Ruination 패치 후 오프라인 재검증

- Status: Completed
- 날짜: 2026-09-08
- 관련: [D-020](../decisions/D-020-project-owned-ruination-patch.md), [EP-011](../plans/EP-011-improved-io.md)

## 실행 전 protocol

질문은 ruination-v1이 지정 피해 규칙과 기존 회귀를 만족하고 EX-017의 계산 오류를 해소하는지다.
분모는 EX-016의 기존 개발15장면 재생과 사후3건이며 신규 장면·확증 팀·Cloud 호출은 없다.
원자료 root는 `.pokechamp-data/experiments/glm-upstream-fallback32-v1/battles`, 발췌는
`.pokechamp-data/benchmarks/glm-upstream-fallback32-v1/analysis/io_evidence.json`이다. 행동 입력은 결정 시점 이전 protocol과 자기 세트만
사용하고 공개 HP 반올림 범위/prior를 유지한다. 사후 검증만 별도 truth root 인자로 원본 상대
세트와 결정 이후 이벤트를 읽는다. 결과는 `.pokechamp-data/io-improvement/ep011-ruination-v1/`의
replay-final/posthoc-final에 별도 봉인한다. 패치/코드 source archive를 보존한다.

성공 기준은 패치 및 기존 회귀 통과, 재생15/15 성공, 사후3/3 일치다. Ruination 기대값은
Tinkaton 최대HP373, 피해186, 잔여187, 공개51/100이다. 새 불일치 또는 미지원 효과 발견 시
해당 검증을 중단한다. 계산 성공은 명중·실행 확률 또는 전체 의미 rubric 통과가 아니다.
`offline_gate_passed=false`를 유지하고 병렬·Cloud·48판은 실행하지 않는다.

## 결과

- 패치 회귀19건 통과; 기존 회귀를 포함한 전체181 tests 통과(33.58초, 외부 Pydantic deprecation 경고1).
- 새 설치와 idempotent 재적용 성공. 버전·누락·파일 변조 및 응답 identity 실패는 종료/LLM 차단.
- Ruff E/F/I/W(100열), Node syntax, compileall 통과.
- 결정시점 재생15/15 성공. 공개 HP 범위 및 prior를 유지했다.
- 사후3/3 일치: Draco Meteor576–678(최대HP415, 기절 cap), Earthquake0(Air Balloon),
  Ruination186(최대HP373, 잔여187, event43 공개51/100).
- `patch_validation_passed=true`, `offline_gate_passed=false`. 의미 rubric 미검증 상태를 유지한다.
- Cloud 호출0; fake12/Cloud180/smoke12/48판 미실행. 효능·승률·실행 확률 claim 없음.

## 봉인 evidence

- [최종 재생 receipt](../../../../.pokechamp-data/io-improvement/ep011-ruination-v1/replay-final/result.json)
- [최종 사후 대조](../../../../.pokechamp-data/io-improvement/ep011-ruination-v1/posthoc-final/result.json)
- [종합 검증 receipt](../../../../.pokechamp-data/io-improvement/ep011-ruination-v1/verification.json)
- [source archive manifest](../../../../.pokechamp-data/io-improvement/ep011-ruination-v1/source.json)

초기 replay/posthoc도 보존한다. README와 test formatting의 source 변경 후 최종 source로 다시
재생/대조하여 별도 `*-final`을 봉인했다. EX-017의 실패 receipt 및68파일 archive 해시도 확인한다.
