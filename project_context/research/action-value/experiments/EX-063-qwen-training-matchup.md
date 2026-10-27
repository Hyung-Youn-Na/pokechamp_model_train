# EX-063 — Qwen 학습 원대진 배틀 진단

- 상태: Completed
- 등록일: 2026-09-29
- 승인: 현재 사용자 지시 / D-100 / EP-104

## 질문·분모·해석

EX-061 최종 모델이 학습 자료의 원대진에서 실제 합법 행동을 선택하여 어떤 승패를 얻는가?
예정 정상 경기 1개, 진영 교환·보충 경기 0이다. 원 EX-058 battle-19/slot b02-r3-s0는
JEV p2가 12턴에 패배한 경기다. 이번 Qwen p2 결과와 함께 보여주되, 개발 자료에 노출된
대진이고 기존 JEV와 모델/정책이 다르며 학습 전 Qwen 배틀이 없어 학습 효과를 분리하지 않는다.
승패와 전략적으로 나쁜 합법 선택은 연결 완료 기준에 영향을 주지 않는다.

## 동결 protocol

- EX-061 최종 epoch-3-adapter와 C-049의 모델 revision·정밀도·비사고 template·독립 후보
  forward·eval/no_grad·업데이트0·16384토큰 무절단 경계를 유지한다. GPU1만 사용한다.
- 새 소유 서버의 저장22관측/167후보를 EX-061 재로딩 예측과 대조한다. prompt/token hash는
  전수 동일, 최대 q 차이≤1e-4, 전후 가중치 fingerprint와 adapter 파일 봉인 동일이어야 한다.
- 원자료 `.pokechamp-data/jev/ex058-live/battle-19`와 EX-060 manifest의 provenance를 대조한다.
  p1 Abyssal/team6(원 SHA256 6e07e00990a931b9c9863c88affdfd8e1f827d3d75a36964fa5d4364ace1fbf3),
  p2 Qwen/team2(원 SHA256 32ff6e8d060188702f7658151514808405867a178d6ba7c9e1ee60dc5fc56adc).
  공개 preview에서 확정된 성별만 채우며 나머지 세트·순서는 동일한 packed team을 제출한다.
  현재 pinned Gen9 OU validator로 검증하고 원문/제출문/packed hash를 보존한다.
- 게임 seed `64650,46273,35382,36029`, actor seed p1=964798779·p2=2142274391.
  Python/NumPy/hash seed 고정, 소유 Showdown 임시 worktree·8109·timer off·배틀 cwd=/workspace/pokechamp.
- HTTP127.0.0.1:8765, 요청600초·전체 시간 상한 없음·전송 재시도/대체0.
  JEV v4 전문·자기 제출 팀·공개 protocol cutoff만 입력 생성에 사용한다.
  seed·snapshot·상대 실제 세트·target·집계·provenance는 모델 입력에서 제외한다.
- 실행 전 source/data/model/team/config hash 동결. 최대 독립 q·동률 원순서,
  단일 후보도 평가하고 전송 직전 rqid/합법 명령 재확인. 외부 API·추가 학습0.

## 검증·복구·완료

입력/HTTP·무전송 경계는 EP-103 관련 검사를 재실행하고 원대진·진영·성별·seed 및 새 probe
경로를 추가 검사한다. 정상 종료1/1·전수 입력/선택/전송/토큰 감사·C-047 오프라인 뷰어·한국어
보고·설정/원자료 봉인·소유 프로세스/worktree 정리·GPU1 반환이 완료 기준이다.
RD11.1/C-018의 준비 단계 구현/경로 교정은 실패 증거 보존과 독립 검사 후 허용한다.
수집 중 실제 입력/서빙/무결성 결함은 의존 실행을 중지한다. provider 판단 오류는 RD11.2/C-046에
따라 합법 선택은 계속하고 실행 불가능 응답은 이 경기 실패로 기록한다. 재수집·재경기0.
최초 서버 로딩부터 누적 시계를 보존하며 새 시계는 기존 EX-062와 별도다.
런너는 경기 격리/기술 중단·소유 자원 정리를 지원하며 자동 복구 수집은 지원하지 않는다.

## 결과

정정 전수 감사 기준 정상1/1·Qwen 0승0무1패·12턴이다. 실제18입력/선택/전송·121후보,
재시도/대체/재경기/재수집0이다. GPU22/167의 prompt/token hash·q 동일(최대차이0.0),
실제121후보 해시 동일·업데이트0·가중치/adapter 불변·GPU1 반환을 확인했다.
원 자동 감사는 protocol 끝 빈 줄 누락으로 실패했다. 원 결과/봉인을 유지하고 평가 코드만
오프라인 교정하여 전18관측 재계산/선택/전송·29검사·뷰어 이동/오프라인 검증을 통과했다.
상세 분모/교정은 [보고](../../../exec-plans/evidence/ep104/report.md)와
[정정 결과](../../../exec-plans/evidence/ep104/result-corrected.json),
[뷰어](../../../../exports/battle_viewers/ex063/index.html)를 참조한다.
원자료 `.pokechamp-data/qwen/ex063-live/result.json`의 당시 자동 감사 실패는 덮어쓰지 않았다.
모든 완료 기준 충족·현재 소유 실행/감시0이다.
