# EP-096 — LAYA 전용 worktree 학습 환경

- 상태: Completed
- 생성일: 2026-09-27
- 책임자: Codex
- 승인 근거: 사용자가 LAYA 전용 worktree·설치/검증·LAYA 우선을 선택하고 최종 계획의 구현을 지시했다.
- 관련 원문: [INDEX](../../../INDEX.md#workflow), [CHARTER](../../../CHARTER.md), [ARCHITECTURE](../../../ARCHITECTURE.md), [연구 설계](../../../RESEARCH_DESIGN.md).

## 목표·범위

LAYA-RLCD의 고정 커밋으로 독립 worktree와 CUDA 학습 환경을 구성하고 공개 LAYA 모델 로딩·최소 추론까지 검증한다. 현재 연구 목표에 대한 보조 환경 준비이며 연구 목표·평가·처치를 변경하지 않는다.

- source: `/workspace/.tools/laya-rlcd/upstream`
- worktree: `/workspace/.tools/laya-rlcd/worktrees/pokemon-training`, branch `pokemon-training-env`
- upstream: `822a5a5ac278682bf4adc4a0f63814b70298be9b`
- Python 3.11.11, upstream `setup.py --training`, Torch 2.11.0+cu128 및 CUDA Torch 제약을 적용한 테스트 의존성.
- 공개 패키지·모델 다운로드 허용. 기본 GPU0, 독립 `.venv-train`, 공개 모델의 고정 revision·SHA-256 검증.
- 현재 미커밋 코드·인덱스·실험 자료·비밀 설정은 복사하지 않는다. driver 변경·자동 package fallback·TypeSafe 호출·배틀·학습/optimizer 갱신·게임/Node 설치는 제외한다.
- EP-062/064/075/077/080의 범위·중단 보존을 확인했다. 기존 integration 변경 및 실험 재개는 없다.

## 완료 기준

- [x] 고정 source와 별도 branch/worktree 구성
- [x] 독립 환경 설치·패키지 목록·pip check
- [x] upstream Python 테스트
- [x] GPU 텐서·행렬 연산·역전파·동기화
- [x] 공개 모델 revision/hash·GPU 로딩·최소 추론
- [x] 한국어 재진입 안내·검증 보고·plan/색인/STATUS 동기화

## 검증·중단

증거는 `../evidence/ep096/`에 보존한다. 설치·GPU·모델 실패는 원인과 미충족 기준을 기록하고 버전·드라이버 변경으로 우회하지 않는다. 비실험 환경 준비이므로 실험 시계·재수집·배틀 뷰어는 해당 없음.

## 진행

- 2026-09-27 — 승인 범위와 계획 등록. 구현 전 현재 worktree·미커밋 상태·upstream dependency/wheel·공개 모델 접근을 확인했다.
- 2026-09-27 — 설치·pip check·upstream20검사·CUDA 연산/역전파·고정 모델 GPU 로딩/최소 추론을 완료했다. driver 변경·API·배틀·학습 실행0. [검증 보고](../../../exec-plans/evidence/ep096/report.md), [환경 안내](../../../../.tools/laya-rlcd/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md). 환경 준비 완료이며 포켓몬 학습·성능은 미평가다.
