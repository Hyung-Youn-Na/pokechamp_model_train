# EP-171 — Pokémon Showdown Strategist 모델 보관·정보 확인

- 상태: Completed
- 생성일: 2026-10-19
- 책임자: Codex
- 승인: 사용자의 `stevenkhan/pokemon-showdown-strategist` 다운로드·모델 정보 확인 지시.
- 기준/실제 연구선: `research/model-training`, `/workspace`, 시작 commit `a4659bf298c7935714f9fbd25246db2d831c5926`; 기존 미커밋 변경 보존.
- 실행기: `/workspace/pokechamp/.venv/bin/hf`, `/workspace/pokechamp/.venv/bin/python`
- 원자료: https://huggingface.co/stevenkhan/pokemon-showdown-strategist
- 고정 revision: `f2726381423690cbe48f581c8027ce8b01012dae`
- 새 보관 위치: `/mnt/digicap/combined/hyna/backup/pokechamp-research/models/stevenkhan/pokemon-showdown-strategist/`
- 새 검증 기록: 위 폴더의 manifest.json, [검증 스크립트](../evidence/ep171/archive.py), [정보 보고](../evidence/ep171/report.md).
- 관련 원문: [INDEX](../../INDEX.md#workflow), [매뉴얼](../../RESEARCH_MANUAL.md), [보존 안내](../../RESEARCH_WORKFLOW.md#preservation), [C-007](../../CONTRACTS.md#c-007-distribution-및-provenance-경계).

## 목표·범위

원본11개 파일 92,248,228 bytes를 다운로드하고 모델 카드·adapter 설정·safetensors 헤더·
학습/추론 스크립트를 정적으로 확인한다. 공개된 가중치는 Qwen/Qwen3-0.6B용 LoRA 어댑터이며
기반 모델 가중치는 이 저장소에 없다. 기반 모델의 정보는 원격 공식 설정으로 확인하고,
별도 기반 모델 다운로드·추론·학습·배틀·의존성 설치는 이번 원본 보관 범위에 포함하지 않는다.
원본 스크립트와 pickle은 실행하지 않는다. training_args는 필요 시 pickle opcode로 정적 열람한다.
active plan 색인을 확인했으며 같은 어댑터 보관과 겹치는 plan은 없다. 기존 모델·환경·
보관본·manifest·실험 자료·중단 상태를 보존한다. 비실험이므로 EX/뷰어·실험 시계는 해당 없다.

## 완료 기준·검증

- [x] 고정 revision 전체 파일 목록·크기·원격 LFS SHA-256/Git blob 대조.
- [x] 어댑터 설정·tensor shape/dtype/parameter 수 확인 및 tokenizer/config JSON 열람.
- [x] 모델 카드·학습 예시·저장 설정의 일치/차이와 미확인 성능/라이선스를 근거와 함께 보고.
- [x] manifest·보고·매뉴얼·색인·STATUS에 보관 위치 및 범위 연결.

## 진행·중단

- 2026-10-19 — 승인 범위 등록. 원격 파일·card·adapter 설정과 스크립트를 확인했다.
- INDEX 공통 기준 적용. 다운로드 실패는 동일 revision으로 이어받고 정체성 불일치는 보고한다.

## 결과·증거

원본11파일·92,248,228 bytes의 전체 원격 크기·해시 대조 및 safetensors 헤더/shape/offset·rank 검증을 통과했다.
FP32 tensor392개·20,185,088 parameter를 확인했고 training_args를 pickle 실행 없이 정적으로 열람했다.
[정보 보고](../evidence/ep171/report.md)에 저장 설정·학습 예시 간 차이, 라이선스·성능·기반 revision의 미확인 범위를 명시했다.
매뉴얼·INDEX·STATUS에 연결하고 신규 링크·수치·문서 공백 검사를 수행했다. 실제 모델 추론·학습·배틀은 없다.
