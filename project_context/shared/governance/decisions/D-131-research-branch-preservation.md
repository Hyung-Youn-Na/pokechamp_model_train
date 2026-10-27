# D-131 — 연구 목적별 브랜치 분리와 실험 자산 보존

- Status: Accepted
- Date: 2026-10-12
- 승인: 사용자가 제공한 「연구 목적별 브랜치 분리 및 실험 자산 보존 계획」의 구현·검증 지시

## 결정과 범위

`main` 및 기존 원격 참조는 `e93a7b166b0c4b8721bd802d1e9d6731eecbffcf`에 유지한다.
현재 미커밋 소스·설정·테스트·문서를 선별 보존한 공통 기준 커밋에서
`research/model-training`, `research/l1-l5-port`를 분기하고 고정 태그
`snapshot/pre-split`을 만든다. 태그는 이후 이동하지 않는다. 원격 push·main 병합은 하지 않는다.

`/workspace`는 모델 학습·정책 개선·독립 평가를 위한 주 개발 브랜치와 기존 실행 환경으로
유지한다. L1–L5 구조 이식 연구는 별도 worktree에서 보존·후속 설계 목적으로 구분하며
현재 실행 작업은 없다. 사용자 지시에 따라 각 브랜치 CHARTER·연구 설계·STATUS·아키텍처·
README의 현재 목적과 안내를 분리한다. 기존 연구 조건·평가·해석을 바꾸거나 실험을 재개하지 않는다.

보존 루트는 `/mnt/digicap/combined/hyna/backup/pokechamp-research`다. 기존
`backup/pokechamp` 학습 자료는 원위치에 유지한다. 원본은 삭제·이동하지 않고 복사 후
파일 종류·크기·SHA-256·symlink 대상과 복사 결과를 대조한다. 별도 Git 저장소·worktree의
커밋·미커밋 변경·미추적 소스, 모델의 실제 blob, 참조된 외부 환경을 포함한다.
자격증명은 Git·보존 패키지에서 제외한다. 복사된 가상환경의 재배치 실행 가능성을 보장하지 않는다.

Git에는 소스·테스트·설정·문서·작은 고정 입력을 명시 목록으로 추가한다. 대형 생성물·과거
evidence·모델·로그·설치 환경은 외부 사본 및 manifest에 연결하며 기존 추적 파일은 제거하지 않는다.
자산 manifest와 Git 연결 receipt를 분리해 최종 커밋·태그·manifest 해시를 외부 receipt에 기록한다.

## 불변 조건과 후속 경계

기존 ADR·EX·동결 protocol·봉인·절대경로·Blocked/Paused 판정은 보존한다. 코드 삭제·공통화,
API/CLI/학습 알고리즘 변경, 환경 이동·재설치·upgrade, submodule pin 변경, GPU/외부 API/실제 배틀,
과거 실험 재개는 이번 범위 밖이다. Qwen 준비 코드의 EP132 경로 불일치는 후속 항목으로 남긴다.
새 실험 출력은 기존 CLI의 명시적 출력 인자로 `runs/model-training/<새 실험 ID>`를 선택한다.
출력 선택이 없는 과거 실행기를 새 실험용으로 자동 재사용하지 않는다.

진행·검증·복원 연결은 [EP-135](../plans/EP-135-research-branch-preservation.md)가 관리한다.
