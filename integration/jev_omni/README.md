# Jev-Omni 텍스트 수행 모델

D-156/EX-103의 `executor.model: jev-omni` 전용 연결이다. 모델·revision·환경·자원은
config.py, 공식 파일 identity는 download.py에서 고정한다. 공식 JevOmni.predict와 head를
원본 그대로 불러오고 로컬 지정 revision을 BF16으로 적재한다. 모델 카드의 FP32 설명과 달리
현재 체크포인트는 BF16이다. head 저장값은 FP32이며 공식 BF16 autocast를 따른다.

전체 state/계획/지시문·후보별 `{ID: 객체}`를 JSON 텍스트로 전달한다. 숫자형 선택지와
공식 processor/chat template·enable_thinking=False를 유지하고 CPU 길이 검사와 실제 forward
입력 ID를 대조한다. 32768토큰·16후보 무절단, 공식 선택 index 역매핑·원확률 보존·출력토큰0.
미디어·생성·양자화·모델 대체는 사용하지 않는다.

GPU0 UUID 소유권·동시1·allocator40GiB/GPU44GiB/소유host32GiB를 적용한다. 영속 HTTP 장부의
중복방지와 별도 omni-forward.jsonl의 실제 forward/원응답을 연결한다. 기존 환경은 보존한다.
사전8요청의 모든 동일 입력 쌍은 선택 일치를 요구하고 확률 차이는 진단으로 남긴다.
구체 실행·중단·완료는 EX-103과 EP-162를 따르며 구현의 존재는 추가 실행을 승인하지 않는다.
