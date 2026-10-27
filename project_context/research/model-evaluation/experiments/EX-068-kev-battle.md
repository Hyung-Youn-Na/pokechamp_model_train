# EX-068 — Kev-4B pokechamp r1 연결 smoke

- 상태: Completed — D-109 조건의 연결 수락 검사 완료. 원 unmerged gate 실패는 보존.
- 등록일: 2026-09-30
- 승인: D-108의 최초 서버 승인, D-109의 fused·merged 추가3관측 및 조건부1경기 후속 승인.
- 실행 계획: [EP-111](../plans/EP-111-kev-battle.md)
- 목적: 입력·서빙 예측·최대값 선택·실제 명령 전송의 연결 검증. 효능 가설/승률 추론 없음.

## 사전 조건과 분모

EX-065 `versions/collection-v5` manifest의 자기 팀/순서 p2, 기존 Abyssal p1, gen9ou singles다.
상대는 reviewed108 중 EX-065의20팀 밖에서 파일명 숫자 오름차순 첫 합법 팀을 고정한다.
팀/seed·source/정적 자산/모델 파일 hash는 실행 전 manifest에 봉인한다. 새 seed namespace는
`ex068-kev-smoke-v1`이다. 한 경기만 시도하며 진영 교환·효과 비교·추가 수집은 하지 않는다.
Tera는 합법 후보에 포함하여 허용하고 필터링하지 않는다. 사용 턴·선택 비율과 Tera 이후
결정 수를 기록한다. 이는 학습 분포 밖 상태가 포함될 수 있는 연결 검사다.

선행 gate: validation의 선봉/일반 행동/강제교체 첫 관측을 순서대로 고정하여 재생한다.
관측 종류가 없으면 누락을 보고하고 다른 test 관측으로 대체하지 않는다. 원 private root에서
official/prefix만 읽고 자기 팀은 manifest에서 얻는다. live generator의 payload_json UTF-8이
저장 model_input의 compact JSON과 byte 단위로 같아야 한다. 원 Abyssal 선택은 입력·선택에
사용하지 않는다. Kev `4b-kev4b-delta-dev/rows.json`의 같은 ID/action p[1]과 서버 noul을
소수 넷째 자리에서 비교하며 차이0만 통과한다. Kev test 파일은 읽지 않는다.

## 원 unmerged 실행의 고정 서빙과 실행

- run `/ref/kev/runs/pokechamp-r1/4b-kev4b-delta`, base revision
  `Qwen/Qwen3.5-4B-Base@1001bb4d826a52d1f399e183466143f4da7b741b`
- bf16, adapter unmerged, temperature1, 문자열 state, chat template/system prompt/criteria 추가0.
- `KEV_MERGE=0 KEV_FUSED=0`을 명시한다. bb7185c의 `serve.py`는 설치된 FLA0.5.2를
  발견하면 fused를 기본 활성화하고 `checkpoint.py:281`에서 bf16 adapter도 merge한다.
  따라서 사용자가 준 기본 명령과 unmerged 설명이 현재 코드에서 일치하지 않는다.
  명시된 unmerged 조건을 우선 고정하며 dev 예측이 다르면 gate 실패 증거를 보존하고 배틀을
  시작하지 않는다. 입력 동일성이 입증된 수치 차이를 질문/state 오류로 단정하지 않는다.
- loopback `http://127.0.0.1:8019/v1/systemone`; `/v1/models`와 로컬 실행 provenance 대조.
- GPU3 전용, 서버가 실행 중이면 다른 GPU3 작업0. 서버 시작 전 준비 완료 후 별도 승인 필요.
- 단일 경기·동시성1·타이머 off·단일 후보도 Kev 호출·대체 선택0·HTTP 재시도0·재경기0.
- 요청 timeout600초. 배틀 누적 상한7200초, 최초 시계 보존. validation 요청은 고정3관측
  각1회(관측 종류 부재 시 가능한 분모를 명시), 같은 프로세스 준비 확인 후 배틀 진입.

## 검증·중단·복구·보고

모든 결정의 JointInput hash, 요청/응답·후보별 p·최댓값/명령·지연·rqid/합법성 재검증·wire를
저장한다. noul은 실행 근거이므로 누락/불량 값은 UnusableChoice로 경기 실패 격리하고
전송하지 않는다. 전략적으로 나쁜 합법 선택은 계속한다. 입력·서빙·무결성 공유 결함은
의존 작업을 중지한다. RD11.1/C-018·RD11.2/C-046 적용, 실제 재수집 허용0이며 CPU 검증/평가
도구 결함은 원 evidence 보존과 독립 검사 후 같은 사전 기준으로 복구한다.

예정/시도/정상/실패/미실행을 분리하고 모든 결정 입력·최댓값·전송·fallback0을 감사한다.
정상 종료 시 C-047의 로컬 뷰어·리플레이·목록/출처·오프라인 열람을 완료한다. 종료 결과와
Tera/지연/토큰은 기술 진단이며 성능 향상 판정에 쓰지 않는다. 설명 평가는 미평가(기본 제외).
소유 Showdown/worker만 종료하고 사용자 서버는 종료하지 않는다. 요청/원자료를 새 학습에 쓰지 않는다.

## 원 unmerged 실행 결과

