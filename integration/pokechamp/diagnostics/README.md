# 특수 기술 오프라인 진단

## JEV 기술별 피해량 샘플 (EP-082)

`jev_damage_samples`는 EX-057 저장 입력의 출전 포켓몬끼리 양방향 피해량을 계산하는
별도 오프라인 변환기다. 2026-09-18 고정 Smogon OU 추천 세트를 세트별로 전개하고
공개 관측으로 제한한다. `jev_damage_verify`는 개별 Smogon 호출과 합성 테라 관측을 대조한다.
모델 호출·새 배틀·JEV 운영 기본값 변경은 없다.

```sh
cd /workspace/pokechamp
PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.diagnostics.jev_damage_samples --output /tmp/jev-damage-review-new
PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.diagnostics.jev_damage_verify --output /tmp/jev-damage-review-new
```

첫 명령은 새 경로만 허용하며 두 번째 명령은 그 산출물을 검증한다.
설정/출처·전체 전후 JSON·기술 비교·미지원 범위·원시 계산은
[EP-082 보고](../../../project_context/exec-plans/evidence/ep082/report.md)를 참조한다.

## 특수 기술 독립 대조

플레이어별 현재 parser/B2/공식 클라이언트 비교는
[EP-055 관측 추적 진단](observation-comparison.md)의 명령·JSONL·경계·해석을 참조한다.

운영 actor/calculator를 수정하지 않고 pinned Showdown Gen9의 테스트 전용 `Format`과
raw @smogon/calc 0.11.0 + ruination-v1, 실제 Python/Node wrapper를 대조한다.

```sh
PYTHONPATH=. pokechamp/.venv/bin/python -m integration.pokechamp.diagnostics.special_moves \
  --output .pokechamp-data/io-improvement/ex019-special-moves-new
```

새 디렉터리만 허용한다. `manifest.json`에 팀1·2·6·12, prior 전체/관측 기술이 없을 때
앞4개 기본 선택, 필수 고위험 기술, 조건, 제외·미검증 사유와 source hash를 먼저 쓴다.
알 수 없는 ID는 중단한다. 원본 Ditto prior의 `Nothing`은 이름/출처를 보존하여 제외한다.
Gen9 custom format은 기술 합법성 검사를 생략하지만 runMove의 실행·면역·Protect 판정은
실행한다. 기존 submodule이나 format registry 파일을 수정하지 않는다.

관측 경계는 `Pokemon.damage` 호출 직전(게임의 Damage event 이후)과 직후다.
명중만 강제하고 자연적으로 확정 critical인 기술을 제외한 critical은 끈다.
각 fixture는 새 Battle을 사용하며 85–100 난수를 각각 실행한다. 연속 공격은 모든 타격에
같은 난수를 주는 조건부 경로이며 독립 난수의 전체 확률분포가 아니다. 반사 기술은 실제
선행 기술 실행과 `beforeTurnCallback`을 사용한다. scheduler/행동 선택·미래 턴·잔여 피해는
실행하지 않으며 필요한 입력이 없는 기술은 정상0이어도 `input_insufficient`다.

- `oracle.jsonl`: Showdown의 직접 피해 전/후 수치, 타격/피격별 관측, 실제 상태, protocol과 raw calculator 응답.
- `wrapper.jsonl`: 같은 pre-move HP를 포함한 실제 Python/Node wrapper 응답.
- `reproductions.jsonl`: 불일치 fixture를 새 Node 프로세스에서 재생성한 결과.
- `results.json`, `report.md`: 경계별 판정과 현재 사용 기술을 우선한 문제 목록.
- `sources.tar.gz`, `checksums.json`: 사용한 source/build/입력 snapshot과 출력 해시.

Showdown의 로드된 build source map은 pinned TypeScript와 대조한다. 테스트 전/후 source
hash를 확인하고, 재현에서는 protocol의 wall-clock `|t:|`만 비교에서 제외한다.
독립 불일치는 계속 조사하지만 oracle·상태 변환·source·검증기 오류는 전체 중단한다.
실패 디렉터리도 보존하고 새 identity로 재실행한다.

`diagnostic_complete`는 선정 시험의 결과/미검증 사유가 확보되었다는 뜻이다.
`calculator_all_passed`나 `offline_gate_passed`가 아니며 gate receipt를 발급하지 않는다.
EX-017·018과 개발 실패 자료는 변경하지 않는다. 자세한 원인과 최종 검증은
[EX-019](../../../project_context/research/input-and-memory/experiments/EX-019-special-move-diagnostics.md)에 기록한다.


## B2 선봉 로컬 검증

`python -m integration.pokechamp.diagnostics.team_preview --output <새 경로>`는
fake model을 쓰는2대응 경기/4 actor만 실행한다. 양측 선봉·첫 출전·B2 전투 입력·공통 원장/시계·viewer와
permit 반환을 검사하고 `verification.json`으로 봉인한다. 모델 호출/전략적 성능 평가는 없다.
실행은 `/workspace/pokechamp`에서 `PYTHONPATH=/workspace .venv/bin/python`을 사용한다.
[설정·명령·제한](../README.md#llm-lead), [EX-039 후속 초안](../../../project_context/research/lead-policy/experiments/EX-039-b2-lead-proposal.md).
