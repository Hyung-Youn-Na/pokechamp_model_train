# JEV-27B 로컬 평가

공개 JEV-27B의 고정 revision·공식 formatter·BF16 backbone·FP32 결정 head를 사용한다.
규범은 [C-063/C-064](../../project_context/CONTRACTS.md#c-064-jev27b-continuation),
실행 조건은 [EX-082](../../project_context/experiments/EX-082-jev27b-ex058-reproduction.md)와
[EX-083](../../project_context/experiments/EX-083-jev27b-four-gpu-continuation.md)를 따른다.

## EX-083 계승

```bash
scripts/jev27b continue \
  --parent /workspace/.pokechamp-data/jev/ex082-live \
  --directory /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-083
```

승인된 EX-082 부모만 받으며 기존 실행 출력/뷰어의 덮어쓰기·재개는 거부한다.
부모 정상23경기를 그대로 계승하고 원 실패24번 추가1회·미실행25–32번만 수행한다.
출력의 `evidence/`에는 CPU·부모검증·진입/종료 근거, `gates/`에는 두 독립 재로딩·591응답
재생·연속 메모리 검사, `serving/`에는 서버 원장·자원 표본, `collection/`에는 새 경기·감사와
계승 분모를 보존한다. root source snapshot은 새 실행 시점의 미커밋 변경도 포함한다.

`ex083` 프로필은 GPU0–3 모두를 잠그고 유휴/UUID를 확인한 뒤 CUDA를 초기화한다.
모델 배치는0–13/14–31/32–49/50–63층이며 embedding은0, 최종 norm/head는3이다.
allocator 예산40GiB와 장치 전체 중단선44GiB를 별도로 적용한다. HTTP 형태와 입력은
그대로이며 프로필/배치/한도는 새 serving identity로 구별한다.

모든 검증을 통과한 동일 서버로만 수집에 진입한다. gate/기술 오류나 자원 초과 시 원인을
기록하고 소유 프로세스·GPU·잠금·포트를 반환한다. 실패 상태에서 자동 재시도하지 않는다.
추가 실험 승인은 이 명령의 존재로 주어지지 않는다.

EX-083 최초 모델 적재 전 UUID 비교 결함의 한정 복구는
`--recover-uuid-preflight --uuid-diagnostic <독립 장치 진단>`을 사용한다.
첫 실패 봉인·추론/배틀0·같은 모델/배치·허용한 소스 차이·네 GPU의 독립 UUID byte 검증과
반환을 확인하고 원본 전체를 `preflight-attempt1/`로 보존한 뒤 모든 gate를 다시 수행한다.
해당 hash의 첫 실패 외에는 거부하며 수치/메모리 실패나 수집 중단을 재개하지 않는다.

완료 뷰어는 `exports/battle_viewers/ex083/index.html`이다. 고유경기와 전체 시도, 부모 원실패,
2GPU/4GPU 구간은 구별한다. 출력 봉인 후 폴더 이동·오프라인 JSON 대조까지 확인한다.

## 기존 경로

`execute`·`download`·`lengths`는 기존 EX-082 고정 경로를 유지한다. 특히 `execute --help`는
실행 인자를 해석하는 도움말이 아니므로 사용하지 않는다. 일반 안내는 `scripts/jev27b --help`,
계승 명령 인자 안내는 `scripts/jev27b continue --help`다.

모델 프로세스는 `.pokechamp-data/jev27b-runtime/.venv/bin/python`, controller/actor는
`pokechamp/.venv/bin/python`을 사용한다. 새 설치·학습·양자화·offload는 수행하지 않는다.
