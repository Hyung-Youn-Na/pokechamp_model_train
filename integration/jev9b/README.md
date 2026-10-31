# JEV-9B 단일 Choice 평가

[EX-085](../../project_context/research/model-evaluation/experiments/EX-085-jev9b-single-choice.md)의 공식 JEV-9B 패키지와
jev-choice-v4 단일 Choice를 연결한다. 기존 JEV 모델 환경·관측 생성·후보 순서·배틀 player·
전송 원장·감사·뷰어 자산을 재사용하고 모델 identity와32층 배치만 명시 프로필로 분리한다.
규범은 [C-066](../../project_context/research/model-evaluation/CONTRACTS.md#c-066-jev9b-single-choice)이다.

```bash
scripts/jev9b download --workers 2
scripts/jev9b prepare
scripts/jev9b execute
scripts/jev9b status
```

`download`는 지정 revision의 텍스트 System1 필수 파일과 공식 identity receipt를 보존한다.
`prepare`는 CPU에서8개 대표 입력을 무절단 토큰화한다. `execute`는 source/조건 고정·CPU 검사·
본 서버1회 적재·최대8회 GPU 검증 후 동일 서버로32경기를 한 번씩 시도하고 감사·비교·
내보내기·반환·봉인을 수행한다. 기존 출력의 덮어쓰기와 수집 재개는 거부한다.
`status`는 저장 결과 조회다. 도움말은 모든 명령에서 실행 전에 인자를 해석한다.

모델 interpreter는 `.pokechamp-data/jev27b-runtime/.venv/bin/python`, actor는
`pokechamp/.venv/bin/python`이다. 새 모델은 `.pokechamp-data/jev9b-runtime/model`, 출력은
`<BACKUP_ROOT>/pokechamp-research/runs/model-training/EX-085`, 뷰어는
`exports/battle_viewers/ex085/index.html`이다. 환경 재설치·학습·양자화·offload0이다.

GPU0 embedding·0–5층, GPU1 6–15층, GPU2 16–25층, GPU3 26–31층·norm/LM head/결정 head를
고정한다. 네 장치의 잠금·유휴·UUID·allocator40GiB/장치44GiB와 호스트32GiB·디스크100GiB를
감시한다. HTTP는600초와 같은 ID/본문의 최대3회 재전송(10/30/60초)을 사용하고 실제 추론은
영속 원장으로 중복을 막는다. 경기/단계/전체 경과시간 상한은 없다.
현재 디스크 계수는 공유 actor 환경·브라우저 도구·브라우저 바이너리도 포함한다.
EX-085의 수집 당시 감시 범위와 종료 후 계수/코드 교정은
[최종 보고](../../project_context/exec-plans/evidence/ep139/report.md)에서 구분한다.

새 경기별로 한 번 감사를 수행한 뒤 종료 시 receipt와 산술을 확인한다. 원문을 모두 내보내
대조하고 정상/자동/실패 표시의 대표 화면만 이동 후 오프라인 검사한다. 마지막 로그와
모든 쓰기가 끝난 뒤 봉인하며 EX-083의 고유32경기는 비교 기준으로만 참조한다.
