# EX123 System One JevK5 실전32

EX116 선택epoch2를 GPU1/2/3 각각의 독립vLLM replica에 적재한다. 고정16진영교환쌍을6/5/5쌍으로 나누며 전체32경기다. 상세v6/Abyssal/원seed를 보존한다. T=1, 서빙BF16 LoRA이며 학습FP32와의차이를 기록한다.

`scripts/jevk5-system1-battle prepare`는 CPU검사와 모의6경기/뷰어검증(모델호출0)을 수행한다.
`run`은 순차적재·replica별6gate→공통시작표식→최대3병렬경기→GPU별원문감사/뷰어→전역32집계/한국어보고/봉인/자원반환이다. `status`는 저장기록만 읽는다.

출력은 보존루트 EX-123, GPU별shards/gpu1..3. 전체뷰어 exports/battle_viewers/ex123/index.html.
원시event번호를병합하지않고slot_id와paired_slot_id로전역목록을연결한다.
모델18851/18852/18853, Showdown8104/8105/8106. GPU0/8107 및 사용자서버는 사용/종료하지 않는다.
GPU각44GiB미만·shardhost32GiB·전체host64GiB. 최초사전요청부터12시간·물리HTTP합계20000, 재경기0. 실제조건은 등록EX123을 따른다.

UIv1은 EX114의검증된8탭/리플레이 renderer를분리복사해새판본 `jevk5-system1-researcher-v1`으로고정했다. 복사소스의LICENSE/NOTICE를유지한다.
