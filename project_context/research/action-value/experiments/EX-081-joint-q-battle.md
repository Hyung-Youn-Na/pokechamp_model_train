# EX-081 — EX066 epoch3 재현성 복구·GPU0 실제 test20

- 상태: Completed
- 생성일: 2026-10-08
- 책임자: Codex
- 승인: [D-129](../decisions/D-129-joint-q-battle.md), 현재 사용자 계획 구현 지시
- 실행 계획: [EP-133](../plans/EP-133-joint-q-battle.md)
- 적용: RD §8/11.1/11.2, C-018/C-046/C-047/C-052/C-062

## 질문·분모·해석

EX066 선택 epoch3를 원 예측 허용오차 안에서 다시 불러온 뒤, 고정 test20에서 매 결정
최대 q를 선택하는 정책의 승패를 탐색적으로 평가한다. q는 Abyssal 후속 정책 조건부 점수다.
학습 효과나 일반 Gen9 OU 효능을 사전 전제하지 않는다. 추가 학습·원 오프라인 test는 제외한다.
EX065 `versions/collection-v5/manifest.json`의 split=test 원순서20행을 사용한다.
manifest SHA256은 `e1d1f15a64746e0ce5888de42846cf3f16eb25638f64183cbdae1ed6a5ea71ef`다.
상대100817·7627·38229·48494·5742 × seed_index0…3, 자기 packed 팀/own.text·p2,
원 simulator_seed·양 actor_seed를 유지한다. 새 팀/seed 선택·진영 교환은 없다.
새 모델 예정20경기, 기준선은 EX065 해당 Abyssal20경기다. 기준선 결과는 설정 동결 뒤
분석에만 읽는다. 저장 test 입력/타깃·private root를 모델/선택·설정 결정에 사용하지 않는다.

## 모델·입력·실행 조건

체크포인트는 `.pokechamp-data/experiments/ex066-joint-q-training/training/epoch-3/`다.
원 files.json 전체와 metadata의 Base/tokenizer/가중치 해시를 검증한다.
Base는 Qwen/Qwen3.5-4B-Base revision `1001bb4d826a52d1f399e183466143f4da7b741b`다.
기존 EVE 환경·renderer/JointValuePolicy, BF16 base/forward·FP32 LoRA/head/readout,
unmerged·use_cache=False·eval/no_grad·관측당 한 forward를 유지하며 optimizer update0이다.
물리 GPU0만 사용하고 CUDA_VISIBLE_DEVICES=0·실제 UUID·소유 lock을 검증한다.
원 metadata의 physical_gpu=1은 학습 provenance로 보존하며 새 실행 자원과 구분한다.

입력은 공식 관측→JointInput→pokemon-joint-q-readout-v1이다. 공개 상태/전체 후보를
한 번 렌더링하고 ID별 Q_VALUE= hidden state에서 독립 sigmoid q를 읽는다.
원 질문·순서·tokenizer와32768토큰 무절단을 유지한다. 최댓값, 정확한 동률은 원후보 첫 ID다.
단일 후보도 호출하며 전송 전 rqid·최신 합법 명령을 재확인한다. 원입력·token/prompt hash·
모든 q·선택·실제 전송을 보존한다. loopback 서버·별도 CPU worker·소유 pinned Showdown으로
gen9ou singles·timer off·기존 Abyssal 상대·합법 Tera 허용·동시성1을 적용한다.
외부 API·fallback·HTTP 재시도0이다.

## 복구·qualification

저장 validation320관측 중319개 q는 원 재로딩과 비트 동일하며
validation-t47268-s0-o0017에서만 최대차이0.0018912255764007568, 최고 후보 선택 변화0이었다.
이 저장 자료 진단은 기존 실패 취소가 아니다. 해당 관측부터 로딩·정밀도·backend/상태 차이를 재현한다.
교정은 새 모듈/별도 버전에 기록하며 원 가중치·입력·허용오차는 유지한다. 단계별 사전 CPU 검사와
교정 독립 재현 뒤 서로 다른 두 프로세스에서 원 validation320관측/2991후보 전체를 평가한다.
각 프로세스와 원 epoch3 예측의 최대 절대 q 차이≤1e-4, 두 프로세스 사이도≤1e-4여야 한다.
마지막 통과 프로세스를 대전 서버로 유지하고 source/config/모델·가중치 불변을 검증한다.
표본 제외·반올림·기준 완화·prompt 변경·재학습으로 통과시키지 않는다.
같은 예산의 독립 원인 진단/교정·validation 재검증은 허용하되 실패를 삭제하거나 성공만 골라 기록하지 않는다.
교정할 수 없거나 기준이 계속 실패하면 배틀0·미완료로 종료한다.

## 예산·시계·실패·복구

사전 구현·해당 단계 CPU 검사 후 첫 GPU 진단 프로세스 시작부터28800초(8시간)를 누적한다.
진단·재검증·복구·서빙·대전·감사·최종화를 포함하고 재시작/새 버전에도 초기화하지 않는다.
요청600초·경기3600초, 마지막1800초는 최종화에 예약한다. 경기상한+정리여유가 남아야 새 경기를 시작한다.
GPU0 다른 작업 점유 시 대기하며 다른 GPU 이동/다른 소유자 프로세스 종료0이다.
GPU 소유권 대기 전에는 첫 시계를 시작하지 않고 시작 뒤 대기는 누적한다.
각 경기 시도1회·총20회, 추가 smoke·재경기·재수집0이며 영속 admission과 첫 시계를 보존한다.

