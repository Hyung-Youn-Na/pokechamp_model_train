# 문서·연구선 운영 — 구성 설명

이 문서는 **개편 전 중앙 문서의 서문·연구선 안내를 당시 범위로 보존**한다.
아래 본문의 “이 문서”, “현재”, “원문 소유권”은 이전 시점의 문서를 가리킨다.
현재 권한 배치·작업 절차는 [루트 INDEX](../../INDEX.md), 현재 목표는 [CHARTER](../../CHARTER.md),
진행 상태는 [STATUS](../../STATUS.md)가 소유한다. 이전 실험의 규범 참조·해석 범위는 보존한다.


D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.

<a id="아키텍처-architecture"></a>
# 아키텍처 (Architecture)

`research/model-training`은 `/workspace`에서 모델 학습·정책 개선·독립 평가를 개발하는
연구선이다. [D-131](decisions/D-131-research-branch-preservation.md)의 분리는 공통 코드 기준선을 유지하고 목적·작업 안내를 구분한다.
기존 Python API·CLI·모델 입출력·학습 알고리즘과 submodule pin은 이번 단계에서 변경하지 않는다.

현재 실행 환경·interpreter·가상환경·캐시는 `/workspace`의 원경로에 둔다. 새 실험은 출력 경로를
선택할 수 있는 기존 CLI의 명시적 인자로 `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/<새 실험 ID>`를
사용하며 과거 실행기의 고정 출력 경로를 바꾸지 않는다. EX-084/085를 완료했으며
EP-140의 EX-086/087 공개 정보 v6 재평가는 공유 입력 결함으로 중단했다.
현재 구현에는 사후CPU 교정이 반영됐고 원 수집source와 구분해 보존한다.
D-136/EP-141의 새 승인으로 EX-088/089를 별도 코호트/출력에서 각32경기 평가하고
감사·비교·뷰어·봉인·반환을 완료했다. D-137/EP-143의 EX-090은 별도 피해 예측 제거 프로필을
사용하며 현재 실행 상태는 STATUS와 개별 EP/EX에서 관리한다.
보존본·별도 Git 저장소·모델 blob·복원 연결은 [연구선 작업·출력·복원 안내](../../RESEARCH_WORKFLOW.md)를 따른다.

L1-L5 구조 이식은 별도 `research/l1-l5-port`의 보존·후속 설계 목적이다.
이 문서의 AgenticSTS와 기존 학습·JEV 구성 설명은 공통 기준선의 사실이며 자동 실행 목록이 아니다.
상세 AgenticSTS 구조는 [상속 아키텍처](../../../AgenticSTS/docs/reference/ARCHITECTURE.md)와
[repository layout](../../../AgenticSTS/docs/reference/REPO_LAYOUT.md)에 보존한다.

현재 공통 경로와 특정 정책의 실행 경로를 구별한다. 실행 승인·조건은 [CONTRACTS](../../CONTRACTS.md)와
[RESEARCH_DESIGN](../../RESEARCH_DESIGN.md), 단계별 자격·결과는 [STATUS](../../STATUS.md)와 개별 EX 기록을 따른다.
기능이 존재한다는 사실은 중단 실험의 재개 권한이 아니다.

D-156의 `integration/jev_omni/`는 공식 JevOmni 텍스트 processor·숫자형 선택지·BF16
분류기를 `jev-planner`의 독립 모델로 연결한다. 전용 환경·GPU0/동시1·32768/16 무절단·
원 index 역매핑·원확률·출력0과 별도 실제 forward 원장을 유지한다. 구체 실행 상태는 EP-162다.
