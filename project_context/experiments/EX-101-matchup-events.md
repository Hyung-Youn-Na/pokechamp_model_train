# EX-101 — 매치업 변화 기반 GLM 계획 갱신

- 상태: Completed
- 생성일: 2026-10-15
- 승인: 현재 사용자 구현·검증·실행 지시 / [D-154](../decisions/D-154-matchup-events.md)
- 계획: [EP-160](../exec-plans/completed/EP-160-matchup-events.md)
- branch/checkout: research/model-training /workspace a4659bf·기존 미커밋 변경 보존

## 질문·처치·고정 조건

EX-100 대비 호출 정책만 바꾼 새 실제1경기에서 호출 빈도·계획 유지기간·지연·토큰·행동·결과를
관찰한다. 단일 궤적 비교로 일반 성능이나 인과효과를 주장하지 않는다.
`trigger.policy: events`, `trigger.events: [faint, tera, forced_switch, active_change, form_change]`.
interval_turns:3은 형식에 남지만 사용하지 않는다. 최초 다후보 선봉 계획을 유지한다.
교체는 양측 switch/drag/replace 공개행(첫등장·피벗·밀어내기·기절후·Illusion 해제 포함),
폼은 현재 출전 대상 detailschange/-formechange/-transform 공개행이다. 벤치는 제외한다.
공개행 좌표별 중복 제거로 잠시 바뀌었다 돌아온 조합도 보존하고 다음 다후보 결정에서 호출한다.
단일후보는 두모델 무호출/사건보류, 겹친 사건은 모든 사유를 기록한 한 호출이다.
강제교체 선택 전과 교체 후 새 대면에서 각각 호출할 수 있다. 모델 입력 구조는 불변이다.

식별자/출력과 위 trigger 외에는 [EX-100](EX-100-glm53-low-sample.md)의 동결 설정·팀·대진·seed·
JEV revision/37파일·환경·프롬프트·피해계산·후보·응답복구/HTTP 정책을 그대로 참조 편입한다.
GLM-5.3/thinking enabled/low/temperature0/top_p0.95/max_tokens131072·경기/전체시간null.
JEV autotrust/JEV-35B-NVFP4 revision10c2c62610e315e31a75baca849ad79d526e4658,
GPU0 Marlin TP1·동시1·기존 메모리 한도, actor pokechamp/.venv/bin/python,
model .pokechamp-data/jev35b-nvfp4-runtime/.venv/bin/python. 환경 재설치 없음.

## 한도·중단·복구

GLM 물리HTTP128·JEV논리256(사전8포함)·경기1·GPUallocator40GiB/전체44GiB·소유host32GiB·
disk null/사용량 기록·포트18845/18846/8109 점유시 미진입. 별도 유료GLM probe0.
CPU·동결 검증 후 새 단일서버 사전8추론을 통과하면 같은 서버로 본1경기를 진행한다.
RD11.1/C-018·RD11.2/C-046·C-070/073 및 EX-100의 격리/복구를 적용한다.
도구결함은 원본보존·영향분석·독립검증 후 처리하며 재수집/재경기/보충/자동재개0.
수집source/조건은 불변, 최초시계/누적호출을 초기화하지 않고 모델/endpoint/인증을 대체하지 않는다.
실패는 부분기록/사유/봉인/자원정리를 완료하고 정상1경기 미달을 보고한다.
전수 전략/설명 정확성 검토는 RD8.1/C-032에 따라 기본 제외한다.

## 검증·출력·완료

양측교체/폼/테라/기절/강제교체·중복·같은턴 여러request·단일후보보류·cutoff·경기격리·
사건없이3턴이상 재호출없음을 CPU검사한다. EX-100 저장궤적 무호출 재생과 독립 공개행 대조의
예상 호출대상은28결정이다. 이는 실제 EX-101 호출수 예측이 아니다.
EX-100 설정차이가 trigger뿐임을 대조하고 source/조건을 동결한다.
모든 호출/미호출 사유를 공개행과 전수대조하고 원문/재시도/usage·선택→명령·자원을 감사한다.
EX-100과 기술·행동 비교, 정상1경기, 이동후 오프라인 뷰어/복사/다운로드, 봉인·반환까지 완료한다.
불변 JEV/환경 검증은 EP-154/158/159 source 일치 범위만 재사용한다.

run: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-101
증거: project_context/exec-plans/evidence/ep160
viewer: exports/battle_viewers/ex101/index.html
condition: glm53-jev35b-nvfp4-matchup-events

## 결과

정상1/1·실패0·player_won·종료82턴.
[최종 보고](../exec-plans/evidence/ep160/report.md)에 모든 검증과 비교를 연결했다.
