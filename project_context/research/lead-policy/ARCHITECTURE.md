# 선봉 선택 정책 — 구성 설명

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="b2-선봉-선택"></a>
## B2 선봉 선택

[D-052](decisions/D-052-llm-lead.md)/[C-033](CONTRACTS.md#c-033-llm-lead)의
`team_preview_study.py`는 기존 정책 hash를 보존한 새 `b2-llm-lead-v1` 준비·검증을 제공한다.
양쪽 actor는 B2이며 slot의 `actor_settings[].team_preview_policy`로 조건을 구분한다.
필드 부재는 기존 `seeded_random` 동작과 identity를 유지한다. actor 생성은 같은 `FixedPlayer`와
`FixedBackend`를 사용하고 기본 모델 설정은 바꾸지 않는다.

`team_preview.py`의 parent mixin은 공개 preview 알림 때 기존 Python RNG shuffle을 한 번 실행한다.
Pinned Player 생성자의 avatar 선택도 기존 RNG 소비에 포함된다. 자기 상세 request가 나중에 도착할 수
있으므로 양쪽 신호가 준비된 뒤 자기 제출 슬롯과 request를 대조한다. 입력은 자기 알려진 정보와
상대 공개 `poke` details만 포함하고 두 신호 이후 protocol/상대 객체·원팀을 읽지 않는다.

경기별 task 하나가 결정 context·선봉 요청·전송을 소유한다. `asyncio.to_thread`에서 기존 동기 Cloud
backend를 실행하고 event loop에서 완료를 기다린 뒤 선택 슬롯만 기존 순열 맨 앞으로 옮겨 전송한다.
중복 preview는 같은 task/결과를 재사용하며 중복 호출/전송하지 않는다. timeout·출력/전송 실패·취소는
명시적 실패이고 random fallback/재질의/대체 모델0이다. 취소 시 진행 호출의 보존·permit 반환을 기다린다.

`call_role=team_preview`의 실제 prompt·input identity/hash·원문/reasoning·검증·선택과 `wire_action`은
기존 recorder/viewer의 준비 결정에 연결된다. 자기 request와 공개 preview의 각각의 cutoff 및 두 신호의
완료 시점을 기록한다. `self_action`은 기존 B2 원본 검증·전달·출력복구를 그대로 거친다.
`POKECHAMP_LEAD_STUDY_ROOT`는 양쪽 요청을 기존 원자 예약/최초 시계/상한 코드에 연결한다.

prepare/verify는 호출0이며 실제 수집을 승인하지 않는다. 명시적 후속 실험 승인 후 등록 API가
EX/승인 근거 hash·고정 예산·source를 별도 실행 등록과 전역 study binding에 연결한다.
기존 actor/worker/backend 경로는 이를 검증하고 등록 부재·변조·동일 identity의 새 폴더를 거부한다.
[EP-040](plans/EP-040-llm-lead.md)의 구현·무유료 로컬 검증을 완료했으며
[EX-039](experiments/EX-039-b2-lead-proposal.md)는 종료·비교 미완료 상태로 보존한다.
D-055/EP-044의 EX-040은 봉인 실험 식별자에서 별도 protocol/binding을 선택한다.
EX-040의 첫429는 HTTP 응답 hook에서 halt를 기록해 다음 예약·HTTP admission·경기 제출을 막는다.
최초 시계는 별도 전역 hash binding으로 검증하며 기존 EX-039 binding/hash는 유지한다.
`team_preview_run.py`가 첫 대응쌍 기술 gate 후 나머지30을 같은 원장/시계로 실행한다.
`team_preview_report.py`가 선봉 조건별·완료쌍별 점수/누락·사용량과 기술 연결을 보고한다.
`a_diagnostic` 원자 예약의 선택적 hook은 C-033에서만 선봉/전투 결정 중복을 거부한다.

<a id="d-056-공급자-기본-동시성과-ex-041"></a>
## D-056 공급자 기본 동시성과 EX-041

`execution.py`는 새 준비의 공급자별 기본값을 선택하며 Z.ai 준비는4·zai-default4-v1을 봉인한다.
A 진단·A/B 직접대결·선봉 정책 준비 CLI/API가 공급자 선택 후 이 결정을 사용한다.
실행/검증/보고는 현재 환경의 기본값이 아닌 봉인 선언을 읽으며 기존 표식도 검증한다.
`team_preview_study.py`의 EX-041 protocol은 별도 binding/원장/최초 시계와 동시성4를 사용한다.
첫429/model halt와 admission은 봉인 식별자로 선택한다. EX-039/040 protocol과 기존 binding은 보존한다.

<a id="ex-042-공급자별-큐와-공유-수집-상태"></a>
## EX-042 공급자별 큐와 공유 수집 상태

`distributed_lead.py`는 EX-042의 버전·공급자 배정·worker별 설정을 관리한다. 선봉 CLI는 기존 준비/검증/등록/보고에서 이 식별자를 선택한다. coordinator의 공급자별 배틀 큐·독립 broker와 공통 원장/최초 시계/halt가 분리된다. 공급자 선택은 worker 입력/환경 복사본으로 전달하며 coordinator의 전역 선택을 교체하지 않는다. 과거 단일 공급자 경로·정책 hash를 유지한다.

정상 경기 목록 CLI는 봉인된 matches/summary에서 유효 경기만 읽고 기존 actor viewer/replay에 상대경로로 연결한다. EX-042 index 신규 생성은 기존52 viewer와 source/봉인 파일을 변경하지 않는다.

<a id="선봉-전략dex-규칙-구성"></a>
## 선봉 전략·Dex 규칙 구성

`lead_rules/`는 기존 `team_preview.build_input`의 완성된 자기 제출·공개 cutoff 입력만 받는다.
고정 Gen9 Dex/OU validator 추출 자산을 별도로 읽어 슬롯 기술 metadata와 종/폼 규칙·주변적 가능성을 추가한다.
`effects/`의 기존 상세 desc와 합쳐 요청별 ID 중복을 제거한다. 새로운 opponent actor/원팀/이후 기록 접근은 없다.
`team_preview_study`는 두 옵션과 결합 identity를 봉인하고 `FixedBackend`는 전송 직전에 같은 구성요소로 재생성한다.
원본 snapshot·요청 원장·wire와 보고에 같은 version/hash를 연결한다. B2 배틀 경로는 그대로이며 옵션 없는 과거 준비는 당시 봉인을 사용한다.

<a id="ex-043-교정-b2-비교"></a>
## EX-043 교정 B2 비교

분산 준비·CLI·실행·원장 경로는 EX-043을 별도 식별자로 선택한다. namespace 일정과 matchup-v2/dex-v2, provider-retry-v2를 봉인하고 과거 EX-042 분기는 유지한다. `diagnostics/corrected_lead.py`가 EP-051 공개 cutoff 재생과 독립 사실 감사를 경기 종료 뒤 수행하며 다음 슬롯 진입 전에 실패를 전체 halt로 연결한다. 실행 완료 판정에32개 감사 receipt를 요구한다. 온라인 감사는 별도 프로세스 그룹에서 실행하며 정리 기한60초 전에 제한한다. 제한 시 부분 자료를 보존하고 자원 정리 후 별도 출력으로 오프라인 감사를 완료한다.

<a id="ex-044-직접-본실험-연결"></a>
## EX-044 직접 본실험 연결

EX-044는 EX-043의 교정 선봉·입력 감사 실행기를 재사용하고 별도 study/clock binding을 가진다. D-065에 한정해 preflight skipped_by_user receipt를 허용한다. 감사 subprocess는 POKECHAMP_ROOT cwd에서 실행하며 이전 중단 자료를 변경하지 않는다.

<a id="ex-045-공식-관측-분산-비교"></a>
## EX-045 공식 관측 분산 비교

분산 실행기가 EX-045에만 공식 backend/build·v1.4.0/b2-official-v1을 준비·등록·worker·요청에 연결한다.
`diagnostics.official_cutoff`는 actor별 기록 행까지 공식 증분/전체 재생 후 정규화·계산·실제 입력·
원장/응답·숫자 슬롯을 대조한다. 자기 request와 공개 원문 사실·미확인 보존도 독립 검사한다.
coordinator는 official-cutoff-v1 receipt 통과 전 해당 자리에 다음 경기를 제출하지 않는다.
`diagnostics.official_lead`는 동일 coordinator의 fake 전용 첫4 제한과 경기당600초 상한으로
본 일정의 첫 공급자별 대응쌍을 검사한다. 과거 EX-043/044의 public-cutoff-v1은 보존한다.

EX-045에서 시간 제한 후 비동기 queue 처리와 wrapper 즉시 소비 검사의 불일치가 드러났다.
[D-068](../input-and-memory/decisions/D-068-official-async.md)/EP-058 연결부는 headless scene의 NaN interruption counter를
정상 초기값1로 두고 공식 atqueueend와 queue 위치를 함께 기다린다. 자기 request 앞·마지막 행의
종료 경계를 보장하며 Node 명령 직렬화·타이머 예외 실패 폐쇄·요청 전체30초를 적용한다.
upstream/build·schema·계산 의미는 유지한다. [EP-058 검증·보고](../../exec-plans/evidence/ep058/report.md)를 완료했으며 과거 수집
source와 중단 판정은 [EP-057 최종 보고](../../exec-plans/evidence/ep057/final-report.md)에 보존한다.
별도 fake 전용 ep058-local-eight 진단은 후속 공급자별4경기씩 동시에 실행하고 본 gate를 만들지 않는다.
