# EX-070 — Kev 후속 정책 질문의 1경기 진단

- 상태: Completed
- 등록일: 2026-10-01
- 승인: [D-111](../decisions/D-111-kev-continuation-question.md)
- 계획: [EP-113](../plans/EP-113-kev-continuation-question.md)

## 질문·처치·모집단

학습된 Kev의 후보별 질문만 바꾸었을 때 이미 관찰한 EX-069 첫 대진에서 나타나는 행동과
결과를 진단한다. `kev-continuation-noul-v1`을 명시적으로 선택하며 질문은 다음 한 줄이다.

```text
Candidate {action_id} ({action}): If we choose this action now, and our side subsequently continues using Kev's current action-selection policy while the opponent continues using the Abyssal policy, what is our probability of winning the game?
```

접두사의 action 설명은 기존 describe를 그대로 사용한다. 기존 `kev-joint-noul-v1`과 기본값은
유지한다. JointInput의 상태 문자열·후보 순서·명령과 HTTP 구조·noul 응답은 불변이다.
공용 생성기·학습 코드/타깃을 바꾸거나 새 prompt를 탐색하지 않는다.

## 고정 실행 조건

EX-069 동결 configuration의 첫 `test-t100817-s0`만 사용한다. 양 packed 팀/자기 입력용
팀 문자열·p2·simulator seed·양 actor seed·gen9ou singles·기존 Abyssal·timer off·동시성1,
합법 Tera 허용·후보별 최대 p(true)·동률 원순서·단일 후보 호출을 그대로 유지한다.
비교 기준은 EX-069의 동일 경기 35턴 패배다. 저장 학습 suite test 입력/타깃 열람0이며
EX-069 live 결정 원자료는 질문 바이트 검사와 사후 비교에만 사용한다.

모델은 EX-069와 동일한 `/ref/kev/runs/pokechamp-r1/4b-kev4b-delta`, Base revision
`1001bb4d826a52d1f399e183466143f4da7b741b`, Kev commit
`bb7185cb567e698b3ed0a2a682b0c3863371bf13`, bf16/T1/LoRA r16·merged/fused·torch·CUDA graphs1·
date facts0·LoRA scale1이다. GPU3 전용·loopback8019·`/ref/kev/.venv/bin/python`·cwd `/ref/kev`,
해당 경로 수정0, GPU1 EX-066 학습 보존이다. 질문·소스·모델·서빙 identity를 실행 전에 동결한다.
사전 CPU 검사는 수행하며 추가 GPU 예측 대조·validation·smoke는0이다.

## 예산·실패·복구

신규 경기 예정1·시도 최대1, 재시도/보충/재수집/fallback0이다. 별도 영속 admission이 출력
폴더 변경으로 초기화되지 않아야 한다. 요청600초·경기1800초·서버 시작부터 정리까지 누적3600초,
마지막60초는 정리용이다. 최초 시계·실패를 보존하며 서버 시작이나 경기 재진입은 없다.
외부 API0이며 소유 Kev·worker·Showdown만 시작/종료한다.

RD11.1/C-018의 원본 보존·독립 검증·저장 자료 재평가를 지원한다. 수집 결함은 영향 경기를
무효로 기록하며 재수집0이다. 공유 입력·관측·서빙·무결성 결함과 GPU3 타 작업은 의존 실행을
중지한다. RD11.2/C-046에 따라 합법적인 나쁜 선택은 계속하고 실행 불가능 응답은 해당 경기
실패로 기록한다. 전송/환경 장애와 판단 오류는 구분하며 실패를 패배로 바꾸지 않는다.

## 측정·해석·완료

예정/시도/정상/유효/실패/무효/미실행 분모, 승패·턴 수·Tera 사용·결정 수·입력/HTTP/서버
지연을 비교한다. 모든 결정의 입력·원 요청/응답·후보 p·최댓값/동률·rqid·합법성·실제 전송을
전수 감사한다. 후보 확률/선택의 직접 비교는 JointInput 바이트와 후보/명령이 같은 결정에만
한정한다. 최초 분기와 이후 서로 달라진 경로는 구분하며 같은 턴 번호만으로 대응하지 않는다.

정상1경기·전수 감사·한국어 보고·봉인·소유 자원 정리·GPU1 보존·C-047 뷰어/이동 후
오프라인 검증을 모두 마쳐야 완료다. 실패하면 분모와 미충족 기준을 보고한다.
재학습 없는 프롬프트 변경 진단이며 현재 학습 타깃은 Abyssal 후속 정책 기준이다.
질문 변경은 Kev 후속 승률 예측의 정확성을 보장하지 않는다. 이미 결과를 확인한 대진의
단일 재실행으로 승률 개선·전패 원인·후속 정책 가치의 보정 정확도를 확정하지 않는다.
설명 평가는 미평가(기본 제외)다.

## 증거·결과

실행 `.pokechamp-data/kev/ex070/`, 보고 `exec-plans/evidence/ep113/`,
뷰어 `exports/battle_viewers/ex070/`.

정상·유효1/1경기, Kev122턴 패배다. EX-069의35턴 패배와 비교했고 동일 입력2결정/19후보 중
1턴의 교체 선택이 달라졌다. 분기 후 경로는 직접 확률 비교에서 제외했다.132결정/1,013후보의
전수 감사·CPU179검사·이동 후 오프라인 뷰어·원/새 봉인·소유 자원 정리와 GPU1 보존을 확인했다.
추가 예측 대조/재시도/재수집0이며 승인된1회를 사용했다. 세부 분모·지연·해석 한계는
[최종 보고](../../../exec-plans/evidence/ep113/report.md), [독립 비교](../../../exec-plans/evidence/ep113/comparison.json),
[종료 확인](../../../exec-plans/evidence/ep113/closure.json)을 따른다.
