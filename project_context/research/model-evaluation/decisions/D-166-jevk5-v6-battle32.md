# D-166 — JevK5-9B v6 상세32경기

- 상태: Accepted
- 날짜: 2026-10-20

## 맥락

사용자가 JevK5-9B를 기존 vLLM으로 서빙하고 연결 확인 뒤 v6 입력·32경기 실행을 명시했다.
서버는 GPU0·18847, 모델 revision d6521a18a86999190e9d775c915af3d6d6772fc4다.

## 결정·근거

EX111에서 v6 원정보와 고정32대진을 채택하고 JevK5의 선택지 logit readout을 구현한다.
일반 문장 생성과 구분하여 native 비Thinking prompt·전체후보 logprob·공식temperature1.316을 사용한다.
이는 명시된 모델의 학습/추론 방식을 맞추는 처리이며 배틀영역의 확률 보정을 입증하지 않는다.
기존 OpenAI 실험과 독립 코드/출력/포트를 사용하고 사용자 서버의 수명을 보존한다.

## 대안·영향

일반 텍스트 생성 후 ID 파싱은 JevK5 readout과 달라 채택하지 않는다. 추가모델·재학습·추가대진0.
설계/상한/검증/해석 원문은 [EX111](../experiments/EX-111-jevk5-v6-battle32.md),
진행은 [EP181](../plans/EP-181-jevk5-v6-battle32.md)이다.
