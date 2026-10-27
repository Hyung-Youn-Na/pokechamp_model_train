# Showdown 규칙 Q&A v1

[EP-169](../../../project_context/research/rule-learning/plans/EP-169-showdown-ruleqa.md)·
[D-159](../../../project_context/research/rule-learning/decisions/D-159-showdown-ruleqa.md)의 CPU 생성기다.
기존 평가/replay를 읽어 학습 입력으로 만들지 않는다. 새 Gen9 OU 팀·제어 장면과 공식 관측기를 사용한다.

## 실행

기존 Python/Node 환경에서 wrapper를 사용한다. GPU·모델 추론·네트워크 다운로드가 없다.

```bash
scripts/pokechamp-ruleqa prepare --groups 1 --output /tmp/ruleqa-pilot
scripts/pokechamp-ruleqa generate --workers 4 --output /tmp/ruleqa-pilot
scripts/pokechamp-ruleqa validate --output /tmp/ruleqa-pilot

scripts/pokechamp-ruleqa prepare
scripts/pokechamp-ruleqa generate --workers 4
scripts/pokechamp-ruleqa validate
# review_samples.json의 96상황을 별도로 읽고 semantic_review.json을 기록한 뒤:
scripts/pokechamp-ruleqa export
```

기본 출력은 `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/showdown-ruleqa/v1/`다.
수직 검증의 1묶음/규칙 자료는 export할 수 없다. prepare 이후 source/data 변경, 기존 출력 덮어쓰기,
미검증/불완전 분모, split 중복, 누락된 의미 검토를 거부한다. 실패 원인은 JSON 보고와 evidence에 남는다.

## 구현 경계

- `specs.py`: 공개 질문의 조건과 새로운 팀·장면 명세. `prepare.cjs`가 Gen9 OU 팀 합법성을 검사한다.
- `simulator.cjs`: 실제 battle에서 선택 전 snapshot과 actor request를 얻는다. HP/상태/설치물/PP 등의
  제어 개입은 scene.stage에 보존한다. 파생 oracle 분기는 원 snapshot 복사본에서 실행한다.
  정상 경기 표본이나 자연적으로 발생한 상태 분포라고 주장하지 않는다.
- `state.py`: actor cutoff → 공식 관측 → 공개 사실 → v6 → names-v1. v6 복사본의 version과
  confusion volatile의 name/kind/general_effect만 교정한다. 같은 이름의 Psychic 기술은 보존한다.
  원 행동 실행 지시문은 QA 입력에 넣지 않으며 실제 합법 행동 후보는 battle_actions에 유지한다.
- `questions.py`: 공개 State·명시적 가정으로 답을 계산하고 독립 Showdown 사실/분기와 대조한다.
  조건부 수치 피해는 기존 v6 계산기의 추천세트 범위를 유지한다. oracle은 model input이 아니다.
- `partition.py`: 최소 관련 사실·조건·질문 및 동일 State를 기준으로 원천 묶음을 연결한다.
  닉네임/request ID는 무시하고 실제 종·기술·유효한 수치 조건은 보존한다. 연결 성분을 깨지 않고
  seed 20261019로 규칙별32/4/4를 배정한 뒤 세 표현을 만든다. 분할 불가능이면 차단한다.
- `validation.py`: 전수 oracle·문항·MC·공개경계·무관변형·대조·교정·분할 검사.
  `lengths.py`는 기존 Tacit/JEV tokenizer의 native chat template로 입력과 전체 SFT 길이를 무절단 검사한다.

## 산출물과 사용

`canonical.jsonl`과 `train/validation/test.jsonl`이 원본 문항이다. `exports/messages/`는 같은 문항의
대화 SFT 표현이며 `exports/multiple_choice/`는 State 선택형만 담는다. 두 export를 독립 표본으로 합산하지 않는다.
짧은 Q&A·State Q&A·State 선택형도 동일 상황의 파생 표현이다.

`evidence/`에는 내부 세트·oracle·검증 로그가 있어 **모델 입력으로 사용하면 안 된다**.
학습에는 exports의 명시된 필드만 사용한다. messages의 assistant가 정답 target이며 system/user가 입력이다.
manifest·검증 보고·규칙별 representatives·96상황 의미 검토는 학습 파일과 별도로 보관한다.
`semantic_review.json`은 canonical_sha256, passed, reviewer, reviewed_at 및 96개의
`{scenario_id, verdict: "pass", notes}`를 갖는다. 자동으로 통과 서명을 만들지 않는다.

이 자료는 같은 템플릿 계열 안의 규칙 적용 검사이며 미지의 템플릿 또는 실제 배틀 성능에 대한
독립 평가를 대신하지 않는다. Stellar·다른 세대·더블은 지원하지 않는다. 각 문항에 명시하지 않은
예외를 지원한다고 주장하지 않는다. Ground 접지는 Gravity/Smack Down/Iron Ball/Ingrain, 일반 Tera는 방어/STAB,
Rapid Spin은 표준 네 종류의 설치물, 행동 순서는 동순위/Trick Room과 우선도 우선 원칙으로 한정한다.

검증된 장면의 질문 표현만 수정할 때에는 새 출력에 `prepare` 후
`generate --relabel-from <검증된 이전 출력>`을 사용할 수 있다. 문항·실행 제어·검증 코드 외
source 변경, 명세·Showdown·자료·관측/계산기 변경은 거부한다. spec/input/result/evidence를
그대로 보존하며 새 question만 만든다. 물리 장면 재사용과 원본 manifest/hash는
relabel_provenance.json에 기록되고, 새 canonical은 전수 validate와 의미 검토를 다시 거친다.

선택형 내보내기의 입력 필드는 `state`, `battle_actions`, `conditions`, `question`, `options`다.
`answer_id`는 target, `rationale`은 설명 target, `id`/`split`은 관리 metadata이므로 입력에 합치지 않는다.
