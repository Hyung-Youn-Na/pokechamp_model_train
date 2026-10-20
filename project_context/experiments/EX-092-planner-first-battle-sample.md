# EX-092 — EX-088 첫 대진의 GLM planner–JEV 샘플

- 상태: Completed
- 완료일: 2026-10-15
- 생성일: 2026-10-15
- 책임자: Codex
- 승인: 사용자 EX-088 첫 경기 샘플 실행 지시 / D-142
- 실행 계획: [EP-148](../exec-plans/completed/EP-148-planner-first-battle-sample.md)
- 연구선·checkout: research/model-training, /workspace
- 시작 commit: a4659bf298c7935714f9fbd25246db2d831c5926; 기존 미커밋 코드/문서 보존·실행 source 동결

## 목적·표본·해석

현재 역할/자원 planner와 표시 이름을 적용한 JEV-9B가 실제 배틀에서 계획을 생성/재사용하고
합법 행동을 선택하는1경기 샘플을 수집한다. 첫 실제 연결과 관찰 사례이며 승률 향상 검정은 아니다.
EX-088 collection manifest의 schedule[0]인 b01-r3-s1만 새로 실행한다. 원EX-088 결과는
그대로 보존하며 과거 경기 outcome을 새 분모에 넣지 않는다.1슬롯/1시도·대응쌍0이다.

- actor p1; 상대 Abyssal p2; 팀키1/2와 showdown_team 원문 동일.
- battle_seed: 20892,520,39040,28395.
- actor_seeds: p1=3890316613, p2=3478776278.
- 자기팀: Lokix, Pecharunt, Zamazenta, Ting-Lu, Latios, Gliscor.
- 상대팀: Zapdos, Hydrapple, Zamazenta, Slowking-Galar, Tinkaton, Ting-Lu.
- 원문 출처: runs/model-training/EX-088/collection/manifest.json. 해당 문서 봉인·팀 SHA와
  첫슬롯 identity를 준비 시 확인하고 provenance에 연결한다.

## 고정 처치

- Planner: Z.ai glm-5.3-flash, thinking enabled/low, temperature1/top_p0.95/max_tokens8192,
  nonstream JSON; 모델 seed 미적용. 새 역할/자원 guide-v1 + strategy-compact + 기존 executor bridge.
- 호출: events_or_periodic, N=3, faint/실제tera/자기forced_switch; 최초 다후보에서 호출.
- Executor: autotrust/JEV-9B revision 7ac669b8fb476ba926491e3d1c39f9330d68dbed,
  기존 BF16/공식 보정·bare-v1·단일Choice·4GPU 6/10/10/6층. 새 가중치/양자화/학습0.
- 입력: 교정 jev-choice-v6, 계산기 포함, candidate_display=names-v1. 후보 ID/명령/순서 보존.
- 경기/모델 동시성1; 단일후보 무호출; 매 경기 원자료·plan 상태 새로 시작.
- 자기 set과 상대 공개 관측만 모델에 전달한다. 일정 파일의 상대 실제팀 정보는 배틀 설정용이다.

## 한도·실행·자원

1경기·planner HTTP 최대128시도(재시도 포함)·JEV 논리 선택 최대256회.
경기3600초, 실행 전체4200초이며 최초 실행 시계와 누적 사용량을 보존한다. 경과시간 종료는
패배로 변환하지 않는다. 별도 유료 probe·GPU 재로딩 반복·추가 smoke 배틀0이다.
이 한도는 요청한1경기 샘플의 실행 제한이며 추가 경기나 한도 소진 후 재호출 승인이 아니다.

기존9B 고정 GPU0–3 프로필: 장치별 allocator40GiB/전체44GiB, 소유호스트32GiB,
공유 자산·새출력 합산디스크100GiB. 실제 UUID/유휴/잠금/메모리·disk 사용량을 기록·감시한다.
기존 가중치/환경을 재사용하고 타 프로세스/자원을 점유하거나 종료하지 않는다.
Z.ai C-038: 연결/timeout/5xx/429 최대3재시도, 대기1/2/4초; 최종429는 신규 수집 중단.
JEV 로컬 HTTP600초·같은ID/본문 재전송 최대3회10/30/60초·영속 중복추론 방지를 유지한다.

