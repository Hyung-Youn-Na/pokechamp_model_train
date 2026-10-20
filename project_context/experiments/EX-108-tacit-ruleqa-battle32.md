# EX-108 — 학습 Tacit 규칙 Q&A 어댑터 실전32

- 상태: Completed
- 완료일: 2026-10-20 (KST)
- 생성일: 2026-10-19
- 책임자: Codex
- 승인: 현재 사용자의 취침 중 학습 모델32경기 예약 요청 / D-162 / EP-176
- 연구선/checkout/시작 commit: research/model-training /workspace a4659bf298c7935714f9fbd25246db2d831c5926

## 목적·선행조건

EX-107이 validation으로 선택한 비병합 LoRA의 실제 배틀 행동 생성·합법성·완주·승무패를 탐색한다.
EX-107 test 성적을 보고 어댑터를 다시 선택하지 않는다. 미학습 기반32경기는 추가하지 않으므로
학습의 배틀 개선 효과를 인과적으로 주장하지 않는다. 규칙 QA와 배틀 행동 선택은 다른 과제다.
사용자가 취침 전32경기를 요청했으며 Thinking 선호 질문에 답이 없으면 학습과 같은 비Thinking을 기본으로 한다.

EX-107 pipeline의 test 두 조건 완료·선택 adapter 내보내기·3rank 재로딩 pass·학습 GPU 반환 뒤 실행한다.
기존 EX-107 의미검토·최종보고는 CPU 후속 작업으로 계속하며 배틀 예약으로 생략하지 않는다.
선행 실패나 장치 사용 중에는 새 배틀을 시작하지 않는다. 선택 adapter identity를 준비 시 동결한다.

## 조건·대진·입력

기반 morriszjm/Tacit-9B revision884838f1698d1fd746625b3c20c8ec2be077a183, EX-107 선택 adapter/tokenizer.
기존 /ref/kev/.venv의 Torch2.8/Transformers5.17/PEFT0.21, BF16 기반/FP32 비병합LoRA·BF16 autocast,
SDPA/Torch native GDN. 신규 다운로드·환경 갱신·외부LLM/API 호출0.

Gen9 OU·Abyssal32경기/16진영교환쌍·동시성1. EX-089/106 동일 팀·seed·제출순서.
모델은 공개프리뷰로 선봉 선택, Abyssal은 기존seed선봉. 양측테라 금지(EX-106과 동일).
공식관측·자기request·동일cutoff 공개prefix·자기팀으로 v6 전체State·피해/속도·names-v1을 구성한다.
RuleQA의 confusion 설명 교정만 적용하고 State/context·조건·질문·A..J 행동선택지로 제시한다.
행동선택 문제이므로 QA의 'Do not choose a battle action' 지침은 사용하지 않는다.
시스템은 공개정보/조건부계산 구별과 합법 행동의 option ID·짧은근거를 요청한다. 숨은 상대세트·미래·oracle·GLM계획0.
학습 장면보다 큰6대6·행동선택으로의 전이이며 같은입력 QA 성능과 구분한다.

native chat enable_thinking=False·greedy·max_new_tokens192·seed20261019·요청 간 KV/대화 상태0.
입력상한32768·무절단. 출력 첫 비어있지 않은 줄의 단일 A..J ID를 합법후보에 연결한다.
ID 단독/점·괄호·콜론 및 Answer: 접두·markdown 강조를 허용하고 복수/후보밖/빈출력을 분류한다.
오류는 seed20261019+슬롯+결정ID SHA256의 독립 균등 합법선택으로 대체하며 재질의0.
이는 학습모델과 대체정책의 결합 성적이다. 단일후보는 무호출 자동선택. 전송 직전 rqid/후보 재검증.

## 자원·예약·gate·중단

