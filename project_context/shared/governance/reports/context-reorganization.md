# EP-185 — 연구 목적 중심 문서 재구성 결과

## 기준선과 범위

개편 전에 코드·문서·작은 입력 460개 파일을
`feda62f733c1b470364868262c789ec857ef67f5`로 커밋했다.
`model-train/research/model-training`의 원격 SHA가 같은 값임을 확인한 뒤 재구성을 시작했다.
수집 원문·가공 데이터·검증 산출물은 기준선 커밋에서 제외하고 로컬에 보존했다.

승인과 새 정책은 [D-170](../decisions/D-170-purpose-based-context.md),
작업은 [EP-185](../plans/EP-185-purpose-based-context.md)가 소유한다.
문서 이동과 실행기의 문서 조회·동결 연결만 변경했다.
새 학습·배틀·API·GPU 실행, 다른 연구선 checkout 변경은 수행하지 않았다.

## 최종 구조

- 기존 결정169개·계획184개·실험113개, 총466개 기록을 목적별 원문으로 배치했다.
  이번 D-170·EP-185를 포함한 등록 원문은468개다.
- 연구 질문9개 폴더와 공통 기반4개 폴더에 질문·읽기 경로·연구 흐름을 작성했다.
  D·EP·EX는 각 주제의 decisions/plans/experiments에 두며 상태 변경으로 이동하지 않는다.
- 중앙 규범265개 절을 공통 문서와36개 주제별 DESIGN/CONTRACTS/ARCHITECTURE로 분리했다.
  각 절의 내용과 당시 적용 범위를 보존하고 개편 전 중앙 서문은 보존 안내로 명시했다.
- 등록부에서 원문 위치·방법·모델·자료·관계를 관리하고20개 탐색 페이지를 생성한다.
  제목·상태는 원문에서 읽는다. 학습 실행과 학습 모델의 배틀 평가는 방법 분류에서도 구분했다.
- STATUS를597행에서38행 수준으로 축약하고 환경·명령 경계와 자료 안내를 공통 기반으로 분리했다.
  현재 목표·작업·제약은 STATUS, 상세 이력·수치는 개별 기록에 둔다.

[전체 연구 목록](../../../research/INDEX.md) · [공통 기반](../../../shared/INDEX.md) ·
[탐색·등록 안내](../../../catalog/INDEX.md) · [ID 및 절 이전 대응](../../../catalog/records.json)

## 경로와 동결

기존 보고서용 이전 경로와 앵커에는 원문 안내를 남겼다. 연결 문서를 원문으로 중복 집계하지 않는다.
원래 존재한474개 경로(호환 링크6개 포함)만 유지하며, 사용된 적 없는 상태별 경로를 새로 만들지 않는다.
실행기의 고정 위치와 디렉터리 전체 검색은 등록 ID 조회로 교체했다.
EP-132를 이전 active 위치에서 찾던 문제도 같은 방식으로 교정했다.

분산된 규범이 동결에서 누락되지 않도록 protocol 복사와 source-list 방식의 준비 경로를 조정했다.
새 protocol/context는 참조 규범·기록의 snapshot이며 `selected_documents`로
해당 실행에서 선택한 문서와 구분한다. 참조 기록 복사는 추가 실행 승인이 아니다.
과거 실행 패키지의 사본을 현재 원문으로 다시 해석하거나 갱신하지 않는다.
새 ID 조회 모듈2개 파일을 배틀·planner·학습 실행기의 소스 동결/검증 목록에 포함했다.
색인 생성기 변경이나 분류 태그 변경은 이 런타임 코드 목록에 추가하지 않는다.

## 검증

| 항목 | 결과·범위 |
|---|---|
| 기록 내용 | 기존466개 원문의 전체 본문을 대조했다. 이동에 따른 Markdown 링크 목적지를 제외한 변경0 |
| 규범 절 | 이전265개 절을 대상으로 링크 목적지·앵커와 공백을 정규화한 본문 포함 대조, 누락0 |
| 링크 | 현재 문서·생성 색인·이전 경로·매뉴얼·관련 README의 파일/앵커 오류0. 기존 C-007 앵커 오류4건도 호환 앵커로 해소 |
| 등록·생성 | ID·원문 경로·관계 대상·authority 파일과20개 생성 페이지의 동기화 확인 |
| CPU 회귀 | 등록부·planner 설정·cohort 동결·학습 계승 freeze·Kev 경계 관련124검사 통과 |
| 최종 보완 검사 | 조회 코드 동결 보완 후 등록부·planner·selfplay43검사 통과. 앞 회귀와 중복되므로 합산 검사 수로 보고하지 않음 |
| 기존 증거 |117,649개 기존 파일의 크기·mtime·symlink 대상 변경0. 과거 내용 전체의 새 hash 인증은 아님 |
| 진행 중 학습 | EP-184 source identity 대상12개 파일을 기준선과 바이트 대조, 변경0 |
| Python·diff | 변경 Python의 구문 검사와 추적 변경분의 whitespace 검사 통과 |

CPU 회귀에서 기존 third-party Pydantic deprecation warning1건이 있었으며 기능 실패는 없었다.
최초 검증에서 이전 폴더를 가정한 테스트와 임시 registry가 없는 fixture를 발견했다.
새 경로에서 해당 cohort의 승인 문서가 선택되는지, 분산 계약이 복사 중 바뀌면 기존대로
동결을 거부하고 최초 시계를 보존하는지 검사하도록 교정했다.
Superseded 상태 안의 상대 링크도 생성 페이지 위치에 맞게 변환하고 회귀를 추가했다.

원자료:
[문서 대조](../../../exec-plans/evidence/ep185/document-validation.json) ·
[이동 대응](../../../exec-plans/evidence/ep185/record-moves.json) ·
[규범 절 대응](../../../exec-plans/evidence/ep185/section-moves.json) ·
[보존 확인](../../../exec-plans/evidence/ep185/preservation-check.json) ·
[CPU 회귀](../../../exec-plans/evidence/ep185/tests.log) ·
[최종 보완 검사](../../../exec-plans/evidence/ep185/tests-final.log)

## 이후 갱신

원문·등록부를 편집하고 `scripts/context-catalog build`와 `check`를 실행한다.
원문 위치는 `scripts/context-catalog resolve EX-113`처럼 ID로 조회한다.
새 정책 변경은 공통/주제별 편집 원문과 ADR에 명시하며, 이력 탐색 분류만으로 연구 의미를 바꾸지 않는다.

이번 원격 push는 개편 전 기준선이다. 개편 변경분은 해당 기준선 이후의 작업 트리에 남겨 검토할 수 있다.