모델 interpreter는 .pokechamp-data/jev27b-runtime/.venv/bin/python, actor는 pokechamp/.venv/bin/python.
실행기 scripts/jev-planner prepare/run --mode live, 실행별 output/directory를 지정한다.
새 run: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-092.
외부 stdout은 run 밖의 EP-148 증거 경로에 둔다. viewer는 exports/battle_viewers/ex092/index.html.
자격증명·private endpoint·machine ID를 이 문서에 적지 않는다.

## 검증·실패·복구

C-070/071/072와 RD11.1/C-018·RD11.2/C-046·C-047을 적용한다.
EP-145/146/147의 CPU/모의·표시/guide 검증과 EX-089의 동일9B 모델 패키지 검증을 재사용한다.
새 실행에서는 현재 source/config/prompt·공식 관측/필수자산·모델 receipt와 GPU/포트/예산을 확인한다.
첫 실제 요청도 본 경기 비용/분모에 포함하며 별도 효과 비교를 만들지 않는다.

사용할 수 없는 계획/choice는 해당 경기 실패다. 유효한 형식의 나쁜 계획/합법 선택은 그대로
기록하며 설명 정확성 사후채점은 기본 제외다. 공유 입력/전송/무결성/자원 오류는 의존 실행을 중단한다.
의도치 않은 입력/수집 변경은 무효/부분으로 보존하고 source·조건을 바꿔 수집을 이어가지 않는다.
재경기·보충·자동재개0이다. 배틀 진입 전 도구 결함은 원본/사용량·최초시계를 보존하고
CPU 교정/독립검증 후 새 준비본으로 처리할 수 있으나 본 경기 시도를 늘리거나 한도를 초기화하지 않는다.
그 밖의 복구/재수집은 이 실행기의 자동 지원이 없으며 기존 봉인/실패를 지워 우회하지 않는다.

완료 기준은 정상1경기와 요청→계획→선택→명령/종료·사용량 원장의 연결,
전수 원문 export·대표 화면 오프라인 검사·run 봉인·소유자원 반환이다.
실패하면 예정/시도/완료/실패/미실행·미확정usage와 부분기록/뷰어·정리 결과를 보고한다.

## 진행·증거

등록 시 실행 전이다. 준비 자료·검증·실행 stdout·종결 보고는 project_context/exec-plans/evidence/ep148,
수집 원문은 새 run에 기록한다. 기존 EX-088/089·Blocked/Paused는 변경하지 않는다.

- 2026-10-15 — 첫일정/팀 봉인 대조·입력자료identity587파일 일치·9B17파일 영수증/리비전·
  자격증명/포트/GPU 유휴 확인을 통과했다. 준비 디스크 약95.315GiB/100GiB.
  새 source/config/prompt 준비본을 고정하고 단일 서버 적재/실제1경기 수집에 진입한다.

## 최종 결과

예정1/시도1/완료1·실패0/미실행0, **55턴 p1 승리**로 정상 종료했다. 대응쌍0이다.
68결정/68명령이며 GLM30호출·JEV66호출·단일후보 자동2회다. HTTP재시도/중복추론0,
GLM입력433,301/출력26,255토큰, JEV입력1,123,360/출력0토큰을 기록했다.
실행기 경과1,186.731초(약19분47초), 사전조사/prepare는 별도다. 화폐 비용은 공급자 미기재다.

독립 전수 기술 감사·68결정 원문export·대표3결정 이동후 오프라인 표시/복사/다운로드,
run 봉인·소유GPU/프로세스/잠금 반환을 완료했다. 기존 EX-088/089·중단/봉인은 보존했다.
이1경기 결과로 planner 독립 기여나 일반 성능 향상을 주장하지 않는다.

[최종 보고](../exec-plans/evidence/ep148/report.md) · [감사](../exec-plans/evidence/ep148/audit.json) ·
[완료](../exec-plans/evidence/ep148/completion.json) · [실제 경기 뷰어](../../exports/battle_viewers/ex092/index.html).
