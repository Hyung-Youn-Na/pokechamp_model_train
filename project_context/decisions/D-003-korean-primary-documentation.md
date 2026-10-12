# D-003 — 한국어 우선 문서 정책 채택

- 상태 (Status): 채택 (Accepted)
- 날짜 (Date): 2026-09-04

## 맥락 (Context)

사용자는 한국어 연구자로서 project-context 문서의 주 언어를 한국어로, 영어를 보조 언어로
사용하라고 지시했다.

## 결정 (Decision)

Root [`AGENTS.md`](../../AGENTS.md)와 `project_context/`의 사람이 읽는 규범적 설명은 한국어를
우선한다. 영어는 괄호 속 용어, 파일명, code/API identifier, command, machine-readable status
value, 정확한 인용 등의 보조 표현으로 유지할 수 있다. 상속된 원저자 문서는 legacy
evidence이므로 이 결정만으로 일괄 번역하지 않는다.

## 거절한 대안 (Rejected Alternatives)

초기화 당시의 영어 우선 서술을 계속 사용하는 방안은 채택하지 않았다.

## 근거 (Rationale)

연구 소유자의 주 언어로 authority와 작업 상태를 직접 표현하면 장기 유지와 검토가 쉬워진다.
영어 technical identifier를 보존하면 code 및 외부 interface와의 대응 관계도 유지된다.

## 영향 (Consequences)

새 template과 control-plane update는 한국어를 기본으로 작성한다. 한국어와 보조 영어 설명이
충돌하면 한국어가 우선한다. 단, code/API identifier, 파일명, command, machine-readable literal,
정확한 인용은 원문 값을 따른다.

## 증거 (Evidence)

2026-09-04의 명시적 사용자 언어 정책 지시.