RD11.1/C-018을 적용한다. 수집 전 도구 교정은 별도 source·재현/회귀 후 같은 예산에서
허용하고 기존 STOP을 삭제하지 않는다. 수집 후 평가 구현 결함은 저장 자료 전조건 재분석으로 교정한다.
공유 입력·서빙·전송·무결성 결함은 의존 수집 중지, 영향 자료는 무효/미완료로 보고한다.
배틀 재수집0이다. 나쁜 합법 선택은 실행하고 실행 불가능한 모델 응답은 해당 경기 실패로
격리하여 독립 경기를 계속한다. 시간초과/실행 실패를 패배로 변환하지 않는다.
소유 서버/worker/Showdown만 종료하고 부분 원자료·오류·시계·예산 소진을 보존한다.

## 지표·검증·완료

주 지표는 유효 완료의 p2 승/무/패와 `(wins+0.5*draws)/valid_completed`다.
예정/시도/정상/유효/실패/무효/미실행과 팀별 결과·Tera·지연·GPU 사용을 보고한다.
기존 Abyssal과 공통 유효 대진을 game_id로 대응하고5팀 cluster bootstrap20000회·seed20261008의
percentile95% 구간을 보조 보고한다.5군집·역사 실행 방식·정책/Tera 차이로 학습 단독 효과를 주장하지 않는다.
CPU 검증은 선봉/기술/Tera/일반·강제교체, readout/ID/동률, 정보 누출, 길이 초과,
불완전/비유한 응답, timeout/stale 무전송·예산/admission을 포함한다.
모든 결정의 공식 입력 재생·q·선택·실제 전송 감사와 checkpoint/실행 가중치 전후 불변을 검증한다.
20경기 유효완료·전수 감사·한국어 보고·봉인·C-047 오프라인 뷰어·소유 자원 정리가 완료 기준이다.
설명 검토는 기본 제외다. 미충족 시 부분 결과/미완료를 보고하며 원 EX066을 Completed로 바꾸지 않는다.

## 증거와 결과

산출물 `.pokechamp-data/experiments/ex081-joint-q-battle/`, 검증 `project_context/exec-plans/evidence/ep133/`,
최종 뷰어 `exports/battle_viewers/ex081-baseline-v2/`에 보존한다. 최초 `final/`과
`exports/battle_viewers/ex081/`는 기준선 누락 당시의 첫 분석/열람본으로 보존한다.

첫 GPU 시계는2026-10-08 09:41:13 KST다. 원경로12forward 진단에 이어 서로 다른 두 프로세스가
각320관측/2991후보에서 원 epoch3 예측과 비트 동일했고 상호 최대차이도0이었다.
가중치·입력·수치 backend 변경0이다. GPU0 재qualification 통과이며 과거 GPU1 실패 원인은 미확정이다.

| 예정 | 시도 | 정상/유효 | 실패 | 무효 | 미실행 | 승·무·패 |
|---:|---:|---:|---:|---:|---:|---|
| 20 | 20 | 20 | 0 | 0 | 0 | 0·0·20 |

970결정·6629후보·실제 전송970건의 공식 입력/계산·원 HTTP·token/readout·최댓값/동률·전송을
전수 감사했다. fallback/재시도0, p2 Tera20회·이후795결정이다. 배틀 모델 요청970회,
전체 모델 forward1622회(진단12+qualification640+배틀970)이며 추가 학습/모델 test 호출0이다.
배틀 GPU 추론3022.018초, 전체 GPU 추론5281.716초다. Base/LoRA/head/checkpoint/source 불변을 확인했다.

첫 분석은 EX065 v5의 `games → ../../games` 보존 링크를 범용 경로 검사로 거부하여 기준선을
누락했다. RD11.1/C-018에 따라 첫 보고·source·뷰어를 보존하고 동일 원실험 계보·버전 seal을
검증하는 capture 경계만 교정했다. 원 대진·팀·seed·terminal 결과20쌍을 저장 자료에서 재분석했다.
기존 Abyssal은11승0무9패, 점수차−55%p·사전5팀 cluster bootstrap95%[-70,-40]%p이며
독립 계산과 일치한다. 이 역사 구성 비교에서 개선을 보이지 않았으며 학습 단독 효과로 해석하지 않는다.

첫 브라우저 검사의 초기화 대기 결함도 원본을 보존한 별도 검사 교정으로 처리했다.
예상 DOM 준비를 기다린 뒤 동일한 원 검증을 적용했으며 뷰어/데이터 변경0이다.
이동·오프라인 실제 브라우저에서20경기·970결정·6629후보 전부 확인했고 오류0이었다.
소유 서버/worker/포트/lock·GPU0을 반환하고5368파일을 봉인·전수 대조했다.
첫 GPU 시계부터 약3시간25분으로8시간 이내에 완료했다. 원 EX066의 오프라인 test 미완료와
Blocked/실패 판정·원자료·가중치는 보존한다.

[정정 최종 보고](../../../../.pokechamp-data/experiments/ex081-joint-q-battle/corrections/baseline-v2/final/report.md) ·
[정정 provenance](../../../../.pokechamp-data/experiments/ex081-joint-q-battle/corrections/baseline-v2/final/receipt.json) ·
[오프라인 전수 검증](../../../../.pokechamp-data/experiments/ex081-joint-q-battle/corrections/viewer-check-v3/viewer-offline.json) ·
[완료·봉인](../../../exec-plans/evidence/ep133/completion.json) ·
[최종20경기 뷰어](../../../../exports/battle_viewers/ex081-baseline-v2/index.html).
