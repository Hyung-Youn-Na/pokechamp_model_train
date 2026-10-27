# D-134 — JEV-9B 단일 Choice 동일32경기

- Status: Accepted
- Date: 2026-10-13
- 승인: 현재 사용자 제공 계획의 구현·검증·새32경기 실행 지시

EX-083과 같은 입력·단일 선택 정책·고정32슬롯을 공식 JEV-9B 패키지로 모두 새로 평가한다.
기존 JEV-27B 결과는 비교에만 사용한다. 모델 identity·head·보정값·경로와4GPU 배치를
명시 프로필로 분리하고 기존 JEV 환경·관측·전송·감사·뷰어를 재사용한다.

조건·자원·최대8회 GPU 사전검증·분모·중단·해석 원문은
[EX-085](../experiments/EX-085-jev9b-single-choice.md), runtime은
[C-066](../CONTRACTS.md#c-066-jev9b-single-choice), 진행은
[EP-139](../plans/EP-139-jev9b-single-choice.md)다.
EX-083의2GPU/4GPU 계승 구성과 공식 패키지 차이를 명시하며 모델 크기만의 효과나
일반적 성능 우위를 주장하지 않는다. 기존 실험·환경·원자료·봉인은 보존한다.
