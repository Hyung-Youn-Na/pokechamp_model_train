# 고정 대진 공개 상태 학습 — 구성 설명

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="고정-대진-공개-상태-정책-학습"></a>
## 고정 대진 공개 상태 정책 학습

[D-119/EX-076](experiments/EX-076-fixed-matchup-mcts.md)의 독립 구현은
`integration/pokechamp/fixed_matchup/`과 `scripts/pokechamp-fixed-matchup`이다.
D-126/EX-079의 `stopping_prepare`는 완료된 EX078 round1과32경기·optimizer/RNG를
새identity에 검증 계승한다. `stopping_run`은 정기 개발 평가 기록에서 종료 상태를 재구성하고,
정체 anchor와 실제 최고 모델을 분리한다. 정상 종료·최고 모델 잠금 이후에만 독립test에 진입하며
`stopping_finalize`가 실제 경기 결과와 종료/선택 기록을 독립 대조한다. 시간 상한은 적용하지 않는다.
D-123/EX-078의 `first_round`는 P0·worker설정만 계승하여 새32경기를 감사·학습하고
round1 체크포인트의 저장/재로딩을 검증한 뒤 종료한다. D-124 이후 별도 protocol의 무제한 경과시간 기록과
진단 완료 판정을 사용하며 기존 전체평가 경로는 유지한다.
D-122/EX-077의 새 기본값은24시간이며 `day-prepare`가 EX-076 정상uniform32와 P0의
출처·봉인을 검사하여 계승한다. CPU 입력 packing은 검증된 행을 모아 tensor별로 한 번 변환한다.
Node의 실제 경기 프로세스만 비공개 로그·원 RNG를 보유한다. 열거된 공개 현재 상태를
새 RNG의 탐색 프로세스에서 복원하며 양측 공동 행동을 한 RPC로 전이한다. Python의 Exp3
선택기는 양측을 독립 표본화하고 확률 분기를 통해 주변 방문 타깃을 생성한다.

정책은 무작위 초기화한 PyTorch TransformerEncoder 4층(hidden128/head4/FFN512)이다.
범주 embedding과 숫자32개 projection을 더한 상태 토큰을 인코딩하고 유효 토큰 평균으로
상태를 집계한다. 상태·후보 표현의 MLP가 합법 행동 logits를, 별도 tanh MLP가 상태가치를 낸다.
토큰 순서 위치 embedding은 없고 관점·종류 범주와 원래 팀/기술 슬롯 숫자가 관계를 나타낸다.
모델 특징은 구조화된 요약이며 시뮬레이터의 공개 상태 직렬화 전체를 무손실 입력하는 것은 아니다.
현재 Dex vocabulary5106개 기준 학습 파라미터는1,500,674개이며 Qwen 가중치를 사용하지 않는다.

CPU worker가 경기/탐색을 수행하고 주 프로세스의 배치 추론 스레드가 단일 소유 GPU를 사용한다.
완료 라운드 checkpoint에 optimizer·난수·replay 식별자·최초 시계를 저장한다.
선택은 dev, 개선 판정은 잠긴 test640경기로 분리한다. 원자료 감사는 실제 Showdown의 정규화된
명령 로그와 기록을 대조하며 오프라인 입력/응답/protocol 뷰어를 내보낸다.
실행·재개와 제약은 [사용법](../../../integration/pokechamp/fixed_matchup/README.md)을 따른다.
GPU 수치·처리량·실험 성공은 CPU 개발 검증에서 확정하지 않는다.
