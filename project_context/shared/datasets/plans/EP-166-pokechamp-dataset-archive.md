# EP-166 — milkkarten/pokechamp 원본 보관

- 상태: Completed
- 생성일: 2026-10-18
- 책임자: Codex
- 승인 근거·범위: 사용자의 `milkkarten/pokechamp`도 같은 위치에 다운로드하라는 현재 지시.
- 관련 원문: [INDEX](../../../INDEX.md#workflow), [C-007](../../../CONTRACTS.md#c-007-distribution-및-provenance-경계), [연구 매뉴얼](../../../RESEARCH_MANUAL.md), [보존 안내](../../../RESEARCH_WORKFLOW.md#preservation)
- 기준/실제 branch: `research/model-training`; 시작 commit `a4659bf298c7935714f9fbd25246db2d831c5926`, 기존 미커밋 변경 보존.
- checkout·실행기: `/workspace`; `/workspace/pokechamp/.venv/bin/hf`, `/workspace/pokechamp/.venv/bin/python`
- 원자료: https://huggingface.co/datasets/milkkarten/pokechamp
- 고정 revision: `b5820ff5d0c8d5e5cec692d55f756b6e5a66a203` (현재 Hub HEAD 조회 결과)
- 새 보관/manifest 위치: `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp/`
- 검증 실행 기록: [archive.py](../../../exec-plans/evidence/ep166/archive.py)

## 목표·범위·불변 조건

README·.gitattributes·resource/method.png·train 37개/test 5개 Parquet를 원래 구조로 다운로드한다.
출처·revision·시각·원문 라이선스 선언 유무·파일 목록과 검증 결과를 manifest에 기록한다.
색인과 active plan의 범위를 확인했고 같은 데이터셋 보관과 겹치는 plan은 없다.
EP-165의 보관본과 기존 snapshot·보존 manifest·실험 자료·실행 환경은 수정하지 않는다.
전처리·분할 변경·학습·모델 호출·배틀·새 실험은 범위 밖이며 EX/뷰어/실험 시계는 해당 없다.

## 완료 기준·검증

- [x] 고정 revision 45개 원본 파일 다운로드, Hub 목록·크기·LFS SHA-256/작은 파일 Git blob ID 대조.
- [x] Parquet 42개를 열어 schema·분할별 metadata 행 수를 원문과 대조하고 각 파일 첫 batch를 읽는다.
- [x] 출처·revision·다운로드 시각·라이선스 선언 유무·검증 결과를 manifest에 기록.
- [x] plan·색인·STATUS에 보관 위치를 연결하고 사용자에게 경로·용량·행 수를 보고.

## 진행·중단

- 2026-10-18 — 승인 범위 등록. Hub API에서 45개 파일·5,566,414,178 bytes·train 1,916,868행/test 213,356행을 확인했다.
- INDEX 공통 기준을 따른다. 다운로드 실패는 같은 revision으로 이어받을 수 있으며 원본 정체성 충돌·검증 불일치는 기록하고 완료로 처리하지 않는다.

## 결과 및 증거

원본 **45개 파일·5,566,414,178 bytes (약 5.57 GB)**를 보관했다.
[보관 폴더](../../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp) · [manifest](../../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp/manifest.json).

- 원격 목록·크기·LFS SHA-256/작은 파일 Git blob ID는 모두 일치했다.
- train 37개 파일 **1,916,868행**, test 5개 파일 **213,356행**, 합계 **2,130,224행**.
  행 수는 Parquet footer metadata로 집계하여 README와 대조했다.
- Parquet 42개 모두 text/month_year/gamemode/elo/battle_id 문자열 schema가 원문과 일치했다.
  각 파일 첫32행을 디코딩했다. 전체 행의 내용 정확성 검사는 수행하지 않았다.
- README front matter와 본문에 라이선스 선언은 없었으며 manifest의 declared_license는 null이다.
- 다운로드 시작 `2026-10-18T23:47:22.517890+00:00`, 완료 `2026-10-18T23:47:31.045921+00:00`,
  검증 `2026-10-18T23:47:37.576689+00:00`.
- [실행·검증 스크립트](../../../exec-plans/evidence/ep166/archive.py)를 pokechamp 기존 Python으로 실행했다.
  기존 manifest가 있으면 덮어쓰지 않는다. hf 전송 metadata는 원본 용량에서 제외했다.
- 승인된 원본 보관 기준을 충족했다. 기존 보관본·snapshot·보존 manifest·실험 자료·환경은
  변경하지 않았고 전처리·분할 변경·학습은 수행하지 않았다.
