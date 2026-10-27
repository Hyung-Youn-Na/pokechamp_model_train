# EP-169 — Showdown 규칙 Q&A·State 데이터셋 v1

- 상태: Completed
- 생성/완료일: 2026-10-19
- 책임자: Codex
- 승인: 현재 사용자의 전체 계획 구현 지시, [D-159](../decisions/D-159-showdown-ruleqa.md)
- 연구선/branch: research/model-training; checkout /workspace
- 시작 commit: a4659bf298c7935714f9fbd25246db2d831c5926; 기존 미커밋 변경과 다른 작업 보존
- 환경: pokechamp/.venv/bin/python, 기존 Node, JEV runtime의 로컬 tokenizer; worker≤4
- 출력: /mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/showdown-ruleqa/v1/
- 계약: [C-074](../CONTRACTS.md#c-074-ruleqa), C-067, C-072
- 설계: [규칙 데이터](../DESIGN.md#showdown-ruleqa)

## 목표·범위

영어24규칙군 ×40대조묶음 ×2상황 ×3표현, 공개 State·oracle 근거·학습용 두 형식을 만든다.
새 CPU Showdown 제어 장면만 사용한다. 기존 EX/보관 replay는 학습에 넣지 않는다.
GPU·모델/API·추가 다운로드0, 정상 경기 성적 수집이 아니므로 C-047은 해당 없음이다.
EP-140의 v6/공개정보와 EP-134/163의 모델·tokenizer 환경 보존 경계를 확인했으며 중단 평가를 재개하지 않았다.

## 완료 기준

- [x] prepare/generate/validate/export와48상황/144문항 수직 검증
- [x] 원천1,920상황/5,760문항, 규칙별 묶음32/4/4
- [x] oracle·조건·설명·정보경계·대조/불변·교정 허용 범위·중복·두 tokenizer 전수 검증
- [x] 96상황 의미 검토, canonical/splits/messages/선택형/manifest/제외 목록/한국어 보고
- [x] 내보내기 전수 대조·후보 순서·엄격 JSON 확인, source/실패/교정 보존 및 문서 연결

## 진행과 교정

1. D-159·RD·C-074를 등록하고 공식 관측→공개 사실→v6→names-v1을 재사용했다.
2. 수직 검증에서 저장 순서·unknown 벤치 검증을 교정했다. 전체 확장 전144문항 gate를 통과했다.
3. 첫 전체 수집의86실패를 차단·보존했다. 팀 텍스트 공백/폼 파싱, Iron Ball 특례,
   Balloon 소실 event, 공개 억제 로그 판정을 교정했다. 집중90상황을 검증했다.
4. 교정 전체1,920상황/5,760문항은 오류0이다. 규칙 간 공유 상황을 함께 배정하는 결정적 분할을 적용했다.
5. 96상황을 읽고 짧은 입력의 공개 Mold Breaker 사실, 조건/완전 목록/current 범위 표현을 보강했다.
   같은 물리 명세·관측·계산기/자료에서만 가능한 generate --relabel-from으로 질문을 재생성하고
   보호된 spec/input/result/evidence 불변을 전수 확인했다. 중첩 정렬 교정도 원본과 함께 보존했다.
6. 최종 전수 검사·의미 검토·내보내기 역대조·규칙별 예시·한국어 보고와 상태 갱신을 완료했다.

## 검증과 결과

[검증 요약](../../../exec-plans/evidence/ep169/report.md)과 연결된 dataset manifest/report가 실행 결과의 원문이다.
최종 기준에서 제외/미충족 규칙군0이다. 원천 상황과 그 세 표현, 두 export를 독립 표본으로 합산하지 않는다.
코드·출력·실패본·상세 source hash는 해당 manifest/evidence를 따른다.

## 해석·종결 경계

제어 장면·고정 템플릿 안의 규칙 자료이며 실제 배틀/Thinking 성능 향상은 미평가다.
미지원 예외·Stellar·다른 세대·더블·특수 포맷을 지원한다고 주장하지 않는다.
에이전트 표본 의미 검토는 외부 인간 블라인드 검토가 아니다.
후속 학습/평가는 이 완료의 승인 범위가 아니며 새 지시·등록을 따른다.
