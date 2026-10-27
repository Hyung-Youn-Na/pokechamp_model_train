# EX-062 — Qwen 최종 LoRA 로컬 배틀 연결 검증

- 상태: Blocked
- 등록일: 2026-09-28
- 승인: 현재 사용자 제공 계획 구현 지시 / D-099 / EP-103

## 질문·분모·해석

EX-061 최종 모델을 실제 GPU HTTP 서빙하고 공식 관측에서 합법 행동을 선택·전송하여
고정2경기를 완주할 수 있는가? 입력22관측·167후보의 재생은 개발 자료 기술 대조다.
새2경기 승패는 연결 검증 결과로만 보고하며 독립 평가/성능 개선 판정에는 사용하지 않는다.
학습 q의 고정 숨은 상태·양측 Abyssal 후속 조건을 유지하며 모델 자체 전경기 승률로 해석하지 않는다.

## 동결 protocol

- Qwen/Qwen3.5-4B revision851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a,
  `.pokechamp-data/training/ex061/train/epoch-3-adapter`의 저장 seal 대조.
  adapter_model SHA256 fdc82e7e3cc3bc564b2baafc26dd888a3c540f2f13428bac2f204d592297ee23.
- EVE 가상환경·물리 GPU1 한 장. FP32 base/adapter·BF16 forward·FP32 A/B readout,
  eval/no_grad·후보별 독립 forward·비사고 template·모델 한 번 로딩·가중치 update0.
- HTTP127.0.0.1:8765·직렬 GPU 요청, 요청600초·전체 시간 상한 없음·재시도/대체0.
  JEV v4 전문 관측과 순서 있는 후보를 InputExample/render로 전달한다.
  금지 타깃/집계/snapshot/provenance 제외·16384토큰 초과 오류·절단0·단일 후보도 평가.
- 검토 완료 목록의 `team_1.gen9ou_team`, `team_10.gen9ou_team`을 pinned Gen9 OU로 검증한다.
  두 경기 p1/team1·p2/team10, 첫 Qwen p1·둘째 Qwen p2, Abyssal은 다른 진영.
  게임 seed `18280,52471,51036,2470`, p1 actor seed20260930·p2 actor seed20260931,
  진영별 Python/NumPy/hash seed·Abyssal 독립 프로세스·순차 실행.
- 소유 임시 Showdown worktree·8109·timer off. 시작 전에 source/model/input/team/config hash 동결.
  선택은 최대 독립 q, 동률 원후보 순서. 전송 직전 rqid·현재 합법 명령 재확인.
- 보존: 원입력·후보·최종 prompt/token hash·q·선택·실제 전송·공식 cutoff/protocol·지연·GPU 사용량,
  설정·실행 source·리플레이·뷰어. 금액 단가 미제공으로 금액 미산정·외부 API0.

## 검증·중단·복구

입력/HTTP 검사는 선봉·기술·테라·일반/강제교체·순서/동률·금지 필드·길이 초과·불완전 응답·
timeout·stale request의 무전송을 포함한다. GPU 대조는 저장22관측/167후보의 전체 token/prompt hash와
HTTP q를 EX-061 재로딩 예측에 대조(최대차이≤1e-4), 가중치 전후 fingerprint 불변을 확인한다.
고정2경기 정상 종료·전수 입력/선택/전송 감사·C-047 뷰어 오프라인 열람·자원 정리가 완료 기준이다.
승패·나쁜 합법 선택은 기준에 영향을 주지 않는다. 보충/재수집0.
RD11.1/C-018의 GPU 전 구현 결함 교정은 독립 검사 후 허용하며 원실패를 보존한다.
실제 수집 중 공유 입력·서빙·무결성 결함은 의존 실행 중단(조건 변경 방지),
실행 불가능 모델 응답만 경기 격리한다. source/처치 변경 후 자동 재경기0.
시계는 최초 GPU 서빙 로딩부터 누적 측정하며 예산 갱신 없이 실패/부분 결과·정리·미충족 기준을 보고한다.

## 결과·미완료

GPU22관측/167후보의 토큰·q 전수 일치(최대차이0.0), 가중치/adapter 불변·업데이트0이다.
배틀은 첫 preview의 worker cwd 오류로 입력 전에 중단하여 정상0/2·시도1·실패1·미실행1이다.
실제 모델 입력/요청/선택/전송0, 추가 배틀/재수집0이며 승패는 미산출이다.
교정본의 실제 Pokémon/세트 로딩 검사·관련26검사·부분 뷰어/오프라인 열람·봉인·정리를 완료했다.
고정2경기 정상 종료와 실제 행동 전수 감사 미충족으로 Blocked를 유지한다.
[보고](../../../exec-plans/evidence/ep103/report.md) · [부분 뷰어](../../../../exports/battle_viewers/ex062/index.html).
