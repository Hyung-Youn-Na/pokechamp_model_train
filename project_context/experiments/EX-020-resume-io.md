# EX-020 — 개선 IO 재실험

- Status: Blocked
- 날짜: 2026-09-08
- 관련: [D-022](../decisions/D-022-resume-io-experiment.md), [EP-011](../exec-plans/active/EP-011-improved-io.md)

## 실행 전 protocol

D-022의 순서·분모·통과·중단·예산 기준을 적용했다. 기존 EX-016 개발15장면과 사후3건,
fake12→Cloud 행동180/별도요약48→smoke12→조건당16/전체48판 순서다. 출력은
`.pokechamp-data/io-improvement/ex020/` 아래 새 단계·source별 디렉터리에 보존한다.
0.11.0+ruination-v1에서 시작하고 실제 발생 계산/입력 오류만 독립 재현 후 패치한다.
EX-019 일괄 수정, 프롬프트·전략 변경·재질문은 제외한다. 최초 Cloud 시계는 재시작에도 유지한다.

## 기술·발생 상황·수정·검증·현재 단계

| 기술/경계 | 발생 상황 | 수정 | 재검증 | 상태 |
|---|---|---|---|---|
| Knock Off / Poison Heal | IO-C04 공개 정보 누락 | 수신 protocol 보완, 복사/타인 귀속 제외 | 독립 Showdown 양성·음성 통과 | 수정 완료 |
| Future Sight | 예약 효과 입력 거부 | 즉시 피해와 예약/미래 미상 구별 | HP341→341→341→267, 음성341불변 | 수정 완료 |
| Bitter Blade + Future Sight | 양측 기절 후 미상 상대 교체 계산 거부 | 합법 교체 유지·피격 UNKNOWN | 독립 양측 기절 fixture 및 음성 통과 | 수정 완료 |
| Quark Drive / Supreme Overlord | 효과 이름과 공개 기절 수 미전달 | 활성 stat·FALLEN2 전달 | 활성/비활성64난수 피해·속도 일치 | 수정 완료 |
| Kowtow Cleave / Ninetales 요약 | 두 번 피격349→64→0을 만피 OHKO로 요약 | 모델/프롬프트 수정 없이 중단 | 원응답과 event70/76 불일치 | Cloud gate 실패 |
| Cloud 중단 응답 보존 | 진행 중1응답 미봉인 | worker 선봉인·intent·신호 후 수집·영속 halt | 로컬 회귀 통과, 과거1건 복원 안 함 | 한계 보고 |

수식·npm 버전·ruination-v1 identity는 유지했다. EX-017/018/019와 실패 자료를 합치지 않는다.
최종214 tests(50.64초), Ruff/Node10파일/compileall,15장면 의미·구조 및 사후3건 통과.
최종 fake12/12·terminal 경기 오류0·실제동시배틀10·격리/정리 통과. 배틀 내 요약7회,
별도 실제 actor/계산기31행동 fixture에서 요약3·통합1을 검증했다.

## Cloud 결과 및 미실행

C 입력 요약8제출 중7봉인·1미봉인이다. 확정 HTTP7, 추가1건의 실제 HTTP/응답/token은
미확정이다. 확정 token 입력150,179/출력9,166(합159,345)은 전체가 아니다.
Coordinator 경과81.12초(봉인 dispatch 시계부터 종료 로그 mtime). 의미 오류 확인 후
SIGINT로 중단했고 이후 보존 결함 수정·로컬 재검증 동안 Cloud 호출0이다. 최초 clock/halt는
보존했다. 구조7/7 통과를 전체 의미 통과로 해석하지 않는다.

| 단계 | 예정 | 시도 | 완료 | 실패 경기 | 미실행 |
|---|---:|---:|---:|---:|---:|
| Cloud 행동 | 180 | 0 | 0 | 해당 없음 | 180 |
| 별도 요약/통합 | 48 | 0 | 0 | 해당 없음 | 48 |
| Cloud smoke | 12 | 0 | 0 | 0 | 12 |
| 비교 A | 16 | 0 | 0 | 0 | 16 |
| 비교 B | 16 | 0 | 0 | 0 | 16 |
| 비교 C | 16 | 0 | 0 | 0 | 16 |

세 대비 각각16대응 누락, Cloud 승패/승률 및 HTTP겹침10/p95비율은 미측정이다.
Smoke 시간 기반 비교 예산 판정도 미실행이다. 중단은 예산 부족이 아닌 모델 요약 의미 오류다.
EX-020/EP-011 전체를 완료 처리하지 않는다.

요약48용4원자료는 EX-016 IO 경기의 양측 actor(IO2와 Abyssal/OneStep 각1)이며 각각30행동
이상이다. 자기 request와 해당 관점의 공개 protocol만 사용한다.12개 요약 맥락 준비 검증이
통과했고 실제 Cloud48호출은 하지 않았다. Fake A의 의도적 비정상 응답/fallback은 원본 경로
검증이며 fake 승패·token은 Cloud 효능·비용과 구별한다.

## 봉인 evidence

- [상세 보고서·집단별 분모/승패/비용/시간](../../.pokechamp-data/io-improvement/ex020/report.md)
- [214회귀·source/출력·자원 검증](../../.pokechamp-data/io-improvement/ex020/verification.json)
- [최종 offline](../../.pokechamp-data/io-improvement/ex020/offline-final/result.json)
- [최종 fake12와 cadence](../../.pokechamp-data/io-improvement/ex020/fake12-final/result.json)
- [Cloud 중단/미확정 사용량](../../.pokechamp-data/io-improvement/ex020/cloud-gate-v1/result.json)
- [확정된 모델 사실 오류](../../.pokechamp-data/io-improvement/ex020/cloud-gate-v1/semantic-failure.json)
- [미실행 일정과 대응 누락](../../.pokechamp-data/io-improvement/ex020/not-run.json)
- [영속 halt](../../.pokechamp-data/io-improvement/ex020/halt.json)

Cloud source는 offline-v8/fake12-v5, 종료/보존 수정 이후 로컬 source는 offline-final/fake12-final이다.
단계·source별 자료를 합치거나 후자를 Cloud 통과로 승격하지 않는다. EX-017/018 및 EX-019
출력8종 checksum,6개 로컬 집단132 actor seals,credential2,636파일/유출0,두 submodule clean,
8000/8100–8109 free 및 소유 calculator/worker 잔여0을 확인했다. 초기 hygiene 검증기의8000
인자 오류는 무효 자료로 보존하고 수정한 검증에서 통과했다.
