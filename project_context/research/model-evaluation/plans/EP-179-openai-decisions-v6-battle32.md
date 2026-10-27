# EP-179 — OpenAI Decisions v6 상세32경기

- 상태: Blocked
- 생성일: 2026-10-20
- 승인: 사용자 “v6 상세 입력을 기본으로 openai decision 모델을 32경기 테스트 해줘”
- 관련: [D-164](../decisions/D-164-openai-decisions-v6-battle32.md), [EX-109](../experiments/EX-109-openai-decisions-v6-battle32.md), C-067/C-046/C-047/C-079
- 연구선/branch: research/model-training; checkout /workspace; 시작 commit a4659bf298c7935714f9fbd25246db2d831c5926
- 기존 다수 미커밋 변경 보존. 입력·과거 실험·가중치 수정 없음.
- interpreter: /workspace/pokechamp/.venv/bin/python. 새 API 배틀 코드 integration/openai_decisions_battle.
- 출력: /mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-109
- 열람: EX-089 보고/manifest 및 사전검증용 저장 입력. 과거 결과는 신규 분모에 합치지 않는다.

## 목표·범위

v6 상세 입력을 공식 OpenAI Decisions Choice API로 손실 없이 전달해 Abyssal32경기/16쌍을 평가한다.
요청/응답/확률/명령/공개로그·사용량·경기별 감사·뷰어·봉인·자원 반환까지 수행한다.
INDEX/CHARTER·매뉴얼·STATUS/색인·RD11.1/11.2와 겹치는 active EP-062/064/075/077/080/134/140을 확인했다.
이전 Blocked/Paused를 재개하지 않으며 새 ID·출력만 사용한다. 모델 외부 호출은 현재32경기 지시의 범위다.

## 완료 기준

- [x] 독립 provider 어댑터·원문 보존·실패격리·원장 구현
- [x] v6/후보 동치·모의 HTTP·무유료 배틀·사전 API 연결 검증
- [ ] 본32경기·16쌍 및 경기별/최종 기술 감사
- [x] 한국어 결과·오프라인 뷰어/링크·봉인/소유 반환·상태 갱신

## 검증·중단

조건/상한/복구 단위는 EX-109에 둔다. 과거 모델 검증을 신규 공급자 검증으로 간주하지 않는다.
기술 결함은 의존 수집을 중지하고 RD11.1에 따라 조사한다. 사전 도구 교정은 가능하나
본경기 재수집은0이다. 판단 오류는 C-046대로 경기 단위이며 확률 이상은 진단으로 남긴다.

## 진행

- 2026-10-20 — 등록. 키 존재만 확인했고 비밀 값 출력0. 실제 API0·본경기0.

- 신규 adapter의 state/지시문/후보 JSON 역변환 동치·확률과 다른 원choice 보존·오류 비밀 제거와
  기존 v6/배틀 회귀94검사 통과. 기존 Pydantic deprecation warning1은 기능 실패가 아니다.
- EX-089 저장 대표3종에서 공식cutoff 재생성·현재 v6 payload/commands 동치를 확인했다.
  실제 OpenAI 사전3요청 모두 성공하고 합법 선택을 받았다. 상세 usage/원문은 새run/preflight에 보존.
- 모의2경기 진행 중이며 본32경기는 아직 미실행이다.

- 모의2경기 정상 종료·175결정/173모의HTTP·경기별 재생성/전송 감사와 최종 산술 통과.
- 신규 runner의 불법선택 경기 격리→다음 기술실패 전체중단을 별도 합성 사례로 검증했다.
  첫 단독 fixture는 Popen mock 이전 미로딩 의존성 때문에 실패했고 선행 import만 교정했다.
  실제 수집/모의경기 source는 해당 실패의 영향을 받지 않았다.
- 모의 후 마지막 변경은 실제 input 수로600결정 상한 계산·자식 환경의 OpenAI 키 제외와
  검증/뷰어 코드 보존이다. 신규10검사 통과. 입력/Choice 전송/관측 생성 로직은 모의와 동일하다.
- 모의뷰어를 다른 폴더로 이동하고 네트워크를 끈 뒤 lead/turn_action/forced_switch/자동선택
  4대표의 API 요청/응답·v6 상태·명령·턴로그·JSON 다운로드·결정 이동을 검증했다.

- 본수집11시도 중10유효(7승3패)·통신실패1·미실행21로 중단했다. 경기별/최종 감사·5대표
  이동후 오프라인뷰어·소유 반환을 완료했지만32경기 목표 미달이다. EX109 원자료/봉인을 유지한다.
- 후속 사용자 재실험 지시는 EP180/EX110으로 분리한다. 이 plan의 자동재개나 Completed 전환은 없다.
