# 전략 계획과 행동 실행 — 구성 설명

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="전략-planner-설정-경로"></a>
### 전략 planner 설정 경로

D-148/EX-095의 `jev35b-nvfp4`는 전용 Python3.11 환경과 GPU0 Marlin W4A16을 사용한다.
장부 앞단18845→원본 공식 serve_decide.py 엔진18846으로 System1 Choice를 전달하고
원ID·후보순서·공식응답/usage를 보존한다. 세 기존 모델 경로와 분리하며 gate는 EX-095를 따른다.

D-139/EP-145의 `integration/jev_planner/`와 `scripts/jev-planner`는 기존 고정EX 경로와
분리된 설정 기반 실행기다. JSON에서 planner·executor·trigger·prompt·evaluation을 분리하고
prepare가 코드·입력·설정·prompt 원문을 고정한다. off는 선택한 입력 표현으로 JEV만 사용한다.
D-141/EP-147의 새 names-v1은 현재 자기 팀/기술 slot에서 표시명을 만들어 후보에 추가한다.
Planner와 JEV의 후보는 동일하고 ID/순서/참조/명령은 보존한다. original과 과거 설정은
원 v6 입력을 유지하며 새 뷰어는 전달된 display_name을 우선 표시한다.
D-140/EP-146부터 새 설정은 prompts.guide의 역할·승리 경로·자원 안내를 별도로 동결해
planner 지시문 뒤에 붙인다. guide 없는 과거 준비본만 당시 v6 안내 조립을 유지한다.
guide별 조합과 비교는 front prompt+guide 본문을 하나의 프롬프트 조건으로 식별한다.
동기 controller는 같은 불변 관측/cutoff에서 계획을 갱신하고 JEV에 전략 조언과 생성/경과턴을
추가한다. D-143의 새 수행 지시문은 현재 목표 충족 확인·불필요한 반복 회피·유효한 미완료 목표
진전을 안내한다. 공개사건 위치와 자기 강제교체 request를 추적하며 동일rqid 중복/변경과 단일후보를 구별한다.
D-154의 명시 사건 선택은 공개 switch/drag/replace와 출전 폼변화 행을 같은 좌표 기반
보류 큐로 처리한다. 기본 사건 목록/모델 입력은 유지한다.
경기별 실제 Showdown 방 이름 재사용은 논리 경기ID와 protocol_battle 분리로 처리한다.

새 runtime은 기존 모델 패키지·formatter·배치/자원감시·영속 요청원장을 재사용한다.
모든 조건에서 하나의 호출예산/최초시계를 공유하고, 동일rqid 내용/후보와 취소를 전송 직전까지
검사한다. 모의 provider는 실제 모델 호출 없이 로컬 Showdown 전송을 검사한다.
출력 실패는 경기로 격리하고 기술/예산 오류는 의존 수집 중단·소유자원 반환·분모 보존으로 연결한다.
모델서버는 별도 프로세스이며 actor 이벤트루프의 planner/결정 task 종료도 그 소유루프에서 수행한다.

D-158의 tacit9b-vllm은 사용자 소유 vLLM 서버와 CPU 프런트의 수명을 분리한다. 프런트의 논리 요청 원장은 중복 실행을 막고 외부 HTTP 세 단계의 모든 후보 logprob·원 token ID·usage를 저장한다. 외부 GPU/합산 host와 PID identity를 감시하되 사용자 서버는 종료하지 않는다. 내부 forward/allocator 미관측과 판독 생성2토큰은 EX-105의 계측 조건에 따른다.

D-157의 tacit9b는 별도 BF16 Transformers 환경에서 첫 라벨 판독·thinking 생성·마감 후 라벨 판독을 순서대로 수행한다. 첫 판단은 그림자 기록이며 최종판단만 명령으로 전달한다. 단일 논리 파이프라인 원장과 단계별 실제 forward/생성 기록을 구분하고 전후 분포·원추론·종료상태를 뷰어에 연결한다. 조건/한도는 EX-104를 따른다.

D-147부터 새 planner의 runtime_name은 디스크 상한 없는 `planner-*` 자원 profile이다.
model_runtime_name으로 기존 모델을 구성한 뒤 디스크 정책만null로 복사하여 모델 메타데이터에도
반영한다. 부모/서버/추가 감시는 같은 자원 profile을 사용한다. 기존 GPU 배치/메모리·사용량 기록과
실제 I/O 오류 처리는 유지하고 과거 실험 profile/봉인은 보존한다.

D-150의 새 planner 기본 temperature0·retry_scope=response_format은 JSON 구문·계획 스키마·
빈/잘린 응답·성공HTTP envelope 오류를 같은 입력/옵션으로 최대5회 추가 재생성한다.
원문/usage·생성/물리HTTP를 보존하고 planner_format_retry와 planner_json_retry를 구별한다.
과거 retry_scope 부재는json_syntax이며 명시 온도도 원값을 유지한다.

D-146 당시 planner.json_retries 기본5는 같은 논리계획 안에서 JSON content 구문 실패만
최초+5회까지 다시 생성한다. `planner_output_attempt`/`planner_json_retry`와 JSON차수별
transport_attempt·논리계획 전체 누적attempt를 기록하고 모든 HTTP를 같은 예산에 센다.
과거 필드 부재는0이며 최종 검증계획만 JEV에 전달한다. 집계는 구문재시도와 HTTP재시도를 구분한다.
EX-094는 이 정책의 새1경기에서64턴 패배로 정상종료했으며 실제 구문재시도는0이다.
합성/EX-093 실패원문으로 재시도 상한·회복을 검증하고 실제69GPU추론·원문·뷰어·반환을 감사했다.

보고기는 모의/저장재생/실제자료, 논리호출/HTTP시도, 미확인usage와 실패/미실행을 분리한다.
대응쌍은 paired_slot_id 그룹의 고유2슬롯/양쪽 actor로 집계하고 두 실험축이 함께 바뀌면 교란을 표시한다.
D-144/EP-150의 새 HTML/JS 경기 화면은 GLM 계획 기본7탭과 sticky 리플레이를 함께 제공한다.
`viewer_data.py`는 observation의 감사와 표시명/계획 추가 전 입력을 저장 피해에 연결하고,
EX-088 계열 `turn_logs`의 actor 공개행·고정 parser·결정 cutoff를 재사용한다.
큰 원문/피해는 결정별 로컬JS packet으로 지연 적재하고 선택 epoch로 늦은 덮어쓰기를 막는다.
`replay.js`는 sandbox iframe에서 부모의 최신 pause/seek만 적용하며 탭/재생 조작은 정보와 독립이다.
외부 공식 Showdown 자산 로딩 실패 시 로컬 로그를 표시한다. 계약은 [C-073](../../shared/viewers/CONTRACTS.md#c-073-planner-viewer)이다. 기존 renderer·뷰어·봉인은
보존한다. D-142/EX-092에서는 GLM planner와 JEV-9B의 실제1경기 연결·종결·감사/뷰어를
확인했다. 다른 조합의 새 실행 성공이나 일반 성능 개선으로 확대하지 않는다.
D-145/EX-093은 변경 수행 지시문의 실제1경기 시도에서14턴 GLM JSON 출력 오류로 실패했다.
부분17결정/16전송·통합뷰어·전수 감사·소유자원 반환을 보존하며 정상 완료로 해석하지 않는다.
[기술 안내](../../../integration/jev_planner/README.md)와 [C-070](CONTRACTS.md#c-070-jev-planner)을 따른다.
