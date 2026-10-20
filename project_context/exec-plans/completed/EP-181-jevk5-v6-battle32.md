# EP-181 — JevK5-9B v6 상세32경기

- 상태: Completed
- 생성일: 2026-10-20
- 책임자: Codex
- 승인: 현재 사용자 “해당 모델을 통해 v6 입력과 32경기 실행을 실험해주세요.”
- 관련: [D-166](../../decisions/D-166-jevk5-v6-battle32.md), [EX-111](../../experiments/EX-111-jevk5-v6-battle32.md), C-018/C-046/C-047/C-067
- 연구선/branch/checkout: research/model-training /workspace
- 시작 commit: a4659bf298c7935714f9fbd25246db2d831c5926. 기존 미커밋 변경·실행 중 EX110 보존.
- interpreter: /workspace/pokechamp/.venv/bin/python; 외부 vLLM은 기존 전용 환경·GPU0.
- 출력: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-111
- 증거: project_context/exec-plans/evidence/ep181; viewer exports/battle_viewers/ex111.
- 참조: EX089 collection 보고/manifest/대표 입력, /ref/jevk5 고정 소스.

## 목표·범위

사용자 소유 JevK5-9B vLLM을 v6 상세32경기에 연결하고 입력·점수·명령 감사와 결과/뷰어를 제공한다.
독립 integration/jevk5_battle·launcher를 구현한다. 진행 중 EX110과 코드·출력·배틀 포트를 분리한다.
INDEX/CHARTER·매뉴얼·STATUS·색인·RD11.1/11.2·계약 및 겹치는 active
EP013/062/064/075/077/080/134/140/179/180의 보존·실행 경계를 확인했다.
기존 중단을 재개하지 않으며 외부 vLLM을 종료·재시작하지 않는다.

## 완료 기준

- [x] 원문/후보 무손실·native prompt/token 대응·raw logprob 보정·실패 경계 검사
- [x] 모의2경기·대표3종 반복6추론·외부 identity/자원 gate
- [x] 새 source/protocol 동결·유효32경기/16쌍·경기별/최종 기술 감사
- [x] 결과/불확실성·오프라인 뷰어/목록·봉인·소유자원 반환·외부서버 유지

## 검증·중단

조건·상한·복구와 해석 원문은 EX111이다. RD11.1/C-018을 적용하며 사전 도구 교정은
원본/시계/호출량 보존과 독립 검증 후 허용한다. 본경기 재수집0. 기술적 영향 수집을 중지하고
판단 오류는 C-046에 따라 분리한다. 문장 설명의 의미 검토는 해당없음(선택지 점수 판독).

## 진행

- 2026-10-20 — 등록. 서빙 확인용120토큰 요청1회는 사용자 이전 연결 확인이며 본 실험 분모 밖이다.
  본 실험 추론/경기0. 실험 등록 후 사전6요청과32경기를 별도 기록한다.

- CPU 신규/기존105검사 통과. 모델 가중치 SHA256은 고정revision 공식 LFS와 일치한다.
  첫 capture는 HF Hub global CAS 파일명을 LFS SHA로 오인한 검사 결함으로 실패했다.
  당시소스/로그를 evidence/ep181에 보존하고 공식 pinned metadata와 파일바이트 해시의 직접 비교로 교정했다.
  실제 모델 추론/본수집 전이며 source/자료/모델 영향0, 교정 capture 통과.

- 첫 모의경기는 기존 BattleServer 허용포트8100..8109 경계에서 차단됐다(모델/HTTP0).
  mock-port-attempt1과 최초소스를 보존하고 현재 비어 있는8108로 실험 전용포트를 교정했다.
  진행 중 EX110의8109와 사용자vLLM18847은 불변이다. 본경기/사전모델호출 전 교정이며 새모의검증한다.

- 모의2경기 정상/175결정·173모의요청 전수감사 및 원토큰/점수/명령 변조거부3검사 통과.
  이동후오프라인 뷰어4대표의 실제프롬프트/확률/요청/응답/상태/명령/다운로드 검증 통과.
- 사전 실제6요청·11934~13373토큰·native template/token동치 통과. 세 종류 반복 선택/확률 차이0.
  외부 GPU0/host 한도 통과. 본 source/조건 동결 후32경기를 시작한다.


## 완료·증거

2026-10-20 새32경기/16쌍·경기별/최종감사를 완료했다. 상세 성적·조건·한계는 EX111을 따른다.
1,143결정의 내보내기 전수대조·오프라인5대표·봉인검증과 소유프로세스/포트/사용잠금 반환을 완료했다.
사용자 vLLM은 유지한다. 수집 종료 시 source동치를 확인한 뒤 뷰어의 기술/교체/선봉 표시명만
보완했으며 원수집source/원자료/봉인은 불변이다. 최종뷰어source와 원버전 차이를 별도 보존했다.

[완료 보고](../evidence/ep181/report.md) · [오프라인](../evidence/ep181/final-browser.json) ·
[봉인 검증](../evidence/ep181/seal-receipt.json) · [뷰어](../../../exports/battle_viewers/ex111/index.html).
