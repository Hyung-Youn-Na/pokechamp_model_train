# EP-098 — RLCD-Lite 전용 worktree 환경

- 상태: Completed
- 생성일: 2026-09-28
- 책임자: Codex
- 승인 근거: 사용자가 RLCD-Lite도 EP-096/097과 같은 방법으로 환경 구성하도록 지시했다. 이전 가상환경 명명 요청을 유지한다.
- 관련: [INDEX](../../INDEX.md#workflow), [CHARTER](../../CHARTER.md), [ARCHITECTURE](../../ARCHITECTURE.md), [EP-097](../completed/EP-097-eve-rlcd-environment.md).

## 목표·범위

독립 source·worktree·명명된 가상환경에서 설치·기본 테스트·CUDA·공개 모델 최소 추론을 검증한다. 현재 연구 목표의 보조 환경 준비이며 연구 방법·처치·평가를 변경하지 않는다.

- source: `/workspace/.tools/rlcd-lite/upstream`
- worktree: `/workspace/.tools/rlcd-lite/worktrees/pokemon-training`, branch `pokemon-training-env`
- upstream commit: `b0f981fab5e6ce53dd089eae71b141ab1099c31a`
- Python3.11.11·`.venv-rlcd-lite`·prompt `rlcd-lite`. uv0.12.9 사용.
- upstream lock의 Torch2.14/CUDA13은 현재 driver535와 맞지 않는다. 외부 worktree의 pyproject에 Torch2.11.0+cu128·공식 cu128 index를 고정하고 lock을 재생성한다. 원본 pyproject/lock은 source clone과 증거로 보존하고 설치본 diff를 기록한다. 이는 >=2.3 요구사항을 만족하는 hardware compatibility 설정이며 upstream lock 동일 재현이라고 주장하지 않는다.
- `all` extras와 dev 의존성 설치. 공개 Qwen2.5-0.5B-Instruct를 고정 revision/hash로 다운로드한다. 기본 GPU0.
- 공개 패키지/모델 다운로드와 설치/검증 도구 추가 허용. 현재 코드/실험/비밀 설정·LAYA/EVE 환경은 보존한다.
- 학습·배틀·TypeSafe 호출·host driver 변경·legacy plan 상속은 제외한다. 기존 active 배틀/IO 계획과 실행 범위가 겹치지 않는다.

## 완료 기준

- [x] 고정 source·독립 branch/worktree·명명된 환경
- [x] CUDA 호환 profile·lock·extras 설치·의존성 검사·패키지 목록
- [x] upstream 기본 Python 테스트·CLI 도움말
- [x] CUDA 연산·역전파·동기화
- [x] 공개 모델 revision/hash·GPU 로딩·최소 구조화 추론
- [x] 한국어 환경 구분/재진입 안내·보고·plan/색인/STATUS 동기화

## 검증·중단

증거는 `../evidence/ep098/`에 보존한다. 실패는 원인과 적용 source/config를 기록하고 재검증은 변경 또는 미해결 우려가 있는 범위로 한정한다. 비실험 환경 준비이므로 실험 시계·재수집·배틀 viewer는 해당 없음.

## 진행

- 2026-09-28 — upstream·Python·의존성/GPU 호환 범위를 확인하고 구현 전 등록했다.
- 2026-09-28 — 독립 환경·CUDA12.8 호환 lock·all extras 설치와 의존성/활성화/CLI 검증을 완료했다. upstream27검사·CUDA 역전파·고정 공개 모델 GPU 로딩·JSON/확률·block/simple/cached 비교가 통과했다. [검증 보고](../evidence/ep098/report.md), [환경 안내](../../../.tools/rlcd-lite/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md). 공개 모델 학습·배틀·TypeSafe 호출0이며 환경 준비 완료다.
