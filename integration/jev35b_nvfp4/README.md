# JEV-35B-NVFP4 단일 GPU 연결

D-148/EX-095 전용 모델 선택은 `executor.model: jev35b-nvfp4`다.
모델·revision·interpreter·GPU0/Marlin·엔진 옵션은 config.py에 고정한다.
공식 파일은 원본 그대로 사용하고 `download.py`가 LFS SHA256 또는 Git blob identity를 검증한다.
전용 Python3.11 환경에는 공식 vLLM0.31.0+cu129 wheel, torch2.13.0+cu129,
torchvision0.28.0+cu129, torchaudio2.11.0+cu129, Transformers5.17.0을 설치한다.
환경 잠금·다운로드 영수증과 실제 검증 결과는 `project_context/exec-plans/evidence/ep154`에 둔다.

`compatibility` 모듈은 새 환경의 CUDA/BF16 실제 연산을 GPU0 소유권/메모리 감시 안에서
한 번 확인한다. 버전 문자열만으로 통과시키지 않는다. 실패 시 모델 적재/GLM/경기에 진입하지 않는다.
통과 뒤 공식파일·CPU감사·포트·자원을 확인하고 기존 `jev-planner prepare/run`을 사용한다.

원 요청은 영속 장부의 앞단18845에서 받고 공식 `serve_decide.py` 자식18846에 전달한다.
공식 System1 템플릿과 같게 state/instructions·완전한 `{ID:후보객체}` 문자열·순서를 보존한다.
엔진의 bias/temperature 적용 결과를 원 ID로 연결하며 공식 응답/usage/엔진 요청 수를 보존한다.
`BoundedWorker`는 모델 의미를 바꾸지 않고 실제 vLLM CUDA worker의 allocator40GiB를 제한·기록한다.
앞단은 CUDA context를 만들지 않고 GPU 잠금·NVML44GiB·소유 프로세스 RSS32GiB 감시를 유지한다.
원 공식 소스는 수정하지 않는다.

`evaluation.executor_preflight`는 무호출 CPU 감사가 만든8요청 JSON 경로다. prepare가 내용을
동결하며 같은 서버로8회 추론·공유256예산 예약·반복 일치/확률차1e-4 이하를 검사한 뒤 경기에
진입한다. 사전추론 기록과 배틀 결정은 구별한다. 엔진 길이32769/입력32768, completion1을
출력0으로 바꾸지 않는다. 적재 실패·진입 실패·부분 경기 실패도 원문과 미실행 분모로 보존한다.

기존 세 모델의 interpreter/loader·과거 실험은 보존한다. 실행 가능한 경로의 추가는
추가 경기·재적재·드라이버 변경·모델 대체의 승인이 아니다.

EX-095는 최초 단일 적재·8사전추론 뒤 반복성 기준 실패로 본경기 미실행1·Blocked다.
구현의 존재가 새 실행이나 자동 재개를 승인하지 않는다. 결과와 한계는 EP-154/EX-095 보고를 따른다.

D-149/EX-096의 `evaluation.executor_repeat_policy=probability_diagnostic`는 반복 확률 차이를
기록하며 계속 진행한다. 반복 선택 일치와 모든 입력/분포/매핑/usage·자원 검사는 유지한다.
필드 부재 또는 `strict`는 기존1e-4 차단을 유지하며 새 정책을 과거 준비본에 소급하지 않는다.
