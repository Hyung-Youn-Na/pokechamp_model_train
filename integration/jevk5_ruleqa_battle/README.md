# 학습 JevK5 LoRA 실전32

EX114 전용. `scripts/jevk5-ruleqa-battle run`은 사전 CPU/모의/UI지원 검증을 요구하고
GPU2의 동일모델·EX113 선택어댑터 임시서버(18849/32768)를 시작한다.
선봉/일반/강제교체 각2회 gate→동결→새32경기→감사→뷰어/보고/봉인과 소유자원 반환을 수행한다.
사용자 GPU1/18848 서버는 유지한다. `status`는 저장기록만 읽는다. 재경기/보충/학습은 없다.

원조건은 [EX114](../../project_context/research/rule-learning/experiments/EX-114-jevk5-ruleqa-battle32.md).
EX111의 v6/판독/감사를 독립 복사하고 UIv1의 기본5탭 뒤 실제프롬프트·선택지확률·선택/전송을 제공한다.
QA temperature1.4125375446227548은 배틀 확률 보정의 증거가 아니며, 학습6144보다 긴 입력의 전이를 구분한다.

출력: 보존루트 runs/model-training/EX-114, viewer exports/battle_viewers/ex114.
CPU검사: `PYTHONPATH=/workspace:/workspace/pokechamp pokechamp/.venv/bin/python -m pytest integration/jevk5_ruleqa_battle/test_core.py -q`.
원공식prompt의 라이선스는 이 폴더 LICENSE/NOTICE를 따른다.

브라우저/UI검사는 기존 `/tmp/ep037/tools/bin/python` 환경으로 `test_viewer.py` 및 `browser_check.py`를 실행한다.
