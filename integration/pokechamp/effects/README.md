# 요청별 Gen9 상세 효과 사전

[D-057](../../../project_context/research/input-and-memory/decisions/D-057-effect-reference.md) /
[C-037](../../../project_context/research/input-and-memory/CONTRACTS.md#c-037-effect-reference)의 원본 자산과 전송 경계다.
`gen9-effects-v1.json`은 저장소 고정 Showdown의 Gen9 Dex `desc`를 그대로 수록한다.
이름·설명은 영어 원문이며 요약·번역·shortDesc 대체·설명 속 다른 항목의 재귀 확장을 하지 않는다.
출처 commit, 자산/extractor SHA-256, 항목 수는 [provenance.json](provenance.json),
라이선스 전문은 [LICENSE](LICENSE)에 있다. 라이선스는 upstream MIT다.

## 생성·검증

저장소 루트에서 실행한다. 기존 버전 자산을 배포 중 덮어쓰는 명령으로 사용하지 않는다.

```bash
node integration/pokechamp/effects/extract.cjs /tmp/new-dex-export
python -m integration.pokechamp.effects.prompt_assets
```

첫 명령 결과를 봉인 자산과 바이트 대조한다. 두 번째는 작성된 schema에서 새 프롬프트 원문과
hash를 재생성한다. 공통 타입·배열 원소는 한 번 정의하며 schema가 설명서와 자료형 검사의 원문이다.
`battle-v1.3.0`, `b2-effects-v1`, `team-preview v1.1.0`, `gen9-effects-v1`은 별도 identity다.

## 입력과 정보 경계

`delivery.build(full, kind="battle"|"b2"|"lead")`는 원본을 바꾸지 않고 모델용 사전을 추가한다.
B2는 기존 동결 codec을 사용한 전송 projection에서 참조를 수집한다. 명시적 item/ability/move 필드,
공개 효과 map, 이력의 요청 JSON·기술 사용·도구/특성 공개·typed source tag를 읽는다.
종족·닉네임·채팅·자연어 설명에서는 세트를 추정하지 않는다. 효과 설명을 스캔해 항목을 늘리지 않는다.
상태 sentinel과 recharge 행동 marker는 항목이 아니다. 실제 참조의 미해석 ID/desc 누락은 경로·ID가
있는 `input_contract` 오류다. 일반 status/volatile 토큰은 반드시 Dex 기술/특성과 같은 개념이 아니므로
일치하는 명시적 효과 이름만 조회한다.

선봉은 기존 자기 제출/최초 request와 공개 preview cutoff만 사용한다. 사전이 특정 상대의 보유나
현재 발동을 뜻하지 않으며 이미 계산된 효과를 다시 적용하지 않도록 system에 명시한다.
`validate`는 전송 직전에 원본과 선택 버전으로 재생성하여 문자열·identity 전체를 대조한다.
원본 snapshot과 모델용 system/user의 hash는 trace와 viewer에 함께 보존한다.

## 선택·호환

D-066 이후 기본 선택은 [공식 관측 안내](../observation/README.md)를 따른다.
명시적 `--observation-backend legacy-poke-env` 새 선봉 `prepare`는 이 문서의 개선 prompt와
`preparation_version=effects-v1`을 봉인한다.
기존 `b2-llm-lead-v1` 정책의 RNG·출력복구·실행기 경계를 재사용하되 D-057의 명시된 새
프롬프트 선택이 이전 정책의 prompt 기본값에 우선한다. `paid_budget=null`, 등록 EX 없음이며
과거 `register_execution`/유료 `reserve`로 전환할 수 없다. 새 성능 실험은 별도 설계·승인이 필요하다.
`--experiment-id EX-039/040/041` 또는 기존 봉인은 v1.2.0/B2/선봉 v1.0.0을 유지한다.
일반 B의 명시적 legacy prepare는 v1.3.0을 봉인하며 명시적 과거 정책은 그 정책의 버전을 선택한다.

검증·대표 전후 입력·크기·한계는 [EP-046 보고서](../../../project_context/exec-plans/evidence/ep046/report.md)를 참조한다.

JEV v3는 별도 `../jev_effects.py`의 typed projection으로 동일 자산을 사용한다.
후보 move.id와 요청 기술 슬롯 ID를 읽고 불리언 terastallize를 이름으로 해석하지 않는다.
JEV 계약은 [C-045](../../../project_context/research/model-evaluation/CONTRACTS.md#c-045-jev-battle),
[오프라인 검증](../../../project_context/exec-plans/evidence/ep074/report.md)을 참조한다.