validation 선봉/일반 행동/강제교체3관측·24후보의 live 생성 bytes와 Kev 내부 토큰열은
동일하다. 승인된 unmerged 서버의 첫 관측6후보는 저장 dev 값과 소수 넷째 자리에서
모두 달랐다. validation 예정3·시도/응답1·통과0·실패1·미실행2, 배틀 예정1·시도0·미실행1이다.
추가 요청·재시도·재수집0이며 소유 서버 종료/GPU3 반환과 GPU1 기존 실행 보존을 확인했다.
성능·실전 fallback·실전 뷰어는 미평가다. 구현/CPU 검증과 중단 정리가 전체 수락 완료를 뜻하지 않는다.

실행에 사용한 [동결 protocol](../../../../.pokechamp-data/kev/ex068-v2/source/project_context/experiments/EX-068-kev-battle.md),
원 준비본 `ex068`과 PID 검사 교정본 `ex068-v2`를 보존했다. 당시 dev의 정확한 merge/fused
설정은 미확인이다. 입력 오류로 단정하거나 기준/조건을 바꿔 gate를 통과시키지 않았다.
[EP-111 중단 보고](../../../exec-plans/evidence/ep111/report.md)와
[종료 원장](../../../exec-plans/evidence/ep111/closure.json)에 수치·근거·남은 조건을 기록한다.

## D-109 추가 실행 — ex068-v3

원 불일치 보고 후 사용자는 fused·merged 최대3관측 재검증과 전부 일치 시1경기 실행을
명시 승인했다. 새 실행은 `KEV_MERGE=1 KEV_FUSED=1`, bf16/T1, torch backend,
CUDA graphs1, date facts0, LoRA scale1을 고정한다. `/ref/kev/.venv/bin/python`을
cwd `/ref/kev`에서 GPU3만으로 실행하며 원 모델 파일은 수정하지 않는다.

원 준비본과 같은 세 관측·24후보의 state/질문/순서를 그대로 재검증한다. 각 관측 최대1회,
추가 최대3요청이며 첫 불일치/기술 실패에서 의존 gate와 배틀을 중지한다. 원 dev p와
소수 넷째 자리 차이0 기준을 유지한다. 원1요청과 새 요청을 합산하며 반복 관측을 독립
표본으로 세지 않는다. 원 `ex068-probe-admission.json`은 보존하고 새 전체 원장
`ex068-fused-probe-admission.json`은 D-109·원 admission/hash·원 첫 시계·누적1요청과 연결한다.

팀·p2·상대 team1·seed·Tera·600초 요청 제한·7200초 배틀 누적 상한·동시성1은 원 준비와 같다.
전체 배틀 상한은 여전히1경기이며 `ex068-battle-admission.json`을 공동 사용한다. 원 배틀
시도0이므로 새 gate 통과 뒤 미사용1경기에만 진입한다. HTTP 재시도·fallback·추가 경기0이다.
원 시계·비용을 삭제하거나 새 폴더로 초기화하지 않으며 gate 요청/서버 시간과 배틀 시계를
구분해 누적 보고한다. 새 원문·코드·승인·모델/팀/입력 hash를 요청 전에 동결한다.

원 `ex068`/`ex068-v2`와 [첫 보고](../../../exec-plans/evidence/ep111/report.md)의 봉인은 보존한다.
추가 실행 준비·검증·결과는 `ex068-v3`와 `exec-plans/evidence/ep111-fused/`에 별도로 둔다.
정상 경기의 전수 감사·C-047 뷰어·오프라인 검증과 직접 시작한 서버/GPU3 정리를 완료한다.
기존 실패는 무효화하지 않으며 새 실행으로 원 unmerged 서빙을 통과한 것으로 표시하지 않는다.

## 추가 실행 결과와 완료

새 validation 예정/시도/통과3관측·24후보의 입력 bytes·질문·요청 순서와 dev p가 소수 넷째
자리까지 일치했다(최대차이0.0000). 원1요청과 합산한 validation 호출은4이며 고유 관측은3이다.
같은 프로세스/모델·원 자기 팀/p2·상대 team1·seed에서 전체 미사용1경기를 실행했다.
배틀 예정/시도/정상/유효 완료1, 실패/미실행0,51턴 Kev 패배다.57개 결정·348후보에 대해
실제 HTTP/응답·rqid 재검증·선택·transport/wire 각57건을 전수 확인했고 fallback·재시도0이다.

Ting-Lu가2턴 Ghost Tera를 사용했다. 선택1/57, 가능 결정 중1/2, 사용 이후 결정54개다.
실전 input/output tokens는831,377/8,356, client 평균 지연1.582초, 서버 평균1.528초다.
경기/worker 정리126.516초와 이후 감사/뷰어 검증을 구분한다. 원 실패를 포함한 모델 요청은
총61건이며 첫 시계와 서버 생존 구간을 최종 보고에 합산했다.

공식 관측 재생 전수 감사·독립 원문 감사·이동 후 오프라인 뷰어 검증이 통과했다. 브라우저
초기화 대기 부족으로 생긴 첫 검사 실패는 보존하고 DOM 준비 대기만 보강하여 검증했다.
제품 코드/원본/뷰어 변경0이다. 소유 Kev/Showdown/worker 종료·GPU3 반환과 기존 GPU1
실행 보존을 확인했다. 설명 평가는 미평가이며 이1경기와 새 설정 묶음으로 성능·인과 효과를
주장하지 않는다. 후속 실행·학습 전용은 현재 범위에 포함하지 않는다.

[최종 보고](../../../exec-plans/evidence/ep111-fused/report.md) ·
[완료 검증](../../../exec-plans/evidence/ep111-fused/verification-final.json) ·
[경기 뷰어](../../../../exports/battle_viewers/ex068/index.html).
