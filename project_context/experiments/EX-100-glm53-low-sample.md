# EX-100 — GLM-5.3 low 동일 대진 NVFP4 샘플1경기

- 상태: Completed
- 생성일: 2026-10-15
- 승인: 현재 사용자 지시 / [D-153](../decisions/D-153-glm53-low-sample.md)
- 계획: [EP-159](../exec-plans/completed/EP-159-glm53-low-sample.md)
- branch/checkout: research/model-training /workspace a4659bf·기존 미커밋 변경 보존

## 질문·처치·고정 조건

[EX-099](EX-099-planner-unlimited-time-max-output.md)의 정상47턴 경기와 같은 조건에서
새 계획 모델의 실제 연결·행동·지연·usage를 관찰하는 탐색적 단일 경기다.
변경은 planner.model:glm-5.3-flash→glm-5.3, reasoning_effort:high→low이다.
식별자/출력 경로 외에는 EX-099의 동결 설정을 유지한다. 모델과 추론 강도가 동시에 바뀌므로
모델 단독 효과나 일반 성능 향상·인과효과를 주장하지 않는다.

GLM Z.ai·기존 endpoint/인증·thinking enabled/low·temperature0·top_p0.95·max_tokens131072,
세프롬프트·피해계산 포함 교정v6/names-v1·최초/3턴/기절/Tera/강제교체 호출을 유지한다.
응답 형식 오류는 같은 입력/옵션으로 최초+최대5회 재생성하며 provider-retry-v2의 개별 통신
 timeout/최대3회 재시도·최종429 중단은 같다. 유효 계획의 전략적 의미를 재생성 gate로 쓰지 않는다.
경기/전체 시간 상한은null이며 양쪽actor/전역/조건/Session/watchdog에 동일 적용한다.
실제 경과시간과 모든 호출/실패/usage를 기록한다. 공용 기본값은 바꾸지 않는다.

JEV autotrust/JEV-35B-NVFP4 revision10c2c62610e315e31a75baca849ad79d526e4658,
GPU0 TP1/동시1 Marlin W4A16/BF16 eager0.80·rank320/System1·공식head/calibration·
기존 고정환경/37파일·prefixcache·32768입력/32769엔진/readout1·16후보·사전8추론을 유지한다.
선택 일치·원ID/분포/usage·Marlin/메모리 검증을 유지하며 확률 차이는probability_diagnostic이다.
첫슬롯b01-r3-s1·자기p1/Abyssal p2·동일 팀·battle seed20892,520,39040,28395·
actor seed3890316613/3478776278이다. 계획은 새 경기에서 생성하며 과거계획/미래/숨은세트는 넣지 않는다.
actor는pokechamp/.venv/bin/python, 모델은.pokechamp-data/jev35b-nvfp4-runtime/.venv/bin/python,
환경은EX-099 고정 버전을 재사용하며 재설치하지 않는다.

## 한도·진입·중단·복구

GLM 물리HTTP128·JEV논리256(사전8포함)·경기1·GPUallocator40GiB/전체44GiB·소유host32GiB·
disk null/사용량 기록·포트18845/18846/8109 점유 시 미진입을 유지한다.
설정/전송 CPU검증 후 새 단일 적재·사전8추론 통과 서버로 본1경기를 수행한다.
별도 유료 GLM probe0이며 첫 실제 호출은 경기 예산에 포함한다. 모델 권한/지원 실패 시
모델/endpoint/인증 변경 또는Flash대체를 하지 않는다. 수집 진입 후source/조건은 불변이다.

RD11.1/C-018·RD11.2/C-046·C-070/073을 따른다. 도구 결함은 원본 보존·영향 분석·
독립검증을 거쳐 처리하고 재수집/재경기/보충/자동재개0이다. 원 시계·누적 호출은 초기화하지 않는다.
형식복구 소진/실행불가 응답은 해당 경기 실패, 통신/상한/공유 무결성·자원 실패는 의존 범위 중단이다.
시간 무상한에서도 사용자 취소·자식/서버 실패 감시·자원 정리는 유지한다.
전수 전략/설명 정확성 검토는RD8.1/C-032에 따라 기본 제외다.

## 검증·출력·완료 기준

불변 JEV formatter/무손실/head/환경 검증은EP-154/158 source·환경 일치 범위만 재사용한다.
새 모델 허용/잘못된 모델 거부·기본값 보존·low/131072/온도0·동일 재시도 wire를 CPU검증한다.
본경기에서는 실제 모델/low·시간null·원문/usage·분모·선택→명령·자원을 전수 감사한다.
EX-099와 결과/행동·지연·토큰·재시도·Ruination 사례를 기술적으로 비교한다.

run: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-100
증거: project_context/exec-plans/evidence/ep159
viewer: exports/battle_viewers/ex100/index.html
condition: glm53-jev35b-nvfp4-low-unlimited-max

정상1경기·실패 포함 분모/모든모델/엔진/원장/사용량·필수감사·통합뷰어/대표 이동후
오프라인/복사/다운로드·run/viewer/evidence 봉인·소유자원 반환이 완료 기준이다.
미충족 시 부분 기록과 차단 사유를 보고한다. 기존EX-093~099 원자료/뷰어/봉인은 불변이다.

## 결과

정상1/1·실패0·player_won·종료턴50·마지막관측50턴.
[최종 보고](../exec-plans/evidence/ep159/report.md)에 실제 분모/감사/비교/뷰어/자원/봉인을 연결했다.
