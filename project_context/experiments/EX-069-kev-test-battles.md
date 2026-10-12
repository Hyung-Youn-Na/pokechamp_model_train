# EX-069 — EX-065 test20 고정 대진의 Kev 본 테스트

- 상태: Completed
- 등록일: 2026-10-01
- 승인: [D-110](../decisions/D-110-kev-test-battles.md)
- 실행 계획: [EP-112](../exec-plans/active/EP-112-kev-test-battles.md)

## 질문·모집단·분모

EX-065에서 학습·development와 팀 단위로 분리했던 test20대진에서 고정 Kev 정책이 얻는
승패/무승부보정 점수와 실행 실패율을 측정한다. 이미 수집된 같은 팀·seed의 원 Abyssal
결과를 참고 비교한다. 소규모5팀 평가이며 전체 모집단 우월성·학습의 단독 인과 효과를
확증하는 검정이 아니다. 결과를 본 뒤 checkpoint·prompt·Tera 설정을 선택하지 않는다.

원문은 `.pokechamp-data/experiments/ex065-joint-q/versions/collection-v5/manifest.json`
(SHA-256 `e1d1f15a64746e0ce5888de42846cf3f16eb25638f64183cbdae1ed6a5ea71ef`)이다.
`games` 중 split=`test`인 원순서20행을 전부 사용한다. 상대100817·7627·38229·48494·5742,
각 seed_index0…3이며 original simulator_seed·양 actor_seeds를 그대로 사용한다.
새 팀/seed 추출·진영 교환·추가 경기0이다. 자기 EX-065 packed 팀·own.text와 p2를 유지한다.

신규 Kev 경기 예정20, 기존 Abyssal 기준선20이다. 원 Abyssal 경기의 실제 terminal 결과를
사용하며 후보 q rollout203,808개를 원경기 승패로 오인하지 않는다. 원 결과는 source/config
동결 뒤 분석에만 읽고 live 입력/선택에 전달하지 않는다. 원 대진 메타데이터 외 저장 test
입력/타깃·private roots 및 `/ref/kev/evals/pokechamp-ex065-v1/test.jsonl`은 열람하지 않는다.

## 고정 실행 조건

EX-068 v3와 같은 `/ref/kev/runs/pokechamp-r1/4b-kev4b-delta`, Base revision
`1001bb4d826a52d1f399e183466143f4da7b741b`, Kev commit `bb7185cb567e698b3ed0a2a682b0c3863371bf13`,
bf16/T1/LoRA r16·merged/fused·torch·CUDA graphs1·date facts0·LoRA scale1을 사용한다.
GPU3 전용, `/ref/kev/.venv/bin/python`, cwd `/ref/kev`, loopback8019, `/ref/kev` 수정0이다.
검증된 `kev_player`/`kev_value`와 JointInput·학습 질문·원순서 최대값·동률 규칙을 유지한다.

상대는 기존 Abyssal, gen9ou singles, timer off, 동시성1이다. 합법 Tera를 모두 허용하고
사용 턴·비율·사용 후 결정을 기록한다. 단일 후보도 Kev 호출, fallback/HTTP 재시도0이다.
추가 단위검사·validation 예측 대조·smoke는 사용자 지시로 `skipped_by_user`다.
기존 수락 근거는 EX-068 v3이며 새 서버의 준비/같은 모델·설정 확인은 실제 실행 진입에 포함한다.
경기 중 응답·rqid·합법성 검사와 종료 후 전수 기록 감사는 유지한다.

## 예산·중단·실패·복구

요청 최대600초, 개별 경기 최대1800초, 본 실행 최초 진입부터 누적14400초(4시간)다.
종료 여유600초를 남긴 시점에 신규 경기를 시작하지 않고 누적 상한60초 전 정리를 시작한다.
경기 시도는 각1회, 총20회이며 보충/재경기/재수집0이다. 별도 새 admission으로 한도를
고정하고 EX-068 원장/봉인은 유지한다. 최초 시계와 실패/미완료를 새 폴더로 초기화하지 않는다.
GPU3 다른 작업 발생·서빙/소스 변경·공유 입력/관측/전송/증거 결함은 의존 수집을 중지한다.

RD11.1/C-018의 평가 도구 교정은 원본 보존과 독립 계산 후 저장 자료에서만 한다.
실제 입력/처치 결함은 영향을 받는 경기를 무효 표시하며 자동 재수집하지 않는다.
RD11.2/C-046에 따라 실행 불가능 모델 응답은 해당 경기 실패로 격리하고 남은 독립 경기를
계속한다. 나쁜 합법 전략 선택은 중단 사유가 아니다. 통신/환경 장애는 공유 영향 범위를
기록하여 중지한다. 원자료·모델·새 경기 결과의 학습 전용은 없다.

## 지표·해석·완료

주 지표는 유효 완료 경기의 p2 승/무/패와 점수 `(wins+0.5*draws)/valid_completed`다.
예정/시도/정상/유효/실패/무효/미실행을 함께 보고한다. 실패를 패배로 바꾸거나 제외 사실을
숨기지 않는다.20대진 전체가 유효 완료되어야 계획된 본 평가를 완료했다고 표시한다.

원 Abyssal과 공통 유효대진의 p2 점수 차이를 game_id로 대응한다. 전체20경기 평균과5개
팀별 평균을 보고하며,5팀을 복원추출하는 paired cluster bootstrap20,000회·seed20261001의
percentile95% 구간을 보조 불확실성으로 사용한다.5개 군집뿐이라는 한계를 명시하고 구간이
0을 포함하지 않더라도 통제되지 않은 실행 방식 차이·정책/Tera 묶음 차이를 학습 단독 효과로
해석하지 않는다. baseline/live의 simulator·정책·초기화 차이는 별도 출처 보고에 연결한다.

모든 결정의 입력/원요청·원응답·후보 p·선택/명령·rqid 재검증·실제 전송을 감사하고,
토큰/지연·fallback·Tera·상태/서버 해시를 보고한다. C-047 뷰어와 원자료 봉인·소유 Kev/
Showdown/worker 정리를 완료한다. 설명 오류 사후 평가는 미평가(기본 제외)다.

## 증거와 결과

실행 자료 `.pokechamp-data/kev/ex069/`, 보고 `exec-plans/evidence/ep112/`,
뷰어 `exports/battle_viewers/ex069/`.

본20경기는 모두 유효 완료했고 Kev는0승·0무·20패, 원 Abyssal은11승·0무·9패다.
점수 차이−55.0%p, 사전 team cluster bootstrap95% 구간[−70.0,−40.0]%p다.
실패/무효/미실행0이며1,398결정·9,982후보 전수 감사와 독립 집계가 일치했다.
fallback/재시도0, Kev Tera20회·이후1,346결정이다. 원 봉인·runtime449파일·모델/서버의
전후 동일성과 소유 자원 정리/GPU3 반환을 확인했다. C-047의20경기 오프라인 전수 확인도 통과했고 완료 처리했다.
세부 분모·비용·기준선 실행 차이·증거는 [보고](../exec-plans/evidence/ep112/report.md),
[집계](../exec-plans/evidence/ep112/analysis.json),
[종료 확인](../exec-plans/evidence/ep112/closure.json)을 따른다.
