# JevK5-9B v6 상세32경기

EX111 전용. 조건·상한·해석은 [EX111](../../project_context/experiments/EX-111-jevk5-v6-battle32.md),
진행은 [EP181](../../project_context/exec-plans/completed/EP-181-jevk5-v6-battle32.md)을 따른다.

`scripts/jevk5-battle status`는 저장 기록만 읽는다. capture는 외부 서버/로컬파일 정체성을
기록하며 모델을 적재하지 않는다. mock은 모의2경기, gates는 대표3종 각2회 실제 추론,
prepare는 동결, execute는 본32경기 단1회, export는 봉인된 수집의 뷰어를 생성한다.
모든 출력은 별도 EX111이며 기존 출력의 덮어쓰기/자동재개를 거부한다.

사용자 소유 GPU0 vLLM18847을 유지하고 소유 Showdown8108·Abyssal/controller·사용 잠금만 반환한다.
v6 전체 입력을 공식 JevK5 evidence/criterion/options에 가역 변환한다.
모든 후보 logprob을 조회하여 temperature1.316 보정/argmax로 원ID를 선택한다.
생성된 글자는 선택 정책이 아니며 응답1토큰은 사용량에 포함한다. 내부 실제 forward 수는 미관측이다.
입력 상한32768·최대16후보·절단/요약/후보제거0이다. 실제 세 종류 prompt를 native template와 대조한다.

`upstream_prompt.py`는 /ref/jevk5 commit f26426d16f59e8bbe1470e5b162cc89329e29b29의
jevk5/prompt.py 원본이다. Apache-2.0 LICENSE/NOTICE와 SemIf 저작권 안내를 함께 보존한다.

검증: `PYTHONPATH=/workspace:/workspace/pokechamp pokechamp/.venv/bin/python -m pytest integration/jevk5_battle/test_core.py -q`.
