# L1–L5 이식 연구의 보존 맥락 — 구성 설명

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="상속-시스템과-미정-목표-아키텍처"></a>
## 상속 시스템과 미정 목표 아키텍처

상속 AgenticSTS는 game/mod HTTP·SSE → typed state → AgentLoop → L1/L2 prompt·L3 knowledge·
L4 memory·L5 skill → backend/검증 → action → gated postrun 흐름이다. SSE 불가 시 polling을 쓰며,
monitor EventBus/WebSocket은 별도 관측 경로다. CombatConversation의 외부 메시지는 시작 cache anchor,
`ok` anchor, 최신 self-contained user state이고 이전 round plan을 다시 보내지 않는다.

Mod는 직렬화/action 실행, `src/state/`는 typed boundary, `src/storage/paths.py`는 dynamic store의
path authority를 소유한다. 정적 L3는 Python component에 남고 frozen comparison store는 새 mutable
실험의 쓰기 대상이 아니다. 세부 module·입출력·dependency는
[상속 아키텍처](../../../AgenticSTS/docs/reference/ARCHITECTURE.md)와
[repository layout](../../../AgenticSTS/docs/reference/REPO_LAYOUT.md),
[Python dependency](../../../AgenticSTS/pyproject.toml)를 따른다.

PokéChamp qualification은 Python3.11.11·uv0.12.9·Node18+/npm·pinned submodule·local disk30GiB 이상을
전제로 한다. Cloud에는 direct Ollama Cloud credential이 필요하지만 local battle에는 필요하지 않다.
상속 game/mod 재빌드는 적법한 game 설치본·.NET9·Godot/Harmony/game assembly가 필요하다.

L1-L5의 `pokechamp` layer mapping과 treatment architecture는 여전히 **TBD**다. D-007의
qualification environment는 채택됐지만 이를 목표 treatment architecture로 해석하지 않는다.
상속된 모든 TODO, roadmap, Future Work, 날짜가 있는 plan은 현재 planning에서 제외한다. 새 목표
아키텍처는 새 연구 목표를 승인한 뒤,
추적 가능한 [`decision`](../../DECISIONS.md)과 exec plan이 변경을 정의할 때만 도입할 수 있다.
