# EP-173 — Tacit 규칙 Q&A LoRA

- 상태: Completed
- 생성일: 2026-10-19
- 책임자: Codex
- 승인: 현재 사용자 계획 실행 지시 / D-161
- 조건 원문: [EX-107](../experiments/EX-107-tacit-ruleqa-lora.md)
- 연구선/checkout/시작 commit: research/model-training /workspace a4659bf298c7935714f9fbd25246db2d831c5926

## 범위·불변조건

integration/pokechamp/rule_qa_training·scripts/pokechamp-ruleqa-train 및 연구 문서/증거 추가.
INDEX/CHARTER/매뉴얼/RD/CONTRACTS와 겹치는 EP-163/172 확인. 기존 변경·중단실험·GPU0 작업 보존.
기존 학습 중단 EP는 고정대진/공동q/RL 연구이며 해당 실행/모듈을 재사용하지 않는다.
AgenticSTS 수정 없음. 출력·환경·복구·중단은 EX-107 원문을 따른다.

## 완료 기준

- [x] EP/ADR/EX 및 domain 연결 등록
- [x] CLI·CPU 검증·자료 준비
- [x] GPU 사전검사·기준선·3epoch 학습·선택
- [x] 잠긴 test 비교·bootstrap·블라인드 검토
- [x] adapter 내보내기·재로딩·보고·자원 반환

## 진행·검증

- 2026-10-19 — GPU1–3 유휴 확인, 기존 환경 버전 일치. 구현 전 등록.
- 증거: EX-107 보존 출력 및 `project_context/exec-plans/evidence/ep173/`.

## 중단

INDEX workflow·EX-107을 따른다. 중단 처리를 실험 완료로 표시하지 않는다.

- CPU GPT/Qwen 선택위치 loss·gradient 동치, native masking, 선택형 파서·선택/cluster bootstrap fixture 검증 통과. 처음 HF5 BatchEncoding 반환 접근 오류는 GPU 전 수정하고 전수 준비를 통과했다.
- 전체 train/validation/test 4608/576/576행·최대4542토큰, train9,497,015토큰/epoch. 기존 연결성분658/83/82·split 교집합0. pinned 모델13개 입력 파일의 현 SHA를 EP163 공식검증 receipt와 대조했다.
- GPU1·2·3 UUID/공용 잠금으로 DDP1업데이트 사전검사 진입. GPU0 EX-106 보존. 본학습·test는 미실행.

- DDP 사전24문항/1업데이트 통과: 세rank 유한 loss/gradient·LoRA갱신·전체 기반 byte hash불변, 실제 GPU최대22.46GiB<44GiB. 업데이트85.84초, 576step단순 추정13.73시간(긴문항 기준·평가제외). 사전상태 폐기 후 기반validation→본학습 진입.

- CPU7검사 통과. 현재 train invocation 성공/selection 확정만 기다려 evaluate→export를 순서대로 실행하는 finish_pipeline.py를 연결했다. 실패 시 후속 진입0이며 종료 뒤 블라인드 의미 검토/최종보고는 별도로 완료해야 한다.

- 기반validation576완료: StateMC120/192(62.5%), 자유형 첫줄 문자열일치 short0/192·State7/192. 의미정확도로 해석하지 않는다. 본학습 진입.
- 완료/실패 감지 completion_alarm.py의 terminal/중복방지 fixture와 현재대화 queue 연결시험 전송 통과. 기존 train invocation→평가/내보내기 완료 후 같은대화에서 블라인드검토/최종보고를 재개한다. 전송 원장은 .pokechamp-data/ex107-completion-alarm에 분리. 추가모델/API/실험재시작 권한을 만들지 않는다.

- 576step/3epoch와 validation선택 완료(epoch3). 현재 잠긴test·내보내기 후속진행. 사용자 새지시의 실전32예약은 별도EP176/EX108이며 원QA protocol을 변경하지 않는다.

## 완료

2026-10-19 승인된 모든 학습·오프라인 평가·내보내기·검토·최종보고를 완료했다.
원문 A/B 판정을 저장한 뒤 모델명을 연결했다. 전수3456평가행·576step×3rank·12checkpoint의
분모/유한성/채점/선택/동일성과 adapter재로딩을 확인했다. 현재소스는 준비판본과 일치한다.
201파일 봉인과 EX107 소유자원반환을 확인했으며 EX108의 이후GPU1 소유는 유지했다.
[최종보고](../../../exec-plans/evidence/ep173/report.md) · [감사](../../../exec-plans/evidence/ep173/final-audit.json) ·
[종결](../../../exec-plans/evidence/ep173/completion.json) · [봉인](../../../exec-plans/evidence/ep173/seal-receipt.json).
