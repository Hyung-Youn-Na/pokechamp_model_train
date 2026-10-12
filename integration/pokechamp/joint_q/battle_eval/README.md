# EX081 공동 q 모델 배틀 평가

EX066 epoch3를 변경 없이 GPU0에서 서빙하고 EX065 test20의 고정 대진을 실행한다.
실행 조건·8시간·재현 gate·실패/복구는 [EX-081](../../../../project_context/experiments/EX-081-joint-q-battle.md),
진행은 [EP-133](../../../../project_context/exec-plans/completed/EP-133-joint-q-battle.md)을 따른다.
원 학습 실행기/체크포인트·GPU1 metadata와 과거 실패는 유지한다.

```bash
scripts/pokechamp-joint-q-battle prepare
scripts/pokechamp-joint-q-battle run
scripts/pokechamp-joint-q-battle status
scripts/pokechamp-joint-q-battle finalize
```

prepare는 새 CPU 검증 receipt·원본 무결성과 기존 manifest 대진을 동결한다.
run은 qualification이 없으면 두 새 GPU 프로세스의 전체 validation을 비교한 뒤, 두 번째 서버로
20경기를 한 번씩 실행한다. 별도 qualify는 통과한 두 번째 서버를 유지하며 run에서 해당
PID/시작시간/source/모델 identity만 다시 사용할 수 있다. 이미 admission이 있으면 재실행을 거부한다.
diagnose는 승인된 원 불일치 관측과 이웃의 validation 진단이며 대전/독립 test가 아니다.
모든 GPU 단계는 첫 clock.json을 공유하고 단계별 새 버전/프로세스에도 누적 상한을 유지한다.

GPU0이 사용 중이면 기다리고 다른 GPU/소유 작업을 종료하지 않는다. 모델 서비스는 EVE 환경,
관측/대전/감사는 기존 PokéChamp 환경을 사용한다. 환경 설치/공유 source 교정 없이 새 모듈에 연결한다.
loopback `/health`는 identity만 제공하고 `/evaluate`는 원 JointInput을 받아 모든 후보의 q를 계산한다.
직렬 forward와 독립 health 응답을 분리하고 timeout/stale 응답은 전송하지 않는다.

finalize는 원자료에서 독립 감사·지표·한국어 보고·뷰어를 만든다. 최종 완료 판정은 이어서
실제 이동 후 오프라인 브라우저 확인·소유 프로세스/포트/GPU 정리·전체 봉인 receipt까지 확인한다.
원 실험 상태를 완료로 바꾸거나 배틀 결과를 학습에 자동 편입하지 않는다.

## 이번 실행의 최종 결과와 정정

GPU0의 두 프로세스 전수 q 재현 최대차이0, 실제20경기 유효완료·0승20패다.
기존 Abyssal20경기는11승9패이며 역사 구성 비교를 학습 단독 효과로 해석하지 않는다.
첫 보고의 보존 symlink 경계 오류는 `outputs.correct_baseline(root)`에서 원 version seal과
같은 원실험 계보를 검증하여 저장20쌍만 정정했다. 일반 경로 검사는 유지하며 원 보고/뷰어는 보존한다.
정정 receipt는 `corrections/baseline-v2/final/`, 최종 열람본은
[ex081-baseline-v2](../../../../exports/battle_viewers/ex081-baseline-v2/index.html)이다.
`viewer.export(..., final_directory=...)`는 해당 receipt와 지표/보고를 결합한다.
브라우저 검사는 초기 DOM 준비 후 원래의 정확한 입력·q·선택·전송 검사를 적용한다.
전체20경기·970결정·6629후보의 이동/오프라인 검증·원자료 봉인·소유 자원 정리가 완료됐다.
원 admission과 clock은 보존하며 같은 실행을 재수집하지 않는다.
