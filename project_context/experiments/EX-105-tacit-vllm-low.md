# EX-105 — Tacit vLLM Thinking + GLM-5.3 Low

- 상태: Completed
- 생성일: 2026-10-16
- 승인: [D-158](../decisions/D-158-tacit-vllm-low.md)
- 계획: [EP-164](../exec-plans/completed/EP-164-tacit-vllm-low.md)
- 연구선/checkout: research/model-training /workspace a4659bf; 기존 미커밋 변경 보존.

## 질문·조건·비교

사용자가 띄운 Tacit-9B vLLM 서버에서 EX-104의 판단 비교와 정상1경기를 새로 수행한다.
[EX-104](EX-104-tacit-thinking-low.md)의 입력·대진·seed·GLM low·사건 정책·사전8·고정3·
첫 판단 기록 후 always thinking·공식 prompt/decode/마감/reencode·8192/0.6/0.95/20·후보 역매핑·
전후 비교·행동 진단·해석 제한을 참조 편입한다. 과거 실험 재개가 아니다.

처치 변경은 수행 모델 backend 패키지다. 동일 Tacit revision884838f1698d1fd746625b3c20c8ec2be077a183,
BF16 vLLM0.31.0, GPU1/TP1, max_model_len49152/max_num_seqs1, prefix caching,
VLLM_USE_FLASHINFER_SAMPLER=0의 native sampler와 현재 서버 설정을 기록한다.
http://127.0.0.1:18847/v1 의 tacit9b에 연결하며 GPU 서버 재적재/변경/종료0이다.
첫/최종 판독은 모든 후보 token ID를 logprob_token_ids로 요청하고 후보 간 정규화한다.
상위20개 근사/후보 누락 허용0. 두 판독의 max_tokens1 생성은 각각 실제 출력량에 포함하고
thinking 생성량과 구분한다. 단계별 HTTP 요청/응답·prompt token ID·생성 token ID·전체 후보
logprob·seed·usage·지연을 보존한다. 물리 forward/allocator/processed input은 직접 관측할 수
없으므로 null과 미관측 사유를 기록하며 HTTP 수/토큰 수로 대체 추정하지 않는다.
동일 seed의 backend 간 토큰 일치를 주장하지 않는다. EX-103 및 EX-104 완결 부분과 비교하되
서빙/계측 변경을 포함한 단일 실행 관찰이며 속도 인과효과나 일반 성능을 주장하지 않는다.

## 검증·한도·중단

CPU 공식 prompt/token ID/후보 보존·readout 정규화·종료·usage·중복방지·raw HTTP/누락 거부 검사,
기존 입력 전수 길이검사 및 사건/공유 실행 회귀 후 source/조건을 동결한다.
외부 서버 identity/PID/startticks/model/config를 read-only 확인하고 같은 서버에서 사전8 반복선택
gate를 적용한다. 확률차는 진단이다. 고정3 후 실제1경기, 추가 경기/재수집/재적재/자동재개0.
논리 pipeline256(사전11포함), 외부 수행 HTTP768(한 pipeline 최대3), GLM HTTP128.
외부 HTTP 자동 재전송0; 프런트의 동일 request ID 재조회는 EX-104와 같은 중복방지 의미다.
GPU1 전체44GiB, 외부 서버 process tree와 소유 CPU 합산 host32GiB를 감시한다.
allocator40GiB는 외부 서버 API로 검증 불가이므로 이번 EX에 적용하지 않고 전체 GPU 측정을
사용한다. 외부 서버 기존 적재 비용은 수집 비용에서 제외한다. 경기/전체시간/disk:null.
외부 서버 소유권/유휴/반환 gate 대신 identity 불변·건강 확인·미종료 검사를 적용한다.
새 소유 CPU 프런트/Showdown/PID/잠금/8109·18845 포트만 정리한다.
RD11.1/C-018, RD11.2/C-046 적용. 기술/gate 실패 시 의존 수집 중단·부분 보존/정리,
독립 CPU 도구 교정/보고만 허용하고 최초 시계·누적 상한 초기화0. 합법 판단 오류는 진단 후 계속.

## 출력·완료

run: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-105
증거: project_context/exec-plans/evidence/ep164
viewer: exports/battle_viewers/ex105/index.html
condition: glm53-tacit-vllm-thinking-matchup-events-low

정상1경기·전수 호출/최종명령/GLM low/서버 identity/자원 감사·전후/기존 비교·관련 사례 검토·
C-047/073 뷰어와 이동후 오프라인/복사/다운로드·기존 봉인 보존·새 봉인·소유 자원 반환·
외부 서버 유지·상태/색인 갱신이 완료 기준이다. 단계 알람으로 수집 종료/차단/최종 완료를 알린다.

## 결과

정상1/1·67턴 패배·75결정(모델73/자동2). 전후 선택 변경25/73, 길이 강제마감49/73. 전체pipeline84/외부HTTP252·GLM30, 중복·미완결·재시도0. 실제 선봉 제외72모델 결정 평균184.16초, 전략 포함189.92초. 전수감사·비교·사례검토·오프라인 뷰어·기존봉인보존·새봉인·소유CPU자원반환/외부서버유지 완료. [최종 보고](../exec-plans/evidence/ep164/report.md). 추가실행0.
