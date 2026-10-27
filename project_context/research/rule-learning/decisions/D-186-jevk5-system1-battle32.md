# D-186 — System One JevK5 선택 어댑터 실전32

- 상태: Accepted
- 날짜: 2026-10-23

## 맥락·결정

사용자가 완료된EX116의후속32경기평가와물리GPU1·2·3사용을명시했다.
선택epoch2 adapter를기존v6·Abyssal고정32대진에적용하고진영교환쌍을유지한3개replica로분리실행한다.
세부조건은[EX123](../experiments/EX-123-jevk5-system1-battle32.md), 구현/검증은[EP211](../plans/EP-211-jevk5-system1-battle32.md)이다.

## 근거·영향

32경기는선택모델의실전전이탐색이다. 추가원본32경기나학습은하지않고과거동일대진은참고비교만한다.
기존vLLM의지원정밀도BF16·학습과다른긴입력/backend한계를기록한다. 이전adapter/서버/Blocked실험/GPU0의병행연구는보존한다.
대안: 새입력표현이나추가대진으로비교범위를확장하는것은이번요청의기본조건으로채택하지않았다.
