# EP-097 — EVE-RLCD 전용 worktree 환경

- 상태: Completed
- 생성일: 2026-09-28
- 책임자: Codex
- 승인 근거: 사용자 요청으로 EVE-RLCD도 EP-096과 같은 방법으로 설치·검증하고 가상환경을 이름으로 구분한다.
- 관련: [INDEX](../../../INDEX.md#workflow), [CHARTER](../../../CHARTER.md), [ARCHITECTURE](../../../ARCHITECTURE.md), [EP-096](EP-096-laya-training-environment.md).

## 목표·범위

고정 EVE-RLCD source와 독립 worktree에서 upstream lock에 맞춘 환경을 설치하고 테스트·CUDA·공개 결정 모델 로딩/최소 추론을 검증한다. 기존 연구 목표의 보조 환경 준비이며 연구 방법·처치·평가를 변경하지 않는다.

- source: `/workspace/.tools/eve-rlcd/upstream`
- worktree: `/workspace/.tools/eve-rlcd/worktrees/pokemon-training`, branch `pokemon-training-env`
- upstream commit: `adb9a0457ef53d2dc0e106215315670f1f6da871`
- Python 3.12 필요. 저장소 로컬 uv 0.12.9로 interpreter 설치와 `uv sync --locked`를 수행한다.
- 이름이 있는 `.venv-eve-rlcd`, `UV_PROJECT_ENVIRONMENT` 및 독립 HF/cache 설정을 사용한다. LAYA `.venv-train`은 보존한다.
- 공개 패키지·Python·모델·CPU 테스트 tokenizer 다운로드 허용. 공개 결정 모델은 정확한 revision과 파일 체크섬을 기록한다. 기본 GPU0 한 장.
- 기존 코드/실험/비밀 설정을 복사하지 않는다. 학습·배틀·TypeSafe 호출·host driver 변경은 제외한다. upstream legacy plan을 현재 작업으로 승계하지 않는다.
- 현재 active 계획은 기존 배틀/IO 실험의 중단 보존 단위로, 별도 source·환경 구성과 실행 범위가 겹치지 않는다. EP-096은 Completed이고 기존 모델 환경 변경은 없다.

## 완료 기준

- [x] 고정 source·독립 branch/worktree·명명된 환경 생성
- [x] Python3.12·upstream lock 설치·의존성 검사·전체 패키지 목록
- [x] upstream 기본 Python 테스트
- [x] CUDA 텐서·행렬 연산·역전파·동기화
- [x] 공개 결정 모델 revision/체크섬·GPU 로딩·최소 추론
- [x] 한국어 환경 구분/재진입 안내·검증 보고·plan/색인/STATUS 동기화

## 검증·중단

증거는 `../evidence/ep097/`에 보존한다. package/driver 실패는 원인과 미충족 기준을 기록하며 변경이 필요하면 현재 source·lock과의 차이를 명시한다. 비실험 환경 준비이므로 실험 시계·재수집·배틀 viewer는 해당 없음. CPU 테스트는 upstream 기본 marker 선택을 유지하고 대형 외부 모델/학습을 요구하는 network/gpu 표시는 자동 실행하지 않는다.

## 진행

- 2026-09-28 — 승인 범위·upstream commit·Python 및 lock 요구사항을 확인하고 구현 전 등록했다.
- 2026-09-28 — Python3.12.14·독립 명명 환경·locked sync·의존성 검사·활성화/모듈 출처를 검증했다. upstream223검사 통과(1 skipped, 5 deselected), CUDA 연산/역전파·고정 공개 모델 GPU 로딩/3종 질문 추론을 완료했다. [검증 보고](../../../exec-plans/evidence/ep097/report.md), [환경 구분 안내](../../../../.tools/eve-rlcd/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md). 학습 CLI 도움말·단위 테스트만 실행했고 공개 모델 학습·배틀·TypeSafe 호출0이다.
