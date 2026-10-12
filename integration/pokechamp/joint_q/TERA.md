# EX-067 Abyssal Tera 보완 데이터

[EX-067](../../../project_context/experiments/EX-067-abyssal-tera-joint-q.md)의 고정
`abyssal-tera-v1`·새80경기·전체 후보32분기를 CPU에서 수집한다. 분기16 worker,
원경기4·입력8·native thread1이며 메모리/디스크24GiB 여유를 유지한다.
정책 구현은 `../abyssal_tera.py`, ID/seed는 `tera_config.py`에 있다.
기존 EX-066 학습의 source·입력·환경을 변경하지 않는다.

```bash
scripts/pokechamp-joint-q-tera prepare
scripts/pokechamp-joint-q-tera freeze
scripts/pokechamp-joint-q-tera run
```

`run`은 필수 CPU 검사 → train10 원경기/입력/등록 → worker1/16 역순 대조·실제 checkpoint
중단/재개 → 분기 수집·전수 감사·파일럿 gate → 나머지 train40/validation10 → test20 →
뷰어·폴더 이동 후 오프라인 Chromium 전수 확인·봉인·복사 검증 순서다. test는 rest gate 전 생성할 수 없다. 설정/정책은 파일럿 전에
동결하며 실패나 성적을 보고 변경하지 않는다. 원자료 기본 경로는
`.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/`, 감독 상태/로그는 별도
`.pokechamp-data/jobs/ex067-abyssal-tera-joint-q/`다.

단계별 실행은 `capture/inputs/register --cohort pilot|rest|test`, `collect`, `export`,
`tokens`, `audit`, `report --cohort ...`, `gate --cohort ...`를 제공한다.
`preflight`, `benchmark`, `recovery-probe`, `verification`은 명시적 검증 receipt를 보존한다.
정상 종료 자료는 `viewer`, `browser`, `seal-copy`로 종결한다. 감독 `run` 재호출은 같은 source와
완료 stage 기록에서 이어간다. 일시 전송 오류만 같은 seed/checkpoint에서 최대3시도한다.
자원 중지는 자원이 회복된 뒤 `resume-resources`로 기록하고 재개한다.
기술 결함은 영향 범위를 보존하고 EX-067의 독립 검증·별도 버전 복구 절차를 적용한다.
STOP 삭제나 원자료 덮어쓰기로 source/검증 gate를 우회하지 않는다.

첫 파일럿의 기절 후 Tera 소모 누락은 `tera_inputs.py`의 공개 이력 기반
`state.terastallization_used.{self,opponent}`와 현재 개체 표시의 설명으로 교정한다.
정책·seed·JointInput class/schema·공개 로더는 유지한다. 등록된 교정은 다음 별도 디렉터리만
허용하며 원 STOP/소스/90,720분기를 보존하고 독립314관측 대조·원자료 봉인 receipt를 요구한다.

```bash
scripts/pokechamp-joint-q-tera prepare-recovery --directory /workspace/.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2
scripts/pokechamp-joint-q-tera freeze --directory /workspace/.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2
scripts/pokechamp-joint-q-tera run --directory /workspace/.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2
```

파일럿10경기를 같은 seed로1회 재수집하고 이후 cohort로 진행한다. 최초 시계와 이전 물리
시도를 이월하되 원 파일럿은 최종 학습 자료의 유효 분모에 포함하지 않는다.

원경기/후속 actor와 snapshot은 policy ID·설정 hash를 함께 가진다. 첫 평가 후보는 강제하고
그 전에 p2 후속 정책을 호출하지 않는다. 정책의 판단 사유·private 원자료는 학습 입력 밖이다.
기존 `JointInput` schema와 `data.load`는 유지하며 공통 instructions에 새 q의 후속 정책을
설명하는 전역 문장만 추가한다. 관측별 사유나 실제 상대 세트는 추가하지 않는다.
모든 타깃은 `(W+0.5D)/32`이고 후보 하나라도 미완료이면 관측 전체 미완료다.

최종 `final/report.md`는 실제 분모·양측 Tera 사용·전후 관측·실패·토큰·시간/용량을 연결한다.
`exports/battle_viewers/ex067/index.html`에는 원경기와 관측별 후보 q를 제공한다.
학습 파일은 기존 백업 위치의 `ex067-abyssal-tera-joint-q/`에 SHA-256·로더를 대조하여 복사한다.
새 q는 새 후속 정책에 조건부이며 현재 학습에 자동 병합하거나 성능 향상을 주장하지 않는다.
