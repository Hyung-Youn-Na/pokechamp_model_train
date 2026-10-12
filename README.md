# 포켓몬 모델 학습 연구선

현재 브랜치 `research/model-training`은 **모델 학습·정책 개선·독립 평가**를 위한 주 개발
연구선이다. 작업과 기존 실행 환경은 `/workspace`를 계속 사용한다.
[D-131](project_context/decisions/D-131-research-branch-preservation.md)에 따라 L1–L5 이식 연구는
별도 `research/l1-l5-port`에서 보존·후속 설계한다. 양쪽은 같은 공통 코드 기준선에서 출발한다.

브랜치·기준 태그·worktree·대형 자산 복사/검증과 목적 문서 분리의 범위·완료 근거는
[EP-135](project_context/exec-plans/completed/EP-135-research-branch-preservation.md)에서 관리한다.
새 연구 실험은 실행 중이지 않다.
기존 source·환경·모델·실험 evidence와 Blocked/Paused 판정을 보존한다.

- [프로젝트 맥락과 작업 규칙](project_context/INDEX.md)
- [이 연구선의 목표](project_context/CHARTER.md) · [연구 설계](project_context/RESEARCH_DESIGN.md)
- [현재 작업·제한](project_context/STATUS.md) · [구성](project_context/ARCHITECTURE.md)
- [작업·새 출력·외부 자산·복원 안내](project_context/RESEARCH_WORKFLOW.md)

외부 보존 루트는 `/mnt/digicap/combined/hyna/backup/pokechamp-research`다. 새 실험 출력은 승인된 새 ID와 기존 CLI의 명시적 출력 인자를
사용하여 그 아래 `runs/model-training/<새 실험 ID>`에 둔다. 출력 선택이 없는 과거 실행기는
자동 재사용하지 않으며 기존 manifest·봉인·고정 경로를 수정하지 않는다.

## AgenticSTS 연구 참고

AgenticSTS 관련 연구와 구현에 대한 자세한 내용은 [AgenticSTS 연구 폴더](AgenticSTS/)를 참고하세요.
