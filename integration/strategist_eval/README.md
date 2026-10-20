# Strategist 첫 배틀 실행기

EX-106 전용 `scripts/strategist-eval {download|prepare|execute|status|export}`.
조건·예산·중단·해석 원문은 project_context/experiments/EX-106-strategist-first-battle.md.

- download: 고정 Qwen revision 내려받기 및 원격 파일 정체성 확인.
- prepare: 보관 adapter 확인, EX-089 일정/팀 복사, 저장 관측 입력 구성·CPU 토큰화, 소스 snapshot.
- execute: 단일 GPU0 서버·6회 연결 검사·동결·새32경기·감사·뷰어·정리·봉인. 실행 receipt 존재 시 재개 금지.
- status: 저장 상태만 읽는다.
- export: 원자료에서 보고/뷰어를 생성한다. 봉인 후 수정은 별도 provenance로 다뤄야 한다.

입력/후보는 공식 snapshot과 같은 공개prefix에서 만든다. public_facts_v6는 공개 사실 추적만
재사용하며 JEV 입력·계산·Choice head를 호출하지 않는다. 출력 오류는 독립 seeded 대체이며
기술 오류는 fail-closed다. 모델 서버 stdin/stdout JSONL은 요청1회/응답1회이며 재전송하지 않는다.
Abyssal은 별도 프로세스의 기존 seed/선봉 정책을 유지하고 테라 후보/전송만 차단한다.
뷰어 입력·원문·선택과 텍스트 리플레이는 완전 오프라인, Showdown 애니메이션은 외부 자산이 필요하다.
