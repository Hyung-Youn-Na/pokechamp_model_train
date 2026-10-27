# EP-201 — 우선순위별 Gen9 규칙 적용 System 1 자료

- 상태: Completed
- 생성일: 2026-10-21
- 승인: 사용자의 5개 데이터 우선순위 순서 생성 지시. D178.
- 연구선/checkout/commit: research/model-training /workspace feda62f733c1b470364868262c789ec857ef67f5; 기존 미커밋 변경 보존.
- 환경: 기존 Node 및 jev35b-nvfp4-runtime Python, CPU only. 모델/GPU/API/학습/서빙 변경0.
- 구현: integration/mechanics_system1/, scripts/mechanics-system1-data.
- 출력: /mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/gen9-mechanics-system1/v1
- 제공: exports/gen9-mechanics-system1-v1 및 ZIP, evidence/ep201.

## 목표와 범위

1. 특성·도구의 무효화·KO 방지·무시/억제
2. 교체 진입·설치물·잔여 효과와 HP/생존
3. 기술 선택 가능성과 실행 성공 조건
4. 명시된 공개 정보 및 가능한 숨은 조건 집합에서 정보 충분성
5. 행동 순서, 성공, 피해, KO 방지, 잔여 효과를 결합한 한 턴 판정

각 우선순위 파일 및 1→5 합본을 만든다. 대표 규칙군의 명시적 유한 조건 그리드이며 모든 Gen9 상호작용 전수라는 주장은 하지 않는다.
고정 Showdown e64915c0eab066db1d3e732b1280386468dd7415 Dex/hooks 및 실제 Battle 메서드로 독립 예상값을 검증한다.
System1은 입력 마지막 위치의 문항별 선택지 CE, 설명/정답 completion0이다. 기존 tokenizer/template 재사용.
합성 제어 조건은 실제 OU 합법 세트로 주장하지 않는다. 4순위는 지정한 완전한 가능세계 집합에 한정하며 숨은 실제값/미래를 입력하지 않는다.
확정 사건/난수 가능/정보 부족을 구분하고, 5순위는 입력에 명시한 결정적 조건 또는 모든 지정 분기를 판정한다.
모든 자료는 학습pool이며 독립 성능·배틀 효과를 평가하지 않는다. 기존 dataset/split/봉인·Blocked 재개0.

## 완료 기준

- [x] 5개 묶음 생성, 커버리지와 제외 범위 기록
- [x] oracle 및 독립 예상값 대조, 경계·대조 사례와 의미 검토
- [x] native token/라벨 분리/metadata 누출/저장 대응 및 CPU CE 검증
- [x] README/한국어 CSV/manifest/검증·출처/ZIP 제공, 문서·상태·색인 갱신

## 진행과 중단

INDEX/CHARTER/매뉴얼/RD/주제 계약과 EP169,134,140,163 및 상태/계획 색인을 확인했다.
실제 경기 평가가 아닌 CPU 제어 규칙 자료이므로 EX·C047 viewer는 해당 없음.
의존성·oracle 불일치는 해당 자료 내보내기를 차단하고 실패/교정을 기록한다.
독립 구현은 파일별 위임하고 공유 빌더·4/5순위·통합 검증은 주 에이전트가 담당한다.

## 완료 결과

우선순위별517/2037/455/399/720문항, 총4128문항·29규칙군을 생성했다.
고정 엔진 대조와 독립 예상값 검증, 별도 에이전트의99대표 의미 사례 검토 및 최종4128저장 대응 검토를 통과했다.
입력245~564토큰, 2~7후보이며 metadata 누출·정답 completion·입력 절단0이다.
P4 초기 기술 슬롯 누락은 차단·교정하고, P1 입력 생존 조건과 P3 명중/큐 조건을 내보내기 전에 정리했다.
우선순위별 choice/native token, 합본, CSV, README, manifest와 ZIP을 제공했으며33봉인파일·ZIP CRC를 확인했다.
실제 모델 학습·GPU·API·서빙 변경0이다. 합성 학습pool이며 모든 Gen9 상호작용·실전 효능 주장은 없다.
[보고](../../../exec-plans/evidence/ep201/report.md) · [전달](../../../exec-plans/evidence/ep201/delivery.json) · [내보내기 검토](../../../exec-plans/evidence/ep201/export-review.json).