새 출력 보존루트 runs/model-training/EX-108, viewer /workspace/exports/battle_viewers/ex108.
GPU1 UUID만 노출·공용 gpu1.lock·유휴 확인. GPU0·2·3 및 외부프로세스 회수0.
GPU44GiB·소유host32GiB·최초 GPU gate부터12시간·실제호출20000·요청180초·경기300턴/600결정.
GPU 준비 전 CPU 대표선봉/일반/강제교체·public boundary·파서·대체·전송·소스/자료 identity 검사.
동일 본서버에서 세 종류2회씩 총6회 반복/generation/resource gate 후 같은서버32경기.
성적이 낮거나 대체가 많아도 조건 변경·재경기·추가학습0. 최초2경기도 본수집에 포함한다.
기술/무결성/입력 초과/OOM/자원한도는 의존수집중단·부분기록/뷰어/반환. 모델오답은 전체중단사유 아님.
RD11.1/C-018·C-046 적용, fixture/분석 교정은 원문보존·독립검증 후 허용하되 실제 재수집0.
예약은 선행완료를 감지하는 단일 watcher가 prepare→execute1회만 수행한다. 선행실패면 중단 알림.
실행receipt가 있으면 자동재개하지 않는다. 최초시계/소모를 리셋하지 않는다.

## 평가·완료

예정32/시도/완료/실패/미완료/미실행·승무패·정상 점수, 완전 진영교환쌍 평균·쌍bootstrap10000(seed42) 탐색95%구간.
선봉/일반/강제의 최초파싱·합법률·오류종류·대체/자동선택·입출력토큰·절단·지연·자원.
전수 입력/출력/판정/명령/seed/종료 감사·C-047 이동후 오프라인뷰어·출처·봉인·소유GPU/PID/포트반환.
설명 의미 전수평가는 요청되지 않았으므로 RD8.1에 따라 미평가로 표시한다.
정상32경기와 후처리까지 완료해야 Completed이며 예약 성공은 실험 완료가 아니다.

- 사용자 후속 지시: 취침 전 필요한 모든 조건을 권장값으로 설정하도록 명시했다. 비Thinking·학습모델단독·Abyssal32·GPU1·외부API0의 권장값을 확정한다. 추가 확인을 기다리지 않는다.

- EX107 선택3epoch adapter/test/3rank재로딩 완료를 확인하고 자동 준비·동일 GPU1서버6gate를 통과했다. 현재32경기 수집 진행 중이며 완료 판정은 하지 않았다.

## 최종 결과

정상32/32·완전16/16쌍,10승0무22패(31.25%). 실패·미완료·무효·미실행0이다.
진영교환쌍 bootstrap10,000회 탐색95%구간18.75–43.75%다. 미학습 기반 대조는 없어 학습의 실전 개선을 단정하지 않는다.
본수집914결정 중885모델호출은 모두 최초 합법이며29단일후보자동선택·무작위대체0·출력절단0이다.
사전6호출을 포함한 전체891호출, 본 입력10,011,698·출력28,086토큰이다.
전체State입력8496–13262토큰·무절단, 호출지연 중앙4.57초/p95 5.59초.
본수집82.7분·GPU gate부터봉인88.1분, GPU최대29.24GiB·소유host최대27.77GiB다.
전수감사·914결정원문/이동후오프라인뷰어·run1408파일/viewer99파일 봉인검증·GPU1/PID/잠금/8108반환을 완료했다.
공통목록 링크누락은 원자료/개별뷰어를 바꾸지 않고 링크1개를 교정해 오프라인접근을 확인했다.
원본 봉인은 보존했으며 추가배틀·학습·QA test 재생성0이다. 설명의미전수평가는 사전범위대로 미평가다.

[최종 보고](../exec-plans/evidence/ep176/report.md) · [최종 지표](../exec-plans/evidence/ep176/final-summary.json) ·
[무결성/자원반환](../exec-plans/evidence/ep176/final-integrity.json) · [종결](../exec-plans/evidence/ep176/completion.json) ·
[32경기 뷰어](../../exports/battle_viewers/ex108/index.html).
