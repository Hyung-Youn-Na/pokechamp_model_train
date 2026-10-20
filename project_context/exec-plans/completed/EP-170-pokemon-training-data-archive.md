# EP-170 — pokemon-training-data 원본 보관

- 상태: Completed
- 생성일: 2026-10-19
- 책임자: Codex
- 승인: 현재 사용자의 `milkkarten/pokemon-training-data` 다운로드 지시.
- 기준/실제 연구선: `research/model-training`, `/workspace`, 시작 commit `a4659bf298c7935714f9fbd25246db2d831c5926`; 기존 미커밋 변경 보존.
- 실행기: `/workspace/pokechamp/.venv/bin/hf`, `/workspace/pokechamp/.venv/bin/python`
- 관련 원문: [INDEX](../../INDEX.md#workflow), [매뉴얼](../../RESEARCH_MANUAL.md#archived-datasets), [보존 안내](../../RESEARCH_WORKFLOW.md#preservation)
- 원자료: https://huggingface.co/datasets/milkkarten/pokemon-training-data
- 고정 revision: `4bdd862f098852498ed0c696a2bbc4d64e43801e` (현재 Hub HEAD 조회 결과)
- 새 보관 위치: `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokemon-training-data/`
- 새 검증 기록: 위 폴더의 `manifest.json`, [실행 스크립트](../evidence/ep170/archive.py).

## 범위·불변 조건

원본 .gitattributes·stage1a/stage_1a.jsonl·stage2a/stage_2a_reasoning.jsonl·
stage2b/counterfactual_actions.jsonl 4개(131,243,573,620 bytes)를 원구조로 보관한다.
README·라이선스 선언·dataset card는 없으며 다른 자료의 설명·라이선스를 승계하지 않는다.
기존 보관본·snapshot·manifest·환경·실험 자료는 수정하지 않는다.
active plan 색인 및 EP-169를 확인했다. EP-169의 generated/showdown-ruleqa/v1 생성과 별도
자료·쓰기 위치이며 그 구현/실행 범위를 변경하지 않는다. 공유 색인·STATUS·매뉴얼은 최신 본문에
본 항목만 추가한다. 전처리·학습·배틀·새 EX/뷰어·실험 시계는 해당 없다.

## 완료 기준·검증

- [x] 고정 revision 전체4파일 다운로드 및 Hub 목록·크기·LFS SHA-256/Git blob 대조.
- [x] JSONL 파일별 전체 물리 행 수 집계, 첫32행 JSON 구문·필드 구조 확인.
- [x] 출처·revision·시각·라이선스 선언 유무·파일 목록·검증 범위를 manifest에 기록.
- [x] 매뉴얼·plan·색인·STATUS에 위치 연결 및 사용자에게 용량·행 수 보고.

## 진행·중단

- 2026-10-19 — 승인 범위 등록. 저장 여유5.1TiB 확인. 원본에 정답 행 수 통계는 없어 실측값으로 기록한다.
- INDEX 공통 기준 적용. 다운로드 실패는 같은 revision으로 이어받고 검증 불일치는 기록·보고한다.

## 결과·증거

원본4개 파일 **131,243,573,620 bytes (약131.24 GB)** 보관 완료.
[보관 폴더](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokemon-training-data/) · [manifest](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokemon-training-data/manifest.json).

- 원격 파일 목록·크기·LFS SHA-256/Git blob ID 전부 일치.
- JSONL 실측 물리 행 수: stage1a 123,740,223 / stage2a 500,000 / stage2b 1,000,000,
  합계125,240,223행. 원본에 정답 행 수 통계는 없다.
- 각 파일 첫32행 Python json 디코딩·필드 구조를 기록했다.
- [비표준 상수 확인](../evidence/ep170/check_json_constants.py): stage1a/stage2a 첫32행은
  표준 JSON 상수 검사 통과. stage2b 첫32행은 모두 rating: NaN을 포함하여 strict JSON은
  통과하지 못한다. 원본 보관 작업이므로 bytes는 보존하고 이 제한을 manifest·매뉴얼에 명시했다.
  최종 verification 상태는 passed_with_source_format_note다.
- 다운로드 시작 `2026-10-19T02:41:51.953595+00:00`, 완료 `2026-10-19T03:09:07.869528+00:00`,
  해시/행 수 검증 `2026-10-19T03:23:48.083743+00:00`.
- 매뉴얼6.3절·색인·STATUS에 연결했다. 링크·수치·상태 및 변경 문서 공백 검사를 수행했다.
- 기존 자료·환경·다른 실행 작업은 변경하지 않았다. 전처리·학습과 전체 JSON 의미 검사는 없다.
