# EP-168 — pokechamp-pretrain-data 원본 보관

- 상태: Completed
- 생성일: 2026-10-19
- 책임자: Codex
- 승인: 현재 사용자의 `milkkarten/pokechamp-pretrain-data` 동일 방식 다운로드 지시.
- 기준/실제 연구선: `research/model-training`, `/workspace`, 시작 commit `a4659bf298c7935714f9fbd25246db2d831c5926`; 기존 미커밋 변경 보존.
- 실행기: `/workspace/pokechamp/.venv/bin/hf`, `/workspace/pokechamp/.venv/bin/python`
- 관련 원문: [INDEX](../../INDEX.md#workflow), [매뉴얼](../../RESEARCH_MANUAL.md#archived-datasets), [C-007](../../CONTRACTS.md#c-007-distribution-및-provenance-경계), [보존 안내](../../RESEARCH_WORKFLOW.md#preservation)
- 원자료: https://huggingface.co/datasets/milkkarten/pokechamp-pretrain-data
- 고정 revision: `be424eb903daf07deb57a579f48be319c02d6224` (Hub HEAD 조회 결과)
- 새 보관 위치: `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp-pretrain-data/`
- 새 검증 기록: 위 폴더의 `manifest.json`, [실행 스크립트](../evidence/ep168/archive.py).

## 범위·불변 조건

원본 .gitattributes·stage_1a.jsonl·stage_1a_stats.json 3개(63,051,202,721 bytes)를 원구조로 보관한다.
Hub에 README·라이선스 파일·dataset card가 없으므로 다른 자료의 설명·라이선스를 승계하지 않는다.
기존 EP-165/166 보관본·snapshot·manifest·환경·실험 자료는 수정하지 않는다.
active plan 색인과 범위를 확인했으며 이 데이터셋 보관과 겹치는 작업은 없다.
전처리·분할 변경·학습·배틀은 범위 밖이며 EX/뷰어·실험 시계는 해당 없다.

## 완료 기준·검증

- [x] 고정 revision 전체3파일 다운로드 및 Hub 파일 목록·크기·LFS SHA-256/Git blob 대조.
- [x] JSONL 전체 행 수를 원본 stats의 total_samples와 대조하고 첫32행 JSON 구문·구조 확인.
- [x] 출처·revision·시각·라이선스 선언 유무·파일 목록·검증 범위를 manifest에 기록.
- [x] 매뉴얼·plan·색인·STATUS에 위치 연결 및 사용자에게 용량·행 수 보고.

## 진행·중단

- 2026-10-19 — 승인 범위 등록. stats의 total_samples는121,960,458이며 실제 행 수는 다운로드 후 대조한다.
- INDEX 공통 기준 적용. 다운로드 실패는 같은 revision으로 이어받고 정체성·검증 불일치는 기록·보고한다.

## 결과·증거

원본3개 파일 **63,051,202,721 bytes (약63.05 GB / 58.72 GiB)** 보관 완료.
[보관 폴더](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp-pretrain-data/) · [manifest](/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp-pretrain-data/manifest.json).

- 전체 파일 목록·크기·LFS SHA-256/Git blob ID 일치.
- `stage_1a.jsonl` **121,960,458행**, 원본 stats의 total_samples와 일치.
- 첫32행 JSON 디코딩 통과. 표본 필드는 prompt/response/opponent_action(str),
  reward(float), done(bool), turn(int), format(str)이며32행 구조가 동일하다.
- 전체 행 JSON 구문·내용의 정확성은 검증하지 않았다. 원본 README·라이선스 선언·분할 설명은 없다.
- 다운로드 시작 `2026-10-19T01:45:25.347617+00:00`, 완료 `2026-10-19T01:58:36.743340+00:00`,
  검증 `2026-10-19T02:02:41.534251+00:00`.
- 매뉴얼6.2절·색인·STATUS에 보관 위치를 연결했다. 새 링크·수치·문서 공백 검사를 수행했다.
  기존 보관본·snapshot·환경·실험 자료 변경과 전처리·학습 실행은 없다.
