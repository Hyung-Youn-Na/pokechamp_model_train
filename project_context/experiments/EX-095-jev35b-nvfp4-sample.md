# EX-095 — JEV-35B-NVFP4 EX-094 동일 대진 샘플

- 상태: Blocked
- 생성일: 2026-10-15
- 승인: 사용자 제공 계획 구현·검증·실행 / D-148
- 계획: [EP-154](../exec-plans/active/EP-154-jev35b-nvfp4-sample.md)
- 연구선/checkout: research/model-training, /workspace; 시작 commit a4659bf, 기존 미커밋 변경 보존

## 질문·조건·분모

EX-094와 같은 첫 대진에서 새 모델의 실제 선택·계획 연동과 정상1경기를 수집한다.
모델·양자화·backend·GPU 배치의 결합 변경이며 단일 경기로 일반 성능·인과 효과를 주장하지 않는다.
학습0·과거 평가 입력은 CPU 연결검증/사전추론에만 사용하며 독립 holdout이라고 주장하지 않는다.
EX-094 b01-r3-s1·p1 대 Abyssal p2·팀/시드·세 프롬프트·GLM 생성 옵션·v6 계산기·표시명·
최초/3턴/기절/Tera/강제교체 호출정책을 동결 복사한다. 계획은 새 경기에서 생성한다.
JSON 구문 오류만 최초+5회 재생성하고 기존 HTTP 재시도 정책을 유지한다.

모델 autotrust/JEV-35B-NVFP4 revision10c2c62610e315e31a75baca849ad79d526e4658.
공식 가중치·토크나이저·adapter_vllm·264-slot head·bias·calibration·서빙 코드 identity 대조.
분리 Python3.11·공식 vLLM0.31.0 CUDA12.9 wheel/대응 PyTorch·Transformers5.17.0 고정.
GPU0·TP1·동시1·Marlin W4A16(BF16 활성화)·eager·gpu_memory_utilization0.80.
System1만 사용하며 thinking/System2·후보순열·tournament·추가양자화0.
앞단18845 영속 장부→공식 serve_decide.py 자식18846, Showdown8109. 점유 시 진입하지 않는다.
원 state/instructions·삽입순서의 {ID:후보객체} 문자열을 최대16옵션 Choice API에 전달한다.
엔진32769·입력32768토큰, readout1토큰 usage 원문을 보존한다.

## 한도·검증·중단

경기1·GLM HTTP128·JEV논리256(사전추론 포함)·경기3600초·전체4200초.
전체 시계는 첫 모델 적재부터 시작해 사전추론을 포함한다. GPUallocator40GiB·전체44GiB·
소유host32GiB·disk null, 사용량 기록. 기존 자격증명 위치만 사용하고 값을 기록하지 않는다.
CPU에서 EX-094의74결정 중 자동5/다후보69개를 분리하고 무손실·순서·표시명·계획·토큰경계 검사.
공식 head264·A–P·bias/temperature·확률/선택 원ID 매핑·요청ID 재전송 중복 추론 방지 검사.
한 번 적재한 본서버로 최대8회 사전추론(선봉/일반/강제교체/최장/최단/반복),
반복 선택 일치·최대 확률차1e-4 이하를 요구한다. 통과한 같은 서버로1경기 실행한다.
Marlin·rank320·드라이버 호환성·메모리 실패 시 GLM/배틀 진입0.
RD11.1/C-018·RD11.2/C-046·C-070/073 적용. 진입 전 도구 결함은 원본 보존·CPU교정/
독립검증을 허용하되 상한/적재 횟수를 늘리지 않는다. 진입 후 source/조건 변경·재경기·보충0.
출력복구 소진/실행 실패는 해당 경기 실패로 보존한다. 설명 정확성은 기본 제외다.

## 출력·완료

run: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-095
증거: project_context/exec-plans/evidence/ep154
viewer: exports/battle_viewers/ex095/index.html

정상1경기·실패포함 분모/GLM생성/재시도/JEV·엔진 수/선택→명령/usage/자원 전수감사,
원문·피해 통합뷰어·대표 이동후 오프라인/복사/다운로드·봉인·GPU반환이 완료 기준이다.
진입 전 실패는 미실행1로 구분하고 부분기록/차단 이유를 봉인한다. 과거 원자료·뷰어·봉인은 보존한다.

## 최종 결과·실패 종결

Marlin W4A16·rank320·GPU0 단일 적재와8사전추론을 수행했으나 반복성 gate를 통과하지 못했다.
최초/마지막 선택은team_1로 같았지만 최대 확률 차이0.004209933265540491>0.0001이다.
같은 입력1·5·8번 전체 최대는0.0071398573376539876이다. GLM/본경기 진입0,
예정1/시도0/완료0/경기실패0/미실행1이며 정상1경기 목표 미달이다.
입력120,704/출력8토큰·실제JEV/엔진8회·전송재시도0·실행257.630초를 기록했다.
추가추론·재적재·기준완화·재경기0이다. 원인은 미확정이며 일반 성능을 비교하지 않는다.

전수기술감사·실제8요청 원문/진단 부분뷰어·이동후 오프라인/복사/다운로드·봉인·GPU0/PID/잠금/
세포트 반환을 완료했다. GPU0 최대관측38,122MiB·최종0MiB, allocator/host 상한도 지켰다.
[실패 종결 보고](../exec-plans/evidence/ep154/report.md) · [감사](../exec-plans/evidence/ep154/audit.json) ·
[부분뷰어](../../exports/battle_viewers/ex095/index.html). 기존 EX-093/094는 보존하며 자동재개하지 않는다.
