# EX-089 — 교정 v6 JEV-9B 신규32경기

- 상태: Completed
- 완료일: 2026-10-14
- 등록일: 2026-10-13
- 승인: 현재 사용자의 새64경기 명시 승인 / D-136 / EP-141
- 연구선·branch: `research/model-training`; checkout `/workspace`
- 시작 commit: `a4659bf298c7935714f9fbd25246db2d831c5926`; 기존 미커밋 구현/교정·자료 보존

기본 열람: [전체32경기 · Damage-calc](../../exports/battle_viewers/ex089-damage-v1/index.html).
[EP-142](../exec-plans/completed/EP-142-jev-damage-viewer.md)의 표시 재내보내기이며,
[수집 당시 봉인 뷰어](../../exports/battle_viewers/ex089/index.html)와 원자료를 보존한다.

[EX-088 공통protocol](EX-088-jev27b-v6-corrected.md)을 적용하고 EX-088 종료/반환 뒤
GPU0–3을 독점하여 신규32경기·16쌍을 실행한다. 모델만
[EX-087의 고정9B 조건](EX-087-jev9b-public-memory-v6.md)을 사용한다.
`autotrust/JEV-9B` revision `7ac669b8fb476ba926491e3d1c39f9330d68dbed`, 공식LoRA병합·
BF16 backbone·FP32 24×4096 head·bare-v1·보정값0.9840233476014968·6/10/10/6층이다.
embedding GPU0·norm/head GPU3, 본서버1회 적재/최대8사전추론·동일서버 수집이다.
기존9B가중치/공유환경을 그대로 사용한다.

비교 기준은 EX-085이며 새모델간 비교는 EX-089−EX-088이다. 이전EX-087의 미실행32와
준비/중단 봉인은 보존하고 새 분모에 계승하지 않는다.
명령 `scripts/jev-eval {prepare|execute|status} --experiment EX-089`;
run `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-089`,
viewer `/workspace/exports/battle_viewers/ex089/index.html`로 분리한다.
자원·검증·중단·비교/해석·완료·환경의 원문은 EX-088 공통protocol이다.

## 최종 결과

신규32경기/32시도·유효32·완료16쌍이며6승0무26패, 점수18.75%다.
실패0·무효0·미실행0·완료율100%이며 최종 기술 감사를 통과했다.
EX-085와의 공통 유효16쌍에서15.625%→18.75%, 차이+3.125%p다.
EX-088과의 공통 유효16쌍에서는 EX-089−EX-088=−28.125%p다.
고정 대진의 결합 처치 탐색 결과이며 일반 성능 개선이나 모델 크기만의 효과를 주장하지 않는다.

저장1,139결정·1,101본수집 추론/HTTP POST·38자동선택·1,139명령이며 재전송/중복추론0이다.
본수집 입력16,712,797토큰·출력0·usage 미확정0이다. 본서버1회 적재와 사전8추론
(입력112,916토큰·21.700초)은 별도 비용으로 보존했다.
경기별1회 감사·종료 완전성/산술·전수 내보내기와 모델별5대표 오프라인 화면 검증을 통과했다.
뷰어는1,139결정·공개11,036행·원문1,240파일을 포함하며 실패 표시는 합성fixture로 구분했다.
모든 쓰기 종료 뒤 run/collection/viewer 봉인과GPU/잠금/포트 반환을 확인했다.
두 모델 controller와 단계 알람 감지기도 종료했으며 추가 경기·재개는 없다.

[통합 최종 보고](../exec-plans/evidence/ep141/report.md) ·
[비교 검증](../exec-plans/evidence/ep141/final-comparisons.json) ·
[봉인/무결성](../exec-plans/evidence/ep141/final-integrity.json) ·
[32경기 Damage-calc 뷰어](../../exports/battle_viewers/ex089-damage-v1/index.html).
원 실행의 동결 protocol/source·원자료와 완료 기록은 위 run 경로에 보존한다.

저장 계산의 결정별 연결·표시 판본 검증은 [EP-142 보고](../exec-plans/evidence/ep142/report.md)에
기록한다. 새 경기·모델 호출·피해 재계산 없이 당시 자료만 표시하며 위 성적/분모는 유지한다.
