# EP-165 — Pokémon Showdown SFT 원본 보관

- 상태: Completed
- 생성일: 2026-10-16
- 책임자: Codex
- 승인 근거·범위: 현재 사용자의 계획 구현 지시. 지정 Hugging Face 데이터셋의 고정 revision 원본 다운로드·검증·보관 기록.
- 관련 원문: [INDEX 절차](../../INDEX.md#workflow), [C-007](../../CONTRACTS.md#c-007-distribution-및-provenance-경계), [연구 매뉴얼](../../RESEARCH_MANUAL.md), [보존 안내](../../RESEARCH_WORKFLOW.md#preservation)
- 기준/실제 연구선: `research/model-training`
- 시작 commit: `a4659bf298c7935714f9fbd25246db2d831c5926`; 기존 미커밋 변경은 보존한다.
- checkout·실행기: `/workspace`, `/workspace/pokechamp/.venv/bin/hf`, `/workspace/pokechamp/.venv/bin/python` (huggingface_hub 0.36.0, pyarrow 22.0.0)
- 새 원본/검증 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/stevenkhan/pokemon-showdown-battle-sft/` 및 그 안의 `manifest.json`
- 참조 원본: https://huggingface.co/datasets/stevenkhan/pokemon-showdown-battle-sft ; revision `8acf5b03d84cc3cad9a52906f237c4db199bd59a`

## 목표·범위·불변 조건

원본 README·.gitattributes·Parquet 2개를 원래 구조로 직접 보관한다. manifest에는 출처 URL,
revision, 다운로드 시각, 원문 선언 라이선스, 파일 목록/크기와 검증 결과를 기록한다.
기존 snapshot·보존 manifest·실험 원자료·봉인은 변경하지 않는다. 전처리·분할 변경·학습·배틀·
GPU/모델/API 추론은 범위 밖이다. 비배틀 자료 보관이므로 EX·뷰어·실험 복구 시계는 해당 없다.
색인과 active plan을 확인했으며 해당 데이터셋 보관과 겹치는 plan은 없다. EP-163/164는 별도
모델 평가로, 그 실행기·환경·원자료를 변경하지 않는다. 기존 환경의 의존성도 변경하지 않는다.

## 완료 기준

- [x] 고정 revision 전체 원본 4개 파일 다운로드, Hub 목록·크기 대조.
- [x] 로컬 Parquet 2개를 열어 총 500,057행과 모든 messages의 role/content 문자열 구조 확인.
- [x] 원문 선언 라이선스·파일 목록·검증·다운로드 시각을 manifest에 기록.
- [x] plan·색인·STATUS에 보관 위치 연결 및 최종 경로·용량·행 수 보고.

## 검증

| 변경 영향 | 검사 | evidence | 결과 |
|---|---|---|---|
| 원본 정체성·완전성 | 고정 revision Hub 파일 목록/크기, LFS SHA-256 및 작은 파일 Git blob 대조 | 데이터셋 manifest | 통과 |
| 데이터 구조·행 수 | pyarrow batch 전수 열람·구조 검사, metadata/실제 행 집계 | 데이터셋 manifest | 통과 |
| 문서 연결 | 변경분·링크·상태 대조 | 본 plan·색인·STATUS | 완료 |

## 진행·중단

- 2026-10-16 — 사용자 승인 범위를 등록했다. Hub API에서 고정 revision 4개 파일·train 500,057행·원문 선언 `apache-2.0`을 확인했다.
- INDEX 공통 중단 기준을 따른다. 원본/revision/검증 충돌은 기록·보고하며 완료로 처리하지 않는다.

## 결과 및 증거

- 원본 4개 파일 합계 **537,045,320 bytes** (537.045320 MB, 약 512.17 MiB); Parquet 합계 537,037,976 bytes.
- train-00000: 250,029행; train-00001: 250,028행; 합계 **500,057행**을 전수 열람했다.
- 모든 행은 system/user/assistant 각 1개씩 3개 메시지이며, role/content는 모두 문자열이다.
- 원격 4개 파일 목록·크기와 로컬을 대조했다. Parquet는 원격 LFS SHA-256,
  README/.gitattributes는 원격 Git blob ID와 일치했다. 원문 선언 라이선스는 `apache-2.0`이다.
- 다운로드 완료 시각: `2026-10-16T08:39:26.028451+00:00` (마지막 원본 파일 mtime);
  검증 시각: `2026-10-16T08:40:02.154071+00:00`.
- [보관 폴더](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/stevenkhan/pokemon-showdown-battle-sft/) · [manifest](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/stevenkhan/pokemon-showdown-battle-sft/manifest.json)
- [검증 스크립트](../evidence/ep165/verify_archive.py):
  `/workspace/pokechamp/.venv/bin/python project_context/exec-plans/evidence/ep165/verify_archive.py`로 실행했다.
  최초 보관용으로 기존 manifest가 있으면 덮어쓰지 않고 중단한다.
- `hf download`의 `.cache/huggingface/`는 전송 metadata이며 원본 파일 수/용량에서 제외했다.
- 원본 보관 기준을 모두 충족했다. 전략 설명의 정확성·학습 적합성·성능은 검증 범위 밖이다.
  기존 snapshot·보존 manifest·환경·실험 자료는 이번 작업에서 수정하지 않았다.
