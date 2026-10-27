# EP-107 — Abyssal 80경기 공동 q 데이터

- 상태: Completed
- 생성일: 2026-09-29
- 책임자: Codex
- 승인: 현재 대화의 EX-065 계획 구현·검증·80경기 수집 지시 / D-103
- 후속 승인: 현재 사용자 제공 「EX-065 학습 데이터 복사」 계획의 구현·검증 지시
- 원문: [EX-065](../experiments/EX-065-joint-q-data.md), [C-051](../CONTRACTS.md#c-051-joint-q)

## 목표와 범위

`integration/pokechamp/joint_q/`에 다경기 원재현·snapshot 검증·재개 가능한 분기 수집,
공동 입력 serializer·로더·감사·보고를 구현한다. 동결 소스/설정/데이터/
private 감사는 `.pokechamp-data/experiments/ex065-joint-q/`에 보존한다.
INDEX/CHARTER·RD·계약·상태·색인과 겹치는 active EP-103/062/064/075/077/080/057/054를
확인했다. 과거 중단 실험 재개·기존 봉인 변경·본학습·모델 추론·GPU·외부 API는 범위 밖이다.
조건·분모·gate·복구는 EX-065가 소유한다. 기본 IO 설명 평가 해당 없음.

후속 범위는 완료된 `versions/collection-v5`의 학습 JSONL 4개와 manifest·토큰 통계·
결과 보고·로더/입력/완료 검증 기록을
`/mnt/digicap/combined/hyna/backup/pokechamp/`에 직접 복사하는 것이다.
복사본 전용 SHA-256 목록과 검증 기록을 생성한다. 대용량 private rollout 원자료와 전체
artifact manifest/봉인 목록은 원래 위치에 보존한다. 새 수집·학습·연구 방법 변경은 포함하지 않는다.

## 완료 기준

- [x] 고정 팀/합법성/그룹/80개 실제 seed와 정책·계산기·serializer provenance 동결
- [x] 공동 입력/학습 레코드 타입 분리·가변 후보 로더·회귀/격리/중단·재개 검사
- [x] 10경기 파일럿 전수 재현/분기 감사·16/32/48 처리량과 자원 검증
- [x] 승인된 50/10/20경기·전 관측/후보×32 완료 또는 사유 있는 미완료 원장
- [x] 독립 전수 감사·분포/비용/한계 보고 (뷰어는 사용자 후속 지시로 생략)
- [x] 과거 봉인 보존·새 산출물 봉인·소유 자원 정리·상태 동기화
- [x] 지정 폴더 복사·파일 크기/SHA-256 일치·2,668관측/24,474후보·입력/타깃 ID 대조

## 진행과 검증

- 2026-09-29 — 사용자 계획을 등록했다. EX-060의 고정22관측/167후보·300추가턴 제한과
  EX-064 사후 unknown 보정 경계를 확인했다. 새 수집 전.
- 2026-09-30 — 복사 후속 작업에서 INDEX/CHARTER·STATUS·plan 색인·EP-107·EX-065·
  C-051·ARCHITECTURE·D-103과 완료/봉인 원문을 다시 확인했다. 완료된 collection-v5의
  16개 파일을 선별했으며 대상 폴더의 빈 상태·쓰기 가능 권한·여유 공간을 확인했다.
  원본 finalizer의 `all-artifacts-verified` 및 완료 기록은 수집/봉인 완료를 나타내며,
  기존 문서의 수집 중 표시는 최종 복사 검증 후 근거와 함께 동기화한다.

## 중단과 복구

[INDEX](../../../INDEX.md#workflow)·RD11.1/C-018 및 EX-065 적용. 공유 무결성 결함은 의존 수집
중지, 증거 보존·독립 회귀 후 영향 관측 전체 후보×32를 새 버전에서 1회 재수집한다.
기술 실패는 같은 논리 rollout·같은 RNG로 최대3시도, 실패를 결과에 합산하지 않는다.
완료되지 않은 분모를 Completed로 보고하지 않는다.

- 2026-09-29 — 사용자 후속 지시로 EX-065 뷰어 생성/검증/링크 완료 기준을 제외했다.

- 뷰어 생략 후 공동 입력/로더·트랜잭션 원장·원/분기 checkpoint·static blob 중복 저장 제거를 구현했다.
  기존 관련75검사 및 후속 codec 포함10검사를 통과했다. 최초 codec fixture가 대기 actor를
  선택하도록 잘못 구성된 오류와 저장량 검증에서 발견한 중복 lookup을 보존/교정했다.
- 최초 파일럿 원경기는 첫 경계 signature에서 nonterminal `winner` 생략으로 실패했다.
  관측/후보/분기0, seed 교체0. source `13b7ff70…`와 실패를 보존하고 경계 회귀 후 새 source에서
  같은 원경기를 실행한다. 실제 타깃 재수집 한도는 사용하지 않았다.

- 파일럿 원경기10개·315관측·2,975후보의 원경기 전체 재현과 모든 root 복원/다음 경계 대조를
  통과했다. Keldeo-Resolute 초기 자기 요청의 canonical species 별칭을 EX-065 어댑터에서
  교정했으며 원 simulator/정책은 수정하지 않았다. 실패 seed 대체0이다.
- CPU 회귀80개, 동일96개 작업의16/32/48 worker·역순 실행 불변성, 실제61결정 rollout의
  20번째 checkpoint 직후 SIGKILL·동일 RNG 재개 trace 대조를 통과했다.
- 정적 lookup 재복원 비용을 줄이는 불변 캐시를 적용해 `versions/collection-v5`를 현재 실행
  디렉터리로 동결했다(source `ebd917a4…`). 이전1,024개 타깃은 별도 보존하고 영향3관측의
  전체 후보×32를 새 버전에서 재수집한다. 합산/재사용0, 새1,024개 전부 결과/trace 동치다.
  교정 전후 기록은 데이터 루트의 `source-recovery-v5.json`, `current-run.json`이 소유한다.
- 새1,024개는16 worker에서34.80초(29.43/s), 오류0이었다. 1,024개 공통 작업으로16/32/48
  추가 처리량 비교 후 파일럿95,200개를 완성한다. 원장 전수 감사와 gate 통과 전 나머지70경기를
  생성하지 않는다. 첫315개 입력은10,091–22,911토큰,98개가16,384초과이며 절단0이다.
- EX-060/061/063/064의 기존 checksums 검사를 모두 통과했다. 뷰어 생성0을 유지한다.
- 파일럿 gate 통과:10경기315관측·2,975후보·95,200유효 rollout, 미완료/중복/split 충돌0.
  W47,505/D0/L47,695이며 q를 정책 성능 비교로 해석하지 않는다. 저장 전후/commit 후 실제
  SIGKILL 검사와23개 장기전 경고/1000턴 자동 무승부 fixture도 통과했다(타깃 분모 제외).
  `pilot-complete/`에 입력/타깃/토큰/감사/gate를 별도 봉인 보존하고,16 worker 설정으로
  나머지 train40+validation10의 원경기 생성/재현에 진입했다. test 생성 전 동결은 유지한다.
- train50+validation10 원경기/모든 snapshot 검증 완료:60경기1,959관측·18,105후보,
  예정579,360분기(파일럿95,200 포함)다. 새 공동 입력 생성 후 남은484,160개 분기를 수집한다.
- train50+validation10의579,360분기와 전수 감사 완료. 미완료/기술 오류/split 충돌0,
  같은 split 의미 중복56관측을 기록했다. 입력 토큰10,091–29,525,16,384초과512관측·절단0.
  `development-complete/`와 `pretest-gate.json`에 감사/동결을 보존하고 test20 원경기 생성에
  진입했다. test 결과를 프롬프트/설정 선택에 사용하지 않는다.
- 승인80경기(50/10/20)와 모든 snapshot 검증 완료. 실제2,668관측·24,474후보·예정783,168분기다.
  train1,639관측/15,114후보, validation320/2,991, test709/6,369다. test203,808분기를
  동일 source/serializer/worker 설정으로 수집 중이다.

## 최종 완료와 학습 자료 복사

- 2026-09-30 — 원본 controller의 `all-data-verified`와 finalizer의
  `all-artifacts-verified` 성공 및
  [완료 기록](../../../../.pokechamp-data/experiments/ex065-joint-q/completion-verification.json)을
  확인했다. 실제80경기(50/10/20)의2,668관측·24,474후보·783,168유효 분기가 모두 완성됐다.
  미완료/중복 논리 결과/split 충돌0, 같은 split 의미 중복71관측이다. 분포·시간·용량·
  한계는 [동결 최종 보고](../../../../.pokechamp-data/experiments/ex065-joint-q/versions/collection-v5/final/report.md)가 소유한다.
  기존 EX-060/061/063/064 및 새 전체 봉인 검사 성공 기록을 확인했다. controller/finalizer
  프로세스는 종료됐고 이번 후속 작업의 새 수집·학습·모델 호출·GPU/API·뷰어 생성0이다.
- 원본 봉인 목록과 선택 파일을 대조한 뒤 학습 JSONL4개·manifest·토큰·최종 보고/감사·
  로더/입력/완료 검증 등16개 파일(555,924,721bytes)을 지정 폴더에 직접 복사했다.
  `audit.json`·`report.json`·`report.md`는 원본 `final/` 봉인본을 사용한다.
  private rollout 원자료·전체 artifact manifest·기존 체크섬은 원위치에 보존했다.
- 최초 추가 검증 코드는 입력 해시를 JSON 문자열로 계산해 실패했다. 원본 pipeline의
  `digest(value.payload)`를 대조해 검증 코드만 교정했고 이미 복사한 자료를 수정/재복사하지
  않았다. [실패 근거](../../../exec-plans/evidence/ep107/copy-training-first-attempt.json)를 보존한다.
- 교정 후 원본/복사본16개 파일의 크기/SHA-256,2,668개 입력/타깃/렌더링/토큰 ID와
  24,474개 후보 ID·순서·q/WDL/후보별 export 동치를 전수 대조했다. 공개 로더도 전체
  자료를 통과했다. 기존 입력 격리 기록315관측의 적용 범위는 그대로 보존했다.
  [복사 검증](../../../exec-plans/evidence/ep107/copy-training-verification.json) ·
  [실행 코드](../../../exec-plans/evidence/ep107/copy_training_data.py).
- 복사본 전용 `copy-verification.json`·`checksums.sha256`를 생성하고
  `sha256sum --check checksums.sha256`의17항목/exit0을 확인했다.
  최종 폴더는18개 파일·555,933,831bytes(530.18MiB)다.
  [최종 용량·체크섬·종료 확인](../../../exec-plans/evidence/ep107/copy-training-closure.json).
  계획/실험/색인/STATUS를 실제 완료 기록과 동기화하고 Completed로 전환했다.
