# EP-104 — Qwen 학습 원대진 실전 배틀

- 상태: Completed
- 생성일: 2026-09-29
- 책임자: Codex
- 승인: 현재 사용자 지시 / D-100
- 관련: C-049 / EX-063 / EX-061

## 목표·범위

EX-061 최종 모델로 학습 원대진 한 경기를 끝까지 실행하고 승패·후보별 q·전송을 보고한다.
INDEX/CHARTER·STATUS/색인·겹치는 active EP-103/062/064/075/077/080/057/054와 관련
RD/C/ARCHITECTURE·원 EX-060/061을 확인했다. 상세 조건/분모/시계/복구/해석은
[EX-063](../experiments/EX-063-qwen-training-matchup.md) 원문을 따른다.
parent integration의 runner·viewer·검사/README를 확장하며 기존 봉인·가중치·submodule·Blocked는
보존한다. 별도 agent 위임 없음.

## 완료 기준

- [x] 원대진/성별/진영/seed·HTTP 및 무전송 검사 통과
- [x] 새 소유 서버 GPU22관측/167후보 대조·가중치 불변
- [x] 고정1경기 정상 종료·전수 입력/선택/전송·토큰 감사
- [x] 한국어 보고·재현 설정/봉인·C-047 뷰어/이동 후 오프라인 열람
- [x] 소유 서버/배틀/worktree 정리·GPU1 반환

## 진행·검증

- 2026-09-29 — 원 JEV 12턴 패배·p1/team6/p2/team2·원seed를 확인하고 새 실행 등록. 준비 등록.
- 원대진 packed team·공개 성별의 원 EX-060 manifest 독립 대조·Gen9 OU 검증 및 관련28검사 통과. 준비 중 변환의 ID 대소문자 차이는 semantic unpacked 대조와 Python packed 재대조로 검증했다. 실제 수집 영향0. 새 소유 서버 GPU22관측/167후보 전수 prompt/token hash 일치·최대 q 차이0.0. 배틀12턴 패배·18결정/121후보. 원 감사 실패의 끝 빈 줄 누락을 평가 코드에서만 교정하여29검사·전수 감사·오프라인 뷰어 통과. 원 자료/실패/봉인 보존·별도 정정 결과, 재수집0.

## 중단·복구

RD11.1/C-018·RD11.2/C-046 적용과 한도·실행기 지원은 EX-063을 참조한다.
준비 결함은 보존/독립 검증 후 교정, 실제 수집의 재경기0. 기존 Blocked는 재개하지 않는다.

## 결과·증거

모든 완료 기준 충족. [최종 보고](../../../exec-plans/evidence/ep104/report.md) · [정정 결과](../../../exec-plans/evidence/ep104/result-corrected.json) · [뷰어](../../../../exports/battle_viewers/ex063/index.html). 소유 자원 정리·GPU1 반환·기존 봉인 보존 완료.
