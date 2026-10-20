# Quyet-Medium 2단계 평가

[EX-084](../../project_context/experiments/EX-084-quyet-medium-two-stage.md)와
[C-065](../../project_context/CONTRACTS.md#c-065-quyet-two-stage)가 조건·실행 경계의 원문이다.
기존 jev-choice-v4 관측과 Abyssal·대진 자산을 사용하며 새 모델 성적은32경기 모두 새로 수집한다.

```bash
scripts/quyet download
scripts/quyet prepare
scripts/quyet execute
```

이미 있는 실행/뷰어를 덮어쓰거나 수집을 재개하지 않는다. `download`는 공개 파일 전송,
`prepare`는 공식 manifest 대조·9개 요청 CPU 토큰화, `execute`는 CPU 검사·GPU0–3의
본 서버1회 적재·최대9회 사전추론·조건부32경기·감사/내보내기·봉인/자원 반환을 수행한다.
`status`는 저장 결과를 읽고 `--help`는 실행하지 않는다.

모델 환경은 기존 `.pokechamp-data/jev27b-runtime/.venv`, 공식 패키지는 `/ref/quyet/src`로
연결한다. 설치/환경 수정은 없다. 입력 상태/전체32768토큰을 자르지 않고 `strict=True`로
검사한다. 공식 prompt v1과 Choice1.3313 보정을 사용한다. 텍스트32층은8층씩 네 GPU에
배치하며 embedding/공유 head는GPU0, 최종 norm은GPU3이다.

각 결정의 `action_type`/`action_detail`에는 자동 사유·실제 HTTP·formatter·응답·usage·
지연이 따로 남는다. 완료한 유형 단계를 재추론하지 않으며 세부 확률은 선택 유형의 조건부다.
대기·선봉/강제교체 유형 생략·단일 후보는 모델 추론과 구분한다.

실행은 보존 루트 `runs/model-training/EX-084`, 열람용 뷰어는
`exports/battle_viewers/ex084/index.html`이다. `collection/battle-N/audit.json`은 경기마다
한 번 수행한 감사, `final-audit.json`은 그 기록의 완전성·산술/봉인 확인이다.
`evidence/completion.json`과 `report.md`는 최초 종결 기록이다. 최종 보고는 `final-report.md`,
종료 로그/봉인 순서 교정은 `corrections/final-seal-v1/`에서 원 봉인·수집 소스와 연결한다.
수집 후 교정한 현재 코드는 완료 로그를 먼저 flush하고 봉인하며, 실험 원자료는 그대로 보존한다.
전수 데이터 대조와 대표 화면의 이동/오프라인 검사를 구분한다.

서버/클라이언트·자원/배틀 lifecycle 코드는 EX-083의 검증된 구현을 이 경로에 분리하여
모델 identity와 단계 의미만 연결했다. 기존 JEV 경로·자료·봉인·환경은 변경하지 않는다.
과거 실패·중단의 재개와 새 실험의 승인 범위는 이 명령의 존재로 확장되지 않는다.
